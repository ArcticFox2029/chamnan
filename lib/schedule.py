"""Run one command later, as a quiet process that exits the moment it has fired.

**This is a SCHEDULE, not an auto-renew, and the difference is the whole design.** Nothing here
notices that a limit was hit, nothing decides on its own that work should resume, and nothing
repeats unless a person asks for a repeat. The owner's reasoning, 2026-09-11: there is no way to
know whether somebody else's session wants to wake itself up, so the safe default is that a human
names the time and chamnan keeps the appointment.

**Why not a LaunchAgent, a crontab, or a menu-bar loop.** The first two write outside the
repository, which this project forbids outright — a stray `defaults` write destroyed a terminal
profile once and the rule dates from that day. The third was how the previous generation of this
worked and it is why this one is different: that design only fired while a separate GUI application
happened to be running, so the schedule silently did nothing whenever it was not. A detached child
of the user's own shell needs no daemon, no installation, and no privileges, and it dies on its own.

**The process exits after firing.** It is not a resident service and never becomes one: it sleeps,
runs the command once, records what happened, releases its record and returns. `cancel` ends it by
the PID written in its own record — never by matching a command line, because a `pgrep -f` pattern
matches the `pgrep` that is searching for it and this project has been bitten by that three times.
"""
import json
import os
import pathlib
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta

def _here():
    """This package's `bin/`, found from this module rather than from the caller's cwd."""
    return pathlib.Path(__file__).resolve().parents[1] / "bin"


STORE = "state/scheduled.json"
LOGDIR = "logs/schedule"
# Re-read the record this often while waiting, so `cancel` is noticed within a tick rather than at
# the end of a long sleep. Short enough to feel immediate, long enough that a night-long wait costs
# a few thousand wakeups rather than a million.
TICK_SECONDS = 20
# 🎯 The previous generation added a fixed buffer to every wait, because a vendor's stated reset
# time and the moment it actually lets you through are not the same instant. Kept, and kept SMALL
# and visible: it is reported back so nobody has to discover it from the source.
BUFFER_SECONDS = 120
# The wall on a resumed job. Six hours: long enough for a session's worth of work, short enough that
# a job which hangs does not keep a process alive until the machine reboots. Every subprocess this
# package starts is bounded, and a check asserts the population rather than each call site.
JOB_TIMEOUT = 6 * 60 * 60

_DURATION = re.compile(r"\A\s*(?:(\d+)\s*d)?\s*(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?\s*(?:(\d+)\s*s)?\s*\Z",
                       re.I)
_CLOCK = re.compile(r"\A\s*(\d{1,2})[:.](\d{2})\s*(am|pm)?\s*\Z", re.I)


def parse_when(text, now=None):
    """`1h32m`, `45m`, `2h`, `90s`, `1d`, or a wall clock like `3:50am` / `15:04`.

    Returns the datetime to fire at, or None. A clock time that has already passed today means
    tomorrow — which is what somebody typing `9:00` at midnight means, and getting that wrong would
    fire the schedule immediately and look like the feature is broken.
    """
    now = now or datetime.now()
    text = (text or "").strip()
    if not text:
        return None
    m = _CLOCK.match(text)
    if m:
        hour, minute, half = int(m.group(1)), int(m.group(2)), (m.group(3) or "").lower()
        if half == "pm" and hour != 12:
            hour += 12
        elif half == "am" and hour == 12:
            hour = 0
        if hour > 23 or minute > 59:
            return None
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return target + timedelta(days=1) if target <= now else target
    m = _DURATION.match(text)
    if not m or not any(m.groups()):
        return None
    days, hours, minutes, seconds = (int(g or 0) for g in m.groups())
    total = timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
    return now + total if total.total_seconds() > 0 else None


def _store(root):
    return root / ".chamnan" / STORE


def read(root):
    """Every record, newest first. Empty on anything unreadable — a schedule store that cannot be
    read is not a reason to fail a command, and every caller here treats empty as "nothing due"."""
    p = _store(root)
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, UnicodeDecodeError, RecursionError):
        return []
    if not isinstance(data, dict):
        return []
    rows = data.get("scheduled")
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]


