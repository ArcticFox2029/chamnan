"""Repeated sequences of commands — the workflow behind the scripts.

scratch_watch already catches the same SCRIPT being written a third time. This catches the thing
that happens more often and leaves no file behind at all: the same half-dozen commands, in the same
order, run again three weeks later because nobody wrote down what the sequence was.

    docker compose up · alembic upgrade · pytest tests/integration · docker compose down

That is a deployment check, or a debugging routine, or the steps to reproduce one bug. It is
knowledge, and today it survives only in whoever ran it.

**A high bar, deliberately.** Sequence detection is far noisier than comparing two script bodies:
any two working sessions share `git status` and `ls`. Four guards keep it quiet —

  1. commands are reduced to a SIGNATURE (`pytest`, `docker compose`) so arguments and paths do
     not have to match, but the tool and its subcommand do;
  2. commands too common to mean anything are dropped entirely (see NOISE);
  3. a run has to be at least MIN_LENGTH distinct signatures long;
  4. it has to have happened REPEAT_AT times.

It speaks once, at the threshold, the same restraint scratch_watch uses. A hint that fires on
every repetition is a hint people learn to scroll past.
"""
import os
import json

import workspace as ws
import re

# Reduced to "program" or "program subcommand". `git status`, `pytest`, `docker compose`,
# `npm run`. Arguments and paths are discarded on purpose: the same workflow across two branches
# will not share filenames, but it will share this.
_SUBCOMMAND_TOOLS = {
    "git", "docker", "npm", "yarn", "pnpm", "cargo", "go", "kubectl", "terraform", "helm",
    "poetry", "pip", "brew", "gh", "make", "bundle", "rails", "python3", "python", "node",
    "ansible-playbook", "systemctl", "claude",
}

# Too common to carry meaning. A sequence made only of these is two people both using a shell.
NOISE = {
    "cd", "ls", "pwd", "echo", "cat", "clear", "which", "whoami", "export", "source",
    "head", "tail", "wc", "sort", "uniq", "cp", "mv", "mkdir", "touch", "chmod", "sleep",
    "grep", "find", "sed", "awk", "less", "more", "man", "history", "env", "date",
}

# 🐛 [2026-08-27] Shell reserved words, not programs — a DIFFERENT reason for dropping a token than
# NOISE, so kept as its own set rather than folded in. `_split_unquoted` breaks a command on `;`, so
# `for f in *; do echo "$f"; done` becomes three parts whose first words are `for`, `do` and `done`;
# each parsed clean as a "program name" and was recorded as a signature. Measured on the live
# workspace this module was developed against: `do` had appeared 50 times in commands.jsonl, `for`
# 14, `done` 10, `break` 9, `then` 5 — about a fifth of the log was shell syntax, not steps of a
# workflow, and it drowned the detector this module exists to run: `repeated()` found nothing at
# all against that log until this set existed.
KEYWORDS = {
    "do", "done", "then", "fi", "else", "elif", "for", "while", "if", "case", "esac",
    "select", "until", "in", "break", "continue", "return", "function", "time", "coproc",
}

MIN_LENGTH = 3        # distinct signatures before a run counts as a workflow
REPEAT_AT = 3         # say something on the third occurrence, matching scratch_watch
WINDOW = 12           # how far back a run is assembled from

# 🐛 [2026-08-28] Retention is a CALENDAR window with a per-day cap, not a flat entry count.
# The `KEEP_ENTRIES = 400` this replaces was bounded, but it bounded the wrong axis: measured on
# the workspace this plugin is developed against, one busy day wrote past 400 in about two hours,
# so the log never held more than a single day. Two readers needed more than that and both were
# silently dead. `repeated()` requires the same sequence on REPEAT_AT DISTINCT days before it says
# anything -- with one day on disk it can never fire, which is exactly what that log showed (zero
# detections, ever). And `usage_counts()` answers "is anyone actually running these commands",
# a question about weeks; over a few hours the only honest answer it can give is "no data".
#
# The per-day cap is what keeps a calendar window bounded. It drops only from the HEAD of a day,
# so the tail `repeated()` reads (`run[-WINDOW:]`) is never touched, and it never drops chamnan's
# own commands: they are rare, they ARE the adoption signal, and evicting one to make room for the
# three-hundredth `grep` would discard the measurement in order to keep the noise.
KEEP_DAYS = 30        # calendar days retained
KEEP_PER_DAY = 300    # ordinary commands kept per day; chamnan's own are never dropped
TRIM_SLACK = 100      # amortise: rewrite once per ~100 surplus entries, not on every append

