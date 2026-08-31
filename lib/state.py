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
import time

import md

PIN_MARK = "📌"

AGES_PATH = "logs/state-ages.json"

_HEADING = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*$", re.M)


def _sections(text):
    """Every heading in `text`: its level, whether it is pinned, and the span from the heading line
    through the next heading of the SAME OR HIGHER level (i.e. its full section, subsections
    included)."""
    heads = md.headings(_HEADING, text)
    out = []
    for i, m in enumerate(heads):
        level = len(m.group(1))
        pinned = m.group(2).rstrip().endswith(PIN_MARK)
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
    head = unpinned_text[:cut]
    dropped_chars = len(unpinned_text) - cut

    parts = [p for p in (pinned_text.strip(), head.strip()) if p]
    injected = "\n\n".join(parts).strip()

    marker = ""
    if dropped_chars > 0:
        marker = f"_…{_human(dropped_chars)} more — read `{path_for_marker}`_"

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
    heads = list(_HEADING.finditer(text))
    units, pinned_until = [], None
    for i, m in enumerate(heads):
        level = len(m.group(1))
        if pinned_until is not None and m.start() < pinned_until:
            continue                      # inside a pin — exempt, subsections included
        if m.group(2).rstrip().endswith(PIN_MARK):
            pinned_until = len(text)
            for nxt in heads[i + 1:]:
                if len(nxt.group(1)) <= level:
                    pinned_until = nxt.start()
                    break
            continue
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        units.append({"start": m.start(), "end": end})
    return units


def _key(chunk):
    """Identity of a section: its text with whitespace collapsed. Any real edit changes it, which
    is what resets the clock; reflowing a paragraph does not, which is what stops a cosmetic change
    from buying another two weeks."""
    return hashlib.sha1(" ".join(chunk.split()).encode("utf-8")).hexdigest()[:16]


def _load_ages(wsdir):
    try:
        return json.loads((wsdir / AGES_PATH).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_ages(wsdir, ages):
    """Best-effort and silent. A workspace on a read-only checkout must still start a session."""
    try:
        dest = wsdir / AGES_PATH
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".tmp")
        tmp.write_text(json.dumps(ages, indent=1, sort_keys=True), encoding="utf-8")
        tmp.replace(dest)
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
