#!/usr/bin/env python3
"""SessionEnd hook — one quiet digest of what repeated today, left for the next session.

The inline nudge in chamnan_scratch_watch.py speaks once, at the moment the third copy of a script is
written, because that is when the file still exists and promoting it costs one command. This is the
other half: at the end of the session, everything that repeated and was never kept gets summarised
in one place, so a pattern that built up across the day is visible even if the moment was missed.

Deliberately not a second chance to nag. It writes at most a handful of lines, chamnan_session_start.py
shows them exactly once and deletes the file, and nothing is written at all when there is nothing
to say.
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
import workspace as ws  # noqa: E402
from workflows import SIMILAR, jaccard  # noqa: E402

WINDOW_HOURS = 24
MIN_REPEATS = 2
MAX_LISTED = 4
# Two bounds on the clustering below, because it is O(entries x families) and SessionEnd is the one
# event with a tight budget: the documented allowance is 1.5 SECONDS SHARED BY EVERY SessionEnd
# hook installed, against 600s for an ordinary hook. Measured on this machine, with every entry
# distinct so each one opens its own family: 300 entries 0.46s, 1,200 entries 7.62s, 2,400 entries
# 30.50s. Over budget the hook is killed, the digest is never written, and the next session is
# simply never told -- a silent failure of the one thing this file does.
#
# scratch_watch caps its log at 300 entries, so the first number is today's realistic worst case
# and it already spends a third of a budget chamnan does not own alone. These bounds hold the work
# flat whatever the file turns out to contain.
MAX_CLUSTERED = 400
# Past this many DISTINCT scripts there is nothing to digest anyway -- the digest reports what
# repeated, and a session with hundreds of one-off scripts has no repeats to report. Entries still
# join a family they match; they just stop opening new ones to be compared against.
MAX_FAMILIES = 120
# Read, shown once and deleted by chamnan_session_start.py on the next session in this repository.
DIGEST_NAME = "repeat_digest.json"


# ENFORCES: memory/rules/a-bad-result-earns-a-gotcha.md
# 🎯 "A result that came out badly earns a gotcha — every time, whatever produced it." The rule is
# about the thing nobody does when tired: the failure is fixed, the session ends, and the reason is
# never written down, so the next session repeats it. This is asked at the one moment the answer is
# known — the end — and it compares two numbers rather than trusting a memory.
GOTCHA_MARK = "\U0001F41B"
MARK_STATE = "state/gotcha_marks.json"
_COUNTED = (".py", ".sh", ".md", ".js", ".ts", ".json")


def _marks(root):
    """How many recorded gotchas exist right now, across the places they are written."""
    n = 0
    for base in (Path(root) / ws.WORKSPACE_DIRNAME, Path(root)):
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if (path.is_file() and path.suffix in _COUNTED
                    and ".git" not in path.parts and "__pycache__" not in path.parts):
                try:
                    n += path.read_text(encoding="utf-8", errors="replace").count(GOTCHA_MARK)
                except OSError:
                    continue
        break                      # the workspace alone: the whole repo is too slow to sweep here
    return n


def _repeated_failures(wsdir):
    """Failures that happened more than once today — the ones a gotcha is owed for."""
    try:
        import gotcha
        return sum(1 for _k, v in gotcha.repeats(wsdir).items() if v[0] >= gotcha.REPEATS)
    except Exception:              # noqa: BLE001
        return 0


def _a_gotcha_is_owed(root, wsdir):
    """"today went wrong N times and nothing was written down" — or "", which is the good case."""
    try:
        import json as _json
        repeats = _repeated_failures(wsdir)
        state = wsdir / MARK_STATE
        before = 0
        if state.is_file():
            before = int(_json.loads(state.read_text(encoding="utf-8")).get("marks", 0))
        now = _marks(root)
        state.parent.mkdir(parents=True, exist_ok=True)
        ws.atomic_write_text(state, _json.dumps({"marks": now}), encoding="utf-8")
        if repeats and now <= before:
            return ("chamnan: %d thing(s) failed more than once here and no gotcha was written "
                    "(%d recorded, unchanged). A result that came out badly earns one — every "
                    "time, whatever produced it. `memory/rules/a-bad-result-earns-a-gotcha.md`."
                    % (repeats, now))
        return ""
    except Exception:              # noqa: BLE001 — a notice is never worth a failed hook
        return ""

def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    root = ws.hook_root(payload)
    wsdir = ws.workspace(root)
    if not wsdir.is_dir() or not ws.enabled("promote", root):
        return 0
    _owed = _a_gotcha_is_owed(root, wsdir)
    if _owed:
        print(_owed)

    log = wsdir / "logs" / "scratch.jsonl"
    if not log.is_file():
        return 0

    cutoff = datetime.now().astimezone() - timedelta(hours=WINDOW_HOURS)
    recent = []
    for line in log.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        try:
            rec = json.loads(line)
            when = datetime.fromisoformat(rec["at"])
        except Exception:
            continue
        # Adopted, not discarded. A naive timestamp — from a hand edit, or a writer that
        # predates the .astimezone() convention — parses fine and then raises TypeError on
        # the comparison below, uncaught, killing the whole hook over one line. Assuming
        # local time is what the record almost certainly meant; dropping it would silently
        # lose real work from the digest, which is the thing this hook exists to produce.
        if when.tzinfo is None:
            when = when.astimezone()
        if when >= cutoff:
            recent.append((set(rec.get("fp", [])), rec.get("head", "")))
    # Newest first, then bounded: a digest of what repeated TODAY should keep the most recent work
    # if it has to drop any.
    recent = recent[-MAX_CLUSTERED:]

    # Single-pass clustering: each script joins the first family it is close enough to. Good enough
    # for a digest — the alternative is a clustering algorithm nobody will tune.
    families = []
    for fp, head in recent:
        for fam in families:
            if jaccard(fp, fam["fp"]) >= SIMILAR:
                fam["n"] += 1
                break
        else:
            # `else` on the FOR, not on the if -- it runs when no family matched.
            if len(families) < MAX_FAMILIES:
                families.append({"fp": fp, "n": 1, "head": head})

    repeated = sorted((f for f in families if f["n"] > MIN_REPEATS), key=lambda f: -f["n"])
    if not repeated:
        return 0

    # Handed to the next session rather than printed. SessionEnd is not one of the four events
    # whose stdout Claude Code shows the model -- and by then the session it would be speaking to
    # is over anyway, so a `print()` here reached nobody at all. Writing the digest turns the same
    # finding into something SessionStart can say at the one moment it can still be acted on.
    digest = {
        "at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "lines": [f"{fam['n']}x  `{fam['head'][:70]}`" for fam in repeated[:MAX_LISTED]],
    }
    # \U0001f41b [2026-09-10] `Path.write_text` truncates on open, and this file has exactly one
    # reader: `chamnan_session_start.py`, which `json.load`s it and deletes it. A session ending
    # while the next one starts — closing one window and opening another is how that happens — let
    # the reader see the truncated middle, and a `json.load` on it drops the whole digest silently.
    # The repository's answer to this has been one function since `atomic_write_text` was written;
    # this call and `workspace.reconcile_version` were the two shipped writers still not using it.
    out = wsdir / "logs" / DIGEST_NAME
    ws.atomic_write_text(out, json.dumps(digest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(ws.never_fail(main))
