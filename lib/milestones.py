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
    # 🐛 [2026-09-09] Opened with no containment check at all, while five DIRECTORY stores got
    # exactly this guard on 2026-09-08 and the three single-FILE stores beside them did not. A
    # workspace travels with a clone, so `milestones.md` arriving as a symlink to `~/.ssh/id_rsa` is
    # chosen by whoever wrote the repository, not by the person reading it — and its content lands
    # in the injected block. The set was "stores this reads"; the fix reached the members that
    # happened to be directories. (R3 agent 2, reproduced.)
    import workspace as _ws
    if not _ws.inside(p, root):
        return []
    try:
        text = p.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return []

    found = list(_ENTRY.finditer(mdblock.masked(text)))
    out = []
    for i, m in enumerate(found):
        end = found[i + 1].start() if i + 1 < len(found) else len(text)
        title = m.group(2)
        # 🐛 [2026-09-07] `append()` folds newlines out of a title now, so no NEW entry can be
        # split in two by one. That says nothing about the entries already in the file, and this
        # file is COMMITTED — a clone carries whatever its author put there, and an install from
        # before the fold wrote titles raw. A title holding "\n## <date> — <text>" therefore
        # produces a second entry that HEAD's own fixed reader trusts completely, and because the
        # date is attacker-chosen it sorts to the top of the two titles the session is shown.
        # Reproduced against HEAD today: the planted entry won the "most recent" slot.
        #
        # The tell is structural rather than semantic: `render_entry` always leaves a blank line
        # under its heading, so a heading whose PREVIOUS line is another heading was not written by
        # this code. Flagged, never dropped — the owner's rule is that nothing here is deleted, and
        # a reader who is told which line is suspect can fix the file, while a reader who is shown
        # nothing cannot.
        # \U0001f41b [2026-09-07] Look at the line immediately above, and at nothing else. The first
        # version did `text[:m.start()].rstrip("\n")` and then asked whether what was left ended in
        # a heading, which cannot tell "no blank line between them" from "a blank line, and a
        # heading above THAT" -- `rstrip` removes the separator it is trying to detect. It was
        # wrong in both directions: two legitimate field-less entries in a row were flagged (a
        # shape `render_entry`'s own docstring designs for), and a single trailing SPACE on the
        # blank line -- invisible in every editor, and inserted by many of them automatically --
        # made the real forgery undetectable, because `rstrip("\n")` stops at the space (R12 a2).
        #
        # `render_entry` always leaves exactly one EMPTY line above a heading. So the test is
        # whether the previous line is that empty line. A space-only line is not what this code
        # writes either, and it is now flagged rather than trusted -- which is the right direction
        # for a tell whose whole job is "this was not written by chamnan".
        _above = text[:m.start()].split("\n")
        # `text[:m.start()]` ends at the newline before the heading, so its last element is "" and
        # the line the reader sees above the heading is the one before that.
        split_off = len(_above) >= 2 and _above[-2] != ""
        if split_off:
            title = (title + " ⚠ this heading follows another with no blank line between them, "
                     "which is not how chamnan writes one — it may have been split out of the "
                     "title above by a newline. Check .chamnan/milestones.md.")
        out.append((m.group(1), title, text[m.end():end].strip()))
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
    # `count=2` bounds how MANY milestones are shown and says nothing about how long each is: one
    # ordinary "what happened and why" title, written the way `/chamnan:milestone` invites, measured
    # 165 tokens on its own.
    lines = [f"- **{mdblock.one_line(date)}** — {mdblock.one_line_capped(title)}"
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
    # 🐛 [2026-09-07] Read the whole file, append in memory, write it back — with no lock, so the
    # last writer's snapshot became the entire file. Six processes appending one milestone each:
    # FIVE VANISHED, valid Markdown throughout, no error anywhere. This is the highest-value store
    # in the workspace, because a milestone is the one thing here a person typed a reason for, and
    # two accounts on one machine both running /chamnan:milestone in the same minute is an ordinary
    # afternoon rather than an edge case (R7 agent 5).
    #
    # The read has to happen INSIDE the lock, which is why this is `rewrite_shared` rather than a
    # lock wrapped around the write: reading first and locking second leaves the same race with a
    # smaller window, which is the version of this fix that looks right and is not.
    p = path(root)

    def _appended(existing):
        if not (existing or "").strip():
            existing = HEADER + "\n"
        return existing.rstrip("\n") + "\n\n" + entry_text.strip() + "\n"

    ws.rewrite_shared(p, _appended)
    return p
