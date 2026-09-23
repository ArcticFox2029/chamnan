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
import re
import unicodedata

import redact
import tools_index
import workspace as ws

INDEX = "state/store_index.json"

# What a store IS, in the order a reader should see them. A rule outranks a lesson outranks a
# session note, because a rule is a standing constraint and a session note is one day's context.
#
# The last two entries name a specific FILE rather than a folder -- see `paths_for()` just below
# for what that changes. `state/research/` also holds five uncurated round logs, a generated
# INDEX/STATE_OF_THE_RESEARCH pair, and a 459-file `old/` archive; only these two curated files are
# meant to answer "should I research X", so they are addressed by name rather than swept in with
# everything beside them.
#
# Weighed by how directly each answers that question. A dead end is the strongest possible
# answer -- someone already asked and measured why not, which reads as closer to a settled
# DECISION than an open one, so it sits just under `rule` and just over `decision`/`lesson`. A
# backlog entry answers the weaker "is this already queued": the question stays open, so it sits
# between `thread` (one day's open context) and `skill` (a followed procedure) rather than beside
# either of the settled kinds above it.
KINDS = (
    ("memory/rules", "rule", 3.0),
    ("memory/decisions", "decision", 2.5),
    ("memory/lessons", "lesson", 2.5),
    ("skills", "skill", 2.0),
    ("threads", "thread", 1.5),
    ("sessions", "session", 1.0),
    ("state/research/chamnan_research_dead_ends.md", "dead_end", 2.75),
    ("state/research/chamnan_research_backlog.md", "backlog", 1.75),
)

# Where a match is worth more. A term in the title is the document being ABOUT that thing; a term
# in the body may be an aside.
FIELD_WEIGHT = {"title": 6.0, "blurb": 3.0, "body": 1.0}

MAX_BODY_TERMS = 400        # per document, by frequency: the tail of a long skill is noise
# Sections, not per-document: measured on this repository's own two research files, a section
# averages ~140 unique terms and rarely exceeds 400 -- so `MAX_BODY_TERMS` applied per section
# barely trims anything, and 99 short sections then cost nearly as much JSON as their 13,800
# uncapped unique terms combined, instead of the ~400-term compression the constant above exists
# to give a single document. `MAX_SECTION_BODY_TERMS` gives each section the same kind of haircut,
# sized to what a SECTION actually needs rather than a whole file: measured to keep the index
# comfortably under both the corpus it indexes and roughly half again its pre-sectioning size.
MAX_SECTION_BODY_TERMS = 60
SNIPPET = 90

_WORD = re.compile(r"[a-z0-9][a-z0-9_.-]*")
# Only a compound is worth splitting: a plain word costs a second regex pass for nothing, and
# this runs over every line of every store on a rebuild.
_SPLITTABLE = re.compile(r"[_.\-]|[a-z][0-9]|[0-9][a-zA-Z]|[a-z][A-Z]")
# The same shape as `_WORD` with the case left alone, because a hump is only
# visible before `lower()` and `_WORD` is applied to lowered text by contract.
_WORD_ANY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
_ASCII_ONLY = re.compile(r"\A[\x00-\x7f]*\Z")


def _ascii(text):
    return bool(_ASCII_ONLY.match(text))


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
    norm = unicodedata.normalize("NFKC", text)
    # The whole tokens, exactly as before this change: every existing caller and every stored index
    # depends on this list, and the parts are ADDED to it rather than replacing anything.
    out = _WORD.findall(norm.lower())
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
    """The store file(s) one `KINDS` entry resolves to.

    Most entries name a directory and mean "every `.md` file under it". A `KINDS` entry can also
    name one file directly -- `state/research/`'s two curated stores are why this exists -- and
    that file is returned on its own, not swept together with whatever else sits beside it.
    """
    base = ws_dir / folder
    if base.is_dir():
        return sorted(base.rglob("*.md"))
    if base.is_file():
        return [base]
    return []


_SECTION_HEADING = re.compile(r"^## (.+)$", re.MULTILINE)


def _sectioned_entries(ws_dir, path, kind, weight):
    """One entry per `## ` heading in `path`, instead of one entry for the whole file.

    Built for the two curated files in `state/research/`: each is well over 100 KB, so indexed
    whole either one would out-score nearly every other document on any query while telling the
    reader nothing about WHERE in the file the answer sits. Both files already carry their own
    `## `-heading quick index for exactly that reason -- the file's own evidence that the section,
    not the document, is the unit a reader wants -- so this reuses that unit rather than inventing
    another.
    """
    if not ws.inside(path, ws_dir):
        return []
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return []
    text = redact.scrub(text)
    heads = list(_SECTION_HEADING.finditer(text))
    mtime = path.stat().st_mtime_ns
    rel = path.relative_to(ws_dir).as_posix()
    out = []
    for i, m in enumerate(heads):
        heading = m.group(1).strip()
        # The file's own table of contents, not a section of content: indexed as an entry it would
        # repeat every other heading's title inside one document, which then out-ranks the very
        # section it points at on any query that names more than one angle.
        if heading.lower().startswith("quick index"):
            continue
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body_text = text[m.end():end]
        blurb = redact.scrub(_blurb_of(body_text, heading))
        counted = {}
        for t in terms(body_text):
            if len(t) > 2:
                counted[t] = counted.get(t, 0) + 1
        body = dict(sorted(counted.items(), key=lambda kv: -kv[1])[:MAX_SECTION_BODY_TERMS])
        out.append({
            # `#N` rather than the heading text: a fragment carrying the full heading would store
            # it twice (once here, once in `title`) for every one of ~140 sections across the two
            # files, which is the kind of per-entry cost this index cannot absorb without breaking
            # the "stays under the corpus" property tests hold it to.
            "path": f"{rel}#{i + 1}",
            "kind": kind,
            "weight": weight,
            "title": heading,
            "blurb": blurb,
            "body": body,
            "text": _non_ascii_lines(body_text),
            "mtime": mtime,
        })
    return out


