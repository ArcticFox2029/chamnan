"""Project memory — why the code is the way it is, kept where the code is.

Three categories, and the split is deliberate rather than decorative:

    decisions/  A choice that was made, and why. "Postgres over SQLite because two writers."
    lessons/    Something that cost time once. "The index looks stale until you remap."
    rules/      A constraint this repository works under. "Never add a Cloud fallback for embeddings."

They differ in how they are used, which is the whole reason they are separate directories. A rule
is a standing constraint that should be in front of the agent before it starts, so rules are
injected. A decision or a lesson is looked up when a particular question comes round, so those
contribute a title and are read on demand -- the same economy skills/ and tools/ already use, and
for the same reason: a registry of names costs a line each and buys the ability to load the right
one, while injecting the bodies costs everything and buys nothing extra.

NOT a conversation log. An entry is written deliberately, by a person or by Claude at their
request, because something was worth keeping. If it can be recovered by reading the code or the
git history, it does not belong here.

**No age-based retention, on purpose.** Session records expire because "where I stopped on the
14th" stops mattering; a decision does not. The reason a database was chosen two years ago is
exactly the thing nobody can reconstruct later, and deleting it on a timer would throw away the
most valuable entries first. Growth is bounded at the INJECTION instead: rules are capped by
characters, titles are capped by count, and the store itself is allowed to grow because these
files are small and each one was written on purpose.
"""
import re
from pathlib import Path
import workspace as ws
import mdblock
import state

CATEGORIES = ("decisions", "lessons", "rules")

# Rules reach every session, so they are capped. Roughly a third of state_token_budget's
# char-equivalent (see lib/state.py): a repository with more than this in standing constraints has
# a documentation problem, not a memory problem.
MAX_RULES_CHARS = 1500

# Titles only, for the two categories that are read on demand.
MAX_TITLES = 8


def directory(root, category=None):
    from workspace import workspace
    base = workspace(root) / "memory"
    return base / category if category else base


def entries(root, category):
    """Every entry in a category, sorted by filename for a stable order in diffs and injections."""
    d = directory(root, category)
    if not d.is_dir():
        return []
    # A symlink out of the repository is refused: the workspace travels with a clone, so the
    # link is chosen by whoever wrote the repo. `~/.ssh/id_rsa` behind a `.md` name reached the
    # injected block before this. See `workspace.inside`.
    #
    # `root` is resolved once here rather than once per file inside `ws.inside` -- it is the same
    # value on every iteration of this loop, so re-resolving it per file was pure repeated work,
    # not a safety check. Each file's own path is still resolved fresh per file, which is the half
    # of the check that actually guards against a symlink swapped in between calls.
    try:
        root_resolved = Path(root).resolve()
    except (OSError, ValueError, RuntimeError):
        return []
    return sorted(p for p in d.glob("*.md")
                  if p.is_file() and ws.inside(p, root, _resolved_root=root_resolved))


# `see memory `slug``, `memory: `slug``, or a bare ``slug`` next to the word memory. Written by
# people and by the write skills, in STATE.md, session records, threads and dated logs.
CITATION = re.compile(r"memory[:\s]+`([a-z0-9][a-z0-9._-]*)`", re.I)


