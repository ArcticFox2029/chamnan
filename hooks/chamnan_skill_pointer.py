#!/usr/bin/env python3
"""PreToolUse hook — when a command starts a kind of work, name the procedure that covers it.

ENFORCES: memory/rules/check-for-a-skill-first-and-extend-it-not-fork-it.md, and the session-start
block's own instruction to read the matching procedure before starting that kind of task.

🐛 [2026-09-18] (R26.5) The instruction has been in the block every session since the workspace existed, and
the procedures are good, and they are still not opened at the moment they apply. The reason is not
mystery: a procedure is named at session start, and the work begins hours and a hundred thousand
tokens later. R19 measured the tier this belongs to — NIOSH ranks administrative controls fourth of
five *because they rely on people following rules* — and found that the two remedies this project
reaches for, remembering and re-reading, are the two with evidence against them. What moves the
number is a control that acts at the moment of the command.

`chamnan_file_pointer.py` already does this for a FILE being opened. This is the same idea for a
COMMAND being run, and it holds itself to the same four rules: silent when it has nothing, once per
procedure per session, never noisy, and never about chamnan's own reading of itself.

**The mapping lives in the skills, not here.** Each procedure declares `COVERS: <pattern> | <pattern>`
in its own header, so a new procedure arrives with its triggers and this file never changes. A table
in the hook would be the defect this repository records most often — a set maintained in one place
and forgotten in the other.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import workspace as ws  # noqa: E402

SEEN = "logs/skill_pointer_seen.json"


def _covers(wsdir):
    """Every procedure that declares what it covers, as (stem, [patterns])."""
    out = []
    base = wsdir / "skills"
    if not base.is_dir():
        return out
    for p in sorted(base.glob("*.md")):
        try:
            head = p.read_text(encoding="utf-8", errors="replace")[:1500]
        except OSError:
            continue
        for line in head.splitlines():
            if line.startswith("COVERS:"):
                pats = [x.strip() for x in line[len("COVERS:"):].split("|") if x.strip()]
                if pats:
                    out.append((p.stem, pats))
                break
    return out


def _first_steps(path):
    """What the procedure says to do first — declared by the procedure, never guessed.

    🐛 The first version picked the first few bullet lines it found, and on both skills tested it
    returned the gotchas rather than the steps: a reminder that quotes the wrong three lines is
    worse than one that quotes none, because it reads as the summary. A procedure knows its own
    opening moves; it declares them on a `FIRST:` line and this prints that or nothing.
    """
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:1500]
    except OSError:
        return []
    for line in head.splitlines():
        if line.startswith("FIRST:"):
            return [x.strip() for x in line[len("FIRST:"):].split("·") if x.strip()]
    return []


# 🐛 [2026-09-18] (R19 agent 4) The division is the owner's, set 2026-09-16 and written in two skills and in the
# operating agent's own definition: this session picks the work, X-rays it and designs the A/B; the
# CUT is dispatched to `engineer-operate` on sonnet; this session judges the result. On 2026-09-18 I
# made every cut of the day myself on opus — two hooks, three checks, three tools, a redactor change
# — and none of them was dispatched. Not once. The rule was read at session start and the edits
# happened hours later, which is the placement problem R19 measured rather than a mystery.
#
# So the reminder moves to the moment of the edit. It does NOT block: a one-line change, a comment,
# or the operating agent's own work would be worse for a refusal, and a hook that blocks editing is
# a hook that gets switched off within a day.
_SURGERY = ("/Work-Mode/chamnan/lib/", "/Work-Mode/chamnan/bin/", "/Work-Mode/chamnan/hooks/")


# 🎯 [R26, 2026-09-18] The Fogg Behavior Model in one line: a behaviour needs motivation, ability AND
# a prompt at the same moment — "no prompt, no behavior", however high the first two are. Measured
# here that day: `chamnan-recall` answers "does this exist already" in under a second, it was called
# TWICE, and the session wrote three tools that duplicated things the store would have named.
# Capra & Pérez-Quiñones is the same result from the user's side: people browse rather than search
# even when search is faster, because browsing costs no query formulation. Sourcegraph Cody's answer
# is the shape adopted here — automatic retrieval is the DEFAULT and asking by hand is the override,
# not the other way round.
#
# So this does not remind anyone to search. It searches, and puts the answer in front of the write.
def _what_this_repo_already_has(payload):
    """Run the store query FOR a new tool file, and show what it names. "" when nothing matches."""
    raw = (payload.get("tool_input") or {}).get("file_path") or ""
    rel = raw.replace("\\", "/")
    if "/.chamnan/tools/" not in rel or not rel.endswith((".py", ".sh")):
        return ""
    if Path(raw).exists():          # editing something that exists is not the case this is for
        return ""
    stem = Path(raw).stem
    words = [w for w in re.split(r"[-_]", stem) if len(w) > 2][:4]
    if not words:
        return ""
    root = ws.hook_root(payload)
    recall = Path(root) / "Work-Mode" / "chamnan" / "bin" / "chamnan-recall"
    if not recall.is_file():
        return ""
    try:
        out = subprocess.run([sys.executable, str(recall)] + words, cwd=str(root),
                             capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return ""
    lines = [ln for ln in out.splitlines() if ln.strip()]
    if not lines or "0 of" in lines[0]:
        return ""
    head = ["chamnan: before writing `%s` — the store was asked for you:" % Path(raw).name]
    head += ["  " + ln.strip()[:130] for ln in lines[:7]]
    head.append("  (this ran automatically; `chamnan-recall <words>` is the manual form)")
    return "\n".join(head)


def _surgery_belongs_to_the_operator(payload):
    """Editing the package's own source is step 4, and step 4 has an owner."""
    raw = (payload.get("tool_input") or {}).get("file_path") or ""
    if not raw or not any(part in raw.replace("\\", "/") for part in _SURGERY):
        return 0
    # The operating agent edits these files too; it must not be told to dispatch itself.
    if os.environ.get("CLAUDE_AGENT_NAME") or os.environ.get("CLAUDE_SUBAGENT"):
        return 0
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext":
        "chamnan: this is the CUT, and the cut is step 4 — `engineer-operate` (sonnet) makes it, "
        "this session X-rays and judges. `.chamnan/skills/working_choosing_and_proving_a_change.md`. "
        "Hand it the sites the x-ray named and the A/B; never ask it whether to cut."}}))
    return 0


