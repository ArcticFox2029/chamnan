"""Answer "what do the stores already say about X" from a derived index, not from a scan.

The absence of this was measured four times in one day, in the session that wrote the measurement
down: the answer was on disk, the session did not reach it, and twice it was more confident for
having read something adjacent. 1.26 item 1 is the response.

**The index is derived and the stores stay authoritative.** Querying must never walk the stores --
55 files and 407 KB in this repository, and this is a small one. A query reads one JSON file. The
build gate this ships under says so: improve retrieval of evidence that genuinely exists *without
forcing a broad scan before every answer*, which rules out doing the scan lazily on the first query
and calling it cheap.

**A stale index is reported, never silently refreshed.** The failure that ends "and then it rebuilt
420 files while you were waiting for an answer" is the one the gate forbids; the failure that ends
"the index is 3 files behind, run `chamnan-recall --reindex`" is a sentence. `stale_by` returns the
count and the caller decides.

**Matching is lexical, and that is a contract rather than a preference.** chamnan's README promises
it executes only `git` and this interpreter, so there is no embedding model and no vector store to
reach for. What lexical buys is that every hit can say WHY it matched, which a cosine distance
cannot.

**Thai is matched by substring, on purpose.** It has no word boundaries, and this repository has
already corrupted text twice by splitting it as though it did -- a 3-character key rewrote หน้าจอ
and a food keyword resolved ชีสเค้ก to เค้ก. A query that is not ASCII is not tokenised: it is
looked for whole, which is slower per term and cannot be wrong in that way.
"""
import hashlib
import math
import os
import re
import unicodedata

import redact
import tools_index
import workspace as ws

INDEX = "state/store_index.json"

# What a store IS, in the order a reader should see them. A rule outranks a lesson outranks a
# session note, because a rule is a standing constraint and a session note is one day's context.
KINDS = (
    ("memory/rules", "rule", 3.0),
    ("memory/decisions", "decision", 2.5),
    ("memory/lessons", "lesson", 2.5),
    ("skills", "skill", 2.0),
    ("threads", "thread", 1.5),
    ("sessions", "session", 1.0),
)

# Where a match is worth more. A term in the title is the document being ABOUT that thing; a term
# in the body may be an aside.
FIELD_WEIGHT = {"title": 6.0, "blurb": 3.0, "body": 1.0}

MAX_BODY_TERMS = 400        # per document, by frequency: the tail of a long skill is noise
SNIPPET = 90

_WORD = re.compile(r"[a-z0-9][a-z0-9_.-]*")
# Only a compound is worth splitting: a plain word costs a second regex pass for nothing, and
# this runs over every line of every store on a rebuild.
_SPLITTABLE = re.compile(r"[_.\-]|[a-z][0-9]|[0-9][a-zA-Z]|[a-z][A-Z]")
# The same shape as `_WORD` with the case left alone, because a hump is only
# visible before `lower()` and `_WORD` is applied to lowered text by contract.
_WORD_ANY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
_ASCII_ONLY = re.compile(r"\A[\x00-\x7f]*\Z")

# The shape of the stored terms. Bump it when `terms()` changes what it emits, so `build()` does
# not half-reuse entries whose terms were computed the old way.
# v3 = blurbs unwrap paired emphasis (R254).
TERMS_VERSION = 3

_SCRUBBER_ID = None


def scrubber_id():
    """Short fingerprint of the redactor that scrubs entries, cached after the first read.

    🐛 [2026-10-05] (R73 acc4, 2026-10-05) The index stores scrubbed text and terms, so an entry is
    only reusable if the same redactor scrubbed it; a redactor upgrade that catches more must not
    leave behind what the old one let through. Returns "unknown" if the file cannot be read.
    """
    global _SCRUBBER_ID
    if _SCRUBBER_ID is None:
        try:
            with open(redact.__file__, "rb") as fh:
                _SCRUBBER_ID = hashlib.sha1(fh.read()).hexdigest()[:12]
        except OSError:
            return "unknown"
    return _SCRUBBER_ID


def _ascii(text):
    return bool(_ASCII_ONLY.match(text))


# The only characters a droppable mark can involve: Latin/Greek/Cyrillic letters outside ASCII
# (which may precompose with a mark) and the combining-mark blocks. Text with none of these (ASCII,
# Thai-only) cannot change, so it skips the per-character loop. Measured: that loop cost ~10x.
_MARK_CANDIDATE = re.compile("[\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u024f\u0300-\u036f\u0370-\u03ff\u0400-\u04ff"
                             "\u1ab0-\u1aff\u1dc0-\u1dff\u1e00-\u1fff\u20d0-\u20ff\ufe20-\ufe2f]")


# Per-character verdict cache for the loop below: 0 = combining mark, 1 = Latin/Greek/Cyrillic
# letter (a base whose marks are dropped), 2 = anything else. Bounded by the distinct characters seen.
_CHAR_KIND = {}


def _drop_marks(text):
    """Remove combining marks that follow a Latin, Greek or Cyrillic letter; keep all others."""
    if not _MARK_CANDIDATE.search(text):
        return text
    out = []
    base_ok = False
    kind = _CHAR_KIND
    for ch in unicodedata.normalize("NFD", text):
        k = kind.get(ch)
        if k is None:
            if unicodedata.category(ch).startswith("M"):
                k = 0
            elif unicodedata.name(ch, "").startswith(("LATIN", "GREEK", "CYRILLIC")):
                k = 1
            else:
                k = 2
            kind[ch] = k
        if k == 0:
            if not base_ok:
                out.append(ch)
            continue
        base_ok = k == 1
        out.append(ch)
    return unicodedata.normalize("NFC", "".join(out))


