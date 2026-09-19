"""STATE.md's injection: token-budgeted, and never silently dropping a pinned section.

Found on the live workspace this plugin is developed against: STATE.md was 12,998 characters and
the hook injected only `[:4000]`, with no marker saying so. 69% of the file disappeared every
session, including three headings the owner had written by hand specifically so a future session
would NOT re-propose settled work -- `### SETTLED — do not raise these again`,
`### Not this project — do not audit`. A memory system that discards the owner's own
do-not-repeat list is worse than having none, because the owner stops trusting that writing one does
anything.

Two independent fixes, not one:

  1. A visible truncation marker. Silent loss is the actual defect; the character count was
     secondary.
  2. Pinned sections. A heading may end with the marker below, which guarantees that section is
     injected in full, ahead of everything else, regardless of where in the file it sits. The owner
     should not have to win a race for the top 4,000 characters to keep a standing instruction
     visible -- they mark it once and it is never lost again.

Budgeted in tokens (see `tokens.py`), not characters: a flat character cap mis-prices any file that
is not mostly Latin script, and the whole point of a cap is to price correctly.

**And aged — which is not the contradiction it looks like.** `memory/` refuses age-based expiry on
principle (see lib/aging.py: a note about a version still in production is current however old it
is). STATE.md is the one file where the opposite holds, because of what it claims to be: *work in
flight*. A heading that says "fixed and committed tonight (do not redo)" was true for one night and
has been charged to every session since. Measured on the workspace this plugin is developed against,
2026-08-30: STATE.md was 2,367 tokens, 37.8% of the whole injection and 667 over its own budget,
and the largest single item in it was a list of one night's commits.

The clock is per SECTION and it resets whenever that section's text changes, so anything actually
being worked on never ages — being edited is the evidence. Three rules keep this from losing
somebody's work:

  * a pinned section (📌) is never aged out, whatever its date;
  * the file itself is never modified — this only decides what gets injected;
  * whatever is held back is named in one line that points at the file, so it is one read away
    rather than gone.

First-seen dates live in `.chamnan/logs/state-ages.json`, keyed by a hash of the section text. Two
things follow from that location and both are deliberate:

  * **It is not committed.** `logs/` is the one part of the workspace chamnan's README already tells
    people to ignore, so this needs no new instruction and adds nothing to anyone's diff. A file
    rewritten at every session start does not belong in a repository whose whole pitch is that its
    contents are worth reading in a commit.
  * **`prune_logs` can delete it, and that is a safe failure.** Its mtime is refreshed every session,
    so it survives normal use; a repository nobody opens for longer than `log_retention_days` loses
    it and every section reads as new again. That errs toward injecting, and after a week away it is
    arguably the right answer anyway.

It is bookkeeping, not knowledge. Every failure path here — missing file, unwritable workspace,
malformed JSON, an exception mid-walk — injects everything rather than nothing.
"""
import hashlib
import json
import re
import mdblock
import time

import md

PIN_MARK = "📌"

AGES_PATH = "logs/state-ages.json"

# `mdblock.HEADING_SPACE`, not `[ \t]`: a CJK keyboard types U+3000 after the hash and this
# pattern did not see it, so the section was absorbed into the one above — pin and all. The
# measurement and the other three spellings of this are in mdblock beside the definition.
_HEADING = re.compile(r"^(#{1,6})" + mdblock.HEADING_SPACE + r"+(.*?)"
                      + mdblock.HEADING_SPACE + r"*$", re.M)


def _heading_text(raw):
    """Heading text with a CommonMark closing sequence removed.

    `## Pinned 📌 ##` renders as "Pinned 📌" in every markdown viewer -- the trailing run of hashes
    is a closing sequence, not content (CommonMark examples 71 and 73). chamnan captured it as text,
    so `.endswith(PIN_MARK)` was False and the pin was silently ignored: the author sees a pin, the
    tool does not, and nothing says so.
    """
    return re.sub(r"[ \t]+#+[ \t]*$", "", raw).rstrip()


