#!/usr/bin/env python3
"""PostToolUseFailure — write down what failed, so a second attempt at it can be recognised.

🎯 [owner 2026-09-23] *"ให้มันจดข้อผิดพลาด แล้วต้องให้มันเรียนรู้ ไม่ทำผิดซ้ำๆ"*, and then the
correction that decided the design: *"ไม่ใช่มุมมองแค่ repo นี้ แต่ต้องมองดึง user ที่ใช้จริง repo
อื่นๆ งานอื่นๆ ด้วย"*.

**Why the obvious design does not work for a real user.** This repository has accumulated 1,843
`🐛` records in its source, 243 folded checks and 232 dead ends. Somebody who installed chamnan this
morning has none of it, and day one is when a person makes the most mistakes. A gotcha system whose
input is "somebody writes the mistake down" is empty exactly when it is needed. Worse, the layer
that can be ENFORCED is thin even here: of 73 recorded rules, lessons, decisions and skills in this
workspace, **5 carry a machine-checkable trailer**. The other 93% rely on somebody reading and
remembering, which is the layer `rulecheck.py` says in its own source is the one that fails.

So the input has to be something nobody types. `PostToolUseFailure` fires when a tool that started
executing fails, and carries the command, the error, the exit code and the duration. A failing
`terraform plan`, a failing `pytest`, a failing `go build` and a failing `psql` all arrive here the
same way, in any repository, in any kind of work, on the first day.

**This records and nothing else, deliberately.** The first failure is how people learn; only the
SECOND one is a gotcha, and deciding what counts as "the same failure" is a measurement nobody can
make until there are real failures to measure. Too loose a key warns on healthy work and people
stop reading it — `skill_overlap.py` has that failure recorded and it has cost this project a
feature before. Too tight and it never fires twice. The capture is cheap and cannot be backdated;
the key is chosen later, from this log.

**An interrupt is not a mistake.** `is_interrupt` means the run was aborted rather than that the
tool reported an error, and recording it would fill the log with the user changing their mind.

WRITES: logs/failures.jsonl per logs/commands.jsonl
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
import redact  # noqa: E402
import workspace as ws  # noqa: E402

LOG = "logs/failures.jsonl"
# A year of failures at this size is a few hundred kilobytes, and the question this answers — has
# this failed here before — is about habit, which needs a long window to be visible at all.
MAX_RECORDS = 4_000
# The error string is whatever the command printed. Only the first line is kept: for Bash that is
# `Exit code N`, which is the part a key can be built from, and the rest is display text that can
# carry a token, a connection string or a customer's name.
ERR_CHARS = 200
CMD_CHARS = 300


def _first_line(text):
    for line in str(text or "").splitlines():
        if line.strip():
            return line.strip()
    return ""


def _subject(tool, tool_input):
    """What the failure was ABOUT: the command for a shell, the path for a file tool.

    Scrubbed before it is stored. A command line carries credentials often enough that storing one
    unscrubbed would make this log the most dangerous file in the workspace — which is the trap the
    context-snapshot idea was parked for, arriving here by a different road.
    """
    if not isinstance(tool_input, dict):
        return ""
    raw = tool_input.get("command") or tool_input.get("file_path") or tool_input.get("path") or ""
    return redact.scrub(str(raw))[:CMD_CHARS]


def failure_of(payload):
    """The error this payload describes, or "" if it describes no failure.

    🐛 [2026-09-23, found by chamnan-doctor on its first run] `logs/failures.jsonl` had never been
    written in this repository, on a day full of commands that exited non-zero. `PostToolUseFailure`
    fires when the TOOL CALL fails — a denied permission, a bad parameter — and a shell command that
    returns 1 is a tool call that SUCCEEDED and reported a non-zero exit. So `gotcha.py`, built the
    same morning to stop a failure repeating, had an input that almost never arrived.

    Both shapes are read here: `error` from the failure event, and a non-zero exit from an ordinary
    PostToolUse response. A command that exits 1 twice is exactly the habit that rule is about.
    """
    if not isinstance(payload, dict) or payload.get("is_interrupt"):
        return ""
    direct = _first_line(payload.get("error"))
    if direct:
        return direct
    resp = payload.get("tool_response")
    if not isinstance(resp, dict):
        return ""
    code = resp.get("exit_code", resp.get("exitCode"))
    if not isinstance(code, int) or code == 0:
        return ""
    detail = _first_line(resp.get("stderr") or "")
    # 🔴 Exit 1 with nothing on stderr is an ANSWER, not a failure: `grep` found no match, `test`
    # was false, `diff` saw a difference. Recording those would fill the log with normal results
    # and then `gotcha` would report "this has failed here twice" about a grep that worked. A real
    # failure almost always says something, and a code other than 1 is not an answer shape at all.
    if code == 1 and not detail:
        return ""
    # The exit code is the KIND; `gotcha.normalise` keeps it whole and drops the detail.
    return f"Exit code {code}" + (f" — {detail}" if detail else "")


def record(payload, err=None):
    """Write one scrubbed line. Returns True when something was written."""
    if err is None:
        err = failure_of(payload)
    if not err:
        return False
    root = ws.hook_root(payload)
    if root is None or ws.read_only():
        return False
    if ws.workspace(root) is None or not ws.workspace(root).is_dir():
        return False                      # not a chamnan workspace; say nothing, write nothing
    err = redact.scrub(err)[:ERR_CHARS]
    row = {"at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "tool": str(payload.get("tool_name") or "")[:40],
           "subj": _subject(payload.get("tool_name"), payload.get("tool_input")),
           "err": err}
    ms = payload.get("duration_ms")
    if isinstance(ms, (int, float)):
        row["ms"] = int(ms)
    row.update(ws.actor(payload))
    ws.append_jsonl(root, LOG, row, MAX_RECORDS)
    return True


def main():
    try:
        payload = json.load(sys.stdin)
        payload = payload if isinstance(payload, dict) else {}
    except (ValueError, RecursionError, OSError):
        return 0
    record(payload)
    # Nothing is printed. A failure the session can already see does not need chamnan to repeat it,
    # and this hook exists to remember, not to comment.
    return 0


if __name__ == "__main__":
    sys.exit(ws.never_fail(main))
