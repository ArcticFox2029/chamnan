"""Candidates — evidence that survives, one file per repeated sequence, never itself knowledge.

`evidence -> candidate -> human confirm -> memory`. This module owns the middle step.

`lib/workflows.py` already detects a command sequence recurring across days and, until now, said
so once and threw the finding away — a session reads the notice, and the next session has to
rediscover the sequence from nothing if nobody happened to run `/chamnan:capture` right then. A
candidate is that finding kept: it survives the session that noticed it, so the decision to promote
it does not have to happen at the exact moment it crossed the threshold.

A candidate is NOT memory. It is never injected into a session's context — only its COUNT reaches
the ledger (see lib/ledger.py, whose `_files(root, "candidates")` already treats a missing
directory as absent rather than zero, which is what lets this store join the ledger line the day it
starts existing, with no change to that module). Promotion into something a session actually reads
-- `/chamnan:capture` into skills/, or a future `/chamnan:remember` into memory/ -- is a human
decision this module does not make.

**Evidence and status are different fields.** `Observed:` is what the workflow log actually
contained; `Status:` is the review decision later awarded to that evidence. `Provenance:` remains
for compatibility and says who or what wrote the candidate. Older files whose provenance already
says `ai-confirmed` or `user` still read as confirmed, so the schema change does not strand them.

**Keyed on the sequence, not on when it was seen.** The filename is derived from the signature
sequence itself, so the SAME sequence detected again -- tomorrow, or on the next Bash call while it
still qualifies -- updates the one file rather than creating another. `observed` is not incremented
by this module; the caller passes the count `workflows.repeated()` already computed (the number of
distinct days), so a write here is idempotent when nothing changed and correct when it did.
"""
import re
import mdblock
import workspace as ws  # noqa: E402

DIRNAME = "candidates"

PROVENANCE = ("user", "ai-drafted", "ai-confirmed", "ai-inferred", "imported", "deprecated")
STATUS = ("observed", "confirmed", "deprecated")

_FIELD = re.compile(r"^\*\*([A-Za-z ]+):\*\*\s*(.*)$", re.M)


def directory(root):
    from workspace import workspace
    return workspace(root) / DIRNAME


# 🐛 [2026-09-07] KNOWN, NOT FIXED. `slug()` truncates at 60 characters with no collision guard,
# so two genuinely different sequences sharing a 60-character prefix resolve to one file and the
# second overwrites the first. Reproduced:
#
#     python3 sed python3 git-add git-commit python3 pytest ruff mypy black
#     python3 sed python3 git-add git-commit python3 pytest ruff mypy isort
#     -> python3-sed-python3-git-add-git-commit-python3-pytest-ruff-m   (both)
#
# Ten-command sequences are exactly what this detector is for, so the prefix collision is not
# exotic. `timeline._distinct_slug` solves the same problem for threads by appending a short hash.
#
# The obvious port of it FAILS here and the reason is worth writing down, because the next attempt
# will otherwise make it again: `_upsert_locked` calls `path_for` BEFORE `_same_habit` has decided
# whether this sequence is a rotation of one already on disk. A per-sequence hash at that point
# gives four rotations of one habit four different filenames and defeats the merge that exists to
# stop exactly that — "ONE HABIT DETECTED AT FOUR OFFSETS IS ONE CANDIDATE" fails immediately.
#
# The fix belongs after the merge decision, not in the name: when `_same_habit` finds nothing and a
# genuinely new file is about to be written, THAT is where a taken name should be disambiguated.
# Left undone rather than shipped half-right, because breaking a deliberate, tested merge to close
# a narrower collision is the wrong trade (R13 agent 3).
def slug(sequence):
    """A readable filename stem for a sequence, distinct for sequences that differ past the cut.

    \U0001f41b [2026-09-10] Truncated at 60 characters with no collision check, so two genuinely
    different ten-step sequences sharing a 60-character prefix resolved to ONE file and the second
    `upsert` overwrote the first — no merge, no warning, and nothing of the first surviving
    anywhere. Ten-command sequences are exactly what this detector is for, so the collision is not
    a corner. Reproduced: two sequences differing only in their last step (`black` against `isort`)
    left one entry on disk (R13 agent 3 recorded it as KNOWN NOT FIXED; R10 agent 3 finding 2
    reproduced it and it was still open).

    The suffix is DETERMINISTIC on the sequence rather than resolved against the directory, and
    that is the difference from `mdblock.distinct_stem`, which the memory and session stores use.
    Those create by TITLE and can ask the directory what a name already holds. Here the sequence IS
    the key — `path_for` is a lookup, and `upsert` finds the existing entry by name — so the same
    sequence has to produce the same name every time, from the sequence alone.
    """
    joined = "-".join(sequence)
    s = mdblock.ascii_stem(joined)
    stem = mdblock.filename_safe(s[:60].rstrip("-")
                                 or mdblock.fallback_name(joined, "candidate"))
    if len(s) > 60:
        import hashlib
        # Only when it was actually cut. A sequence that fits keeps the readable name it has always
        # had, so nothing already on disk is renamed by this and a person can still guess a file.
        stem = f"{stem}-{hashlib.sha1(joined.encode('utf-8')).hexdigest()[:6]}"
    return stem


