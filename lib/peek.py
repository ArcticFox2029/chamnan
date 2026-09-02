"""Read the SHAPE of a file that is too large or too binary to read whole.

The index says a directory holds 12,400 PDFs so nobody goes looking. This is the other half: when
a task genuinely needs one of them, opening it whole is the wrong move and skipping it is also the
wrong move. A 40 MB CSV is 11 million tokens; its column list, row count and three sample rows are
about two hundred, and for almost every question that is asked of a CSV the two hundred is the
answer. Same for a spreadsheet's sheet names, an archive's member list, a database's schema, a
log's error lines.

So each format gets a handler that returns structure first and content only on request. Nothing
here loads a whole file into memory when the format allows seeking, and every handler is bounded.

Standard library only, which shapes what is possible and is worth stating rather than hiding:
zipfile opens .xlsx, .docx and .apk because those ARE zips; sqlite3 reads a database's schema;
zlib decompresses PDF streams well enough to pull text out; struct reads image headers. Parquet and
Avro are identified and measured but not decoded — that needs a real reader, and adding one would
cost the plugin its only deployment advantage. Where a format cannot be understood, the handler
says so instead of guessing.
"""
import binascii
import csv
import io
import json
import re
import struct
import sys
import zipfile
from collections import Counter
from pathlib import Path

import mapper
import redact
import tokens
DEFAULT_BUDGET = 400           # tokens of output; the whole point is to stay small
SAMPLE_ROWS = 3
MAX_MEMBERS = 25
MAX_KEYS = 40
ROW_CAP = 2_000_000      # stop counting rows; the count is then reported as a floor, not a fact
HIT_CAP = 8
TEXT_LIKE = {".txt", ".log", ".md", ".rst", ".ini", ".cfg", ".conf", ".properties", ".env",
             ".sql", ".yaml", ".yml", ".toml", ".html", ".htm", ".xml", ".svg", ".eml"}
ZIP_LIKE = {".zip", ".xlsx", ".docx", ".pptx", ".jar", ".apk", ".whl", ".ipa", ".odt", ".epub"}
IMAGE_LIKE = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".tif"}
OPAQUE = {".parquet": "columnar (Parquet)", ".avro": "row-oriented (Avro)",
          ".orc": "columnar (ORC)", ".pb": "protobuf wire format",
          ".mp4": "video container", ".wav": "audio", ".mp3": "audio",
          ".iso": "disc image", ".bin": "opaque binary", ".dat": "opaque binary"}
MAGIC = [
    (b"%PDF-", "PDF document"), (b"PK\x03\x04", "ZIP-based container"),
    (b"\x89PNG", "PNG image"), (b"\xff\xd8\xff", "JPEG image"), (b"GIF8", "GIF image"),
    (b"SQLite format 3", "SQLite database"), (b"\x1f\x8b", "gzip stream"),
    (b"PAR1", "Parquet"), (b"Obj\x01", "Avro"), (b"\x7fELF", "ELF binary"),
    (b"BZh", "bzip2"), (b"\xfd7zXZ", "xz"), (b"Rar!", "RAR archive"),
]


def _looks_binary(path):
    """True when a file claiming to be text is not. A NUL byte settles it; otherwise judge by how
    much of the first block is outside the printable range, which mojibake fails and real text --
    including Thai, Japanese and Cyrillic, whose UTF-8 bytes decode cleanly -- passes."""
    try:
        with path.open("rb") as fh:
            head = fh.read(4096)
    except OSError:
        return False
    if not head:
        return False
    if b"\x00" in head:
        return True
    # 🐛 A 4096-byte read cuts wherever it lands, and a multi-byte character straddling that
    # boundary raised UnicodeDecodeError — which this treated as proof of binary content. The
    # docstring names the exact case it was failing: "real text — including Thai, Japanese and
    # Cyrillic, whose UTF-8 bytes decode cleanly — passes." Measured on one Thai CSV at three byte
    # offsets: two of the three were declared binary, on every file over 4KB, which is the only
    # size peek exists for. The tool then asserted "of bin that a plain read cannot open" about a
    # plain UTF-8 CSV and reported 0 tokens spent.
    #
    # Trimmed back to the last complete sequence rather than decoded with errors="ignore": ignoring
    # would also swallow genuine mojibake, which is what this function is for.
    for _cut in range(4):
        try:
            text = head[:len(head) - _cut].decode("utf-8")
            break
        except UnicodeDecodeError:
            continue
    else:
        return True
    odd = sum(1 for ch in text if ord(ch) < 32 and ch not in "\t\n\r")
    return odd > len(text) * 0.05


