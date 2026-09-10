"""One pruned walk of the repository, shared by everything that needs to look at every file.

Measured on a 224-file repository before this existed: `chamnan-map` took 75s, and 31s of that was
`render()` — 26.8s of which was inside `rglob`, across **94,538 calls**. Nine separate full-tree
walks were running per map, one per scanner and several inside per-pattern loops:

    assets.scan        rglob("*")                         19.2s
    deploy.scan        rglob(pattern) per pattern          9.5s
    catalogs.scan_routes rglob(pat) per pattern            7.4s
    catalogs.scan_env  rglob("*.yaml"/"*.yml"/"*.json")    6.2s
    schema             rglob("*.sql"), rglob("*.prisma")
    mapper             rglob(".git"), rglob("*")

Each of them filtered SKIP_DIRS *after* pathlib had already descended, so every one paid the full
cost of `.venv`, `node_modules`, `.git` and any nested checkout before throwing the results away —
and `catalogs` and `schema` had no skip list at all, so a YAML file inside a virtualenv counted as
this repository's configuration.

`os.walk` with in-place pruning of `dirnames` never enters those directories in the first place, and
doing it once and caching means the second scanner pays nothing. This helps the FIRST run as much as
a repeat one, which is why it is the walk that was fixed rather than a cache added on top of it.

Reading every file to hash it, for comparison, costs 0.08s on the same repository — so if an
incremental index is ever built, this is the layer it should sit on, not a replacement for it.
"""
import os
from contextlib import contextmanager
from pathlib import Path

# What the walk is allowed to prune: the INTERSECTION of what every scanner already skipped, not
# the union. Pruning wider would silently change what those scanners see — measured: pruning with
# mapper's 27-entry list dropped one directory's stored-material count from 774 files to 762,
# because assets never skipped `build/`, `out/` or `tmp/` and suddenly did. A performance change
# that quietly rewrites the map is not a performance change.
#
# So each module keeps its own filter, applied after the walk exactly as before, and this set holds
# only the directories all five agreed on. That is enough: these are the ones that are enormous.
# Directories the walk could not enter, filled by the onerror hook below and reported by
# chamnan-map. A set, because one walk may hit the same parent repeatedly.
UNREADABLE = set()

# 🐛 `.git` was the only version-control directory in this set, while workspace.VCS_MARKERS has
# treated `.git`, `.hg` and `.svn` as equals since the beginning — so `find_root` calls a Mercurial
# or Subversion checkout a repository and the walker calls its internal store ordinary source. An
# `.svn/pristine` tree is every file in the working copy a second time (R21 agent 5).
VCS_DIRS = (".git", ".hg", ".svn")
PRUNE_DIRS = {"node_modules", "vendor", "__pycache__", ".venv", *VCS_DIRS}

_CACHE = {}


