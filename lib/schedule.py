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


# 🐛 [2026-09-25] (R119, 2026-09-25) Every appointment was a NAIVE local time, compared with a naive
# `datetime.now()`. So it was a wall-clock reading, not an instant: set "in 2h" in Bangkok, move the
# machine to Tokyo, and it fired after one hour -- measured -- and a daylight-saving change moves it
# the same way. `due()` below claimed the opposite. An appointment is now stored with its UTC
# offset and every comparison is between instants. A record written before this has no offset
# and is read as local time, which is what it always meant.
def _aware(dt):
    """`dt` as an instant: unchanged if it carries a zone, else read as this machine's local time."""
    return dt if dt.tzinfo is not None else dt.astimezone()


def _instant(text):
    """The appointment in a record's `when` as an instant. ValueError when it is not a time."""
    return _aware(datetime.fromisoformat(str(text or "")))


def parse_when(text, now=None):
    """`1h32m`, `45m`, `2h`, `90s`, `1d`, or a wall clock like `3:50am` / `15:04`.

    Returns the datetime to fire at, or None. A clock time that has already passed today means
    tomorrow — which is what somebody typing `9:00` at midnight means, and getting that wrong would
    fire the schedule immediately and look like the feature is broken.
    """
    now = _aware(now or datetime.now())
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
    # \U0001f41b [2026-09-12] This asked with `os.kill(pid, 0)`, which is the POSIX idiom for "does
    # this process exist" and is NOT a question on Windows — CPython's own test suite says so in one
    # line: "os.kill on Windows can take an int which gets set as the exit code". Signal 0 there
    # means terminate with exit code 0, so the call that asks whether a process is alive would have
    # killed it: `chamnan-schedule list` would have stopped the process it was reporting on, and the
    # routing decision would have killed the user's own agent a moment before typing into it.
    #
    # And then the fix was wrong a second time, which is the part worth recording. A Windows branch
    # was written here from scratch — and `workspace._pid_is_alive` has been the package's answer to
    # this exact question all along, with three things the new one did not have: `use_last_error`,
    # because ctypes' own documentation says a raw `GetLastError` is unreliable; ACCESS_DENIED read
    # as "it exists and we may not open it" rather than as absence; and exit code 259 treated as
    # legal rather than as proof of life. One definition, not two.
    import workspace as _ws
    return _ws._pid_is_alive(pid)


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
          # `transport` and `handle` are recorded to REPORT where the schedule came from, not to answer
    # through — chamnan is a plugin that installs alongside a CLI, so a CLI is what it drives.
    "transport", "handle", "app_pid", "app_started", "runner_explicit",
          "cwd", "pid",
          # The WAITING process's own birth time, beside `pid` for the identical reason `app_pid`
          # is beside `app_started`: a pid alone is reused, and `describe()` must not mistake an
          # unrelated live process for the one it spawned. Named `pid_started`, not `started` —
          # that name already answers a different question, the firing timestamp read below.
          "pid_started",
          "status", "created", "reset_provider", "reset_kind", "reset_source",
          "reset_observed_at", "reset_at")

DEFAULT_RUNNER = ("claude", "-p")

# How to hand a prompt to each agent this package knows, and how to continue an existing
# conversation with it. Two vendors, two different answers to both questions, which is exactly why
# this is a table and not a constant:
#
#   claude   prompt on ARGV          resume with `--resume <id>` as a FLAG
#   codex    prompt on STDIN (`-`)   resume with `resume <id>` as a SUBCOMMAND
#
# A scheduler that hardcoded one of them would fire the wrong binary at the wrong agent — and
# silently, because both accept a trailing string without complaining.
#
# 🎯 [owner 2026-09-12] "ครอบคลุมทุก llm ที่เราวางไว้": chamnan writes context for twenty-two hosts,
# but only some of those have a CLI that can be handed a prompt from a script at all. The honest
# split is this table for the ones that do, and `--runner` for everything else — an agent framework,
# a router, an HTTP wrapper somebody writes themselves. Adding a vendor here is four values, and the
# checks derive their cases from this dict so a new row is covered the day it arrives.
#
# `start` is the argv that opens a fresh conversation. `resume` is a function of the session id,
# returning the argv that continues one; None where the vendor offers no way to. `stdin` says the
# prompt is written to the process rather than appended to its arguments.
RUNNERS = {
    "claude": {
        "start": ("claude", "-p"),
        "resume": lambda sid: ("claude", "-p", "--resume", str(sid)),
        "stdin": False,
    },
    "codex": {
        # `--skip-git-repo-check` because a scheduled job may land in a directory codex has not been
        # told to trust, and refusing there would be a failure nobody is watching for. `-` is what
        # makes it read the prompt from stdin; without it codex takes the prompt as an argument and
        # this would silently be a different command.
        "start": ("codex", "exec", "--sandbox", "read-only", "--skip-git-repo-check", "-"),
        "resume": lambda sid: ("codex", "exec", "resume", str(sid), "--sandbox", "read-only",
                               "--skip-git-repo-check", "-"),
        "stdin": True,
    },
}


