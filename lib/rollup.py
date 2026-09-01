"""Folding an oversized index down to one line per directory.

Lives in lib/ rather than in the hook because two places need the same answer: the hook, which does
the folding at session start, and chamnan-map, which has to tell the user what that will cost. A
separate estimate in the reporting path was wrong by 2.4x the first time it was tried — close enough
to look plausible, far enough to make the decision on bad numbers. One implementation, called twice.
"""
import subprocess

import tokens

# Below this, the history is too thin to rank with. Measured elsewhere: commit-history memory
# degrades localization by 13.1pp on repos with sparse history (arXiv:2510.01003), so a young repo
# is better served by the stable alphabet than by a ranking built on four commits.
MIN_COMMITS_TO_RANK = 50

# How far back to count. Far enough to see what a repo works on, near enough that a file abandoned
# two years ago stops crowding out one being edited this week.
CHURN_WINDOW = 600


# One `git log` per process. collapse() is now called several times in a session when the block is
# over its byte ceiling and the index is being stepped down, and re-shelling for an answer that
# cannot have changed between those calls is pure latency on every session start.
_CHURN_CACHE = {}


def forget_churn():
    """Drop the memo. Needed only by a caller that changes the repository's history mid-process --
    which the hook and chamnan-map never do, and a test that builds up a fixture repo does."""
    _CHURN_CACHE.clear()


def _churn(root, window=CHURN_WINDOW):
    """Commits touching each tracked path over the last `window` commits, or {} if git cannot say.

    Local, read-only, no network -- `git log` is the one external process this package allows
    itself, and a repo without git simply falls back to the alphabet.
    """
    if not root:
        return {}
    key = (str(root), window)
    if key in _CHURN_CACHE:
        return _CHURN_CACHE[key]
    try:
        out = subprocess.run(
            # --name-status -M, not --name-only. Without rename detection a file that has been
            # renamed has its history split across two literal strings: the old name collects the
            # commits before the move, the new name only those after. Measured on a file with six
            # touches across one `git mv`, plain --name-only reports old:4 new:2 and the true six
            # appears nowhere -- so the file that actually exists is ranked on a third of its real
            # churn, and drops off a roll-up line it had earned a place on.
            # -c core.quotePath=false: git's default C-quotes any non-ASCII path, so
            # `รายงาน.py` comes back as `"\340\270\243..."` and the lookup against the index's real
            # path never matches -- every such file is credited zero churn, silently. That is the
            # whole ranking, disabled, for any repository whose filenames are not ASCII.
            ["git", "-C", str(root), "-c", "core.quotePath=false",
             "log", "--name-status", "-M",
             "--pretty=format:", "-n", str(window)],
            # A hook's stdin carries the host's JSON payload. A child that inherits it can consume
            # bytes the hook has not read yet, or block waiting on a prompt that will never come.
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            # errors="replace": a raw invalid-UTF-8 byte in a filename raises
            # UnicodeDecodeError, which is neither an OSError nor a SubprocessError,
            # so the except below would not catch it and the whole hook would die.
            errors="replace", timeout=10)
    except (OSError, subprocess.SubprocessError):
        return _CHURN_CACHE.setdefault(key, {})
    if out.returncode != 0:
        return _CHURN_CACHE.setdefault(key, {})
    counts = {}
    seen_commits = 0
    renamed_from = {}          # old path -> the name it ends up under
    for line in out.stdout.splitlines():
        if not line.strip():
            seen_commits += 1
            continue
        # --name-status emits "<status>\t<path>", and for a rename or copy
        # "R100\t<old>\t<new>". Credit the whole history to the name that survives.
        parts = line.split("\t")
        if len(parts) >= 3 and parts[0][:1] in ("R", "C"):
            old, new = parts[1], parts[2]
            renamed_from[old] = renamed_from.get(new, new)
            counts[new] = counts.get(new, 0) + 1
        elif len(parts) >= 2:
            counts[parts[1]] = counts.get(parts[1], 0) + 1
    # Fold each old name's commits into whatever it was renamed to, following a chain of moves.
    for old, new in renamed_from.items():
        seen = set()
        while new in renamed_from and new not in seen:
            seen.add(new)
            new = renamed_from[new]
        if old in counts and old != new:
            counts[new] = counts.get(new, 0) + counts.pop(old)
    if seen_commits < MIN_COMMITS_TO_RANK:
        return _CHURN_CACHE.setdefault(key, {})
    return _CHURN_CACHE.setdefault(key, counts)


def _disambiguate(path, name, top):
    """`api/handler.py` rather than `handler.py`, when the bare name would name two files at once.

    The directory prefix is taken relative to the group's own top-level folder, since that is
    already on the line -- repeating it would spend budget saying what the reader can see.
    """
    rel = path[len(top) + 1:] if path.startswith(top + "/") else path
    return rel if "/" in rel else name


