"""The lesson recorded at this exact place, said when somebody edits it again.

ENFORCES: memory/rules/a-bad-result-earns-a-gotcha.md

🎯 [owner 2026-09-23] Measured in this repository the day this was
written: **4,144 gotchas recorded in 478 files, and nothing read a single one of them.** They were
written into the code, above the line they are about, by sessions that had just paid for the
lesson — and the only way a later session saw one was by happening to read that part of the file,
which the whole rest of this plugin exists to avoid doing.

So the store was full and the retrieval was missing, which is exactly the failure
`knowledge-gardener` was built for one repository over: knowledge that is correct, indexed, and
never reached.

**Attachment is by POSITION, because that is how the note was written.** The convention in this
codebase is a `🐛` comment immediately above the code it is about; a note is therefore about the
lines that follow it, and the question "what was learned here" is answered by the nearest preceding
note — not by a search, which would return the whole file's worth.

**A full overwrite is its own case.** Writing a file that holds notes discards every one of them,
and that is worth a sentence before it happens rather than a `git log` afterwards.
"""
import pathlib
import re

MARK = "\U0001F41B"
RADIUS = 40              # lines above the edit a note can still be about; a note further up is
                         # about different code, and quoting it teaches people to ignore the notice
MAX_BYTES = 2_000_000
_COMMENTISH = re.compile(r"^\s*(?:#|//|\*|--)")
NOTE_LINES = 6           # how much of one note to carry; the rest is in the file


def _lines(path):
    try:
        p = pathlib.Path(path)
        if p.stat().st_size > MAX_BYTES:
            return []
        return p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _note_at(lines, i):
    """The whole note beginning at line `i`, as one string."""
    out = [lines[i].strip()]
    for j in range(i + 1, min(i + NOTE_LINES, len(lines))):
        if not _COMMENTISH.match(lines[j]) or MARK in lines[j]:
            break
        out.append(lines[j].strip().lstrip("#/*- ").strip())
    return " ".join(x for x in out if x)


def near(path, needle, radius=RADIUS):
    """The recorded lessons attached to the region `needle` sits in. [] when there are none."""
    lines = _lines(path)
    if not lines or not needle:
        return []
    first = (needle.splitlines() or [""])[0].strip()
    if len(first) < 4:
        return []
    where = next((n for n, ln in enumerate(lines) if first in ln), None)
    if where is None:
        return []
    span = needle.count("\n") + 1
    found = []
    # Inside the replaced text itself: the edit is about to rewrite the note's own subject.
    for n in range(where, min(where + span, len(lines))):
        if MARK in lines[n]:
            found.append((n + 1, _note_at(lines, n)))
    # Above it: the nearest note is the one that was written about this code.
    for n in range(where - 1, max(where - radius, -1), -1):
        if MARK in lines[n]:
            found.append((n + 1, _note_at(lines, n)))
            break
    return found


def count_in(path):
    """How many lessons this file records — for the overwrite case."""
    return sum(1 for ln in _lines(path) if MARK in ln)


def advice(tool, tool_input, root=None):
    """One notice, or "". Silent for the great majority of edits, which touch no recorded lesson."""
    if not isinstance(tool_input, dict):
        return ""
    target = tool_input.get("file_path") or ""
    if not target:
        return ""
    if tool == "Write":
        held = count_in(target)
        if held >= 3:
            return ("chamnan: `%s` records %d gotcha(s) — lessons written in place by sessions "
                    "that paid for them. A full overwrite drops every one. Nothing is blocked."
                    % (pathlib.Path(target).name, held))
        return ""
    if tool != "Edit":
        return ""
    hits = near(target, tool_input.get("old_string") or "")
    if not hits:
        return ""
    line, text = hits[0]
    return ("chamnan: this place already records a lesson — `%s:%d` %s Nothing is blocked."
            % (pathlib.Path(target).name, line, text[:300]))