def dangling_citations(root):
    r"""[(slug, [(file, line), …]), …] for every ``memory `slug``` reference that names no entry.

    🐛 Nothing detected this class. Found on a real work repository: STATE.md and a dated log both
    cite entries whose files were never created, and all three memory directories there are empty —
    the lesson was described, pointed at, and never written. Someone follows the pointer, finds
    nothing, and the reason it was worth recording is gone.

    Same shape as a MAP.md entry naming a file that no longer exists, and it earns the same
    treatment: reported where a person looks at workspace health rather than injected into every
    session. `chamnan-report` costs nothing on the hot path and already says what the workspace
    holds.

    **Grouped by slug and carrying line numbers on purpose.** One missing entry is usually cited in
    several places, and a report that lists the same slug three times reads as three problems. The
    line number is what makes a false positive cheap: the pattern is deliberately broad — anything
    backticked after the word "memory" — because a missed citation is the failure this exists to
    catch, while a wrong one costs a single glance at the line it names.

    A slug is an entry's FILENAME without `.md`, which is what the write skills produce and what a
    citation is written from. Prose without backticks ("see memory for details") does not match.

    Measured across the four real workspaces on this machine: 3 matches, all 3 genuinely dangling,
    no false positives.
    """
    known = set()
    for category in ("decisions", "incidents", "lessons", "rules"):
        known.update(e.stem for e in entries(root, category))

    from workspace import workspace
    wsdir = workspace(root)
    sources = []
    for pattern in ("STATE.md", "milestones.md", "sessions/*.md", "threads/*.md",
                    "logs/*.md", "memory/*/*.md"):
        for f in wsdir.glob(pattern):
            try:
                if f.is_file() and ws.inside(f, root):
                    sources.append((-f.stat().st_mtime, f))
            except OSError:
                continue

    found = {}
    for _, f in sorted(sources, key=lambda r: r[0]):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # Scanned over the WHOLE text, with the line derived from the match offset. Matching
        # line by line looked equivalent and was not: `memory[:\s]+` admits a newline, so a
        # citation wrapped across two lines is a real and common shape. It cost a detection the
        # moment it was introduced — rancher went from two dangling slugs to one — which is why
        # this is written the slower way on purpose.
        for m in CITATION.finditer(text):
            slug = m.group(1)
            if slug in known:
                continue
            where = (f"{f.relative_to(wsdir).as_posix()}", text.count("\n", 0, m.start()) + 1)
            found.setdefault(slug, [])
            if where not in found[slug]:
                found[slug].append(where)
    return [(slug, places) for slug, places in found.items()]


def case_collisions(paths):
    """Group `paths` whose filename stems are identical except for case.

    🐛 On a case-insensitive filesystem (APFS, the default on this machine, and NTFS), writing
    `no-force-push.md` and then `No-Force-Push.md` leaves exactly one FILE on disk -- the first
    name, the second file's CONTENT -- with nothing on disk that records a second file ever
    existed. `git status` on this same machine's default `core.ignorecase=true` shows it as an
    ordinary single-file edit too, so there is no recovery signal once it happens. On a
    case-sensitive checkout of the same tree (Linux, most CI), both files coexist and both reach
    `entries()` -- injected as two independent-looking rules that happen to say opposite things,
    with nothing marking them as the same name in disguise. This is the one place that coexistence
    is still visible: before the workspace is ever synced to a case-insensitive machine.
    """
    groups = {}
    for p in paths:
        groups.setdefault(p.stem.casefold(), []).append(p)
    return [sorted(g) for g in groups.values() if len(g) > 1]


def title_of(path, text=None):
    """The entry's `# ` heading, falling back to a readable form of the filename."""
    try:
        text = text if text is not None else path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return path.stem.replace("-", " ")
    # 🐛 A UTF-8 BOM sits before the `#`, so `startswith("# ")` was False on the first line and the
    # real title was unreachable: `# Why Postgres over SQLite` was injected as `why postgres`, the
    # de-slugged filename. Editors on Windows write a BOM by default, and this is the only place a
    # BOM could change what a session is told.
    for line in text.lstrip("\ufeff").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem.replace("-", " ")


def _cut_clean(body, limit):
    """`body` cut to `limit`, never inside a fenced block and never mid-line.

    The same two hazards the whole-budget cut below documents: a cut inside ``` leaves the fence
    open and everything after it renders as code, and a cut mid-sentence reads as corruption.
    """
    head = body[:limit]
    if head.count("```") % 2:
        head = head[:head.rfind("```")]
    # Back off to a line break, but only a nearby one: a rule written as one long paragraph has no
    # newline to find, and `rsplit("\n", 1)[0]` then returned the heading alone — 171 characters of
    # a 1,500-character budget. Fall back to a word boundary, which every text has.
    nl = head.rfind("\n")
    if nl > limit * 0.6:
        return head[:nl].rstrip()
    sp = head.rfind(" ")
    return (head[:sp] if sp > limit * 0.6 else head).rstrip()


CONFLICT_MARKERS = ("<<<<<<< ", "=======", ">>>>>>> ")


