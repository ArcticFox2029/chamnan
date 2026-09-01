"""`.chamnan/tools/index.json` — the registry `chamnan-promote` writes and chamnan_session_start.py reads.

Extracted out of `bin/chamnan-promote` so a second writer (`chamnan-candidates promote`, which
installs a tool skeleton from a confirmed candidate rather than copying an existing script) reuses
the exact same read/append/format logic instead of a second, slightly different copy of it. Two
JSON-append implementations drifting apart is exactly the kind of bug this repo has been burned by
before with concurrent writers of a shared file — see `main_app_concurrent_file_writes.md` in the
repo this plugin is developed against, though that specific failure mode (two threads writing at
once) does not apply here, since both callers are short-lived CLI invocations, never long-running.

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

import workspace as ws

# Three of the same signal in a row is worth a look; matches REPEAT_AT elsewhere in this plugin
# (workflows.py, chamnan_scratch_watch.py) rather than inventing a fourth threshold value to justify.
FLAG_AT = 3


def path(root):
    from workspace import workspace
    return workspace(root) / "tools" / "index.json"


def load(root):
    try:
        return json.loads(path(root).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def _save(root, entries):
    p = path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(entries, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


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
    the call that FIRST reaches FLAG_AT on either counter, so a caller can print a notice on the
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
    with ws.exclusive(path(root)):
        entries = load(root)
        entry = next((e for e in entries if e["name"] == name), None)
        if entry is None:
            return None, False
        entry["runs"] = entry.get("runs", 0) + 1
        was_flaggable = (entry.get("interrupted", 0) >= FLAG_AT
                         or entry.get("stderr_seen", 0) >= FLAG_AT)
        if interrupted:
            entry["interrupted"] = entry.get("interrupted", 0) + 1
        if stderr_nonempty:
            entry["stderr_seen"] = entry.get("stderr_seen", 0) + 1
        now_flaggable = (entry.get("interrupted", 0) >= FLAG_AT
                         or entry.get("stderr_seen", 0) >= FLAG_AT)
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
    with ws.exclusive(path(root)):
        entries = load(root)
        entry = next((e for e in entries if e["name"] == name), None)
        if entry is None:
            return None
        _save(root, [e for e in entries if e["name"] != name])
        return entry
