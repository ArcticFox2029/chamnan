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
    # Emitted since 1.11.0 and never ranked, so it fell to the unlisted-section default and was
    # dropped ahead of everything but the index. It is the section that stops a wrong action being
    # proposed at all, which puts it above what is merely useful to know.
    "Environment constraints",
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
    # An unlisted section is a new one nobody has ranked yet. It used to be dropped SECOND, ahead
    # of everything but the index, and two shipped sections have always been unranked — including
    # "Repeated last session and never kept", whose source file the hook deletes as it emits it, so
    # the drop notice named a path that no longer existed. fit.py's own docstring justifies whole
    # section dropping precisely because "a section that is named and on disk is recoverable in one
    # grep"; there it was neither. Unknown value is not the same as no value, and it is not the same
    # as least value either: rank it in the middle, so it is dropped before what has been argued
    # for and after what has not.
    return len(DROP_ORDER) / 2.0


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


def _followers(order, i):
    """The bare lines after a section that belong to it -- the index's "Full detail lives in
    MAP.md" pointer, the staleness warning, the "more rules in ..." tail. `reorder` already treats
    these as one block with their heading; dropping did not, so a live block shipped
    "Full detail lives in .chamnan/MAP.md" while naming Architecture index in the same breath as a
    section it had left out. A pointer to a heading that is not there is worse than silence."""
    j, out = i + 1, []
    while j < len(order) and not title_of(order[j]):
        out.append(j)
        j += 1
    return out


# Filled when a restore is refused for being oversized; read once, at the end of shrink().
_oversize = []


