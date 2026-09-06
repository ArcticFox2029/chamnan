"""Folding an oversized index down to one line per directory.

Lives in lib/ rather than in the hook because two places need the same answer: the hook, which does
the folding at session start, and chamnan-map, which has to tell the user what that will cost. A
separate estimate in the reporting path was wrong by 2.4x the first time it was tried — close enough
to look plausible, far enough to make the decision on bad numbers. One implementation, called twice.
"""
import re
import json
import mdblock
import subprocess
from pathlib import Path

import tokens
import workspace as ws

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


_SHA = re.compile(r"\A[0-9a-f]{40}\Z")


def _head_from_disk(root):
    """HEAD read straight off the filesystem, or "" when the layout is anything but the plain case.

    This value is a CACHE KEY, so a wrong one is worse than a slow one — it would serve a stale
    churn ranking as if it were current. Every branch here therefore returns "" rather than a guess,
    and the caller falls back to asking git. Handles the two ordinary shapes: a detached HEAD, which
    holds the sha itself, and a symref to a loose ref. A packed ref, a worktree's `.git` file, or
    anything unexpected is left to the subprocess.
    """
    try:
        git_dir = Path(root) / ".git"
        if not git_dir.is_dir():          # a worktree or submodule: `.git` is a FILE
            return ""
        head = (git_dir / "HEAD").read_text(encoding="utf-8-sig").strip()
        if _SHA.match(head):
            return head                   # detached
        if not head.startswith("ref: "):
            return ""
        ref = git_dir / head[5:].strip()
        if not ref.is_file():
            return ""                     # packed-refs, or an unborn branch
        value = ref.read_text(encoding="utf-8-sig").strip()
        return value if _SHA.match(value) else ""
    except (OSError, ValueError, UnicodeDecodeError):
        return ""


def _head(root):
    """The commit the churn answer belongs to, or "" when git cannot say.

    🐛 A subprocess for a value that is usually two small file reads. Measured 19-65ms against
    ~0.1ms, and the whole SessionStart hook 0.517s to 0.457s, on every session (R3 agent 1). The
    filesystem answer is used only when it is unambiguous; everything else still asks git, so the
    result is identical either way.
    """
    from_disk = _head_from_disk(root)
    if from_disk:
        return from_disk
    if not ws.git_owns(root):
        # A directory holding a `.git` git itself refuses is not a repository to git: the call
        # below would walk up and return an ANCESTOR's HEAD, which then gets stamped into MAP.md
        # as the commit this index was built from (R6 acc3, first ten minutes).
        return ""
    try:
        out = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                             stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def _disk_cache_path(root, window):
    try:
        import workspace as ws_mod
        d = ws_mod.workspace(root) / "state"
        return d / f"churn-{window}.json" if d.parent.is_dir() else None
    except Exception:
        return None


def _read_disk_cache(path, head):
    """The stored counts when they belong to this commit, else None. Never raises."""
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    if not isinstance(data, dict) or data.get("head") != head:
        return None
    counts = data.get("counts")
    return counts if isinstance(counts, dict) else None