# 🐛 [2026-10-01] (R185 acc4, 2026-09-30) Measured on a store with notes titled Café, Straße,
# İstanbul, Σοφός and Résumé: `cafe`, `CAFÉ`, `strasse`, even `straße` itself, `istanbul`,
# `ΣΟΦΟΣ`, `σοφος`, `resume` and `RÉSUMÉ` all found nothing. `terms()` kept only ASCII runs, so
# `Café` indexed as `caf`, and the substring path compared case-sensitively with marks. One
# folding function now runs on BOTH the stored and the query side. Marks are dropped only after
# a Latin, Greek or Cyrillic letter; after any other script they are kept, because in Thai a tone
# mark changes the word (ทำ / ท้า, คำ / ค้า) and stripping it would merge different words.
def fold(text):
    """NFKC, casefold, then drop accents on Latin/Greek/Cyrillic letters only."""
    if _ASCII_ONLY.match(text):
        return text.lower()
    return _drop_marks(unicodedata.normalize("NFKC", text).casefold())


# An identifier's parts. `_` and `.` split on the word pattern's own boundaries; a camelCase hump
# does not, so it is found here. Digits end a part (`utf8Decode` -> utf, 8, decode) because a
# version or a size is a word of its own in the names this indexes.
_HUMP = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z][a-z0-9]*|[a-z0-9]+")


def terms(text):
    """The ASCII words of `text`, lowercased, INCLUDING the parts of a compound identifier.

    🎯 [owner 2026-09-23, direction K] `apply_promo_code` tokenised to one term, so somebody who
    remembers what a function DOES and not what it is called searched `promo` and found nothing —
    which is the position of everybody who did not write the code. Splitting on `_` and on camelCase
    humps makes the parts searchable while keeping the whole, so an exact name still wins: the
    scorer counts terms, and a full-name match contributes the whole and every part.

    The whole is kept rather than replaced, and both go in. Dropping it would make
    `chamnan-recall apply_promo_code` score the same as `chamnan-recall apply`, which is the
    opposite of the point.

    Stop words are NOT removed here and must not be: `build()` derives them from document frequency
    over this repository's own stores, which works for its Thai notes as well as its English ones.
    A hand-written English list would be the enumerated-set mistake this package keeps paying for,
    and it is the one thing the spec for this direction got wrong.
    """
    # ASCII is the hot case (every title and blurb per query); NFKC and mark-dropping are identities
    # on it, so skip both. `fold(text)` below takes its own ASCII fast path.
    norm = text if _ASCII_ONLY.match(text) else _drop_marks(unicodedata.normalize("NFKC", text))
    # The whole tokens, exactly as before this change: every existing caller and every stored index
    # depends on this list, and the parts are ADDED to it rather than replacing anything.
    out = _WORD.findall(fold(text))
    # 🐛 [2026-09-23] (self-measured) The first version split the already-lowercased words, so
    # `utf8Decode` stayed one term — by then the hump it needed was gone. A camelCase boundary only
    # exists while the case does, so this pass reads the ORIGINAL and lowercases the parts after.
    for word in _WORD_ANY.findall(norm):
        if not _SPLITTABLE.search(word):
            continue
        low = word.lower()
        out.extend(part for part in (p.lower() for p in _HUMP.findall(word))
                   if len(part) > 1 and part != low)
    return out


# 🎯 [2026-09-27] (R91 acc2, 2026-09-27) A crude suffix strip, not a real stemmer -- exactly
# enough to group `boundary`/`boundaries` and `redact`/`redactor`/`redaction`/`redacted` without a
# dependency. Words ending in "ss" are excluded (a plural-looking "ss" strip would mangle short
# words like "process"), and the result must stay at least 4 characters so it cannot collapse
# unrelated short words onto the same stem.
def stem(w):
    for suf, rep in (("ies", "y"), ("ied", "y"), ("ying", "y"), ("ing", ""), ("ion", ""), ("ed", ""),
                     ("ors", ""), ("or", ""), ("es", ""), ("s", "")):
        if w.endswith(suf) and not w.endswith("ss") and len(w) - len(suf) + len(rep) >= 4:
            return w[: len(w) - len(suf)] + rep
    return w


def _title_of(path, text):
    """The first `# ` heading, else a frontmatter `title:`, else the filename made readable."""
    head = text.split("\n", 60)[:60]
    for line in head:
        if line.startswith("# "):
            return line[2:].strip()
    if head and head[0].strip() == "---":
        for line in head[1:]:
            if line.strip() == "---":
                break
            if line.lower().startswith("title:"):
                return line.split(":", 1)[1].strip()
    return path.stem.replace("_", " ").replace("-", " ")


def _blurb_of(text, title):
    """The first line of real prose under the title -- what the document says it is for."""
    for line in text.split("\n"):
        s = line.strip()
        if not s or s.startswith(("#", "---", "<!--", "|", "```")):
            continue
        if s.strip("*_ ") == title:
            continue
        # 🐛 [2026-10-01] (R254 acc4, 2026-10-01) Only the line ends were stripped, so a leading
        # `**Status:** closed` left a stray `**` mid-line. Paired emphasis is unwrapped first; a
        # lowercase `__init__` is a dunder identifier, not bold, and single `_` in words is kept.
        s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
        s = re.sub(r"(?<!\w)__(.+?)__(?!\w)",
                   lambda m: m.group(0) if re.fullmatch(r"[a-z0-9_]+", m.group(1)) else m.group(1), s)
        return re.sub(r"\s+", " ", s.strip("*_ "))[:240]
    return ""


