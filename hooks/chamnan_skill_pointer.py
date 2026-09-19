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
COMMAND being run, and it holds itself to the same four rules: silent when it has nothing, at most
three times per procedure per session, never noisy, and never about chamnan's own reading of itself.

**The mapping lives in the skills, not here.** Each procedure declares `COVERS: <pattern> | <pattern>`
in its own header, so a new procedure arrives with its triggers and this file never changes. A table
in the hook would be the defect this repository records most often — a set maintained in one place
and forgotten in the other.

🐛 [2026-09-18] (R19 agent 4, 2026-09-18) "Once per procedure per session" assumed a session is short. Measured on this
repository's own session today, from `.chamnan/logs/commands.jsonl` and the old
`logs/skill_pointer_seen.json`: 387 tool commands over 8.0 hours (07:12 → 15:12), the pointer spoke
3 times — one procedure each — all before 08:30, then silence for roughly 360 commands. The
heaviest three hours of work, 271 of the 387 commands, got no pointer at all. This is the identical
defect already found and fixed in the sibling hook, `chamnan_scratch_watch.py` (its `NUDGE_AT` /
`NUDGE_AGAIN_AT` comment there, "one ask per session, at call 10, and then silence"): a budget keyed
to "session" instead of to elapsed work goes quiet exactly when a long session most needs it. Fixed
the same way here — a procedure may speak up to three times per session, mirroring the sibling's
own re-ask marks so the two numbers cannot drift apart.
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import workspace as ws  # noqa: E402

# Mirrors chamnan_scratch_watch.NUDGE_AGAIN_AT (its resume nudge fires again at 150 and 400 calls).
# Kept as a literal rather than an import: that module's top-level pulls in `redact` and other
# PostToolUse-only weight this frequently-run PreToolUse hook should not pay for on every command
# (see the dated note further down about two PreToolUse hooks on Bash doubling the cost -- it is
# referenced, not repeated, because a bug marker in a cross-reference reads as a second defect
# record to anything that counts them). The two
# constants must move together by hand.
NUDGE_AGAIN_AT = (150, 400)

# One state file per session (own directory — this hook does not share chamnan_scratch_watch.py's
# `logs/nudge`, because its entries are keyed per PROCEDURE, not one counter for the whole session).
NUDGE_DIR = "logs/skill_pointer_nudge"
NUDGE_MAX_AGE = 2 * 24 * 3600     # a session older than this is over; its marker is dead weight


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


def _nudge_path(wsdir, session_id):
    """One state file per session, never one shared dict keyed by session id — the same reasoning
    as chamnan_scratch_watch.py's `_nudge_path`: a shared file is a read-modify-write with no lock,
    and two writers on one repository is normal rather than exotic. This hook does not reuse that
    module's file, because its entries are keyed per procedure rather than one counter."""
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in str(session_id))[:64] or "none"
    return wsdir / NUDGE_DIR / f"{safe}.json"


def _nudge_read(wsdir, session_id):
    try:
        d = json.loads(_nudge_path(wsdir, session_id).read_text(encoding="utf-8-sig"))
    except (UnicodeDecodeError, OSError, json.JSONDecodeError, RecursionError):
        return {"calls": 0, "procs": {}}
    # Valid JSON of the wrong shape is not a missing file.
    return d if isinstance(d, dict) else {"calls": 0, "procs": {}}


def _nudge_write(wsdir, session_id, entry):
    if ws.read_only():
        return
    p = _nudge_path(wsdir, session_id)
    try:
        ws.atomic_write_text(p, json.dumps(entry))
        for old in p.parent.glob("*.json"):
            if old != p and time.time() - old.stat().st_mtime > NUDGE_MAX_AGE:
                old.unlink()
    except OSError:
        pass


