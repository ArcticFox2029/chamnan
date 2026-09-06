"""`.chamnan/tools/index.json` — the registry `chamnan-promote` writes and chamnan_session_start.py reads.

Extracted out of `bin/chamnan-promote` so a second writer (`chamnan-candidates promote`, which
installs a tool skeleton from a confirmed candidate rather than copying an existing script) reuses
the exact same read/append/format logic instead of a second, slightly different copy of it. Two
JSON-append implementations drifting apart is exactly the kind of bug this repo has been burned by
before with concurrent writers of a shared file — see `main_app_concurrent_file_writes.md` in the
repo this plugin is developed against, though that specific failure mode (two threads writing at
once) does not apply here, since every caller is a short-lived CLI invocation, never long-running.

The schema is deliberately small: `name`, `desc`, `added` (ISO timestamp), `origin` (where the
content came from — a file path for a promoted script, `"candidate:<slug>"` for one generated from
a detected sequence), `runs` (a usage counter `record_call()` increments on every matched Bash
call and `usage()` reads back for `chamnan-report`'s Usage section), `interrupted` and
`stderr_seen` (Stage 10's two honest signals, below).

**There is no exit code to track, and this module does not pretend otherwise.** Confirmed against
another installed plugin's own comment stating the exact fact twice over: a Bash `tool_response`
carries only `stdout`, `stderr` and `interrupted` — never a numeric status. `record_call()` counts
the two signals that ARE real: `interrupted` (the call was killed or timed out — an unambiguous
fact) and `stderr_seen` (the call wrote to stderr at all — a WEAK signal, since plenty of correct
commands write progress or warnings there too). Neither is reported as "the tool failed"; both are
reported as exactly what they are, and a human reading a flag decides what it means. This is the
same discipline Stage 8's promotion classifier already applies to itself: state the real signal and
its limits, never invent a confidence number to paper over not having one.
"""
import json
from datetime import datetime

import workspace as ws

# Three of the same signal in a row is worth a look; matches REPEAT_AT elsewhere in this plugin
# (workflows.py, chamnan_scratch_watch.py) rather than inventing a fourth threshold value to justify.
FLAG_AT = 3

# 🐛 [2026-09-04] `stderr_seen` no longer raises the flag, and this is the measurement that took it
# out. `runs` and `stderr_seen` were EQUAL for every tool in a real workspace:
#
#     session_block_size.py   runs=4  stderr_seen=4
#     extract_findings.py     runs=5  stderr_seen=5
#     silent_probe.py         runs=1  stderr_seen=1   <- its entire body is print("ok")
#
# A script whose only statement writes one line to stdout cannot produce stderr, and it was counted
# anyway. So in at least one shipped harness the `stderr` field of a Bash `tool_response` is never
# empty -- it appears to carry the host's own trailing notice, not the command's output -- and the
# counter is a constant, not a signal. Every promoted tool crossed the threshold on its third run
# and was reported as "worth a look" for behaving correctly.
#
# The docstring above called it "a WEAK signal". Weak would be survivable. A constant is worse: it
# fires on everything, which trains a reader to ignore the notice, which costs the `interrupted`
# signal beside it -- and that one IS real, because a killed or timed-out call is an unambiguous
# fact the harness genuinely reports.
#
# It is still COUNTED, and still printed by chamnan-report, because the number is evidence about
# the harness and someone should be able to see it. It just cannot raise an alarm on its own.


def path(root):
    from workspace import workspace
    return workspace(root) / "tools" / "index.json"


def load(root):
    """The index, or [] — never a shape a reader has to check for itself.

    🐛 This returned whatever the file happened to parse to, and five readers here index it as a
    list of dicts. `index.json` holding `{}` — a hand-edit, a bad merge, a half-written file — made
    `usage()` iterate the dict's KEYS and then subscript a string, so `chamnan-report` died with a
    TypeError instead of reporting. Three sibling readers of other stores already guard their shape
    and this one did not, which is this repository's recurring defect: the same rule applied to some
    members of a set (R1 agent 4).

    Entries that are not dicts are dropped rather than taking the file down with them: a list with
    one bad row is still nine good tools, and losing the file loses the run counters too.
    """
    try:
        loaded = json.loads(path(root).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, RecursionError):
        return []
    if not isinstance(loaded, list):
        return []
    return [e for e in loaded if isinstance(e, dict)]