# How far into an entry a pin has to appear to count. A pin is a heading decoration -- it belongs on
# the title line or in the opening sentence -- and the stores that are not markdown-sectioned have
# no heading structure to hang it off, so they look at the head of the text instead of parsing it.
PIN_HEAD_CHARS = 400


def pinned(text):
    """True when the owner pinned this entry.

    One predicate for every store that CUTS. `_sections` above answers the same question for
    STATE.md, where a heading is the unit and `.endswith` is exact; everywhere else the unit is a
    whole file or a whole entry, and the question is whether the pin is at the top of it.

    This exists because the pin reached the stores one at a time. `state.py` has honoured 📌 since
    it was written and `fit._fit_lines` reserves pinned blocks before it fills anything else; the
    rules store got it on 2026-09-09; `memory.titles`, `milestones.recent_titles` and
    `timeline.open_titles` -- three listings that cut by recency exactly as the rules store did --
    did not, so an owner who pinned a decision, a milestone or a thread saw the mark ignored with
    nothing to say it had been. The convention now lives in one place so the fifth store to be
    written gets it by calling this rather than by remembering.
    """
    return PIN_MARK in (text or "")[:PIN_HEAD_CHARS]


def _sections(text):
    """Every heading in `text`: its level, whether it is pinned, and the span from the heading line
    through the next heading of the SAME OR HIGHER level (i.e. its full section, subsections
    included)."""
    heads = md.headings(_HEADING, text)
    out = []
    for i, m in enumerate(heads):
        level = len(m.group(1))
        pinned = _heading_text(m.group(2)).endswith(PIN_MARK)
        end = len(text)
        for nxt in heads[i + 1:]:
            if len(nxt.group(1)) <= level:
                end = nxt.start()
                break
        out.append({"start": m.start(), "end": end, "pinned": pinned, "level": level})
    return out


def split_pinned(text):
    """(pinned_text, unpinned_text). Pinned sections are concatenated in their original order;
    the same ranges are removed from `unpinned_text` so nothing is ever injected twice. A pin
    nested inside another pin is not extracted a second time -- only the outermost pin in a chain
    is pulled whole, subsections included."""
    claimed = []
    for s in _sections(text):
        if not s["pinned"]:
            continue
        if any(c[0] <= s["start"] < c[1] for c in claimed):
            continue
        claimed.append((s["start"], s["end"]))
    claimed.sort()

    pinned_text = "\n\n".join(text[a:b].strip() for a, b in claimed)

    parts, cursor = [], 0
    for a, b in claimed:
        parts.append(text[cursor:a])
        cursor = b
    parts.append(text[cursor:])
    unpinned_text = "".join(parts)

    return pinned_text, unpinned_text


def _human(n):
    if n < 1000:
        return str(n)
    return f"{n / 1000:.1f}k"


def _safe_cut(text, cut):
    """Move `cut` back to the end of the last complete line that is not inside a fence.

    A budget cut is a character index; markdown structure is not. Landing inside a ``` block left
    it unclosed and every later line of the injected block rendered as code.
    """
    # Moved to `mdblock.cut_outside_a_fence` on 2026-09-08, where `fenced_lines` lives and where
    # the other four callers that cut markdown by a budget can reach it. Kept as a name because
    # this module's comments refer to it and the indirection costs nothing.
    return mdblock.cut_outside_a_fence(text, cut)