def _walk(root):
    """(file_rels, git_rels) — paths RELATIVE to root, from a single pruned traversal.

    Relative on purpose. Callers do `path.relative_to(root)` with whatever form of the root they
    were given, and `relative_to` raises ValueError when the two forms differ — an unresolved root
    against a resolved path, a symlinked path against its real one. Every caller here treats that
    exception as "skip this file", so returning resolved absolutes silently dropped files instead
    of failing: measured on this repository as 1,145 -> 1,133 in the stored-material section, with
    nothing reported. Storing relatives and re-joining onto the caller's own root cannot drift.

    `.git` is inside SKIP_DIRS and must never be descended into, but mapper needs to know WHERE the
    .git directories are to spot a checkout inside this checkout. os.walk hands us `dirnames`
    before the prune, so both facts come out of the same pass.
    """
    base = Path(root)
    # Resolved ONCE. It is constant for the whole walk and was being re-resolved per
    # file, alongside a `full.resolve()` on every file whether or not that file was a
    # link. The guard below reads as "resolve only when linked" -- the short-circuit is
    # right there in the `if` -- but both resolves sat above it, so it never applied.
    # Isolated on 6,000 files: bare os.walk 0.048s, this loop 0.907s, this loop with both
    # fixes 0.151s. The SessionStart hook, which fires up to 82 times a session, went
    # 2.121s -> 1.244s at 6,000 files and 3.566s -> 1.897s at 20,000, output byte-identical.
    _base_resolved = base.resolve()
    files, gits = [], []
    # 🐛 os.walk defaults to onerror=None, which means IGNORE SILENTLY. A directory chamnan could
    # not read was indistinguishable from one that is not there: chmod 000 on a subtree holding 5
    # of a repository's 6 source files produced "1 source file(s)" and a green
    # "described 1/1 files (100%)". Root-owned directories left by a Docker bind mount or a CI
    # checkout are the ordinary way this happens, and the session-start hook's own comment names
    # that exact scenario as the reason its guard exists.
    #
    # Collected, never raised: every scanner shares this one walk and a session must still start.
    #
    # 🐛 [2026-09-08] This used to `UNREADABLE.clear()` here, on every walk. Every sibling in the
    # family -- `mapper.SKIPPED_TOO_LARGE`, `SKIPPED_BINARY`, all of them -- accumulates for the RUN
    # and is reset once by `mapper.reset_skips()`, and `bin/chamnan-map` reads all of them together
    # at the end as if they had the same lifetime. They did not: a map build walks more than once,
    # so the second walk wiped the first walk's record and the line that prints it
    # ("COULD NOT BE READ, so the counts below exclude them") had almost nothing left to print, ever.
    # Reproduced by spying on `_walk`: two calls, the second starting with the first's two entries
    # and clearing them. One member of a set with a different lifetime from the rest, which is this
    # repository's most-repeated defect wearing a different hat.
    #
    # Reset with the others now. The direction is deliberate and the sibling comment already argues
    # it: over-reporting costs a reader a name they see twice, under-reporting costs them a file
    # that vanished from a report claiming to be complete.

    def _note(err):
        try:
            UNREADABLE.add(str(Path(err.filename).relative_to(base).as_posix()))
        except (ValueError, TypeError):
            pass

    for dirpath, dirnames, filenames in os.walk(base, topdown=True, followlinks=False,
                                                onerror=_note):
        here = Path(dirpath)
        rel_dir = here.relative_to(base)
        # A submodule and a `git worktree add` checkout both carry `.git` as a FILE holding
        # `gitdir: ...`, not as a directory -- so os.walk never puts it in dirnames and neither
        # was recognised as a nested checkout. Somebody else's code was then indexed as this
        # repository's own, which is the exact failure the nested-checkout exclusion exists to
        # prevent; it was closed for the directory case and left open for the two commonest ways
        # a checkout is actually nested.
        for _vcs in VCS_DIRS:
            if _vcs in dirnames or _vcs in filenames:
                gits.append(rel_dir / _vcs)
        # In place, and before descending: this is the whole point of the module.
        dirnames[:] = [d for d in dirnames if d not in PRUNE_DIRS]
        for name in filenames:
            # A symlink to a FILE is not covered by followlinks=False, which only stops recursion
            # into symlinked DIRECTORIES. The file link is still yielded, and read_text() follows it
            # transparently -- so a link named `leaked.py` pointing at something outside the
            # repository has its contents scanned, its leading comment copied verbatim into MAP.md,
            # and MAP.md is then `git add`ed by the pre-commit hook and committed.
            #
            # Reproduced before this guard existed: a link to a file holding a database DSN outside
            # the root was walked, read, and its docstring copied into the index. The redactor does
            # not help -- it gates on the LINK's own name and extension, so an innocuous `.py` link
            # passes, and it strips `key = "value"` lines rather than prose.
            #
            # A link that stays inside the repository is fine and is kept: that is an ordinary way to
            # arrange a tree. Only escapes are dropped.
            full = here / name
            try:
                # isjunction as well as is_symlink: a Windows directory junction carries a
                # different reparse tag and is_symlink() never reports it, which is why Python
                # 3.12 added a separate os.path.isjunction(). Without this the escape guard is
                # simply absent on the platform where the confusion is most likely.
                _linked = full.is_symlink() or (
                    hasattr(os.path, "isjunction") and os.path.isjunction(full))
                # Compared component by component, not as a string prefix. `startswith` says
                # `/x/app-secrets/prod_db.py` is inside `/x/app`, so a symlink from `app/src/` to
                # a SIBLING directory whose name merely begins with the repository's walked
                # straight through this guard -- and a plain-prose credential in that file reached
                # the Quick Index, which the pre-commit hook then commits. The guard was right
                # about what to check and wrong about how to check it.
                # `full.resolve()` only when the entry is actually a link -- which is what
                # the condition below always meant, and what the cost was hiding.
                if _linked:
                    _resolved = full.resolve()
                    if (_resolved.parts[:len(_base_resolved.parts)]
                            != _base_resolved.parts):
                        continue
            except (OSError, RuntimeError):
                # RuntimeError as well as OSError, and it is not defensive padding: a symlink loop
                # (`a -> b -> a`, or a link to itself) makes Path.resolve() raise
                # RuntimeError("Symlink loop from ..."), which this except never caught. That
                # escaped the walk, killed mapper.scan(), and with it every other section of
                # chamnan-map -- assets, catalogs, deploy and schema all share this walk.
                #
                # 🐛 [2026-09-09] Caught, and then dropped in SILENCE -- the one exit from this
                # walk that recorded nothing, while `_note` above records an unreadable DIRECTORY
                # and `mapper.indexable` records an unresolvable link it is handed. This branch
                # took the link away before `indexable` could ever see it, so on the Pythons that
                # raise here the accounting had nothing to account for: `chamnan-map` printed
                # "1/1 files (100%)" over a tree whose other two entries it had quietly refused.
                #
                # It read as a version difference and is not one. Python 3.13 rewrote
                # `Path.resolve()` onto `os.path.realpath(strict=False)`, which returns a path for
                # a symlink loop instead of raising; 3.8 through 3.12 raise RuntimeError. So the
                # SAME tree was reported honestly on 3.13 and silently truncated on every older
                # interpreter chamnan supports -- and the check that covers it passed on the
                # version the author happened to run.
                UNREADABLE.add(str((rel_dir / name).as_posix()))
                continue          # a broken, looping or unresolvable link is not indexable either
            files.append(rel_dir / name)
    files.sort()
    return files, gits


