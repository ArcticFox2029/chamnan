"""Which file you change next, learned by counting — no model call, no user command.

The gap this closes was measured rather than assumed. On a real work repository chamnan recorded
zero sessions, decisions, lessons, rules and threads across three days and 764 commands, while
Claude Code's own memory tool captured six substantive lessons from the same work in the same
window. chamnan's knowledge only accumulates when somebody runs a command, and on that repository
nobody ran one — chamnan's own commands were invoked zero times in the whole period.

So the question became: what can be learned from what the hooks ALREADY see, without asking the
user for anything and without a model?

Command signatures cannot answer it. `commands.jsonl` stores the first token, and on that
repository the top of the list is `ssh` 107 times, `sudo` 43, `curl` 23, `def`, `tr`, `puts` —
`workflows.repeated()` returns None on all 2,477 entries across both real logs. "You ran ssh 107
times" is not a lesson.

Edits can. Measured across 16 real sessions and 929 edited files, asking "of the times A was
edited, how often was B edited within the next five edits":

    pmg-evidence-print.html  ->  pmg-evidence.html        10/10   100%
    shop_sim.mjs             ->  bank_sim.mjs             10/10   100%
    chamnan-candidates       ->  run_tests.py              9/9    100%
    claude_session2.sh       ->  start_recheckapp.command  9/9    100%

45 pairs cleared a 40% bar. That is a real, deterministic signal about this repository, available
for the cost of counting, and it is the shape of thing the native memory tool wrote by hand.

Two things this deliberately is not. It is not a dependency graph — `lib/impact.py` reads imports
and answers "what breaks", which is a different and stronger question. This answers "what did you
touch next", which is habit, and habit includes the test file, the changelog and the config that no
import edge would ever show. And it is not stored as a derived artefact: the log is the record, the
correlation is computed on read, so there is nothing to regenerate, invalidate, or merge.
"""
import json
import subprocess
import workspace as ws
import time
from collections import Counter, defaultdict
import mdblock

LOG = "logs/edits.jsonl"
# How many later edits count as "next". Five was not tuned: it is the window the measurement above
# used, and widening it turns "I changed the test with the code" into "I was in the same session".
WINDOW = 5
# Below this, one coincidence looks like a rule. At 8 the pairs that survive on real data are the
# ones a person would also name.
MIN_EDITS = 8
MIN_CONFIDENCE = 0.4
MAX_PARTNERS = 2
# A log older than this describes a codebase that has moved. Kept in step with the rest of the
# workspace's retention rather than invented here.
MAX_AGE_DAYS = 30


# 🐛 The log was appended to and never bounded. Listing it in `SELF_PRUNING_LOGS` stops the
# directory sweep deleting the whole feature after a quiet week, but that list is a PROMISE that the
# file bounds itself by record — and this one did not, so it just grew. Measured: ~1.7 µs per line
# on read, which reaches ~512 ms per lookup at 300,000 lines, on a hook that fires on every Read,
# Edit and Write. The retention the sweep applies is mtime-based and structurally cannot catch a
# file that is appended to every day.
MAX_LINES = 20_000
# 🎯 [owner 2026-09-23] "12 months, no more" — a condition on every log this project grows from
# here. The line cap above is a SIZE bound and cannot deliver it: 20,000 lines is a few months of
# heavy work and several years of light work, so a quiet repository would carry records from three
# years ago under a cap that never trips. Both bounds apply, in the same locked pass, so the promise
# `SELF_PRUNING_LOGS` makes — that this file bounds itself by record — is true in both directions.
MAX_AGE_TRIM_DAYS = 365
# Rewritten only when it has grown well past the cap, so the cost is amortised rather than paid on
# every edit. 20,000 lines is about 1.5 MB and several months of heavy work at the rate measured
# here; the trim keeps the newest, because a co-edit habit from last quarter is not this one.
TRIM_AT = int(MAX_LINES * 1.25)