def reset_observations(payload, now=None):
    """Structured future reset times in a Claude status payload or Codex rate-limit response.

    Returns records with `provider`, `limit_kind`, `resets_at` and `source`, ordered by reset time.
    Missing, nullable, malformed and past fields produce no record -- absence is expected for both
    vendors and is the signal for the caller to retain the manual path, never to guess a delay.

    🎯 [2026-09-12, R2 RQ5] Both current vendors expose an epoch-second reset, but both also
    have a live N=1 report of the field being absent or misleading. This therefore reads only the
    documented structured fields and offers them as an explicit source; it does not scrape UI text
    and it does not replace the duration/clock parser a person already controls.
    """
    if not isinstance(payload, dict):
        return []
    now = now or datetime.now()
    floor = now.timestamp()
    found = []

    def add(provider, kind, value, source):
        if isinstance(value, bool):
            return
        try:
            stamp = float(value)
        except (TypeError, ValueError, OverflowError):
            return
        if stamp <= floor:
            return
        found.append({"provider": provider, "limit_kind": str(kind), "resets_at": stamp,
                      "source": source})

    claude = payload.get("rate_limits")
    if isinstance(claude, dict):
        for kind, window in claude.items():
            if isinstance(window, dict):
                add("claude", kind, window.get("resets_at"), "statusline")

    # `account/rateLimits/read` responses may wrap the result, but `rateLimits` is the documented
    # boundary. Walk below that boundary only: an unrelated `resetsAt` elsewhere in a response is
    # not quota evidence and must not become an appointment.
    rate_roots = []

    def collect_rate_roots(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "rateLimits":
                    rate_roots.append(child)
                elif isinstance(child, (dict, list)):
                    collect_rate_roots(child)
        elif isinstance(value, list):
            for child in value:
                collect_rate_roots(child)

    collect_rate_roots(payload)

    def collect_codex(value, path=()):
        if isinstance(value, dict):
            if "resetsAt" in value:
                add("codex", ".".join(path) or "rate_limit", value.get("resetsAt"),
                    "account/rateLimits/read")
            for key, child in value.items():
                if isinstance(child, (dict, list)):
                    collect_codex(child, path + (str(key),))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                collect_codex(child, path + (str(index),))

    for rate_root in rate_roots:
        collect_codex(rate_root)

    unique = {}
    for observation in found:
        key = (observation["provider"], observation["limit_kind"],
               observation["resets_at"])
        unique[key] = observation
    return sorted(unique.values(), key=lambda item: item["resets_at"])


def reset_time(payload, now=None, limit_kind=None):
    """`(datetime-with-buffer, observation)` for the selected reset, or `(None, None)`.

    The earliest future reset is the useful default: it is the first documented window at which
    work may continue. `limit_kind` makes the choice explicit where a caller needs another window.
    """
    now = _aware(now or datetime.now())
    observations = reset_observations(payload, now=now)
    if limit_kind:
        observations = [item for item in observations
                        if item["limit_kind"] == str(limit_kind)]
    if not observations:
        return None, None
    observation = observations[0]
    target = datetime.fromtimestamp(observation["resets_at"], tz=now.tzinfo)
    return target + timedelta(seconds=BUFFER_SECONDS), observation


def runner_for(agent):
    """The table entry for `agent`, falling back to claude's shape when the agent is unknown.

    Unknown is the ordinary case rather than an error: `host.primary` answers `generic` for a
    repository with no agent set up, and twenty of the twenty-two hosts chamnan writes context for
    have no CLI this could drive. The fallback is named so the failure, when it comes, is "claude is
    not installed" rather than something shaped like a bug in here.
    """
    return RUNNERS.get(str(agent or "").lower(), RUNNERS["claude"])


# Every transport this can recognise, and the one fact each needs to be answered through.
# Ordered: the first that matches wins, most specific first. `cli` matches everything left over and
# is not a failure — a terminal with no multiplexer is the ordinary case.
TRANSPORTS = (
    ("tmux", "TMUX_PANE"),
    ("vscode", "VSCODE_INJECTION"),
    ("cursor", "CURSOR_TRACE_ID"),
    ("wezterm", "WEZTERM_PANE"),
    ("zellij", "ZELLIJ_SESSION_NAME"),
    ("screen", "STY"),
    ("windows-terminal", "WT_SESSION"),
    ("ssh", "SSH_TTY"),
)


def transport_of(env=None):
    """`(name, handle)` — how this session was reached, and the address to reach it again.

    Derived from the table above rather than written as a chain of `if`s, so a terminal added to
    it is answered by arriving. `("cli", "")` when nothing matches, which is an answer and not an
    error: it simply means there is no pane to talk back to and the schedule must resume instead.
    """
    env = os.environ if env is None else env
    for name, key in TRANSPORTS:
        if env.get(key):
            return name, env[key]
    return "cli", ""


def process_started(pid, run=None):
    """The moment `pid` was born, as a string that never changes, or "" when it cannot be known.

    Thin delegating wrapper — the body moved to `workspace._process_started` (2026-09-18), the same
    move `alive()` above already made for plain liveness, so `exclusive()`'s lock can answer the
    identical pid-reuse question without a second implementation.
    """
    import workspace as _ws
    return _ws._process_started(pid, run=run)


def agent_process(start_pid=None, env=None, run=None):
    """The pid of the agent this code runs underneath, from what the host itself says.

    The messaging socket is named for the agent's own pid — a socket called `731.sock` is the host
    stating which process it is, with no guessing and no walking.

    \U0001f41b [2026-09-12] The first version walked the parent chain by shelling out to `ps` once per
    level, up to twelve times, and matched process names against a list of agent names. Both halves
    were wrong: twelve spawns to answer one question the socket already answers, and matching by
    NAME is the `pgrep -f` mistake one step removed — this project has three incidents from deciding
    what a process is by what it is called. Where no socket is offered the answer is 0, which the
    caller already handles as "no session to talk back to" and routes around.
    """
    env = os.environ if env is None else env
    sock = env.get("CLAUDE_CODE_MESSAGING_SOCKET", "")
    if sock:
        stem = os.path.basename(sock).split(".")[0]
        if stem.isdigit():
            return int(stem)
    return 0


def still_the_same(pid, started, run=None):
    """True only when that pid is alive AND was born at the recorded moment.

    Both halves. A pid alone is reused — after a reboot, or after enough process churn — and two
    hours is long enough for it to happen. Answering "is it alive" and calling that identity is how
    a schedule ends up typing into somebody else's program.
    """
    if not pid or not started:
        return False
    # Through `alive`, which knows what "is this process there" means on each platform. Asking with
    # `os.kill(pid, 0)` directly is the bug recorded in that function: on Windows it terminates.
    if not alive(pid):
        return False
    return process_started(pid, run=run) == started


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
    """One line a person can read: when it fires, whether anything is still waiting for it.

    `watching` starts from `alive()` — a pid that is not alive is gone, full stop — and only
    downgrades that to "gone" when a recorded `pid_started` and a freshly-read one are BOTH present
    and disagree, the same pid-reuse case `still_the_same` exists to catch (R27.7). Any other combination —
    no `pid_started` recorded, or the current start time unreadable on this platform — leaves the
    answer at whatever `alive()` said, on the same bias `workspace._lock_holder_state` uses: "cannot
    tell" resolves to still watching, because a false "gone" costs a live job the user cancels, while
    a false "watching" only withholds a warning.
    """
    now = _aware(now or datetime.now())
    try:
        due = _instant(rec.get("when")).astimezone()
    except ValueError:
        return "%s — unreadable time, nothing will fire" % (rec.get("id") or "?")
    left = due - now
    status = rec.get("status") or "pending"
    if status == "firing":
        # Neither waiting nor finished. A record left here means the process was killed between
        # starting the job and recording what happened, so the job MAY have run — and saying
        # "fired" or "pending" would each be a guess in one direction.
        return ("%s — started at %s and never reported back; it may or may not have run. "
                "`cancel` it to clear." % (rec.get("id"), rec.get("started") or "?"))
    if status != "pending":
        return "%s — %s at %s" % (rec.get("id"), status, due.strftime("%H:%M"))
    pid_started = rec.get("pid_started")
    watching = alive(rec.get("pid"))
    if watching and pid_started:
        current_started = process_started(rec.get("pid"))
        if current_started and current_started != pid_started:
            watching = False
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
    now = _aware(now or datetime.now())
    out = []
    for r in rows:
        if (r.get("status") or "pending") != "pending":
            continue
        try:
            if _instant(r.get("when")) <= now:
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
    now = _aware(now or datetime.now())
    try:
        return max(0, int((now - _instant(rec.get("when"))).total_seconds()))
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


def delivery(rec):
    """How this record should be answered: `(route, argv)`. Two routes, best first.

    1. `resume` — the conversation survived even though the process did not, so a new one is told
       to continue it and the history comes with it.
    2. `fresh` — nothing survived but what was written down, so the runner is pointed at the record.

    \U0001f3af [owner 2026-09-12] There WAS a third route: type into the pane the session is still open
    in, which keeps the live context whole and is the best answer whenever it applies. It is gone,
    and the reasoning is worth keeping because it decides the shape of this whole feature.

    It required running `tmux`, and this package's README makes a promise a user can check: at
    runtime it executes `git` and this interpreter, nothing else. A pane route would have quietly
    made that false. The owner's call was to keep the promise and lose the route — and their reason
    is the better one: **the CLI is the honest boundary**. chamnan installs where a CLI lives, so a
    terminal, tmux, a shell on Linux or a command prompt on Windows are all reachable and all
    predictable. A purpose-built app or a browser tab is not, because chamnan cannot be installed
    into it at all. Supporting one multiplexer well while pretending the rest of that world is
    covered would be worse than saying plainly where the edge is.
    """
    entry = runner_for(rec.get("agent"))
    prompt = resume_prompt(rec)

    # A runner the user named is an instruction about what to execute.
    if rec.get("runner_explicit"):
        return "fresh", list(rec.get("runner") or entry["start"]) + [prompt]
    # The vendor decides how a conversation is continued: claude takes `--resume <id>` as a flag,
    # codex takes `resume <id>` as a subcommand, and a vendor with no answer takes the fresh route
    # rather than a flag invented here that it would reject.
    if rec.get("session") and entry["resume"]:
        return "resume", list(entry["resume"](rec["session"])) + ([] if entry["stdin"] else [prompt])
    return "fresh", list(entry["start"]) + ([] if entry["stdin"] else [prompt])


LOG_HEAD = 24 * 1024        # enough to see how the job started
LOG_TAIL = 40 * 1024        # and how it ended, which is usually the answer


def _trim_log(log):
    """Bound what the job log KEEPS, and return a slice of it for the status detail.

    A log over the cap is rewritten as its head, a line saying how much was dropped, and its tail.
    Both ends are kept because they answer different questions: the head says what the job was and
    whether it started, the tail says how it ended. Nothing in the middle has ever been the answer.
    """
    try:
        size = log.stat().st_size
        if size <= LOG_HEAD + LOG_TAIL:
            return log.read_text(encoding="utf-8", errors="replace")
        with open(log, "r", encoding="utf-8", errors="replace") as fh:
            head = fh.read(LOG_HEAD)
            fh.seek(max(0, size - LOG_TAIL))
            tail = fh.read()
        kept = ("%s\n\n  ---- %d byte(s) of output dropped: a job log is bounded so that a chatty "
                "session cannot fill the workspace. The head and the tail are kept. ----\n\n%s"
                % (head, size - LOG_HEAD - LOG_TAIL, tail))
        # Atomic, like every other shared write in this package: this file is read by
        # `chamnan-schedule list` and by whoever is watching a job, and a plain `write_text`
        # truncates on open — a reader arriving mid-rewrite would get a short log and conclude the
        # job produced nothing. The suite names this class by file and line, which is how this one
        # was caught minutes after it was written.
        import workspace as ws
        ws.atomic_write_text(log, kept)
        return kept
    except OSError:
        return ""


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
    route, argv = delivery(rec)
    logdir = root / ".chamnan" / LOGDIR
    logdir.mkdir(parents=True, exist_ok=True)
    log = logdir / ("%s.log" % rec.get("id"))
    # The person's own command runs in the person's environment, not in the one chamnan narrowed for
    # its own git reads (see workspace.env_for_the_persons_command).
    import workspace as _ws
    env = _ws.env_for_the_persons_command()
    # The account is the one that SET the schedule. A job that resumed on a different account would
    # spend tokens nobody intended and would not see the history the work depends on.
    if rec.get("account"):
        env["CLAUDE_CONFIG_DIR"] = str(rec["account"])
    late = lateness(rec, now() if now else None)
    # \U0001f3af [2026-09-12] "Firing once does not guarantee running once": the child can die
    # after the job starts and before the outcome is written, leaving the record `pending` for
    # something else to pick up. That makes the guarantee AT-LEAST-ONCE by accident, and the choice
    # between the two should be made rather than inherited.
    #
    # AT-MOST-ONCE is the right side here, and the reason is what this feature is for. It exists to
    # get around a usage limit; a job that fires twice spends the quota it was scheduled to wait
    # for, which is worse than one that does not fire at all — and one that does not fire is VISIBLE
    # (`list` says so) while one that fires twice looks like success from every angle.
    #
    # The claim is written BEFORE the work starts, so a killed child leaves `firing` rather than
    # `pending`: nothing picks it up, and `list` can say it was interrupted mid-flight, which is a
    # different fact from "waiting" and from "done".
    update(root, rec.get("id"), status="firing", started=_now_iso(), route=route)
    try:
        if run is not None:
            code, text = run(argv, env)
        else:
            # The prompt goes to stdin for vendors that read it there, and is already in `argv`
            # for the ones that do not. Passing it both ways would send it twice; passing it
            # neither way is a job that opens and asks nothing, which looks like success.
            entry = runner_for(rec.get("agent"))
            feed = resume_prompt(rec) if entry["stdin"] else None
            # 🐛 [2026-09-12, R1 agent 1 Q8] `capture_output=True` held the child's ENTIRE output in
            # this process's memory for up to JOB_TIMEOUT — six hours — and then wrote all of it to
            # the log. A resumed session that prints steadily is exactly the job this feature is
            # for: at 1 MB a minute that is a 360 MB string in RAM on somebody's laptop and a 360 MB
            # file in their workspace, and the report said "no truncation, only bound is the
            # timeout". It was right and it understated it: the disk was the visible half.
            #
            # The file IS the buffer now, so memory is bounded by the pipe rather than by the run,
            # and what PERSISTS is bounded separately below. A log exists to answer what happened,
            # and the head and the tail answer that; the megabyte between them is what makes
            # somebody delete the directory.
            with open(log, "w", encoding="utf-8", errors="replace") as fh:
                fh.write("scheduled for %s, fired %s, %d second(s) late\n\n"
                         % (rec.get("when"), _now_iso(), late))
                fh.flush()
                done = sp.run(argv, cwd=str(root), env=env, stdout=fh, stderr=sp.STDOUT,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=JOB_TIMEOUT, input=feed)
            code = done.returncode
            text = _trim_log(log)
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
    if run is not None:
        # The injected runner returns its output as a string rather than writing the file, so the
        # header and the body are written here for it — the real path wrote them as it went.
        try:
            import workspace as ws
            ws.atomic_write_text(log, "scheduled for %s, fired %s, %d second(s) late\n\n%s"
                                 % (rec.get("when"), _now_iso(), late, text))
        except OSError:
            pass
    update(root, rec.get("id"), status="fired" if code == 0 else "failed",
           fired=_now_iso(), late_seconds=late, exit_code=code, route=route)
    return code


def wait_and_fire(root, rid, sleep=time.sleep, now=None, run=None):
    """Sleep until the appointment, fire once, and return. This is the whole waiting process.

    It re-reads its own record every tick so `cancel` is noticed within a tick rather than at the
    end of a long wait, and so a record removed by hand simply ends the wait instead of firing.
    """
    while True:
        rec = next((r for r in read(root) if r.get("id") == rid), None)
        if rec is None or (rec.get("status") or "pending") != "pending":
            # `firing` included: a record claimed by another process is not this one's to run, which
            # is the whole point of writing the claim before the work rather than after it.
            return 0
        if due([rec], now() if now else None):
            return fire(root, rec, run=run, now=now)
        sleep(TICK_SECONDS)
