"""Folding an oversized index down to one line per directory.

Lives in lib/ rather than in the hook because two places need the same answer: the hook, which does
the folding at session start, and chamnan-map, which has to tell the user what that will cost. A
separate estimate in the reporting path was wrong by 2.4x the first time it was tried — close enough
to look plausible, far enough to make the decision on bad numbers. One implementation, called twice.
"""
import tokens


def collapse(index, map_rel, budget=None):
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
    out = "\n".join(header + folded)
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