def unresolved_conflict(body):
    """True when this entry is mid-merge and both sides are still in the file.

    🐛 Nothing looked. A rule carrying `<<<<<<< HEAD` reached the model as one rule holding two
    contradictory instructions — "deploy only on Tuesdays after the DBA signs off" and "deploy
    whenever CI is green" — with no indication that the file was in conflict, inside the fence that
    tells the reader this text comes from the repository. The model then has to guess which side is
    current, and either guess is presented to it as settled policy.
    
    A rule in conflict is not a rule. Saying the file needs resolving is the only honest thing to
    inject, and it is also what gets it fixed: the alternative is a session acting on the losing
    side of a merge nobody finished.

    Both a marker line AND a closer are required, so a document that merely quotes `=======` as a
    markdown rule, or a diff pasted into a lesson, is not accused of being a conflict.
    """
    lines = body.split("\n")
    opened = any(l.startswith(CONFLICT_MARKERS[0]) for l in lines)
    closed = any(l.startswith(CONFLICT_MARKERS[2]) for l in lines)
    return opened and closed


def rules_text(root):
    """Every rule, concatenated, capped. This is what goes in front of the agent each session."""
    out, titles = [], []
    rule_paths = entries(root, "rules")
    collision_of = {p: g for g in case_collisions(rule_paths) for p in g}
    for path in rule_paths:
        try:
            body = path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        group = collision_of.get(path)
        if group:
            # Same reasoning as the merge-conflict branch below, same shape of injection: a rule
            # whose filename collides by case only is not reliably ONE rule -- on a case-sensitive
            # checkout the sibling file is real content nobody meant to inject as fact, and on the
            # case-insensitive machine that wrote it, it already silently ate the other one's body.
            others = ", ".join(f"`{mdblock.as_quoted(p.name)}`" for p in group if p != path)
            out.append(f"**{mdblock.one_line(title_of(path))}** — ⚠ this rule's filename collides with {others}, "
                       f"differing only by case. Filesystems disagree on whether these are one file "
                       f"or two, so it is NOT in force until the files are merged or renamed apart; "
                       f"do not act on either side.")
            titles.append(title_of(path))
        elif body and unresolved_conflict(body):
            # Named, not silently dropped: a rule that vanishes is indistinguishable from one that
            # was never written, and the point is to get this file resolved.
            out.append(f"**{mdblock.one_line(title_of(path))}** — ⚠ this rule is mid-merge and both sides are still "
                       f"in `{mdblock.as_quoted(path.name)}`. It is NOT in force until someone "
                       f"resolves it; do not act on either side.")
            titles.append(title_of(path))
        elif body:
            # Closed per RULE, not only once around the finished section. A fence left open
            # in one rule's own file otherwise runs to the end of the whole section, and
            # every rule written after it renders as code inside that block — measured: the
            # section-level close stops the damage escaping the section, and leaves the
            # rules after the broken one swallowed exactly as before. Balancing here also
            # means both cuts below operate on text whose fences already match.
            out.append(mdblock.close_dangling_fence(_flatten(body)))
            titles.append(title_of(path))
    if not out:
        return ""
    joined = "\n\n".join(out)
    if len(joined) <= MAX_RULES_CHARS:
        return joined
    # 🐛 A single overall cap, so ONE long rule ate the whole budget and every rule after it was
    # dropped. Measured on the repository this was built in: two rules totalling 6,392 characters
    # returned 1,612 — rule one cut mid-sentence, rule two never shown at all. The comment above
    # says "a repository with more than this in standing constraints has a documentation problem";
    # the first real user hit the cap at n=2, which makes it a cap problem.
    #
    # A per-rule share first, so every rule gets a turn before any rule gets a second helping. The
    # whole-budget cut below still runs afterwards and is still what guarantees the total — this
    # only changes WHICH characters survive to reach it.
    share = max(300, MAX_RULES_CHARS // max(len(out), 1))
    if len(out) > 1 and any(len(o) > share for o in out):
        trimmed = []
        for body, title in zip(out, titles):
            if len(body) <= share:
                trimmed.append(body)
            else:
                trimmed.append(_cut_clean(body, share) +
                               f"\n\n_…the rest of **{mdblock.one_line(title)}** is in `.chamnan/memory/rules/`._")
        joined = "\n\n".join(trimmed)
        if len(joined) <= MAX_RULES_CHARS:
            return joined
    # 🐛 Two things went wrong at this cut, and both were silent.
    #
    # It landed anywhere, including inside a ``` block, leaving the fence open — after which every
    # later line of the injected block rendered as code, INCLUDING the "more rules" notice itself,
    # so the reader was not told anything had been left out. `state._safe_cut` was written for
    # exactly this and was never used here.
    #
    # And it dropped WHOLE RULES by filename alphabet without naming them: a verbose `a-*.md`
    # starved `c-prod.md` — "Never write to prod" — out of the injection entirely, under a notice
    # that said only how many rules exist. A rule that does not arrive is the one case where saying
    # which one is missing costs a line and buys everything.
    cut = state._safe_cut(joined, MAX_RULES_CHARS)
    kept = joined[:cut].rstrip()
    missing = [t for t in titles if t not in kept]
    tail = f"\n\n_…more rules in `.chamnan/memory/rules/` — {len(out)} in total."
    if missing:
        tail += " Not shown above: " + ", ".join(f"**{t}**" for t in missing[:6])
        if len(missing) > 6:
            tail += f", and {len(missing) - 6} more"
        tail += "."
    return kept + tail + "_"


def rules_with_titles(root):
    """[(title, raw text)] for every rule. rules_text() flattens and caps for injection; a checker
    needs the unflattened body (its Check trailer survives) and the title to name what broke."""
    out = []
    for path in entries(root, "rules"):
        try:
            body = path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if body:
            out.append((title_of(path, body), body))
    return out


def _flatten(body):
    """Demote an entry's own headings before it is injected.

    An entry is a standalone file, so it opens with `# Title`. The hook drops it inside a `###`
    section, and an H1 nested under an H3 makes the injected block's structure read wrongly — the
    rule looks like a new top-level document rather than one item in a list of constraints.

    The demotion itself lives in `mdblock.demote_headings` now, shared with every other caller
    that injects free-form, multi-line, repository-authored text under one of chamnan's own `###`
    sections -- this was the only one of them doing it before.
    """
    return mdblock.demote_headings(body).strip()


def titles(root):
    """(category, title, filename) for the categories read on demand, capped in total.

    Decisions and lessons share one cap rather than getting one each: the agent needs to know what
    is available, and a repository with forty decisions should spend the same on saying so as one
    with four.
    """
    found = []
    for category in ("decisions", "lessons"):
        for path in entries(root, category):
            found.append((category, title_of(path), path.name))
    return found


# 🐛 [2026-08-27] title_of() reads a `# ` heading with no length limit of its own, and this was the
# one place in the whole injection pipeline that passed it straight through -- a genuinely unbounded
# channel, unlike everything else here which is capped somewhere. A title this long is also almost
# certainly the wrong thing to have written as a title in the first place, so truncating it doubles
# as a visible nudge to shorten it, rather than a silent workaround.
MAX_TITLE_CHARS = 120


def render_titles(found):
    """One line per entry, with the path to read. Empty when there is nothing, so the hook injects
    no heading rather than an empty one."""
    if not found:
        return ""

    def _cap(title):
        return title if len(title) <= MAX_TITLE_CHARS else title[:MAX_TITLE_CHARS].rstrip() + "…"

    # 🐛 The cap was applied to the concatenation, which is in category-then-filename order — so a
    # repository with ten decisions and two lessons sent NO LESSON to the session at all, under a
    # line reading "…and 4 more" that never said a whole category was missing. Interleave, so each
    # category is represented before either takes a second slot.
    by_cat = {}
    for row in found:
        by_cat.setdefault(row[0], []).append(row)
    interleaved, i = [], 0
    while len(interleaved) < len(found):
        for cat in sorted(by_cat):
            if i < len(by_cat[cat]):
                interleaved.append(by_cat[cat][i])
        i += 1
    shown = interleaved[:MAX_TITLES]
    lines = [f"- **{cat[:-1]}** · `{mdblock.as_quoted(name)}` — {mdblock.one_line(_cap(title))}"
             for cat, title, name in shown]
    if len(found) > MAX_TITLES:
        missing = sorted({c for c, _, _ in found} - {c for c, _, _ in shown})
        note = f"- _…and {len(found) - MAX_TITLES} more in `.chamnan/memory/`"
        if missing:
            note += ", including every " + " and ".join(missing)
        lines.append(note + "_")
    return "\n".join(lines)


def counts(root):
    return {c: len(entries(root, c)) for c in CATEGORIES}


def slug(title):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", title.strip().lower()).strip("-")
    return (s[:50].rstrip("-") or "entry")


def filename(title):
    return f"{slug(title)}.md"
