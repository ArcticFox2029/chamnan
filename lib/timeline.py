"""Threads — one line of work followed across the sessions it actually took.

The stores that already exist each answer a different question, and none of them answers this one:

    STATE.md      what is happening right now (one file, overwritten, present tense)
    sessions/     where one session stopped (many files, 30-day retention)
    milestones.md the handful of changes that reshaped the repo (one flat list, never pruned)
    threads       what happened to ONE subject over time, and what each round cost

A thread is the connective tissue between the other four. "We have tried to fix this three times"
is knowledge nobody can reconstruct from a git log, because the three attempts are three unrelated
commits weeks apart, and the thing that ties them together was only ever in somebody's head.

**Threading is a pick from a declared list, never a string match.** This is the whole design and it
is worth stating plainly, because the obvious implementation is the wrong one. Guessing which
thread an entry belongs to by matching words in its text fails on the first synonym: one session
writes "auth", the next writes "login", the third writes "the SSO work", and a string matcher
scatters one thread across three. So `append()` REFUSES a thread that has not been declared —
`chamnan-timeline new` declares one, and everything after that picks from what exists. The set of
files in `threads/` IS the declared vocabulary; there is no second list to keep in sync with it.

**`Files:` is the join key, and it is checked.** An entry may name paths it touched. Those are what
`chamnan-timeline for <path>` joins on, and what lets an impact question carry "last time this
changed, it needed a rollback" instead of only naming what imports what. Free prose is not a join
key — the same reason `Symptom:` was cut from the memory format.
"""
import re
import mdblock

DIRNAME = "threads"

# Only OPEN threads reach a session, and only as titles. A closed thread is history: still there
# to read, still joined against by `for`, but it has stopped being something the agent should be
# holding in mind before it starts.
INJECT_OPEN = 3

# Same shape as milestones' _ENTRY, and all three dash characters are listed explicitly for the
# same reason -- an en-dash from an editor's autocorrect silently failing to match is a bug this
# repository has already paid for once (see lib/milestones.py).
_ENTRY = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*[—–-]\s*(.+?)\s*$", re.M)
_STATUS = re.compile(r"^\*\*Status:\*\*\s*(\w+)", re.M)
_FILES = re.compile(r"^\*\*Files:\*\*\s*(.+?)\s*$", re.M)

OPEN, CLOSED = "open", "closed"


def directory(root):
    from workspace import workspace
    return workspace(root) / DIRNAME


def slug(title):
    """A readable filename for a thread title.

    Lossy on purpose -- punctuation and case go -- so two DIFFERENT titles can land on the same
    name: "Fix Auth!!!" and "Fix, Auth" both give `fix-auth`, and the second silently appended an
    unrelated subject to the first thread's file. That is the scattering this module exists to
    prevent, running in reverse.

    The collision is handled in create(), not here, and that placement is the fix for a fix. This
    function once appended a hash whenever slugging "changed" the title -- but slugging changes
    every title with an internal hyphen, so `bge-m3 migration` became `bge-m3-migration-12a9e3`
    and `chamnan-timeline close bge-m3-migration`, the obvious guess, matched nothing. A pure
    function cannot know whether a name collides; only the directory can. So this stays readable
    and guessable, and create() disambiguates when it actually has to.
    """
    s = re.sub(r"[^a-zA-Z0-9]+", "-", title.strip().lower()).strip("-")
    return s[:50].rstrip("-") or "thread"


def _distinct_slug(directory_, title):
    """`slug(title)`, or that plus a short hash when the name is taken by a DIFFERENT title."""
    base = slug(title)
    path = directory_ / f"{base}.md"
    if not path.is_file() or title_of(path).strip().lower() == title.strip().lower():
        return base
    import hashlib
    canonical = " ".join(title.split()).lower()
    return f"{base}-{hashlib.sha1(canonical.encode('utf-8')).hexdigest()[:6]}"


def threads(root):
    """Every declared thread's path, sorted by filename. [] when the directory does not exist —
    which is the common case and not an error, the same way every other store here reads."""
    d = directory(root)
    if not d.is_dir():
        return []
    return sorted(p for p in d.glob("*.md") if p.is_file())


def resolve(root, ident):
    """One thread's path from its slug, its filename, or its 1-based position in `threads()`.

    Position is computed fresh on every call and never cached, matching `lib/candidates.py`: a
    number the user just read off a listing is the fastest thing to type, and a number remembered
    from an hour ago pointing at a different thread would be the worst outcome.
    """
    found = threads(root)
    if not found:
        return None
    ident = str(ident).strip()
    if ident.isdigit():
        i = int(ident)
        return found[i - 1] if 1 <= i <= len(found) else None
    want = ident[:-3] if ident.endswith(".md") else ident
    for p in found:
        if p.stem == want or p.stem == slug(want):
            return p
    return None


def title_of(path):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return path.stem.replace("-", " ")
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem.replace("-", " ")


