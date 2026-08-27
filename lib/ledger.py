"""The ledger — one line that turns an empty store into a printed zero instead of an absence.

Written after measuring the live workspace this plugin was built against: the hook-written logs
(`logs/scratch.jsonl`, `logs/commands.jsonl`) held 700 records while every skill-written store —
`sessions/`, all three `memory/` categories, `milestones.md` — held zero, after five weeks of daily
use. A store nobody can see is a store nobody feeds. This module counts what actually exists, every
session, so the absence is a fact on the screen rather than a fact nobody notices.

It must show MOVEMENT, not a static number. A count that never changes is what gets tuned out — not
the word "zero" — so `render()` always states how much arrived in the last week, once there is
anything to compare against. See `render()`'s two branches.

Every store is counted defensively: a directory that does not exist yet (because a later release
has not created it) reads as absent, not zero, and its clause is simply omitted from the line. That
is what lets `candidates/` (added in 1.5.1) join the ledger automatically the day it starts existing,
with no further change here.
"""
import re
import time

WEEK = 7 * 86400

# Matches the date convention sessions.py documents for its own filenames: "sorted by filename,
# which begins with the date". Used in preference to file mtime, because mtime resets to checkout
# time on a fresh clone or machine move and would otherwise report every existing session as
# written this week the moment the repository is cloned.
_SESSION_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def _files(root, *parts):
    """Every `.md` file directly under workspace/parts..., or None when that directory does not
    exist at all -- distinct from existing and holding nothing."""
    from workspace import workspace
    d = workspace(root)
    for p in parts:
        d = d / p
    if not d.is_dir():
        return None
    return sorted(p for p in d.glob("*.md") if p.is_file())


def _mtimes(paths):
    out = []
    for p in paths:
        try:
            out.append(p.stat().st_mtime)
        except OSError:
            continue
    return out


def _ymd_to_ts(y, m, d):
    import calendar
    try:
        return calendar.timegm((int(y), int(m), int(d), 12, 0, 0))
    except (ValueError, TypeError):
        return None


def _milestone_timestamps(root):
    """One timestamp per milestone entry, from the date in its own heading -- there is no per-entry
    file to stat, since every milestone lives inside one appended file."""
    from milestones import entries as milestone_entries
    out = []
    for date_str, _title, _body in milestone_entries(root):
        ts = _ymd_to_ts(*date_str.split("-")) if date_str.count("-") == 2 else None
        if ts is not None:
            out.append(ts)
    return out


def _session_timestamps(paths):
    """One timestamp per session record, read from the date at the start of its filename when it
    parses, falling back to the file's mtime otherwise -- a session record written by hand outside
    the `sessions.filename()` convention should still count, just less precisely."""
    out = []
    for p in paths:
        m = _SESSION_DATE.match(p.name)
        ts = _ymd_to_ts(*m.groups()) if m else None
        if ts is None:
            try:
                ts = p.stat().st_mtime
            except OSError:
                continue
        out.append(ts)
    return out


def snapshot(root, now=None):
    """Everything the ledger line needs, gathered once. `now` is injectable so tests do not depend
    on wall-clock time."""
    now = time.time() if now is None else now
    cutoff = now - WEEK

    sessions = _files(root, "sessions")
    decisions = _files(root, "memory", "decisions")
    lessons = _files(root, "memory", "lessons")
    rules = _files(root, "memory", "rules")
    candidates = _files(root, "candidates")  # None until 1.5.1 creates the directory

    memory_files = (decisions or []) + (lessons or []) + (rules or [])
    # Memory entries carry no date of their own until Stage 4 adds `as-of`, so mtime is the only
    # signal available today -- imprecise across a fresh clone, but not silently wrong the way
    # using it for sessions would be, since a decision's mtime at least reflects when THIS copy
    # last saw a write, not a date the file never claimed to have.
    memory_mtimes = _mtimes(memory_files)

    session_ts = _session_timestamps(sessions or [])
    milestone_ts = _milestone_timestamps(root)

    record_count = len(sessions or []) + len(milestone_ts)
    record_recent = (sum(1 for t in session_ts if t >= cutoff)
                      + sum(1 for t in milestone_ts if t >= cutoff))

    all_ts = session_ts + memory_mtimes + milestone_ts
    last_write = max(all_ts) if all_ts else None

    return {
        "now": now,
        "record_count": record_count,
        "record_recent": record_recent,
        "memory_count": len(memory_files),
        "last_write": last_write,
        # None = the store does not exist yet; 0 = it exists and is empty. render() treats these
        # differently on purpose -- see the module docstring.
        "candidate_count": None if candidates is None else len(candidates),
    }


def _age(seconds, now):
    days = int((now - seconds) // 86400)
    if days <= 0:
        return "today"
    if days == 1:
        return "1 day ago"
    return f"{days} days ago"


def render(snap):
    """The ledger line's body (no leading `_chamnan · ` prefix decision made here beyond the
    literal text) -- callers wrap it as they see fit."""
    rc, mc = snap["record_count"], snap["memory_count"]
    if rc == 0 and mc == 0 and snap["candidate_count"] in (None, 0):
        return "chamnan · 0 records · 0 memory entries · nothing written yet"

    parts = [
        f"{rc} record{'s' if rc != 1 else ''} (+{snap['record_recent']} this week)",
        f"{mc} memory {'entries' if mc != 1 else 'entry'}",
    ]
    if snap["last_write"] is not None:
        parts.append(f"last write {_age(snap['last_write'], snap['now'])}")
    if snap["candidate_count"] is not None:
        cc = snap["candidate_count"]
        parts.append(f"{cc} awaiting review" if cc else "0 awaiting review")
    return "chamnan · " + " · ".join(parts)


def line(root, now=None):
    """The full injected line, ready to print."""
    return "_" + render(snapshot(root, now)) + "_"