def _save(root, entries):
    """🐛 A plain `write_text`, so a SIGKILL between truncate and flush left the registry a
    truncated file — which `load()` degrades to `[]`, the same value it returns for a file that
    never existed. Reproduced with a real SIGKILL mid-write: a healthy five-tool registry became
    empty, silently and permanently, and the next registration wrote a one-entry file over it.

    This module was MISSED when every other writer was routed through `ws.atomic_write_text`, and
    the commit that did that work said the class was closed. It was not; `tools_index.py` is not in
    `grep -rl atomic_write_text lib hooks bin`. Two rounds of the same disease — a fix applied to
    the members of a set somebody enumerated, and not to the one they forgot.

    It also makes `register`'s stated reasoning true. That function proceeds without the lock on the
    grounds that "the file is written atomically either way", which was simply false until now.
    """
    # RAISES on failure, unlike most callers of atomic_write_text. That helper is best-effort by
    # default because a workspace on a read-only checkout must still let a session start — but a
    # registration is a thing the user asked for, and `chamnan-promote` rolls back the copied file
    # when the index write fails. Swallowing it left the executable installed, announced, and
    # unregistered. Caught by the read-only-index test, which exists for exactly that.
    if not ws.atomic_write_text(path(root),
                                json.dumps(entries, indent=1, ensure_ascii=False) + "\n"):
        raise OSError(f"could not write {path(root)}")


def register(root, entry):
    """Append one entry and write the index back. `entry` must have `name`; every other field is
    optional and defaults sensibly. Returns the full, updated list."""
    # 🐛 `record_call` wraps its read-modify-write in `ws.exclusive`; `register` and `remove` did
    # the same read-modify-write with no lock at all. A lock only one of three writers holds
    # serialises nothing: reproduced by racing a promotion against `record_call`, the freshly
    # registered tool was written and then overwritten by the other writer's snapshot. The file
    # existed on disk and the registry had no record of it, so the session-start tool list,
    # `chamnan-report` and `match_call` would never see it again. `record_call` fires from a
    # PostToolUse hook on every Bash call, which is exactly the window a promotion runs in.
    # The lockfile lives beside the index, and `register` is usually what CREATES the index — so
    # without this the very first call cannot take a lock, `exclusive` yields False, and the
    # registration is skipped. Found by the suite the moment the lock went in.
    try:
        path(root).parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    with ws.exclusive(path(root)) as held:
        if not held:
            # Registering matters more than serialising it: a promotion the user asked for that
            # silently does nothing is worse than a rare lost update, and the file is written
            # atomically either way.
            return _register_locked(root, entry)
        return _register_locked(root, entry)


def _register_locked(root, entry):
    entries = load(root)
    entries.append({
        "name": entry["name"],
        "desc": entry.get("desc", ""),
        "added": entry.get("added", ""),
        "origin": entry.get("origin", ""),
        "runs": entry.get("runs", 0),
        "interrupted": entry.get("interrupted", 0),
        "stderr_seen": entry.get("stderr_seen", 0),
        "last_run": entry.get("last_run", ""),
    })
    _save(root, entries)
    return entries


def match_call(root, command):
    """The registered tool NAME a Bash command string invokes, or None. A plain substring check
    against `.chamnan/tools/<name>` for every registered entry -- honest about being exactly that:
    it will miss a tool invoked through an alias or a wrapper, and that is the right failure
    direction. A false negative costs one unflagged failure; a false positive would blame the wrong
    tool for something it never ran."""
    entries = load(root)
    if not entries or not command:
        return None
    for e in entries:
        needle = f".chamnan/tools/{e['name']}"
        if needle in command:
            return e["name"]
    return None


