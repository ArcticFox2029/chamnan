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

PRUNE_DIRS = {".git", "node_modules", "vendor", "__pycache__", ".venv"}

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
    UNREADABLE.clear()

    def _note(err):
        try:
            UNREADABLE.add(str(Path(err.filename).relative_to(base)))
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
        if ".git" in dirnames or ".git" in filenames:
            gits.append(rel_dir / ".git")
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


def files(root):
    """Every file under root that is not inside a skipped directory, sorted.

    Returned joined onto the root AS GIVEN, so `p.relative_to(root)` always works for the caller.
    """
    base = Path(root)
    return [base / rel for rel in _entries(root)[0]]


def git_dirs(root):
    """Every `.git` found, including inside otherwise-skipped trees — see _walk."""
    base = Path(root)
    return [base / rel for rel in _entries(root)[1]]


def by_suffix(root, *suffixes):
    """Files whose suffix matches, case-insensitively. Replaces `rglob('*.ext')`."""
    wanted = {s.lower() if s.startswith(".") else "." + s.lower() for s in suffixes}
    return [p for p in files(root) if p.suffix.lower() in wanted]


def matching(root, pattern):
    """Files matching a glob pattern. Replaces `rglob(pattern)`.

    A pattern with no separator is matched against the filename at any depth, which is what rglob
    did; one containing a separator is matched against the whole path relative to root.
    """
    import fnmatch
    base = Path(root)
    out = []
    for rel in _entries(root)[0]:
        target = str(rel) if "/" in pattern else rel.name
        if fnmatch.fnmatch(target, pattern):
            out.append(base / rel)
    return out