def _needs_substring(line):
    """Does this line contain a LETTER that word-splitting cannot handle?

    🐛 The first version asked `not _ascii(line)`, and kept 60% of the corpus — because this
    repository's prose is full of em dashes, `·`, `🐛` and curly quotes, every one of which is
    non-ASCII and none of which needs substring matching. An index came out at 130% of the corpus
    it indexes. The question is not "is this ASCII" but "is there a letter here that has no word
    boundary", so it asks for a non-ASCII character whose Unicode category is a letter: Thai and
    CJK qualify, punctuation and emoji do not.
    """
    for ch in line:
        if ch > "\x7f" and unicodedata.category(ch).startswith("L"):
            return True
    return False


def _non_ascii_lines(text):
    """Only the lines a substring query could ever need.

    🐛 [2026-09-21] (self-measured) Used to cap the joined result at 4,000 characters, which
    silently dropped Thai content past that point -- Thai has no word boundaries, so substring
    matching is the only way Thai content is findable at all. Measured by building the real index
    both ways against `run_tests.py`'s `index_size <= corpus_size` corpus (78 documents,
    2,196,408 bytes): capped index 1,268,439 bytes (57.8% of corpus), uncapped 1,487,242 bytes
    (67.7% of corpus). The cap protected a property that had thirty points of headroom to spare.
    """
    return "\n".join(ln for ln in text.split("\n") if _needs_substring(ln))


def paths_for(ws_dir, folder):
    """Every `.md` file under the folder one `KINDS` entry names."""
    base = ws_dir / folder
    if base.is_dir():
        return sorted(p for p in base.rglob("*.md") if not ws.is_sync_conflict_copy(p))
    return []


# The fields a reused entry must carry for `build(ws, previous=...)` to trust it without
# re-reading the file. `size` and `ig` are new (see `_entry` and `build` below); an index written
# before this change lacks them and every entry from it fails this test, so it is rebuilt exactly
# as before. `tt`/`bt` (precomputed `terms(title.lower())`/`terms(blurb.lower())`) are gone --
# see the removal note on `_hits` -- and are deliberately NOT in this tuple: an index that still
# carries them from before this change is a perfectly good, still-reusable entry, since `_hits`
# no longer reads either field.
_REUSABLE_ENTRY_FIELDS = ("path", "kind", "weight", "title", "blurb", "body", "text",
                          "mtime", "size", "ig")


def _entry(ws_dir, path, kind, weight, prev=None):
    """One document, reduced to what a query needs and nothing it does not.

    🎯 [2026-09-28] (R122 acc2, 2026-09-28) `recall.build(ws)` profiled at 14.2s on this
    repository's own workspace (1,328 entries), 12.6s (89%) of it inside `redact.scrub`, called
    here for every store note's text, title and blurb on EVERY build -- so `chamnan-recall
    --reindex` re-scrubbed every unchanged note to pick up the one that actually changed. `prev`
    is the matching entry from the previous index, keyed by path, when one exists. A note whose
    `path`, `mtime_ns` AND on-disk `size` all still match `prev` is returned as a COPY of `prev`
    (never the same dict `build()`'s caller may still hold, since the caller reassigns `"body"`
    and `"ig"` in place afterward) instead of being read and scrubbed again. `mtime` alone is not
    enough: two different byte counts can share a coarse mtime on some filesystems, and `size` is
    one `stat()` field that was already being paid for.
    """
    # 🐛 [2026-09-12, R2 agent 1 F5] `rglob` returns whatever is at the path, and a committed
    # symlink at `.chamnan/memory/rules/x.md` pointing outside the workspace was followed: the
    # target's content became this entry's title and blurb and its raw bytes were written into the
    # persisted index. `workspace.inside()` exists for exactly this and its own docstring names the
    # case; `tools_index.load()` already calls it before trusting `tools/index.json`. A new reader
    # of the workspace is a new member of that set the day it is written, and this one was not.
    if not ws.inside(path, ws_dir):
        return None
    # 🐛 [R2 agent 1, F1] Each store folder carries its own `README.md` — an index OF the folder,
    # not an entry in it. Indexed as a rule or a skill, `skills/README.md` ranked first for
    # "skills index", above every real document. A folder's table of contents is the one file in it
    # that never answers "what do we already know about X".
    if path.name == "README.md":
        return None
    # 🐛 [2026-09-28] (R77 acc2, 2026-09-28) git's racy-timestamp problem in miniature: the mtime
    # used to be taken AFTER `read_text` returned, so a concurrent edit landing between the read and
    # the stat left the OLD content indexed under the NEW mtime -- and `stale_by`, which flags a
    # file only when its mtime is newer than the index's `newest`, then reported 0 forever, because
    # the recorded mtime already matched (or exceeded) the edited file's own. Reproduced
    # deterministically by patching `Path.read_text` to rewrite the file right after returning the
    # old text: indexed title stayed "Old title" while the file read "# New title", and `stale_by`
    # never flagged it. Taking the stat FIRST means a concurrent edit can only leave the file's real
    # mtime newer than the one recorded here -- worst case the file is flagged stale one build early
    # (safe), never missed (unsafe). The same stat also gives the size the reuse test above needs,
    # for free.
    try:
        st = path.stat()
    except OSError:
        return None
    mtime, size = st.st_mtime_ns, st.st_size
    # 🐛 [2026-10-03] (R25 acc5, 2026-10-03) restic trusted an equal path, size and restored mtime
    # and missed changed contents; the same hole was here. Reproduced: index a note saying
    # ALPHAWORD with `chamnan-recall --reindex`, rewrite it to BRAVOWORD (same byte length), restore
    # its mtime with `os.utime(p, ns=(atime, mtime))` (what `cp -p`, `rsync -a`, tar and unzip do),
    # `--reindex` again: the old entry was reused, `chamnan-recall BRAVOWORD` found nothing and
    # ALPHAWORD still matched. The inode change time (`ctime`) cannot be set by `os.utime`, so any
    # rewrite moves it. It joins the reuse key, and `build()`/`stale_by()` count it too. POSIX only:
    # on Windows `st_ctime` is the creation time and never moves on a write, so there it adds
    # nothing and no `ctime` field is stored. An entry from an older index has no `ctime` and is
    # rebuilt once -- the safe direction.
    ctime = None if os.name == "nt" else st.st_ctime_ns
    if (isinstance(prev, dict) and prev.get("mtime") == mtime and prev.get("size") == size
            and (ctime is None or prev.get("ctime") == ctime)
            and all(k in prev for k in _REUSABLE_ENTRY_FIELDS)):
        return dict(prev)
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return None
    # 🐛 [R2 agent 1, Q9] The index persists to disk and nothing scrubbed it, while `mapper.py`
    # makes the identical call before writing `MAP.md`. A credential written into a rule or a
    # session note was cached in the clear in `state/store_index.json`. It is gitignored, so this
    # is a local plaintext cache rather than a supply-chain leak — which is a reason to fix it
    # quietly, not a reason to leave it.
    text = redact.scrub(text)
    title = redact.scrub(_title_of(path, text))
    blurb = redact.scrub(_blurb_of(text, title))
    counted = {}
    for t in terms(text):
        if len(t) > 2:
            counted[t] = counted.get(t, 0) + 1
    body = dict(sorted(counted.items(), key=lambda kv: -kv[1])[:MAX_BODY_TERMS])
    return {
        "path": path.relative_to(ws_dir).as_posix(),
        "kind": kind,
        "weight": weight,
        "title": title,
        "blurb": blurb,
        # `body` is the FULL, unfiltered term-count map at this point -- `build()`'s closing pass
        # is what splits it into `body`/`ig` (kept/ignored) once `common` is known. A freshly built
        # entry has no `ig` key yet; `build()` treats that as `{}` (nothing stripped so far).
        "body": body,
        # 🐛 Kept as `text[:4000]` first, and the index came out at 547 KB against a 407 KB
        # corpus — an index larger than the thing it indexes is not an index. Only the lines
        # carrying non-ASCII are kept, because those are the only ones the substring path needs:
        # an English query is answered by the term map above. On this repository that is 2% of
        # the bytes and it keeps every Thai line that exists.
        "text": _non_ascii_lines(text),
        "mtime": mtime,
        "size": size,
        **({} if ctime is None else {"ctime": ctime}),
    }


