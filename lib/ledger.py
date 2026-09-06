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

import workspace as ws

WEEK = 7 * 86400

# Matches the date convention sessions.py documents for its own filenames: "sorted by filename,
# which begins with the date". Used in preference to file mtime, because mtime resets to checkout
# time on a fresh clone or machine move and would otherwise report every existing session as
# written this week the moment the repository is cloned.
_SESSION_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
# The date `memory.py` writes at the foot of every entry. Same reason as above, and it was
# available for a whole release before this read it: the comment below used to say memory entries
# "carry no date of their own until Stage 4 adds `as-of`" — Stage 4 shipped, and nothing came back
# here, so a fresh clone reported every decision ever recorded as written today.
_AS_OF = re.compile(r"^\*\*As-of:\*\*\s*(\d{4})-(\d{2})-(\d{2})", re.M)


def _files(root, *parts):
    """Every `.md` file directly under workspace/parts..., or None when that directory does not
    exist at all -- distinct from existing and holding nothing."""
    from workspace import workspace
    d = workspace(root)
    for p in parts:
        d = d / p
    if not d.is_dir():
        return None
    return sorted(p for p in d.glob("*.md") if p.is_file() and not ws.is_store_index(p))


def _mtimes(paths):
    out = []
    for p in paths:
        try:
            out.append(p.stat().st_mtime)
        except OSError:
            continue
    return out


def _ymd_to_ts(y, m, d):
    """The timestamp for a date, or None when the date is not one.

    🐛 `calendar.timegm` does not validate the day: it rolled 2026-02-30 forward to 2026-03-02 and
    returned a timestamp for a date nobody wrote. The same gap is documented in `sessions.prune`
    and listed as open for `environments.py`; this was the third copy. `datetime` refuses it, which
    is what the caller's "undated" branch already exists to handle.

    A date in the FUTURE is refused for a different reason and it is the one that mattered: a typo'd
    `2099-01-01` made `_age()` report "today" (it floors a negative difference to 0) and satisfied
    `record_recent`'s `t >= cutoff`, so the ledger line claimed a record written this week when the
    newest real one was six months old. That line is injected into every session, and this module's
    own docstring says it exists because "a count that never changes gets tuned out" — it was
    manufacturing movement instead. A slack of one day is allowed, so a record written in a
    timezone ahead of this machine is not thrown away.
    """
    import datetime
    try:
        when = datetime.datetime(int(y), int(m), int(d), 12, 0, 0, tzinfo=datetime.timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None
    ts = when.timestamp()
    return None if ts > time.time() + 86400 else ts


def _milestone_timestamps(root):
    """One timestamp per milestone entry, from the date in its own heading -- there is no per-entry
    file to stat, since every milestone lives inside one appended file."""
    from milestones import entries as milestone_entries
    # A milestone with a calendar-invalid date -- 2026-13-40, a typed month -- still EXISTS: the
    # entry parser requires the shape, not the calendar, so milestones.entries() returns it and
    # this list used to silently drop it. The ledger then printed "2 records" for three real
    # entries on disk, and a fat-fingered date could also make "last write N days ago" stale by
    # excluding the most recent activity there is. Undercounting the store is the exact opposite of
    # what a ledger is for.
    out, undated = [], 0
    for date_str, _title, _body in milestone_entries(root):
        ts = _ymd_to_ts(*date_str.split("-")) if date_str.count("-") == 2 else None
        if ts is not None:
            out.append(ts)
        else:
            undated += 1
    _milestone_timestamps.undated = undated
    return out


def _dated(paths):
    """One timestamp per memory entry, read from its own `**As-of:**` line when present and from
    mtime otherwise. A hand-written entry with no As-of still counts, just less precisely."""
    out = []
    for p in paths:
        ts = None
        try:
            m = _AS_OF.search(p.read_text(encoding="utf-8", errors="replace"))
            if m:
                ts = _ymd_to_ts(*m.groups())
            if ts is None:
                ts = p.stat().st_mtime
        except OSError:
            continue
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
    thread_files = _files(root, "threads")   # None until 1.6.0 creates the directory

    memory_files = (decisions or []) + (lessons or []) + (rules or [])
    memory_mtimes = _dated(memory_files)

    session_ts = _session_timestamps(sessions or [])
    milestone_ts = _milestone_timestamps(root)

    # Counted from what is on disk, not from what could be dated. A milestone whose date does not
    # parse is still a milestone.
    record_count = (len(sessions or []) + len(milestone_ts)
                    + getattr(_milestone_timestamps, "undated", 0))
    record_recent = (sum(1 for t in session_ts if t >= cutoff)
                      + sum(1 for t in milestone_ts if t >= cutoff))

    thread_mtimes = _mtimes(thread_files or [])
    all_ts = session_ts + memory_mtimes + milestone_ts + thread_mtimes
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
        # Counted separately from `record_count` and not folded into it: a thread is not a record
        # of a session, and adding it to that number would silently change what the number has
        # meant since 1.5.0. Same None-vs-0 rule as candidates above.
        "thread_count": None if thread_files is None else len(thread_files),
    }


