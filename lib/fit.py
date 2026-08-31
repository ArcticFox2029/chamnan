"""Keep the injected block inside the host's per-hook stdout cap.

Claude Code truncates a SessionStart hook's stdout above a cap measured at 10,000 bytes on this
host (largest delivery that arrived whole: 9,690 bytes; smallest that did not: 10,293). Over it,
the block is replaced by its first 2,048 bytes plus a pointer to a file on disk. Measured across
120 recorded injections, 47 were truncated that way, each losing 80-86% of the payload.

The damage is not proportional to the loss, because the cut is positional and the architecture
index is emitted first. In the worst case seen, the 2,048 bytes that survived were the tail of a
rolled-up directory listing, and everything after byte 2,048 was gone: the repository's rules, the
recorded decisions, the open threads, the session handoff, and every pinned heading -- including
several that exist precisely to stop the next session redoing settled work. `split_pinned()` had
correctly protected all of them; the host then dropped them anyway.

Nothing reports this at the time. The preview ends mid-sentence and reads like the whole block.

So the ceiling is enforced here, where the choice of what to lose can be made deliberately.
Sections are dropped whole and lowest-value first, and each drop is reported with the file it came
from -- because a section that is named and on disk is recoverable in one grep, and a section cut
in half mid-sentence is not recoverable at all. Dropping the index costs a grep of MAP.md, which
is the fallback the index itself already tells the reader to use; dropping the rules costs a
standing instruction being broken. That asymmetry is the whole drop order.
"""
import re

# Default sits under the measured 10,000-byte cap with room for a host that counts the newline,
# a wrapper, or a slightly different boundary. Raising it to the cap exactly is how a margin gets
# spent by something outside this repository's control.
CEILING = 9000

# First to drop, last to drop. A section is dropped only if everything before it in this list has
# already gone. Ranked by what the loss actually costs: how big the section is, and whether the
# reader can get it back from a file the block still names.
DROP_ORDER = [
    "Architecture index",
    "This repo's own tools — prefer these over writing a new script",
    "Recent milestones",
    "Recorded procedures",
    "Recorded decisions and lessons",
    "Where the last session stopped",
    "Open threads",
    "Reply style for this repo",
    "Work in flight (from the last session)",
    "Rules this repository works under",
]

_TITLE = re.compile(r"\A\n### ([^\n]+)\n")


def title_of(part):
    """The section heading a part carries, or "" for a bare line that is not a section.

    Anchored at the start on purpose: a fenced payload can contain its own `### ` headings --
    STATE.md routinely does -- and matching those would let a payload rename its own container.
    """
    m = _TITLE.match(part)
    return m.group(1) if m else ""


def _rank(part):
    t = title_of(part)
    if not t:
        return None
    for i, name in enumerate(DROP_ORDER):
        if t.startswith(name):
            return i
    # An unlisted section is a new one nobody has ranked yet. Drop it before anything explicitly
    # ranked as worth keeping, but after the index -- unknown value is not the same as no value.
    return 0.5


def shrink(header, parts, ceiling=CEILING, sources=None):
    """Return (body, dropped) with body at or under `ceiling` bytes where that is achievable.

    `sources` maps a section title to the file it was read from; the hook already records exactly
    that while building the block, so nothing new has to be threaded through to get it.

    `dropped` is a list of (title, source) for what was removed, so the caller can say so out loud
    instead of leaving the reader to trust a block that is quietly missing its middle.
    """
    parts = list(parts)
    dropped = []
    if ceiling <= 0:
        return header + "".join(parts), dropped

    # The notice is part of what gets emitted, so it has to be inside the measurement. Sizing the
    # body without it is how a block lands three lines over the limit and is truncated anyway.
    def size():
        return len((header + "".join(parts) + notice(dropped, ceiling)).encode())

    droppable = sorted(
        ((_rank(p), i) for i, p in enumerate(parts) if _rank(p) is not None),
        key=lambda r: (r[0], r[1]),
    )
    for _, i in droppable:
        if size() <= ceiling:
            break
        t = title_of(parts[i])
        dropped.append((t, (sources or {}).get(t, "")))
        parts[i] = ""

    return header + "".join(parts) + notice(dropped, ceiling), dropped


def notice(dropped, ceiling=CEILING):
    """One line naming what was left out and where to read it. Empty when nothing was dropped."""
    if not dropped:
        return ""
    named = ", ".join(f"{t} (`{s}`)" if s else t for t, s in dropped)
    return (f"\n_Left out to stay under the {ceiling:,}-byte hook limit — read it if you need it: "
            f"{named}._\n")
