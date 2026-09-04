"""Rewrite `lib/unicode_marks.py`'s MARKS constant from the running Python's unicodedata.

The suite fails when the constant stops covering every Mn/Mc codepoint, which is what a Unicode
release looks like from inside this repository -- Unicode 16 added 51 of them (Garay,
Tulu-Tigalari, Arabic pepet) and the check went red on 2026-09-04. This is the other half of that
check: the thing that makes it green again without hand-editing 300 ranges.

It exists because the docstring used to say "regenerate with" a one-liner that printed a flat list
of 2,488 integers. That is the input to the answer, not the answer -- the ranges still had to be
collapsed by hand, and codepoints above U+FFFF need `\\U0001xxxx` escapes that the one-liner never
produced. Nobody following that instruction could reproduce the file.

Run on the NEWEST Python available: the constant is a superset, and a wider one is safe on an older
interpreter (every mark that interpreter knows about is still inside it), while a narrower one
silently stops indexing names.
"""
import pathlib
import re
import sys
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parent.parent
TARGET = ROOT / "lib" / "unicode_marks.py"
WIDTH = 96


def escape(cp):
    return f"\\u{cp:04x}" if cp <= 0xFFFF else f"\\U{cp:08x}"


def collapse(codepoints):
    """[1,2,3,7] -> [(1,3),(7,7)] — the file stores ranges, not a list."""
    out, start, prev = [], codepoints[0], codepoints[0]
    for cp in codepoints[1:]:
        if cp == prev + 1:
            prev = cp
            continue
        out.append((start, prev))
        start = prev = cp
    out.append((start, prev))
    return out


def main():
    marks = [cp for cp in range(sys.maxunicode + 1)
             if unicodedata.category(chr(cp)) in ("Mn", "Mc")]
    ranges = collapse(marks)
    body = "".join(escape(a) if a == b else f"{escape(a)}-{escape(b)}" for a, b in ranges)

    # Wrap on escape boundaries. Splitting mid-escape would produce a class that still compiles and
    # matches the wrong thing, which is the failure mode worth spending a regex on.
    tokens = re.findall(r"\\u[0-9a-f]{4}-\\u[0-9a-f]{4}|\\U[0-9a-f]{8}-\\U[0-9a-f]{8}"
                        r"|\\u[0-9a-f]{4}-\\U[0-9a-f]{8}|\\u[0-9a-f]{4}|\\U[0-9a-f]{8}", body)
    if "".join(tokens) != body:
        raise SystemExit("regen: the escape tokenizer did not round-trip; refusing to write")

    lines, cur = [], ""
    for tok in tokens:
        if len(cur) + len(tok) > WIDTH:
            lines.append(cur)
            cur = tok
        else:
            cur += tok
    if cur:
        lines.append(cur)

    block = (f"# {len(marks)} codepoints in {len(ranges)} ranges.\nMARKS = (\n"
             + "\n".join(f'    "{l}"' for l in lines) + "\n)")

    src = TARGET.read_text(encoding="utf-8")
    match = re.search(r"^# \d+ codepoints in \d+ ranges\.\nMARKS = \(\n(?:.*\n)*?\)$",
                      src, re.MULTILINE)
    if not match:
        raise SystemExit("regen: could not find the MARKS block to replace")
    TARGET.write_text(src[:match.start()] + block + src[match.end():], encoding="utf-8")
    print(f"{TARGET.relative_to(ROOT)}: {len(marks)} codepoints in {len(ranges)} ranges "
          f"(Unicode {unicodedata.unidata_version}, Python "
          f"{sys.version_info.major}.{sys.version_info.minor})")


if __name__ == "__main__":
    main()
