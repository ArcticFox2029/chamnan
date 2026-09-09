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
import unicodedata
from pathlib import Path
import workspace as ws
import mdblock
import state

CATEGORIES = ("decisions", "lessons", "rules")

# Rules reach every session, so they are capped. Roughly a third of state_token_budget's
# char-equivalent (see lib/state.py): a repository with more than this in standing constraints has
# a documentation problem, not a memory problem.
# 🐛 [2026-09-09] Hardcoded at 1,500 on 2026-08-20, when this repository had ONE rule. By
# 2026-09-09 it had nine, totalling 22,669 characters, and the budget had never moved — so four
# rules arrived with a body and five arrived as a title, and which four was decided by the first
# letter of the filename. Measured on the real block the same day: `Work in flight` 4,702 bytes,
# rules 1,972, the architecture index 1,680, against a 9,000-byte ceiling.
#
# The other two of those three have a config key (`state_token_budget`, `index_token_budget`) and
# an owner can raise them. The rules section — the one carrying the standing instructions a person
# gave and expects to be followed — was the only one nobody could give more room to. That is the
# defect: not the number, the absence of the dial.
#
# The default stays 1,500 so no existing workspace changes shape on upgrade. `fit.shrink` still
# arbitrates against the ceiling afterwards, which is what stops a large value simply cutting the
# index instead.
DEFAULT_RULES_CHARS = 1500
MAX_RULES_CHARS = DEFAULT_RULES_CHARS


def rules_budget(root=None):
    """The rules section's character budget: `rules_char_budget` in config, else the default."""
    if root is None:
        return MAX_RULES_CHARS
    try:
        import workspace as _ws
        value = _ws.load_config(root).get("rules_char_budget")
    except Exception:                        # noqa: BLE001 — config must never break the block
        return MAX_RULES_CHARS
    return value if isinstance(value, int) and 300 <= value <= 20_000 else MAX_RULES_CHARS

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
                  if p.is_file() and not ws.is_store_index(p)
                  and ws.inside(p, root, _resolved_root=root_resolved))


# `see memory `slug``, `memory: `slug``, or a bare ``slug`` next to the word memory. Written by
# people and by the write skills, in STATE.md, session records, threads and dated logs.
CITATION = re.compile(r"memory[:\s]+`([a-z0-9][a-z0-9._-]*)`", re.I)

# 🐛 [2026-09-08] The OTHER syntax, and the one the memory store's own entries actually use.
# `dangling_citations` exists to catch a pointer to an entry nobody wrote, and it could not see
# nine `[[slug]]` links across eight files in this repository's live workspace -- two of which
# point at slugs that exist nowhere, confirmed against the files on disk. One store, two citation
# formats, and only one of them checked: the same shape this codebase carries more fixes for than
# any other, in the function whose entire job is to find broken pointers (R7 agent 3).
#
# A `[[...]]` may carry a path (`[[../lessons/some-slug]]`) or a `.md`, because that is how people
# write them; both are reduced to the bare stem, which is what an entry is named by. A link whose
# target RESOLVES as a real file relative to the citing document is not a memory citation at all --
# `[[../../../CLAUDE.md]]` is a link to the repository's own file, and reporting it as dangling
# would be a false positive in a report whose value depends on every line being real.
WIKILINK = re.compile(r"\[\[([^\]|#\n]{1,200})\]\]")


def _wikilink_slug(target):
    """The entry name a `[[...]]` target refers to, or None when it is not one."""
    stem = target.strip().rsplit("/", 1)[-1]
    if stem.lower().endswith(".md"):
        stem = stem[:-3]
    return stem if re.fullmatch(r"[a-z0-9][a-z0-9._-]*", stem, re.I) else None


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
            text = f.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        # Scanned over the WHOLE text, with the line derived from the match offset. Matching
        # line by line looked equivalent and was not: `memory[:\s]+` admits a newline, so a
        # citation wrapped across two lines is a real and common shape. It cost a detection the
        # moment it was introduced — rancher went from two dangling slugs to one — which is why
        # this is written the slower way on purpose.
        # Both citation formats, from one loop, so a third cannot be added to one and forgotten
        # in the other. `CITATION` is the prose form; `WIKILINK` is what the entries themselves use.
        for pattern in (CITATION, WIKILINK):
            for m in pattern.finditer(text):
                if pattern is CITATION:
                    slug = m.group(1)
                    # 🐛 [2026-09-08] An entry's slug is its filename WITHOUT `.md` -- that is what
                    # the write skills produce and what a citation is written from. So a backticked
                    # token that still carries the extension is a FILENAME, and this rule was
                    # reporting `Memory: ``MEMORY.md`` index now truncates at 25KB` -- a changelog
                    # line about a file -- as a pointer to a memory entry nobody wrote. One wrong
                    # line costs this report more than it looks: it is read to decide whether the
                    # other lines are worth chasing.
                    if slug.lower().endswith(".md"):
                        continue
                else:
                    slug = _wikilink_slug(m.group(1))
                    # A link that resolves to a real file beside the citing document is a file
                    # link, not a memory citation, and it is not this function's business.
                    if slug is None or (f.parent / m.group(1).strip()).exists():
                        continue
                if slug in known:
                    continue
                where = (f"{f.relative_to(wsdir).as_posix()}",
                         text.count("\n", 0, m.start()) + 1)
                found.setdefault(slug, [])
                if where not in found[slug]:
                    found[slug].append(where)
    return [(slug, places) for slug, places in found.items()]


