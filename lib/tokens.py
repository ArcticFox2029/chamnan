"""Estimate token counts without a tokenizer, honestly enough to enforce a budget.

A single characters-per-token constant is only ever right for one language. Measured
against Claude's own accounting, English code runs about 2.5 characters per token
while Thai runs 1.2 and Chinese 0.96 -- so a flat 3.6 under-counted a Chinese index
by a factor of nearly four. That matters because this number is not decoration: it
decides how much of the architecture index gets injected at session start. A repo
whose summaries are not in English was silently blowing through the budget it set.

The weights below come from bench/calibrate_tokens.py, which measures real prompts
against the real API rather than guessing. The Latin divisor is deliberately on the
low side: over-estimating tokens wastes a little budget, while under-estimating
overruns it, and only one of those is a bug.
"""

# One token per character, roughly: Han, kana, Hangul, and CJK compatibility forms.
_CJK = ((0x4E00, 0x9FFF), (0x3040, 0x30FF), (0x3400, 0x4DBF),
        (0xAC00, 0xD7AF), (0xF900, 0xFAFF), (0x2E80, 0x2FDF), (0x3100, 0x312F))

# Abugidas, which tokenize almost as densely: Thai, Lao, Devanagari through Sinhala,
# and the Myanmar block.
_DENSE = ((0x0E00, 0x0EFF), (0x0900, 0x0DFF), (0x1000, 0x109F))

_CJK_WEIGHT = 1.00
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