def _age(seconds, now):
    days = int((now - seconds) // 86400)
    if days <= 0:
        return "today"
    if days == 1:
        return "1 day ago"
    return f"{days} days ago"


def humanize_age(ts, now=None):
    """Public wrapper for `_age()`, for callers outside this module (`chamnan-report`'s inventory)
    that want the same wording without reaching into a private function. "never" for `None`, which
    `inventory()` returns for a store with nothing written yet."""
    if ts is None:
        return "never"
    return _age(ts, time.time() if now is None else now)


def render(snap):
    """The ledger line's body (no leading `_chamnan · ` prefix decision made here beyond the
    literal text) -- callers wrap it as they see fit."""
    rc, mc = snap["record_count"], snap["memory_count"]
    # Every store has to be in this condition, or the line claims "nothing written yet" over a
    # store that holds something -- which is worse than a missing clause, because it is a
    # statement of fact that is false. Adding a store means adding it here.
    if (rc == 0 and mc == 0 and snap["candidate_count"] in (None, 0)
            and snap.get("thread_count") in (None, 0)):
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
    # Only when there ARE threads: an empty threads/ directory says nothing worth the characters,
    # unlike candidates, where "0 awaiting review" is itself the useful answer to "is there a
    # queue building up".
    tc = snap.get("thread_count")
    if tc:
        parts.append(f"{tc} thread{'s' if tc != 1 else ''}")
    return "chamnan · " + " · ".join(parts)


def line(root, now=None):
    """The full injected line, ready to print."""
    return "_" + render(snapshot(root, now)) + "_"


def inventory(root, now=None):
    """(label, count, last_write_ts_or_None) for every store, in display order -- for
    `chamnan-report`'s knowledge inventory, which is read on demand rather than injected.

    Unlike the ledger LINE, which omits a store's clause entirely when it does not exist yet (to
    keep the always-on injection honest about what nothing costs), the full inventory always shows
    every store, `0` and all. A deliberate, on-demand report has room to say "0" plainly; the
    budget-constrained line does not.
    """
    now = time.time() if now is None else now
    from milestones import entries as milestone_entries

    sessions = _files(root, "sessions") or []
    decisions = _files(root, "memory", "decisions") or []
    lessons = _files(root, "memory", "lessons") or []
    rules = _files(root, "memory", "rules") or []
    cand = _files(root, "candidates") or []
    thr = _files(root, "threads") or []
    ms = milestone_entries(root)

    def last(ts):
        return max(ts) if ts else None

    return [
        ("sessions/", len(sessions), last(_session_timestamps(sessions))),
        ("memory/decisions/", len(decisions), last(_dated(decisions))),
        ("memory/lessons/", len(lessons), last(_dated(lessons))),
        ("memory/rules/", len(rules), last(_dated(rules))),
        ("milestones.md", len(ms), last(_milestone_timestamps(root))),
        ("candidates/", len(cand), last(_mtimes(cand))),
        ("threads/", len(thr), last(_mtimes(thr))),
    ]


_BACKTICK = re.compile(r"`([^`]+)`")


# Real files that carry no extension. Deliberately a short closed list rather than "anything
# capitalised": the point of the extension test is to reject `MAX_STATE_CHARS` and `_write_index`,
# and a loose rule would let those back in.
_EXTENSIONLESS_FILES = frozenset({
    "Makefile", "makefile", "GNUmakefile", "Dockerfile", "Containerfile", "Jenkinsfile",
    "Rakefile", "Gemfile", "Procfile", "Vagrantfile", "Brewfile", "Justfile", "justfile",
    "LICENSE", "LICENCE", "NOTICE", "CODEOWNERS", "AUTHORS", "CHANGELOG", "README",
})


_LOCATOR = re.compile(r":\d+(?:-\d+)?$")


def _strip_locator(token):
    """`src/fit.py:142` names a file; `.exists()` says it does not. chamnan's own guidance asks for
    exactly this citation format, so every entry that followed it counted against the repository it
    was written about -- the check was measuring compliance with its own convention as a failure."""
    return _LOCATOR.sub("", token)


def _looks_like_a_path(token):
    """A backtick-quoted span worth checking against the filesystem: has a `/`, or ends in a short
    dot-extension. Filters out the far more common case of a backtick around a function or constant
    name (`_write_index`, `MAX_STATE_CHARS`) with neither. A glob or a span with a space is excluded
    entirely rather than guessed at -- `src/*.py` cannot be resolved with `.exists()`, and a wrong
    guess here would misreport an entry that is actually fine."""
    if "*" in token or " " in token:
        return False
    # Extensionless filenames are real files and this said they were not, so an entry naming only
    # `Makefile` and `Dockerfile` -- both present at the root of the repository it was judging --
    # was reported as "naming no real file". A false claim about whether stored knowledge is about
    # this codebase, which is the one thing this function is for.
    return ("/" in token or bool(re.search(r"\.\w{1,4}$", token))
            or token in _EXTENSIONLESS_FILES)


def entries_naming_no_file(root, category="lessons"):
    """(naming_none, total) for a memory category: how many entries contain not one backtick-quoted
    span that resolves to a real path in this repository.

    A heuristic, not a fact — a renamed or deleted file, or a glob, both read as "names no file"
    even when the entry is still exactly right. It exists to answer one question: how much of what
    is written here is actually ABOUT this codebase's files, versus knowledge that would still be
    true if this repository did not exist. That is the same question a personal, cross-repository
    memory scope would need answered before it is worth building — see PLAN.md §12.
    """
    from workspace import find_root
    from memory import entries as memory_entries
    repo_root = find_root(root)
    total = naming_none = 0
    for path in memory_entries(root, category):
        total += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            naming_none += 1
            continue
        # Stripped BEFORE the shape test, not after: `Makefile:12` has no slash and no longer ends
        # in a dot-extension, so testing the raw token throws away the extensionless case entirely.
        spans = [_strip_locator(t) for t in _BACKTICK.findall(text)]
        candidates = [t for t in spans if _looks_like_a_path(t)]
        if not candidates or not any((repo_root / c).exists() for c in candidates):
            naming_none += 1
    return naming_none, total


_REJECTED = re.compile(r"^\*\*Rejected:\*\*", re.M)


def decisions_without_rejected(root):
    """(without, total) — how many decisions have no `**Rejected:**` trade-off slot filled in.

    Never used to auto-fill one: whether there WAS a real alternative worth naming is a judgement
    the writer makes, not something this function can honestly guess. It only counts, so
    `chamnan-report` can say what is missing and leave the decision about each one to a person.
    """
    from memory import entries as memory_entries
    total = without = 0
    for path in memory_entries(root, "decisions"):
        total += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            without += 1
            continue
        if not _REJECTED.search(text):
            without += 1
    return without, total
