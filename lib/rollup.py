"""Folding an oversized index down to one line per directory.

Lives in lib/ rather than in the hook because two places need the same answer: the hook, which does
the folding at session start, and chamnan-map, which has to tell the user what that will cost. A
separate estimate in the reporting path was wrong by 2.4x the first time it was tried — close enough
to look plausible, far enough to make the decision on bad numbers. One implementation, called twice.
"""


def collapse(index, map_rel):
    """Fold a too-large index down to one line per directory instead of cutting its tail off.

    Truncating at a byte offset drops whatever sorts last, so on a 196-file repo everything from
    roughly `s` onward vanishes from the session with no indication that a whole area of the code
    exists. The agent then greps for it, which is the cost this file is meant to remove.

    A directory roll-up keeps every part of the repo visible at lower resolution: the agent still
    learns that `2dspeak/` and `game/` are there and how big they are, and can read the full entry
    for one of them out of MAP.md. Coarse and complete beats detailed and arbitrarily half-missing.
    """
    header, rows = [], []
    for line in index.splitlines():
        (rows if line.startswith("- **`") else header).append(line)
    groups = {}
    for line in rows:
        path = line.split("`")[1]
        top = path.split("/")[0] if "/" in path else "(root)"
        groups.setdefault(top, []).append(path.split("/")[-1])
    folded = [f"_{len(rows)} files. Rolled up by directory to stay inside the session budget —"
              f" read `{map_rel}` for any one of them in full._", ""]
    for top, names in sorted(groups.items()):
        shown = ", ".join(f"`{n}`" for n in sorted(names)[:8])
        more = f" _+{len(names)-8} more_" if len(names) > 8 else ""
        folded.append(f"- **{top}/** ({len(names)}) — {shown}{more}")
    return "\n".join(header + folded)