# 🐛 [2026-09-18] (R19 agent 4, 2026-09-18) The division is the owner's, set 2026-09-16 and written in two skills and in the
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
        # The argv is one list literal with `*words` spread into it, not `[...] + words`: a
        # concatenation is a BinOp, and the sweep that asserts every subprocess call runs git or
        # this interpreter cannot read the head of a BinOp, so it reports the site as executing
        # something unknown. And `text=True` alone decodes with the platform's preferred encoding,
        # which is not UTF-8 everywhere this ships.
        out = subprocess.run([sys.executable, str(recall), *words], cwd=str(root),
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=20).stdout
    except Exception:
        return ""
    lines = [ln for ln in out.splitlines() if ln.strip()]
    if not lines or "0 of" in lines[0]:
        return ""
    head = ["chamnan: before writing `%s` — the store was asked for you:" % Path(raw).name]
    head += ["  " + ln.strip()[:130] for ln in lines[:7]]
    head.append("  (this ran automatically; `chamnan-recall <words>` is the manual form)")
    return "\n".join(head)


# 🐛 [2026-09-19] (self-measured), from the full gate run of this date. This hook emitted four `additionalContext` payloads and ran none of them through
# the redactor — the one hook in the family that did not, while every sibling has since
# 2026-09-06. Scrub is the credential half; `for_a_terminal` is the control-character half, and it
# has to reach the TEXT: `json.dumps` escapes every non-ASCII code point to `\uXXXX`, which no
# character filter matches and which Claude Code decodes straight back on the other side.
#
# `redact` is imported HERE rather than at module scope, and that is the whole reason this was put
# off. Measured on this machine, five runs, after `workspace` is already imported (which this hook
# pays for anyway): **20.5 ms marginal**, tight across runs. This is a PreToolUse hook on every Bash
# command, so at module scope that is 20.5 ms every command, forever, including the large majority
# of commands where the hook says nothing at all. Inside the one function that writes, it is paid
# only when there is something to write. The cost argument was real; it was an argument about
# WHERE, not about whether.
def _emit(text):
    """The one place this hook writes to stdout. Scrubbed, then control-stripped, then serialised."""
    import redact
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": redact.for_a_terminal(redact.scrub(text))}}))


# 🐛 [2026-09-19] (self-measured) A `git checkout -- <directory>` was run to undo ONE file a tool had mangled, and
# it discarded every uncommitted change under that directory — four files of work that had no
# commit behind them yet. The class was already recorded in four places: two gotchas in
# `working_fixing_a_finding.md` and two "X-ray the blast radius" references in the skills. It
# happened anyway, which is this repository's own measured finding about rules: the ones that break
# are the ones with no machine.
#
# So the control moves to the moment of the command, which is the only place it can act — the
# operation is irreversible the instant it runs, and there is nothing to inspect afterwards. It
# does not block: it says how many files with uncommitted work sit inside the path, and lets the
# caller decide. A count is what was missing, not permission.
_DESTRUCTIVE = (
    ("git checkout --", "checkout -- discards every uncommitted change under the path"),
    ("git restore", "restore overwrites the working tree from the index or a commit"),
    ("git reset --hard", "reset --hard throws away every uncommitted change in the tree"),
    ("git clean", "clean deletes untracked files outright"),
    ("git stash drop", "stash drop cannot be undone once the ref is gone"),
    ("git stash clear", "stash clear deletes every stash"),
)


def _about_to_discard(command, root):
    """A line naming what an irreversible git command is about to take, or ''.

    Counts only what is actually AT RISK — files git reports as modified, staged or untracked —
    because a path holding a hundred clean files and one dirty one is a one-file decision.
    """
    _hit = next((why for frag, why in _DESTRUCTIVE if frag in command), "")
    if not _hit:
        return ""
    try:
        out = subprocess.run(["git", "-C", str(root), "status", "--porcelain"],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=10)
    except Exception:            # noqa: BLE001 — a guard must never be why a command fails
        return ""
    if out.returncode != 0:
        return ""
    dirty = [ln[3:] for ln in out.stdout.splitlines() if ln.strip()]
    if not dirty:
        return ""
    return ("chamnan: %s. %d file(s) in this repository currently carry uncommitted work.\n"
            "  Name the exact paths instead of a directory, or commit first — this is not "
            "recoverable afterwards.\n  %s" % (_hit, len(dirty), ", ".join(dirty[:6])))