_WORD = re.compile(r"^[A-Za-z_][\w.-]*$")
# This plugin's own commands, which the per-day cap must never evict. Anchored, so a signature
# that merely CONTAINS the word (`add-chamnan`, seen in the live log) is correctly not matched.
_KEEP_ALWAYS = re.compile(r"^chamnan-")

_SEPARATORS = ("&&", "||", ";", "|")


def _split_unquoted(text):
    """Split `text` on `;`, `&&`, `||` and `|`, but never inside a quoted string.

    🐛 The regex this replaced (`\\s*(?:&&|\\|\\||;|\\|)\\s*`) split blindly on every occurrence
    of these characters, with no idea one might sit inside a quoted argument. A commit message
    like `git commit -m "Refactor; use fetch instead of urllib"` split into TWO parts on the `;`
    still inside the quotes, and the second part's first word ("use" -- plain English from the
    commit message, not a command) became a fabricated `signature()`, scored the same as a real
    shell step and counted toward `repeated()`'s "you keep running this sequence" detector.

    Not a full shell parser -- just enough to track single/double-quote state (with basic
    backslash-escape handling inside double quotes, matching POSIX) for the four separators this
    module actually splits on.
    """
    parts, buf, quote, i, n = [], [], None, 0, len(text)
    while i < n:
        ch = text[i]
        if quote:
            buf.append(ch)
            if ch == "\\" and quote == '"' and i + 1 < n:
                i += 1
                buf.append(text[i])
            elif ch == quote:
                quote = None
            i += 1
            continue
        if ch in "\"'":
            quote = ch
            buf.append(ch)
            i += 1
            continue
        if text[i:i + 2] in ("&&", "||"):
            parts.append("".join(buf))
            buf = []
            i += 2
            continue
        if ch in ";|":
            parts.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    parts.append("".join(buf))
    return parts


def signature(command):
    """A stable name for what a command DOES, or "" when it is not worth remembering.

    `pytest tests/payment -x` and `pytest tests/fleet` are the same step of the same workflow, and
    a fingerprint that disagreed would never match anything twice.
    """
    parts = command.strip().split()
    if not parts:
        return ""
    # Leading environment assignments: FOO=bar cmd ...
    while parts and "=" in parts[0] and not parts[0].startswith("-"):
        parts = parts[1:]
    if not parts:
        return ""
    prog = parts[0].rsplit("/", 1)[-1]
    if not _WORD.match(prog) or prog in NOISE or prog in KEYWORDS:
        # Known limitation, same shape as the flag one below: `; do pytest;` is one semicolon
        # fragment whose FIRST word is the keyword "do", so a real command right after it is never
        # reached -- the fragment drops instead of yielding "pytest". Recovering it would mean
        # knowing which keywords syntactically precede a COMMAND (`do`, `then`, `else`) versus an
        # EXPRESSION (`for`, `while`, `if` — where the next word is a variable or a condition, not
        # a program), and guessing wrong there suggests the wrong routine. The loop's real command
        # going undetected this one time is the smaller cost.
        return ""
    if prog in _SUBCOMMAND_TOOLS:
        # Known limitation: a global flag that takes a VALUE before the subcommand
        # (`docker --context prod compose up`) yields `docker prod`, because telling
        # `--context prod` apart from `--debug compose` needs each tool's flag grammar. Left
        # alone rather than guessed at — the consequence is that such a command does not match
        # its own sequence and the workflow simply is not detected. Failing quiet is the right
        # direction for a hint; a heuristic wrong the other way would suggest the wrong routine.
        for arg in parts[1:]:
            if _WORD.match(arg) and not arg.startswith("-"):
                return f"{prog} {arg}"
            if arg.startswith("-"):
                continue
            break
    return prog


