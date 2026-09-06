"""Estimate token counts without a tokenizer, honestly enough to enforce a budget.

A single characters-per-token constant is only ever right for one language. Measured
against Claude's own accounting, English code runs about 2.5 characters per token
while Thai runs 1.2 and Chinese 0.96 -- so a flat 3.6 under-counted a Chinese index
by a factor of nearly four. That matters because this number is not decoration: it
decides how much of the architecture index gets injected at session start. A repo
whose summaries are not in English was silently blowing through the budget it set.

The weights below come from bench/calibrate_tokens.py, which measures real prompts
against the real API rather than guessing.

WHAT THIS MODULE DOES NOT DO, stated first because it used to be claimed here and was
not true: it does not always err toward over-counting. That was written as a design
principle and read back for a year as a measured property. It was never checked
against a real artefact -- the calibration corpus is seven short synthetic samples,
none of them an architecture index -- and when chamnan's own MAP.md was finally
measured it came back UNDER by 8.2%, and its symbol-dense Full Detail section by
18.1%. The safe direction was the one the module was wrong in, on the single file it
exists to budget.

What was missing was a term for punctuation. A path or a signature is a third
non-alphanumeric (`/`, `.`, `_`, `-`, `:`, backtick, `|`), each mostly a token of its
own, and pricing those at the same rate as letters is what produced the gap. Splitting
the old single divisor into letters, symbols and whitespace closes most of it without
moving prose, which has almost no symbols and so is barely touched.

Measured against the real API, on real artefacts as well as the synthetic corpus --
the left column is before that split, the right is after:

    chamnan's own MAP.md, Quick Index   -8.2%  ->  -1.5%
    ...its Full Detail section         -18.1%  ->  -8.5%
    a real STATE.md                     +9.8%  -> +13.3%
    this repo's own Python             +14.3%  -> +16.9%
    JSON                               -11.8%  ->  -1.7%
    URLs                                -6.3%  ->  +3.1%
    english_code                        +3.1%  ->  +7.9%
    english_prose                      +36.2%  -> +34.1%
    russian                            +17.6%  -> +16.3%
    german                              -7.8%  ->  -9.0%
    thai / chinese / japanese                 unmoved

So the honest claim is narrower than the old one, and it is the claim the callers
should be read against: on the content chamnan actually budgets the error is now
within about 10% in either direction, where it used to reach 18% in the direction
that overruns. It is not a bound, and three shapes are still badly under-counted and
left that way on purpose because no caller budgets them: base64 and other
high-entropy blobs (-56%), emoji (-32%), and a long run of one repeated character,
which costs one real token per character where this module charges 0.4.

GERMAN is the one script under-estimated in the synthetic corpus, at -9.0%, and it is
left that way. One 1,266-character sample is not enough to move a constant every other
Latin-script repository depends on, and compounding is what makes German an outlier
rather than a correction -- the same effect shows up in long code identifiers, which
are under-counted by 16.6% for the same reason. The numbers are recorded here instead
of being tuned away, and the byte ceiling in lib/fit.py bounds what an error of this
size can actually cost: delivery is enforced in bytes, which no estimate touches.

ENGLISH PROSE is over-estimated by a third, because the letter divisor is fitted on a
corpus that is mostly code and index. That is the right bias for this module's main
caller, but it means a prose-heavy STATE.md is reported as costing more than it does
and can be rolled up earlier than it needs to be.
"""

# One token per character, roughly: Han, kana, Hangul, and CJK compatibility forms.
#
# The last two ranges are punctuation, and leaving them out was a real under-count rather than a
# rounding detail. CJK text is written with CJK punctuation -- the ideographic comma and full stop
# (0x3001, 0x3002) and the fullwidth comma (0xFF0C) -- and every one of them was falling through to
# the Latin divisor at 0.42 tokens where it costs about 1. That was 18 of 306 characters in the
# Chinese calibration sample and 18 of 480 in the Japanese one, which is most of the gap those two
# used to show.
from collections import Counter

_CJK = ((0x4E00, 0x9FFF), (0x3040, 0x30FF), (0x3400, 0x4DBF),
        (0xAC00, 0xD7AF), (0xF900, 0xFAFF), (0x2E80, 0x2FDF), (0x3100, 0x312F),
        (0x3000, 0x303F), (0xFF00, 0xFFEF))

# Abugidas, which tokenize almost as densely: Thai, Lao, Devanagari through Sinhala,
# and the Myanmar block.
_DENSE = ((0x0E00, 0x0EFF), (0x0900, 0x0DFF), (0x1000, 0x109F))

# Measured at 1.04 tokens per character on the Chinese sample once its punctuation was counted
# above; rounded up, because rounding down is the direction that overruns a budget. Japanese is
# genuinely lighter than Chinese (kana tokenize better than Han), so one weight cannot be tight for
# both and this one is set by the heavier.
_CJK_WEIGHT = 1.05
_DENSE_WEIGHT = 0.84
# Letters and digits only. One divisor for every non-CJK character could not be right for both
# prose and paths at once, and the direction it was wrong in was the unsafe one -- see the
# measurements in the docstring above.
_LATIN_DIVISOR = 2.43     # covers Latin, Cyrillic, Greek, Arabic, Hebrew, and code
# Punctuation and symbols, priced per character rather than by a divisor. `/`, `.`, `_`, `-`, `:`,
# backtick and `|` mostly tokenize alone or split the word beside them, which is why an index of
# paths and signatures costs far more per character than the prose the old single divisor was
# fitted on. This is the term that was missing.
_SYMBOL_WEIGHT = 0.68
# Whitespace is cheap but not free: runs fold, and a newline is usually absorbed by the token
# beside it. Fitted rather than assumed, because an indented index is a third whitespace.
_SPACE_WEIGHT = 0.38