def alive(pid):
    """True when that pid is a process we can signal. Never matches a command line.

    `pgrep -f <pattern>` matches the `pgrep` process that is doing the searching, which has cost
    this project three separate incidents including one inside a subagent that hung for 58 minutes.
    A pid written down by the process itself is unambiguous.
    """
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError, PermissionError) as exc:
        return isinstance(exc, PermissionError)
    return True


def detach_kwargs(osname):
    """The Popen arguments that detach a child on `osname`. A pure function of the name.

    \U0001f41b [2026-09-11] This logic lived inside `spawn`, and the only way to test the branch this
    machine never takes was to patch `os.name` globally — which `pathlib` also reads, so a `Path`
    constructed anywhere inside the patched window became a `WindowsPath` and raised. It passed
    standalone and killed the folded suite twice, the second time because the function had grown a
    `Path` of its own since the first fix.
    #
    Taking the platform as an ARGUMENT removes the whole class: both branches are reachable from a
    test with nothing patched and nothing to restore, which is what makes "works on every OS" a
    thing this suite can actually assert rather than describe.
    """
    if osname == "nt":
        # Windows has neither `nohup` nor a session leader. `getattr` with a default keeps this
        # importable on a POSIX host, where those constants do not exist — the branch itself only
        # ever runs on Windows, where they always do.
        return {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
                "creationflags": (getattr(subprocess, "DETACHED_PROCESS", 0)
                                  | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))}
    # The POSIX `setsid` SYSCALL, which needs no binary — this machine has no `setsid` binary at
    # all, and `nohup` would need a shell.
    return {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL, "start_new_session": True}


def spawn(root, rid, prefix=()):
    """Start the waiting process, detached from this terminal, and return its pid.

    `start_new_session=True` is the POSIX `setsid` SYSCALL, which is present. The setsid BINARY is
    not on this machine, and reaching for it in a shell is the shape that fails here — the syscall
    through Popen needs no binary at all. On Windows the equivalent flags are passed instead, since
    neither `nohup` nor a session leader exists there.
    """
    # Built here, from this interpreter, rather than handed in. The waiter is always THIS package
    # re-entered — never an arbitrary program — and a sweep that reads every subprocess call site
    # has to be able to see that at the call. An argv passed in as an opaque variable is invisible
    # to it, which is exactly what the sweep is for.
    argv = [sys.executable, str(_here() / "chamnan-schedule"), "--wait", str(rid)]
    argv = list(prefix) + argv
    kw = dict(detach_kwargs(os.name), cwd=str(root))
    return subprocess.Popen(argv, **kw).pid


# ---------------------------------------------------------------- what a record actually carries
#
# **The record is the WORK, not a command line.** The owner's case, in their words: the limit is
# about to be hit, the job must carry on, so you fire `2h31m` and the SAME job finishes later
# without being asked to confirm anything. A command line cannot express "finish what you were
# doing" — it would mean retyping the job at exactly the moment the session is about to end, which
# is the thing this exists to avoid.
#
# So the record points at where the work is already written down, and the runner is told to resume
# from there. That is the same principle 1.26 is built on: what is RECORDED is what survives a
# compaction or a limit, and a schedule is worth exactly as much as the record it resumes from.
#
# `account` is deliberately the config directory in force when the schedule was SET, not a name and
# not a default. The schedule belongs to the session and the main account that created it; a job
# that resumed on a different account would spend tokens the owner did not intend and would not see
# the same history. Anyone wiring a different harness — a non-CLI model, an agent framework — sets
# their own `runner`, which is why it is a field rather than a constant.
#
# **Nothing here ever fires by itself.** A waiting process exists only because somebody ran `set` in
# this shell. Opening a session does not start one, reading the store does not start one, and a
# store that arrived inside a cloned repository starts nothing at all — which matters, because the
# store names a command and a repository is not a trusted author.
FIELDS = ("id", "when", "runner", "resume_from", "note", "account", "session", "agent", "pool",
          "cwd", "pid", "status", "created")

DEFAULT_RUNNER = ("claude", "-p")