def render(text, budget, path_for_marker):
    """(injected_text, marker) for STATE.md under a token budget.

    Pinned sections are never cut, in full, first. Whatever budget remains after them fills from
    the top of everything else, exactly as a plain head-cut would with no pins at all -- so a file
    with no pins behaves exactly as before, just token-priced instead of character-priced. `marker`
    is "" unless something from the UNPINNED pool was actually dropped; pins are never the reason
    for a marker, because pins are never dropped.
    """
    import tokens

    # 🐛 [2026-09-06] A committed, badly-resolved merge leaves `<<<<<<< HEAD` in STATE.md, and this
    # injected BOTH sides as settled fact — two contradictory 📌-pinned lines, inside the fence that
    # tells the reader the text comes from the repository, with nothing marking either as disputed.
    # The fix already existed one file away: `memory.unresolved_conflict()` guards rules against
    # exactly this and was never called from here, so the same rule was applied to one of two stores
    # (R9 agent 3, 2026-09-06). Its own docstring says why a rule in conflict is not a rule — a plan in conflict
    # is not a plan either, and the honest injection is that the file needs resolving.
    #
    # Said instead of the content, not beside it: the point is that neither side is trustworthy, and
    # printing them under a warning invites the reader to pick one, which is the failure.
    import memory
    if memory.unresolved_conflict(text):
        return ("**`STATE.md` is mid-merge and both sides are still in the file.** Nothing from it "
                "is injected this session, because neither side of an unresolved conflict is what "
                "this repository decided. Resolve the conflict markers and it comes back.", "")

    pinned_text, unpinned_text = split_pinned(text)
    pinned_cost = tokens.estimate(pinned_text)
    remaining = max(0, budget - pinned_cost)

    # 🐛 [2026-09-10] This took `unpinned_text[:cut]` — the START of the file — so the budget kept
    # whatever was written FIRST and dropped whatever was written LAST. New work is appended at the
    # end of this file, so the section the budget cut first was the one holding what is currently
    # open, while three 📌-pinned handoffs from a fortnight earlier survived every budget down to
    # 150 tokens. Measured on the real file: at 600 tokens the only section dropped was
    # `→ 1.25: the research queue`, which is where "Open, end of 2026-09-10" lives.
    #
    # The owner's framing, and it is the right one: a stage grows as real work accumulates, and
    # there is no reason to carry all of it every time — carry the LATEST, and name the rest so a
    # session can go and get one when a command actually calls for it.
    #
    # Selection by recency; presentation in file order. The two are separate on purpose: choosing
    # newest-first is what makes the survivor the useful one, and emitting them in the order the
    # file writes them is what keeps the block readable — a block whose sections arrive in reverse
    # reads as though something is wrong with it.
    # 🐛 [2026-09-10] "the outermost sections" was `_sections` minus anything contained in another,
    # and on this file that is ONE unit: `# Work in flight` is a level-1 title wrapping every `##`
    # item under it, so the selection had exactly one thing to choose from and did nothing at all.
    # The suite caught it, on a fixture with the same shape.
    #
    # The unit is the shallowest level that has more than one section — a document TITLE is not a
    # stage entry, and a file with one heading has nothing to choose between either way.
    _units = [s for s in _sections(unpinned_text) if not s["pinned"]]
    _by_level = {}
    for _s in _units:
        _by_level.setdefault(_s["level"], []).append(_s)
    _tops = []
    for _lvl in sorted(_by_level):
        if len(_by_level[_lvl]) > 1:
            _tops = _by_level[_lvl]
            break
    if _tops:
        _keep, _spent = [], 0
        for _s in reversed(_tops):                 # newest last in the file, so newest first here
            _chunk = unpinned_text[_s["start"]:_s["end"]]
            _cost = tokens.estimate(_chunk)
            if _spent + _cost > remaining and _keep:
                break                              # room is gone; the rest is named in the marker
            _keep.append(_s)
            _spent += _cost
        _keep.sort(key=lambda s: s["start"])
        _kept_at = {s["start"] for s in _keep}
        _lost_heads = [_heading_text(md.headings(_HEADING, unpinned_text[s["start"]:s["end"]])[0]
                                     .group(2)).strip()
                       for s in _tops if s["start"] not in _kept_at]
        # Anything before the first heading belongs to no section and is kept whole: it is the
        # file's own opening line, and `fit.reorder` already relies on a lead line staying put.
        _lead = unpinned_text[:_tops[0]["start"]]
        head = _lead + "".join(unpinned_text[s["start"]:s["end"]] for s in _keep)
        head = _safe_cut_text(head, remaining)
        dropped_chars = len(unpinned_text) - len(head)
    else:
        cut = tokens.cut_at(unpinned_text, remaining)
        # Backed up to a line boundary outside any fence. cut_at counts characters, so the cut
        # landed wherever the budget ran out -- mid-word, and worse, inside a ``` block, which left
        # the fence open. Everything after it in the injected block then rendered as code,
        # including the drop marker and any section that followed.
        cut = _safe_cut(unpinned_text, cut)
        head = unpinned_text[:cut]
        dropped_chars = len(unpinned_text) - cut
        _lost_heads = [_heading_text(m.group(2)).strip()
                       for m in md.headings(_HEADING, unpinned_text) if m.start() >= cut]

    parts = [p for p in (pinned_text.strip(), head.strip()) if p]
    injected = "\n\n".join(parts).strip()

    marker = ""
    if dropped_chars > 0:
        # 🐛 [2026-09-10] This said only "…9.3k more". A number is not a reason to go and read; a
        # list of what is MISSING is. The rules section already names every rule it could not show
        # and delivered measurably better for it — 3 of 10 arriving with a body became 5 of 10 when
        # its pointer stopped wasting bytes on repetition — and this is the same shape one store
        # over, which is the defect this repository records more than any other. The headings are
        # free here: the cut is an offset into `unpinned_text`, so what fell past it is already in
        # hand (R1 finding, `state_outgrows_its_budget_unnoticed`, item 2).
        #
        # Titles only, and at most four. The point is to make the reader decide whether to open the
        # file, not to smuggle the section back in past its own budget.
        _lost = [h for h in _lost_heads if h]
        _shown = _lost[:4]
        if _shown:
            _names = ", ".join(f"**{h}**" for h in _shown)
            # The ellipsis counts what was LOST, not what exists. Comparing against every heading in
            # the file made it appear whenever anything survived the cut, which says "there is more
            # than this" about a list that is already complete -- the small dishonesty that teaches
            # a reader the line is decorative.
            _more = "…" if len(_lost) > len(_shown) else ""
            marker = (f"_…{_human(dropped_chars)} more, not shown: {_names}{_more} — "
                      f"read `{path_for_marker}`_")
        else:
            marker = f"_…{_human(dropped_chars)} more — read `{path_for_marker}`_"
    # Pins are never cut, so a pinned block larger than the whole budget is delivered in full and
    # the block is over budget by however much it exceeds it. That is the right behaviour -- the
    # point of a pin is that it survives -- but the marker used to describe only the unpinned
    # overflow, so a 4,639-token injection under a 50-token budget reported "…39 more". Saying so
    # is the difference between a deliberate overrun and a silent one.
    if pinned_cost > budget:
        over = f"_pinned sections alone are {pinned_cost:,.0f} tokens against a {budget:,} budget; "
        over += f"they are never cut — see `{path_for_marker}`_"
        marker = f"{marker}\n{over}" if marker else over

    return injected, marker


