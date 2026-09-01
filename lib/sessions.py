"""Session records — where the last piece of work stopped, so the next one does not restart it.

Distinct from STATE.md on purpose, and the distinction is worth holding onto because the two will
otherwise drift into duplicates of each other:

    STATE.md   ONE file, overwritten. "What is true about this repo's work right now."
    sessions/  MANY files, append-only. "Where the session on the 14th got to, and what it left."

STATE.md answers a question about the present. A session record answers a question about a
particular stretch of work — and the only part of it anybody needs at the start of the next
session is the part that was not finished.

One file per session rather than one growing log, because these files live in a git repository and
get written on branches. Many small files merge cleanly; a single append-only document conflicts
every time two branches both worked a day.

Nothing here writes: Claude writes the record, through skills/resume. A hook cannot, because a hook
has no access to what the session was about -- chamnan_session_end.py can see which scripts repeated and
nothing else. So this module reads, selects, and prunes, and the format below is the contract
between the skill that writes and the hook that reads.
"""
import calendar
import datetime
import re
import mdblock
import time

# Written by skills/resume. Deliberately flat markdown with no frontmatter: the file is meant to be
# read by a person in a diff, and a header block would be one more thing to get wrong.
HEADINGS = ("Done", "Remaining", "Files", "Decisions", "Blockers")

# Only these reach the next session. "Done" is history and "Files" is recoverable from git; what
# the next session cannot work out for itself is what was left and what was in the way.
CARRIED = ("Remaining", "Blockers")

# A record is bounded so one enormous session cannot swamp the injection. Roughly the same order as
# state_token_budget's char-equivalent in the hook (see lib/state.py).
MAX_CARRY_CHARS = 1200

_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def directory(root):
    from workspace import workspace
    return workspace(root) / "sessions"


_SESSION_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def records(root):
    """Every session record, newest first. Sorted by filename, which begins with the date."""
    d = directory(root)
    if not d.is_dir():
        return []
    # 🐛 Sorted by filename alone, so ANY name starting with a letter beat every `YYYY-…` record:
    # a `TEMPLATE.md`, a `README.md` or a `notes.md` dropped in this directory became "the last
    # session", and the header still said so, which is how it read as real. `prune()` already
    # treats the filename date as the authority; this did not. Dated records first, newest first;
    # anything undated sorts behind all of them rather than in front.
    return sorted((p for p in d.glob("*.md") if p.is_file()),
                  key=lambda p: (bool(_SESSION_DATE.match(p.name)), p.name), reverse=True)


def latest(root):
    found = records(root)
    return found[0] if found else None


def written_today(root, today=None):
    """True when a session record's own FILENAME date matches today -- not file mtime, which
    resets on a checkout and would falsely say yes on a fresh clone. `today` is injectable
    (YYYY-MM-DD) so a caller does not need real wall-clock time to test this."""
    import datetime
    today = today or datetime.datetime.now().astimezone().strftime("%Y-%m-%d")
    return any(p.name.startswith(today) for p in records(root))


def _sections(text):
    """Split a record into {heading: body}. Unknown headings are kept, so a record written by a
    newer version is read rather than discarded.

    Fence-aware, because this feeds carry_forward() and carry_forward() is injected at the top of
    the next session. A `## Done` body quoting a snippet that contained the line `## Remaining`
    used to split there: the next session was handed a fabricated section, and the real one after
    it was dropped without a trace.
    """
    out, current, buf = {}, None, []
    for line, in_fence in mdblock.fenced_lines(text):
        m = None if in_fence else re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if current:
                out[current] = "\n".join(buf).strip()
            current, buf = m.group(1), []
        elif current:
            buf.append(line)
    if current:
        out[current] = "\n".join(buf).strip()
    return out


def title_of(path, text=None):
    text = text if text is not None else path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def carry_forward(root):
    """The part of the newest record the next session needs: what is unfinished, and what blocked.

    Returns "" when there is no record, when the record has nothing outstanding, or when the file
    cannot be read. An empty return means the hook injects nothing at all, which is the right
    outcome for a repository where the last session finished what it started.
    """
    path = latest(root)
    if path is None:
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""

    found = _sections(text)
    parts = []
    for name in CARRIED:
        body = found.get(name, "").strip()
        if body and not _is_nothing(body):
            parts.append(f"**{name}**\n{body}")
    if not parts:
        return ""

    m = _DATE.match(path.name)
    when = m.group(1) if m else path.stem
    head = f"_Last session ({when}) — {title_of(path, text)}_"
    body = "\n\n".join(parts)
    if len(body) > MAX_CARRY_CHARS:
        body = body[:MAX_CARRY_CHARS].rsplit("\n", 1)[0] + \
            f"\n\n_…truncated — read `{path.name}` for the rest._"
    return f"{head}\n\n{body}"


# The skill asks for the section to be left out when there is nothing to say, but people write
# "- none" and mean it, and carrying that into the next session is the same as carrying a blank.
_NOTHING = {"", "-", "—", "*", "none", "nothing", "n/a", "na", "no blockers", "not yet", "tbd"}


def _is_nothing(body):
    lines = [re.sub(r"^\s*[-*+]\s*", "", l).strip().rstrip(".").lower()
             for l in body.splitlines() if l.strip()]
    return all(l in _NOTHING for l in lines)


def prune(root, days):
    """Delete records older than the retention window. Best-effort and silent, like prune_logs:
    housekeeping must never be the reason a command the user asked for fails.

    Unbounded is not an option. These accumulate one per working session, in a directory that is
    committed, in somebody else's repository.
    """
    d = directory(root)
    if not d.is_dir() or not days:
        return 0
    cutoff = time.time() - days * 86400
    removed = 0
    for path in d.glob("*.md"):
        try:
            if not path.is_file():
                continue
            # The filename's own date first; mtime only when there isn't one. ledger.py documents
            # this exact trap -- "mtime resets to checkout time on a fresh clone or machine move" --
            # and avoids it for its own feature, but the fix was never ported here, to the function
            # that actually DELETES files. Measured: a record filed 2020-01-01, 2,435 days old by
            # its own name, with mtime reset by a clone, survived prune(days=30) untouched. This
            # repository migrates machines routinely and the "bounded, never leaks disk" promise
            # was quietly not being kept.
            stamp = _DATE.match(path.name)
            age = None
            if stamp:
                try:
                    y, m, dd = (int(x) for x in stamp.group(1).split("-"))
                    # date() first, because calendar.timegm does NOT validate the day: it takes
                    # (2026, 2, 30) and silently returns March 2nd. An impossible date is a typo,
                    # and a typo must not become a deletion decision that looks correct.
                    datetime.date(y, m, dd)
                    age = time.time() - calendar.timegm((y, m, dd, 12, 0, 0))
                except (ValueError, OverflowError):
                    age = None      # an impossible date is not a date; fall back to mtime
            if age is not None:
                if age > days * 86400:
                    path.unlink()
                    removed += 1
            elif path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            continue
    return removed


def slug(title):
    """A filename fragment from a title. ASCII-only and short, because these names are read in a
    directory listing and in git diffs."""
    s = re.sub(r"[^a-zA-Z0-9]+", "-", title.strip().lower()).strip("-")
    return (s[:40].rstrip("-") or "session")


def filename(date, title):
    return f"{date}-{slug(title)}.md"