def signatures(command_text):
    """Every meaningful signature in one shell invocation, in order, de-duplicated consecutively.

    A single Bash call is often a pipeline or a chain; each part is a step. Consecutive duplicates
    collapse because `git add && git commit` twice in a row is one step repeated, not two.
    """
    out = []
    for part in _split_unquoted(command_text):
        sig = signature(part)
        if sig and (not out or out[-1] != sig):
            out.append(sig)
    return out


# Lines `read()` could not use, from its last call. A list rather than a count so a caller can show
# one if it ever needs to; today only the length is used.
LAST_SKIPPED = []


def read(log_path):
    """Every entry currently on disk, in order, malformed lines skipped. Read-only, and public
    because the PostToolUse hook needs exactly this: the history as it stood BEFORE the command it
    is about to record. It used to get that by calling `record()` with an empty list -- which, back
    when `record()` rewrote the whole file unconditionally, cost two full rewrites of the log per
    Bash call. Reading is now a read."""
    # 🐛 Malformed lines are skipped, which is right — a torn last line is what a killed process
    # leaves behind — but the count was thrown away, and `chamnan-report` prints "these counts are
    # exact for that window" over the result. Exact is a strong word and this could not back it.
    # Recorded the way workspace.py records LAST_IGNORE_RULES_ADDED, so the caller can say so
    # without every caller having to change shape (R1 agent 4).
    del LAST_SKIPPED[:]
    if not log_path.is_file():
        return []
    out = []
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, RecursionError):
            LAST_SKIPPED.append(line[:80])
            continue
        # A line holding `[]` or `42` is valid JSON and every caller here calls .get on it. Skipped
        # like a malformed line, which is what it is for this log's purposes (R4 agent 1).
        if isinstance(entry, dict):
            out.append(entry)
        else:
            LAST_SKIPPED.append(line[:80])
    return out


# Paths appended to without the lock on Windows, for a test to assert the fallback is reachable and
# for anybody debugging a short log to find. Never read at runtime.
_unlocked_appends = []


def _append_entries(log_path, fresh):
    """The append itself, so the locked and unlocked paths cannot drift apart."""
    with log_path.open("a", encoding="utf-8") as handle:
        for entry in fresh:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def record(log_path, sigs, when, tool=None, interrupted=False):
    """Append signatures to the bounded log and return the full history.

    `tool` and `interrupted` are evidence about the ONE Bash call that produced every signature in
    `sigs` — they are the same call, so the same evidence applies to each. `interrupted` is written
    only when true: there is no exit code in a Bash tool_response (confirmed against another
    installed plugin's own comment on this exact fact — only stdout, stderr and interrupted exist),
    so recording `False` on every entry would be noise dressed as data, not evidence.

    Every new entry carries `kind: "command"` so a reader can tell it apart from any other record
    shape this log ever holds. An entry already on disk with no `kind` at all reads as `"command"`
    by the readers below — this is not a migration, nothing here rewrites what already exists.
    """
    fresh = []
    for sig in sigs:
        entry = {"at": when, "kind": "command", "sig": sig}
        if tool:
            entry["tool"] = tool
        if interrupted:
            entry["interrupted"] = True
        fresh.append(entry)

    log_path.parent.mkdir(parents=True, exist_ok=True)
    if fresh:
        # Append, do not rewrite. This runs from a PostToolUse hook on every single Bash call, and
        # a calendar window holds more than a flat 400 did, so rewriting the whole file every time
        # would make the log's own cost grow in step with its usefulness.
        #
        # 🐛 "The append path above is safe on its own -- O_APPEND writes of short lines do not
        # interleave" was true, and true only on POSIX. Windows documents no such guarantee and does
        # not provide one. Measured on a Windows Server 2025 runner, six processes appending 200
        # short lines each: 1,034 of 1,200 lines reached the disk. 166 gone, 13.8%, no error
        # anywhere. The same lab on ubuntu-latest in the same run: 1,200 of 1,200.
        #
        # So the append takes the lock too, on that platform only. POSIX keeps the lock-free path
        # because it is correct there and this runs on every Bash call; paying a lock per call to
        # fix a platform that does not have the problem would be the wrong trade.
        if os.name == "nt":
            with ws.exclusive(log_path) as held:
                # Appended either way, and deliberately. The trim below RETURNS when the lock was
                # not taken, because rewriting unguarded destroys other processes' records; an
                # append cannot destroy anything, it can only fail to survive a collision. Not
                # appending loses this record with certainty; appending unguarded loses it with the
                # probability the lab measured, 13.8% under six-way contention. The certain loss is
                # the worse one, so the flag is read and the decision is written down rather than
                # the block silently doing the same thing either way.
                if not held:
                    _unlocked_appends.append(str(log_path))
                _append_entries(log_path, fresh)
        else:
            _append_entries(log_path, fresh)

    history = read(log_path)
    kept = prune(history)
    # Only rewrite once enough surplus has accumulated to be worth the write. The log is therefore
    # allowed to sit up to TRIM_SLACK entries above target, which no reader cares about --
    # `repeated()` reads a tail and `usage_counts()` a total, and neither is harmed by extra
    # history.
    if len(history) - len(kept) >= TRIM_SLACK:
        # The trim is a truncate-and-overwrite built from a snapshot that another process can have
        # appended to since. The append path above is safe on its own -- O_APPEND writes of short
        # lines do not interleave -- but a rewrite racing appends throws them away wholesale.
        # Measured before this, 6 processes racing appends against rewrites: 131 of 240 freshly
        # appended signatures, 55%, vanished from the log. A workflow's evidence deleted by an
        # unrelated Bash call.
        #
        # Re-read INSIDE the lock rather than trusting the snapshot, so anything appended between
        # the read above and the lock is trimmed rather than lost.
        with ws.exclusive(log_path) as held:
            # 🐛 The rewrite sat OUTSIDE this guard. `ws.exclusive` yields False after a two-second
            # timeout, and on that path the log was truncated and rewritten from the stale snapshot
            # read before the lock was attempted — discarding every append another process had made
            # in the meantime. Reproduced with the lock held elsewhere: 50 concurrent appends, 0
            # survivors. That is verbatim the failure the comment above says was fixed by adding
            # the lock; under real contention the lock bought two seconds and then did the damage
            # anyway. Skipping the trim costs nothing — the log is trimmed on the next call, and a
            # log slightly over its bound is not a defect. Losing an append is.
            if not held:
                return
            history = read(log_path)
            kept = prune(history)
            _rewrite(log_path, kept)
        history = kept
    return history