def _tool_entries(ws):
    """Registered tools, through the module that owns that registry.

    🐛 Written first as `ws.load_json(...)`, which returns `{}` for a top-level LIST — and this
    registry is a list of 69 records, so the tools silently contributed nothing and the only symptom
    was that no result was ever a tool. `installs.py` carries a fix for the same coercion.

    🐛 Then rewritten to parse the file directly, which made this the FOURTH reader of that index
    and the only one not asking `tools_index.real_name` whether the entry names a file that is
    really there. An entry whose file was deleted by hand would have been offered as somewhere to
    look. The suite caught it by name — that predicate was unified in 2026-09-10 precisely because
    three readers each carried their own copy, and a new reader is a new member of that set the day
    it is written.
    """
    out = []
    root = ws.parent
    for rec in tools_index.load(root):
        if not isinstance(rec, dict):
            continue
        name = tools_index.real_name(root, rec.get("name", ""))
        desc = rec.get("desc") or rec.get("description") or ""
        if not name:
            continue
        counted = {}
        for t in terms(f"{name} {desc}"):
            if len(t) > 2:
                counted[t] = counted.get(t, 0) + 1
        title, blurb = str(name), str(desc)[:240]
        out.append({"path": f"tools/{name}", "kind": "tool", "weight": 2.0,
                    "title": title, "blurb": blurb, "body": counted,
                    "text": _non_ascii_lines(f"{name} {desc}"), "mtime": 0})
    return out


# A Full Detail row in `MAP.md`: "- `name(args)` — what it does". The docstring half is optional
# and two thirds of the rows here do not carry one, which is why the NAME is indexed either way.
_MAP_ROW = re.compile(r"^- `([A-Za-z_][\w.]*)\([^`]*`(?:\s+—\s+(.*))?$", re.M)
_MAP_FILE = re.compile(r"^## `([^`]+)`$", re.M)