def _remember(path, head, key, counts):
    """Store in both caches and return the counts, so a caller can `return _remember(...)`.

    Best-effort on disk: a read-only checkout, a full disk or a racing writer all fall back to the
    in-process cache, which is exactly the behaviour that existed before.
    """
    if path and head:
        try:
            import workspace as ws_mod
            ws_mod.atomic_write_text(path, json.dumps({"head": head, "counts": counts}))
        except Exception:
            pass
    return _CHURN_CACHE.setdefault(key, counts)


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
    # 🐛 That cache is per PROCESS, and the process it most needs to serve is the SessionStart hook,
    # which is a fresh interpreter every session and every compaction. Profiled: this one
    # `git log --name-status -M -n 600` is 1.263 s of the hook's 2.387 s — 53% of the thing sitting
    # on the critical path of every session start on a 1,209-commit repository, paid again each time
    # for an answer that had not changed.
    #
    # HEAD is the exact key: churn is derived from commit history and nothing else, so an unchanged
    # HEAD means an unchanged answer, and `git rev-parse HEAD` costs 44 ms against 1,263.
    head, disk = _head(root), _disk_cache_path(root, window)
    if head and disk:
        cached = _read_disk_cache(disk, head)
        if cached is not None:
            return _CHURN_CACHE.setdefault(key, cached)
    if not ws.git_owns(root):
        # See git_owns: an ancestor's churn would rank THIS repository's files.
        return _CHURN_CACHE.setdefault(key, {})
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
             # 🐛 `--no-merges` is not tidiness, it is the difference between a 600-commit window and a
             # 300-commit one. git does not diff a merge commit by default, so a merge contributes a
             # header and zero file-status lines — and on a project that merges pull requests with
             # --no-ff, which is most of them, half the window is merges. Measured on a repository
             # with that ordinary shape: 49.9% of the 600 commits produced nothing, so the ranking
             # was built from ~300 real edits while believing it had 600.
             #
             # It did not affect the figures this project has published: chamnan's own history is
             # 2.1% merges in the window and the development monorepo is 0%. It affects the users
             # whose repositories look like the ones this tool was written for.
             "log", "--no-merges", "--name-status", "-M",
             "--pretty=format:", "-n", str(window)],
            # A hook's stdin carries the host's JSON payload. A child that inherits it can consume
            # bytes the hook has not read yet, or block waiting on a prompt that will never come.
            stdin=subprocess.DEVNULL, capture_output=True,
            # `encoding` is named rather than left to `text=True` alone: that decodes with the
            # machine's preferred encoding, which on Windows is its ANSI code page -- so a commit
            # message or a filename with a Thai character or an em dash raises UnicodeDecodeError
            # there and nowhere else. `errors="replace"` because a raw invalid-UTF-8 byte in a
            # filename raises the same exception, which is neither an OSError nor a
            # SubprocessError, so the except below would not catch it and the whole hook would die.
            text=True, encoding="utf-8", errors="replace", timeout=10)
    except (OSError, subprocess.SubprocessError):
        return _remember(disk, head, key, {})
    if out.returncode != 0:
        return _remember(disk, head, key, {})
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
        return _remember(disk, head, key, {})
    return _remember(disk, head, key, counts)


def _disambiguate(path, name, top):
    """`api/handler.py` rather than `handler.py`, when the bare name would name two files at once.

    The directory prefix is taken relative to the group's own top-level folder, since that is
    already on the line -- repeating it would spend budget saying what the reader can see.
    """
    rel = path[len(top) + 1:] if path.startswith(top + "/") else path
    return rel if "/" in rel else name


# How many SPLITS the directory roll-up may take looking for a grouping that separates. Counted in
# splits, not path segments: a Maven tree does not branch until segment seven
# (`src/main/java/com/company/product/moduleNN`), and the earlier reading of this constant -- "three
# is far enough to get past src/main/java" -- stopped at `src/` with one line for 300 files, because
# it gave up the moment the NEXT segment failed to separate. Non-branching segments are skipped, up to
# MAX_SPINE_SEGMENTS, and only a segment that separates counts as a split.
MAX_GROUP_DEPTH = 3
# The longest non-branching prefix the roll-up will walk down looking for a split. Past this, a
# tree that still has not branched is one directory deep in a way no grouping will improve.
MAX_SPINE_SEGMENTS = 12
# Below this, one line per top-level directory is already a fine summary and deepening is noise.
MIN_FILES_TO_DEEPEN = 40
# One directory holding this share of everything means the depth is too shallow to be telling
# anyone anything.
#
# 🐛 0.6 was too permissive to catch the case it exists for. Measured on this repository's own
# index: `.chamnan/` is 48.6% of all files — under the threshold — so it stayed one bucket, and
# `.chamnan/tests/` (118 files) and `.chamnan/tools/` (40) were folded together into a single
# `.chamnan/ (158)` line. `tools/` is the directory the block itself tells an agent to prefer over
# writing a new script, so hiding it inside a bucket dominated by the test suite loses exactly the
# distinction a reader of this workspace needs (R3 agent 3).
#
# 0.45 separates them: the roll-up goes 1,509 to 2,293 tokens against a 3,000 budget, so it still
# fits with a quarter to spare. MIN_FILES_TO_DEEPEN and MAX_GROUP_DEPTH still bound how far this
# can go on a repository shaped differently.
DOMINANT_SHARE = 0.45


