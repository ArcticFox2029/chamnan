#!/usr/bin/env python3
"""UserPromptSubmit hook: the first message after a night, in a conversation left open.

🎯 [2026-11-05] (owner) *"ถ้ากรณีเปิดทิ้งไว้ prompt แรก ที่โดนสั่ง ไม่ว่า claude folder ไหน มันควรเด้งถาม
คล้ายกฏรอง"*. The session-start hook hands off a conversation RESUMED after a night, but a window
left open overnight starts nothing: the person types into it the next morning and no SessionStart
fires. Measured on the owner's work repository: 5 of 31 nights were that case, and each re-sent the
whole conversation on every request that followed.

So the first prompt after the gap is where it is caught. The rule is the same one everywhere
(`handoff.decide`: a new date AND eight hours since the last reply). When it holds, the handoff is
written (inside a chamnan workspace only) and the model is told to ask, in one line, whether to
hand off and `/clear` before starting on the message. A "no" carries on; nothing is blocked, and
nothing here can clear a conversation by itself.

Silent in every other case, and on any doubt: no transcript, no reply in its tail, a print-mode
dispatch, or a resume the session-start hook already handed off after this same gap.
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
import handoff  # noqa: E402
import workspace as ws  # noqa: E402

# Constant: the same words every time they appear, nothing from the clock.
_ASK = ("Before starting on this message, ask the user in one line whether to hand off and clear "
        "first. On yes: write the session record as `/chamnan:resume` does, make sure "
        "`.chamnan/STATE.md` names what is still open, and ask them to type `/clear` (the new "
        "conversation starts from the handoff). On no: carry on with the message and do not ask "
        "again in this conversation._")
ASK_WRITTEN = ("_chamnan: **this conversation sat idle overnight** — a new date and eight hours or "
               "more since its last reply — so from here on every request re-sends all of it. "
               "chamnan has written its handoff to `.chamnan/logs/handoff.md`. " + _ASK)
ASK_BARE = ("_chamnan: **this conversation sat idle overnight** — a new date and eight hours or "
            "more since its last reply — so from here on every request re-sends all of it. "
            + _ASK.replace(" (the new conversation starts from the handoff)", ""))


def notice(payload):
    """The context line for this prompt, or "". Writes the handoff when it says so. Never raises."""
    if not isinstance(payload, dict):
        return ""
    if os.environ.get("CLAUDE_CODE_ENTRYPOINT", "").startswith("sdk"):
        return ""
    transcript, sid = payload.get("transcript_path"), payload.get("session_id")
    if not transcript or not sid:
        return ""
    try:
        last = handoff.last_reply_at(transcript)
        if last is None:
            return ""
        verdict, why = handoff.decide(last)
        if verdict != handoff.FRESH:
            return ""
        root = ws.hook_root(payload)
        wsdir = ws.workspace(root)
        if not wsdir.is_dir() or ws.read_only():
            return ASK_BARE
        note = wsdir / "logs" / handoff.HANDOFF_NAME
        # A resume after this same gap was already handed off at session start, and said so.
        if note.is_file() and note.stat().st_mtime > last.timestamp() \
                and ("`%s`" % sid) in note.read_text(encoding="utf-8", errors="replace"):
            return ""
        written = handoff.write_handoff(root, sid, transcript, last, why, by=handoff.BY_PROMPT)
        return ASK_WRITTEN if written else ASK_BARE
    except Exception:          # noqa: BLE001 — a notice is never worth a lost prompt
        ws.record_swallowed()
        return ""


def main():
    try:
        payload = ws.read_hook_payload()
    except Exception:          # noqa: BLE001
        return 0
    said = notice(payload)
    if said:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                                 "additionalContext": said}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