def record(wsdir, path, op=None, actor=None):
    """Append one edit. Called from the PostToolUse hook, which already fires on Write and Edit.

    🐛 The append used to happen OUTSIDE any lock (`dest.open("a")`, unguarded), with only the
    occasional trim below taking `ws.exclusive`. That is not enough: `_trim`'s rewrite replaces
    the file via `os.replace`, and a concurrent `open("a")` from this function can hold a
    descriptor to the OLD inode across that replace -- its write then lands in bytes nothing will
    ever read from `dest` again, lost the moment that descriptor closes, even though the append
    itself "succeeded". Locking only the trim (an earlier fix here) cut the loss from 63% to a few
    percent but did not close it; the append has to be inside the same lock as the trim for the
    two to never interleave. This is the same shape `tools_index.record_call` already uses for the
    tool registry -- lock the WHOLE read-modify-write, not just the write, and skip (never write
    unlocked) when the lock is busy. Reproduced before this fix: 6 processes x 40 appends against a
    file already past the size gate, 151-239 of 240 (63% down to under 1%, but not 0) lost across
    repeated runs, always silent and always reported as success.
    """
    try:
        dest = wsdir / LOG
        dest.parent.mkdir(parents=True, exist_ok=True)
        with ws.exclusive(dest) as held:
            # A dropped record under contention is the cheap outcome; a lost update from writing
            # an unserialised snapshot is not -- same choice tools_index.record_call and
            # workflows.record() already make for exactly this shape of shared, hot-path log.
            if not held:
                return
            with dest.open("a", encoding="utf-8") as fh:
                row = {"at": int(time.time()), "fp": str(path)}
                # Absent rather than empty when it does not apply, so a main-thread edit costs the
                # same two keys it has always cost and a reader can tell "the session did this"
                # from "an agent did this and we could not say which".
                if op:
                    row["op"] = str(op)[:16]
                row.update(actor or {})
                fh.write(json.dumps(row) + "\n")
            _trim(dest)
    except OSError:
        pass          # a read-only checkout must still be able to edit files


def _trim(dest):
    """Drop the oldest lines once the file has drifted past the cap. Silent, and never partial.

    Called from inside `record()`'s `ws.exclusive(dest)` block -- never on its own -- so the read
    below is never stale and the write below never races a concurrent append. Written through a
    per-pid temp and `os.replace` regardless, for the reason the ages file needed the same
    treatment: a shared staging name is not made safe by an atomic replace on its own, and a
    half-written ledger reads as a torn line rather than as an error.
    """
    try:
        # 🐛 The gate was `TRIM_AT * 40` bytes on the assumption of a 40-byte line. A real line with a
        # short path is about 33, so a file could sit 5,800 lines over the cap and never trip it —
        # the cheap check made the cap unenforceable rather than merely late. Bounded BELOW the
        # shortest line a record can be (`{"at": N, "fp": "a"}` is 28 with its newline), so this can
        # only ever fire early, which costs one read, never late, which costs the cap.
        if dest.stat().st_size < TRIM_AT * 20:
            return
        lines = dest.read_text(encoding="utf-8-sig", errors="replace").splitlines(True)
        if len(lines) <= TRIM_AT:
            return
        kept = lines[-MAX_LINES:]
        ws.atomic_write_text(dest, "".join(_within_age(kept)))
    except OSError:
        pass


def _within_age(lines, now=None):
    """The tail of `lines` from the first record this cannot prove is older than the window.

    The log is append-ordered, so "the first line to keep" is all this has to find: everything after
    it is newer. A line that cannot be parsed, or carries no `at`, counts as NOT provably old and
    therefore starts the tail — dropping it would make an unreadable line a reason to delete the
    readable records that follow it, and this function may only delete what it can prove.
    """
    cutoff = (now or time.time()) - MAX_AGE_TRIM_DAYS * 86400
    for i, line in enumerate(lines):
        try:
            at = json.loads(line).get("at")
        except (ValueError, AttributeError):
            return list(lines[i:])
        if not isinstance(at, (int, float)) or at >= cutoff:
            return list(lines[i:])
    return []


def _sequence(wsdir):
    cutoff = time.time() - MAX_AGE_DAYS * 86400
    out = []
    try:
        with (wsdir / LOG).open(encoding="utf-8-sig", errors="replace") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except (ValueError, RecursionError):
                    continue          # a torn append is one lost edit, not a broken feature
                if isinstance(rec, dict) and rec.get("fp") and (rec.get("at") or 0) >= cutoff:
                    out.append(rec["fp"])
    except OSError:
        return []
    return out