def _human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024


def _identify(head):
    for sig, name in MAGIC:
        if head.startswith(sig):
            return name
    return None


# ------------------------------------------------------------------ tabular
def peek_csv(path, find=None):
    delim = "\t" if path.suffix.lower() in (".tsv", ".tab") else ","
    rows, total, widths = [], 0, Counter()
    hits, capped = [], False
    # 🐛 utf-8-SIG, matching mapper. A UTF-8 BOM is what Excel writes on "Save As CSV UTF-8" and
    # what a good many Windows editors add to source, and read as plain utf-8 it arrives as a
    # U+FEFF character at the front of the file. The damage is not cosmetic:
    #
    #   bom.py   the index row reads `(3L, 1fn) — Module docstring here.` and peek showed
    #            `1: ﻿"""Module docstring here."""` with NO summary and NO symbol list,
    #            because the extractor did not recognise the docstring and peek fell through to
    #            its plain-text branch. peek_source's own docstring says "same extractor as the
    #            index, so a file peeked and a file indexed agree with each other". They did not.
    #   bom.csv  the first column came back named `﻿name`, so `--find name` never matched it
    #            and neither would anything downstream.
    #
    # Changed at all six decode points in one pass rather than at the branch that was noticed.
    # _whole_file_tokens below prices the file by decoding it too, and if only some of them learn
    # about the BOM then peek's shape and peek's own cost note stop being computed from the same
    # string — which is the shape of the bug being fixed here, one level down.
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as fh:
        reader = csv.reader(fh, delimiter=delim)
        try:
            header = next(reader)
        except StopIteration:
            return ["empty file"]
        for i, row in enumerate(reader):
            total += 1
            widths[len(row)] += 1
            if len(rows) < SAMPLE_ROWS:
                rows.append(row)
            if find and len(hits) < HIT_CAP and any(find.lower() in c.lower() for c in row):
                hits.append((i + 2, row))
            if total >= ROW_CAP:
                capped = True
                break
    # Both caps used to be silent, and this whole module exists so a number here can be trusted
    # instead of the file being read. "2,000,000 data rows" for a file with three million of them
    # is a stated fact that is wrong, and a 60-column CSV listed 40 columns and never said the
    # other 20 existed. `_shape` below has always written `…+N`; say it here too.
    out = [f"{len(header)} columns, "
           + (f"more than {total:,} data rows (stopped counting at the {ROW_CAP:,} cap)"
              if capped else f"{total:,} data rows")]
    shown = header[:MAX_KEYS]
    more = f", …+{len(header)-len(shown)} more" if len(header) > len(shown) else ""
    out.append("columns: " + ", ".join(f"`{c.strip()}`" for c in shown) + more)
    if len(widths) > 1:
        out.append(f"ragged: {len(widths)} different row widths seen — {dict(widths.most_common(3))}")
    if find:
        tail = "" if len(hits) < HIT_CAP else f" — the first {HIT_CAP}; there may be more"
        out.append(f"\nrows matching {find!r} ({len(hits)} shown{tail}):")
        out += [f"  line {n}: " + " | ".join(c[:28] for c in r[:8]) for n, r in hits]
    else:
        out.append("\nfirst rows:")
        out += ["  " + " | ".join(c[:28] for c in r[:8]) for r in rows]
    return out


# ------------------------------------------------------------------ json
def _shape(value, depth=0):
    if depth > 4:
        return "…"
    if isinstance(value, dict):
        items = list(value.items())[:MAX_KEYS]
        inner = ", ".join(f"{k}: {_shape(v, depth + 1)}" for k, v in items)
        more = f", …+{len(value)-len(items)}" if len(value) > len(items) else ""
        return "{" + inner + more + "}"
    if isinstance(value, list):
        return f"[{len(value)} × {_shape(value[0], depth + 1) if value else 'empty'}]"
    return type(value).__name__