_DEPTH = 0


@contextmanager
def session():
    """Scope within which the walk is cached and shared. Outside one, every call walks fresh.

    🐛 The cache cannot be unconditional. A caller that scans, writes files, and scans again gets
    the first listing back for the second scan — which is not a hypothetical: chamnan's own suite
    creates `src/__init__.py` between two `mapper.scan()` calls and asserts the second one sees it.
    A stale index is the exact failure this project treats as worse than no index, so the default
    is correctness and the caching is opt-in, per operation, by the code that owns the operation.

    A fresh walk costs 0.04s on a 1,478-file repository, so the fallback is cheap; what is
    expensive is doing it nine times inside ONE map, which is what the session prevents.
    """
    global _DEPTH
    _DEPTH += 1
    try:
        yield
    finally:
        _DEPTH -= 1
        if _DEPTH == 0:
            _CACHE.clear()


def _entries(root):
    key = str(Path(root).resolve())
    if _DEPTH and key in _CACHE:
        return _CACHE[key]
    entries = _walk(root)
    if _DEPTH:
        _CACHE[key] = entries
    return entries


def rel_parts(path, root):
    """`path`'s components below `root`, or its own components when it is not below root.

    🐛 [2026-09-10] Written out byte for byte in `catalogs.py`, `deploy.py` and `schema.py`, which
    are the three modules that group files by where they sit. Every copy was correct — and the
    fallback is the interesting half: a path OUTSIDE the root keeps its own components rather than
    raising, so a caller grouping by directory still gets an answer for a file the root does not
    contain. Three modules each deciding that independently is three chances for one of them to
    decide it differently, and a grouping that silently changes shape for out-of-tree paths is the
    kind of thing nothing fails on (R1, the duplicate-body sweep).

    Lives here rather than in `workspace`: all three already import `tree`, so this costs no new
    dependency, and "which components of this path sit under that root" is what this module is for.
    """
    try:
        return Path(path).relative_to(root).parts
    except (ValueError, TypeError):
        return Path(path).parts


def files(root):
    """Every file under root that is not inside a skipped directory, sorted.

    Returned joined onto the root AS GIVEN, so `p.relative_to(root)` always works for the caller.
    """
    base = Path(root)
    return [base / rel for rel in _entries(root)[0]]


def vcs_dirs(root):
    """Every VCS_DIRS marker found, including inside otherwise-skipped trees — see _walk."""
    base = Path(root)
    return [base / rel for rel in _entries(root)[1]]


def by_suffix(root, *suffixes):
    """Files whose suffix matches, case-insensitively. Replaces `rglob('*.ext')`."""
    wanted = {s.lower() if s.startswith(".") else "." + s.lower() for s in suffixes}
    return [p for p in files(root) if p.suffix.lower() in wanted]