def status_of(path):
    """`open` or `closed`. A thread with no Status line at all reads as OPEN — the field is
    additive, and a file written by hand without it should behave like the common case rather
    than disappear from the listing."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return OPEN
    # Masked, because this searches the WHOLE file for the first match. A thread whose body quotes
    # an example containing `**Status:** closed` inside a fence read as closed -- and open_titles()
    # then dropped it from the "Open threads" the next session is handed. Unfinished work vanishing
    # from the handoff is the one failure this module exists to prevent, and content was deciding
    # it.
    m = _STATUS.search(mdblock.masked(text))
    return CLOSED if (m and m.group(1).lower() == CLOSED) else OPEN


def entries_of(path):
    """(date, note, files) oldest first — the order they were appended in.

    `files` is the list from that entry's `**Files:**` line, or [] when it has none. Nothing here
    checks whether those paths exist; that is `for_path()`'s business, and an entry naming a file
    that has since been deleted is still a true record of what happened.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    # Scanned over a copy with fenced lines blanked; offsets are preserved, so every slice below
    # still indexes the real text. A real entry that quoted a bad example -- `## 2099-01-01 — FAKE`
    # with its own `**Files:**` line -- parsed as a second, indistinguishable entry, and for_path()
    # then attached that thread's history to a file the thread had never touched.
    masked = mdblock.masked(text)
    found = list(_ENTRY.finditer(masked))
    out = []
    for i, m in enumerate(found):
        end = found[i + 1].start() if i + 1 < len(found) else len(text)
        body = text[m.end():end].strip()
        fm = _FILES.search(mdblock.masked(body))
        files = [f.strip().strip("`") for f in fm.group(1).split(",")] if fm else []
        out.append((m.group(1), m.group(2), [f for f in files if f]))
    return out


def create(root, title, today):
    """Declare a thread. Returns (path, is_new) — an existing thread is returned untouched rather
    than overwritten, so running this twice is safe and never loses entries."""
    d = directory(root)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{_distinct_slug(d, title)}.md"
    if path.is_file():
        return path, False
    path.write_text(f"# {title.strip()}\n\n**Started:** {today}\n**Status:** {OPEN}\n",
                    encoding="utf-8")
    return path, True


def append(root, ident, date, note, files=None):
    """Add one entry to a DECLARED thread. Returns the path, or None when no such thread exists.

    None rather than creating it: an unknown name is far more likely a typo or a synonym for a
    thread that already exists than a genuinely new line of work, and silently creating a second
    thread for the same subject is exactly the scattering this module is built to prevent. The
    caller prints the declared list so the choice is visible.
    """
    path = resolve(root, ident)
    if path is None:
        return None
    body = [f"## {date} — {note.strip()}", ""]
    named = [f.strip() for f in (files or []) if f.strip()]
    if named:
        body.append("**Files:** " + ", ".join(f"`{f}`" for f in named))
        body.append("")
    existing = path.read_text(encoding="utf-8", errors="replace").rstrip("\n")
    path.write_text(existing + "\n\n" + "\n".join(body).strip() + "\n", encoding="utf-8")
    return path


def set_status(root, ident, status):
    """Returns the path, or None when no such thread exists. Rewrites an existing Status line in
    place and appends one when the file has none, so a hand-written thread gains the field rather
    than being rejected for not having it."""
    path = resolve(root, ident)
    if path is None:
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    if _STATUS.search(text):
        text = _STATUS.sub(f"**Status:** {status}", text, count=1)
    else:
        lines = text.splitlines()
        at = 1 if lines and lines[0].startswith("# ") else 0
        lines.insert(at, f"\n**Status:** {status}")
        text = "\n".join(lines)
    path.write_text(text.rstrip("\n") + "\n", encoding="utf-8")
    return path


def for_path(root, target):
    """[(thread_path, date, note)] for every entry naming `target` in its `Files:` line, newest
    first. This is the join Stage 13b's impact query reads: given a file somebody is about to
    change, what has already happened to it.

    Matches a declared path exactly, or as a suffix of one — an entry written as `src/app.py`
    should still answer a question asked about `src/app.py` from a subdirectory. Deliberately not
    a fuzzy match: `app.py` matching `src/vendor/app.py` would attach one file's history to
    another's, which is worse than finding nothing.
    """
    target = str(target).strip().strip("`").lstrip("./")
    if not target:
        return []
    hits = []
    for path in threads(root):
        for date, note, files in entries_of(path):
            for f in files:
                f = f.lstrip("./")
                if f == target or f.endswith("/" + target) or target.endswith("/" + f):
                    hits.append((path, date, note))
                    break
    return sorted(hits, key=lambda h: h[1], reverse=True)


def open_titles(root, count=INJECT_OPEN):
    """The open threads, one line each, newest activity first. Empty string when there are none,
    so the hook injects no heading rather than an empty one."""
    rows = []
    for path in threads(root):
        if status_of(path) != OPEN:
            continue
        found = entries_of(path)
        last = found[-1][0] if found else ""
        rows.append((last, path, len(found)))
    if not rows:
        return ""
    rows.sort(key=lambda r: r[0], reverse=True)
    lines = []
    for last, path, n in rows[:count]:
        when = f", last {last}" if last else ""
        lines.append(f"- **{title_of(path)}** — {n} entr{'y' if n == 1 else 'ies'}{when} "
                     f"(`{path.name}`)")
    if len(rows) > count:
        lines.append(f"- _…and {len(rows) - count} more open in `.chamnan/{DIRNAME}/`_")
    return "\n".join(lines)