def whose_session(root, env=None):
    """Which agent this session is running under, and how sure we are: `(name, strength)`.

    \U0001f3af [2026-09-11 owner] The hard part of firing later is not the context — that structure
    already exists — it is knowing WHAT to fire at. Somebody running several cascade pools, or a
    router in front of many models, cannot be served by a guess, and chamnan cannot interrogate a
    vendor to find out.

    So it does the one thing that is always true and always cheap: it remembers which agent the
    session that SET the schedule was running under, and marks the record with it. `host.primary`
    already answers that question for the twenty-two hosts this package writes context for, and it
    answers `("generic", "")` when it cannot tell — which is an honest answer and not an error.

    When the user says nothing more, the schedule fires at the main account and the agent the
    session was using. That is the owner's rule, and it is the right default precisely because a
    router makes every other default wrong: a pool chosen for one session is not a pool anyone can
    infer later, so the only defensible answer is the one that was actually in use at the time.
    """
    try:
        import host
        return host.primary(root=root, env=env)
    except Exception:      # noqa: BLE001 — an undetectable host is not a reason to refuse a schedule
        return ("generic", "")


def describe(rec, now=None):
    """One line a person can read: when it fires, whether anything is still waiting for it."""
    now = now or datetime.now()
    try:
        due = datetime.fromisoformat(str(rec.get("when") or ""))
    except ValueError:
        return "%s — unreadable time, nothing will fire" % (rec.get("id") or "?")
    left = due - now
    status = rec.get("status") or "pending"
    if status != "pending":
        return "%s — %s at %s" % (rec.get("id"), status, due.strftime("%H:%M"))
    watching = alive(rec.get("pid"))
    secs = int(left.total_seconds())
    when = ("%dh%02dm" % (secs // 3600, (secs % 3600) // 60)) if secs > 0 else "now"
    return ("%s — fires %s (in %s)%s" %
            (rec.get("id"), due.strftime("%H:%M"), when,
             "" if watching else "  ⚠ nothing is waiting for it; the process is gone"))


def _now_iso():
    return datetime.now().isoformat(timespec="seconds")


def _dump(rows):
    return json.dumps({"scheduled": rows}, indent=2, ensure_ascii=False) + "\n"


def _rows_from(text):
    try:
        data = json.loads(text or "")
    except (ValueError, RecursionError):
        return []
    if not isinstance(data, dict):
        return []
    rows = data.get("scheduled")
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def _rewrite(root, change):
    """Read-decide-write with the lock held across all three, through the shared primitive.

    Not `atomic_write_text` on its own. The two halves are not interchangeable and having only one
    looks correct: an atomic write stops a reader seeing half a file and says nothing about which
    of two writers wins, and a lock without it still lets a crash leave a torn file. Two shells
    scheduling at once is the ordinary case here, not the exotic one.
    """
    import workspace as ws
    p = _store(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    return ws.rewrite_shared(p, lambda text: _dump(change(_rows_from(text))))


def add(root, rec):
    def change(rows):
        return [r for r in rows if r.get("id") != rec.get("id")] + [rec]
    _rewrite(root, change)
    return rec


def update(root, rid, **fields):
    def change(rows):
        for r in rows:
            if r.get("id") == rid:
                r.update(fields)
        return rows
    _rewrite(root, change)


def due(rows, now=None):
    """The pending records whose time has arrived. Absolute comparison, never a countdown.

    This is the whole reason the record stores a datetime rather than a remaining duration. A
    process that sleeps in ticks and subtracts from a total counts only the ticks it was AWAKE for,
    so on a machine that suspends — this one sleeps after a single idle minute — it would be hours
    late and would have no way to know. Comparing against the clock is correct across suspend,
    hibernate, a timezone change, and a clock set backwards.
    """
    now = now or datetime.now()
    out = []
    for r in rows:
        if (r.get("status") or "pending") != "pending":
            continue
        try:
            if datetime.fromisoformat(str(r.get("when") or "")) <= now:
                out.append(r)
        except ValueError:
            continue
    return out


def lateness(rec, now=None):
    """How far past its appointment a record is firing, in seconds. Never negative.

    Reported rather than hidden. A machine asleep past the time cannot run anything, so firing late
    is the honest outcome — and a caller that printed "fired on time" regardless would be the same
    shape as reporting drift of zero because the file it compares against was missing.
    """
    now = now or datetime.now()
    try:
        return max(0, int((now - datetime.fromisoformat(str(rec.get("when") or ""))).total_seconds()))
    except ValueError:
        return 0


def resume_prompt(rec):
    """What the runner is told. It points at the record; it does not restate the work.

    The work is already written down — that is the premise of the whole feature and of 1.26's
    subject. Restating it here would mean composing the job at the moment the session is ending,
    which is the thing the schedule exists to avoid, and it would put a model prompt inside a
    package that deliberately never calls a model.
    """
    where = rec.get("resume_from") or ".chamnan/STATE.md"
    note = (rec.get("note") or "").strip()
    lines = ["Resume the work recorded in %s. It was scheduled from an earlier session that was "
             "about to reach a usage limit, so continue it rather than starting anything new."
             % where]
    if note:
        lines.append("The session that scheduled this added: %s" % note)
    return " ".join(lines)


def ws_cannot_answer():
    """The package's single definition of "a program could not be started or did not behave"."""
    import workspace as ws
    return ws.git_cannot_answer()


def fire(root, rec, run=None, now=None):
    """Run the job once, record what happened, and return. Never becomes resident.

    `run` and `now` are injectable so a test can exercise every branch without starting a process
    and without waiting — the three outcomes that matter (ran, failed, runner missing) are reachable
    without a real model call, a network, or a usage limit to hit.

    \U0001f41b [2026-09-11] `now` was NOT threaded here at first, so lateness was computed against the
    real clock while the rest of the function ran on an injected one. A test that slept a simulated
    machine five minutes past its appointment got `late_seconds: 0` back, which is exactly the
    reassuring answer this field exists to prevent — and the one property the design names as
    non-negotiable would have shipped untestable.
    """
    import subprocess as sp
    argv = list(rec.get("runner") or DEFAULT_RUNNER) + [resume_prompt(rec)]
    logdir = root / ".chamnan" / LOGDIR
    logdir.mkdir(parents=True, exist_ok=True)
    log = logdir / ("%s.log" % rec.get("id"))
    env = dict(os.environ)
    # The account is the one that SET the schedule. A job that resumed on a different account would
    # spend tokens nobody intended and would not see the history the work depends on.
    if rec.get("account"):
        env["CLAUDE_CONFIG_DIR"] = str(rec["account"])
    late = lateness(rec, now() if now else None)
    try:
        if run is not None:
            code, text = run(argv, env)
        else:
            done = sp.run(argv, cwd=str(root), env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=JOB_TIMEOUT)
            code, text = done.returncode, (done.stdout or "") + (done.stderr or "")
    except sp.TimeoutExpired:
        # A resumed job that never returns would hold this process open for ever, which is the one
        # thing it promises not to do. The wall is generous because the work is a whole session's
        # worth, and it is a wall rather than a budget: crossing it is recorded as a failure with
        # its own detail, not as a job that finished.
        update(root, rec.get("id"), status="failed", fired=_now_iso(), late_seconds=late,
               detail="the job was still running after %d seconds and was stopped" % JOB_TIMEOUT)
        return 2
    except ws_cannot_answer() as exc:
        # The one shared definition of "starting a program failed", not a tuple written again here.
        # It carries `NotImplementedError` too, which is how an environment with no process layer at
        # all fails — WASM, and some restricted CI containers — and which every hand-written tuple
        # in this package had missed. A runner that is not installed is the commonest failure on
        # somebody else's machine, and it must not read the same as a job that ran and said nothing.
        update(root, rec.get("id"), status="failed", fired=_now_iso(), late_seconds=late,
               detail="the runner could not be started: %s" % exc.__class__.__name__)
        return 2
    try:
        import workspace as ws
        ws.atomic_write_text(log, "scheduled for %s, fired %s, %d second(s) late\n\n%s"
                             % (rec.get("when"), _now_iso(), late, text))
    except OSError:
        pass
    update(root, rec.get("id"), status="fired" if code == 0 else "failed",
           fired=_now_iso(), late_seconds=late, exit_code=code)
    return code


def wait_and_fire(root, rid, sleep=time.sleep, now=None, run=None):
    """Sleep until the appointment, fire once, and return. This is the whole waiting process.

    It re-reads its own record every tick so `cancel` is noticed within a tick rather than at the
    end of a long wait, and so a record removed by hand simply ends the wait instead of firing.
    """
    while True:
        rec = next((r for r in read(root) if r.get("id") == rid), None)
        if rec is None or (rec.get("status") or "pending") != "pending":
            return 0
        if due([rec], now() if now else None):
            return fire(root, rec, run=run, now=now)
        sleep(TICK_SECONDS)
