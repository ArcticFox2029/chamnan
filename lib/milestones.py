"""Project milestones — the handful of changes that reshaped this repository.

Not project management. There is no status, no owner, no assignee, no estimate and no due date,
because none of those are knowledge — they are coordination, and coordination belongs in whatever
tool the team already argues about. A milestone here answers one question and only one:

    "Why does this part of the system look the way it does?"

Four fields, and the middle two are the point:

    ## 2026-08-20 — Authentication migration
    **Why:** sessions dropped under load; the old design held state per node.
    **Affected:** auth module, API layer
    **Decisions:** short-lived tokens; the old endpoint stays for one release

A git log says what changed. It rarely says why the change was worth making, and never says which
areas moved together. That is what somebody needs six months later, usually while deciding whether
they are allowed to undo it.

**One file, appended at the end.** Session records get a file each because they are written on
branches and would conflict; milestones are few, read in order, and rarely written concurrently.
Appending at the bottom keeps every diff to added lines — prepending would rewrite the context of
the whole file on each entry, which is the sort of thing that turns a history into a merge
conflict.

**Not pruned.** Same reasoning as memory: the oldest entry is usually the one nobody can
reconstruct. Only the two most recent titles are injected, so the file's length costs nothing per
session.
"""
import re
import mdblock
import workspace as ws  # noqa: E402

FILENAME = "milestones.md"
HEADER = "# Project milestones\n"

# Only the newest few reach a session, and only as titles. "The last big thing here was the auth
# migration" is worth about twenty tokens and orients a session immediately; the bodies are a grep
# away in a file the agent can open when a title looks relevant.
INJECT_RECENT = 2

# 🐛 [2026-08-27] `[—-]` in a character class is em-dash (U+2014) or hyphen-minus (U+002D) only --
# an entry written with an en-dash (U+2013), which many editors autocorrect "--" into, silently
# failed to match at all. Because entries() only splits the file at headings this regex recognises,
# an unmatched entry was not merely mis-parsed: it was absorbed whole into the PRECEDING entry's
# body, with no error and no sign anything had gone wrong. All three dash characters are listed
# explicitly now rather than as a range, since "—" to "-" is not an ascending codepoint range.
_ENTRY = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*[—–-]\s*(.+?)\s*$", re.M)
FIELDS = ("Why", "Affected", "Decisions")


def path(root):
    from workspace import workspace
    return workspace(root) / FILENAME


def entries(root):
    """(date, title, body) oldest first — the order they are written in.

    Returns [] when the file is absent or holds nothing that parses, which is the common case and
    not an error.
    """
    p = path(root)
    if not p.is_file():
        return []
    try:
        text = p.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return []

    found = list(_ENTRY.finditer(mdblock.masked(text)))
    out = []
    for i, m in enumerate(found):
        end = found[i + 1].start() if i + 1 < len(found) else len(text)
        out.append((m.group(1), m.group(2), text[m.end():end].strip()))
    return out


def recent_titles(root, count=INJECT_RECENT):
    """The newest few, as one line each. Empty when there are none, so no heading is injected."""
    found = entries(root)
    if not found:
        return ""
    # 🐛 `found[-count:]` takes the last few by WRITE POSITION, and this file is append-only — so a
    # backfilled `2026-01-05` entry appended today rendered above `2026-08-20`, under a hook comment
    # that says "newest first", and pushed the genuinely second-newest out of the list entirely.
    # An undated entry sorts last rather than being dropped: it still happened.
    ordered = sorted(found, key=lambda e: (e[0] or "", ), reverse=True)
    lines = [f"- **{mdblock.one_line(date)}** — {mdblock.one_line(title)}"
             for date, title, _ in ordered[:count]]
    if len(found) > count:
        lines.append(f"- _…{len(found) - count} earlier in `.chamnan/{FILENAME}`_")
    return "\n".join(lines)


def render_entry(date, title, why="", affected="", decisions=""):
    """One entry in the canonical shape. Fields with nothing in them are left out rather than
    written empty — a heading followed by nothing reads as an oversight."""
    # Every field folded onto one line before it is written. This file is append-only and is
    # parsed back out by `## ` headings, so a title carrying a newline used to write a second,
    # entirely well-formed milestone underneath the real one -- and being later in the file, the
    # fabricated one won the "most recent" slot that recent_titles() injects.
    parts = [f"## {mdblock.one_line(date)} — {mdblock.one_line(title)}", ""]
    for label, value in (("Why", why), ("Affected", affected), ("Decisions", decisions)):
        value = mdblock.one_line(value or "")
        if value:
            parts.append(f"**{label}:** {value}")
    parts.append("")
    return "\n".join(parts)


def append(root, entry_text):
    """Add an entry to the end of the file, creating it with its header if absent.

    Returns the path written. The caller is responsible for the entry's content; this only owns
    where it goes and that the file keeps its shape.
    """
    p = path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = ""
    if p.is_file():
        try:
            existing = p.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            existing = ""
    if not existing.strip():
        existing = HEADER + "\n"
    body = existing.rstrip("\n") + "\n\n" + entry_text.strip() + "\n"
    ws.write_or_raise(p, body)
    return p
