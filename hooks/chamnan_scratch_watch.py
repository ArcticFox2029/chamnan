#!/usr/bin/env python3
"""PostToolUse hook — notice when the same throwaway script keeps being rewritten.

A one-off script is fine. The waste is the analysis re-derived every few days: the same check,
thought up again from scratch, arriving slightly different each time. That is both tokens spent
twice and a check that cannot be trusted to compare runs.

This does not block anything and does not write files anywhere the user did not ask for. It watches
inline scripts, fingerprints them, and when a third near-identical one appears it says so once, then
gets out of the way. Suggesting is the whole job — deciding what deserves to be kept is the user's.

Similarity is a Jaccard overlap of long-ish word tokens. Deliberately crude: a fingerprint that
needed parsing would have to understand every language a user might write a scratch script in.
"""
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
import candidates  # noqa: E402
import environments  # noqa: E402
import redact  # noqa: E402
import sessions  # noqa: E402
import tools_index  # noqa: E402
import workflows  # noqa: E402
import workspace as ws  # noqa: E402

HEREDOC = re.compile(r"<<-?\s*'?([A-Za-z_][A-Za-z0-9_]*)'?\s*\n(.*?)\n\1", re.S)
TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")
SIMILAR = 0.55        # Jaccard at or above this counts as "the same script again"
REPEAT_AT = 3         # say something on the third one, not the second
KEEP_ENTRIES = 300    # bounded log; this is a hint generator, not an archive
# Unique identifiers of four characters or more. A real five-line analysis script has about
# eight; 12 was tuned against long scripts and silently ignored exactly the short, repeated
# one-off that this hook exists to catch. Found by the test suite, not in use.
MIN_TOKENS = 8
# How many PostToolUse calls (Bash, Write or Edit -- every tool this hook sees) a session has to
# make before the resume nudge is even considered. Not the first thing a session sees before any
# real work has happened; low enough to still fire well inside a normal working session.
# 🐛 One ask per session, at call 10, and then silence. Measured on a real work repository: a
# session ran 489 calls over three days, the nudge fired once near the very beginning, and the
# workspace finished with zero sessions, decisions, lessons, rules and threads recorded — while
# Claude Code's own memory tool captured six substantive lessons from the same work in the same
# window. Asking once, early, before there is much to record, and never again is close to not
# asking at all.
#
# Three points across a long session instead, and only ever while nothing is recorded for today.
# Not more than three: the thing this protects against is a tool that nags, and a session that has
# declined twice has answered.
NUDGE_AT = 10
NUDGE_AGAIN_AT = (150, 400)


def body_of(payload):
    name = payload.get("tool_name") or ""
    inp = payload.get("tool_input") or {}
    if name == "Bash":
        cmd = str(inp.get("command") or "")
        blocks = [m.group(2) for m in HEREDOC.finditer(cmd)]
        return max(blocks, key=len) if blocks else ""
    if name in ("Write", "Edit"):
        path = str(inp.get("file_path") or "")
        if "/tmp/" in path or "/scratch" in path:
            return str(inp.get("content") or inp.get("new_string") or "")
    return ""


def fingerprint(text):
    return set(t.lower() for t in TOKEN.findall(text))


SKIP_HEAD = re.compile(r"^\s*(#|//|/\*|\*|import\b|from\b|require\(|use\b|package\b|$)")


def headline(text):
    """The first line that says something. The literal first line is usually `import json`, which
    makes every digest entry look identical and tells the reader nothing about which script it was."""
    for line in text.strip().splitlines():
        if not SKIP_HEAD.match(line):
            return " ".join(line.split())[:80]
    return " ".join(text.strip().splitlines()[0].split())[:80] if text.strip() else ""



NUDGE_DIR = "logs/nudge"
NUDGE_MAX_AGE = 2 * 24 * 3600     # a session older than this is over; its marker is dead weight