def filename(sequence):
    return f"{slug(sequence)}.md"


def _legacy_filename(sequence):
    """The name this sequence had BEFORE the collision suffix existed.

    A workspace written by an older chamnan holds files under the plain truncated name. Renaming
    them would make every one of them unreachable at once and the detector would re-create
    duplicates beside them, so `path_for` keeps using the old name where it finds one.
    """
    joined = "-".join(sequence)
    s = mdblock.ascii_stem(joined)
    return mdblock.filename_safe(s[:60].rstrip("-")
                                 or mdblock.fallback_name(joined, "candidate")) + ".md"


def path_for(root, sequence):
    """Where this sequence's file is, preferring one an older chamnan already wrote.

    The legacy name is used only when a file is actually there AND records this same sequence — a
    file at that name holding a DIFFERENT sequence is the collision itself, and the suffixed name
    is what keeps the two apart.
    """
    d = directory(root)
    legacy = d / _legacy_filename(sequence)
    if legacy.is_file() and _records_this_sequence(legacy, sequence):
        return legacy
    return d / filename(sequence)


def _records_this_sequence(path, sequence):
    """True when the file at `path` is about this exact sequence."""
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return False
    want = " ".join(sequence).strip().lower()
    for line in text.splitlines():
        low = line.strip().lower()
        if low.startswith("**steps:**") or low.startswith("steps:"):
            return want in low.replace("`", "").replace(",", " ").replace("  ", " ")
    return False


def _fields(text):
    """Trailer fields as a lowercase-keyed dict, e.g. {"observed": "3", "provenance": "ai-inferred"}."""
    return {m.group(1).strip().lower(): m.group(2).strip() for m in _FIELD.finditer(text)}


def status_of(fields):
    """The explicit status, or the status an older provenance-only candidate already implied."""
    status = fields.get("status") if isinstance(fields, dict) else None
    if status in STATUS:
        return status
    provenance = fields.get("provenance") if isinstance(fields, dict) else None
    if provenance == "deprecated":
        return "deprecated"
    return "confirmed" if provenance in ("ai-confirmed", "user") else "observed"


def render(sequence, observed, last_seen, provenance, status=None):
    """The candidate file's full text. Raises ValueError on an unknown provenance -- rejected at
    the point of writing, never stored, per the closed enum this whole module exists to enforce."""
    if provenance not in PROVENANCE:
        raise ValueError(f"unknown provenance: {provenance!r}")
    status = status or status_of({"provenance": provenance})
    if status not in STATUS:
        raise ValueError(f"unknown status: {status!r}")
    # 🐛 `title` was folded and `steps` was not — the same data, one line apart. A step carrying a
    # newline and a `## chamnan` heading, or an ANSI escape, therefore landed raw in a file that
    # gets COMMITTED, and the heading opened a section every later reader treats as real. Reachable
    # end to end from `chamnan-promote --desc` through `tools/index.json` to
    # `chamnan-candidates demote` (R2 agent 2). Folded per step rather than after joining, so a
    # newline inside one step cannot survive by hiding next to the separator.
    title = " · ".join(mdblock.one_line(s) for s in sequence)
    steps = ", ".join(mdblock.one_line(s) for s in sequence)
    return (f"# {mdblock.one_line(title)}\n\n"
            f"**Sequence:** {steps}\n"
            f"**Observed:** {observed}\n"
            f"**Last seen:** {last_seen}\n"
            f"**Status:** {status}\n"
            f"**Provenance:** {provenance}\n")


