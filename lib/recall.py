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
_ASCII_ONLY = re.compile(r"\A[\x00-\x7f]*\Z")


def _ascii(text):
    return bool(_ASCII_ONLY.match(text))


def terms(text):
    """The ASCII words of `text`, lowercased. Non-ASCII is deliberately not tokenised here."""
    return _WORD.findall(unicodedata.normalize("NFKC", text).lower())


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


def _non_ascii_lines(text, cap=4000):
    """Only the lines a substring query could ever need."""
    return "\n".join(ln for ln in text.split("\n") if _needs_substring(ln))[:cap]


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


def build(ws):
    """Walk the stores once and return the index. The only function here that reads them."""
    entries, newest = [], 0
    for folder, kind, weight in KINDS:
        base = ws / folder
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.md")):
            e = _entry(ws, path, kind, weight)
            if e:
                entries.append(e)
                newest = max(newest, e["mtime"])
    entries += _tool_entries(ws)

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
        base = ws / folder
        if not base.is_dir():
            continue
        for path in base.rglob("*.md"):
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
