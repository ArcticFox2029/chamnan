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

DIRNAME = "candidates"

PROVENANCE = ("user", "ai-drafted", "ai-confirmed", "ai-inferred", "imported", "deprecated")

_FIELD = re.compile(r"^\*\*([A-Za-z ]+):\*\*\s*(.*)$", re.M)


def directory(root):
    from workspace import workspace
    return workspace(root) / DIRNAME


def slug(sequence):
    joined = "-".join(sequence)
    s = re.sub(r"[^a-zA-Z0-9]+", "-", joined.strip().lower()).strip("-")
    return mdblock.filename_safe(s[:60].rstrip("-") or "candidate")


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
    title = " · ".join(sequence)
    steps = ", ".join(sequence)
    return (f"# {mdblock.one_line(title)}\n\n"
            f"**Sequence:** {steps}\n"
            f"**Observed:** {observed}\n"
            f"**Last seen:** {last_seen}\n"
            f"**Provenance:** {provenance}\n")


def upsert(root, sequence, observed, when, provenance="ai-inferred"):
    """Create or update the one candidate for `sequence`. `observed` and `when` (a date string) are
    written as given -- not accumulated here -- so calling this repeatedly with the same values is
    a no-op on disk, and calling it with a fresher count or date correctly updates in place.

    Returns (path, is_new). Raises ValueError on an unknown provenance, before anything is written.
    """
    if provenance not in PROVENANCE:
        raise ValueError(f"unknown provenance: {provenance!r}")
    p = path_for(root, sequence)
    is_new = not p.is_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render(sequence, observed, when, provenance), encoding="utf-8")
    return p, is_new


def read(root, sequence):
    """(observed, last_seen, provenance) for an existing candidate, or None if it does not exist
    or does not parse. Never raises on a malformed file -- a candidate is a hint store, not a
    contract the rest of the plugin can depend on being well-formed."""
    p = path_for(root, sequence)
    if not p.is_file():
        return None
    try:
        fields = _fields(p.read_text(encoding="utf-8", errors="replace"))
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
    return sorted(p for p in d.glob("*.md") if p.is_file())


def fields_of(path):
    """Trailer fields for a specific candidate FILE, when the caller already has the path rather
    than the sequence `read()` needs. `{}` for a missing or unreadable file -- a review tool
    listing candidates should show what it can, not crash on one bad file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
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
    text = path.read_text(encoding="utf-8", errors="replace")
    new_line = f"**Provenance:** {provenance}"
    if _FIELD.search(text) and "provenance" in _fields(text):
        text = re.sub(r"^\*\*Provenance:\*\*.*$", new_line, text, count=1, flags=re.M)
    else:
        text = text.rstrip("\n") + f"\n{new_line}\n"
    path.write_text(text, encoding="utf-8")


def count(root):
    """Number of candidates, or None when the directory does not exist at all -- distinct from
    existing and holding none, the same rule lib/ledger.py already applies to every other store."""
    d = directory(root)
    if not d.is_dir():
        return None
    return len(entries(root))