def contested(wsdir, window=WINDOW, since_days=MAX_AGE_DAYS):
    """[(path, [actors])] for files two or more DIFFERENT actors wrote inside `window` edits.

    🎯 [R43 #5, and the owner's direction A] Measured on real GitHub history: pull requests from
    different agents conflict 41.7% of the time against 19.8% when they come from the same one. The
    question that follows — *did two agents just write the same file* — could not be asked here
    because `edits.jsonl` recorded only a time and a path. It records who since 2026-09-23.

    **This is the reader that justifies the field.** A log nobody queries is weight, not evidence,
    and the field was added with this in the same change rather than on the promise of a later one.

    Why the WINDOW rather than the whole log: two agents editing one file a week apart is ordinary
    work on a shared codebase. Inside five edits of each other is the shape that loses one of them.

    The main thread counts as an actor, under the name `session`. A subagent overwriting what the
    session just wrote is the same defect as two subagents doing it, and leaving the main thread out
    would hide the commonest case — which is the mistake `_de_silent`'s own comment records in a
    different form: an exemption needs a reason, and this one would have had none.
    """
    cutoff = time.time() - since_days * 86400
    rows = []
    try:
        with (wsdir / LOG).open(encoding="utf-8-sig", errors="replace") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except (ValueError, RecursionError):
                    continue
                if not isinstance(rec, dict) or not rec.get("fp"):
                    continue
                if (rec.get("at") or 0) < cutoff:
                    continue
                rows.append((rec["fp"], rec.get("ag") or rec.get("ty") or "session"))
    except OSError:
        return []
    out = {}
    for i, (fp, who) in enumerate(rows):
        # Look BACK over the window rather than forward, so one pass answers it and a file edited
        # at the very end of the log is treated like any other.
        near = {w for f, w in rows[max(0, i - window):i] if f == fp}
        if near and near != {who}:
            out.setdefault(fp, set()).update(near | {who})
    return sorted(((fp, sorted(who)) for fp, who in out.items()),
                  key=lambda r: (-len(r[1]), r[0]))


def partners(wsdir, path, window=WINDOW):
    """[(other_path, times, confidence)] for files usually edited right after `path`.

    Confidence is P(B edited within the window | A edited), and B is counted at most once per edit
    of A — the obvious version counts every co-occurrence in the window and produces confidences
    above 100%, which is how the first measurement of this was wrong.
    """
    seq = _sequence(wsdir)
    if not seq:
        return []
    edits = Counter(seq)
    if edits.get(str(path), 0) < MIN_EDITS:
        return []
    follows = defaultdict(int)
    target = str(path)
    for i, a in enumerate(seq):
        if a != target:
            continue
        for b in set(seq[i + 1:i + 1 + window]):
            if b != target:
                follows[b] += 1
    n = edits[target]
    rows = [(b, c, c / n) for b, c in follows.items() if c / n >= MIN_CONFIDENCE and c >= 3]
    rows.sort(key=lambda r: (-r[2], -r[1], r[0]))
    return rows[:MAX_PARTNERS]


def line(wsdir, path, display=str):
    """One sentence for the file pointer, or "" when there is nothing worth saying."""
    rows = partners(wsdir, path)
    if not rows:
        return ""
    parts = ", ".join(f"`{mdblock.as_quoted(display(b))}` ({p * 100:.0f}%)"
                     for b, _, p in rows)
    return f"_You usually change {parts} right after this one._"


# How long a quiet gap has to be before the next edit belongs to a different sitting. Four hours is
# not tuned, and cannot be: nothing the hooks receive marks where one session ended, because the
# record below carries only `at` and `fp`. What four hours buys is that it is longer than any break
# taken mid-task and shorter than a night, which is the only distinction this needs to make. Adding
# a session id to the record would be exact, but it would also make this feature dead until enough
# new records accumulated, and the point of it is that the data is ALREADY on disk.
SITTING_GAP = 4 * 3600
# A sitting older than this is not "where you left off", whatever the gap says.
SITTING_MAX_AGE_DAYS = 7
SITTING_MAX_FILES = 5