def _nudge_path(wsdir, session_id):
    """One state file per session, never one shared dict keyed by session id.

    The shared file was a read-modify-write with no lock, and two sessions in one repository is
    normal rather than exotic -- 98 of 100 concurrent increments were lost when it was measured
    at the function level. It stayed valid JSON the whole time, just wrong, which is the lost
    update anomaly: an atomic write does not prevent it, only a lock spanning read AND write, or
    not sharing the file at all.

    lib/pointer.py reached the same conclusion for exactly the same shape of store and chose the
    same answer, with the reasoning written out there: a lock would have to survive flock's
    non-reentrancy and fcntl's rule that closing any descriptor drops the process's locks, while
    a per-session file needs none of that to be correct. This applies that decision to the one
    store in this package that had not received it. The eviction loop goes with it -- a sweep of
    files older than the session that wrote them replaces counting entries in one dict.
    """
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in str(session_id))[:64] or "none"
    return wsdir / NUDGE_DIR / f"{safe}.json"


def _nudge_read(wsdir, session_id):
    try:
        d = json.loads(_nudge_path(wsdir, session_id).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"calls": 0, "nudged": False}
    # Valid JSON of the wrong shape is not a missing file: a list here raised AttributeError on
    # every subsequent tool call in the session.
    return d if isinstance(d, dict) else {"calls": 0, "nudged": False}


def _nudge_write(wsdir, session_id, entry):
    p = _nudge_path(wsdir, session_id)
    try:
        # Shared `.tmp` name, same bug as pointer.py and chamnan-map had. See ws.atomic_write_text.
        ws.atomic_write_text(p, json.dumps(entry))
        for old in p.parent.glob("*.json"):
            if old != p and time.time() - old.stat().st_mtime > NUDGE_MAX_AGE:
                old.unlink()
    except OSError:
        pass


