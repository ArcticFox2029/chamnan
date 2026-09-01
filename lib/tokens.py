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


def estimate(text):
    """Estimated token count for a string, weighted by the scripts it contains."""
    if not text:
        return 0.0
    cjk = dense = symbol = space = other = 0
    for ch in text:
        o = ord(ch)
        if _in(o, _CJK):
            cjk += 1
        elif _in(o, _DENSE):
            dense += 1
        elif ch.isspace():
            space += 1
        elif not ch.isalnum():
            symbol += 1
        else:
            other += 1
    return (cjk * _CJK_WEIGHT + dense * _DENSE_WEIGHT + symbol * _SYMBOL_WEIGHT
            + space * _SPACE_WEIGHT + other / _LATIN_DIVISOR)


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