def peek_json(path, find=None):
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except (json.JSONDecodeError, MemoryError) as err:
        return [f"not valid JSON as a whole ({type(err).__name__}); may be JSON Lines",
                *peek_text(path, find)]
    out = ["structure (keys and types only, no values):", "  " + _shape(data)]
    if find:
        blob = json.dumps(data)
        hits = [m.start() for m in re.finditer(re.escape(find), blob, re.I)][:6]
        out.append(f"\n{len(hits)} occurrence(s) of {find!r}:")
        out += ["  …" + blob[max(0, h - 60):h + 80].replace("\n", " ") + "…" for h in hits]
    return out


def peek_jsonl(path, find=None, sample=SAMPLE_ROWS):
    """JSON Lines: how many records, and the shape of one.

    🐛 `.jsonl` and `.ndjson` reached no branch at all and fell through to `peek_binary`, which
    described a plain text file as "unrecognised; 100% printable", gave a crc32 and five string
    fragments, and claimed a compression ratio — the worst answer this module can give, and the one
    `peek_source`'s docstring was written to close for source files. `peek_json` already names JSON
    Lines in its own fallback and `_cost_note` already whitelists `.jsonl` as comparable, so the
    handler was intended and simply absent.
    """
    rows, total, bad = [], 0, 0
    hits = []
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace") as fh:
            for i, line in enumerate(fh):
                line = line.strip()
                if not line:
                    continue
                total += 1
                if len(rows) < sample:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        bad += 1
                if find and len(hits) < HIT_CAP and find.lower() in line.lower():
                    hits.append((i + 1, line))
    except OSError as err:
        return [f"could not be read ({type(err).__name__})"]
    if not total:
        return ["empty file"]
    out = [f"{total:,} JSON Lines record(s)"]
    if rows:
        out.append("shape of the first record (keys and types only, no values):")
        out.append("  " + _shape(rows[0]))
        shapes = {tuple(sorted(r)) for r in rows if isinstance(r, dict)}
        if len(shapes) > 1:
            out.append(f"ragged: {len(shapes)} different key sets in the first {len(rows)} records")
    if bad:
        out.append(f"{bad} of the first {len(rows) + bad} record(s) did not parse as JSON")
    if find:
        tail = "" if len(hits) < HIT_CAP else f" — the first {HIT_CAP}; there may be more"
        out.append(f"\nrecords matching {find!r} ({len(hits)} shown{tail}):")
        out += [f"  line {n}: " + r[:110] for n, r in hits]
    return out


# ------------------------------------------------------------------ archives
# ------------------------------------------------------------------ OOXML bodies
# A .docx and a .xlsx are zips, and listing their members says nothing a reader wants: the
# clause and the column are inside one XML part. Both are read here rather than left to the
# archive listing, because a contract and a price table are the two attachments most likely
# to be the actual reason someone opened the file.
_CELL = re.compile(r"<c\b([^>]*)>(.*?)</c>|<c\b([^>]*)/>", re.S)
_VAL = re.compile(r"<v>(.*?)</v>", re.S)
_INLINE = re.compile(r"<t[^>]*>(.*?)</t>", re.S)
_ROW = re.compile(r"<row\b[^>]*>(.*?)</row>", re.S)
# One shared string is one <si>. A rich-text <si> — a header cell with one word bolded, the most
# common formatting in a real spreadsheet — holds one <t> PER RUN, so collecting <t> elements
# flatly produced more entries than the table has and shifted every index after it. Measured on a
# three-row sheet with a partially bold header: not one printed value was the value in that cell,
# `Gadget` never appeared at all, and `Widget` appeared twice in cells that never held it. The
# whole claim of this module is that its two hundred tokens substitute for reading the file.
_SI = re.compile(r"<si\b[^>]*>(.*?)</si>|<si\b[^>]*/>", re.S)
_PARA = re.compile(r"<w:p\b[^>]*>(.*?)</w:p>", re.S)
_RUN = re.compile(r"<w:t[^>]*>(.*?)</w:t>", re.S)


def _unxml(s):
    return (s.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
             .replace("&apos;", "'").replace("&amp;", "&"))