def _write(strict):
    """The writer `upsert` should use for the caller it has.

    🐛 [2026-09-07] `upsert` has exactly two callers and they sit on opposite sides of the line
    `workspace.write_or_raise` documents. `chamnan_scratch_watch.py` is a background hook, where a
    workspace that cannot be written must not stop a session and silence is the policy. `chamnan-
    candidates demote` is a command somebody typed by name — and it prints the path of the review
    record it just wrote. With the candidates directory read-only it printed "back for review at
    .chamnan/candidates/a-tool.md", exit 0, with no such file: by that point in the same command
    the tool had already been moved to `tools/archived/` and its index entry already removed, both
    successfully. So the net effect was the permanent, silent loss of the only record of why the
    tool existed, under a message naming the file that holds it (R7 agent 1, finding 2).
    """
    return ws.write_or_raise if strict else ws.atomic_write_text


def upsert(root, sequence, observed, when, provenance="ai-inferred", strict=False):
    """Create or update the one candidate for `sequence`. `observed` and `when` (a date string) are
    written as given -- not accumulated here -- so calling this repeatedly with the same values is
    a no-op on disk, and calling it with a fresher count or date correctly updates in place.

    Returns (path, is_new). Raises ValueError on an unknown provenance, before anything is written.
    """
    if provenance not in PROVENANCE:
        raise ValueError(f"unknown provenance: {provenance!r}")
    # 🐛 [2026-09-07] The merge below is a read-modify-write across the WHOLE DIRECTORY, not one
    # file: `_same_habit` scans every candidate, then this unlinks one and writes another. Two
    # PostToolUse hooks firing together each scanned, each found nothing to merge with, and each
    # wrote its own file — reproducing, under concurrency, the exact "five files for one habit"
    # the comment below says this merge exists to prevent (R7 agent 5).
    #
    # The lock is on the directory because the invariant is: one habit, one file. A per-file lock
    # cannot express that — the two writers are racing over which file should EXIST, and they hold
    # different ones.
    with ws.exclusive(directory(root)) as held:
        if not held and strict:
            raise TimeoutError(f"could not lock {directory(root)} — another process is writing a "
                               f"candidate. Nothing was changed; try again in a moment.")
        return _upsert_locked(root, sequence, observed, when, provenance, strict)


def _upsert_locked(root, sequence, observed, when, provenance, strict):
    """`upsert`'s body, with the candidates directory already locked. Split out so the lock is
    visible in the caller rather than buried, and so the early returns stay early returns."""
    p = path_for(root, sequence)
    prior_status = status_of(fields_of(p)) if p.is_file() else None
    if not p.is_file():
        # 🐛 [2026-09-07] One workflow produced FIVE candidate files in this repository's own queue:
        # `python3, git add, git commit`, the same three rotated two ways, and two more with an
        # extra `python3` on the end. `repeated()` sees a sliding window over a command log, so one
        # habit performed at slightly different offsets is detected as several sequences, and each
        # one got a file. A reviewer then pays five decisions for one habit — and the queue's own
        # count says five things are waiting when one is (R12 agent 5 predicted this; the queue
        # then produced it).
        #
        # Merged only when the new sequence is a ROTATION of an existing one or a contiguous run
        # inside it. Both mean the same commands in the same cyclic order, which is what a habit
        # detected at a different offset looks like; two genuinely different sequences that happen
        # to share commands are not related by either test.
        existing = _same_habit(root, sequence)
        if existing is not None:
            kept, seen = existing
            kept_status = status_of(fields_of(kept))
            # The LONGER sequence is the better description of the habit, and the count is the
            # larger of the two rather than their sum -- they are the same events counted twice.
            merged = sequence if len(sequence) > len(seen) else seen
            target = path_for(root, merged)
            if kept != target:
                try:
                    kept.unlink()
                except OSError:
                    pass
            prior = read(root, merged if merged is seen else seen)
            try:
                was = int(str((prior or ("0",))[0]).strip())
            except (TypeError, ValueError):
                was = 0
            target.parent.mkdir(parents=True, exist_ok=True)
            _write(strict)(target, render(merged, max(observed, was), when, provenance,
                                          status=kept_status))
            return target, False
    is_new = not p.is_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    _write(strict)(p, render(sequence, observed, when, provenance, status=prior_status))
    # 🐛 [2026-09-10] The merge above runs only on the branch that CREATES a file, so a duplicate
    # sitting beside an existing target was never reconciled — every later upsert rewrote the target
    # and stepped over the other one. Reproduced in this repository's own queue: two files, identical
    # sequences, both observed 3 times, in a queue of eight where six rows describe one routine.
    #
    # Only an EXACT duplicate is collapsed here. A rotation or a contained run is the same habit
    # seen at a different offset and is still merged on the create branch, where the longer sequence
    # wins; doing that reconciliation on every upsert would rewrite files on every hook firing for
    # no new information. Same commands in the same order at a second path is unambiguous.
    for _other in entries(root):
        try:
            if _other.resolve() == p.resolve():
                continue
            _got = _fields(_other.read_text(encoding="utf-8-sig", errors="replace"))
        except OSError:
            continue
        _seq = tuple(x.strip() for x in (_got.get("sequence") or "").split(",") if x.strip())
        if _seq and _seq == tuple(sequence):
            try:
                _other.unlink()
            except OSError:
                pass
    return p, is_new