# How deep the directory roll-up may go looking for a split that separates. Three is far enough to
# get past src/main/java without turning a line into a path nobody can read.
MAX_GROUP_DEPTH = 3
# Below this, one line per top-level directory is already a fine summary and deepening is noise.
MIN_FILES_TO_DEEPEN = 40
# One directory holding this share of everything means the depth is too shallow to be telling
# anyone anything.
DOMINANT_SHARE = 0.6


def collapse(index, map_rel, budget=None, root=None, per_dir=8):
    """Fold a too-large index down to one line per directory instead of cutting its tail off.

    Truncating at a byte offset drops whatever sorts last, so on a 196-file repo everything from
    roughly `s` onward vanishes from the session with no indication that a whole area of the code
    exists. The agent then greps for it, which is the cost this file is meant to remove.

    A directory roll-up keeps every part of the repo visible at lower resolution: the agent still
    learns that `2dspeak/` and `game/` are there and how big they are, and can read the full entry
    for one of them out of MAP.md. Coarse and complete beats detailed and arbitrarily half-missing.

    WHICH eight filenames survive per directory used to be `sorted(names)[:8]` -- the alphabet,
    which knows nothing about the repo. Measured on this one: of 12,332 re-read events across six
    working sessions, the alphabetical eight named 22.7% of them, git-churn-ranked eight named
    35.6%, and the unreachable oracle that picks with hindsight reaches 57.0%. Ranking by how often
    a file is committed captures over a third of the available headroom for one `git log`.

    `root` is optional and the ranking is a bonus, never a requirement: no git, a shallow clone, or
    a repo under MIN_COMMITS_TO_RANK commits all fall back to the alphabet, which is stable and
    diffs cleanly. Names are always emitted sorted regardless of how they were chosen, so the line
    reads the same way and a re-run does not reshuffle it.

    `per_dir` is how many names each directory line carries. It exists so a caller that is over a
    hard output limit can spend the index's resolution before spending the index: four names still
    orient a reader, and `per_dir=0` still says the directory exists and how big it is. Losing
    resolution is cheaper than losing the section, and much cheaper than losing whatever would have
    been dropped in its place.
    """
    # Split by POSITION, not by kind. Bucketing every non-row line into one "header" and appending
    # the roll-up after it put the roll-up last -- and _enforce cuts from the end, so on any index
    # large enough to need collapsing, the roll-up was cut in its entirety. Measured on an 804-file
    # corpus: the non-row lines are the Data model, API surface and Configuration sections, 7,412
    # tokens against a 3,000-token budget, so the delivered block carried 3,000 tokens of those
    # sections and ZERO file rows. The Quick Index rendered as a heading followed by nothing, under
    # a line telling the reader to read it in full.
    #
    # Keeping document order fixes it without a special case: the roll-up goes exactly where the
    # rows it replaces were, and what follows them still follows them. _enforce then cuts the
    # sections after the index first, which is the right thing to lose.
    # Bounded to the Quick Index section. `- **`path`**` is not unique to it: the "Stored material
    # (not source)" section that assets.py renders uses the identical shape for DIRECTORY rows, so
    # an unbounded scan folded a directory in with the files and produced an entry whose basename
    # was the empty string -- and, worse, put the last row far past the Quick Index, so everything
    # between the two sections was swallowed into the replaced span.
    lines = index.splitlines()
    # Scoped only when the heading is actually there. A hand-written map, one from an older
    # chamnan, or a caller passing a bare list of rows has no `## Quick Index` at all -- and for
    # those the whole input IS the index, which is what this function has always assumed. Scoping
    # unconditionally turned that case into "no rows found" and returned the input untouched.
    has_heading = any(line.strip() == "## Quick Index" for line in lines)
    in_index = not has_heading
    row_at = []
    for i, line in enumerate(lines):
        if line.startswith("## "):
            in_index = line.strip() == "## Quick Index"
            continue
        if in_index and line.startswith("- **`"):
            row_at.append(i)
    rows = [lines[i] for i in row_at]
    head = lines[:row_at[0]] if row_at else lines
    tail = lines[row_at[-1] + 1:] if row_at else []
    # Grouped at whatever depth actually separates this repository, not always at depth 1. Most
    # repositories keep their source under one directory -- src/, app/, lib/ -- and grouping by the
    # first segment then yields ONE line reading `src/ (528)`, which is a roll-up in shape only: it
    # names nothing the reader did not already know. Measured on an 804-file corpus whose files all
    # sit under `corpus/`, depth 1 gave 2 groups for 529 files.
    #
    # So: go deeper while the split is not telling anyone anything. The test is groups-per-file --
    # one directory holding almost everything means the depth is too shallow. It stops as soon as
    # the split is informative, so a repository that is already flat at depth 1 is untouched.
    paths = [line.split("`")[1] for line in rows]

    def at_depth(depth):
        out = {}
        for path in paths:
            parts = path.split("/")
            # No trailing slash: the renderer adds one. Carrying it here produced `corpus/apps//`.
            # A file shallower than the chosen depth keeps its own real parent instead of
            # falling into "(root)". Once one dominant directory pushes the depth to 2,
            # `src/blocking.rs` and `tests/fs.rs` both have only one directory segment — and both
            # landed in the same "(root)" bucket, which then read as 175 loose files at the top of
            # the repository. It merged production code with integration tests under a name that
            # was true of neither. "(root)" now means what it says: a file with no directory.
            if len(parts) > depth:
                key = "/".join(parts[:depth])
            elif len(parts) > 1:
                key = "/".join(parts[:-1])
            else:
                key = "(root)"
            out.setdefault(key, []).append((path, parts[-1]))
        return out

    groups = at_depth(1)
    depth = 1
    while depth < MAX_GROUP_DEPTH and len(paths) > MIN_FILES_TO_DEEPEN:
        biggest = max((len(v) for v in groups.values()), default=0)
        if biggest <= len(paths) * DOMINANT_SHARE:
            break
        deeper = at_depth(depth + 1)
        # Only if it actually separates. A directory of 500 files with one subdirectory splits into
        # the same single group one level down, and taking it would spend a longer name for nothing.
        if len(deeper) <= len(groups):
            break
        groups, depth = deeper, depth + 1
    if not groups:
        # Nothing here has the `- **`path`**` shape this groups on: a hand-written map, one from an
        # older chamnan, or -- the case that actually happened -- an index that has already been
        # folded once. Announcing "0 files, rolled up by directory" above content that plainly is
        # not, and is not smaller either, is worse than doing nothing. _enforce still has the last
        # word on the budget.
        return _enforce(index, map_rel, budget) if budget else index
    folded = [f"_{len(rows)} files. Rolled up by directory to stay inside the session budget —"
              f" read `{map_rel}` for any one of them in full._", ""]
    churn = _churn(root)
    for top, entries in sorted(groups.items()):
        names = [n for _, n in entries]
        if churn:
            # Rank by commits, break ties on the name so the choice is deterministic.
            entries = sorted(entries, key=lambda e: (-churn.get(e[0], 0), e[1]))
        else:
            entries = sorted(entries, key=lambda e: e[1])
        # Disambiguated by the path, not the basename. Grouping kept only `path.split("/")[-1]`,
        # so three genuinely different files -- src/api/handler.py, src/utils/handler.py,
        # src/jobs/handler.py -- rendered as `handler.py`, `handler.py`, `handler.py`: three
        # identical tokens naming three different files, none of them recoverable from the line.
        # A repeated basename across subpackages is the normal shape of a large repo
        # (__init__.py, index.js, types.ts), so this is common rather than exotic.
        chosen = entries[:per_dir]
        counts = {}
        for _, n in chosen:
            counts[n] = counts.get(n, 0) + 1
        picked = sorted(_disambiguate(pth, n, top) if counts[n] > 1 else n for pth, n in chosen)
        shown = ", ".join(f"`{n}`" for n in picked)
        hidden = len(names) - len(picked)
        # "+N more" is only meaningful next to names it is more THAN. With none shown the count
        # already says how many there are, and repeating it as "(12) +12 more" reads as a bug.
        more = f" _+{hidden} more_" if hidden and picked else ""
        folded.append(f"- **{top}/** ({len(names)})" + (f" — {shown}{more}" if shown else ""))
    out = "\n".join(head + folded + tail)
    return _enforce(out, map_rel, budget) if budget else out


def _enforce(out, map_rel, budget):
    """Last resort when the roll-up did not actually get under the budget.

    Grouping only works on rows this module recognises. A hand-written map, one written by an older
    chamnan, or a future change to the row format all produce zero groups — and the old code then
    returned its input untouched while the caller went on believing it had been folded, injecting an
    over-budget index with nothing to show that anything had gone wrong. A budget that fails open is
    not a budget. Cutting on a line boundary and saying so is worse than a roll-up and far better
    than a silent overrun.
    """
    if tokens.fits(out, budget):
        return out
    note = (f"\n\n_Cut to fit the session budget — the roll-up could not group this map's rows."
            f" Read `{map_rel}` for anything missing here._")
    keep = tokens.cut_at(out, budget - tokens.estimate(note))
    cut = out[:keep].rsplit("\n", 1)[0] if "\n" in out[:keep] else out[:keep]
    return cut + note