def _sheet_rows(zf, names, limit):
    """Rows of the first worksheet, resolving both shared and inline strings."""
    sheet = next((n for n in names if re.fullmatch(r"xl/worksheets/sheet1?\.xml", n)), None)
    if not sheet:
        return []
    shared = []
    if "xl/sharedStrings.xml" in names:
        _sxml = zf.read("xl/sharedStrings.xml").decode("utf-8", "replace")
        # Per <si>, joining that entry's runs — never per <t>.
        shared = ["".join(_unxml(t) for t in _INLINE.findall(m.group(1) or ""))
                  for m in _SI.finditer(_sxml)]
    xml = zf.read(sheet).decode("utf-8", "replace")
    rows = []
    for body in _ROW.findall(xml):
        cells = []
        for attrs, inner, _empty in _CELL.findall(body):
            if not attrs and not inner:
                cells.append("")
                continue
            if 't="s"' in attrs:                       # index into the shared string table
                v = _VAL.search(inner)
                idx = int(v.group(1)) if v and v.group(1).isdigit() else -1
                cells.append(shared[idx] if 0 <= idx < len(shared) else "")
            elif 't="inlineStr"' in attrs:
                cells.append(_unxml("".join(_INLINE.findall(inner))))
            else:
                v = _VAL.search(inner)
                cells.append(_unxml(v.group(1)) if v else "")
        rows.append(cells)
        if len(rows) >= limit:
            break
    return rows


def _docx_paragraphs(zf):
    xml = zf.read("word/document.xml").decode("utf-8", "replace")
    paras = [_unxml("".join(_RUN.findall(body))).strip() for body in _PARA.findall(xml)]
    return [p for p in paras if p]


def peek_zip(path, find=None):
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        out = [f"{len(names)} member(s), {_human(sum(i.file_size for i in zf.infolist()))} uncompressed"]
        # .xlsx and .docx are zips with their meaning in known members, so read those directly.
        if "xl/workbook.xml" in names:
            book = zf.read("xl/workbook.xml").decode("utf-8", "replace")
            sheets = re.findall(r'<sheet[^>]*name="([^"]+)"', book)
            out.append("spreadsheet sheets: " + ", ".join(f"`{s}`" for s in sheets))
            # Bounded on purpose: reading past a few hundred rows to sample three of them
            # would spend the memory this module exists to avoid.
            rows = _sheet_rows(zf, names, 400 if find else SAMPLE_ROWS + 1)
            if rows:
                head = rows[0]
                out.append(f"{len(head)} columns on `{sheets[0] if sheets else 'sheet1'}`")
                out.append("columns: " + ", ".join(f"`{c}`" for c in head[:MAX_KEYS] if c))
                if find:
                    hits = [r for r in rows[1:] if any(find.lower() in c.lower() for c in r)]
                    out.append(f"\nrows matching {find!r} ({len(hits[:8])} of {len(hits)} shown):")
                    out += ["  " + " | ".join(c[:28] for c in r[:8]) for r in hits[:8]]
                else:
                    out.append("\nfirst rows:")
                    out += ["  " + " | ".join(c[:28] for c in r[:8])
                            for r in rows[1:SAMPLE_ROWS + 1]]
        if "word/document.xml" in names:
            paras = _docx_paragraphs(zf)
            out.append(f"{len(paras):,} paragraph(s) of text")
            if find:
                hits = [(i, p) for i, p in enumerate(paras, 1) if find.lower() in p.lower()]
                out.append(f"\nparagraphs matching {find!r} ({len(hits[:6])} of {len(hits)} shown):")
                out += [f"  ¶{i}: {p[:220]}" for i, p in hits[:6]]
            else:
                out.append("\nopening text:")
                out += [f"  {p[:220]}" for p in paras[:4]]
        if "docProps/core.xml" in names:
            core = zf.read("docProps/core.xml").decode("utf-8", "replace")
            for tag in ("dc:title", "dc:creator", "dcterms:created"):
                m = re.search(rf"<{tag}[^>]*>([^<]+)<", core)
                if m:
                    out.append(f"{tag.split(':')[1]}: {m.group(1)}")
        if "AndroidManifest.xml" in names:
            out.append("android package — manifest present")
        listed = [n for n in names if find.lower() in n.lower()] if find else names
        out.append(f"\nmembers{' matching ' + repr(find) if find else ''}:")
        out += [f"  {n}" for n in listed[:MAX_MEMBERS]]
        if len(listed) > MAX_MEMBERS:
            out.append(f"  …+{len(listed)-MAX_MEMBERS} more")
    return out