def _rotations(seq):
    """Every cyclic rotation of `seq`, as tuples."""
    t = tuple(seq)
    return {t[i:] + t[:i] for i in range(len(t))}


def _same_habit(root, sequence):
    """(path, its sequence) of an existing candidate describing the same habit, or None.

    The same habit at a different offset in the command log, which is what a sliding window
    produces: a rotation of the same commands, or one sequence sitting contiguously inside the
    other. Anything else is a different candidate and is left alone.
    """
    want = tuple(sequence)
    # 🐛 [2026-09-10] This skipped `got == want` on the reasoning that `path_for` already finds the
    # file recording this exact sequence — true of ONE file, and there can be two. The naming
    # scheme gained a collision suffix, `path_for` prefers the legacy plain name when it holds the
    # same sequence, and the suffixed file written before that preference existed is then reachable
    # by nothing: not by `path_for`, and not by this merge, because the one condition that would
    # have caught it was the one being skipped.
    #
    # Found in this repository's own queue: two files, byte-identical sequences, both observed 3
    # times, sitting side by side in a queue of eight where six rows describe one routine. An exact
    # duplicate is the easiest case to merge and was the only case excluded.
    #
    # Skipped by PATH now, which is what the original reasoning actually meant.
    mine = path_for(root, sequence)
    for other in entries(root):
        try:
            if other.resolve() == mine.resolve():
                continue
        except OSError:
            continue
        try:
            fields = _fields(other.read_text(encoding="utf-8-sig", errors="replace"))
        except OSError:
            continue
        got = tuple(x.strip() for x in (fields.get("sequence") or "").split(",") if x.strip())
        if not got:
            continue
        if got == want:
            return other, list(got)
        if want in _rotations(got) or got in _rotations(want):
            return other, list(got)
        longer, shorter = (got, want) if len(got) > len(want) else (want, got)
        if any(longer[i:i + len(shorter)] == shorter
               for i in range(len(longer) - len(shorter) + 1)):
            return other, list(got)
        # 🐛 [2026-09-15] The three tests above — equal, a rotation, one sitting contiguously
        # inside the other — miss the case a real command log actually produces: the same commands
        # in the same habit at a different MULTIPLICITY. Measured on this repository's own queue:
        # **eight candidate files carrying twenty-five observations between them, over three
        # distinct sets of verbs.** `python3, python3, git add, git commit` and
        # `python3, -s, python3, python3, -s, git add, git commit` are one routine written twice,
        # and neither is a rotation or a substring of the other, so each waited alone and none
        # ever reached the count that would make it worth capturing. The detector was splitting the
        # evidence for a habit across files and then finding no habit.
        #
        # The SET is the habit. `_rotations` and the containment test stay, because they carry the
        # stronger claim (same order, same offsets) and they are what the merge message reads
        # from; this is the weaker claim underneath, and it only ever merges things that use the
        # same commands. A different routine that happens to use the same verbs merges with it,
        # which is the intended trade: this store is a hint queue, and two hints about `python3`
        # and `git commit` are one hint.
        if set(got) == set(want):
            return other, list(got)
    return None


