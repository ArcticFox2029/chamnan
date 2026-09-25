"""Knowledge that names a file, pushed at the moment that file is opened.

`chamnan-impact` answers "what breaks if I change this" and is the most obviously useful command
here. Measured on the workspace this plugin is developed against, over ten days: it was run **zero
times** — by the person who wrote it, in the repository it was written for. Every other query
command scored the same. `chamnan-map` 3, `chamnan-report` 1, `chamnan-timeline` 1, the remaining
six all 0.

The honest reading of that is not "nobody wants this". It is that a CLI is the wrong surface for it.
The caller is a model, and a model does not stop before an edit and think *"I should run
chamnan-impact first"* — remembering to ask is exactly the work this plugin exists to remove. So the
knowledge stops waiting to be asked for and arrives with the file instead.

**What it matches, and what it deliberately does not.** An entry is related to a file if its body
text names the file — the file's basename WITH its extension, or its path. That is the cheap design
already accepted over a `files:` front-matter field: a text match that is too noisy is cheap to
learn from and cheap to abandon, while a new required field on every existing entry is neither.
The extension is not decoration; it is the whole guard. A bare stem match on `state.py` would fire
on every sentence containing the word "state", and a pointer that fires on everything is read as
noise within a day and then ignored forever.

**Silence on no match is correct here.** The prompt-router version of this idea replaces something a
session used to get unconditionally, so a miss there loses information and it must fail toward
injecting. This one only ever adds, on a surface that fires many times per session, so a miss costs
nothing and a false positive costs attention. The two halves of the same feature fail in opposite
directions on purpose.

**Once per file per session.** Editing one file ten times must not print the same three lines ten
times. The pointer is a fact about the file, not about the edit.

**It has to be cheap enough to run on every Read and Edit.** MAP.md on the development repository is
320k characters; the memory and skill corpus is small markdown. Budget is stated rather than
assumed — see MAX_MS in the hook, which prints nothing rather than run long.
"""
import json
import re
import time
from pathlib import Path


import md
import workspace as ws
import mdblock

# Scanned in the order they are listed, which is the order they are printed: the reason first, then
# the procedure, then the line of work. `label` is what the reader sees.
SOURCES = (
    ("memory/decisions", "decision"),
    ("memory/incidents", "incident"),   # not a store yet; joins automatically the day it exists
    ("memory/lessons", "lesson"),
    ("memory/rules", "rule"),
    ("skills", "procedure"),
    ("threads", "thread"),
)

_CLOSED_THREAD = re.compile(r"^\*\*Status:\*\*\s*closed\b", re.M | re.I)
MAX_HITS = 4          # per file; past this the pointer is a wall of text and stops being read
MAX_BYTES = 60_000    # per entry; a knowledge file larger than this is not a knowledge file
SEEN_DIR = "logs"
SEEN_PREFIX = "pointer_seen"
SEEN_MAX_AGE = 2 * 24 * 3600     # a store older than this belongs to a session that is long gone
EVENT_LOG = "logs/pointer.jsonl"

_FRONT_NAME = re.compile(r"^description:\s*(.+?)\s*$", re.M)  # applied to front matter ONLY
# See mdblock.HEADING_SPACE — `[ \t]` misses the space a CJK keyboard types.
_HEADING = re.compile(r"^#{1,3}" + mdblock.HEADING_SPACE + r"+(.+?)\s*$", re.M)
# An HTML-comment description, which is how the skills in this workspace carry theirs.
_COMMENT_DESC = re.compile(r"<!--\s*description:\s*(.+?)\s*-->", re.S)


_BOUNDARY_CACHE = {}


def _title(text, fallback):
    """One short line naming what an entry is, from whichever convention it happens to use.

    Each convention is looked for only where it is actually valid. `description:` counts inside a
    real front-matter block and nowhere else -- searching the whole document once had this titling
    an entry with a fragment of its own prose that happened to start with the word. A heading is a
    heading only outside a fenced code block, for the same reason.
    """
    front = md.front_matter(text)
    if front:
        m = _FRONT_NAME.search(front)
        if m:
            return mdblock.as_quoted(m.group(1), 96)
    m = _COMMENT_DESC.search(text)
    if m:
        return mdblock.as_quoted(m.group(1), 96)
    heads = md.headings(_HEADING, text)
    if heads:
        return mdblock.as_quoted(heads[0].group(1), 96)
    return fallback


