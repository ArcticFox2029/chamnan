#!/usr/bin/env python3
"""How many more tokens the same sentence costs in one script than in another.

Why this file exists. The README and `lib/workspace.py` both cited "1.53x for Thai versus English
across three matched sentence pairs" and neither the sentences nor the script that produced the
figure was ever committed -- unlike `calibrate_tokens.py`, three files away, which ships its inputs
and its raw counts. A number whose inputs are lost cannot be checked, corrected, or re-run on a new
tokeniser, and this repository's own archive names that as the failure that gets a finding reported
three times and fixed none (R2 agent 4, and twice before it).

So the sentences are here, in the file, and the number this prints is the number the documentation
quotes. If they disagree, one of them is wrong and it is visible.

What it measures, and what it does not. `lib/tokens.py`'s estimator, which is what chamnan itself
budgets with -- not a vendor tokeniser. That makes the ratio reproducible offline and makes it the
right number for a claim about chamnan's own budgeting, and the wrong number for a claim about what
an API will bill. The estimator is calibrated against measured API usage (`bench/calibration.json`),
so it is not arbitrary, but it is an estimate and this file says so rather than implying a receipt.

    python3 bench/script_ratio.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import tokens as tk  # noqa: E402

# Matched pairs: the same thing said once in each script, by a person who reads both, at the length
# a code comment actually runs to. Not translations of marketing copy -- these are the register the
# claim is about, which is comments and session notes in a working repository.
PAIRS = [
    ("en/th",
     "The session ended before the migration finished, so the index is out of date.",
     "เซสชันจบก่อนที่การย้ายข้อมูลจะเสร็จ ดัชนีจึงไม่เป็นปัจจุบัน"),
    ("en/th",
     "Retry the upload when the gateway returns a 502, up to three times.",
     "ลองอัปโหลดใหม่เมื่อเกตเวย์ตอบ 502 ได้ไม่เกินสามครั้ง"),
    ("en/th",
     "This function is the only writer of the shared file, and it holds no lock.",
     "ฟังก์ชันนี้เป็นตัวเดียวที่เขียนไฟล์ที่ใช้ร่วมกัน และไม่ได้ถือล็อกไว้"),
]


def main():
    print(f"{'':4} {'EN tok':>8} {'TH tok':>8} {'TH/EN':>7}   {'EN ch':>6} {'TH ch':>6}")
    ratios = []
    for i, (_, en, th) in enumerate(PAIRS, 1):
        e, t = tk.estimate(en), tk.estimate(th)
        ratios.append(t / e)
        print(f"{i:>4} {e:>8.1f} {t:>8.1f} {t / e:>7.2f}   {len(en):>6} {len(th):>6}")
    mean = sum(ratios) / len(ratios)
    # Every number carries its unit, including the range: a check that parses this line looked for
    # `1.50x-1.85x` and found `1.50-1.85`, and the mismatch was in the printer, not the parser.
    print(f"\n  mean {mean:.2f}x   range {min(ratios):.2f}x-{max(ratios):.2f}x   "
          f"over {len(PAIRS)} pairs")
    print("  Estimated with lib/tokens.py, the estimator chamnan budgets with. Not a vendor")
    print("  tokeniser and not a bill; see bench/calibration.json for what it is calibrated against.")
    # The spread is the honest part. Three pairs is a small sample and one of them sits well above
    # the other two, so a single mean quoted without its range would be the tidier lie.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