# How far back to look for commits, and how many. Both bound a `git log` on a repository this
# code knows nothing about: a monorepo with a hundred commits an hour must cost the same as a quiet
# one. The window matches SITTING_MAX_AGE_DAYS so neither source can report a sitting the other
# would have aged out.
SITTING_GIT_COMMITS = 60

# The byte a commit timestamp is emitted behind, so that no PATH can be mistaken for one. Git
# C-quotes any path containing a control character whatever `core.quotePath` says -- measured, a
# file named "\x011234567890" comes back as `"\0011234567890"` -- so a path line can never begin
# with this however the file is named. A bare timestamp had no such guarantee; see the parse below.
_STAMP = "\x01"


def _git_edits(root, now, cutoff):
    """[(at, path)] for files touched by recent commits, or [] when git cannot answer.

    🐛 [2026-09-22] (self-measured) `edits.jsonl` is written from the PostToolUse hook, which fires
    on Edit and Write. A session that changes files by RUNNING something -- a `sed`, a patch script,
    a formatter -- writes nothing to it, and Claude Code's own auto mode instructs exactly that
    ("make file changes with sed, heredocs, or short scripts, rather than using the dedicated
    Read, Edit, or Write tools"). Measured on the session that found it: the ledger's newest entry
    was 15.3 hours old while six files had been changed that day, and the hand-off named last
    night's work as though nothing had happened since.

    git sees a change whatever made it, so it is read as a second source rather than a replacement:
    the ledger still carries edits that have not been committed, and git carries the ones no tool
    event ever saw. Merged, not chosen between -- picking the newer source alone would drop
    uncommitted work the moment anything was committed.
    """
    try:
        out = subprocess.run(
            # 🐛 The workspace's own bookkeeping is excluded, and without it this answered with
            # it. `.chamnan/` changes in most commits of any repository that uses chamnan -- a
            # state file, a tool registry, a check floor -- so ranking by how often a path appears
            # put chamnan's own housekeeping at the top of a line whose whole job is to remind
            # somebody what THEY were doing. `_map_is_current_by_git` already excludes the same
            # directory for the same reason, and this is that convention rather than a new idea.
            # 🐛 [audit-qa 2026-09-22] `core.quotePath` defaults to true, so git C-quotes every
            # byte above ASCII: a Thai or Japanese filename arrived here as
            # `"\340\270\243\340\270\262..."` and was handed straight to the hand-off line, which
            # is prose somebody reads. chamnan ships into other people's repositories, where a
            # non-English filename is ordinary rather than exotic.
            ["git", "-c", "core.quotePath=false", "-C", str(root),
             "log", "-n", str(SITTING_GIT_COMMITS),
             "--since=%d" % int(cutoff), "--name-only", "--pretty=format:" + _STAMP + "%ct",
             "--", ".", ":(exclude).chamnan"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
    except ws.git_cannot_answer():
        return []
    if out.returncode != 0:
        return []
    rows, at = [], None
    for line in out.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        # A commit timestamp arrives behind _STAMP; anything else is a path.
        #
        # 🐛 [audit-qa 2026-09-22] The timestamp used to be bare, told apart from a path by being
        # ten digits long -- and the comment here said the LENGTH was the safeguard against an
        # all-digit path. It is not: an epoch is exactly ten digits, so a file named `1234567890`
        # is not an unlikely collision but an exact one. Reproduced: one such file at the root of a
        # commit was read as a timestamp of February 2009, and every path AFTER it in that commit
        # then failed the window test and vanished. One bad name silently cost the rest of the
        # commit, which is the false absence this line is supposed to prevent.
        if line.startswith(_STAMP) and line[1:].isdigit():
            at = int(line[1:])
            continue
        if at is not None and cutoff <= at <= now:
            rows.append((at, line))
    return rows


def last_sitting(wsdir, now=None):
    """(files, seconds_ago) for the most recent unbroken run of edits, newest file first.

    Why this exists, measured rather than assumed. Resuming a long conversation re-sends the whole
    transcript, and on a resume the cache has expired -- so every token is charged at the
    cache_WRITE price, which is 12.5x cache_read. Three real resumes of one repository cost 843,816,
    849,857 and 859,794 tokens on their FIRST request, before the user had said anything. The
    transcript those tokens re-transmit is 161 MB sitting on the same disk as this ledger.

    So the expensive part of a resume is not the knowledge, it is the transport. What somebody
    resumes a session FOR -- which files they were in the middle of -- is already recorded here, and
    reading it locally costs no tokens at all. This returns it so a fresh session can start knowing
    what a resumed one would have paid ~860,000 tokens to be told.

    Cost, measured rather than extrapolated: 0.59 ms median on this repository's 218-line ledger
    and 60.6 ms at `MAX_LINES`, once per session, against a session start of 2,133 ms. The whole
    file is read even though the sitting is always at its end, and that is a deliberate trade: a
    tail read would buy back those 60 ms and add a torn-first-line case plus a silent wrong answer
    whenever a sitting ran longer than the window chosen for it.

    It deliberately reports files and nothing else. The reasoning behind an edit is not in this log,
    and inventing a summary of intent from a list of paths would be the kind of confident guess that
    is worse than saying less.
    """
    now = time.time() if now is None else now
    cutoff = now - SITTING_MAX_AGE_DAYS * 86400
    rows = []
    try:
        with (wsdir / LOG).open(encoding="utf-8-sig", errors="replace") as fh:
            for raw in fh:
                try:
                    rec = json.loads(raw)
                except (ValueError, RecursionError):
                    continue          # a torn append is one lost edit, not a broken feature
                if not (isinstance(rec, dict) and rec.get("fp")):
                    continue
                at = rec.get("at") or 0
                if at >= cutoff and at <= now:
                    rows.append((at, rec["fp"]))
    except OSError:
        rows = []
    # The other half, which the ledger structurally cannot see -- but only when the ledger looks
    # incomplete. Measured: 32 ms of the git call is the process spawn alone and cannot be tuned
    # away, so a session that edits through the Edit and Write tools should not pay it at all. If
    # the ledger already has something inside the current sitting, it saw this session's work.
    newest_logged = max((at for at, _ in rows), default=0)
    if now - newest_logged > SITTING_GAP:
        rows += _git_edits(wsdir.parent, now, cutoff)
    if not rows:
        return [], 0
    # The log is appended to under a lock, so it is in order -- but a clock that stepped backwards
    # would otherwise silently truncate the sitting to one record, so sort rather than trust it.
    rows.sort()
    newest = rows[-1][0]
    keep = [rows[-1]]
    for at, fp in reversed(rows[:-1]):
        if keep[-1][0] - at > SITTING_GAP:
            break
        keep.append((at, fp))
    # 🐛 Ranked by recency alone, this named whatever the newest commit happened to touch --
    # `.gitignore`, a tool registry, a generated state file -- while the modules actually being
    # worked on sat one commit behind. Factually right and useless, which is the failure a
    # hand-off has: the reader glances at it, recognises nothing they were doing, and stops
    # reading the line. Ranked by how many times a path appears in the sitting instead: a file
    # touched once by a tool loses to one edited repeatedly, and recency breaks the ties.
    hits, seen_at = {}, {}
    for at, fp in keep:
        hits[fp] = hits.get(fp, 0) + 1
        seen_at[fp] = max(seen_at.get(fp, 0), at)
    files = sorted(hits, key=lambda fp: (-hits[fp], -seen_at[fp], fp))
    return files[:SITTING_MAX_FILES], int(now - newest)


def _ago(seconds):
    """"13h", "2d" -- the coarsest unit that is still true, because precision here is noise."""
    if seconds < 3600:
        return "%dm" % max(1, seconds // 60)
    if seconds < 36 * 3600:
        return "%dh" % (seconds // 3600)
    return "%dd" % (seconds // 86400)


def sitting_line(wsdir, now=None):
    """One line naming where the last sitting stopped, or "" when the log cannot say.

    No advice and nothing asked of the reader: a warning here was rejected on the grounds that
    people go back to working in the repository regardless of what they are told, which is correct.
    This is the information a resume would have carried, not a suggestion to resume differently.
    """
    files, ago = last_sitting(wsdir, now=now)
    if not files:
        return ""
    parts = ", ".join("`%s`" % mdblock.as_quoted(fp) for fp in files)
    return "_Last edited %s ago: %s_" % (_ago(ago), parts)