def needles(rel_path):
    """The strings whose presence in an entry counts as naming this file.

    Both are extension-bearing on purpose (see the module docstring). The path is included as well
    as the basename because two files can share a name, and an entry that spelled out the full path
    meant that one.
    """
    # 🐛 `lstrip("./")` strips a character SET, so `.github/workflows/ci.yml` became
    # `github/workflows/ci.yml` and the tier-0 full-path pointer could never fire for any file in a
    # dot-directory — nor at all for a root dotfile like `.env.example`, whose whole name is eaten.
    # Only a leading `./` is a relative-path marker.
    rel = str(rel_path).replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    rel = rel.lstrip("/")
    base = rel.rsplit("/", 1)[-1]
    out = [rel]
    if base != rel and "." in base:
        out.append(base)
    return [n for n in out if len(n) >= 4]


def _glob_covers(glob, rel):
    """True when `rel` is one of the paths `Path.glob(glob)` would return, judged lexically.

    Lexical rather than by touching the filesystem: this runs on every Read, and the question is
    whether the rule's pattern NAMES this path, not whether the path happens to exist right now.
    `**` crosses directories, a single `*` does not -- the same split Path.glob makes.
    """
    raw = glob.strip()
    # A trailing slash means a DIRECTORY, and a rule written `in `src/`` means everything under it.
    # Path.glob would return only the directory itself; the intent in a Check trailer is the tree,
    # and the code this replaces honoured that with a `/*` fallback. Kept, made recursive.
    if raw.endswith("/"):
        prefix = raw.strip("/")
        return bool(prefix) and rel.startswith(prefix + "/")
    pattern = raw.strip("/")
    if not pattern:
        return False
    parts = pattern.split("/")
    rx = []
    for part in parts:
        if part == "**":
            rx.append(r"(?:[^/]+/)*")
            continue
        piece = ""
        for ch in part:
            piece += "[^/]*" if ch == "*" else ("[^/]" if ch == "?" else re.escape(ch))
        rx.append(piece + "/")
    joined = "".join(rx).rstrip("/")
    if joined.endswith("(?:[^/]+/)*"):
        joined += ".*"
    return re.fullmatch(joined, rel) is not None


# Trailers parsed once per record body rather than once per opened file. `related` runs inside every
# Read, and it asks this of every record that missed the text tiers — so the parse was repeating
# across the whole store on every tool call. Measured on this workspace: parsing is 19x the cost of
# the glob match it exists to feed, and the record's text is the same text every time.
_TRAILER_CACHE = {}


def _trailers(text):
    key = (len(text), hash(text))
    got = _TRAILER_CACHE.get(key)
    if got is None:
        try:
            import rulecheck
        except ImportError:
            return ()
        got = tuple(rulecheck.parse(text))
        _TRAILER_CACHE[key] = got
    return got


def _governs(text, rel_path):
    """Does a record's Check trailer claim authority over this path?

    Tier 2 on purpose — below both text-match tiers. A record that names the file in prose is
    talking about that file; one whose glob happens to cover it is talking about a category. The
    first is the better pointer when both exist.
    """
    rel = str(rel_path).replace("\\", "/")
    for _mode, _pattern, glob, _per_file in _trailers(text):
        # Matched the way rulecheck RESOLVES it, not the way fnmatch reads it. fnmatch's `*`
        # crosses `/`; Path.glob's does not, and rulecheck -- the module that actually runs the
        # check -- uses Path.glob. So `src/*.py` had the pointer telling a session that
        # `src/deep/nested/leaky.py` was covered by a recorded rule, while the checker had never
        # looked at that file and never would. Two modules, one glob, opposite answers, and the one
        # that spoke to the model was the one that was wrong.
        if _glob_covers(glob, rel):
            return True
    return False