def _safe_cut_text(text, budget):
    """`text` trimmed to `budget` tokens on a fence-safe line boundary, or unchanged when it fits.

    The section-selection path above assembles whole sections and can still land over budget when a
    single section is larger than the room — the same case `_safe_cut` exists for, applied to an
    assembled body rather than to the file.
    """
    import tokens                       # local, like `render`'s own import — see the note there
    if tokens.estimate(text) <= budget:
        return text
    return text[:_safe_cut(text, tokens.cut_at(text, budget))]


def _age_units(text):
    """The spans aged independently: a heading together with its OWN prose, not with its
    subsections.

    Found before release, on a real STATE.md: claiming outermost sections the way `split_pinned`
    does made this file two units, because it happens to have two `#` headings. Two consequences,
    both bad and both silent. Any edit anywhere reset a third of the file, so nothing would ever
    have aged; and a `#` block that is not itself pinned would have been dropped whole, **taking the
    📌 subsections inside it with it** — discarding the owner's own do-not-raise-again lists, which
    is the exact failure lib/state.py was written to fix in the first place.

    So the unit is a heading plus the text before its first subheading, and anything at or inside a
    pinned heading is not a unit at all: it is exempt, at any depth.
    """
    # md.headings, not a raw finditer -- the same fence-blindness that tore a pinned block in half
    # in 1.10.0, still live in this function because the fix was applied to _sections() and not
    # ported to its sibling. A `#` comment inside a bash fence became a unit boundary here, which
    # split a pinned section's aging span so the half after the fence aged out on its own.
    heads = md.headings(_HEADING, text)
    units, pinned_until = [], None
    for i, m in enumerate(heads):
        level = len(m.group(1))
        if pinned_until is not None and m.start() < pinned_until:
            continue                      # inside a pin — exempt, subsections included
        if _heading_text(m.group(2)).endswith(PIN_MARK):
            pinned_until = len(text)
            for nxt in heads[i + 1:]:
                if len(nxt.group(1)) <= level:
                    pinned_until = nxt.start()
                    break
            continue
        # 🐛 The unit used to end at the NEXT HEADING OF ANY DEPTH, so a `##` whose body is
        # entirely `###` subsections had a one-line unit that never changed — it aged out on
        # schedule while its live children survived and slid up under whatever heading came before.
        # Reproduced: `## Do NOT touch — vendored, upstream owns it` was left standing over
        # `### src/cascade.py`, a file the same document calls safe to refactor. The session was
        # told the exact opposite of what the file says, and the marker reported only that two
        # sections were held back. A heading and the subsections under it age together or not at
        # all; that is what a section IS.
        # ...and it also stops at a PINNED heading of any depth, because a unit that spans a pin
        # cannot age without taking the pin with it. Extending units to cover their subsections
        # made `# Work in flight` span the whole document on the first try, so ageing the top
        # heading discarded the do-not-raise-again list underneath it.
        end = len(text)
        for nxt in heads[i + 1:]:
            if len(nxt.group(1)) <= level or _heading_text(nxt.group(2)).endswith(PIN_MARK):
                end = nxt.start()
                break
        units.append({"start": m.start(), "end": end})
    return units