def _symbol_entries(ws):
    """Every function and class the architecture index names, with its one-line description.

    🎯 [owner 2026-09-23, direction K] `chamnan-recall` searched the STORES — rules, decisions,
    skills — and not the code, so somebody who remembers what a function does and not what it is
    called had nothing to ask. Reading `MAP.md` rather than the source keeps the promise this
    module makes in its own docstring: a query reads one file and never walks the tree, and the
    index is rebuilt only when asked.

    Measured on this repository: MAP.md is 510 KB, 3,302 symbols, and **1,081 of them (33%) carry
    a description**. Only those are indexed — see the 🐛 below. The other two thirds would
    contribute a name, and searching by name is what `chamnan-where` already answers.

    Weight 1.0, the floor. A recorded decision that mentions a function is about that decision; the
    function's own row is a pointer to code, which is a weaker answer to "what do we already know
    about this" and must not outrank the rule that governs it.
    """
    out = []
    try:
        text = (ws / "MAP.md").read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return out
    # Which file each row belongs to: the rows follow their `## \`path\`` heading, so one pass
    # carrying the last heading seen is enough, and no row has to be matched back to a file.
    owner, seen = "", set()
    for line in text.splitlines():
        head = _MAP_FILE.match(line)
        if head:
            owner = head.group(1)
            continue
        row = _MAP_ROW.match(line)
        if not row or not owner:
            continue
        name, desc = row.group(1), (row.group(2) or "").strip()
        # 🐛 [2026-09-23] (self-measured) Indexing every symbol put the index at 119% of the files
        # it is built from — an index larger than its documents is not an index, and the corpus
        # check says so. The cut is not arbitrary: this feature exists to find a function by what
        # it DOES, and a symbol with no description cannot answer that. It would contribute its
        # name, and searching by name is what the user already had. 1,081 of 3,302 rows here carry
        # a description; those are the ones that add the capability.
        if not desc:
            continue
        key = f"{owner}:{name}"
        if key in seen:
            continue
        seen.add(key)
        counted = {}
        for term in terms(f"{name} {desc}"):
            if len(term) > 2:
                counted[term] = counted.get(term, 0) + 1
        title, blurb = f"{name}()", desc[:240]
        row = {"path": owner, "kind": "symbol", "weight": 1.0,
               "title": title, "blurb": blurb, "body": counted}
        if desc:
            # Only a described symbol can carry non-ASCII worth indexing; a bare identifier is
            # ASCII by definition and the field would be an empty list on every row.
            row["text"] = _non_ascii_lines(f"{name} {desc}")
        out.append(row)
    return out


def sources(ws):
    """Every file this index is built FROM, so a cost claim about it can be measured honestly.

    🐛 [2026-09-23] (self-measured) The suite checks that the index does not cost more than the
    documents it indexes, and derived those documents from `KINDS`. `MAP.md` became a source when
    symbols were indexed and is not in `KINDS`, so the ratio broke by construction: the numerator
    grew and the denominator could not. One definition, used by `build()`'s sources and by the
    check, is what stops the two drifting again.
    """
    out = [p for folder, _k, _w in KINDS for p in paths_for(ws, folder)]
    m = ws / "MAP.md"
    if m.is_file():
        out.append(m)
    return out


# Which `KINDS` entries are single-file-per-entry, so a stat can decide staleness cheaply. Tool
# and symbol entries have no such per-entry file -- see the note on `build()`'s `previous` below.
_STORE_KINDS = {kind for _folder, kind, _weight in KINDS}


