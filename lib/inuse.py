"""Is something running this file right now? — asked before the edit, not after the crash.

ENFORCES: memory/rules/the-full-gate-runs-twice.md

🐛 [2026-09-23] (self-measured) Twice in one hour, and the second time was an hour after recording the first as a
lesson. Four research rounds were dispatched, then `ask-codex-account.sh` was edited while they
were in flight; every round died with `unexpected EOF`. The lesson was written into the file with
`chamnan-gotcha`. An hour later the same file was edited again, with a fifth round running, and
that round died the same way.

A recorded lesson only reaches a session that touches the same LINE; `bugnotes.py` is deliberately
positional. This is the other half, and it is not about any one file: **a script is read from disk
as it runs**, so editing it mid-run changes the program underneath itself. The same shape killed
three chamnan suite runs in one day, which is what `never-edit-source-during-a-suite-run` records.

The question is cheap and exact — is this path named in any live process's command line — and it
needs no convention, no declaration and no list.
"""
import os
import pathlib
import subprocess

import workspace as ws

# 🐛 [2026-09-23] (self-measured) This was `("inuse", "grep", "ps ")` — a substring test against the whole command
# line — and the check written for it created its fixture in a temp directory called
# `chamnan-inuse-XXXX`. The running script's own path therefore contained "inuse" and every real
# hit was filtered out; the standalone probe passed only because ITS temp directory did not. A
# filter that matches anywhere in a path is the same shape as the blanket-replace lesson.
_SKIP_EXACT = ("inuse.py",)          # this module, when something runs it directly
# 🐛 [2026-09-24] (self-measured) Written as command-line PREFIXES, `/usr/bin/grep` included, and
# tested with `head.endswith("ps")` — so any program whose name merely ends in "ps" (`apps`,
# `gps`) was skipped as though it were the question, and an absolute path sat in a runtime file
# that has to work where `grep` lives somewhere else. The program's own NAME is what identifies it.
_SKIP_PROGRAMS = ("ps", "grep")


def _is_the_question_itself(cmd):
    """True for the processes that are ASKING, rather than ones that are running the file."""
    head = cmd.split(" ", 1)[0]
    return (head.rsplit("/", 1)[-1] in _SKIP_PROGRAMS
            or any(cmd.endswith(x) or f"{x} " in cmd for x in _SKIP_EXACT))


def users_of(path):
    """Live processes whose command line names `path`, as (pid, command). [] is the usual answer."""
    try:
        name = pathlib.Path(path).name
        if not name:
            return []
        out = subprocess.run(["ps", "-Ao", "pid=,command="], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=3).stdout
    except ws.git_cannot_answer():       # every way running a program fails, WASM included
        return []
    skip = {str(os.getpid()), str(os.getppid())}
    hits = []
    for line in out.splitlines():
        pid, _, cmd = line.strip().partition(" ")
        if pid in skip or _is_the_question_itself(cmd):
            continue
        if name in cmd:
            hits.append((pid, cmd.strip()))
    return hits


def advice(tool, tool_input, root=None):
    """One notice, or "". Silent unless the file being edited is executing right now."""
    if tool not in ("Edit", "Write", "NotebookEdit") or not isinstance(tool_input, dict):
        return ""
    target = tool_input.get("file_path") or ""
    if not target:
        return ""
    # Only a file something can RUN. Editing a document another process happens to name is fine.
    if pathlib.Path(target).suffix not in ("", ".py", ".sh", ".command", ".js", ".rb", ".pl"):
        return ""
    live = users_of(target)
    if not live:
        return ""
    pid, cmd = live[0]
    return ("chamnan: `%s` is running right now (pid %s, `%s`)%s. A script is read from disk AS it "
            "runs, so an edit lands in the middle of the program — on 2026-09-23 that killed five "
            "research rounds and three suite runs. Nothing is blocked."
            % (pathlib.Path(target).name, pid, cmd[:60],
               f" and {len(live) - 1} more" if len(live) > 1 else ""))