def knowledge_for(root, target):
    """[(category, path, title)] for every memory entry that DECLARES `target` on a `Files:` line.

    The other half of the join `timeline.for_path` already does. That one answers "what has HAPPENED
    to this file"; this answers "what was DECIDED about it, what went wrong with it, and what rule
    covers it" -- and until now nothing did, so `chamnan-impact` and the file pointer could name
    what imports a file and never what the repository had already learned about it.

    **Declared, not inferred.** The first version of this matched backticked filenames in the prose,
    and measuring it on this workspace is what killed it: of 55 "files" it found, most were not
    files. `1.6.0` and `v1.9.0` are versions, `127.0.0.1` and `luminapp.xyz` are hosts, and
    `os.replace`, `ws.exclusive`, `sessions.prune` and `permissions.ask` are functions -- every one
    of them a backticked token with a dot in it, which is exactly what `style.css` is too. A
    directory match was worse: `Work-Mode/chamnan` named in one rule attached that rule to every
    file in the plugin, so the pointer would have said the same four things about every file in the
    repository, which is how a reader learns to stop reading it.

    `Files:` is the join key here for the same reason `timeline.py`'s docstring gives for threads:
    free prose is not a join key. The cost is honest and worth stating -- an entry that does not
    declare its files answers nothing, and on the day this was written that was every entry in this
    workspace. It fills as records are written, which is the same way every other store here fills.
    """
    hits = []
    for category in ("decisions", "incidents", "lessons", "rules"):
        for entry in entries(root, category):
            try:
                text = entry.read_text(encoding="utf-8-sig", errors="replace")
            except OSError:
                continue
            if any(mdblock.names_the_path(declared, target)
                   for declared in mdblock.files_named(text)):
                hits.append((category, entry, title_of(entry, text)))
    return sorted(hits, key=lambda h: (h[0], h[2]))


def case_collisions(paths):
    """Group `paths` whose filename stems collide once the filesystem is done with them.

    Case is one such equivalence and Unicode normalisation is the other, and both are folded here
    because both fail the same way and the caller cannot tell them apart.

    🐛 On a case-insensitive filesystem (APFS, the default on this machine, and NTFS), writing
    `no-force-push.md` and then `No-Force-Push.md` leaves exactly one FILE on disk -- the first
    name, the second file's CONTENT -- with nothing on disk that records a second file ever
    existed. `git status` on this same machine's default `core.ignorecase=true` shows it as an
    ordinary single-file edit too, so there is no recovery signal once it happens. On a
    case-sensitive checkout of the same tree (Linux, most CI), both files coexist and both reach
    `entries()` -- injected as two independent-looking rules that happen to say opposite things,
    with nothing marking them as the same name in disguise. This is the one place that coexistence
    is still visible: before the workspace is ever synced to a case-insensitive machine.

    🐛 [2026-09-06] The key was `casefold()` alone, and `casefold()` does not normalise. A
    precomposed `café` (U+00E9) and its decomposed twin (`e` + U+0301) render identically, collapse
    into ONE file on this machine's APFS exactly as the case pair does -- verified by writing both
    names and getting a single `listdir` entry holding the second write -- and hashed to two
    different keys here, so the guard built for precisely this failure returned nothing. NFC first,
    then casefold, catches both classes in one pass (R6 acc3, hostile filesystem).

    Pure Thai text is NOT the exposure and a future round should not go looking there: Thai
    combining vowel and tone marks have no precomposed form, so NFC and NFD coincide for it. The
    risk is accented Latin and Vietnamese names -- `café`, `naïve`, `façade` -- which are ordinary
    in a bilingual repository and normalise differently depending on which tool typed them.
    """
    groups = {}
    for p in paths:
        groups.setdefault(mdblock.filesystem_key(p.stem), []).append(p)
    return [sorted(g) for g in groups.values() if len(g) > 1]