def _is_a_directory_heading(line):
    """A bare `**`path/`**` line -- a Quick Index directory heading and nothing else.

    Matched on the whole stripped line rather than a prefix, so a sentence that merely begins with a
    bolded path is not mistaken for a heading and deleted.
    """
    stripped = line.strip()
    return (stripped.startswith("**`") and stripped.endswith("`**")
            and stripped.count("**") == 2)


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
    # 🐛 [2026-09-06] The last line of `head` is the directory heading the FIRST row happened to sit
    # under in the un-rolled index, and everything below is about to be regrouped -- so that heading
    # is left standing over a list it does not describe. On this repository's real block, at the
    # production default budget, `**`.chamnan/tests/`**` headed twenty directories from six
    # different trees. It is a false claim in the one section three rounds have called the reason
    # the block is a pointer rather than content, and it is in every session's context.
    #
    # Recorded as a low-budget artefact in the backlog ("orphaned-heading artefact at the cliff",
    # 350-500 tokens) and independently reproduced there by R3 agent 3, which concluded the cliff
    # was unreachable in practice. Both were right about the cliff and wrong about the scope: the
    # heading is dropped only when the whole SECTION goes, so the cliff is where the symptom
    # disappears, not where it starts. Gated on folding actually happening, not on the budget
    # (R7 agent 1).
    # Trailing blanks first: whether a blank line separates the heading from the first row is a
    # detail of how MAP.md was rendered, not of whether the heading is orphaned. Checking `head[-1]`
    # before stripping them made the fix work on the real index (no blank there) and silently do
    # nothing on a fixture that had one -- which is the shape of a guard that only looks where it
    # expects the problem, and this file has paid for that twice already.
    if row_at:
        while head and not head[-1].strip():
            head = head[:-1]
        if head and _is_a_directory_heading(head[-1]):
            head = head[:-1]
            while head and not head[-1].strip():
                head = head[:-1]
    # Grouped at whatever depth actually separates this repository, not always at depth 1. Most
    # repositories keep their source under one directory -- src/, app/, lib/ -- and grouping by the
    # first segment then yields ONE line reading `src/ (528)`, which is a roll-up in shape only: it
    # names nothing the reader did not already know. Measured on an 804-file corpus whose files all
    # sit under `corpus/`, depth 1 gave 2 groups for 529 files.
    #
    # So: go deeper while the split is not telling anyone anything. The test is groups-per-file --
    # one directory holding almost everything means the depth is too shallow. It stops as soon as
    # the split is informative, so a repository that is already flat at depth 1 is untouched.
    # The Quick Index states a directory once and then lists basenames under it, so a row's own
    # backticks may hold only the filename. Reconstruct the full path from the nearest preceding
    # `**\`dir/\`**` heading — reading the basename as a path would group every directory's files
    # under "(root)" and produce a roll-up that names nothing.
    paths = []
    _dir = ""
    _at = set(row_at)
    for i, line in enumerate(lines):
        if line.startswith("## "):
            _dir = ""
            continue
        st = line.strip()
        if st.startswith("**`") and st.endswith("/`**"):
            _dir = st[3:-4]
            continue
        if i in _at:
            name = line.split("`")[1]
            paths.append(f"{_dir}/{name}" if _dir and "/" not in name else name)

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
    splits = 0
    while splits < MAX_GROUP_DEPTH and len(paths) > MIN_FILES_TO_DEEPEN:
        biggest = max((len(v) for v in groups.values()), default=0)
        if biggest <= len(paths) * DOMINANT_SHARE:
            break
        # 🐛 Only if it actually separates -- but LOOK for the depth that does, rather than testing
        # the very next one and giving up. `src/main/java/com/company/product/module01/...` has six
        # segments that each yield the same single group; the old loop tried depth 2, saw one group
        # again, and broke, leaving 60 modules as one `src/` line whose eight sample names all came
        # from module01 -- which looked like a distinction had been made when none had. Reproduced
        # on a 300-file Maven fixture: 1 group named out of 60.
        look = depth + 1
        deeper = at_depth(look)
        while len(deeper) <= len(groups) and look < MAX_SPINE_SEGMENTS:
            look += 1
            deeper = at_depth(look)
        if len(deeper) <= len(groups):
            break          # nothing separates within the spine limit: a longer name for nothing
        groups, depth, splits = deeper, look, splits + 1
    if not groups:
        # Nothing here has the `- **`path`**` shape this groups on: a hand-written map, one from an
        # older chamnan, or -- the case that actually happened -- an index that has already been
        # folded once. Announcing "0 files, rolled up by directory" above content that plainly is
        # not, and is not smaller either, is worse than doing nothing. _enforce still has the last
        # word on the budget.
        return _enforce(index, map_rel, budget) if budget else index
    folded = [f"_{len(rows)} files. Rolled up by directory to stay inside the session budget —"
              f" read `{map_rel}` for any one of them in full._", ""]
    # Where the per-directory lines start. `folded` opens with a header and a blank, so the counts
    # collected below align with `folded[first:]` and not with `folded` itself.
    first = len(folded)
    meta = []          # (group key, file count) per directory line, same order as folded[first:]
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
        # 🐛 The basename was shown, so the line named a path that DOES NOT EXIST whenever the file
        # sits in a subdirectory. Measured across four real repositories: 35 of 101 sampled paths
        # were wrong — gum's `internal/ (6) — align.go, context.go, tty.go` are really
        # internal/decode/align.go, internal/timeout/context.go and internal/tty/tty.go, 6 of 6
        # wrong; execa 29 of 34, because all 108 of its `lib/` files are in subdirectories.
        #
        # A wrong path costs a failed Read and then a recovery search, which is the failure this
        # project calls worse than a missing entry — and the roll-up exists precisely to be the
        # thing a session trusts when the per-file index does not fit.
        #
        # The path relative to the group, always: `decode/align.go` under `internal/` reconstructs
        # to the real file by concatenation. The disambiguation below stays for the case it was
        # written for — two files that are genuinely identical relative to the group cannot happen,
        # but a group at depth > 1 can still produce repeats.
        def _rel_to_group(pth):
            return pth[len(top) + 1:] if top != "(root)" and pth.startswith(top + "/") else pth
        counts = {}
        for pth, _ in chosen:
            r = _rel_to_group(pth)
            counts[r] = counts.get(r, 0) + 1
        picked = sorted(_disambiguate(pth, _rel_to_group(pth), top)
                        if counts[_rel_to_group(pth)] > 1 else _rel_to_group(pth)
                        for pth, _ in chosen)
        shown = ", ".join(f"`{n}`" for n in picked)
        hidden = len(names) - len(picked)
        # "+N more" is only meaningful next to names it is more THAN. With none shown the count
        # already says how many there are, and repeating it as "(12) +12 more" reads as a bug.
        more = f" _+{hidden} more_" if hidden and picked else ""
        # 🐛 as_quoted, not one_line: `one_line` folds newlines and strips control characters
        # but leaves BACKTICKS, and this line wraps nothing in a code span itself -- a
        # directory named ``code`` closed the span the caller opens and rendered as chamnan
        # speaking. Verified end to end, chamnan-map -> MAP.md -> the injected block.
        folded.append(f"- **{mdblock.as_quoted(top, 80)}/** ({len(names)})"
                      + (f" — {shown}{more}" if shown else ""))
        # 🐛 Carried as DATA beside the line, never re-extracted from it. The overflow fold used to
        # regex this count back out of the markdown above, and a directory named `evil** (99999)`
        # survives `as_quoted` — which strips backticks, not asterisks or parentheses — to be
        # matched FIRST by that regex. The repository could dictate the figure chamnan printed in
        # its own voice. Re-parsing your own output is the whole defect; the count never leaves
        # Python now.
        meta.append((top, len(names)))
    out = "\n".join(head + folded + tail)
    if budget:
        out = _fold_the_overflow(head, folded, first, meta, tail, map_rel, budget)
    return _enforce(out, map_rel, budget) if budget else out