def related(wsdir, rel_path, max_hits=MAX_HITS):
    """[(label, path_in_workspace, title)] — entries whose text names this file.

    Ordered by full-path match over basename match, then by HOW OFTEN the entry names the file,
    then by SOURCES order. The occurrence count is what separates a document about this file from
    an index that lists it once among fifty — found on the first live run against a real workspace,
    where the skills index outranked the procedure literally titled after the file being opened
    (README.md named it once, that procedure seven times). Counting is the whole rule: no
    path-shape heuristic, nothing to tune.

    Anything unreadable is skipped rather than raised: this runs inside a tool call, and a pointer
    that can break somebody's edit is worse than no pointer.
    """
    wsdir = Path(wsdir)
    wanted = needles(rel_path)
    if not wanted:
        return []
    found = []
    for rank, (sub, label) in enumerate(SOURCES):
        d = wsdir / sub
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.md")):
            # 🐛 [2026-09-09] This module imports `workspace as ws` and never called `ws.inside`.
            # A committed symlink at `memory/x.md` pointing outside the repository was opened here
            # and its heading printed into the tool-call context — the same leak the workspace
            # stores were guarded against on 2026-09-08, in the one reader that was not part of
            # that sweep because it lives in a different module. What a pointer surfaces is a
            # TITLE, which is exactly the first line of whatever it was aimed at. (R3 agent 2,
            # reproduced end to end.)
            if not ws.inside(f, wsdir):
                continue
            try:
                if f.stat().st_size > MAX_BYTES:
                    continue
                text = f.read_text(encoding="utf-8-sig", errors="replace")
            except OSError:
                continue
            # 🐛 [2026-09-24] (R21, 2026-09-24) A thread marked closed was still named every time a file it
            # lists was opened: on Lumin-App the most-named entry in 24 days, 56 times, was a thread
            # closed since the 1.6.0 batch, and in 35 of those it was the ONLY thing named — so the
            # pointer's whole message was "read this finished work". Found by testing a research
            # finding (knowledge should fade by use and by what replaced it). Demoting it would not
            # have helped when it is the sole hit; a closed thread is history, not a thing to read
            # before editing, so it is not named at all.
            if label == "thread" and _CLOSED_THREAD.search(text):
                continue
            for tier, needle in enumerate(wanted):
                # 🐛 A raw substring count, so `memory.py` matched inside `vector_memory.py`. The
                # docstring calls carrying the extension "the whole guard", and it is not: opening
                # chamnan/lib/memory.py pointed at two procedures for a DIFFERENT codebase's vector
                # store — five substring hits, zero real ones, 1 of 5 pointer fires in a live
                # session. The ranking made it worse: `-seen` rewards the collision, so a document
                # mentioning `vector_memory.py` five times outranks one naming the real file once.
                #
                # A boundary on the LEFT only. The right side is already anchored by the extension,
                # and requiring one there would lose `` `path/to/memory.py` `` in prose, which is how
                # these documents actually write a filename. `/` and `.` are deliberately NOT in the
                # exclusion set for the same reason — a path separator or a `./` prefix is exactly
                # the context a real reference appears in. Only a word character or a hyphen before
                # the name means it is part of a LONGER name.
                seen = len(_BOUNDARY_CACHE.setdefault(
                    needle, re.compile(r"(?<![\w-])" + re.escape(needle))).findall(text))
                if seen:
                    found.append(((tier, -seen, rank, f.name), label, f, text))
                    break
            else:
                # A rule's `**Check:**` trailer names a GLOB, and a glob is a machine-readable
                # statement of which files the rule governs. Text matching cannot see it — the rule
                # says `src/*.py`, the file is `src/cascade.py`, and nothing in the body names it.
                #
                # This is the one place the research is unambiguous about: re-injecting a whole
                # instruction block on a timer measurably does NOT restore adherence, while a short,
                # single-purpose message delivered right before the decision point does. A rule that
                # governs the file about to be edited, surfaced at the moment it is about to be
                # edited, is exactly that message — and the glob is already written down.
                # \U0001f41b [2026-09-14] This read `label == "rule"`, and every Check trailer in
                # the workspace it was written for lives in a SKILL or a lesson — rules carry none.
                # So the tier below never fired once: `_governs` returned True for a hook the
                # lesson's glob covers, and `related` dropped it on the way out. The comment above
                # says "a rule's trailer" because rules were the first store to get the grammar,
                # but `rulecheck.parse` has always read any record and `chamnan-report` has always
                # evaluated them all. One store of six was wired to the reader.
                if _governs(text, rel_path):
                    found.append(((2, 0, rank, f.name), label, f, text))
    found.sort(key=lambda x: x[0])
    return [(label, str(f.relative_to(wsdir).as_posix()), _title(text, f.stem.replace("-", " ")))
            for _, label, f, text in found[:max_hits]]