def build(ws, previous=None):
    """Walk the stores once and return the index. The only function here that reads them.

    🎯 [2026-09-28] (R122 acc2, 2026-09-28) Profiled at 14.2s on this repository's own workspace
    (1,328 entries), 12.6s (89%) inside `redact.scrub` -- called once per store note on every
    build, so `chamnan-recall --reindex` re-scrubbed 1,327 unchanged notes to pick up the one that
    changed. `previous` is the last-built index, when the caller has one; `_entry()` reuses a
    store note's previous entry outright when its path, mtime and size all still match (see its
    own docstring), skipping the read and the scrub. Only store notes (`_STORE_KINDS`) are
    reused: tool entries come from one shared `tools/index.json` and carry no real per-entry
    mtime (it is a constant `0` today), and symbol entries come from parsing the whole of
    `MAP.md` in one pass with no per-symbol file to stat -- neither has the per-entry file this
    cheap test needs, so both are rebuilt in full on every call, exactly as before this change.
    A fresh build (`previous=None`, or a `previous` that is not a dict) reuses nothing and
    behaves exactly as it always has.

    🐛 [2026-09-28] (R122 acc2, 2026-09-28) The first version of this reuse made document
    frequency an ESTIMATE for a reused entry, by assuming it still carried every term the
    PREVIOUS build had ever called common. Measured wrong two ways: a term that later fell below
    the 60% bar could never be released again, because every reused entry kept voting for it
    forever; and a reused SHORT note (originally <=30 raw terms) could be miscounted as a
    qualifying "document" once its stripped terms were assumed back in, changing `n` itself. Both
    are fixed by never estimating: every store-note entry now also carries `"ig"` -- exactly the
    `{term: count}` pairs `common` removed from its `body` last time, `{}` when none were. `full =
    {**e["body"], **e.get("ig", {})}` reconstructs each entry's TRUE, complete term-count map
    (a freshly built entry has no `"ig"` yet, so `full` is just its `body`, unchanged from
    before). Document frequency, `n`, and the final `body`/`ig` split are all computed from `full`
    for every entry, reused or fresh -- exact, not approximated, so an index rebuilt after however
    many incremental passes always equals one built from scratch of the same state. Measured: 78
    of this workspace's store entries carry a non-empty `ig` (1,164 (entry, term) pairs total,
    about 17 KB of JSON against a 1.1 MB index) -- cheap to carry on every entry that can use it.

    🐛 [2026-09-28] (R122 acc2, 2026-09-28) `ig` was first set on EVERY entry this function
    returns, tool and symbol included, "for consistency" -- but tool and symbol entries are never
    reused (see above: neither has a cheap per-entry staleness test), so nothing ever reads their
    `ig` back. On this workspace that was 41 KB of the 1.49 MB index carrying data no code path
    consults. `ig` is now set ONLY on store-note entries (`kind in _STORE_KINDS`, the only kind
    the closing loop below ever puts it on); a tool or symbol entry carries no `ig` key at all.
    """
    prev_by_path = {}
    if isinstance(previous, dict) and (previous.get("terms") != TERMS_VERSION
                                       or previous.get("scrubber") != scrubber_id()):
        previous = None
    if isinstance(previous, dict):
        for e in previous.get("entries", []) or []:
            if (isinstance(e, dict) and e.get("kind") in _STORE_KINDS
                    and isinstance(e.get("path"), str)):
                prev_by_path[e["path"]] = e

    entries, newest = [], 0
    for folder, kind, weight in KINDS:
        for path in paths_for(ws, folder):
            rel = path.relative_to(ws).as_posix()
            e = _entry(ws, path, kind, weight, prev_by_path.get(rel))
            if e:
                entries.append(e)
                # `ctime` counts too on POSIX (see `_entry`): `stale_by` compares against this.
                newest = max(newest, e["mtime"], e.get("ctime", 0))
    entries += _tool_entries(ws)
    entries += _symbol_entries(ws)

    # 3. Drop the words that cannot discriminate, derived rather than listed. A term in most of the
    #    documents tells a reader nothing about which one to open, and without this the longest
    #    document wins every query on the strength of "the" and "this". A hand-written stopword list
    #    would be the enumerated-set mistake this repository keeps paying for, and an English one
    #    would be wrong for a repository whose notes are half Thai.
    # Document frequency over the DOCUMENTS, not over every entry: 69 of these are registered
    # tools contributing a name and one sentence each, and counting them quadrupled the denominator
    # so that only the single word "the" cleared the bar.
    #
    # `full` is each entry's TRUE, unfiltered term-count map -- see the 🐛 above for why this must
    # never be estimated. `full_by_entry` is built once and read three times (the `docs` gate, the
    # `seen` tally, the closing split) so nothing here recomputes it, and so a later reader cannot
    # accidentally fall back to the approximation by reading `e["body"]` directly at this stage.
    full_by_entry = [(e, {**e["body"], **e.get("ig", {})}) for e in entries]

    docs = [full for _e, full in full_by_entry if len(full) > 30]
    n = len(docs) or 1
    seen = {}
    for full in docs:
        for term in full:
            seen[term] = seen.get(term, 0) + 1
    common = {t for t, c in seen.items() if c > n * 0.6}
    for e, full in full_by_entry:
        e["body"] = {t: c for t, c in full.items() if t not in common}
        # `ig` only on store notes: they are the only kind `_entry()` ever reuses, so a tool or
        # symbol entry carrying its own `ig` would be data nothing reads back.
        if e.get("kind") in _STORE_KINDS:
            e["ig"] = {t: c for t, c in full.items() if t in common}
    return {"entries": entries, "newest": newest, "count": len(entries),
            "ignored": sorted(common), "terms": TERMS_VERSION,
            "scrubber": scrubber_id()}


def stale_by(ws, index):
    """How many store files are newer than the index. Reads mtimes (and ctimes on POSIX), never contents.

    A directory listing is not a scan: `stat` on 55 paths is microseconds and reads no bytes, which
    is the difference between reporting staleness and paying for a rebuild to discover it.
    """
    newest = index.get("newest", 0) if isinstance(index, dict) else 0
    # An index scrubbed by another redactor is stale in full (R73 acc4): every path counts.
    all_stale = isinstance(index, dict) and index.get("scrubber") != scrubber_id()
    behind = 0
    for folder, _kind, _w in KINDS:
        for path in paths_for(ws, folder):
            try:
                st = path.stat()
                # The inode change time catches a rewrite whose mtime was restored afterward
                # (R25 acc5, see `_entry`); on Windows it is the creation time, so it is skipped.
                if all_stale or st.st_mtime_ns > newest or (os.name != "nt" and st.st_ctime_ns > newest):
                    behind += 1
            except OSError:
                continue
    return behind