# \U0001f41b [2026-09-09] `fnmatch.fnmatch` normalises case with `os.path.normcase`, which folds on
# Windows and does not on macOS or Linux. git decides the same question with `core.ignorecase`, and
# the two disagree on this machine's own defaults: `core.ignorecase` is TRUE here (the filesystem is
# case-insensitive) while `os.name` is posix, so `fnmatch` is case-SENSITIVE and every gitignore and
# gitattributes pattern chamnan evaluated diverged from what git itself would answer. On Windows it
# diverges the other way — `fnmatch` folds even where `core.ignorecase` is false.
#
# Three call sites had the identical gap: `mapper._is_generated`, `catalogs`' gitignore reader and
# `matching` below (R10 agent 1, findings 1 and 2). One matcher now, asking git rather than the
# platform, and `fnmatchcase` underneath so the fold is never applied behind our back.
_IGNORECASE = {}


def git_folds_case(root):
    """git's own `core.ignorecase` for the repository at `root`. Cached; False when git cannot say.

    The git call itself lives in `workspace.git_folds_case`, deferred-imported here. This module is
    stdlib-only on purpose and every `git -C` caller has to pass through the ownership guards that
    live beside git in `workspace` — asking a parent repository how IT folds case is the same class
    of error those guards exist to stop.

    False on any doubt, deliberately: case-sensitive matching is git's documented default, so an
    unreadable config degrades to the standard behaviour rather than to a guess.
    """
    key = str(root)
    if key in _IGNORECASE:
        return _IGNORECASE[key]
    try:
        import workspace as _ws
        verdict = _ws.git_folds_case(root)
    except ImportError:
        # ImportError alone, and NARROW on purpose. A bare `except Exception` here swallowed a
        # NameError from a missing import inside `workspace.git_folds_case` and answered False —
        # the safe-looking default, silently wrong, on every repository, with nothing to say so.
        #
        # Every way GIT can fail is already handled in the callee through `git_cannot_answer()`,
        # which is the one definition and is the only place that knows `NotImplementedError` is how
        # an environment with no process layer at all fails. Repeating a subset of that tuple here
        # would be a second, narrower opinion about the same question — exactly what that helper
        # exists to prevent. What is left for this handler is the one failure the callee cannot
        # report: a workspace imported without its siblings.
        verdict = False
    _IGNORECASE[key] = verdict
    return verdict


# git's gitignore glob is NOT `fnmatch`, and the two differ in exactly the ways that matter:
#
#   * `*` does not cross a `/`. `config/*.env` matches `config/local.env` and NOT
#     `config/nested/local.env` — `fnmatch` matched both, so chamnan skipped a file git would
#     happily commit, silently leaving it out of the index.
#   * `**` does cross.
#   * a pattern ending in `/` names a DIRECTORY, and everything inside it is ignored.
#     `secrets/` was rstripped to `secrets` and then matched nothing under it, so chamnan indexed
#     and warned about files git had been told to ignore.
#   * a pattern containing a `/` anywhere is anchored to the directory holding the `.gitignore`;
#     one without is matched against any path component at any depth.
#
# Verified against real `git check-ignore` in both directions rather than against a reading of the
# documentation (R3 agent 2 finding 8, re-filed as R10 agent 2 finding 8). This is the no-git
# fallback only — where git is present chamnan asks it — but that path is the one a repository
# without git, or a plain directory, actually takes.
_GITIGNORE_CACHE = {}


def gitignore_matches(rel, pattern, fold=False):
    """`rel` (posix, relative to the directory holding the `.gitignore`) against one pattern."""
    import re as _re
    key = (pattern, fold)
    rx = _GITIGNORE_CACHE.get(key)
    if rx is None:
        pat = pattern
        dir_only = pat.endswith("/")
        pat = pat.rstrip("/")
        # A LEADING slash means "anchored to this directory" and is not part of the path to match:
        # `/root_only.txt` ignores it at the top and not in `sub/`. Left in, the regex looked for a
        # path beginning with a slash and matched nothing at all.
        anchored = "/" in pat
        pat = pat[1:] if pat.startswith("/") else pat
        out, i = [], 0
        while i < len(pat):
            c = pat[i]
            if c == "*":
                if pat[i:i + 2] == "**":
                    # `a/**/b` matches `a/b` as well as `a/x/y/b` — `**` between slashes may stand
                    # for NO directory at all, which a bare `.*` cannot express because the slashes
                    # around it are still required. Consume the trailing slash with it.
                    if pat[i:i + 3] == "**/":
                        out.append("(?:.*/)?")
                        i += 3
                        continue
                    out.append(".*")
                    i += 2
                    continue
                out.append("[^/]*")
            elif c == "?":
                out.append("[^/]")
            elif c == "[":
                j = pat.index("]", i) + 1 if "]" in pat[i:] else i + 1
                out.append(pat[i:j])
                i = j
                continue
            else:
                out.append(_re.escape(c))
            i += 1
        body = "".join(out)
        # Anchored to the .gitignore's own directory when the pattern has a slash; otherwise it
        # matches a component at any depth, which is git's rule and the reason `*.log` works
        # everywhere without being written `**/*.log`.
        head = "" if anchored else "(?:.*/)?"
        tail = "(?:/.*)?$" if dir_only else "(?:/.*)?$"
        rx = _re.compile("^" + head + body + tail, _re.I if fold else 0)
        _GITIGNORE_CACHE[key] = rx
    return bool(rx.match(rel))