def render(rel_path, hits, edges=None):
    """The block that gets injected, or "" when there is nothing to say.

    Deliberately flat and short. It is read mid-task, between deciding to open a file and reading
    it, which is the least patient moment there is.
    """
    lines = []
    for label, path, title in hits:
        lines.append(f"  {label:9} {mdblock.one_line(path)} — {mdblock.as_quoted(title, 100)}")
    if edges:
        used, tests = edges.get("used_by") or [], edges.get("tests") or []
        if used:
            more = f" +{edges.get('used_by_more', 0)}" if edges.get("used_by_more") else ""
            lines.append(f"  {'used by':9} {', '.join(mdblock.one_line(u) for u in used)}{more}")
        if tests:
            more = f" +{edges.get('tests_more', 0)}" if edges.get("tests_more") else ""
            lines.append(f"  {'tested by':9} {', '.join(mdblock.one_line(t) for t in tests)}{more}")
    if not lines:
        return ""
    return (f"[chamnan] what this repository already records about {mdblock.one_line(rel_path)}:\n"
            + "\n".join(lines)
            + "\n  (read one only if it bears on the change — this is a pointer, not a summary)")


# ---------------------------------------------------------------- once per file per session
def _seen_path(wsdir, session_id):
    """One store per session, named after it. Two sessions never share a file.

    This used to be a single `pointer_seen.json` holding {"session": id, "paths": [...]}, reset
    whenever the id changed. That is a read-modify-write with no lock, and two sessions in one
    repository is normal rather than exotic. Measured on the real function: four concurrent writers
    recorded 48 of 160 paths -- 70% lost -- and two sessions alternating wiped each other down to a
    single entry, so `already_pointed` returned False for a file that had just been pointed at.

    The rule this store exists to keep is "once per file per session". Under concurrency it was
    keeping nothing, and the failure was silent: the file stayed valid JSON, just wrong. That is the
    lost-update anomaly, and an atomic write does not prevent it -- only a lock spanning the read AND
    the write does, or not sharing the file at all.

    Not sharing is the better answer here. A lock would have to survive flock's non-reentrancy across
    two file descriptors in one process, and fcntl's rule that closing ANY descriptor to the file
    drops every lock the process holds on it. Per-session files need none of that reasoning to be
    correct, and a session id is already in hand at every call site.
    """
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in str(session_id))[:64] or "none"
    return Path(wsdir) / SEEN_DIR / f"{SEEN_PREFIX}.{safe}.json"


def _sweep_seen(wsdir, keep):
    """Delete stores from sessions that are over. Bounded work, best effort, never raises."""
    try:
        for f in (Path(wsdir) / SEEN_DIR).glob(f"{SEEN_PREFIX}.*.json"):
            if f != keep and time.time() - f.stat().st_mtime > SEEN_MAX_AGE:
                f.unlink()
    except OSError:
        pass


def already_pointed(wsdir, session_id, rel_path):
    """True if this session has already been shown this file."""
    try:
        d = json.loads(_seen_path(wsdir, session_id).read_text(encoding="utf-8-sig"))
    except Exception:
        return False
    # 🐛 A freshly parsed JSON value was used as a dict with no check that it was one. A file
    # holding `[]`, `42` or `null` is valid JSON, so it parsed, and `.get` then raised
    # AttributeError. coedit.py and chamnan_scratch_watch.py guard the identical shape with a
    # comment naming this exact bug; these siblings did not (R4 agent 1).
    if not isinstance(d, dict):
        return False
    paths = d.get("paths")
    # `{"paths": 7}` is a dict AND valid JSON, so the shape check above passes and `in` then raises
    # TypeError. The value's own shape has to be checked too, not just its container's.
    return rel_path in paths if isinstance(paths, list) else False