def _surgery_belongs_to_the_operator(payload):
    """Editing the package's own source is step 4, and step 4 has an owner."""
    raw = (payload.get("tool_input") or {}).get("file_path") or ""
    if not raw or not any(part in raw.replace("\\", "/") for part in _SURGERY):
        return 0
    # The operating agent edits these files too; it must not be told to dispatch itself.
    if os.environ.get("CLAUDE_AGENT_NAME") or os.environ.get("CLAUDE_SUBAGENT"):
        return 0
    _emit("chamnan: this is the CUT, and the cut is step 4 — `engineer-operate` (sonnet) makes it, "
          "this session X-rays and judges. `.chamnan/skills/working_choosing_and_proving_a_change.md`. "
          "Hand it the sites the x-ray named and the A/B; never ask it whether to cut.")
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
            _emit(_already)
            return 0
    if _tool in ("Edit", "Write"):
        return _surgery_belongs_to_the_operator(payload)
    if _tool != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not command:
        return 0
    root = ws.hook_root(payload)
    _risk = _about_to_discard(command, root)
    if _risk:
        _emit(_risk)
        return 0
    wsdir = ws.workspace(root)
    if not wsdir.is_dir():
        return 0

    # 🐛 [2026-09-18] (R18 agent 1, 2026-09-18) Two PreToolUse hooks on Bash cost 234 ms per command against 132 for one —
    # measured — and every shell command in a session pays it. R18's own finding says a change is
    # perceptible at about 20% of the base, and this was doubling it. So Bash has ONE hook and it
    # does both jobs by CALLING the other module rather than copying it: the long-read notice lives
    # in `chamnan_bulk_read_notice.py` and stays there, which is the difference between reusing a
    # guard and forking one.
    _long = _long_read_notice(payload)
    if _long:
        _emit(_long)
        return 0

    # Every Bash command this hook evaluates counts toward the session's call total, whether or
    # not it matches a procedure — the same thing chamnan_scratch_watch.py's `entry["calls"]`
    # counts. Read before computing hits, so the total reflects the whole session, not just the
    # commands that happened to match.
    session = str(payload.get("session_id") or "")
    entry = _nudge_read(wsdir, session)
    entry["calls"] = entry.get("calls", 0) + 1
    calls = entry["calls"]

    hits = [(stem, pats) for stem, pats in _covers(wsdir)
            if any(pat in command for pat in pats)]
    if not hits:
        _nudge_write(wsdir, session, entry)
        return 0
    stem = hits[0][0]

    # At most three times PER PROCEDURE per session: immediately on the first match, then again
    # once the session has passed each of chamnan_scratch_watch.NUDGE_AGAIN_AT's own marks (150,
    # 400 calls) — mirrored above so the two budgets cannot drift apart. `0` stands for "no
    # minimum": unlike that hook's resume nudge, the first time IS the point of this one, so it
    # does not wait for a threshold the way NUDGE_AT does. A reminder on every command is noise,
    # and noise is what gets a hook switched off — which would be worse than the drift it exists
    # to stop, so the budget stops at three rather than firing on every later match too.
    procs = entry.setdefault("procs", {})
    proc = procs.setdefault(stem, {"nudges": 0})
    marks = (0,) + NUDGE_AGAIN_AT
    done = int(proc.get("nudges", 0))
    if done >= len(marks) or calls < marks[done]:
        _nudge_write(wsdir, session, entry)
        return 0
    proc["nudges"] = done + 1
    _nudge_write(wsdir, session, entry)

    steps = _first_steps(wsdir / "skills" / (stem + ".md"))
    lines = ["chamnan: this work has a recorded procedure — `.chamnan/skills/%s.md`" % stem]
    for s in steps:
        lines.append("  · " + s[:150])
    if steps:
        lines.append("  (read it before going further; said up to 3 times per session — now, "
                      "and again past %d and %d commands)" % NUDGE_AGAIN_AT)
    _emit("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(ws.never_fail(main))