def peek_tar(path, find=None):
    import tarfile
    with tarfile.open(path) as tf:
        members = tf.getmembers()
        out = [f"{len(members)} member(s), {_human(sum(m.size for m in members))} uncompressed"]
        listed = [m for m in members if not find or find.lower() in m.name.lower()]
        out += [f"  {m.name}  {_human(m.size)}" for m in listed[:MAX_MEMBERS]]
        if len(listed) > MAX_MEMBERS:
            out.append(f"  …+{len(listed)-MAX_MEMBERS} more")
    return out


# ------------------------------------------------------------------ sqlite
def peek_sqlite(path, find=None):
    import sqlite3
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        tables = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        out = [f"{len(tables)} table(s)"]
        for name in tables[:MAX_MEMBERS]:
            cols = [r[1] for r in con.execute(f"PRAGMA table_info('{name}')")]
            try:
                n = con.execute(f"SELECT count(*) FROM '{name}'").fetchone()[0]
            except sqlite3.Error:
                n = "?"
            out.append(f"  `{name}` ({n:,} rows) — " + ", ".join(cols[:12]) if isinstance(n, int)
                       else f"  `{name}` — " + ", ".join(cols[:12]))
        if find:
            out.append(f"\ntables or columns matching {find!r}: " +
                       ", ".join(t for t in tables if find.lower() in t.lower()))
    finally:
        con.close()
    return out


# ------------------------------------------------------------------ pdf
def peek_pdf(path, find=None):
    import zlib
    raw = path.read_bytes()
    out = []
    pages = len(re.findall(rb"/Type\s*/Page[^s]", raw))
    out.append(f"{pages or '?'} page(s)")
    for key in (b"Title", b"Author", b"Subject", b"Producer", b"CreationDate"):
        m = re.search(rb"/" + key + rb"\s*\(([^)]{1,120})\)", raw)
        if m:
            out.append(f"{key.decode()}: " + m.group(1).decode("utf-8", "replace"))
    # Text lives in FlateDecode streams; zlib is in the standard library, so a rough extraction is
    # available without a PDF library. Rough is the right word — enough to answer "what is this
    # document about", not enough to reproduce it.
    text = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", raw, re.S):
        if len(text) > 40:
            break
        try:
            body = zlib.decompress(m.group(1))
        except zlib.error:
            continue
        text += [t.decode("utf-8", "replace") for t in re.findall(rb"\((.{1,200}?)\)\s*Tj", body)]
    joined = " ".join(text)
    if find and joined:
        hits = [m.start() for m in re.finditer(re.escape(find), joined, re.I)][:5]
        out.append(f"\n{len(hits)} match(es) for {find!r}:")
        out += ["  …" + joined[max(0, h-70):h+90] + "…" for h in hits]
    elif joined:
        out.append("\nextracted text (first 400 chars):")
        out.append("  " + joined[:400])
    else:
        out.append("no extractable text — likely a scan; an OCR step would be needed")
    return out