def glob_matches(name, pattern, fold=False):
    """`name` against a glob `pattern`, folding case only when the caller says git would.

    `fnmatchcase` rather than `fnmatch`: the latter decides for itself from `os.name`, which is the
    defect this exists to close.

    `fold` may be a callable, and callers should pass one. Asking git for `core.ignorecase` costs a
    subprocess, measured at ~50 ms on the first call for a root — and it is only ever needed in the
    narrow case where the two answers DIFFER: a case-sensitive match already succeeding needs no
    opinion about folding, and a name that does not match either way needs none either. So the
    question is asked last, and on this repository's own patterns it is almost never asked at all.
    """
    import fnmatch
    if fnmatch.fnmatchcase(name, pattern):
        return True
    if not fnmatch.fnmatchcase(name.lower(), pattern.lower()):
        return False
    return bool(fold() if callable(fold) else fold)


def matching(root, pattern):
    """Files matching a glob pattern. Replaces `rglob(pattern)`.

    A pattern with no separator is matched against the filename at any depth, which is what rglob
    did; one containing a separator is matched against the whole path relative to root.
    """
    base = Path(root)
    fold = lambda: git_folds_case(root)               # noqa: E731 -- asked only if it matters
    out = []
    for rel in _entries(root)[0]:
        target = str(rel) if "/" in pattern else rel.name
        if glob_matches(target, pattern, fold):
            out.append(base / rel)
    return out



# The old name for `vcs_dirs`, kept because it is what the one external caller and the suite say.
git_dirs = vcs_dirs


# The one size ceiling, and the module that has no imports of its own is where it belongs so that
# every walker can reach it. Two million bytes: past that a file is a bundle, a vendored tree, a
# fixture or a database dump, and reading it whole costs seconds and gains an index nothing.
#
# 🐛 [2026-09-08] This number was written out by hand in three places -- `mapper.MAX_FILE_BYTES`,
# `peek.ZIP_MEMBER_CEILING` (whose comment says "matching mapper.MAX_FILE_BYTES", which is a
# promise a comment cannot keep) and `peek.ROW_CAP` -- and NOT written at all in the two places
# that most needed it: `lib/catalogs.py` read every `.proto` and every API-spec file whole on every
# ordinary map build, and `peek.peek_source` read a whole source file with no bound while the
# `mapper` beside it refused anything over this size. A 150 MB file hung `chamnan-peek` for over
# 150 seconds (R7 agent 2, R8 agent 2).
MAX_FILE_BYTES = 2_000_000


def within_size(path, limit=MAX_FILE_BYTES):
    """True when `path` is small enough to read whole. False for a bundle or a dump.

    SKIP rather than truncate is the policy `mapper` set and this keeps: half a file parsed is an
    answer nobody can check, and `mapper` records what it skipped (`SKIPPED_TOO_LARGE`) so the
    coverage number degrades honestly instead of staying at 100% over a smaller set.

    A file that cannot be stat'd is treated as too large, because the alternative is reading it.
    """
    try:
        return path.stat().st_size <= limit
    except OSError:
        return False


def read_capped(path, limit=MAX_FILE_BYTES, encoding="utf-8-sig"):
    """At most `limit` bytes of `path`, decoded. For a PREVIEW, where truncation is the point.

    The other half of `within_size`, and the two are deliberately different answers to the same
    question: an INDEX skips a file it cannot read whole, because a partial index lies about what
    a file contains; a PREVIEW truncates, because a preview never claimed to be complete and its
    caller prints a truncation notice.

    Bounded on the way IN, not after reading: `path.read_text()[:limit]` has already spent the
    memory and the seconds this exists to save.
    """
    with open(path, "rb") as handle:
        return handle.read(limit).decode(encoding, errors="replace")