def read(root, sequence):
    """(observed, last_seen, provenance) for an existing candidate, or None if it does not exist
    or does not parse. Never raises on a malformed file -- a candidate is a hint store, not a
    contract the rest of the plugin can depend on being well-formed."""
    p = path_for(root, sequence)
    if not p.is_file():
        return None
    try:
        fields = _fields(p.read_text(encoding="utf-8-sig", errors="replace"))
    except OSError:
        return None
    if "observed" not in fields:
        return None
    return fields.get("observed"), fields.get("last seen"), fields.get("provenance")


def entries(root):
    """Every candidate file, sorted for a stable order in diffs and injections."""
    d = directory(root)
    if not d.is_dir():
        return []
    # Same refusal as threads/ and memory/: a symlink out of the repository is the repository's
    # choice, arriving with a clone, and its content is not this store's to read.
    return sorted(p for p in d.glob("*.md")
                  if p.is_file() and not ws.is_store_index(p) and ws.inside(p, root))


def fields_of(path):
    """Trailer fields for a specific candidate FILE, when the caller already has the path rather
    than the sequence `read()` needs. `{}` for a missing or unreadable file -- a review tool
    listing candidates should show what it can, not crash on one bad file."""
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return {}
    return _fields(text)


def resolve(root, ident):
    """A candidate's path from either its 1-based position in `entries()` (the same order `list`
    prints, computed fresh -- not cached from an earlier call) or its slug/filename, with or
    without `.md`. Supports whichever is faster to type: `confirm 2` and
    `confirm git-add-git-commit-git-push` both work. Returns None rather than raising when nothing
    matches, so a caller can print its own message instead of a traceback."""
    found = entries(root)
    if ident.isdigit():
        i = int(ident) - 1
        return found[i] if 0 <= i < len(found) else None
    name = ident if ident.endswith(".md") else ident + ".md"
    for p in found:
        if p.name == name:
            return p
    return None


def set_provenance(path, provenance):
    """Rewrite ONLY the `**Provenance:**` line of an existing candidate file, in place, leaving
    every other field untouched. Raises ValueError on an unknown provenance, same as `render()` --
    a reviewer confirming or rejecting a candidate is still bound by the closed enum.

    🐛 [2026-09-13] `read()`, `fields_of()` and the merge scans in `upsert`/`_same_habit` all guard
    this same `read_text` against `OSError` -- this one and `set_status` beside it did not, so a
    candidate resolved by number (`chamnan-candidates confirm 3`) and then removed by the
    background hook's own dedup unlink (`upsert`, a few lines above) or by a second command in
    another terminal surfaced a raw `[Errno 2] No such file or directory: '<path>'` instead of a
    message naming what actually happened. Same store, same TOCTOU window `resolve()`'s own
    docstring already names; guarded to match the siblings that already handle it.
    """
    if provenance not in PROVENANCE:
        raise ValueError(f"unknown provenance: {provenance!r}")
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        raise OSError(f"{path.name} no longer exists -- it may have already been reviewed "
                      f"by another command") from None
    new_line = f"**Provenance:** {provenance}"
    if _FIELD.search(text) and "provenance" in _fields(text):
        text = re.sub(r"^\*\*Provenance:\*\*.*$", new_line, text, count=1, flags=re.M)
    else:
        text = text.rstrip("\n") + f"\n{new_line}\n"
    ws.write_or_raise(path, text)


def set_status(path, status):
    """Rewrite only `Status:`; provenance and the observation it describes stay untouched.

    Same guard as `set_provenance` beside it, same reason -- see its docstring."""
    if status not in STATUS:
        raise ValueError(f"unknown status: {status!r}")
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        raise OSError(f"{path.name} no longer exists -- it may have already been reviewed "
                      f"by another command") from None
    new_line = f"**Status:** {status}"
    if "status" in _fields(text):
        text = re.sub(r"^\*\*Status:\*\*.*$", new_line, text, count=1, flags=re.M)
    else:
        # Before Provenance keeps the stable trailer order used by freshly rendered candidates.
        match = re.search(r"^\*\*Provenance:\*\*.*$", text, flags=re.M)
        if match:
            text = text[:match.start()] + new_line + "\n" + text[match.start():]
        else:
            text = text.rstrip("\n") + f"\n{new_line}\n"
    ws.write_or_raise(path, text)


def count(root):
    """Number of candidates, or None when the directory does not exist at all -- distinct from
    existing and holding none, the same rule lib/ledger.py already applies to every other store."""
    d = directory(root)
    if not d.is_dir():
        return None
    return len(entries(root))