# ------------------------------------------------------------------ images
def peek_image(path):
    head = path.read_bytes()[:64]
    if head.startswith(b"\x89PNG"):
        w, h = struct.unpack(">II", head[16:24])
        depth, colour = head[24], head[25]
        kinds = {0: "greyscale", 2: "RGB", 3: "palette", 4: "greyscale+alpha", 6: "RGBA"}
        return [f"PNG {w}×{h}, {depth}-bit {kinds.get(colour, colour)}"]
    if head.startswith(b"\xff\xd8"):
        # 🐛 This used to scan the raw bytes for an SOF marker with a regex, and the FIRST one it
        # found belonged to the EXIF THUMBNAIL — every phone photo carries one — so a 4032×3024
        # photograph was reported as 160×120. Walking the segment chain skips APP1 by its declared
        # length, which is how the thumbnail stops being reachable at all rather than being
        # filtered out afterwards.
        raw = path.read_bytes()
        i, SOF = 2, set(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}
        while i + 3 < len(raw):
            if raw[i] != 0xFF:
                i += 1
                continue
            marker = raw[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            if marker == 0xDA or marker == 0xD9:      # start of scan / end of image
                break
            seg = struct.unpack(">H", raw[i + 2:i + 4])[0]
            if marker in SOF and i + 9 <= len(raw):
                h, w = struct.unpack(">HH", raw[i + 5:i + 9])
                return [f"JPEG {w}×{h}"]
            i += 2 + max(seg, 2)
        return ["JPEG, dimensions not found in the frame headers"]
    if head.startswith(b"GIF8"):
        w, h = struct.unpack("<HH", head[6:10])
        return [f"GIF {w}×{h}"]
    return ["image, header not recognised"]


# ------------------------------------------------------------------ text and fallback
def peek_text(path, find=None):
    lines, total = [], 0
    with path.open("r", encoding="utf-8-sig", errors="replace") as fh:
        for i, line in enumerate(fh):
            total += 1
            if find:
                if find.lower() in line.lower() and len(lines) < 12:
                    lines.append((i + 1, line.rstrip()[:160]))
            elif i < 8:
                lines.append((i + 1, line.rstrip()[:160]))
    out = [f"{total:,} lines"]
    if find:
        out.append(f"lines matching {find!r} ({len(lines)} shown):")
    else:
        out.append("first lines:")
    out += [f"  {n}: {t}" for n, t in lines]
    return out


def peek_binary(path):
    raw = path.open("rb").read(4096)
    kind = _identify(raw) or "unrecognised"
    printable = sum(32 <= b < 127 or b in (9, 10, 13) for b in raw)
    strings = re.findall(rb"[ -~]{6,}", raw)[:8]
    return [f"{kind}; {printable * 100 // max(len(raw), 1)}% printable in the first 4KB",
            "crc32 of first 4KB: " + format(binascii.crc32(raw) & 0xFFFFFFFF, "08x"),
            "readable strings: " + ", ".join(s.decode("ascii")[:40] for s in strings[:5])]


# ------------------------------------------------------------------ dispatch
# Formats with a real handler above, as opposed to the two fallbacks. The distinction matters to
# anything deciding whether a shape is worth showing UNASKED: for a CSV, a spreadsheet or a database
# the shape genuinely substitutes for the read, while for 674KB of JavaScript `peek_binary` offers a
# crc32 and five string fragments, which is not an answer to anything. Measured on a real file
# before this existed — the .js output was 135 tokens of nothing.
#
# Derived from peek()'s own dispatch rather than listed twice, so a new handler joins both at once.
STRUCTURED = set((".csv", ".tsv", ".tab", ".json", ".jsonl", ".ndjson", ".tar", ".tgz", ".pdf",
                  ".db", ".sqlite", ".sqlite3")) | ZIP_LIKE | IMAGE_LIKE


def has_structure(path):
    """True if peek() would reach a real handler for this path, not peek_text or peek_binary."""
    path = Path(path)
    if path.suffix.lower() in STRUCTURED:
        return True
    return path.name.endswith((".tar.gz", ".tar.bz2", ".tar.xz"))


def peek_source(path, find=None):
    """A source file's shape: what it opens with, and what it defines.

    Source code used to reach peek_binary -- there was no branch for `.py`, `.js`, `.go` or any
    other language, and no source extension in TEXT_LIKE either, so the single most common kind of
    file in every repository chamnan targets got the worst answer the tool can give: "unrecognised;
    100% printable in the first 4KB", a CRC32 and a strings dump. Two commands earlier, chamnan-map
    had read the same file and listed its functions by name.

    Same extractor as the index, so a file peeked and a file indexed agree with each other.
    """
    lang = mapper.EXT_LANG.get(path.suffix.lower())
    source = path.read_text(encoding="utf-8-sig", errors="replace")
    out = []
    try:
        summary, functions, classes, _rest = mapper._extract_one(source, str(path), lang)
    except Exception:
        return peek_text(path, find)
    if summary:
        out.append(summary)
        out.append("")
    # The extractor returns tuples, and the shape differs per kind: (signature, comment) for a
    # function, (name, comment, [methods]) for a type. Read positionally, the way render() does.
    for name, note, methods in (classes or []):
        members = ", ".join(methods[:MAX_MEMBERS]) if methods else ""
        line = f"type `{name}`" + (f" — {note}" if note else "")
        out.append(line + (f"\n  members: {members}" if members else ""))
    funcs = [sig for sig, _note in (functions or [])]
    if funcs:
        out.append(f"{len(funcs)} function(s):")
        out.extend(f"  {sig}" for sig in funcs[:MAX_MEMBERS])
        if len(funcs) > MAX_MEMBERS:
            out.append(f"  …and {len(funcs) - MAX_MEMBERS} more")
    if find:
        hits = [f"{i}: {ln.strip()[:120]}" for i, ln in enumerate(source.splitlines(), 1)
                if find.lower() in ln.lower()][:SAMPLE_ROWS * 4]
        out.append("")
        out.append(f"lines matching {find!r}: {len(hits)}" if hits else f"no line matches {find!r}")
        out.extend(f"  {h}" for h in hits)
    if not out:
        # A file this extractor finds nothing in is still text, and showing its opening lines beats
        # describing it as an unrecognised blob.
        return peek_text(path, find)
    return out


def peek(path, find=None, budget=DEFAULT_BUDGET):
    path = Path(path)
    if not path.is_file():
        return f"chamnan-peek: not a file: {path}"
    size = path.stat().st_size
    if redact.is_never_opened(path):
        # A key file's shape IS its content. Naming it and refusing is the whole useful answer;
        # peek is the one command that opens an arbitrary path on request, which makes it the
        # one that most needs a deny-list, and it did not have one.
        return (f"# {path.name}\n{_human(size)} · {path.suffix.lower() or 'no extension'}\n\n"
                f"Refused: chamnan does not open this kind of file. Its contents are credentials "
                f"or a key, and there is no summary of them that is safe to put in a session.\n\n"
                f"_[nothing read]_")
    ext = path.suffix.lower()
    header = [f"# {path.name}", f"{_human(size)} · {ext or 'no extension'}"]

    # An extension is a claim, not a fact. Handed binary data named .csv, the csv reader parses it
    # perfectly happily -- errors="replace" guarantees it never raises -- and the result was a
    # column list of raw control characters going straight into the session. Sniff the bytes first
    # and let the binary handler describe it instead; that handler exists precisely to say "this is
    # not text" without pretending to read it.
    if (ext in (".csv", ".tsv", ".tab", ".json", ".jsonl", ".ndjson")
            or ext in TEXT_LIKE) and _looks_binary(path):
        return "\n".join(header + ["", *[str(x) for x in peek_binary(path)]]) + \
               "\n\n" + _cost_note(path, ".bin", size, "")

    try:
        if ext in (".csv", ".tsv", ".tab"):
            body = peek_csv(path, find)
        elif ext == ".json":
            body = peek_json(path, find)
        elif ext in (".jsonl", ".ndjson"):
            body = peek_jsonl(path, find)
        elif ext in ZIP_LIKE and zipfile.is_zipfile(path):
            body = peek_zip(path, find)
        elif ext in (".tar", ".tgz") or path.name.endswith((".tar.gz", ".tar.bz2", ".tar.xz")):
            body = peek_tar(path, find)
        elif ext in (".db", ".sqlite", ".sqlite3") or path.open("rb").read(15) == b"SQLite format 3":
            body = peek_sqlite(path, find)
        elif ext == ".pdf":
            body = peek_pdf(path, find)
        elif ext in IMAGE_LIKE:
            body = peek_image(path)
        elif ext in OPAQUE:
            body = [f"{OPAQUE[ext]} — no standard-library reader for this format.",
                    "Identified and measured only; decoding it needs a dedicated library.",
                    *peek_binary(path)]
        elif ext in TEXT_LIKE or ext == "":
            body = peek_text(path, find)
        elif ext in mapper.EXT_LANG:
            body = peek_source(path, find)
        else:
            body = peek_binary(path)
    except Exception as err:                     # a malformed file must not crash the caller
        body = [f"could not read as {ext or 'unknown type'}: {type(err).__name__}: {err}",
                *peek_binary(path)]

    out = "\n".join(header + [""] + [str(x) for x in body])
    cut = tokens.cut_at(out, budget)
    if cut < len(out):
        out = out[:cut] + f"\n\n_[truncated at {budget} tokens — narrow it with --find]_"
    # One choke point, matching how the map is scrubbed. peek reads .env, .ini, .yaml and source
    # on demand, and printed AWS, Stripe, Slack and GitHub credentials verbatim into the session
    # until this line existed.
    out = redact.scrub(out)
    return out + "\n\n" + _cost_note(path, ext, size, out)


# 🐛 [2026-08-30] The comparison figure read the WHOLE file. Measured on a 4.8MB CSV: peek_csv did
# its work in 0.14s and the whole call took 7.5s, all of it spent tokenizing five megabytes to
# print one decorative ratio. On a 40MB export that is a minute of waiting for a number nobody
# asked for — and it is what stopped the bulk-read hook from being able to show a shape at all.
#
# Sampled above SAMPLE_BYTES and labelled "about", exact below it, so a small file's figure and
# every existing test are unchanged. An estimate is what this line always was; it just used to buy
# its precision at a price out of all proportion to the claim.
# 16KB, not more: measured on a 4.8MB CSV, a 16,000-byte sample gives exactly the same estimate as
# a 512,000-byte one (2.43% off the exact figure either way -- the error is the header row, not the
# sample size) and costs 25ms against 759ms.
SAMPLE_BYTES = 16_000


def _whole_file_tokens(path, size):
    """(tokens, sampled) for reading this file whole. `size` is BYTES on disk.

    Both conversions are measured on the sample rather than assumed, and the byte one is not
    optional: this plugin's own corpus is Thai, where one character is three bytes, so scaling a
    per-CHARACTER token rate by a BYTE count would have reported every Thai file as three times its
    real cost.
    """
    if size <= SAMPLE_BYTES:
        return tokens.estimate(path.read_text(encoding="utf-8-sig", errors="replace")), False
    with path.open("rb") as fh:
        raw = fh.read(SAMPLE_BYTES)
    # Drop a trailing partial character rather than letting errors="replace" invent one.
    head = raw.decode("utf-8", errors="ignore")
    if not head:
        return 0, False
    chars_per_byte = len(head) / len(raw)
    per_char = tokens.estimate(head) / len(head)
    return int(per_char * chars_per_byte * size), True


def _cost_note(path, ext, size, out):
    """Say what the peek cost, and only claim a saving where the alternative actually exists.

    The first version of this line divided the file's size on disk by a characters-per-token
    constant and reported the result as what reading it whole would have cost -- for every file,
    including a SQLite database, where it announced a 9,962x saving over a number that could never
    have been spent, because Read cannot open a database at all. Nor can it open a PNG. And for a
    .xlsx or a .docx the bytes on disk are deflate-compressed, so even where a comparison exists
    the size is the wrong basis for it. A tool whose whole subject is token honesty cannot round
    its own headline up.
    """
    spent = tokens.estimate(out)
    # Source code belongs on the comparable side. A plain read CAN open a .py, so claiming
    # otherwise would be the same dishonesty in the other direction that this function exists to
    # avoid -- and the comparison is real: the outline of a 3.4KB module is genuinely smaller.
    if (ext in TEXT_LIKE or ext in mapper.EXT_LANG
            or ext in (".csv", ".tsv", ".tab", ".json", ".jsonl", ".ndjson", "")):
        try:
            whole, sampled = _whole_file_tokens(path, size)
        except OSError:
            return f"_[{spent:,.0f} tokens]_"
        ratio = f" — {whole/max(spent, 1):,.0f}× smaller" if whole > spent * 2 else ""
        about = "about " if sampled else ""
        return f"_[{spent:,.0f} tokens instead of {about}{whole:,.0f} for the whole file{ratio}]_"
    return (f"_[{spent:,.0f} tokens. The file itself is {_human(size)} of {ext.lstrip('.') or 'binary'} "
            f"that a plain read cannot open, so this is not a saving over reading it — "
            f"it is the only way to see inside it without leaving the session.]_")