def _file_entries(ws_dir, path, kind, weight):
    """`_entry()`, wrapped to return a list -- so `build()` can treat it like `_sectioned_entries`."""
    e = _entry(ws_dir, path, kind, weight)
    return [e] if e else []


def _entry(ws_dir, path, kind, weight):
    """One document, reduced to what a query needs and nothing it does not."""
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
        "body": body,
        # 🐛 Kept as `text[:4000]` first, and the index came out at 547 KB against a 407 KB
        # corpus — an index larger than the thing it indexes is not an index. Only the lines
        # carrying non-ASCII are kept, because those are the only ones the substring path needs:
        # an English query is answered by the term map above. On this repository that is 2% of
        # the bytes and it keeps every Thai line that exists.
        "text": _non_ascii_lines(text),
        "mtime": path.stat().st_mtime_ns,
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
        out.append({"path": f"tools/{name}", "kind": "tool", "weight": 2.0,
                    "title": str(name), "blurb": str(desc)[:240], "body": counted,
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
    a description**. The other two thirds are indexed on their name alone, which the compound
    splitting in `terms()` makes searchable — `apply_promo_code` answers to `promo`.

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
        row = {"path": owner, "kind": "symbol", "weight": 1.0,
               "title": f"{name}()", "blurb": desc[:240], "body": counted}
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


def build(ws):
    """Walk the stores once and return the index. The only function here that reads them."""
    entries, newest = [], 0
    for folder, kind, weight in KINDS:
        # A `KINDS` entry naming one file directly (not a directory) is split into sections --
        # see `paths_for()` and `_sectioned_entries()`.
        sectioned = not (ws / folder).is_dir()
        for path in paths_for(ws, folder):
            new = _sectioned_entries(ws, path, kind, weight) if sectioned \
                else _file_entries(ws, path, kind, weight)
            for e in new:
                entries.append(e)
                newest = max(newest, e["mtime"])
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
    docs = [e for e in entries if len(e["body"]) > 30]
    n = len(docs) or 1
    seen = {}
    for e in docs:
        for term in e["body"]:
            seen[term] = seen.get(term, 0) + 1
    common = {t for t, c in seen.items() if c > n * 0.6}
    for e in entries:
        e["body"] = {t: c for t, c in e["body"].items() if t not in common}
    return {"entries": entries, "newest": newest, "count": len(entries),
            "ignored": sorted(common)}


def stale_by(ws, index):
    """How many store files are newer than the index. Reads mtimes only, never contents.

    A directory listing is not a scan: `stat` on 55 paths is microseconds and reads no bytes, which
    is the difference between reporting staleness and paying for a rebuild to discover it.
    """
    newest = index.get("newest", 0) if isinstance(index, dict) else 0
    behind = 0
    for folder, _kind, _w in KINDS:
        for path in paths_for(ws, folder):
            try:
                if path.stat().st_mtime_ns > newest:
                    behind += 1
            except OSError:
                continue
    return behind


def _hits(entry, wanted, phrases):
    """Score one entry, and the fields that earned it. Returns `(score, why)`."""
    score, why = 0.0, []
    fields = (("title", entry.get("title", "")), ("blurb", entry.get("blurb", "")))
    for name, value in fields:
        low = value.lower()
        for w in wanted:
            if w in terms(low):
                score += FIELD_WEIGHT[name]
                why.append(name)
        for p in phrases:
            if p in value:
                score += FIELD_WEIGHT[name]
                why.append(name)
    body = entry.get("body", {})
    for w in wanted:
        n = body.get(w, 0)
        if n:
            # Diminishing: a word used forty times is not forty times more relevant than one used
            # four times, and without this the longest document wins every query.
            score += FIELD_WEIGHT["body"] * (1 + min(n, 20) ** 0.5)
            why.append("body")
    text = entry.get("text", "")
    for p in phrases:
        if p in text:
            score += FIELD_WEIGHT["body"] * 2
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
        if _ascii(w):
            wanted += [t for t in terms(w) if len(t) > 1]
        else:
            phrases.append(unicodedata.normalize("NFKC", w))
    if not wanted and not phrases:
        return []

    # 🐛 [R2 agent 1, Q8] `index.get("entries", [])` guards a non-dict index and not a non-list
    # `entries`, so `{"entries": "not-a-list"}` iterated a STRING and `{"entries": [1, 2, None]}`
    # reached `.get` on an int — both a raw `AttributeError` traceback and exit 1, past the
    # command's own "no index yet" sentence. A file on disk is a shape nobody promised.
    raw = index.get("entries") if isinstance(index, dict) else None
    scored = []
    for e in raw if isinstance(raw, list) else []:
        if not isinstance(e, dict):
            continue
        s, why = _hits(e, wanted, phrases)
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
    found = [p for p in phrases if p in entry.get("text", "")]
    # De-duplicated in order: a term that matched the title AND the body was being named twice,
    # which reads as two separate reasons to open the file when it is one.
    seen, named_terms = set(), []
    for w in needles + found:
        if w not in seen:
            seen.add(w)
            named_terms.append(w)
    named = ", ".join(named_terms[:3])
    return f"matched {named} in the {where}" if named else f"matched in the {where}"