def say(text):
    """Emit one notice to the model.

    PostToolUse is NOT one of the four events whose plain stdout Claude Code shows to the model --
    only `UserPromptSubmit`, `UserPromptExpansion`, `SessionStart` and `PostModelSwitch` are, and
    everything else goes to the debug log alone. A `print()` here therefore reached nobody. The
    documented channel for this event is a JSON object on stdout carrying
    `hookSpecificOutput.additionalContext`, which is what the two PreToolUse hooks in this
    directory have always used. Exactly one object may be written, which is why every check in
    main() returns immediately after speaking.
    """
    sys.stdout.write(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse", "additionalContext": text}}) + "\n")

def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def notice_workflow(payload, wsdir, root):
    """Record this command's signatures, keep the candidate for the qualifying sequence in sync,
    and speak if it has just reached the threshold.

    The candidate is written every time the sequence still qualifies, not only on the crossing --
    `candidates.upsert()` is idempotent when nothing changed (same day-count, same date) and
    correct when something did (a new day, a longer sequence), so writing it unconditionally here
    costs nothing extra and means the file never falls behind what repeated() currently knows.
    Speaking stays gated to the crossing; a candidate updating silently in the background is not a
    second notice.

    Returns True when it spoke, so the caller does not also fire the script-repeat hint or the
    resume nudge. Two notices in one turn is how a useful nudge becomes noise.
    """
    if (payload.get("tool_name") or "") != "Bash":
        return False
    command = str((payload.get("tool_input") or {}).get("command") or "")
    sigs = workflows.signatures(command)
    if not sigs:
        return False
    # There is no exit code in a Bash tool_response -- only stdout, stderr and interrupted -- so
    # this is the one honest piece of evidence about whether the call went cleanly.
    interrupted = bool((payload.get("tool_response") or {}).get("interrupted"))

    now = datetime.now().astimezone().isoformat(timespec="seconds")
    log = wsdir / "logs" / "commands.jsonl"
    before = workflows.repeated(workflows.read(log))
    history = workflows.record(log, sigs, now, tool="Bash", interrupted=interrupted)
    found = workflows.repeated(history)
    if not found:
        return False
    sequence, count = found

    candidate_path, _is_new = candidates.upsert(root, sequence, count, now[:10],
                                                provenance="ai-inferred")

    # Only the crossing speaks. If this exact sequence already qualified before this command, the
    # threshold was passed earlier and saying so again is repetition.
    if before and before[0] == sequence:
        return False
    say(workflows.describe(sequence, count, candidate_path.relative_to(root)))
    return True


_HAS_AS_OF = re.compile(r"^\*\*As-of:\*\*", re.M)
_HAS_PROVENANCE = re.compile(r"^\*\*Provenance:\*\*", re.M)


def _stamp_memory_entry(payload, root):
    """If this Write/Edit just touched a file under `.chamnan/memory/`, add `As-of:` and
    `Provenance:` trailers when the file does not already have them. Silent -- this never prints,
    because it is a mechanical fixup, not a notice, and does not compete with the one-message-per-
    turn budget the other checks in this file share.

    This is the one place `As-of` actually gets written, and it is a hook for the same reason the
    write-skills line and the ledger exist: `skills/remember/SKILL.md` could simply ASK Claude to
    include the field, but this project's founding finding is that a memory system's skill-written
    stores sat empty for five weeks precisely because things that depend on being remembered do not
    reliably happen. `As-of` is objective (today's date) and `Provenance` defaults to `ai-drafted`
    because that is the mechanical truth of how the file arrived -- through a tool call, not yet
    confirmed by a human. Promoting it to `ai-confirmed` is a human decision (Stage 7, 1.5.1), not
    something a hook can honestly do for itself.
    """
    if (payload.get("tool_name") or "") not in ("Write", "Edit"):
        return
    file_path = str((payload.get("tool_input") or {}).get("file_path") or "")
    if not file_path:
        return
    memory_dir = (root / ".chamnan" / "memory").resolve()
    try:
        resolved = Path(file_path).resolve()
    except OSError:
        return
    if memory_dir not in resolved.parents or resolved.suffix != ".md":
        return
    try:
        text = resolved.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    if not text.strip():
        return

    additions = []
    if not _HAS_AS_OF.search(text):
        today = datetime.now().astimezone().strftime("%Y-%m-%d")
        additions.append(f"**As-of:** {today}")
    if not _HAS_PROVENANCE.search(text):
        additions.append("**Provenance:** ai-drafted")
    if not additions:
        return

    stamped = text.rstrip("\n") + "\n\n" + "\n".join(additions) + "\n"
    try:
        resolved.write_text(stamped, encoding="utf-8")
    except OSError:
        pass


def _track_tool_health(payload, root):
    """Silent unless a flag threshold is FRESHLY crossed. See lib/tools_index.py for exactly what
    is and is not tracked, and why -- there is no exit code in a Bash tool_response, so this counts
    `interrupted` (a real fact) and non-empty `stderr` (a weak signal, shown as itself, never
    reported as "the tool failed").

    Also where `runs` gets incremented (Stage 11 reads it; nothing writes it before this).
    """
    if (payload.get("tool_name") or "") != "Bash":
        return False
    command = str((payload.get("tool_input") or {}).get("command") or "")
    name = tools_index.match_call(root, command)
    if name is None:
        return False
    response = payload.get("tool_response") or {}
    interrupted = bool(response.get("interrupted"))
    stderr_nonempty = bool((response.get("stderr") or "").strip())
    entry, just_flagged = tools_index.record_call(root, name, interrupted, stderr_nonempty)
    if not just_flagged or entry is None:
        return False
    signal = max(entry.get("interrupted", 0), entry.get("stderr_seen", 0))
    say(f"chamnan: `.chamnan/tools/{name}` has been interrupted or written to stderr "
          f"{signal} times in its last {entry.get('runs', '?')} run(s) — worth a look. "
          f"`chamnan-candidates demote {name}` sends it back for review if it no longer does "
          f"what you expect.")
    return True


def _environment_notice(payload, wsdir, root):
    """Once per environment per session: the constraints declared for the environment a Bash
    command just targeted.

    **This is PostToolUse, and it is deliberately not a guard.** Stage 15 proposed intercepting
    the command beforehand, which needs a PreToolUse `permissionDecision` — and the documented
    enum is `allow`/`deny`/`escalate` with no `ask` at all, while whether `escalate` reaches a
    prompt under `defaultMode: "auto"` is not documented either way. A guard that might silently
    fail to fire is worse than no guard, because it is trusted. So the constraints go in front of
    the agent by two mechanisms that ARE proven here: chamnan_session_start.py injects every environment's
    constraints before any command is written, and this names the specific one the moment a
    session is demonstrably working against it — so the NEXT command, which is usually the one
    that matters, is written knowing.

    Once per (session, environment), tracked in the same state file and by the same `session_id`
    the resume nudge uses. A notice that fired on every `kubectl --context prod` call is one
    people learn to scroll past.
    """
    if not ws.enabled("environments", root):
        return False
    if (payload.get("tool_name") or "") != "Bash":
        return False
    command = str((payload.get("tool_input") or {}).get("command") or "")
    name = environments.match_command(root, command)
    if not name:
        return False
    notice = environments.constraints_notice(root, name)
    if not notice:
        return False

    session_id = str(payload.get("session_id") or "")
    if not session_id:
        return False
    entry = _nudge_read(wsdir, session_id)
    told = entry.get("envs_told") or []
    if name in told:
        return False
    entry["envs_told"] = told + [name]
    _nudge_write(wsdir, session_id, entry)
    # The constraint text comes straight out of a committed `environments.md`. The SessionStart
    # block scrubs the same text; this second, automatic path did not, and it fires on any Bash
    # command that matches a declared environment — so the guarded and unguarded readers of one
    # store sat two hooks apart.
    say(redact.scrub(notice))
    return True


def _resume_nudge(payload, wsdir, root):
    """Once per session: if a fair bit of work has already happened here and nothing is recorded
    for today, say so. Silent otherwise -- gated on the same "ledger" flag as the write-skills line
    and the ledger line, since this is the same finding (an empty store nobody notices) applied at
    the moment it can still be acted on, rather than only in the numbers chamnan_session_start.py prints.

    Tracked per `session_id`, which every PostToolUse payload carries (confirmed against another
    installed plugin's own use of the same field). A CALENDAR-DAY marker would fire once per day
    regardless of which session is running; "once per session" is a different, narrower promise --
    a second session on the same day has not seen whatever the first one already said, so it gets
    its own chance to nudge.
    """
    if not ws.enabled("ledger", root):
        return False
    session_id = str(payload.get("session_id") or "")
    if not session_id:
        return False

    entry = _nudge_read(wsdir, session_id)
    entry["calls"] = entry.get("calls", 0) + 1
    _nudge_write(wsdir, session_id, entry)

    if sessions.written_today(root):
        return False
    marks = [NUDGE_AT] + list(NUDGE_AGAIN_AT)
    done = int(entry.get("nudges", 1 if entry.get("nudged") else 0))
    if done >= len(marks) or entry["calls"] < marks[done]:
        return False

    entry["nudges"] = done + 1
    entry["nudged"] = True          # kept so an older workspace's state still reads correctly
    _nudge_write(wsdir, session_id, entry)
    # The later asks say something the first one cannot: that the session is long now, which is the
    # actual argument for recording it.
    if done == 0:
        say("chamnan: a fair bit has happened this session and nothing is recorded for today yet. "
            "/chamnan:resume takes about 30 seconds and is what the next session reads first.")
    else:
        say(f"chamnan: {entry['calls']} calls into this session and still nothing recorded for "
            f"today. Whatever you worked out here is about to be the next session's problem to "
            f"work out again — /chamnan:resume is 30 seconds.")
    return True


def _record_edit(payload, root, wsdir):
    """Append this edit to the ledger co-edit partners are counted from. Never prints, never fails.

    chamnan's own files are excluded. A session that edits `.chamnan/STATE.md` after every third
    source file would otherwise learn that every file in the repository is followed by STATE.md,
    which is true and useless.
    """
    if (payload.get("tool_name") or "") not in ("Write", "Edit"):
        return
    file_path = str((payload.get("tool_input") or {}).get("file_path") or "")
    if not file_path:
        return
    try:
        resolved = Path(file_path).resolve()
        rel = resolved.relative_to(Path(root).resolve())
    except (OSError, ValueError):
        return
    if rel.parts and rel.parts[0] == ".chamnan":
        return
    import coedit
    coedit.record(wsdir, rel)


def main():
    try:
        payload = json.load(sys.stdin)
        # A payload that parses but is not an object -- JSON `null`, or an array -- used to
        # crash on .get() with an AttributeError, on every matching call, all session.
        payload = payload if isinstance(payload, dict) else {}
    except Exception:
        return 0
    root = ws.hook_root(payload)
    wsdir = ws.workspace(root)
    if not wsdir.is_dir():
        return 0

    # Silent and independent of everything below: never prints, so it does not compete for the
    # one-notice-per-turn budget the checks after it share.
    #
    # Gated on `memory`, and checked BEFORE the `promote` gate rather than under it. It used to sit
    # inside that gate, which meant `"memory": false` still stamped As-of/Provenance trailers onto
    # memory entries and `"promote": false` stopped it -- the exact opposite of what the remember
    # skill documents, in both directions.
    if ws.enabled("memory", root):
        _stamp_memory_entry(payload, root)
        # Silent, and the whole point: this is the one thing chamnan can learn without the user
        # doing anything. Measured on a real work repository, three days and 764 commands produced
        # zero recorded sessions, decisions, lessons, rules and threads, because every one of those
        # needs a command somebody has to remember to run. An edit is a fact the hook already sees.
        # `lib/coedit.py` carries the measurement behind it.
        _record_edit(payload, root, wsdir)

    if not ws.enabled("promote", root):
        return 0

    # A plain Bash command carries no script body, so the path below ignores it entirely — and a
    # repeated SEQUENCE of them is the thing that leaves no file behind at all. Checked first, and
    # only one of the two ever speaks in a single turn.
    if notice_workflow(payload, wsdir, root):
        return 0

    # Runs (silently) on every Bash call regardless of what it invoked; only speaks on the call
    # that freshly crosses a flag threshold for a promoted tool.
    if _track_tool_health(payload, root):
        return 0

    # Before the resume nudge: a command that just touched a declared environment is the more
    # specific, more time-sensitive thing to say, and only one notice speaks per turn.
    if _environment_notice(payload, wsdir, root):
        return 0

    # Independent of the above: this counts every PostToolUse call regardless of tool, so it still
    # runs even when notice_workflow's own checks return early for a non-Bash call.
    if _resume_nudge(payload, wsdir, root):
        return 0

    text = body_of(payload)
    if not text.strip():
        return 0
    fp = fingerprint(text)
    if len(fp) < MIN_TOKENS:
        return 0

    tool_name = payload.get("tool_name") or ""
    file_path = str((payload.get("tool_input") or {}).get("file_path") or "")

    log = wsdir / "logs" / "scratch.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    prior = []
    if log.is_file():
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                _rec = json.loads(line)
                # A line that is valid JSON but not an object -- a stray number left by a
                # half-written entry -- parsed fine and then raised AttributeError later.
                if isinstance(_rec, dict):
                    prior.append(_rec)
            except json.JSONDecodeError:
                continue

    # A record with no `kind` predates this field and is a scratch fingerprint by construction --
    # nothing else was ever written here before now -- so missing reads as "scratch". Anything
    # tagged something else must not be treated as one, the same rule workflows._runs() applies to
    # commands.jsonl: a future record shape sharing this log must not silently join a comparison it
    # was not written for.
    matches = [p for p in prior
               if p.get("kind", "scratch") == "scratch" and jaccard(fp, set(p.get("fp", []))) >= SIMILAR]
    entry = {
        "at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "kind": "scratch",
        "tool": tool_name,
        "fp": sorted(fp)[:120],
        "head": headline(text),
    }
    if file_path:
        entry["file"] = file_path
    prior.append(entry)
    log.write_text("\n".join(json.dumps(p, ensure_ascii=False) for p in prior[-KEEP_ENTRIES:]) + "\n",
                   encoding="utf-8")

    # Only the exact threshold speaks. Firing on every later repeat would turn a useful nudge into
    # noise the user learns to scroll past.
    if len(matches) + 1 == REPEAT_AT:
        first = matches[0].get("at", "")[:10]
        say(f"chamnan: that is the {REPEAT_AT}rd near-identical scratch script since {first}. "
              f"If it is worth keeping, save it and run: "
              f"chamnan-promote <file> <name> --desc \"what it checks\" — "
              f"then it is one command next time instead of writing it again.")
    return 0


def _never_fail_the_session():
    """`main()`, but a hook that hits something it cannot read exits 0 in silence rather than
    exiting 1 with a traceback.

    A hook's stderr never reaches the transcript, so a crash here is invisible: the session simply
    starts without whatever this hook contributes, and nothing says why. Measured with a
    `chmod 000` on `.chamnan/logs` — the ordinary result of a container or CI run touching the
    workspace as root — four of the five hooks died this way. Silence is the correct failure for a
    hook that only writes; `chamnan_session_start.py` does more than this, because it has something
    partial worth emitting.
    """
    try:
        return main()
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(_never_fail_the_session())
