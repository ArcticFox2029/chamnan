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
"""
import re

PIN_MARK = "📌"

_HEADING = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*$", re.M)


def _sections(text):
    """Every heading in `text`: its level, whether it is pinned, and the span from the heading line
    through the next heading of the SAME OR HIGHER level (i.e. its full section, subsections
    included)."""
    heads = list(_HEADING.finditer(text))
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
