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

import fnmatch

import md

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

MAX_HITS = 4          # per file; past this the pointer is a wall of text and stops being read
MAX_BYTES = 60_000    # per entry; a knowledge file larger than this is not a knowledge file
SEEN_DIR = "logs"
SEEN_PREFIX = "pointer_seen"
SEEN_MAX_AGE = 2 * 24 * 3600     # a store older than this belongs to a session that is long gone
EVENT_LOG = "logs/pointer.jsonl"

_FRONT_NAME = re.compile(r"^description:\s*(.+?)\s*$", re.M)  # applied to front matter ONLY
_HEADING = re.compile(r"^#{1,3}[ \t]+(.+?)\s*$", re.M)
# An HTML-comment description, which is how the skills in this workspace carry theirs.
_COMMENT_DESC = re.compile(r"<!--\s*description:\s*(.+?)\s*-->", re.S)


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
            return " ".join(m.group(1).split())[:96]
    m = _COMMENT_DESC.search(text)
    if m:
        return " ".join(m.group(1).split())[:96]
    heads = md.headings(_HEADING, text)
    if heads:
        return " ".join(heads[0].group(1).split())[:96]
    return fallback


def needles(rel_path):
    """The strings whose presence in an entry counts as naming this file.

    Both are extension-bearing on purpose (see the module docstring). The path is included as well
    as the basename because two files can share a name, and an entry that spelled out the full path
    meant that one.
    """
    rel = str(rel_path).replace("\\", "/").lstrip("./")
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


def _governs(text, rel_path):
    """Does a rule's Check trailer claim authority over this path?

    Tier 2 on purpose — below both text-match tiers. A rule that names the file in prose is talking
    about that file; a rule whose glob happens to cover it is talking about a category. The first is
    the better pointer when both exist.
    """
    try:
        import rulecheck
    except ImportError:
        return False
    rel = str(rel_path).replace("\\", "/")
    for _mode, _pattern, glob in rulecheck.parse(text):
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
            try:
                if f.stat().st_size > MAX_BYTES:
                    continue
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for tier, needle in enumerate(wanted):
                seen = text.count(needle)
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
                if label == "rule" and _governs(text, rel_path):
                    found.append(((2, 0, rank, f.name), label, f, text))
    found.sort(key=lambda x: x[0])
    return [(label, str(f.relative_to(wsdir)), _title(text, f.stem.replace("-", " ")))
            for _, label, f, text in found[:max_hits]]


def render(rel_path, hits, edges=None):
    """The block that gets injected, or "" when there is nothing to say.

    Deliberately flat and short. It is read mid-task, between deciding to open a file and reading
    it, which is the least patient moment there is.
    """
    lines = []
    for label, path, title in hits:
        lines.append(f"  {label:9} {path} — {title}")
    if edges:
        used, tests = edges.get("used_by") or [], edges.get("tests") or []
        if used:
            more = f" +{edges.get('used_by_more', 0)}" if edges.get("used_by_more") else ""
            lines.append(f"  {'used by':9} {', '.join(used)}{more}")
        if tests:
            more = f" +{edges.get('tests_more', 0)}" if edges.get("tests_more") else ""
            lines.append(f"  {'tested by':9} {', '.join(tests)}{more}")
    if not lines:
        return ""
    return (f"[chamnan] what this repository already records about {rel_path}:\n"
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
        d = json.loads(_seen_path(wsdir, session_id).read_text(encoding="utf-8"))
    except Exception:
        return False
    return rel_path in (d.get("paths") or [])


def mark_pointed(wsdir, session_id, rel_path):
    p = _seen_path(wsdir, session_id)
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        d = {"session": str(session_id), "paths": []}
    if rel_path in d.get("paths", []):
        return
    d.setdefault("paths", []).append(rel_path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        # Beside the target, never in the system temp directory: os.replace fails with EXDEV across
        # mount points, and a copy-and-delete fallback would give up the atomicity this is here for.
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(d), encoding="utf-8")
        tmp.replace(p)
        _sweep_seen(wsdir, p)
    except OSError:
        pass


def note(wsdir, session_id, rel_path, hits, ms):
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
    try:
        p = Path(wsdir) / EVENT_LOG
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass
