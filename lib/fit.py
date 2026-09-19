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

import workspace as ws  # noqa: E402 -- `workspace` imports only stdlib, so this direction is cycle-free

# Default sits under the measured 10,000-byte cap with room for a host that counts the newline,
# a wrapper, or a slightly different boundary. Raising it to the cap exactly is how a margin gets
# spent by something outside this repository's control.
#
# 🐛 [2026-09-17] This used to be a literal `9000`, typed separately from `workspace.DEFAULT_CONFIG`
# and `workspace._UPPER_BOUND` -- both of which had already moved to 9,500 on 2026-09-14. Same
# defect as the config merge two sections up: one limit, kept as more than one number by hand.
# Derived now, so there is exactly one place this ceiling is ever typed.
CEILING = ws.DEFAULT_CONFIG["output_byte_ceiling"]

# ------------------------------------------------------------------ the floor under every store
# 🐛 [2026-09-15] Everything below used to be leftovers: sections were packed in full, dropped
# whole until the block fit, and whatever room happened to survive was offered to the best single
# casualty. A store therefore had no floor at all -- it got what nothing else wanted, which on a
# workspace of any size is nothing. Measured over 400 recorded firings here: tools and skills were
# delivered on 3.2% of them, decisions on 21.5%, and eleven firings of 400 dropped nothing at all.
#
# Tuning a budget by hand moved which store starved and never stopped one starving, because the
# quantity being tuned was the size of the CONTENT and the constraint is the size of the BLOCK. A
# repository that adds ten skills next month walks straight back into it.
#
# So a share of the ceiling is RESERVED before anything is packed, and spent only on stores that
# would otherwise vanish, as names. What the reserve buys does not depend on how much is in a
# store: 29 skill names or 300, the slot is the same size and the list says how many did not fit.
# What is not needed is handed back -- a workspace whose stores all fit reserves nothing, so a
# small repository is bit-for-bit unaffected.
# 🐛 [2026-09-15] This was a share of the ceiling that I picked -- 0.28 -- which is the same
# mistake one level up from the one it was fixing. A hand-picked fraction is a number somebody has
# to come back and re-tune the next time a store grows, and coming back to re-tune is exactly what
# the owner has asked three times today to stop doing.
#
# Derived instead: the reserve is what the waiting stores actually ASK for -- one floor each,
# which scales with how many stores exist and not with how much is in them -- bounded by the room
# that is genuinely spare once the content nothing can drop has been paid for. Nothing is reserved
# when nothing has to be dropped, and never more than the briefs can use, so a workspace that fits
# is bit-for-bit unaffected and a workspace with twelve stores reserves twelve floors rather than
# whatever 28% happened to come to.

# Enough for a lead line, a fence, a heading and a few names. Below this a brief says less than
# `notice()` already does, so the room is better spent on the section above it.
BRIEF_FLOOR = 420

# One line's worth, reserved alongside the briefs and spent only when at least one section was
# reduced to names. Without it the line has nowhere to go on exactly the workspaces that need it:
# measured here, the block filled to 9,491 of 9,500 and the sentence saying five sections had
# arrived as names only could not fit in the nine bytes left. A message about what the budget cost
# has to be inside the budget, or it is a message that only prints when nobody needed it.
SHORT_NOTICE_FLOOR = 190

# First to drop, last to drop. A section is dropped only if everything before it in this list has
# already gone. Ranked by what the loss actually costs: how big the section is, and whether the
# reader can get it back from a file the block still names.
DROP_ORDER = [
    # \U0001f41b [2026-09-10] Tools sat at position 0 — dropped FIRST, delivered on 18% of real
    # firings — and it is the section that exists to stop somebody rewriting a script that already
    # exists. On the night this moved, three near-identical scratch scripts were written that were
    # already registered tools; chamnan's own repeat detector fired on each and the section that
    # would have named them was cut every time. One of the three, `archive_report.py`, writes the
    # marker without which an archived report becomes uncitable, and four reports went in without it.
    #
    # The evidence genuinely split, which is why this was not decided on that story alone. R7 agent 3
    # measured, over 2,226 recorded commands, that when this section DID arrive it corresponded to no
    # shift in which tool a session reached for — a real measurement against moving it. What changed
    # is its premise: it was taken when the index held 15 of 58 tools, so even a delivered section
    # listed mostly the wrong things. All 58 are registered now.
    #
    # Put independently to two other models with both sides stated; both answered move it, both
    # because the old measurement's premise is obsolete. Three of three with this session's own read.
    #
    # ONE swap rather than a re-rank, so the effect is measurable against the delivery figures
    # already on file. Milestones takes position 0: two dated one-line entries, and nothing in the
    # archive measures a session acting on one. The same judgement `rules_char_budget` reached an
    # hour earlier, where milestones also lost.
    "Recent milestones",
    "This repo's own tools — prefer these over writing a new script",
    "Recorded procedures",
    "Recorded decisions and lessons",
    "Where the last session stopped",
    "Open threads",
    "Reply style for this repo",
    # Emitted since 1.11.0 and never ranked, so it fell to the unlisted-section default and was
    # dropped ahead of everything but the index. It is the section that stops a wrong action being
    # proposed at all, which puts it above what is merely useful to know.
    "Environment constraints",
    # Was FIRST to drop, and the list above says it is ranked by "how big the section is, and
    # whether the reader can get it back from a file the block still names". Measured on this
    # repository the index is 794 bytes — the SMALLEST droppable section — so the rank contradicted
    # its own stated criterion, and recoverability does not separate it: every memory section here
    # is equally one grep away from a file the block names.
    #
    # What that cost: dropping the index did not bring the block under the ceiling, so `Work in
    # flight` went too, and dropping THAT alone would have sufficed. The index was spent for
    # nothing. Delivery fell from 100% on 2026-08-29 to 41% on 2026-09-02 across 126 real firings,
    # and the block measured while writing this carried none of it — while the README says
    # "Nothing is silently dropped".
    #
    # It sits here rather than at the very end on purpose. The hook fires 17 to 82 times a session
    # and most of those are resumes and compactions, not fresh starts: at that moment the model has
    # just lost the conversation, and the handoff is the section written for exactly that moment.
    # The index is one grep of a file the block still names. So it outranks the memory sections it
    # used to be sacrificed for, and yields to the handoff and the rules.
    "Architecture index",
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
    # 🎯 [2026-09-15] A bare line carrying the warning mark, sitting AHEAD of every heading, is the
    # most expensive line in the block: the prompt cache is prefix-based, so a notice that appears
    # the moment a file is written and disappears when the map is rebuilt invalidates everything
    # behind it, several times in an ordinary session. Measured at 4.4% of the block surviving a
    # mid-session file write, against 95.4% of its bytes being unchanged.
    #
    # Moved HERE rather than at each site that writes one. There are eleven of those and a twelfth
    # will be added by somebody who has not read this; ordering is a property of the emission, and
    # this function is where emission order is decided. A notice that FOLLOWS a section is left
    # alone — it is that section's footnote, it moves with it, and a section whose content changed
    # has already paid for the reprocess.
    lead, tail, blocks = [], [], []
    for part in parts:
        if title_of(part):
            blocks.append([part])
        elif blocks:
            blocks[-1].append(part)
        elif part.lstrip().startswith("_⚠"):
            tail.append(part)          # about the moment: after everything read from files
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
    return lead + [part for i in ordered for part in blocks[i]] + tail


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


def _oversize_note():
    """The refusal notice, as a function so `shrink` can MEASURE it instead of only appending it.

    🐛 It was built inline after the last `size()` call, so its ~250 bytes were outside every budget
    decision in the function. A block that fitted exactly then shipped over the ceiling — measured at
    9,398 bytes against 9,000 while restoring the architecture index, which is the host truncating
    the tail of a block this module exists to keep whole.
    """
    if not _oversize:
        return ""
    return ("\n_A dropped section could not be brought back: its pinned lines alone exceed the "
            "room left. Pins are never cut, so it stays out rather than push the block past "
            "the host's limit. Shorten a 📌 heading, or raise `output_byte_ceiling`._\n")


def _usage_of(sources, usage):
    """Which droppable positions belong to a store this workspace has been seen to open.

    `usage` is {store name: times opened}, as `pointer.opens_by_store()` counts it, and `sources`
    already maps a section title to the file it was read from -- so the store a section speaks for
    is the first segment of its source path under the workspace. Nothing new has to be threaded
    through the hook to join them.

    Returns {position index: count}, and an empty dict whenever there is no usage on record, which
    is the case on every fresh install and is why this cannot change behaviour there.
    """
    if not usage or not sources:
        return {}
    by_title = {}
    for title, src in sources.items():
        rel = str(src or "").replace("\\", "/")
        rel = rel.split(".chamnan/", 1)[-1]
        store = rel.split("/", 1)[0].replace(".md", "")
        if usage.get(store):
            by_title[title] = usage[store]
    return by_title


def shrink(header, parts, ceiling=CEILING, sources=None, absent=(), briefs=None,
           usage=None):
    """Return (body, dropped) with body at or under `ceiling` bytes where that is achievable.

    `sources` maps a section title to the file it was read from; the hook already records exactly
    that while building the block, so nothing new has to be threaded through to get it.

    `dropped` is a list of (title, source) for what was removed, so the caller can say so out loud
    instead of leaving the reader to trust a block that is quietly missing its middle.

    `absent` is the other half of that promise, and it was missing. A section the CALLER decided
    not to build never reaches this function, so it can be neither dropped nor reported here -- and
    the caller's own comment, "the drop notice says the same in a line", was false for exactly that
    path. Measured on this repository's `logs/block_shape.jsonl`: of 61 real startup firings in one
    day, 26 delivered the Architecture index, 1 named it in the notice, and 34 showed it in NEITHER
    -- the largest section in the block, gone with no trace anywhere, at 8,632-8,938 bytes against a
    9,000 ceiling, so nothing here had any reason to drop it (R7 agent 7, new finding 1). Titles
    passed in here are reported exactly as a drop is, and are counted in the size, because the
    notice line they add is bytes the block has to pay for like any other.
    """
    absent = [(t, (sources or {}).get(t, "")) if isinstance(t, str) else tuple(t) for t in absent]
    _oversize.clear()      # per call, not per process
    order = list(parts)          # the untouched originals, to trim from after the drops
    parts = list(parts)
    dropped = []
    if ceiling <= 0:
        return header + "".join(parts), absent + dropped

    # The notice is part of what gets emitted, so it has to be inside the measurement. Sizing the
    # body without it is how a block lands three lines over the limit and is truncated anyway.
    def size():
        return len((header + "".join(parts) + notice(absent + dropped, ceiling) + _oversize_note()).encode())

    # 🎯 [2026-09-15] `DROP_ORDER` is one global ranking, written once from what mattered on the
    # day it was written, and it decides what every workspace loses forever. Measured on this one:
    # of 11 recorded store opens, 8 were `skills/` and 3 were `memory/` -- and `skills` sits near
    # the cheap end of that list, so the store this repository actually reaches for is the store it
    # is told to lose first. The ranking is not wrong so much as blind: nothing in it can move.
    #
    # `usage` is what the workspace has been seen to open (`pointer.note_opened` has been recording
    # it all along and nothing read it). A store that has been opened is dropped AFTER every store
    # that has not; inside each group `DROP_ORDER` decides, unchanged. So a fresh install, where
    # every count is zero, behaves exactly as it does today, and a workspace earns its order by
    # using it rather than by somebody re-ranking a list.
    # 🐛 Scoped, and the first form was not. `pointer.note_opened` records opens of files INSIDE a
    # store directory -- `skills/x.md`, `memory/rules/y.md` -- and records nothing for `MAP.md` or
    # `STATE.md`, which sessions reach through a grep rather than by opening the file whole. Ranked
    # against each other on that evidence, the two most valuable sections in the block came last
    # and were both dropped: measured immediately, `Architecture index` and `Work in flight` left
    # the block the first time this ran. A store with no counter is not a store nobody uses; it is
    # a store this log cannot speak for, and treating the two as the same thing is the error a
    # reach measurement in this repository has already made once (AUDIT-6: 91% became 3% once the
    # question changed from "mentions it" to "opened it").
    #
    # So usage decides only among the sections the log CAN speak for -- the ones that register a
    # brief, which is the same set as the ones whose files live in a store directory. Every prose
    # section keeps its `DROP_ORDER` rank exactly.
    _by_title = _usage_of(sources, usage)
    droppable = sorted(
        ((_rank(p), i) for i, p in enumerate(parts) if _rank(p) is not None),
        key=lambda r: (r[0], r[1]),
    )
    # 🐛 The first form let a store with a counter outrank a section without one, and the two most
    # valuable sections in the block have no counter: `MAP.md` and `STATE.md` are reached by grep,
    # not by opening the file, so `note_opened` never sees them. `Architecture index` and `Work in
    # flight` were both dropped the first time this ran. A store with no counter is not a store
    # nobody uses — it is a store this log cannot speak for, and treating those as the same thing
    # is the error AUDIT-6 already made here once (91% "mentions it" against 3% "opened it").
    #
    # So usage permutes the briefed stores AMONG THEMSELVES and moves nothing else: the positions
    # those stores occupy in `DROP_ORDER` stay exactly where they are, and which store sits in
    # which of them is decided by what this workspace has been seen to open. The whole ranking is
    # unchanged on a fresh install, where every count is zero.
    _slots = [_n for _n, (_r, _i) in enumerate(droppable) if (briefs or {}).get(title_of(parts[_i]))]
    if _slots and _by_title:
        _held = [droppable[_n] for _n in _slots]
        # Least-opened first, so the store this workspace actually reaches for is dropped last.
        # `DROP_ORDER` breaks every tie, which is every pair on a workspace with no evidence.
        _held.sort(key=lambda r: (_by_title.get(title_of(parts[r[1]]), 0), r[0], r[1]))
        for _n, _row in zip(_slots, _held):
            droppable[_n] = _row

    # Held back BEFORE the packing, not offered after it. `target` is what the drop and restore
    # passes below are allowed to fill; the sweep at the end spends the difference on names for
    # whatever they had to leave out. Nothing is reserved when nothing has to be dropped, and never
    # more than the briefs can actually use, so a workspace that fits keeps every byte it has.
    reserve = 0
    if briefs and size() > ceiling:
        _want = sum(min(len((briefs.get(title_of(parts[i])) or "").encode()) or BRIEF_FLOOR,
                        BRIEF_FLOOR)
                    for _r, i in droppable if briefs.get(title_of(parts[i])))
        # What cannot be dropped has to be paid for first: the header, the untitled lines, and
        # every section `_rank` does not rank. Whatever is left after that is the only room a
        # reserve could ever come out of, so it is the bound -- no fraction, nothing to tune.
        _fixed = len((header + "".join(p for p in parts if _rank(p) is None)
                      + notice(absent, ceiling) + _oversize_note()).encode())
        reserve = max(0, min(_want + SHORT_NOTICE_FLOOR, ceiling - _fixed))
    target = ceiling - reserve
    # `dropped_at` shadows `dropped` position for position, so a restored section can be removed
    # from the report by WHICH ONE it was rather than by its title. Two sections can legitimately
    # share a title -- two `Recorded decisions and lessons` blocks, say -- and removing by title
    # took both entries out of the report while restoring only one of them. The other section was
    # then absent from the block, absent from `dropped`, and absent from the notice: gone with no
    # trace anywhere, which is precisely the "looks complete and is not" this module exists to stop.
    dropped_at = []
    for _, i in droppable:
        if size() <= target:
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
        used = len((header + "".join(parts) + notice(absent + dropped, ceiling) + _oversize_note()).encode())
        # `target`, not `ceiling`: a restored section is a FULL one, and letting it spend the
        # reserve is how the stores below it go back to receiving nothing. The reserve is for
        # names, and names are the form that fits in what is left of a saturated block.
        room = target - used
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
            # 🐛 Everything went through `_trim`, which always rebuilds the frame and always appends
            # "… cut to fit" — so a section SMALLER than the room available was still cut, and paid a
            # fence and a note for the privilege. Under `_trim`'s 300-byte floor the result was "",
            # and a section that fitted comfortably was left out entirely.
            #
            # Measured on this repository at the time: the Architecture index is 794 bytes. It was
            # rank 0 in DROP_ORDER then and went first — it is rank 8 of 11 today, moved on
            # 2026-09-10, and this sentence went on saying rank 0 until somebody quoted it as
            # current on 2026-09-15 and built a finding on top of it, dropping it did NOT bring the block under the ceiling —
            # `Work in flight` had to go as well, and dropping that alone would have sufficed — and
            # then the restore refused to put 794 bytes back into 1,300 bytes of room. Delivery of
            # the index fell from 100% on 2026-08-29 to 41% on 2026-09-02, measured over 126 real
            # firings, with the block written while fixing this carrying none of it.
            #
            # If it fits whole it goes back whole. Trimming is for what does not fit.
            _whole = order[i]
            if len(_whole.encode()) <= room_here:
                trimmed = _whole
            else:
                trimmed = _trim(_whole, room_here, sources)
                # 🐛 [2026-09-15] A section that does not fit and cannot be trimmed is left out
                # entirely, and two of them were left out EVERY TIME: `This repo's own tools` and
                # `Recorded procedures` were delivered **zero times in 400 recorded firings**, at
                # the 9,000 ceiling and at 9,500 alike. Both are lists, both cost about 1,386
                # bytes, and `_trim`'s 300-byte floor means the 200 bytes of room actually left
                # buys nothing at all.
                #
                # A section may now register a BRIEF: the same heading, one line, saying the store
                # exists, how much is in it and where. It is used only here, only when the full
                # form has already failed, so nothing that fits today gets smaller — which is the
                # trade the first attempt at this got wrong by compacting unconditionally and
                # taking the tool names away from every workspace small enough to have had them.
                #
                # This is the shape the owner asked for in as many words: do not preload what is
                # not needed, leave something that can be reached when it is.
                if briefs and (not trimmed or len(trimmed.encode()) > room_here):
                    _brief = briefs.get(title_of(_whole)) or ""
                    if _brief and len(_brief.encode()) <= room_here:
                        trimmed = _brief
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
                used = len((header + "".join(parts) + notice(absent + dropped, ceiling) + _oversize_note()).encode())
                room = target - used
                if room <= 0:
                    break
                continue

    # ------------------------------------------------- what is still dropped leaves its NAMES
    # 🐛 [2026-09-15] The restore pass above brings back ONE section -- the best that fits -- and
    # everything else dropped leaves nothing in the block but its title in the notice. Measured
    # over 400 recorded firings on this repository: `This repo's own tools` and `Recorded
    # procedures` were dropped on 96.8% of them, `Recorded decisions and lessons` on 78.5%, the
    # session handoff on 58.8%.
    #
    # Raising the ceiling does not touch those figures and was tried: 9,000 and 9,500 give the
    # same four casualties, because the material is three to four times the ceiling at either
    # value. A bigger budget cannot fix a FIXED GLOBAL DROP ORDER -- it only moves where the same
    # cut lands. A workspace whose skills are the point never receives its skills, on any session,
    # for as long as it stays that size. That is the defect, and it is the one the owner has
    # raised more times than any other in this file.
    #
    # So whatever room is left after the restore is spent on BRIEFS, most-valuable-first, for
    # every section still dropped rather than for one. A brief is names: what stops the next
    # session rewriting a tool that already exists is the name of the tool, and the prose around
    # it is the part that does not fit. Nothing that fits today gets smaller -- this runs only
    # over sections already removed, and only into room that was going to be wasted.
    briefed_at = []
    # Reserving the allowance is not enough on its own: the sweep and the upgrade below fill
    # whatever room they can see, and they saw this too. They fill to here instead, so the line
    # explaining what the budget cost is the one thing that cannot be crowded out by the budget.
    content_ceiling = ceiling - SHORT_NOTICE_FLOOR if briefs else ceiling
    if dropped and briefs:
        # SHARED, not first-come. Walking most-valuable-first and handing each one all the room
        # left is the same starvation one level down: the first brief takes the reserve and the
        # store below it is back to a title in the notice. Each waiting store gets an equal share,
        # and what a store does not use rolls forward to the next — so a small brief subsidises a
        # big one instead of being crowded out by it.
        _waiting = [i for _r, i in reversed(droppable)
                    if parts[i] == "" and i in dropped_at and briefs.get(title_of(order[i]))]
        for _n, i in enumerate(_waiting):
            room = content_ceiling - size()
            if room <= 0:
                break
            _left = len(_waiting) - _n
            # The last one in the queue is welcome to everything still unspent.
            _share = room if _left <= 1 else max(BRIEF_FLOOR, room // _left)
            # Its followers do NOT come back: a brief stands in for the section, and the material
            # that trailed the full form is exactly what there is no room for.
            _b = _fit_brief(briefs[title_of(order[i])], min(_share, room))
            if not _b:
                continue
            parts[i] = _b
            briefed_at.append(i)
            at = dropped_at.index(i)
            dropped.pop(at)
            dropped_at.pop(at)

    # ------------------------------------------------- and the reserve goes back if it was not used
    # The reserve is an upper bound, not a quota. What the briefs did not spend is real room, and
    # leaving it unspent is the same waste that made the restore pass refuse a 794-byte section
    # into 1,300 bytes of space -- measured here as blocks landing at 8,893 of 9,500 with sections
    # still in brief form. So the last pass walks the briefs most-valuable-first and puts back the
    # FULL section wherever it fits.
    #
    # This is the whole design in one line: every store gets its names first, and prose only out of
    # what is genuinely left over. Growing a store cannot starve its neighbour, because the
    # neighbour was served before the growth was measured.
    # Most-valuable-first, which is the order `droppable` gives when it is reversed.
    for i in [j for _r, j in reversed(droppable) if j in briefed_at]:
        _room_up = content_ceiling - size() + len(parts[i].encode())
        _foll_up = _followers(order, i)
        _room_up -= len("".join(order[j] for j in _foll_up).encode())
        if len(order[i].encode()) <= _room_up:
            parts[i] = order[i]
            for j in _foll_up:
                parts[j] = order[j]
            continue
        # The full form does not fit, but the room is still real: spend it on MORE NAMES in the
        # brief that is already there. Room left over as a number nobody can read is room wasted,
        # and a name list is the one form in the block that can absorb any amount of it.
        _longer = _fit_brief(briefs[title_of(order[i])],
                             content_ceiling - size() + len(parts[i].encode()))
        if _longer and len(_longer.encode()) > len(parts[i].encode()):
            parts[i] = _longer

    # What drove the budget, when it is something the reader can act on. `state.render` says so in
    # the section itself when pinned content alone exceeds its budget; joining that to the list of
    # casualties is what turns "the index is missing" into "unpin something and it comes back".
    cause = ""
    if (dropped or briefed_at) and any("pinned sections alone are" in part for part in parts):
        cause = ("Pinned sections in `.chamnan/STATE.md` are taking the budget — unpin one to get "
                 "these back.")
    # 🐛 [2026-09-15] Every section gained a brief, so nothing is dropped WHOLE any more — and the
    # line that says what the budget cost, and what to change to get it back, is written only from
    # the dropped list. A reader who has pinned more than the block can carry used to be told
    # "Pinned sections are taking the budget — unpin one"; after the briefs they were told nothing
    # at all, and the block simply looked thinner for no stated reason.
    #
    # A section reduced to its names is not a section that arrived. It is named here with the file
    # its full form is in, which is the same promise `notice()` makes for a dropped one.
    # 🐛 [2026-09-15] The first form of this was appended AFTER the body was assembled, so it was
    # never counted — the block went to 10,264 bytes against a 9,500 ceiling and straight past the
    # host's own cut, which is the single failure this module exists to prevent. It also spelled
    # each section's full TITLE, and a title here runs to seventy characters ("Environment
    # constraints — check these before proposing infrastructure work") while the thing the reader
    # actually needs is the path. Paths, and measured like everything else.
    _short = sorted({(sources or {}).get(title_of(order[i]), "") for i in briefed_at} - {""})
    _line = ""
    if _short:
        _named = ", ".join(f"`{_s}`" for _s in _short[:5])
        _more = f" +{len(_short) - 5}" if len(_short) > 5 else ""
        _line = (f"\n_{len(_short)} section(s) arrived as names only; the full text is in "
                 f"{_named}{_more}." + (" " + cause if cause else "") + "_\n")

    body = header + "".join(parts) + notice(absent + dropped, ceiling, cause)
    if _line and len((body + _line).encode()) <= ceiling:
        body += _line
    elif _line:
        # It did not fit whole. The count and the cause are the half a reader acts on; the paths
        # are recoverable from the sections themselves, which are all still here.
        _tiny = (f"\n_{len(_short)} section(s) arrived as names only."
                 + (" " + cause if cause else "") + "_\n")
        if len((body + _tiny).encode()) <= ceiling:
            body += _tiny
    if _oversize:
        body += _oversize_note()
    # Said out loud when it did not work. Undroppable content -- bare lines carrying no title, or
    # the header itself -- can exceed the ceiling on its own, and both loops above then run out of
    # moves and return anyway. `dropped` still names what it removed, which reads as "handled".
    # Meanwhile the host's own cut takes over at 10,000 bytes, positional and blind, which is the
    # single failure this module was written to prevent. A budget that fails open is not a budget.
    over = len(body.encode()) - ceiling
    if over > 0:
        # 🐛 [2026-09-09] This named `index_token_budget`, and that key cannot reach the section
        # the reader would be trying to shrink. It is consumed in exactly one place --
        # `tokens.section_budget` (`lib/tokens.py:232`), for the four OPTIONAL index subsections
        # (routes, env, schema, deploy) -- never for the Quick Index the block actually carries.
        # R1 measured it across 1,400 to 3,000 and the delivered index sat at 3,286 bytes at every
        # value: more than a 2x range, zero bytes of movement. So the one message a user reads at
        # the moment the block breaks sent them to a dial that is not connected to anything, and
        # `chamnan-map`'s own over-budget notice sent them to the same one.
        #
        # What is left when the block is over the ceiling is by definition undroppable: the header,
        # the untitled lines, and whatever `_fit_lines` reserved because it is pinned. Two things
        # act on that -- `state_token_budget`, which caps STATE.md and the rules block, and the
        # pins themselves.
        body += (f"\n_⚠ This block is {over:,} bytes over its {ceiling:,}-byte limit and could not "
                 f"be reduced further — what follows may be cut by the host. What is left is "
                 f"undroppable: lower `state_token_budget` in .chamnan/config.json, unpin a 📌 "
                 f"section in `.chamnan/STATE.md`, or raise `output_byte_ceiling` if your host "
                 f"allows more._\n")
    return body, absent + dropped


# A cut list always carries this, so it is paid for from the first name on rather than found to
# be unaffordable after the last one has been added.
_MORE_FMT = ", _+{} more_"


def _fit_brief(brief, room):
    """`brief` whole if it fits, else its name list cut at a name boundary. "" if it cannot.

    A brief is a section of the shape `_trim` takes apart, and it is already the short form: there
    is nothing left to summarise. What it usually is, though, is a lead sentence followed by a
    comma-separated list of NAMES -- the tools in the index, the skills on disk, the decisions on
    record -- and such a list can lose its tail without losing its point, because a name is useful
    one at a time. Twenty tool names is twenty scripts that do not get rewritten.

    A brief that is prose rather than a list is returned whole or not at all. Half a sentence is
    the mid-cut the fence exists to prevent, and `notice()` already names the file it came from.
    """
    if len(brief.encode()) <= room:
        return brief
    lines = brief.split("\n")
    if len(lines) < 5 or not lines[1].startswith("### "):
        return ""
    body = lines[3:-2]
    # The LAST line carrying a list, so a lead sentence above it survives the cut rather than
    # being the thing that gets shortened.
    at = next((i for i in range(len(body) - 1, -1, -1) if body[i].count(", ") >= 2), -1)
    if at < 0:
        return ""
    items = body[at].split(", ")
    frame = len(brief.encode()) - len(body[at].encode())
    worst = _MORE_FMT.format(len(items))
    kept = []
    for it in items:
        if frame + len((", ".join(kept + [it]) + worst).encode()) > room:
            break
        kept.append(it)
    left = len(items) - len(kept)
    # Fewer than three names says less than the notice does, and costs more to say it.
    if len(kept) < 3 or left <= 0:
        return ""
    body[at] = ", ".join(kept) + _MORE_FMT.format(left)
    return "\n".join(lines[:3] + body + lines[-2:])


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
    # 🐛 [2026-09-09] The 300-byte floor above was the only test of whether a fragment was worth
    # keeping, and it counts bytes rather than content. Measured on this repository at the live
    # 9,000-byte ceiling: the Architecture index arrived as 1,113 bytes containing the map title,
    # a file count, "do not read this in full", a grep recipe, a "cut to fit" note and a staleness
    # warning -- and zero directory lines. Every sentence delivered was chamnan telling the reader
    # to go somewhere else, which is what `notice()` already does in a tenth of the bytes.
    if _only_the_opening_block(lines[3:-2], body):
        return ""
    return f"\n{lines[1]}\n{open_mark}\n" + "\n".join(body) + f"\n{close_mark}\n{note}\n"


def _only_the_opening_block(full, kept):
    """True when the fragment kept nothing past the body's own opening block.

    A section whose first block introduces the ones beneath it loses all of what is introduced
    before it loses any of the introduction, because `_fit_lines` fills in document order and the
    introduction comes first. The Architecture index is the one that bites: its opening paragraph
    is a how-to-read for a Quick Index that the cut then removes entirely.

    The guard is deliberately narrow, and a threshold was tried here first and withdrawn. Scoring
    the fragment by what share of it came from the opening block put the real section's 1,600-byte
    cut at 50.3% -- the first room where actual directory lines arrive -- so any threshold near a
    half decided that case by rounding. "Kept nothing at all past the introduction" needs no
    tuning and is the state that was actually measured.

    The one-block case is left alone on purpose: a plain list or a single paragraph has no
    introduction to be reduced to, and refusing those would trade this bug for a worse one, a
    section that is nothing but content dropped for having no headings.
    """
    blocks = _blocks(full)
    if len(blocks) < 2:
        return False
    if _is_subsequence(kept, blocks[0]):
        return True
    # 🐛 [2026-09-09] The subsequence test above is exact, and it is exactly one shape. A cut
    # landing a few lines PAST block 0 -- far enough to carry the second block's heading and the
    # italic line under it, not far enough to carry one of its rows -- is not a subsequence of block
    # 0, so it was accepted and shipped. Reproduced by setting `CHAMNAN_CONTEXT_PROFILE` to a name
    # that does not exist: the warning that says so is ~190 bytes, the budgets it resolves to are
    # identical to the default, and that alone moved the delivered Architecture index from 1,378
    # bytes / 7 directory rows to 1,136 bytes / ZERO rows -- under a heading reading "## Quick
    # Index" and a line describing rows that were not there (R7 agent 7, 2026-09-09, new finding 2). A typo in
    # a config key the reader is invited to set cost them the section the warning was about.
    #
    # So the question is asked about content rather than about position: when the body has rows at
    # all, a fragment carrying none of them is framing, and `notice()` already says "this section
    # was cut" in a tenth of the bytes. A body that is genuinely prose has no rows to lose and
    # falls through to the subsequence test unchanged, which is what keeps the withdrawn threshold
    # from coming back in another form: the 1,600-byte cut this guard must NOT refuse is the first
    # room where real directory rows arrive, and it keeps them.
    return bool(_rows(full)) and not _rows(kept)


_ROW = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")


def _rows(lines):
    """The list items in `lines` -- what these sections are actually made of.

    Every section the block injects is a list under a heading: files, rules, tools, milestones,
    threads. The heading and the sentence under it describe the list; the list is the content. A
    fenced example is not counted, on the same reasoning as `_blocks`: a `- ` inside ``` is
    somebody's sample output, not a row of ours.
    """
    out, in_fence = [], False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if not in_fence and _ROW.match(line):
            out.append(line)
    return out


def _is_subsequence(small, big):
    """Whether `small` appears inside `big` in order. Both may repeat blank and list lines, so
    identity of the lines is not enough on its own and the walk has to be positional."""
    it = iter(big)
    return all(any(line == other for other in it) for line in small)


PIN = "\U0001F4CC"


def _blocks(lines):
    """Split a section body into heading-delimited blocks, blind to nothing.

    Pulled out of `_fit_lines` so the fill and `_only_the_opening_block` cannot disagree about
    where block 0 ends -- two copies of this walk is exactly the shape of bug this repository
    keeps finding: a rule applied to one member of a set and forgotten in the identical one
    beside it.
    """
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
    return blocks


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
    blocks = _blocks(lines)

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


def notice(dropped, ceiling=CEILING, cause=""):
    """One line naming what was left out and where to read it. Empty when nothing was dropped.

    🐛 `cause` exists because the notice named the casualties and never the reason. A STATE.md with
    twenty pinned sections consumes the budget — pinned content is deliberately never cut, which is
    the whole point of a pin — and the Architecture index is then dropped to fit. Measured on an
    eight-file fixture: twenty ordinary pinned threads, and the index goes.
    #
    # Nothing here is silent: the section is listed, with the file to read it in. But the two facts
    # sat in different places. The reader was told `.chamnan/MAP.md` had been left out, and
    # separately that pins are never cut, and nothing joined them — so the one action that would
    # get the index back, unpinning something, was not visible from either. The trade is right; not
    # saying what drives it is what was wrong (R3 agent 3).
    """
    if not dropped:
        return ""
    named = ", ".join(f"{t} (`{s}`)" if s else t for t, s in dropped)
    tail = f" {cause}" if cause else ""
    return (f"\n_Left out to stay under the {ceiling:,}-byte hook limit — read it if you need it: "
            f"{named}.{tail}_\n")
