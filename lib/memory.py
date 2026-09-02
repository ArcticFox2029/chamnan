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
    return sorted(p for p in d.glob("*.md") if p.is_file())


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


def rules_text(root):
    """Every rule, concatenated, capped. This is what goes in front of the agent each session."""
    out, titles = [], []
    for path in entries(root, "rules"):
        try:
            body = path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if body:
            out.append(_flatten(body))
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
                               f"\n\n_…the rest of **{title}** is in `.chamnan/memory/rules/`._")
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
    """
    out = []
    for line, in_fence in mdblock.fenced_lines(body):
        if in_fence:
            # A `#` inside a fence is a comment in the example, not a heading of the rule. It used
            # to be demoted like any other, so a rule whose whole point was `# retries=3 is
            # load-bearing` was injected with that marker stripped off the line it annotated.
            out.append(line)
        elif line.startswith("# "):
            out.append(f"**{line[2:].strip()}**")
        elif line.startswith("#"):
            out.append(re.sub(r"^#+\s*", "", line))
        else:
            out.append(line)
    return "\n".join(out).strip()


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
    lines = [f"- **{cat[:-1]}** · `{name}` — {_cap(title)}" for cat, title, name in shown]
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