def _hits(entry, wanted, phrases, idf=None, pidf=None):
    """Score one entry, and the fields that earned it. Returns `(score, why)`.

    `idf` is an optional `{term: weight}` for terms in `wanted`. It is `None` for every caller
    that predates it, and a missing term inside a supplied dict scores at 1.0 either way, so
    nothing but `query()` itself has to change.

    `pidf` is the same idea for `phrases` (the non-ASCII, substring side of a query) -- an
    optional `{phrase: weight}`. `None` for every caller that predates it.

    🐛 [2026-09-27] (R53, 2026-09-27) `phrases` (the non-ASCII, substring side of a query) are
    NFKC-normalised by `query()` before they get here, but the entry's own `title`/`blurb`/`text`
    were compared un-normalised -- `build()` never normalises what it stores. NFKC decomposes Thai
    SARA AM (U+0E33, ำ) into NIKHAHIT + SARA AA (U+0E4D U+0E32), so a phrase containing ำ no longer
    matched the very same character stored whole. Measured on this workspace's own index (1,322
    entries, 44 containing ำ): the queries ทำ, จำ, คำ, น้ำ each returned 0 hits. Fixed by
    normalising the field text at compare time too (once per field per call, not once per phrase);
    `build()`'s stored shape is unchanged, so old indexes keep working.

    🎯 [2026-09-28] (R96 acc4, 2026-09-28) This was calling `terms(value.lower())` on every entry's
    title and blurb on EVERY query, even though a title/blurb only changes when its document does.
    Measured (cProfile, 3 queries against this repository's 1,313-entry, 1.1 MB index): 7,878
    `terms()` calls and ~36,000 `stem()` calls per query, most of the ~362 ms scoring time (index
    load itself was ~62 ms). The FIX for that measurement (R122 acc2) was to precompute
    `terms(title.lower())`/`terms(blurb.lower())` at `build()` time and store them as `"tt"`/`"bt"`
    on the entry -- reversed below.

    🐛 [2026-09-28] (R122 acc2, 2026-09-28) `"tt"`/`"bt"` cost real bytes on every entry for a gain
    that does not need storage at all: measured on this workspace, storing them took the index from
    82% of the corpus (before commit b247174) to 104% at HEAD -- an index larger than the documents
    it indexes, which the suite already guards and had gone quietly over. Replaced with an EXACT
    prefilter that needs no storage. Every term `terms(value.lower())` can produce is a literal
    substring of `norm = NFKC(value.lower())`, computed once per field per call below: the whole
    tokens come straight from `_WORD.findall(norm)` (verbatim substrings of `norm` by construction),
    and the underscore/dot/dash/camelCase compound parts `_HUMP` adds are themselves substrings of
    the whole token they were split from, hence of `norm` too. `stem()` is never in this path --
    `query()`'s stemmed `extra_terms` are literal words pulled from some document's OWN `body`, not
    stems, and they reach `_hits` through the ordinary `wanted` argument. So when NO wanted word is
    a substring of `norm`, none of them can be a term of this field, and `terms()` need not run at
    all; when at least one might be, `terms()` runs once and every wanted word is still checked
    individually (a substring match is necessary, not sufficient -- "cat" inside "category" is not
    a term of it). Verified empirically, not just argued: every term of every title/blurb in this
    workspace's own index (2,658 (entry, field) pairs) is a substring of that field's `norm`, and a
    battery of synthetic cases (German ß, Thai combining marks, CJK, ligatures, fullwidth digits,
    camelCase, snake_case, dotted/dashed compounds) turned up none that were not. An index that
    still carries `"tt"`/`"bt"` from before this change is read exactly like one that never did --
    neither field is read here any more, so old data is inert, not consulted.
    """
    score, why = 0.0, []
    fields = (("title", entry.get("title", "")), ("blurb", entry.get("blurb", "")))
    for name, value in fields:
        norm_lower = fold(value)
        if any(w in norm_lower for w in wanted):
            field_terms = terms(value.lower())
            for w in wanted:
                if w in field_terms:
                    score += FIELD_WEIGHT[name] * (idf.get(w, 1.0) if idf else 1.0)
                    why.append(name)
        norm_value = fold(value)
        for p in phrases:
            if p in norm_value:
                score += FIELD_WEIGHT[name] * (pidf.get(p, 1.0) if pidf else 1.0)
                why.append(name)
    body = entry.get("body", {})
    for w in wanted:
        n = body.get(w, 0)
        if n:
            # Diminishing: a word used forty times is not forty times more relevant than one used
            # four times, and without this the longest document wins every query.
            score += FIELD_WEIGHT["body"] * (1 + min(n, 20) ** 0.5) * (idf.get(w, 1.0) if idf else 1.0)
            why.append("body")
    text = entry.get("text", "")
    # Only phrases read it, and folding a long body is the costliest step here.
    norm_text = fold(text) if phrases else ""
    for p in phrases:
        if p in norm_text:
            score += FIELD_WEIGHT["body"] * 2 * (pidf.get(p, 1.0) if pidf else 1.0)
            why.append("body")
    return score * float(entry.get("weight", 1.0)), why