def title_of(path, text=None):
    """The entry's `# ` heading, falling back to a readable form of the filename."""
    try:
        text = text if text is not None else path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return path.stem.replace("-", " ")
    # 🐛 A UTF-8 BOM sits before the `#`, so `startswith("# ")` was False on the first line and the
    # real title was unreachable: `# Why Postgres over SQLite` was injected as `why postgres`, the
    # de-slugged filename. Editors on Windows write a BOM by default.
    #
    # 🐛 [2026-09-06] "this is the only place a BOM could change what a session is told" is what
    # this comment used to say, and it was wrong in the way this repository is always wrong -- one
    # member of a set fixed, the identical ones beside it left. `timeline.title_of` reads a thread
    # the same way, and a BOM there made `_distinct_slug` fork a thread's history into a second
    # file; `sessions.title_of` lost the "last session" title the same way (R11 agent 1). So the
    # BOM is stripped at the READ now -- every `read_text` in lib/, bin/ and hooks/ decodes
    # `utf-8-sig`, which is plain UTF-8 plus "drop a leading BOM if there is one" -- and this
    # `lstrip` stays only because `text` may be passed in by a caller that read it itself.
    # \U0001f41b [2026-09-07] `startswith("# ")` again, and this file is where the comment above
    # says the disease lives -- one member of a set fixed, the identical ones beside it left. The
    # heading unification reached `state`, `pointer`, `timeline.title_of` and `sessions`; it did
    # not reach here or `timeline.set_status`, so a memory entry titled with a CJK keyboard's
    # U+3000 after the hash was injected under its de-slugged FILENAME instead of its title, and a
    # decision the owner wrote by hand arrived unrecognisable (R12 agent 2).
    for line in text.lstrip("\ufeff").splitlines():
        title = mdblock.heading_title(line)
        if title is not None:
            return title
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


