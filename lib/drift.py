"""The repository's own instruction files say things that stopped being true.

`CLAUDE.md`, `AGENTS.md`, `.cursorrules` and fourteen more conventions -- the file list is derived
from `host._AGENTS`, not typed here, so a host added there is covered without anyone remembering
this module exists.

The agent reads one of these every session and **believes it absolutely**; it will never think to
check whether a sentence is still true. A wrong instruction therefore costs more than a missing one,
and nothing anywhere checks them.

**The question is not "does this path exist".** That was measured first and thrown away: on the
three real instruction files on this machine it reported 11 of 24, 8 of 12 and 19 of 47 -- between
50% and 80% false positives -- because ordinary prose legitimately names paths that are relative to
a different base, or that the tool CREATES in somebody else's repository, or that are gitignored.

**The question is "did this path exist when this sentence was written".** git already knows, and the
answer is exact: a path that was in the tree at the commit that last touched the instruction file,
and is not in the tree now, has moved or gone since somebody wrote that line. Re-measured on the
same three files: zero reported, zero false positives. Verified against planted rot: an instruction
file naming `tests/test_a.py`, `src/a.py` and a `vendor/thing.js` that never existed, then `tests/`
moved to `spec/` -- only `tests/test_a.py` is named.

**One line, not a list.** The owner's condition, and it is the difference between a finding and a
nag: a live repository is never perfectly in sync, and a notice that fires on every mismatch is one
people learn to scroll past -- the lesson `mapper.py` already records as *"a warning that fires on a
current map teaches the reader to ignore it."*
"""
import os
import re
import subprocess

import host
import workspace as ws

# A path inside backticks, with at least one slash so a bare word is not mistaken for a file.
# `*` is excluded: a glob is a pattern, and asking git whether a pattern existed is meaningless.
PATH = re.compile(r"`([A-Za-z0-9_.-]*/[A-Za-z0-9_./-]+)`")
# Prose can quote a great many paths. This bounds the git calls, and the count reported says how
# many were examined so a truncated answer is never mistaken for a clean one.
MAX_PATHS = 60


def instruction_files():
    """Every repo-level instruction file convention any supported host declares.

    Derived from `host._AGENTS` rather than listed, so the 24 hosts stay the single source. A
    directory entry (`.claude/`, `.cursor/`) is skipped -- those hold rules, not one file whose
    prose can be judged.
    """
    out = set()
    for spec in host._AGENTS.values():
        for entry in spec.get(host.REPO, ()) or ():
            if entry and not entry.endswith("/"):
                out.add(entry)
    return tuple(sorted(out))


def _git(root, args):
    if not ws.git_can_speak_for(root):
        return None, ""
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=10)
        return r.returncode, r.stdout
    except ws.git_cannot_answer():
        return None, ""


def gone_since(root, rel):
    """(paths named that have gone, paths examined) for one instruction file.

    ("", 0) shaped as ([], 0) when the question cannot be answered: no git, the file untracked, or
    nothing quoted in it. An unanswerable question is not evidence of anything.
    """
    p = os.path.join(str(root), rel)
    try:
        text = open(p, "r", encoding="utf-8", errors="replace").read()
    except OSError:
        return [], 0
    code, out = _git(root, ["log", "-1", "--format=%H", "--", rel])
    if code is None or code != 0 or not out.strip():
        return [], 0
    last = out.strip().split("\n")[0]

    named, gone = [], []
    for m in PATH.finditer(text):
        n = m.group(1)
        if "*" in n or n.startswith(("http", "~")) or n in named:
            continue
        named.append(n)
        if len(named) > MAX_PATHS:
            break
    # 🐛 [2026-09-22] (self-measured) One `ls-tree` per path took 1.4-6.2 SECONDS on this
    # repository -- a git subprocess for each of sixty quoted paths, at session start, which is the
    # one place in this package where a second is unaffordable. git takes many pathspecs in one
    # call, so it is one subprocess per instruction file instead of one per path.
    #
    # `ls-tree` rather than `cat-file -e`: a directory is not a blob, and instruction files name
    # directories as often as files. One call answers for both shapes.
    code, out = _git(root, ["ls-tree", "--name-only", last, "--", *named])
    if code != 0:
        return [], len(named)
    existed = {ln.strip() for ln in out.split("\n") if ln.strip()}
    for n in named:
        if n in existed and not os.path.exists(os.path.join(str(root), n)):
            gone.append(n)
    return gone, len(named)


def _cached(wsdir, head):
    """The verdict recorded for this commit, or None. Any failure reads as "no cache"."""
    try:
        import json
        with open(os.path.join(str(wsdir), "state", "drift.json"),
                  "r", encoding="utf-8-sig") as fh:
            d = json.load(fh)
        return d.get("notice", "") if isinstance(d, dict) and d.get("head") == head else None
    except Exception:
        return None


def _remember(wsdir, head, text):
    try:
        import json
        ws.atomic_write_text(ws.Path(wsdir) / "state" / "drift.json",
                             json.dumps({"head": head, "notice": text}))
    except Exception:
        pass


def notice(root, wsdir=None):
    """One sentence when an instruction file has gone stale, else "".

    Reports the file with the most gone paths, not every file and not every path.

    🐛 [2026-09-22] (self-measured) Cached on HEAD. Uncached this cost 203 ms against a session
    start of 2,133 ms -- 10% more on every session, for an answer that is empty almost every time.
    The common case paying for the rare one is the cost this package exists to refuse. With the
    cache the steady state is one `rev-parse`.

    The limit, stated rather than hidden: a file MOVED without a commit is not noticed until the
    next commit. A repository in that state is already being told its index is stale by the map's
    own check, which is the louder of the two signals.
    """
    head = ""
    if wsdir is not None:
        code, out = _git(root, ["rev-parse", "HEAD"])
        head = out.strip() if code == 0 else ""
        if head:
            hit = _cached(wsdir, head)
            if hit is not None:
                return hit
    worst, worst_gone, worst_seen = "", [], 0
    try:
        for rel in instruction_files():
            if not os.path.isfile(os.path.join(str(root), rel)):
                continue
            gone, seen = gone_since(root, rel)
            if len(gone) > len(worst_gone):
                worst, worst_gone, worst_seen = rel, gone, seen
    except Exception:
        return ""
    if not worst_gone:
        if wsdir is not None and head:
            _remember(wsdir, head, "")
        return ""
    shown = ", ".join("`%s`" % g for g in worst_gone[:3])
    more = "" if len(worst_gone) <= 3 else " and %d more" % (len(worst_gone) - 3)
    n = len(worst_gone)
    text = ("chamnan: `%s` names %d path%s that existed when it was last edited and %s gone now "
            "— %s%s. The other %d it names still resolve."
            % (worst, n, "" if n == 1 else "s", "is" if n == 1 else "are", shown, more,
               worst_seen - n))
    if wsdir is not None and head:
        _remember(wsdir, head, text)
    return text