def _key(chunk):
    """Identity of a section: its text with whitespace collapsed. Any real edit changes it, which
    is what resets the clock; reflowing a paragraph does not, which is what stops a cosmetic change
    from buying another two weeks."""
    return hashlib.sha1(" ".join(chunk.split()).encode("utf-8")).hexdigest()[:16]


def _load_ages(wsdir):
    try:
        data = json.loads((wsdir / AGES_PATH).read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_ages(wsdir, ages):
    """Best-effort and silent. A workspace on a read-only checkout must still start a session.

    🐛 `dest.with_suffix(".tmp")` is the SAME path for every process, so two sessions starting at
    once wrote `state-ages.tmp` on top of each other and then each replaced `state-ages.json` with
    whatever the file held at its own moment. The `os.replace` is atomic and was never the problem;
    the shared staging name is. `os.getpid()` makes it per-process, which is what the atomicity was
    assuming all along.
    """
    try:
        # The per-pid fix this docstring describes now lives in one place, so it cannot be right
        # here and missing three files away — which is exactly what happened. Imported inside the
        # function, which is this file's existing convention for reaching workspace.
        import workspace as ws_mod
        ws_mod.atomic_write_text(wsdir / AGES_PATH,
                                 json.dumps(ages, indent=1, sort_keys=True))
    except Exception:
        pass


def age_out(text, wsdir, days, now=None):
    """(kept_text, marker) — hold back sections whose text has not changed in `days` days.

    Called on the RAW file, before redaction: scrubbing rewrites substrings, and a section whose
    hash changed because a hostname in it was masked would look edited every single session and
    never age at all.

    `days <= 0` disables the whole pass. So does an unreadable or unwritable workspace, a file with
    no headings, and any exception on the way — every one of those errs toward injecting.
    """
    if not days or days <= 0 or not text.strip():
        return text, ""

    now = int(now if now is not None else time.time())
    cutoff = now - days * 86400

    try:
        sections = _age_units(text)
    except Exception:
        return text, ""
    if not sections:
        return text, ""

    # 🐛 Read, decide, write — with nothing holding the file across the three. Every session start
    # runs this, so two sessions opening together each read the ages file, each computed a fresh map
    # from their own view, and the second write erased the first. Forced-overlap measurement: 26 of
    # 40 concurrent updates lost, 65%.
    #
    # The write was already atomic, and CLAUDE.md's own note on the identical defect in the vector
    # index says why that was never enough: atomic alone does not stop a lost update, and a lock
    # alone does not stop a torn file. `ws.exclusive` is the same helper `tools_index` uses for the
    # same shape. It yields False rather than raising when the lock cannot be taken, and the block
    # still runs then — an ages file is a staleness hint, and refusing to start a session over one
    # would be a worse failure than the race it prevents.
    #
    # 🐛 [2026-09-07] "The block still runs then" was the deliberate choice above, and it was wrong
    # in a way that only shows under the contention it was reasoning about. `exclusive` yields
    # False, not an exception, when the lock cannot be taken inside LOCK_TIMEOUT — and the yielded
    # value was never inspected, so the full read-decide-write ran anyway, WHILE a legitimate
    # holder still had the lock. Reproduced: a holder taking the lock for 3.0s, `age_out` returning
    # after exactly 2.003s having rewritten the ages file inside the holder's window. Under real
    # contention two non-holders can then race EACH OTHER, which is the 26-of-40 loss the comment
    # above measures for the pre-lock code — gated on load rather than removed by the fix.
    #
    # Skipping the REWRITE is the harmless direction and this function's own docstring already
    # argues for it: every failure path here errs toward injecting, and an ages file one session
    # out of date holds a section back one session late. Losing another writer's ages does not
    # come back.
    import workspace as ws_mod
    with ws_mod.exclusive(wsdir / AGES_PATH) as held:
        return _age_out_locked(text, wsdir, sections, now, cutoff, days, save=held)


def _age_out_locked(text, wsdir, sections, now, cutoff, days, save=True):
    ages = _load_ages(wsdir)
    fresh_ages, drop = {}, []
    for sec in sections:
        chunk = text[sec["start"]:sec["end"]]
        k = _key(chunk)
        first_seen = ages.get(k, now)
        fresh_ages[k] = first_seen
        # A section first seen this run is never stale — which is also what an unreadable ages
        # file makes every section look like, and is why a lost ages file injects everything.
        # Pinned sections never reach here at all; _age_units does not emit them.
        if first_seen <= cutoff:
            # The heading comes off the chunk this loop already sliced. Carried here so the marker
            # can say WHICH section was held back -- see the note where the marker is built.
            head = chunk.lstrip().split("\n", 1)[0].lstrip("# ").strip()
            drop.append((sec["start"], sec["end"], now - first_seen, head))

    # `save` is False when the lock could not be taken. The ages this run computed are still used
    # to decide what to hold back — that decision is read-only and correct — they are just not
    # written over the holder's.
    if save:
        _save_ages(wsdir, fresh_ages)

    if not drop:
        return text, ""

    parts, cursor = [], 0
    for a, b, _, _ in drop:
        parts.append(text[cursor:a])
        cursor = b
    parts.append(text[cursor:])
    kept = "".join(parts)

    oldest = max(d for _, _, d, _ in drop) // 86400
    # 🐛 [2026-09-09] The marker gave a COUNT and an age and nothing else, while this module's own
    # docstring says what is held back "is named in one line that points at the file, so it is one
    # read away rather than gone". It pointed at STATE.md as a whole, which is the file the aging
    # exists to avoid re-reading. A reader given "1 section held back" has no basis for deciding
    # whether it matters right now, so the marker was either ignored or paid for with a full read —
    # both of which defeat it. The heading is the one fact that makes the pointer usable, and it
    # was in the slice the loop above already took (R5 agent2, 2026-09-09).
    names = [mdblock.one_line(h) for _, _, _, h in drop if h]
    shown = ", ".join(f"**{n}**" for n in names[:3])
    if len(names) > 3:
        shown += f", and {len(names) - 3} more"
    marker = (f"_{len(drop)} section(s) unchanged for {days}+ days (oldest {oldest}) held back"
              + (f" — {shown}" if shown else "")
              + f". Read them in the file, or mark a heading {PIN_MARK} to keep it._")
    return kept, marker