def mark_pointed(wsdir, session_id, rel_path):
    # 🐛 [2026-09-07] `_seen_path`'s docstring describes an EARLIER version of this bug — one shared
    # `pointer_seen.json` losing 70% of concurrent writes — and records the fix as "not sharing the
    # file at all", one file per session_id. That assumption is exactly what a subagent breaks: a
    # subagent's hooks fire with its PARENT's session_id (there is no field that tells them apart),
    # so a parent and its subagents all write the same per-session file and are, in fact, sharing
    # it. Twelve concurrent file-opens under one session id: ELEVEN LOST.
    #
    # What that costs is the thing the per-session redesign was built for. `already_pointed()` then
    # returns False for files that were already shown, so the pointer re-fires and spends the
    # once-per-file-per-session budget again on every later open of the same file.
    #
    # The per-session file is still right — it keeps contention down to one parent and its own
    # subagents rather than the whole workspace. It just also needs the lock.
    p = _seen_path(wsdir, session_id)

    def _with_path(text):
        try:
            d = json.loads(text or "")
        except Exception:
            d = None
        if not isinstance(d, dict) or not isinstance(d.get("paths", []), list):
            d = {"session": str(session_id), "paths": []}
        if rel_path in d.get("paths", []):
            return None
        d.setdefault("paths", []).append(rel_path)
        # `.tmp` was a name shared by every process, so two sessions staged into the same file and
        # each replaced the target with whatever it held at their own moment. One helper now, so
        # the staging name cannot be got wrong here or anywhere else -- see ws.atomic_write_text.
        return json.dumps(d)

    try:
        # Housekeeping: a pointer that cannot be recorded must not stop the session, and the cost
        # of losing one is that the pointer fires twice.
        if ws.rewrite_shared(p, _with_path, strict=False):
            _sweep_seen(wsdir, p)
    except OSError:
        pass


def note(wsdir, session_id, rel_path, hits, ms, actor=None, why=""):
    """Record that a pointer fired, and what it named.

    This is the measurement the last review round asked for and it is deliberately NOT
    "did it match". A router or pointer that matches 39 times out of 42 and names the wrong file
    scores identically to one that names the right file, so `match` is not evidence of use. What is
    evidence is whether the session then opened what it was pointed at — and every path named here
    is written down, so a later reader can compare this log against the files the session actually
    read. Nothing here scores anything; it records what happened.
    """
    rec = {"t": int(time.time()), "session": session_id, "path": rel_path,
           "named": [h[1] for h in hits], "ms": round(ms, 1)}
    # 🎯 [1.31 queue item 3, a second reader 2026-09-23] An open does not mean the brief was bad: some
    # work has to open the file because it is about to change it. Without a reason beside it, an open is
    # an undifferentiated event and a utility-per-byte allocator would learn from a mixed signal.
    #
    # 🔴 The reason is not inferred and not guessed: it is the TOOL the host used, which states
    # the intent outright. `Read` is a look, and a look at something the index could have answered
    # is the case worth counting. `Edit`, `Write` and `NotebookEdit` are a declared intent to
    # change the file, and opening a file you are about to edit is correct behaviour that must
    # never be scored as a pointer failing.
    if why:
        rec["why"] = why[:24]
    # Which AGENT was pointed at something, not only which session — a session that dispatches ten
    # subagents looks like one reader in this log without it, which is the shape M page 2 asks
    # about. Absent on the main thread, like every other actor field.
    rec.update(actor or {})
    # 🐛 [2026-09-10] The bound added the day before was a `_trim()` here that did an
    # unlocked read-modify-write on `EVENT_LOG` — and `EVENT_LOG` is ONE path that every session on
    # the machine writes, carrying `session` as a FIELD rather than as a filename. A record appended
    # between one session's `read_text` and its `atomic_write_text` was dropped: the lost update
    # `blocklog` and `tools_index` each take `ws.exclusive` to prevent. Silent when it happened, and
    # rare enough to stay silent — the trim only woke past 200 KB (R4 agent 1, 2026-09-10, finding 4).
    #
    # `ws.append_jsonl` is that entire pattern — locked, SKIPPING rather than blocking when another
    # process holds it, atomic, bounded by `keep` — extracted on 2026-09-10 and already the writer
    # for two other logs. A fourth hand-rolled copy, in the package whose own advisory counts
    # function bodies written in more than one file, was not the answer. It never raises.
    ws.append_jsonl(Path(wsdir).parent, EVENT_LOG, rec, KEEP)


