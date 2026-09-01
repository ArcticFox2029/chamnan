"""Keep the injected block inside the host's per-hook stdout cap.

Claude Code truncates a SessionStart hook's stdout above 10,000 bytes, replacing the block with its
first 2,048 bytes plus a pointer to a file on disk. Measured across 120 recorded injections here, 47
were truncated that way, each losing 80-86% of the payload.

The number was bracketed from evidence before it was looked up -- the largest delivery that arrived
whole was 9,690 bytes, the smallest that did not was 10,293 -- and then confirmed against upstream:
anthropics/claude-code #70460 ("SessionStart hook output silently truncated at 10KB -- model never
sees the missing content") and #44086 ("truncated to 2000 characters when 10,000 character limit
exceeded"). Reported from Claude Code v2.1.88; measured here on 2.1.251. Both issues note there is
no workaround, which is true from inside a hook's own output, and is why the only move left is not
to exceed the cap in the first place.

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


# Constraints first, data in the middle, the thing to act on last. Position inside a prompt is not
# cosmetic: mid-prompt rules are measured to lose 30-50% of their compliance, while content at the
# beginning is used correctly in about 73% of positionally-sensitive cases, and the final span before
# the user's turn is well attended. chamnan emitted the architecture index -- pure data -- in the
# primacy slot and put the repository's own rules in the middle, which is the worst available
# arrangement of the two.
#
# A second argument lands on the same order. If output_byte_ceiling is set to 0, the host's own cut
# takes over, and that cut is positional: it keeps the first 2,048 bytes. Whatever is emitted first
# is what survives the degraded case too.
#
# Reordering costs nothing. Anything not named here keeps its original position among the middle
# blocks, so a new section does not have to be added to this list to behave sensibly.
EMIT_ORDER = [
    "Rules this repository works under",
    "Reply style for this repo",
]
EMIT_LAST = [
    "Where the last session stopped",
    "Work in flight (from the last session)",
]


def reorder(parts):
    """Constraints to the front, the session handoff to the back, everything else left alone.

    Moves BLOCKS, not sections. A section is followed by bare lines that belong to it -- the index
    is followed by "Full detail lives in MAP.md", and by the staleness warning when there is one --
    and moving the heading away from its own footnotes would be worse than any ordering gain.
    """
    lead, blocks = [], []
    for part in parts:
        if title_of(part):
            blocks.append([part])
        elif blocks:
            blocks[-1].append(part)
        else:
            lead.append(part)          # framing, ledger line, skills line: always first

    def rank(block):
        title = title_of(block[0])
        for i, name in enumerate(EMIT_ORDER):
            if title.startswith(name):
                return (0, i)
        for i, name in enumerate(EMIT_LAST):
            if title.startswith(name):
                return (2, i)
        return (1, 0)

    ordered = sorted(range(len(blocks)), key=lambda i: (rank(blocks[i]), i))
    return lead + [part for i in ordered for part in blocks[i]]


def shrink(header, parts, ceiling=CEILING, sources=None):
    """Return (body, dropped) with body at or under `ceiling` bytes where that is achievable.

    `sources` maps a section title to the file it was read from; the hook already records exactly
    that while building the block, so nothing new has to be threaded through to get it.

    `dropped` is a list of (title, source) for what was removed, so the caller can say so out loud
    instead of leaving the reader to trust a block that is quietly missing its middle.
    """
    order = list(parts)          # the untouched originals, to trim from after the drops
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

    # Dropping whole sections can overshoot badly. A single section larger than the ceiling forces
    # every cheaper one out and then goes itself, and the block lands at a third of the limit with
    # its most valuable part missing -- observed exactly once, when STATE.md alone reached 11,000
    # bytes. So if there is real room left, the best thing that was dropped comes back trimmed.
    # Half a session handoff beats none of one, and the room was going to be wasted either way.
    if dropped:
        used = len((header + "".join(parts) + notice(dropped, ceiling)).encode())
        room = ceiling - used
        # Reversed: droppable is ordered cheapest-first for dropping, so the most valuable thing
        # that was dropped is at the END of it. Walking it forwards brings back the least valuable
        # section instead of the most — which is the opposite of the point, and is what this did
        # until a live run showed STATE.md dropped with 55% of the ceiling unused.
        for rank, i in reversed(droppable):
            if parts[i] != "":
                continue
            title = _dropped_title(dropped, i, order)
            if title is None:
                continue
            trimmed = _trim(order[i], room, sources)
            if trimmed:
                parts[i] = trimmed
                dropped = [d for d in dropped if d[0] != title]
                break

    return header + "".join(parts) + notice(dropped, ceiling), dropped


def _trim(part, room, sources):
    """A fenced section cut to `room` bytes, still closed, and saying it was cut. "" if pointless.

    A section is `\n### Title\n<open>\n<body>\n<close>\n`, and cutting it at a byte offset would
    leave the opening fence unterminated -- the reader could not then tell where repository text
    stopped and chamnan's own words began, which is the one thing the fence exists to say. So the
    frame is rebuilt around a shortened body instead.
    """
    lines = part.split("\n")
    if len(lines) < 5 or not lines[1].startswith("### "):
        return ""
    title, open_mark, close_mark = lines[1][4:], lines[2], lines[-2]
    src = (sources or {}).get(title, "")
    # OUTSIDE the closing marker, not inside it. The framing line tells the reader that everything
    # between the markers is text read from a file in this repository; chamnan's own note about
    # having cut it is not, and putting it inside quietly makes the fence's one claim untrue.
    note = f"_… cut to fit the hook limit; the rest is in `{src}`._" if src else "_… cut to fit._"
    frame = len(f"\n{lines[1]}\n{open_mark}\n\n{close_mark}\n{note}\n".encode())
    budget = room - frame
    # Under a few hundred bytes the surviving fragment says nothing the notice does not.
    if budget < 300:
        return ""
    body = _fit_lines(lines[3:-2], budget)
    if not body:
        return ""
    return f"\n{lines[1]}\n{open_mark}\n" + "\n".join(body) + f"\n{close_mark}\n{note}\n"


PIN = "\U0001F4CC"


def _fit_lines(lines, budget):
    """Fit `lines` into `budget` bytes, keeping every 📌 block whatever its position.

    Taking the head and dropping the tail is the cut this whole module exists to replace. Done here
    it reproduces the original bug one level down: `state.split_pinned` deliberately protects the
    headings someone marked 📌 -- "do not raise these again", "not this project" -- and a positional
    trim throws away whichever of them happened to sit late in the file. That is exactly what the
    host does at 10,000 bytes, and it is exactly as wrong at this scale.

    So pinned blocks are reserved first and unpinned lines fill what is left, with the original
    order restored at the end. If the pinned material alone exceeds the budget it is kept anyway and
    the section runs over: a pin is the owner saying this must not be cut, and silently cutting it
    would make the marker a lie. The over-budget case is visible in `--explain` rather than hidden.
    """
    blocks, cur = [], []
    for line in lines:
        if line.startswith("#") and cur:
            blocks.append(cur)
            cur = []
        cur.append(line)
    if cur:
        blocks.append(cur)

    # Reserve whole pinned blocks first, then fill the remainder LINE by line. Filling by block
    # would make a section with no headings at all -- a plain list, a paragraph -- one indivisible
    # atom that either fits or vanishes, which trades this bug for a worse one.
    n = 0
    pinned_lines, rest = set(), []
    for b in blocks:
        is_pin = bool(b) and PIN in b[0]
        for line in b:
            (pinned_lines.add(n) if is_pin else rest.append(n))
            n += 1
    flat = [line for b in blocks for line in b]
    size = lambda i: len(flat[i].encode()) + 1

    keep = set(pinned_lines)
    total = sum(size(i) for i in keep)
    for i in rest:
        if total + size(i) > budget:
            break               # stop at the first that does not fit, so what is kept stays contiguous
        keep.add(i)
        total += size(i)
    return [flat[i] for i in sorted(keep)]


def _dropped_title(dropped, i, order):
    t = title_of(order[i])
    return t if any(d[0] == t for d in dropped) else None


def notice(dropped, ceiling=CEILING):
    """One line naming what was left out and where to read it. Empty when nothing was dropped."""
    if not dropped:
        return ""
    named = ", ".join(f"{t} (`{s}`)" if s else t for t, s in dropped)
    return (f"\n_Left out to stay under the {ceiling:,}-byte hook limit — read it if you need it: "
            f"{named}._\n")