def _long_read_notice(payload):
    """The bulk-read notice, from the module that owns it. "" when it has nothing to say."""
    import io as _io
    import contextlib as _ctx
    try:
        import importlib.util as _ilu
        spec = _ilu.spec_from_file_location(
            "chamnan_bulk_read_notice",
            str(Path(__file__).resolve().parent / "chamnan_bulk_read_notice.py"))
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception:
        return ""
    buf = _io.StringIO()
    try:
        # It reads stdin and prints; give it the payload and take what it printed.
        import json as _json
        _stdin, sys.stdin = sys.stdin, _io.StringIO(_json.dumps(payload))
        try:
            with _ctx.redirect_stdout(buf):
                mod.main()
        finally:
            sys.stdin = _stdin
    except Exception:
        return ""
    out = buf.getvalue().strip()
    if not out:
        return ""
    try:
        return _json.loads(out)["hookSpecificOutput"]["additionalContext"]
    except Exception:
        return ""


def main():
    try:
        payload = json.load(sys.stdin)
        payload = payload if isinstance(payload, dict) else {}
    except Exception:
        return 0
    _tool = payload.get("tool_name") or ""
    if _tool == "Write":
        _already = _what_this_repo_already_has(payload)
        if _already:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                     "additionalContext": _already}}))
            return 0
    if _tool in ("Edit", "Write"):
        return _surgery_belongs_to_the_operator(payload)
    if _tool != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not command:
        return 0
    root = ws.hook_root(payload)
    wsdir = ws.workspace(root)
    if not wsdir.is_dir():
        return 0

    # 🐛 [2026-09-18] (R18 agent 1) Two PreToolUse hooks on Bash cost 234 ms per command against 132 for one —
    # measured — and every shell command in a session pays it. R18's own finding says a change is
    # perceptible at about 20% of the base, and this was doubling it. So Bash has ONE hook and it
    # does both jobs by CALLING the other module rather than copying it: the long-read notice lives
    # in `chamnan_bulk_read_notice.py` and stays there, which is the difference between reusing a
    # guard and forking one.
    _long = _long_read_notice(payload)
    if _long:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                 "additionalContext": _long}}))
        return 0

    hits = [(stem, pats) for stem, pats in _covers(wsdir)
            if any(pat in command for pat in pats)]
    if not hits:
        return 0
    stem = hits[0][0]

    # Once per procedure per session. A reminder on every command is noise, and noise is what
    # gets a hook switched off — which would be worse than the drift it exists to stop.
    session = str(payload.get("session_id") or "")
    seen_path = wsdir / SEEN
    try:
        seen = json.loads(seen_path.read_text(encoding="utf-8-sig")) if seen_path.is_file() else {}
    except (OSError, ValueError):
        seen = {}
    if not isinstance(seen, dict):
        seen = {}
    if stem in (seen.get(session) or []):
        return 0
    seen[session] = sorted(set((seen.get(session) or []) + [stem]))
    # Keep only the last few sessions; this file is a convenience, never a record.
    if len(seen) > 8:
        for k in list(seen)[:-8]:
            seen.pop(k, None)
    try:
        seen_path.parent.mkdir(parents=True, exist_ok=True)
        ws.atomic_write_text(seen_path, json.dumps(seen, indent=1))
    except Exception:
        pass

    steps = _first_steps(wsdir / "skills" / (stem + ".md"))
    lines = ["chamnan: this work has a recorded procedure — `.chamnan/skills/%s.md`" % stem]
    for s in steps:
        lines.append("  · " + s[:150])
    if steps:
        lines.append("  (read it before going further; this is said once per session)")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                             "additionalContext": "\n".join(lines)}}))
    return 0


if __name__ == "__main__":
    sys.exit(ws.never_fail(main))
