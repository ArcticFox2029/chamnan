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

**`Provenance:` is one field, not two.** A separate `State:` (confirmed / observed / draft) would
overlap it by about 80%, and two fields for one idea is how a format rots — the same reasoning
`lib/memory.py` and the trailer grammar in `lib/milestones.py` already follow. `deprecated` is the
value that retires a candidate without deleting it, matching `memory.py`'s refusal to prune by age:
the oldest entry is usually the one nobody could reconstruct, so nothing here deletes on a timer
either.

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
    joined = "-".join(sequence)
    s = mdblock.ascii_stem(joined)
    return mdblock.filename_safe(s[:60].rstrip("-")
                                 or mdblock.fallback_name(joined, "candidate"))


def filename(sequence):
    return f"{slug(sequence)}.md"


def path_for(root, sequence):
    return directory(root) / filename(sequence)


def _fields(text):
    """Trailer fields as a lowercase-keyed dict, e.g. {"observed": "3", "provenance": "ai-inferred"}."""
    return {m.group(1).strip().lower(): m.group(2).strip() for m in _FIELD.finditer(text)}


def render(sequence, observed, last_seen, provenance):
    """The candidate file's full text. Raises ValueError on an unknown provenance -- rejected at
    the point of writing, never stored, per the closed enum this whole module exists to enforce."""
    if provenance not in PROVENANCE:
        raise ValueError(f"unknown provenance: {provenance!r}")
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
            _write(strict)(target, render(merged, max(observed, was), when, provenance))
            return target, False
    is_new = not p.is_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    _write(strict)(p, render(sequence, observed, when, provenance))
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
    for other in entries(root):
        try:
            fields = _fields(other.read_text(encoding="utf-8-sig", errors="replace"))
        except OSError:
            continue
        got = tuple(x.strip() for x in (fields.get("sequence") or "").split(",") if x.strip())
        if not got or got == want:
            continue
        if want in _rotations(got) or got in _rotations(want):
            return other, list(got)
        longer, shorter = (got, want) if len(got) > len(want) else (want, got)
        if any(longer[i:i + len(shorter)] == shorter
               for i in range(len(longer) - len(shorter) + 1)):
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
    a reviewer confirming or rejecting a candidate is still bound by the closed enum."""
    if provenance not in PROVENANCE:
        raise ValueError(f"unknown provenance: {provenance!r}")
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    new_line = f"**Provenance:** {provenance}"
    if _FIELD.search(text) and "provenance" in _fields(text):
        text = re.sub(r"^\*\*Provenance:\*\*.*$", new_line, text, count=1, flags=re.M)
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