def opens_by_store(root):
    """{store name: how many times a session has opened a file in it}, from this log.

    `note_opened` has been writing these records since it was added and nothing has ever read one.
    That is the whole gap this closes: chamnan could say which store a session went to and used a
    ranking written by hand instead. Measured here the day it was first read, over 175 records:
    `skills` 8, `memory` 3, and nothing else at all -- while `skills` sits near the cheap end of
    `fit.DROP_ORDER` and is therefore the first thing this repository is told to lose.

    Counts, not recency, and no decay: a store opened once a month is still a store this workspace
    uses, and the log bounds itself at `KEEP` records so old evidence ages out by volume anyway.

    Never raises. A missing or half-written log means "no evidence", which is the same answer a
    fresh install gives, and the ordering falls back to `DROP_ORDER` exactly as before.
    """
    out, seen = {}, {}
    try:
        path = ws.workspace(root) / EVENT_LOG
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except (ValueError, RecursionError):
                    # A torn last line is not a reason to lose the rest, and a record nested past
                    # the interpreter's limit is a torn line by another name — this log is written
                    # by a hook and read by one, so neither end may raise.
                    continue
                if not isinstance(rec, dict) or rec.get("event") != "opened":
                    continue
                rel = str(rec.get("path") or "").replace("\\", "/")
                store = rel.split("/", 1)[0]
                if store:
                    seen.setdefault(store, set()).add(rel)
    except (OSError, ValueError, RecursionError):
        return {}
    out = {k: len(v) for k, v in seen.items()}
    # 🐛 [2026-09-15] `tools` counted zero here while `state/tool_usage.json` held 179 entries, and
    # the ordering therefore treated the most-used store in the workspace as the least-used one.
    # A tool is RUN, not opened, so it never reaches this log -- the evidence for it has always
    # been kept somewhere else, and reading one of the two records and calling the answer "usage"
    # is how a store that is used constantly gets ranked as a store nobody touches.
    #
    # Counted in the same unit as the rest: DISTINCT members of the store with any use on record,
    # so eight opens of one skill do not outweigh eight different ones, and a store is compared by
    # how much of it is live rather than by how often somebody reached for the same file.
    try:
        reg = ws.workspace(root) / "state" / "tool_usage.json"
        with open(reg, encoding="utf-8") as fh:
            used = json.load(fh)
        if isinstance(used, dict) and used:
            out["tools"] = len(used)
    except (OSError, ValueError, RecursionError):
        pass                      # no register is no evidence, which is a valid answer
    return out


def note_opened(wsdir, session_id, rel_path, actor=None):
    """Record that a session opened one of chamnan's own STORE files directly.

    Called from the hook's early return for a path under the workspace itself -- exactly where
    `note()` above can never fire, because a pointer is never rendered for chamnan's own files.
    Without this, a session that actually opened the skill it was pointed at looked identical, in
    every log this plugin keeps, to one that never did.

    `rel_path` is relative to the WORKSPACE (`skills/x.md`, `memory/rules/x.md`), the same shape
    `related()` already returns as `named` above, so a later reader can join the two directly
    rather than reconcile two path conventions.

    `"event": "opened"` is what tells this apart from an offered record. It cannot be inferred from
    an empty `named` list -- three existing records already carry one for unrelated reasons.
    """
    rec = {"t": int(time.time()), "session": session_id, "path": rel_path, "event": "opened"}
    rec.update(actor or {})
    ws.append_jsonl(Path(wsdir).parent, EVENT_LOG, rec, KEEP)


