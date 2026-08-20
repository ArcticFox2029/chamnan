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

import tokens
DEFAULT_BUDGET = 400           # tokens of output; the whole point is to stay small
SAMPLE_ROWS = 3
MAX_MEMBERS = 25
MAX_KEYS = 40
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
    hits = []
    with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
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
            if find and len(hits) < 8 and any(find.lower() in c.lower() for c in row):
                hits.append((i + 2, row))
            if total > 2_000_000:
                break
    out = [f"{len(header)} columns, {total:,} data rows"]
    out.append("columns: " + ", ".join(f"`{c.strip()}`" for c in header[:MAX_KEYS]))
    if len(widths) > 1:
        out.append(f"ragged: {len(widths)} different row widths seen — {dict(widths.most_common(3))}")
    if find:
        out.append(f"\nrows matching {find!r} ({len(hits)} shown):")
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
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
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
        shared = [_unxml(s) for s in
                  _INLINE.findall(zf.read("xl/sharedStrings.xml").decode("utf-8", "replace"))]
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
        raw = path.read_bytes()
        for m in re.finditer(b"\xff[\xc0\xc1\xc2]", raw):
            h, w = struct.unpack(">HH", raw[m.start() + 5:m.start() + 9])
            return [f"JPEG {w}×{h}"]
        return ["JPEG, dimensions not found in the first frame header"]
    if head.startswith(b"GIF8"):
        w, h = struct.unpack("<HH", head[6:10])
        return [f"GIF {w}×{h}"]
    return ["image, header not recognised"]


# ------------------------------------------------------------------ text and fallback
def peek_text(path, find=None):
    lines, total = [], 0
    with path.open("r", encoding="utf-8", errors="replace") as fh:
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
def peek(path, find=None, budget=DEFAULT_BUDGET):
    path = Path(path)
    if not path.is_file():
        return f"chamnan-peek: not a file: {path}"
    size = path.stat().st_size
    ext = path.suffix.lower()
    header = [f"# {path.name}", f"{_human(size)} · {ext or 'no extension'}"]

    try:
        if ext in (".csv", ".tsv", ".tab"):
            body = peek_csv(path, find)
        elif ext == ".json":
            body = peek_json(path, find)
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
        else:
            body = peek_binary(path)
    except Exception as err:                     # a malformed file must not crash the caller
        body = [f"could not read as {ext or 'unknown type'}: {type(err).__name__}: {err}",
                *peek_binary(path)]

    out = "\n".join(header + [""] + [str(x) for x in body])
    cut = tokens.cut_at(out, budget)
    if cut < len(out):
        out = out[:cut] + f"\n\n_[truncated at {budget} tokens — narrow it with --find]_"
    return out + "\n\n" + _cost_note(path, ext, size, out)


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
    if ext in TEXT_LIKE or ext in (".csv", ".tsv", ".tab", ".json", ".jsonl", ".ndjson", ""):
        try:
            whole = tokens.estimate(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            return f"_[{spent:,.0f} tokens]_"
        ratio = f" — {whole/max(spent, 1):,.0f}× smaller" if whole > spent * 2 else ""
        return f"_[{spent:,.0f} tokens instead of {whole:,.0f} for the whole file{ratio}]_"
    return (f"_[{spent:,.0f} tokens. The file itself is {_human(size)} of {ext.lstrip('.') or 'binary'} "
            f"that a plain read cannot open, so this is not a saving over reading it — "
            f"it is the only way to see inside it without leaving the session.]_")