def _in(o, ranges):
    return any(lo <= o <= hi for lo, hi in ranges)


def weight(ch):
    """Estimated tokens contributed by a single character."""
    o = ord(ch)
    if _in(o, _CJK):
        return _CJK_WEIGHT
    if _in(o, _DENSE):
        return _DENSE_WEIGHT
    if ch.isspace():
        return _SPACE_WEIGHT
    if not ch.isalnum():
        return _SYMBOL_WEIGHT
    return 1.0 / _LATIN_DIVISOR


# 🐛 The loop below used to run per CHARACTER, calling _in() — itself a generator over range
# tuples — twice each. Measured at 0.35 MB/s, and on apache/commons-lang (625 files, 8.5 MB) it was
# **44 of chamnan-map's 46 seconds of scan time: 96% of the command's runtime**, producing one
# headline number on line 2 of the output that no budget decision reads.
#
# Counter is the same arithmetic over DISTINCT characters instead of every character. Source is
# overwhelmingly ASCII, so a megabyte of Java collapses to ~100 keys and the classification runs
# ~100 times rather than a million. The weights are untouched: tokens.py's own docstring records
# that a single flat divisor was measurably wrong for CJK, which is why the weighted version
# exists, and a Japanese repository's headline would be off ~2.5× without it. Same inputs, same
# outputs, one classification per distinct character.
_WEIGHT_CACHE = {}


def estimate(text):
    """Estimated token count for a string, weighted by the scripts it contains."""
    if not text:
        return 0.0
    total = 0.0
    cache = _WEIGHT_CACHE
    for ch, n in Counter(text).items():
        w = cache.get(ch)
        if w is None:
            o = ord(ch)
            if _in(o, _CJK):
                w = _CJK_WEIGHT
            elif _in(o, _DENSE):
                w = _DENSE_WEIGHT
            elif ch.isspace():
                w = _SPACE_WEIGHT
            elif not ch.isalnum():
                w = _SYMBOL_WEIGHT
            else:
                w = 1.0 / _LATIN_DIVISOR
            # Bounded by the number of distinct characters a repository actually contains; a
            # polyglot tree with CJK, Thai and emoji is still a few thousand keys.
            if len(cache) < 20000:
                cache[ch] = w
        total += w * n
    return total


def cut_at(text, budget):
    """Index at which `text` reaches `budget` tokens, or len(text) if it never does.

    Slicing by characters would cut a Chinese document at four times its budget, which
    is the whole reason this module exists.
    """
    if budget <= 0:
        return 0
    running = 0.0
    for i, ch in enumerate(text):
        running += weight(ch)
        if running > budget:
            return i
    return len(text)


def fits(text, budget):
    """True when `text` is within `budget` tokens."""
    return estimate(text) <= budget


# 🐛 [2026-09-06] These two lived in `catalogs.py` as `_section_budget` / `_fill_by_budget`, and
# the module's own comment beside them names the failure they exist to stop: "count caps and
# mdblock.as_quoted's per-entry length cap bound quantity and size separately, and nothing bounds
# their product". `deploy.py` renders into the SAME budgeted index from the SAME two primitives --
# `MAX_PER_GROUP = 14` and `as_quoted(n, 80)` -- and never got the fix. Measured on eight kinds of
# twenty objects with 73-character names, the length a GitOps monorepo reaches once environment and
# region suffixes are on it: 4,059 tokens for the deployment section alone, against a default
# `index_token_budget` of 3,000, while the count cap reported nothing wrong (R10 acc3).
#
# The rule is here, in the module both of them already import, rather than exported from one
# renderer to the other -- a section renderer added next year needs the budget available where it
# looks for token arithmetic, not in whichever sibling happened to be fixed first.
def section_budget(share, configured=None):
    """A section's token budget as a share of the index budget the user actually configured.

    A user who raises `index_token_budget` to 6,000 has asked for a bigger index and should not
    still get a section sized for 3,000; one who lowers it to 1,500 should not have a single
    optional section eat most of the whole budget. The floor of 120 keeps a section from
    collapsing to nothing on a very small budget -- one entry is a summary, zero rows is not.
    """
    if configured is None:
        try:
            import workspace as _ws
            configured = _ws.load_config().get("index_token_budget", 3000)
        except Exception:
            configured = 3000
    return max(int(configured * share), 120)


def fill_by_budget(entries, render_one, token_budget, count_cap):
    """Keep `entries` in order until either the token budget or the count cap is spent.

    Returns (kept_render_lines, kept_count). At least one entry is always kept when the list is
    non-empty, even if it alone exceeds the budget -- a budget of zero rows is not a summary, and
    `mdblock.as_quoted`'s own per-entry cap already bounds how bad the single worst case can be.
    """
    lines = []
    spent = 0.0
    for e in entries:
        if len(lines) >= count_cap:
            break
        line = render_one(e)
        cost = estimate(line)
        if lines and spent + cost > token_budget:
            break
        lines.append(line)
        spent += cost
    return lines, len(lines)