def note_query(wsdir, session_id, rel_path, pattern="", actor=None):
    """Record that a session SEARCHED one of chamnan's own files, rather than opening it.

    🎯 [R3.11.5, 2026-09-16] `note_opened` can only see a Read, and the two artefacts this plugin
    exists for are not read — they are grepped. `MAP.md` is 428,000 characters and its own header
    tells you never to read it whole; `STATE.md` is scanned for the section that applies. So both
    register ZERO opens, and `lib/fit.py` carries the scar: ranked on that evidence alone, the
    architecture index and the work-in-flight section were the first two things dropped from the
    block.

    Recorded as `"event": "query"`, deliberately DISTINCT from `"opened"`, and nothing ranks on it
    yet. Mixing the two is how the defect above happened, and the instrument has to exist before
    anybody can argue about what it means. What it answers that nothing else can: whether a store
    with no opens is a store nobody needs, or one everybody reaches by search.

    The pattern is truncated hard and passed through the redactor by the caller -- a search string
    is user text and can carry anything.
    """
    rec = {"t": int(time.time()), "session": session_id, "path": rel_path, "event": "query"}
    if pattern:
        rec["q"] = pattern[:80]
    rec.update(actor or {})
    ws.append_jsonl(Path(wsdir).parent, EVENT_LOG, rec, KEEP)


# 🐛 [2026-09-09] `workspace.SELF_PRUNING_LOGS` exempts this file from the 7-day sweep, and
# its own comment states the contract: "A log that bounds itself by record must say so here, or the
# directory sweep bounds it by date instead." This file was on that list and nothing bounded it —
# `note()` was the only writer and it only appended. Every sibling on that list has a `KEEP`; this
# one had the exemption without the obligation (R4 agent 4, 2026-09-09).
#
# By record rather than by date, which is what the exemption promises. One PreToolUse firing per
# file pointer is a handful a session, so this holds months of them.
KEEP = 2000


def named_counts(root, prefix="memory/rules/"):
    """{filename: how many times this store file was NAMED for a file somebody was working on}.

    🎯 [owner 2026-09-22] *"it should load only what pairs with the most recent work ... the rules
    are still important, they are the secondary rules, so keep the others waiting to be called"*.
    The block carries every rule each session and the largest section is the rules — 35% of a block
    that is 30 bytes under its ceiling — while `CLAUDE.md` governs on top of them anyway.

    `named` is the right signal and it was already being written. It is not "a session opened this
    file": it is the file pointer deciding, at the moment somebody touched a source file, that THIS
    rule governs it. Accumulated over real work that is exactly "what work used which rules", and
    nothing had ever read it. Measured the day it was first read, over 241 records: 27 for
    `the-set-not-the-member.md`, 10 for the round-numbering rule, 5 for the extend-a-skill rule.

    That first number is the case for doing this at all. `memory.rules_text` orders by pin then by
    mtime, and `the-set-not-the-member.md` — this repository's most-recorded defect, and the rule
    named more often than any other — was arriving as a TITLE ONLY. Its own file records the
    consequence: it was violated about twenty hours after being written, while unreadable.

    Counts, not recency, for the reason `opens_by_store` gives beside it: a rule that governs work
    done once a month still governs it. Never raises; no log is no evidence, which is the answer a
    fresh install gives and which leaves the existing ordering exactly as it was.
    """
    out = {}
    try:
        path = ws.workspace(root) / EVENT_LOG
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except (ValueError, RecursionError):
                    continue          # a torn line is one lost record, not a broken feature
                if not isinstance(rec, dict):
                    continue
                for named in (rec.get("named") or []):
                    rel = str(named).replace("\\", "/")
                    if rel.startswith(prefix):
                        name = rel.rsplit("/", 1)[-1]
                        out[name] = out.get(name, 0) + 1
    except (OSError, ValueError, RecursionError):
        return {}
    return out
