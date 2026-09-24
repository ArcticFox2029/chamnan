"""When a resumed conversation costs more than it is worth, and where that can be decided.

The measurement this exists for, taken on 2026-09-23 with `claude -p --output-format json` on one
repository, one account and the same question in both arms:

    fresh session   write 24,846  read 69,964  out 1,054   $0.2339
    resume 13.5h    write 58,101  read 90,138  out   490   $0.9432   4.03x
    fresh session   write 22,173  read 70,931  out   874   $0.2091
    resume 13.7h    write 71,176  read 113,696 out   664   $1.3984   6.69x

Both arms answered the question correctly, and the resumed arm answered it SHORTER every time. The
difference is not chamnan's block -- that is 4,148 tokens on startup and 4,139 on resume in the same
repository, nine tokens apart. It is the conversation being re-sent after its prompt cache expired.

**Two conditions, and both must hold.** The owner's rule, and the reasoning is the working day
rather than the clock:

  * the calendar date differs from the last response's, AND
  * at least `LONG_GAP_SECONDS` have passed since it

Either one alone gets a real case wrong. A date change alone cuts the session of anyone who works
past midnight -- 22:00 to 02:00 is four hours of one sitting and two calendar days. A gap alone cuts
someone who spent nine hours of one working day in meetings. Requiring both means the default is
always to resume, and the split only happens when the evidence is unambiguous: a new day AND a
night's worth of silence.

**What the ladder settles, and what it does not (measured 2026-09-23, direction O).** A second
reader objected that the 8 had no measurement under it, and that the mechanism is cache continuity
rather than the calendar. Both halves were answered from 160 transcripts already on disk — 6,905
requests, each one's own usage — by asking what share of the first request after a gap was charged
as a cache WRITE. `.chamnan/tools/resume_ladder.py` recomputes it:

    gap ≤ 30m     9.5% written        the cache is essentially intact
    gap ≤  1h    30.8%
    gap ≤  2h    89.4%                the cache is essentially gone
    gap ≤  8h    96.2%
    gap ≤ 24h    95.8%

**Continuity breaks between one and two hours, not at eight.** The largest step in the whole ladder
is there: 58.7 points. Everything past 2h is flat, so the extra six hours in `LONG_GAP_SECONDS`
save nothing that 2h had not already lost.

**That does not move the threshold, and the reason is the trade below rather than the number.** By
2h the money is already spent whatever this decides, so the gap is no longer a cost lever at all —
which means the 8 is doing the only job left: protecting continuity. Cutting at 2h would split
sittings all day to save nothing. The rule stands, and its justification is now the right one.

The case this deliberately lets resume: finishing at 02:00 and returning at 10:00 the same date.
That is a new sitting by any reasonable reading, and it will pay. Accepted, because the cost of a
wrong cut is a person losing the thread of their own work, and the cost of a wrong resume is money.

**This module decides and explains. It never deletes anything and never ends a session.** The
transcript stays on disk: not reading it is the whole saving, and deleting it would also remove the
only record of what happened. `housekeeping.py` has never touched session transcripts at any age and
`test_claude_data_retention.py` fails if that changes.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Eight hours, the owner's number, chosen as "a night" rather than fitted to data. It is a
# CONFIGURABLE floor rather than a constant so a team that works in shifts can move it; the pair of
# conditions is what makes the default safe, not the precision of this figure.
#
# 🎯 [1.31, direction O, measured 2026-09-23] A second reader called the 8 provisional because
# nothing measured stood under it. Something does now, and it did not move the number — it moved
# the ARGUMENT, which had been the wrong one. `tools/resume_ladder.py` over 160 transcripts, gap
# between consecutive requests against the share of input that had to be re-cached:
#
#       up to 30m     9.5% cache write        up to 4h     92.6%
#       up to  1h    30.8%                    up to 8h     96.2%
#       up to  2h    89.4%                    up to 24h    95.8%
#
# The step is between 1h and 2h, 58.7 points, and it is mechanical rather than behavioural: it is
# the prompt cache expiring. 🔴 So the cost of resuming stops varying at about two hours — past
# that a resume pays a full re-cache whether the gap is three hours or thirty. Every hour of this
# floor above ~2h therefore buys nothing in money and is a judgement about the PERSON: has the
# reader lost the thread of their own work. That is the right question to answer with a human
# number, and "a night" is a good answer to it.
#
# What the measurement does rule out is defending this figure on cost. It also rules out the
# opposite move, lowering it to 2h to "save money": below the floor the module resumes, and
# between 2h and 8h a resume already costs full price, so lowering it would cut sittings apart
# to save nothing. The ladder is archived at `state/resume_ladder_2026-09-23.txt`.
LONG_GAP_SECONDS = 8 * 3600

FRESH, RESUME = "fresh", "resume"

# Read from the end. A transcript here reached 826 MB, and the naive `read_text()` on one is a
# minute of I/O and a gigabyte of memory to find a timestamp in the last kilobyte.
_TAIL_BYTES = 256 * 1024


def decide(last_at, now=None, gap_seconds=LONG_GAP_SECONDS):
    """(FRESH or RESUME, one sentence saying why). `last_at` is a timezone-aware datetime.

    Returns RESUME when `last_at` is unknown: an absent answer is not evidence for the destructive
    reading, and the expensive default is the safe one for the person, not for the bill.
    """
    now = now or datetime.now().astimezone()
    if last_at is None:
        return RESUME, "no readable timestamp in the last transcript, so nothing was assumed"
    if last_at.tzinfo is None:
        last_at = last_at.astimezone()
    gap = (now - last_at).total_seconds()
    # Compared in LOCAL time on both sides. A UTC comparison moves the boundary by the offset, which
    # for this machine's +07:00 would call 23:30 local "tomorrow" and cut a session mid-evening.
    new_day = now.astimezone().date() != last_at.astimezone().date()
    hours = gap / 3600.0
    if new_day and gap >= gap_seconds:
        return FRESH, (f"last response was {hours:.1f}h ago and on an earlier date — "
                       f"both conditions for a new sitting")
    if new_day:
        return RESUME, (f"a new date, but only {hours:.1f}h ago — one sitting that ran past "
                        f"midnight, not a new one")
    if gap >= gap_seconds:
        return RESUME, (f"{hours:.1f}h ago but the same date — a long break inside one working "
                        f"day, not a new one")
    return RESUME, f"last response {hours:.1f}h ago"


def last_response_at(transcript):
    """When the newest entry in a transcript was written, or None.

    Reads the tail only. Every line is JSON with a `timestamp`, and the newest usable one wins --
    the last line can be a partial write, and an entry without a timestamp is not an error.
    """
    try:
        path = Path(transcript)
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > _TAIL_BYTES:
                fh.seek(size - _TAIL_BYTES)
                fh.readline()                 # drop the partial line the seek landed inside
            tail = fh.read().decode("utf-8", errors="replace")
    except (OSError, ValueError):
        return None
    for line in reversed(tail.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            stamp = json.loads(line).get("timestamp")
        except (ValueError, RecursionError):
            continue
        if not stamp:
            continue
        try:
            # Transcripts write UTC with a trailing Z, which `fromisoformat` did not accept before
            # Python 3.11 -- and this package supports 3.8.
            return datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        except ValueError:
            continue
    return None


def project_dir(repo, config_dir=None):
    """Where this host keeps the transcripts for `repo`, or None.

    `CLAUDE_CONFIG_DIR` or `~/.claude` is the rule the CLI itself follows, and it is the right one
    HERE even though `installs.py` warns against the same variable for finding the plugin registry.
    The two questions differ: the registry lives beside the code, which is why that module derives
    it from `__file__`; transcripts live beside the account, which is exactly what the variable
    names.

    The directory name is the absolute path with every separator replaced by a dash. That encoding
    is lossy -- a folder whose own name contains a dash is indistinguishable from a separator -- so
    this builds the name and checks whether it exists rather than trying to parse one back.
    """
    base = Path(config_dir or os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude"))
    try:
        encoded = str(Path(repo).resolve()).replace(os.sep, "-").replace("/", "-")
    except (OSError, ValueError):
        return None
    candidate = base / "projects" / encoded
    return candidate if candidate.is_dir() else None


def has_a_message(transcript):
    """True when a transcript holds at least one user or assistant turn.

    🐛 [2026-09-24] (self-measured) Hit for real by the owner. A transcript can survive with
    its metadata and no conversation — nine lines of title, mode and cost state, not one message.
    `claude --resume` on that id answers "No conversation found with session ID", so resuming the
    newest FILE sent the person straight into an error. Streamed and stopped at the first hit: a
    real transcript has a message within its first few lines, and one here reached 826 MB.
    """
    try:
        with Path(transcript).open("rb") as fh:
            for raw in fh:
                if b'"type":"user"' in raw or b'"type":"assistant"' in raw \
                        or b'"type": "user"' in raw or b'"type": "assistant"' in raw:
                    return True
    except OSError:
        return False
    return False


def newest_session(repo, config_dir=None):
    """(session_id, path, last_response_at) for the most recently written transcript, or None.

    Ordered by the timestamp INSIDE the newest transcript rather than by mtime where both are
    available: a file can be touched by a tool that never added a turn, and the question here is
    when somebody last talked to it.
    """
    d = project_dir(repo, config_dir)
    if d is None:
        return None
    # Newest first, and the first one that is actually a conversation wins. An empty one is
    # skipped rather than reported: it cannot be resumed, and naming it as "the earlier
    # conversation" would hand the person an id that fails the moment they try it.
    dated = []
    for f in d.glob("*.jsonl"):
        try:
            dated.append((f.stat().st_mtime, f))
        except OSError:
            continue
    best = None
    for mtime, f in sorted(dated, key=lambda mf: mf[0], reverse=True):
        if has_a_message(f):
            best = (mtime, f)
            break
    if best is None:
        return None
    return best[1].stem, best[1], last_response_at(best[1])


# ------------------------------------------------------------------ the handoff a fresh session gets
# 🎯 [owner 2026-09-24] "เริ่มใหม่เองได้ โดยดึงค่า idle + ข้ามวัน มาวาง handoff แล้วเริ่มใหม่" — and
# a fresh command that really starts a new session, not a /clear. Before this, `chamnan-open`
# decided FRESH correctly and then launched a session that knew nothing of the one it replaced: the
# workspace block carries STATE.md and git's view, and neither says what the person last ASKED.
# That is the one thing only the old transcript holds, and the reason this reads it — the tail
# only, the person's own turns only, each scrubbed before it touches disk.
#
# Written under `.chamnan/logs/`, which is gitignored on purpose and swept by retention: a handoff
# is a note from one sitting to the next, not a record, and a prompt must never reach a commit.

HANDOFF_NAME = "handoff.md"
HANDOFF_MESSAGES = 5
HANDOFF_MESSAGE_CHARS = 600
HANDOFF_CHANGED_SHOWN = 8   # files named when the repository moved; the rest is a count

# English on purpose and stated as a task, so the first turn of the new session does the reading
# instead of waiting for someone to ask. The chat language is the repository's CLAUDE.md's business.
HANDOFF_PROMPT = ("Read .chamnan/logs/handoff.md and .chamnan/STATE.md, then carry on with the "
                  "work that was in flight.")

# Harness and slash-command wrappers that arrive as `user` turns but were never typed by anybody.
_NOT_TYPED = ("<command-name>", "<command-message>", "<local-command", "<system-reminder>",
              "<task-notification>", "Caveat: The messages below", "[Request interrupted")


def _typed_text(entry):
    """The text a person typed in one transcript entry, or ""."""
    if not isinstance(entry, dict) or entry.get("type") != "user" or entry.get("isMeta") \
            or entry.get("isSidechain"):
        return ""
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        parts = [content]
    elif isinstance(content, list):
        # A list holding a tool_result is the harness answering a tool call, not a person.
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
            return ""
        parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
    else:
        return ""
    text = "\n".join(p for p in parts if p).strip()
    if not text or text.startswith(_NOT_TYPED):
        return ""
    return text


def last_user_messages(transcript, limit=HANDOFF_MESSAGES):
    """The person's last `limit` typed messages, oldest first. Reads the tail only."""
    try:
        path = Path(transcript)
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > _TAIL_BYTES * 4:
                fh.seek(size - _TAIL_BYTES * 4)
                fh.readline()
            tail = fh.read().decode("utf-8", errors="replace")
    except (OSError, ValueError):
        return []
    found = []
    for line in reversed(tail.splitlines()):
        if not line.startswith("{"):
            continue
        try:
            text = _typed_text(json.loads(line))
        except (ValueError, RecursionError):
            continue
        if text:
            found.append(text)
            if len(found) >= limit:
                break
    return list(reversed(found))