def record_call(root, name, interrupted=False, stderr_nonempty=False):
    """Increment `runs`, and `interrupted`/`stderr_seen` when the call showed that signal, for the
    entry named `name`. Returns (entry, just_flagged) -- `just_flagged` is True exactly once, on
    the call that FIRST reaches FLAG_AT on `interrupted` -- `stderr_seen` is counted but cannot
    raise the flag, for the reason measured at FLAG_AT above -- so a caller can print a notice on the
    crossing and stay silent on every repeat after it, the same restraint every other notice in
    this plugin already uses."""
    # The whole read-modify-write under one lock, not just the write. An atomic write alone does
    # not prevent a lost update -- both processes read the same `runs`, both add one, and one of
    # the two increments is gone. Measured before this, 8 processes x 50 calls against one index:
    # 187 of 400 recorded, 53% lost. Silent, and it stays wrong forever, because the number is a
    # running total and nothing recomputes it.
    #
    # This is a SHARED registry, so pointer.py's answer to the same problem -- one file per session,
    # no lock at all -- is not available: every session has to see the same list of tools.
    with ws.exclusive(path(root)) as held:
        # A background counter, so a dropped increment is the cheap outcome and a lost update is
        # not: this fires from a PostToolUse hook on every Bash call, and writing an unserialised
        # snapshot back would revert whatever a concurrent `register` or `remove` had just done.
        # Same choice `workflows.record()` makes, for the same reason. Measured under contention:
        # 10-12.5% of increments were being lost every trial, which is what proceeding cost.
        if not held:
            return None, False
        entries = load(root)
        entry = next((e for e in entries if e["name"] == name), None)
        if entry is None:
            return None, False
        entry["runs"] = entry.get("runs", 0) + 1
        # 🐛 Two developers each adding one call on their own branch both write `runs: 5 -> 6` --
        # the same line, the same text, no conflict marker -- and `git merge` takes either side
        # cleanly. Seven real calls land recorded as six, forever, because nothing recomputes a
        # running total. Unequal deltas (5->6 vs 5->8) already conflict on their own; only the
        # equal-delta case was silent. A microsecond timestamp on every call makes two
        # independently-recorded increments differ almost always even when `runs` lands on the
        # same number, which turns the silent case into the same human-visible merge conflict the
        # unequal-delta case already gets -- cheaper than a custom git merge driver, which would
        # need a `.gitattributes` entry AND a per-clone `git config` write outside this workspace.
        entry["last_run"] = datetime.now().astimezone().isoformat(timespec="microseconds")
        was_flaggable = entry.get("interrupted", 0) >= FLAG_AT
        if interrupted:
            entry["interrupted"] = entry.get("interrupted", 0) + 1
        if stderr_nonempty:
            entry["stderr_seen"] = entry.get("stderr_seen", 0) + 1
        now_flaggable = entry.get("interrupted", 0) >= FLAG_AT
        _save(root, entries)
    return entry, (now_flaggable and not was_flaggable)


def usage(root):
    """(name, runs) for every registered tool, in registration order — the read side of the `runs`
    counter `record_call()` writes on every matched Bash call. Stage 11's whole job here: this
    field has been counting since Stage 10 shipped and nothing has printed it until now."""
    return [(e["name"], e.get("runs", 0)) for e in load(root)]


def remove(root, name):
    """Delete one entry from the index (the tool FILE itself is a separate deletion the caller does
    — this module only ever owns index.json). Returns the removed entry, or None if there was no
    such name. Used by `chamnan-candidates demote` to undo a promotion."""
    # The third writer of this file. `record_call` fires from a PostToolUse hook on every Bash
    # call, so a demotion racing it lost either the removal or the run counter, silently.
    with ws.exclusive(path(root)) as held:
        # Refused, not attempted anyway, and this is the opposite call from `register`'s. Removing
        # is destructive and the failure is not symmetric: an unserialised remove writes back a
        # snapshot taken before a concurrent writer's change, so a tool the user had just DEMOTED
        # comes back. Reproduced in 2 of 5 trials under contention — a command that reports success
        # while undoing itself. Raised rather than returned as None, because None already means
        # "no such tool" and a caller that cannot tell the two apart prints the wrong sentence.
        if not held:
            raise TimeoutError(f"could not lock {path(root).name}; another process is writing it")
        entries = load(root)
        entry = next((e for e in entries if e["name"] == name), None)
        if entry is None:
            return None
        _save(root, [e for e in entries if e["name"] != name])
        return entry