def query(index, words, limit=6):
    """Rank entries against `words`. Pure: takes a loaded index and reads nothing.

    `words` is what the user typed. ASCII terms are matched as words; anything else is matched as a
    substring, whole, for the reason in this module's docstring.
    """
    raw = [w for w in (words or []) if w.strip()]
    wanted, phrases = [], []
    for w in raw:
        fw = fold(w)
        if _ascii(fw):
            wanted += [t for t in terms(fw) if len(t) > 1]
        else:
            phrases.append(fw)
    if not wanted and not phrases:
        return []

    # 🐛 [R2 agent 1, Q8] `index.get("entries", [])` guards a non-dict index and not a non-list
    # `entries`, so `{"entries": "not-a-list"}` iterated a STRING and `{"entries": [1, 2, None]}`
    # reached `.get` on an int — both a raw `AttributeError` traceback and exit 1, past the
    # command's own "no index yet" sentence. A file on disk is a shape nobody promised.
    raw = index.get("entries") if isinstance(index, dict) else None
    entries = raw if isinstance(raw, list) else []

    # 🐛 [2026-09-30] (R189 acc4, 2026-09-30) `build()` derives the words present in most documents
    # (stored as `"ignored"`) and strips them from every entry's body, but `query()` kept them in the
    # query. Two consequences: (1) `_hits` still scored them in every entry's title and blurb, and
    # (2) because they were stripped from the bodies their document frequency in the idf loop below
    # is 0, so they received the HIGHEST idf of any word. Measured: `chamnan-recall recipe for banana
    # bread` returned 6 entries, 5 of them matched only on the word `for` in a title. The phrase
    # (non-ASCII) side is untouched: `ignored` holds ASCII terms produced by `terms()`.
    # A query made ONLY of such words keeps them: they are in most documents, and an empty result
    # would make `chamnan-recall` say the thing "is not recorded" -- the opposite of the truth.
    common = index.get("ignored") if isinstance(index, dict) else None
    if isinstance(common, list) and common:
        common = {t for t in common if isinstance(t, str)}
        wanted = [w for w in wanted if w not in common] or wanted

    # 🐛 [2026-09-26] (R173, 2026-09-26) Every wanted word added the same weight to a score
    # whether it turned up in 3 entries or 800, so a query mixing a rare word with a common one let
    # the common word's sheer bulk in one document outrank the rare word's exact hit somewhere else.
    # Measured on this workspace's own index (`.chamnan/logs/recall_known_item.py`, 219 known-item
    # trials of "find the entry these 3 of its own body words came from"): MRR 0.578 -> 0.642,
    # top1 39.7% -> 46.1%, top3 72.1% -> 79.0%; the Thai/substring `phrases` path is untouched.
    # IDF is computed here, for the wanted ASCII terms only (cheap -- never the whole vocabulary),
    # and is never written back into the index: `build()`'s output on disk does not change shape.
    docs_with_body = [e for e in entries if isinstance(e, dict) and e.get("body")]
    n_docs = len(docs_with_body)
    idf = {}
    for w in wanted:
        df = sum(1 for e in docs_with_body if w in e["body"])
        idf[w] = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))

    # 🐛 [2026-09-27] (R8 acc2, 2026-09-27) Every Thai/non-ASCII `phrases` hit added the same flat
    # `FIELD_WEIGHT[...]` regardless of how many entries carried it, while ASCII `wanted` terms got
    # the idf weighting just above -- so the substring side of a query had no way to prefer a rare
    # phrase over a common one. Measured on this workspace's own index
    # (`.chamnan/logs/recall_thai_idf_ab.py`, known-item trials with 4-7 char Thai substrings): MRR
    # 0.921 -> 0.971, top1 85.3% -> 95.1%, top6 unchanged at 100%; with whole Thai runs 0.853 ->
    # 0.955. `df` is entries whose NFKC-normalised text/title/blurb contains the phrase; `N` is the
    # number of dict entries. Never written back into the index.
    all_entries = [e for e in entries if isinstance(e, dict)]
    n_entries = len(all_entries) or 1
    pidf = {}
    if phrases:
        norm_fields = [
            (fold(e.get("text", "")),
             fold(e.get("title", "")),
             fold(e.get("blurb", "")))
            for e in all_entries
        ]
        for p in phrases:
            df = sum(1 for t, ti, b in norm_fields if p in t or p in ti or p in b)
            pidf[p] = math.log(1 + (n_entries - df + 0.5) / (df + 0.5))

    # 🎯 [2026-09-27] (R91 acc2, 2026-09-27) An exact word match found only the entries carrying
    # that literal form -- `boundaries` never found the 11 entries that only say `boundary`, and the
    # redact/redactor/redaction/redacted family spread 24 entries over four forms nobody's query
    # covered at once. Every OTHER indexed form sharing a wanted word's stem is now scored too, at
    # half weight (an exact match is still the better signal), inheriting the idf of the wanted word
    # it came from. Measured (`.chamnan/logs/recall_word_forms_ab.py`): queries in a different form
    # MRR 0.414 -> 0.531, top6 65.6% -> 81.2%; exact-word queries MRR 0.651 -> 0.635 (top6 90.0% ->
    # 89.0%) -- accepted trade.
    extra_terms = {}
    if wanted:
        wanted_stems = {stem(w) for w in wanted}
        forms_of_stem = {}
        # 🎯 [2026-10-02] (R33 acc5, 2026-10-02) This stemmed every body term of every entry, so a
        # query paid 35,998 `stem()` calls on this repository's 1,337-entry index although only
        # 8,825 of those terms are distinct. Stemming the distinct vocabulary once is a lookup
        # instead of a repeated scan: median query time 90-100 ms -> 52-55 ms, with identical
        # results over a seeded battery of 64 queries.
        vocab = set()
        for e in docs_with_body:
            vocab.update(e["body"])
        for t in vocab:
            st = stem(t)
            if st in wanted_stems:
                forms_of_stem.setdefault(st, set()).add(t)
        for w in wanted:
            for form in forms_of_stem.get(stem(w), ()):
                if form != w and form not in extra_terms:
                    extra_terms[form] = idf.get(w, 1.0)

    scored = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        s, why = _hits(e, wanted, phrases, idf, pidf)
        if extra_terms:
            fs, fwhy = _hits(e, list(extra_terms), [], extra_terms)
            s += 0.5 * fs
            why += fwhy
        if s > 0:
            scored.append((s, e, sorted(set(why))))
    # Score first, then kind weight is already in the score, then path for a stable order between
    # ties -- an unstable order makes two runs of the same query disagree for no reason.
    scored.sort(key=lambda t: (-t[0], t[1]["path"]))
    return scored[:limit]


def why_line(entry, why, wanted, phrases):
    """One line saying what matched, so a reader can judge the hit without opening the file."""
    where = " and ".join(w for w in ("title", "blurb", "body") if w in why) or "body"
    needles = [w for w in wanted if w in terms(entry.get("title", "") + " " +
                                               entry.get("blurb", ""))] or wanted
    # 🐛 [2026-09-27] (R53, 2026-09-27) same NFKC mismatch as `_hits` -- normalise the stored text
    # before comparing it against a phrase that `query()` already normalised.
    found = [p for p in phrases if p in fold(entry.get("text", ""))]
    # De-duplicated in order: a term that matched the title AND the body was being named twice,
    # which reads as two separate reasons to open the file when it is one.
    seen, named_terms = set(), []
    for w in needles + found:
        if w not in seen:
            seen.add(w)
            named_terms.append(w)
    named = ", ".join(named_terms[:3])
    return f"matched {named} in the {where}" if named else f"matched in the {where}"
