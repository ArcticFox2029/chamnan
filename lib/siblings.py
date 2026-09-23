"""This edit's text also lives in N other files — said before the cut, not after the bug.

ENFORCES: memory/rules/the-set-not-the-member.md

🎯 [owner] The most-recorded failure in this workspace: a fix lands on one member of a set and is
forgotten in the identical ones beside it. Eighteen instances were counted before this was written,
and every one looked the same afterwards — the changed file was right, the three beside it were
still wrong, and nothing failed, because each file is independently valid.

A rule cannot catch that: at the moment of the edit the other members are not on screen, which is
the whole reason they are missed. A search can, and it costs one pass over files that already
share this one's extension.

**What it does NOT do is decide.** Sometimes one member genuinely differs and the others must not
change. It names the siblings and stops; widening the cut is a judgement, and this package does
not make judgements.

Bounds, so an edit never waits on it: the needle must be long enough to mean something, only files
with the same suffix are read, each is read once with a cap on size, and the walk stops after a
fixed number of files. A guard that makes editing slow is a guard somebody turns off.
"""
import pathlib

MIN_NEEDLE = 12          # shorter than this and a match says nothing about intent
MAX_FILES = 300          # a bound, not a tuning knob: the walk stops here whatever is left
ENOUGH = 8               # once this many peers are in hand, widening buys noise, not coverage
WIDEN_STEPS = 3          # directory, parent, grandparent — "beside it", not "anywhere in the repo"
MAX_BYTES = 400_000      # one file's worth; anything larger is data, not a sibling
NAME_LIMIT = 3           # how many to name before saying "and N more"
_SKIP = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".mypy_cache"}


def _candidates(target, root):
    """Files that could plausibly be the same KIND of thing as `target`.

    🐛 [2026-09-23] The first version walked the whole repository and took 2.7 seconds on a real
    edit — for a notice, on every edit, which is a guard somebody switches off by lunchtime. It
    starts at the target's own directory and widens only while it has found too few to compare
    against, because the rule's own words are "the identical ones BESIDE it": a sibling three
    directories away is a different kind of question.
    """
    suffix = target.suffix
    if not suffix:
        return []
    out, seen = [], set()
    scope = target.parent
    for _ in range(WIDEN_STEPS):
        for path in sorted(scope.glob("*" + suffix)):
            if path == target or not path.is_file() or path in seen:
                continue
            seen.add(path)
            out.append(path)
        if len(out) >= ENOUGH or scope == root or root not in scope.parents:
            break
        scope = scope.parent
    return out[:MAX_FILES]


def also_in(needle, target, root):
    """Every sibling file containing `needle`. [] when the edit is genuinely local."""
    if not needle or len(needle.strip()) < MIN_NEEDLE or not root:
        return []
    try:
        target = pathlib.Path(target).resolve()
        root = pathlib.Path(root).resolve()
        target.relative_to(root)
    except Exception:              # noqa: BLE001 — outside the repo is boundary.py's business
        return []
    hits = []
    for path in _candidates(target, root):
        try:
            if path.stat().st_size > MAX_BYTES:
                continue
            if needle in path.read_text(encoding="utf-8", errors="replace"):
                hits.append(path)
        except OSError:
            continue
    return hits


def advice(tool, tool_input, root):
    """One notice, or "" — which is the answer for almost every edit."""
    if tool != "Edit" or not isinstance(tool_input, dict):
        return ""
    needle = tool_input.get("old_string") or ""
    target = tool_input.get("file_path") or ""
    if not target:
        return ""
    # 🐛 A replace_all edit is already the whole-set answer for THIS file, but says nothing about
    # the files beside it — so it is checked exactly like any other.
    hits = also_in(needle, target, root)
    if not hits:
        return ""
    names = [str(p.relative_to(pathlib.Path(root).resolve())) for p in hits[:NAME_LIMIT]]
    more = len(hits) - len(names)
    return ("chamnan: this exact text is also in %s%s. The most-recorded failure here is a fix "
            "landing on one member of a set and being forgotten in the identical ones beside it — "
            "check whether they need the same cut. Nothing is blocked."
            % (", ".join("`%s`" % n for n in names), f" and {more} more" if more else ""))