def shrink(header, parts, ceiling=CEILING, sources=None):
    """Return (body, dropped) with body at or under `ceiling` bytes where that is achievable.

    `sources` maps a section title to the file it was read from; the hook already records exactly
    that while building the block, so nothing new has to be threaded through to get it.

    `dropped` is a list of (title, source) for what was removed, so the caller can say so out loud
    instead of leaving the reader to trust a block that is quietly missing its middle.
    """
    _oversize.clear()      # per call, not per process
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
    # `dropped_at` shadows `dropped` position for position, so a restored section can be removed
    # from the report by WHICH ONE it was rather than by its title. Two sections can legitimately
    # share a title -- two `Recorded decisions and lessons` blocks, say -- and removing by title
    # took both entries out of the report while restoring only one of them. The other section was
    # then absent from the block, absent from `dropped`, and absent from the notice: gone with no
    # trace anywhere, which is precisely the "looks complete and is not" this module exists to stop.
    dropped_at = []
    for _, i in droppable:
        if size() <= ceiling:
            break
        t = title_of(parts[i])
        dropped.append((t, (sources or {}).get(t, "")))
        dropped_at.append(i)
        parts[i] = ""
        for j in _followers(order, i):
            parts[j] = ""

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
            if i not in dropped_at:
                continue
            # The followers come back with it, so they have to be paid for out of the same room.
            foll = _followers(order, i)
            room_here = room - len("".join(order[j] for j in foll).encode())
            trimmed = _trim(order[i], room_here, sources)
            # 🐛 `_trim` is allowed to return MORE than the room it was given: `_fit_lines` reserves
            # every pinned line before it starts filling, and if the pins alone exceed the budget it
            # keeps them anyway — which is the promise the pin exists for. This branch accepted the
            # result on truthiness alone, so an oversized section came back and the whole block went
            # past the host's cap.
            #
            # Measured on this project's own repository: `_trim` was asked for 5,773 bytes and
            # returned 7,822 — larger than the section it was shrinking, with zero lines removed.
            # The block finished at 11,230 bytes against a 9,000 ceiling, the host kept the first
            # 2,048, and every session began with one rule cut mid-sentence and nothing else: no
            # index, no procedures, no decisions, no handoff. 81.8% of the block destroyed.
            #
            # Refused rather than clamped. Clamping means cutting pinned lines, which is exactly the
            # loss state.py was written to end — a 📌 heading is how the owner stops a session
            # re-raising settled work, and trimming it silently would trade a visible catastrophe
            # for an invisible one. A section left dropped is NAMED in the notice and is one grep
            # away; a host-truncated one is not named at all.
            if trimmed and len(trimmed.encode()) > room_here:
                head = (order[i].strip().splitlines() or ["?"])[0][:60]
                _oversize.append(head)
                trimmed = ""
            if trimmed:
                parts[i] = trimmed
                for j in foll:
                    parts[j] = order[j]
                at = dropped_at.index(i)
                dropped.pop(at)
                dropped_at.pop(at)
                # 🐛 `break` after the first restore. It was right while a refused restore could not
                # happen: whatever came back filled the room and there was nothing left to give.
                # Now that an oversized section is refused rather than accepted, the room it did not
                # take is real — measured on this repository, 5,308 of 9,000 bytes sat unused with
                # five sections still dropped. Recompute and keep going; the loop is already
                # ordered most-valuable-first, so it fills with the best of what is left.
                used = len((header + "".join(parts) + notice(dropped, ceiling)).encode())
                room = ceiling - used
                if room <= 0:
                    break
                continue

    body = header + "".join(parts) + notice(dropped, ceiling)
    if _oversize:
        body += ("\n_A dropped section could not be brought back: its pinned lines alone exceed the "
                 "room left. Pins are never cut, so it stays out rather than push the block past "
                 "the host's limit. Shorten a 📌 heading, or raise `output_byte_ceiling`._\n")
    # Said out loud when it did not work. Undroppable content -- bare lines carrying no title, or
    # the header itself -- can exceed the ceiling on its own, and both loops above then run out of
    # moves and return anyway. `dropped` still names what it removed, which reads as "handled".
    # Meanwhile the host's own cut takes over at 10,000 bytes, positional and blind, which is the
    # single failure this module was written to prevent. A budget that fails open is not a budget.
    over = len(body.encode()) - ceiling
    if over > 0:
        body += (f"\n_⚠ This block is {over:,} bytes over its {ceiling:,}-byte limit and could not "
                 f"be reduced further — what follows may be cut by the host. Lower "
                 f"`index_token_budget` in .chamnan/config.json, or raise `output_byte_ceiling` if "
                 f"your host allows more._\n")
    return body, dropped


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
    # 🐛 Fence-blind. Any line starting with `#` began a new block and got a depth, so a
    # `# rebuild the map` comment inside a ```bash block had depth 1, which is <= the pin's depth,
    # and ENDED the pinned span — dropping the two `##` subsections beneath it and leaving the
    # fence unclosed. The comment above says this function was written after exactly that shape of
    # bug; the fix tracked pin depth and never made the scan fence-aware, which is the whole reason
    # `lib/md.py` exists. `state.split_pinned` and this still disagreed about the same text.
    in_fence = False
    blocks, cur = [], []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
        elif line.startswith("#") and not in_fence and cur:
            blocks.append(cur)
            cur = []
        cur.append(line)
    if cur:
        blocks.append(cur)

    # Reserve whole pinned blocks first, then fill the remainder LINE by line. Filling by block
    # would make a section with no headings at all -- a plain list, a paragraph -- one indivisible
    # atom that either fits or vanishes, which trades this bug for a worse one.
    # A pin covers its SUBSECTIONS too, which is what state.split_pinned already means by it: a
    # pinned span runs to the next heading at the same depth or shallower, subsections included.
    # This function used to pin only a block whose own first line carried the marker, so the two
    # modules disagreed about the same text -- and the disagreement was silent and one-directional.
    # Reproduced: `# Settled — do not raise these again 📌` with two `##` subsections under it.
    # state.render returned marker == "", meaning nothing was held back, and _trim then dropped the
    # second subsection ("Do not re-add the retry wrapper — tried twice, both reverted") at every
    # room below 3,500 bytes. A line the owner pinned so it could never be lost, lost, under a
    # marker saying nothing had been.
    def _depth(line):
        return len(line) - len(line.lstrip("#"))

    n = 0
    pinned_lines, rest = set(), []
    pin_depth = None
    for b in blocks:
        head = b[0] if b else ""
        if head.startswith("#"):
            d = _depth(head)
            if pin_depth is not None and d <= pin_depth:
                pin_depth = None          # the pinned span ended here
            if PIN in head:
                pin_depth = d
        is_pin = pin_depth is not None
        for line in b:
            (pinned_lines.add(n) if is_pin else rest.append(n))
            n += 1
    flat = [line for b in blocks for line in b]
    size = lambda i: len(flat[i].encode()) + 1

    keep = set(pinned_lines)
    total = sum(size(i) for i in keep)
    # 🐛 `break`, not `continue`. One pasted traceback in the middle of a handoff discarded
    # everything after it — measured: `## Blockers` and its contents thrown away with 380 of 400
    # bytes still unused, under a marker that said only "cut to fit". The stated reason ("so what
    # is kept stays contiguous") did not hold anyway, because the pinned reservation above already
    # makes `keep` non-contiguous. Skip what does not fit and keep filling.
    for i in rest:
        if total + size(i) > budget:
            # A line that could not fit an EMPTY budget is an anomaly — a pasted traceback, a
            # base64 blob — and skipping it costs nothing that was going to be kept anyway.
            # A line that does not fit because the budget is now full is the ordinary end, and
            # stopping there keeps what survives contiguous. `break` for both discarded everything
            # after one long line: measured, `## Blockers` and its contents thrown away with 380 of
            # 400 bytes unused. `continue` for both turns the fill into cherry-picking short lines
            # from anywhere, which is a different kind of wrong and the suite already pinned it.
            if size(i) > budget:
                continue
            break
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