def mtime_or_zero(path):
    """Last-modified time, or 0 when it cannot be read -- which sorts the entry last rather than
    dropping it, the same choice `milestones` makes for an entry with no date: it still exists.

    🐛 [2026-09-09] Written here as a second copy of the one the session-start hook already had,
    four lines apart in behaviour and identical in effect. Two copies of one rule is the defect
    this repository records more than any other, and it was caught by the caller sweep in
    `before_the_suite.py` rather than by reading — which is the argument for that sweep.
    """
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def rules_text(root):
    """Every rule, concatenated, capped. This is what goes in front of the agent each session."""
    out, titles = [], []   # titles: (title, filename)
    # 🐛 [2026-09-09] `entries()` returns filename order, and the budget carries about four rules
    # out of nine here — so which rules got a BODY was decided by their first letter. A rule written
    # tonight, in response to something said four times, sat under `s` and arrived as a title while
    # a months-old one under `l` arrived in full. Every rule is still NAMED, which is what stops
    # this being a disappearance; what alphabet was deciding is which ones the agent can actually
    # read without opening a file.
    #
    # Newest first, filename as the tie-break, the same ordering the skills list and
    # `memory.titles()` were given the day before for the identical reason. After a clone every
    # mtime is the checkout time, and then this falls back to exactly the previous behaviour.
    rule_paths = sorted(entries(root, "rules"),
                        key=lambda p: (-mtime_or_zero(p), p.name))
    collision_of = {p: g for g in case_collisions(rule_paths) for p in g}
    for path in rule_paths:
        try:
            body = path.read_text(encoding="utf-8-sig", errors="replace").strip()
        except OSError:
            continue
        # 🐛 [2026-09-06] `title_of(path)` was called with no body, at five sites in this loop, so
        # every rule file was read a further FOUR times to recover a heading the caller already had
        # in `body`. Measured by instrumenting the real hook sequence: 1,500 `read_text` calls for
        # 500 rule files, where 500 is the whole requirement. The parameter to pass it exists and
        # its docstring says what it is for (R12 agent 3).
        title = title_of(path, body)
        group = collision_of.get(path)
        if group:
            # Same reasoning as the merge-conflict branch below, same shape of injection: a rule
            # whose filename collides by case only is not reliably ONE rule -- on a case-sensitive
            # checkout the sibling file is real content nobody meant to inject as fact, and on the
            # case-insensitive machine that wrote it, it already silently ate the other one's body.
            others = ", ".join(f"`{mdblock.as_quoted(p.name)}`" for p in group if p != path)
            out.append(f"**{mdblock.one_line(title)}** — ⚠ this rule's filename collides with {others}, "
                       f"differing only by case. Filesystems disagree on whether these are one file "
                       f"or two, so it is NOT in force until the files are merged or renamed apart; "
                       f"do not act on either side.")
            titles.append((title, path.name))
        elif body and unresolved_conflict(body):
            # Named, not silently dropped: a rule that vanishes is indistinguishable from one that
            # was never written, and the point is to get this file resolved.
            out.append(f"**{mdblock.one_line(title)}** — ⚠ this rule is mid-merge and both sides are still "
                       f"in `{mdblock.as_quoted(path.name)}`. It is NOT in force until someone "
                       f"resolves it; do not act on either side.")
            titles.append((title, path.name))
        elif body:
            # Closed per RULE, not only once around the finished section. A fence left open
            # in one rule's own file otherwise runs to the end of the whole section, and
            # every rule written after it renders as code inside that block — measured: the
            # section-level close stops the damage escaping the section, and leaves the
            # rules after the broken one swallowed exactly as before. Balancing here also
            # means both cuts below operate on text whose fences already match.
            out.append(mdblock.close_dangling_fence(_flatten(body)))
            titles.append((title, path.name))
    if not out:
        return ""
    joined = "\n\n".join(out)
    cap = rules_budget(root)
    if len(joined) <= cap:
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
    share = max(300, cap // max(len(out), 1))
    if len(out) > 1 and any(len(o) > share for o in out):
        trimmed = []
        for body, (title, fname) in zip(out, titles):
            if len(body) <= share:
                trimmed.append(body)
            else:
                # 🐛 [2026-09-09] This named the DIRECTORY. Every other injected store gives an
                # exact filename per line -- skills, tools, decisions and lessons all do -- and
                # rules were the one that did not, in any of their three render paths. A session
                # wanting the body of a title-only rule had one instruction: open the directory and
                # find it, against ten abstract titles whose filenames need not resemble them.
                # `path.name` was in scope the whole time; it just was not carried through (R5 agent2).
                trimmed.append(_cut_clean(body, share) +
                               f"\n\n_…the rest of **{mdblock.one_line(title)}** is in "
                               f"`.chamnan/memory/rules/{mdblock.as_quoted(fname)}`._")
        joined = "\n\n".join(trimmed)
        if len(joined) <= cap:
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
    cut = state._safe_cut(joined, cap)
    kept = joined[:cut].rstrip()
    missing = [(t, f) for t, f in titles if t not in kept]
    tail = f"\n\n_…more rules in `.chamnan/memory/rules/` — {len(out)} in total."
    if missing:
        # The filename beside the title, for the same reason as the trim tail above: a rule that
        # did not arrive is exactly the one somebody has to go and open.
        tail += " Not shown above: " + ", ".join(
            f"**{t}** (`{mdblock.as_quoted(f)}`)" for t, f in missing[:6])
        if len(missing) > 6:
            tail += f", and {len(missing) - 6} more"
        tail += "."
    return kept + tail + "_"


def rules_pressure(root):
    """Which rules reach a session in full, which arrive as a title only, and how far over the
    budget the store is. `(fitted, title_only, chars, budget)`.

    🐛 [2026-09-09] Nothing anywhere reported this. `MAX_RULES_CHARS` was set when this repository
    had one rule; by the time it had nine, four arrived with a body and five arrived as a name, and
    the only way to find out was to run the hook and read the block by eye. A person adding a tenth
    rule has no reason to suspect their earlier ones stopped arriving — the tool has to notice, and
    the person cannot be asked to count bytes.

    Read from the same function the session actually gets, so this cannot drift from it: whatever
    `rules_text` decided is what a title is checked against.
    """
    titled = rules_with_titles(root)
    if not titled:
        return [], [], 0, rules_budget(root)
    delivered = rules_text(root)
    fitted, title_only = [], []
    for title, body in titled:
        # A rule is "fitted" when a distinctive sentence of its body survived, not merely its name:
        # the drop notice lists every title, so a title in the text proves nothing on its own.
        probe = _flatten(body)[len(title):][:120].strip()
        (fitted if probe and probe[:60] in delivered else title_only).append(title)
    return fitted, title_only, sum(len(b) for _t, b in titled), rules_budget(root)


def rules_with_titles(root):
    """[(title, raw text)] for every rule. rules_text() flattens and caps for injection; a checker
    needs the unflattened body (its Check trailer survives) and the title to name what broke."""
    out = []
    for path in entries(root, "rules"):
        try:
            body = path.read_text(encoding="utf-8-sig", errors="replace").strip()
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
        paths = entries(root, category)
        # 🐛 [2026-09-06] `case_collisions` was wired into `rules_text` and nowhere else. Decisions
        # and lessons are the same mechanism -- one file per entry, named from its title -- and got
        # no collision detection at all (R12 agent 1). The consequence is quieter than a rule's and
        # not smaller: a colliding pair leaves ONE file on APFS or NTFS holding the SECOND entry's
        # body under the FIRST entry's name, so this listing tells a reader a decision exists, they
        # open it, and they get a different one. Marked rather than dropped, for the reason the
        # rules branch already gives: an entry that vanishes is indistinguishable from one nobody
        # wrote.
        collided = {q for g in case_collisions(paths) for q in g}
        for path in paths:
            title = title_of(path)
            if path in collided:
                title = ("⚠ " + title + " — this filename collides with another in the same store, "
                         "differing only by case or Unicode form; one of the two files may hold the "
                         "other's body. Read them before trusting either.")
            found.append((category, title, path.name, _written_at(path)))
    # 🐛 [2026-09-08] The cap below chose which entries a session sees BY FILENAME ALPHABET, so a
    # lesson written today lost its slot to one written months ago whose title happens to start with
    # an earlier letter. Reproduced on this repository's own store: two entries committed that day
    # were absent from the block while an older one was shown (R1 agent 4).
    #
    # Both siblings that face the identical "more entries than the cap" problem already sort by
    # recency -- `milestones.recent_titles` and `timeline.open_titles` -- and `rules_text` in THIS
    # file was fixed for an adjacent version of it four days earlier. One more member of a set that
    # did not get the rule.
    #
    # It is mtime rather than a date in the file, because these entries carry no date: they are a
    # heading and a body, and inventing a metadata format for them is a bigger change than the bug.
    # mtime is meaningless straight after a clone -- git does not preserve it, so every file gets
    # the checkout time -- and that case falls back exactly to the previous behaviour, because the
    # filename is the tie-break. Where it is meaningful is a workspace somebody is actually writing
    # in, which is the only place the bug was ever felt.
    found.sort(key=lambda row: (-row[3], row[0], row[2]))
    return [(cat, title, name) for cat, title, name, _ in found]


def _written_at(path):
    """Last-modified time, or 0 when it cannot be read -- which sorts the entry to the end rather
    than dropping it, on the same reasoning as `milestones`' undated entries: it still happened."""
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


# 🐛 [2026-08-27] title_of() reads a `# ` heading with no length limit of its own, and this was the
# one place in the whole injection pipeline that passed it straight through -- a genuinely unbounded
# channel, unlike everything else here which is capped somewhere. A title this long is also almost
# certainly the wrong thing to have written as a title in the first place, so truncating it doubles
# as a visible nudge to shorten it, rather than a silent workaround.
# whole_graphemes, as every other cutter in this codebase: a title ending in a flag emoji cut
# mid-cluster left one regional indicator behind, rendering as a stray letter box in the injected
# block (R4 agent 1). That cut is `mdblock.one_line_capped` now, shared with the three sections
# that were missing it entirely.
#
# The number moved to `mdblock.INJECTED_ITEM_CHARS`, which is where the reasoning above now lives
# too: this was the only section that had this guard, and three siblings that needed the identical
# one did not have it because both the number and the argument were local to this file.
MAX_TITLE_CHARS = mdblock.INJECTED_ITEM_CHARS


def render_titles(found):
    """One line per entry, with the path to read. Empty when there is nothing, so the hook injects
    no heading rather than an empty one."""
    if not found:
        return ""

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
    lines = [f"- **{cat[:-1]}** · `{mdblock.as_quoted(name)}` — {mdblock.one_line_capped(title, MAX_TITLE_CHARS)}"
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
    # 🐛 `mdblock.filename_safe` exists because a record titled "CON" or "nul" becomes
    # `con.md` or `nul.md`, which on Windows are the console and the bit-bucket: the write
    # does not fail, it goes to the DEVICE, and the record is gone. Its own docstring says
    # "both slug() functions in this codebase" — there are five, and three never called it
    # (R2 agent 1 found one; the set walk found the other two).
    s = mdblock.ascii_stem(title)
    return mdblock.filename_safe(s[:50].rstrip("-")
                                 or mdblock.fallback_name(title, "entry"))


def filename(title):
    return f"{slug(title)}.md"