def _rewrite(log_path, entries):
    """Replace the log with `entries`. Kept apart from `record()` so the append path above is the
    one that runs on every call and this one only on a trim.

    🐛 A plain `write_text` truncates the file and then fills it, so the log sits at ZERO BYTES for
    the length of the write — measured at about a second on a real log. A `chamnan-report` landing
    in that window read 450 real invocations as "(nothing logged yet)", which is not a slow answer
    but a wrong one, and the trim is a background tidy-up nobody asked for. `atomic_write_text`
    writes a temporary file and renames it, so a reader sees the old log or the new one and never
    an empty one — and it is the same helper that honours CHAMNAN_READ_ONLY (R1 agent 4).
    """
    ws.atomic_write_text(log_path,
                         "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n")


def prune(history, days=KEEP_DAYS, per_day=KEEP_PER_DAY):
    """`history` reduced to the last `days` calendar days, with at most `per_day` ordinary command
    signatures kept within each day.

    Two rules decide what survives a busy day, and both exist so that trimming the noise never
    costs a reader the thing it came for:

      * Entries are dropped from the HEAD of a day, never the tail. `repeated()` only ever looks at
        `run[-WINDOW:]`, so the sequence it detects is bit-for-bit what it would have seen had
        nothing been pruned at all.
      * chamnan's own commands are exempt, as is any record whose `kind` is not `"command"` -- a
        future record shape sharing this log is not this function's to ration. Both are rare by
        construction; the day window is what bounds them.
    """
    by_day = {}
    for entry in history:
        by_day.setdefault(str(entry.get("at") or "")[:10], []).append(entry)

    out = []
    for day in sorted(by_day)[-days:]:
        kept, ordinary = [], 0
        for entry in reversed(by_day[day]):
            exempt = (entry.get("kind", "command") != "command"
                      or _KEEP_ALWAYS.match(str(entry.get("sig") or "")))
            if exempt:
                kept.append(entry)
            elif ordinary < per_day:
                kept.append(entry)
                ordinary += 1
        kept.reverse()
        out.extend(kept)
    return out