def _fold_the_overflow(head, folded, first, meta, tail, map_rel, budget):
    """One more level of folding, for when the directory lines THEMSELVES do not fit.

    🐛 Measured on 300 sibling packages -- a Lerna/Nx/Turborepo/Go-multi-module layout, and the shape
    a package-per-service team has: `per_dir=0` named 212 of them and the other 88 were the tail
    `_enforce` cut off. The block then said "Quick Index is cut short", which is true and useless: it
    names no directory, gives no count, and the reader cannot tell whether three are missing or three
    hundred. `collapse`'s own docstring promises "coarse and complete beats detailed and arbitrarily
    half-missing", and past ~200 groups it was delivering exactly the arbitrary half.

    So the overflow is folded one level UP rather than dropped: the leftover groups are gathered by
    their parent and each parent gets a line saying how many directories and files are under it. The
    reader learns that `packages/` holds 88 more, which is the difference between a known gap and an
    invisible one. Nothing is silently lost, and the cost is one line per parent.
    """
    if tokens.estimate("\n".join(head + folded + tail)) <= budget:
        return "\n".join(head + folded + tail)

    def parent_of(top):
        return top.rsplit("/", 1)[0] if "/" in top else ""

    # 🐛 `kept` stepped by a stride under `while kept > 0`, so it walked PAST zero without ever
    # evaluating it — and zero is the maximally folded, smallest, most useful candidate. For any
    # budget tight enough to need full folding, this fell through to returning the raw unfolded
    # dump: the exact failure the function exists to prevent, hidden because `_enforce` runs
    # afterward and cuts the tail, so the block looked merely truncated rather than unfolded.
    # The candidates are enumerated explicitly now, and the last one is 0.
    # Down to ONE named group, never to zero. R10 agent 2 called zero "the maximally folded,
    # smallest, most useful candidate"; driving it showed the opposite — on an index whose bulk is
    # the sections AFTER the file rows, folding every group away hands the reader a single summary
    # line where ten named directories would have survived `_enforce`'s tail cut. Folding is only
    # ever an improvement while something is still named.
    stride = max(1, len(meta) // 40)
    for keep_n in sorted({*range(len(meta), 0, -stride), 1}, reverse=True):
        summary = []
        for par in dict.fromkeys(parent_of(top) for top, _ in meta[keep_n:]):
            rows = [(top, n) for top, n in meta[keep_n:] if parent_of(top) == par]
            where = f"`{mdblock.as_quoted(par, 60)}/`" if par else "the repository root"
            summary.append(f"- _{len(rows)} more director{'y' if len(rows) == 1 else 'ies'} under "
                           f"{where}, {sum(n for _, n in rows):,} files, not named here — "
                           f"grep `{map_rel}`_")
        candidate = "\n".join(head + folded[:first + keep_n] + summary + tail)
        if tokens.estimate(candidate) <= budget:
            return candidate
    # Nothing fits even with one group named, which means the budget is being spent somewhere other
    # than these lines. Hand back the unfolded text and let `_enforce` cut the tail, which is what it
    # did before this function existed — folding further would only delete the part still worth
    # having.
    return "\n".join(head + folded + tail)


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
    # 🐛 The note said "the roll-up could not group this map's rows" whatever had actually been cut.
    # That wording is calibrated for one case — ungroupable Quick Index rows — and this function
    # also fires when the thing removed is a whole catalog section, which is prose and was never
    # row-shaped and was never offered to the grouping logic at all. Measured on the published
    # corpus: 3,474 tokens, 46.3% of the catalog payload — Configuration, Deployment and Stored
    # material — vanished with no heading, no count, and a note blaming a mechanism that had not
    # run on them. A reader who followed it would go looking at the Quick Index.
    #
    # So say what went, by name. A section that is named is one grep away in MAP.md; a section
    # that is gone with no trace is the "looks complete and is not" this module exists to stop,
    # and it is the same defect that let the architecture index disappear from 59% of firings.
    def _headings(text):
        return [l[3:].strip() for l in text.split("\n") if l.startswith("## ")]

    # The note's own length changes where the cut lands, and where the cut lands changes which
    # headings are lost, which changes the note. So settle it rather than guess once: a first pass
    # naming nothing produced a note that claimed `Quick Index` had been removed whole while it was
    # still in the output, because "lost" had been read off a provisional cut the final one did not
    # match. Three passes is enough for it to stop moving; the last one is authoritative.
    # 🐛 The note had no bound of its own. Naming every removed section made the note itself the
    # thing that blew the budget: a 20-token budget over a map with forty sections produced 1,052
    # tokens of output, 1,050 of them the note. A budget enforcer that overruns by 53x is not one.
    #
    # Four names and a count. Four is what the sibling notices in `fit.py` and `impact.py` already
    # use, and the reason is the same — past four, a reader is scanning a list rather than reading a
    # sentence, and the count carries the rest. If even that does not fit, the short form does,
    # because a truncated explanation is worse than a general one.
    NAMED = 4

    # 🐛 Sections removed WHOLE were named; a section cut in half was not. This is a prefix cut, so
    # the last heading it keeps is a section that kept its title and lost most of its body — and
    # said nothing about it. Measured: sixty routes selected, twenty-nine delivered, heading intact,
    # no notice, and the section's own "Showing 60 of 5,000" line left standing as a claim about
    # content that is not there.
    #
    # That is quieter than the whole-section drop this note already reports, and worse for the same
    # reason `fit.py` drops sections whole rather than cutting them: a reader can act on "this is
    # missing, go and grep it", and cannot act on a list that looks complete and is not.
    def _trimmed_in(cut_text):
        heads = _headings(cut_text)
        if not heads:
            return None
        # A cut landing exactly on the next heading's line leaves the previous section intact.
        return None if cut_text.rstrip().endswith(f"## {heads[-1]}") else heads[-1]

    def _note_for(lost, trimmed):
        # Three tiers, longest first, because the note has to fit inside the budget it is enforcing
        # — a 20-token budget once produced a 1,052-token note, 1,050 of it this sentence. Adding
        # the "cut short" clause made the full form overflow on tight budgets and fall all the way
        # back to naming nothing, which lost MORE than the clause added. So the explanation is what
        # goes first, then the names, and only then the bare form.
        short = (f"\n\n_Cut to fit the session budget — the tail did not fit."
                 f" Read `{map_rel}` for anything missing here._")
        if not lost and not trimmed:
            return short
        named = ""
        if lost:
            named = (f"Removed whole: {', '.join(f'`{h}`' for h in lost[:NAMED])}"
                     + (f" _+{len(lost) - NAMED} more_" if len(lost) > NAMED else "") + ".")
        for clause in ((f"`{trimmed}` is cut short — its own counts describe what was selected, "
                        f"not what is here.") if trimmed else "",
                       f"`{trimmed}` is cut short." if trimmed else ""):
            body = " ".join(x for x in (named, clause) if x)
            cand = f"\n\n_Cut to fit the session budget. {body} Read `{map_rel}` for the rest._"
            if tokens.estimate(cand) < budget:
                return cand
        if named:
            cand = (f"\n\n_Cut to fit the session budget. {named}"
                    f" Read `{map_rel}` for the rest._")
            if tokens.estimate(cand) < budget:
                return cand
        return short

    note, cut = _note_for([], None), ""
    for _ in range(3):
        keep = tokens.cut_at(out, max(budget - tokens.estimate(note), 1))
        cut = out[:keep].rsplit("\n", 1)[0] if "\n" in out[:keep] else out[:keep]
        fresh = _note_for([h for h in _headings(out) if h not in _headings(cut)],
                          _trimmed_in(cut))
        if fresh == note:
            break
        note = fresh
    # One last cut against the note that is actually going out, so the total never exceeds budget.
    keep = tokens.cut_at(out, max(budget - tokens.estimate(note), 1))
    cut = out[:keep].rsplit("\n", 1)[0] if "\n" in out[:keep] else out[:keep]
    return cut + note
