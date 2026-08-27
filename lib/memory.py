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
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem.replace("-", " ")


def rules_text(root):
    """Every rule, concatenated, capped. This is what goes in front of the agent each session."""
    out = []
    for path in entries(root, "rules"):
        try:
            body = path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if body:
            out.append(_flatten(body))
    if not out:
        return ""
    joined = "\n\n".join(out)
    if len(joined) > MAX_RULES_CHARS:
        cut = joined[:MAX_RULES_CHARS].rsplit("\n", 1)[0]
        joined = cut + (f"\n\n_…more rules in `.chamnan/memory/rules/` — "
                        f"{len(out)} in total._")
    return joined


def _flatten(body):
    """Demote an entry's own headings before it is injected.

    An entry is a standalone file, so it opens with `# Title`. The hook drops it inside a `###`
    section, and an H1 nested under an H3 makes the injected block's structure read wrongly — the
    rule looks like a new top-level document rather than one item in a list of constraints.
    """
    out = []
    for line in body.splitlines():
        if line.startswith("# "):
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

    lines = [f"- **{cat[:-1]}** · `{name}` — {_cap(title)}"
             for cat, title, name in found[:MAX_TITLES]]
    if len(found) > MAX_TITLES:
        lines.append(f"- _…and {len(found) - MAX_TITLES} more in `.chamnan/memory/`_")
    return "\n".join(lines)


def counts(root):
    return {c: len(entries(root, c)) for c in CATEGORIES}


def slug(title):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", title.strip().lower()).strip("-")
    return (s[:50].rstrip("-") or "entry")


def filename(title):
    return f"{slug(title)}.md"
