"""Estimate token counts without a tokenizer, honestly enough to enforce a budget.

A single characters-per-token constant is only ever right for one language. Measured
against Claude's own accounting, English code runs about 2.5 characters per token
while Thai runs 1.2 and Chinese 0.96 -- so a flat 3.6 under-counted a Chinese index
by a factor of nearly four. That matters because this number is not decoration: it
decides how much of the architecture index gets injected at session start. A repo
whose summaries are not in English was silently blowing through the budget it set.

The weights below come from bench/calibrate_tokens.py, which measures real prompts
against the real API rather than guessing. Over-estimating tokens wastes a little
budget while under-estimating overruns it, so where the two directions are not
equally safe the constants sit on the over-estimating side.

Where it actually lands, checked against bench/calibration.json (real counts, seven
scripts) and re-checked on every run of tests/run_tests.py:

    chinese   -7.7% -> +0.4%     thai            -0.7%
    japanese  +6.7% -> +14.5%     english_code    +3.1%
    german          -7.8%         russian        +17.6%
                                  english_prose  +36.2%

The two arrows are this commit: CJK punctuation was falling through to the Latin
divisor. Nothing else moved, because nothing else was wrong.

Two of those deserve their numbers said out loud rather than buried:

English PROSE is over-estimated by a third, because _LATIN_DIVISOR is calibrated on
code (2.47 chars/token measured) and prose runs far lighter (3.27). That is the right
bias for this module's main caller -- the architecture index is paths and signatures,
not prose -- but it means a prose-heavy STATE.md is reported as costing more than it
does, and can be rolled up earlier than it needs to be.

GERMAN is the one script still under-estimated, at -7.8%, and it is left that way on
purpose. One 1,266-character sample is not enough to move a constant that every other
Latin-script repository depends on, and compounding is exactly the feature that makes
German an outlier rather than a correction. The number is recorded here instead of
being tuned away, and the byte ceiling in lib/fit.py now bounds what a token error of
this size can actually cost: delivery is enforced in bytes, which no estimate touches.
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
_LATIN_DIVISOR = 2.4      # covers Latin, Cyrillic, Greek, Arabic, Hebrew, and code


def _in(o, ranges):
    return any(lo <= o <= hi for lo, hi in ranges)


def weight(ch):
    """Estimated tokens contributed by a single character."""
    o = ord(ch)
    if _in(o, _CJK):
        return _CJK_WEIGHT
    if _in(o, _DENSE):
        return _DENSE_WEIGHT
    return 1.0 / _LATIN_DIVISOR


def estimate(text):
    """Estimated token count for a string, weighted by the scripts it contains."""
    if not text:
        return 0.0
    cjk = dense = other = 0
    for ch in text:
        o = ord(ch)
        if _in(o, _CJK):
            cjk += 1
        elif _in(o, _DENSE):
            dense += 1
        else:
            other += 1
    return cjk * _CJK_WEIGHT + dense * _DENSE_WEIGHT + other / _LATIN_DIVISOR


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
