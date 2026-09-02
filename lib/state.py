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
import os
import re
import mdblock
import time

import md

PIN_MARK = "📌"

AGES_PATH = "logs/state-ages.json"

_HEADING = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*$", re.M)


def _heading_text(raw):
    """Heading text with a CommonMark closing sequence removed.

    `## Pinned 📌 ##` renders as "Pinned 📌" in every markdown viewer -- the trailing run of hashes
    is a closing sequence, not content (CommonMark examples 71 and 73). chamnan captured it as text,
    so `.endswith(PIN_MARK)` was False and the pin was silently ignored: the author sees a pin, the
    tool does not, and nothing says so.
    """
    return re.sub(r"[ \t]+#+[ \t]*$", "", raw).rstrip()


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
        out.append({"start": m.start(), "end": end, "pinned": pinned})
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
    if cut >= len(text):
        return len(text)
    at, depth = 0, 0
    safe = 0
    for line, in_fence in mdblock.fenced_lines(text):
        nxt = at + len(line) + 1
        if nxt > cut:
            break
        at = nxt
        if not in_fence:
            safe = at
    return safe if safe else cut


def render(text, budget, path_for_marker):
    """(injected_text, marker) for STATE.md under a token budget.

    Pinned sections are never cut, in full, first. Whatever budget remains after them fills from
    the top of everything else, exactly as a plain head-cut would with no pins at all -- so a file
    with no pins behaves exactly as before, just token-priced instead of character-priced. `marker`
    is "" unless something from the UNPINNED pool was actually dropped; pins are never the reason
    for a marker, because pins are never dropped.
    """
    import tokens

    pinned_text, unpinned_text = split_pinned(text)
    pinned_cost = tokens.estimate(pinned_text)
    remaining = max(0, budget - pinned_cost)

    cut = tokens.cut_at(unpinned_text, remaining)
    # Backed up to a line boundary outside any fence. cut_at counts characters, so the cut landed
    # wherever the budget ran out -- mid-word, and worse, inside a ``` block, which left the fence
    # open. Everything after it in the injected block then rendered as code, including the drop
    # marker and any section that followed.
    cut = _safe_cut(unpinned_text, cut)
    head = unpinned_text[:cut]
    dropped_chars = len(unpinned_text) - cut

    parts = [p for p in (pinned_text.strip(), head.strip()) if p]
    injected = "\n\n".join(parts).strip()

    marker = ""
    if dropped_chars > 0:
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
        data = json.loads((wsdir / AGES_PATH).read_text(encoding="utf-8"))
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
        dest = wsdir / AGES_PATH
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".%d.tmp" % os.getpid())
        tmp.write_text(json.dumps(ages, indent=1, sort_keys=True), encoding="utf-8")
        tmp.replace(dest)
    except Exception:
        try:
            tmp.unlink()
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
    import workspace as ws_mod
    with ws_mod.exclusive(wsdir / AGES_PATH):
        return _age_out_locked(text, wsdir, sections, now, cutoff, days)


def _age_out_locked(text, wsdir, sections, now, cutoff, days):
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
            drop.append((sec["start"], sec["end"], now - first_seen))

    _save_ages(wsdir, fresh_ages)

    if not drop:
        return text, ""

    parts, cursor = [], 0
    for a, b, _ in drop:
        parts.append(text[cursor:a])
        cursor = b
    parts.append(text[cursor:])
    kept = "".join(parts)

    oldest = max(d for _, _, d in drop) // 86400
    marker = (f"_{len(drop)} section(s) unchanged for {days}+ days (oldest {oldest}) held back — "
              f"read the file, or mark a heading {PIN_MARK} to keep it._")
    return kept, marker