def _runs(history):
    """Split the flat history into runs, one per calendar day.

    A workflow is a sequence performed in one sitting. Joining across days would stitch the end of
    Tuesday to the start of Wednesday and call it a routine.
    """
    runs, current, day = [], [], None
    for entry in history:
        # A record with no `kind` predates this field and is a command signature by construction
        # (nothing else was ever written to this log before now) -- so missing reads as "command",
        # not as "unknown, skip it". Anything explicitly tagged something ELSE is a future record
        # shape this function was not built to sequence and must not silently join a run.
        if entry.get("kind", "command") != "command":
            continue
        d = (entry.get("at") or "")[:10]
        if d != day:
            if current:
                runs.append(current)
            current, day = [], d
        current.append(entry.get("sig", ""))
    if current:
        runs.append(current)
    return runs


def repeated(history):
    """The longest sequence that has occurred REPEAT_AT times on distinct days, or None.

    Returns (sequence, count). Ordered and contiguous within a day — "these steps, in this order",
    which is what makes it a workflow rather than a set of tools somebody happens to use.
    """
    runs = _runs(history)
    if len(runs) < REPEAT_AT:
        return None

    seen = {}
    for i, run in enumerate(runs):
        window = run[-WINDOW:]
        # Every contiguous slice of at least MIN_LENGTH, recorded once per day so a sequence
        # repeated twice in one sitting does not count as two days' evidence.
        local = set()
        for start in range(len(window)):
            for end in range(start + MIN_LENGTH, len(window) + 1):
                slice_ = tuple(window[start:end])
                if len(set(slice_)) < MIN_LENGTH:
                    continue
                local.add(slice_)
        for slice_ in local:
            seen.setdefault(slice_, set()).add(i)

    qualifying = [(s, days) for s, days in seen.items() if len(days) >= REPEAT_AT]
    if not qualifying:
        return None
    # Longest wins: the fuller sequence is the more useful thing to write down, and a shorter one
    # contained inside it says less.
    best, days = max(qualifying, key=lambda kv: (len(kv[0]), len(kv[1])))
    return list(best), len(days)


def describe(sequence, count, candidate_path=None):
    """`candidate_path`, when given, is where this sequence's finding now lives on disk (see
    lib/candidates.py) -- named so the notice points at something that outlives the session,
    rather than only describing a moment that will otherwise be forgotten the instant it scrolls
    past. Optional so this stays callable exactly as before wherever a candidate is not in play."""
    steps = " → ".join(f"`{s}`" for s in sequence)
    where = f" Recorded as a candidate at `{candidate_path}`." if candidate_path else ""
    return (f"chamnan: this sequence has come round {count} times now — {steps}.{where} "
            f"If it is a routine worth keeping, run /chamnan:capture and write it down as a "
            f"procedure; the next session reads it instead of rediscovering the order.")


def usage_counts(log_path, names):
    """How many times each name in `names` occurs as a `sig` in the log, plus the oldest and
    newest `at` seen across every entry (not just the counted ones) — so a caller can say what
    span the count actually covers.

    The log is bounded by CALENDAR time (`KEEP_DAYS`), so the span is usually the window itself --
    but a repository younger than the window, or one worked on in bursts, still returns whatever it
    has. Reporting a count without the span it was measured over would let "14 calls" read as a
    rate it never claimed to be, so the span comes back with it either way.

    Counts for chamnan's own commands are exact: `prune()` exempts them from the per-day cap, so
    none is ever evicted to make room for ordinary shell noise.

    Returns (counts, oldest_at, newest_at). `counts` covers exactly `names`, zeros included, so a
    command that was never run reads as 0 rather than being silently missing from the dict —
    the same "print zero plainly" choice `lib/ledger.py` already makes for its own stores.
    """
    counts = {n: 0 for n in names}
    oldest = newest = None
    for entry in read(log_path):
        if entry.get("kind", "command") != "command":
            continue
        at = entry.get("at")
        if at:
            oldest = at if oldest is None else min(oldest, at)
            newest = at if newest is None else max(newest, at)
        sig = entry.get("sig", "")
        if sig in counts:
            counts[sig] += 1
    return counts, oldest, newest