def handoff_text(session_id, transcript, last_at, why, changed=None):
    """The note a fresh session reads first. Every quoted message passes the redactor.

    `changed` is [(at, path)] for files committed after `last_at` — work the old conversation never
    saw. 🎯 [2026-09-24] (R12 acc5, 2026-09-24) Tested from a research finding (SyncMind): an agent that does
    not know the repository moved since it last looked recovered in 0.33-3.33% of cases. The
    handoff is exactly that moment, so it says what moved.
    """
    import redact
    lines = ["# Handoff from the previous session", "",
             "Written by `chamnan-open` when it started a new conversation instead of resuming: "
             + why + ".", "",
             "- previous session: `%s` — kept, not deleted; `claude --resume %s` reopens it"
             % (session_id, session_id)]
    if last_at is not None:
        lines.append("- its last response: %s" % last_at.astimezone().strftime("%Y-%m-%d %H:%M"))
    if changed:
        import redact
        paths = sorted({p for _at, p in changed})
        shown = ", ".join("`%s`" % redact.for_a_terminal(redact.scrub(p)) for p in paths[:HANDOFF_CHANGED_SHOWN])
        more = len(paths) - HANDOFF_CHANGED_SHOWN
        lines.append("- **committed since then, by another session or by hand** — %d file(s): %s%s. "
                     "Read these before trusting anything below about them."
                     % (len(paths), shown, " and %d more" % more if more > 0 else ""))
    lines += ["- what is in flight: `.chamnan/STATE.md`", "",
              "## What the person asked last, oldest first", ""]
    asked = last_user_messages(transcript)
    if not asked:
        lines.append("_Nothing readable — start from STATE.md._")
    for text in asked:
        one = redact.for_a_terminal(redact.scrub(" ".join(text.split())))
        if len(one) > HANDOFF_MESSAGE_CHARS:
            one = one[:HANDOFF_MESSAGE_CHARS].rstrip() + " …"
        lines.append("- " + one)
    return "\n".join(lines) + "\n"


def write_handoff(repo, session_id, transcript, last_at, why):
    """Write the handoff into `repo`'s workspace logs; its path, or None when it could not be."""
    import workspace as ws
    dest = ws.workspace(repo) / "logs" / HANDOFF_NAME
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    changed = []
    if last_at is not None:
        try:
            import time
            import coedit
            changed = coedit._git_edits(repo, time.time(), last_at.timestamp())
        except Exception:          # noqa: BLE001 — a handoff without this line is still a handoff
            changed = []
    ok = ws.atomic_write_text(dest, handoff_text(session_id, transcript, last_at, why, changed))
    return dest if ok else None
