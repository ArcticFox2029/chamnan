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
import subprocess
import re
import mdblock
import tokens
from pathlib import Path
import workspace as ws
import time

# Written by skills/resume. Deliberately flat markdown with no frontmatter: the file is meant to be
# read by a person in a diff, and a header block would be one more thing to get wrong.
HEADINGS = ("Done", "Remaining", "Files", "Decisions", "Blockers")

# Only these reach the next session. "Done" is history and "Files" is recoverable from git; what
# the next session cannot work out for itself is what was left and what was in the way.
CARRIED = ("Remaining", "Blockers")

# A record is bounded so one enormous session cannot swamp the injection. Roughly the same order as
# state_token_budget's char-equivalent in the hook (see lib/state.py).
#
# 🐛 [2026-09-07] In TOKENS, not characters. `lib/state.py`'s own docstring names this exact
# anti-pattern two files away — "a flat character cap mis-prices any file that is not mostly Latin
# script" — and this cap was the member of that set nobody revisited. Measured with chamnan's own
# estimator: a Thai carry-forward note costs 1.99x the tokens of an English one at the same
# character count, so a repository working in Thai was silently spending twice the injection budget
# this number was chosen to bound (R10 acc3, 2026-09-07). 500 is what 1,200 characters of English came to, so
# the English case is unchanged and only the mis-priced one moves.
MAX_CARRY_TOKENS = 500

_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def _interrupted_by(root):
    """(what git is in the middle of, how to finish it, how to undo it), or None.

    git does not put this in `status --porcelain` -- a conflicted merge shows as `UU path` and a
    rebase shows as an ordinary dirty tree, neither of which says "you are stuck". The state lives
    as marker files inside the git directory, which is the cheapest and most reliable place to read
    it: no extra subprocess on a path that already spends three.

    Order matters. A rebase that hits a conflict leaves BOTH a rebase directory and, for some
    strategies, merge markers; naming it a merge would send the reader at `git merge --abort`,
    which is not the command that gets them out.
    """
    git_dir = Path(root) / ".git"
    if git_dir.is_file():
        # A linked worktree: `.git` is a file holding `gitdir: <path>`, and the state lives there.
        try:
            pointed = git_dir.read_text(encoding="utf-8-sig", errors="replace").strip()
        except OSError:
            return None
        if not pointed.startswith("gitdir:"):
            return None
        git_dir = Path(pointed.split(":", 1)[1].strip())
        if not git_dir.is_absolute():
            git_dir = (Path(root) / git_dir).resolve()
    for marker, what, finish, undo in (
            ("rebase-merge", "a rebase", "git rebase --continue", "git rebase --abort"),
            ("rebase-apply", "a rebase", "git rebase --continue", "git rebase --abort"),
            ("CHERRY_PICK_HEAD", "a cherry-pick",
             "git cherry-pick --continue", "git cherry-pick --abort"),
            ("REVERT_HEAD", "a revert", "git revert --continue", "git revert --abort"),
            ("MERGE_HEAD", "a merge", "git commit", "git merge --abort")):
        try:
            if (git_dir / marker).exists():
                return what, finish, undo
        except OSError:
            return None
    return None


def directory(root):
    from workspace import workspace
    return workspace(root) / "sessions"


_SESSION_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def records(root):
    """Every session record, newest first. Sorted by filename date, mtime tiebreaking two records
    that share the same date."""
    d = directory(root)
    if not d.is_dir():
        return []
    # 🐛 Sorted by filename alone, so ANY name starting with a letter beat every `YYYY-…` record:
    # a `TEMPLATE.md`, a `README.md` or a `notes.md` dropped in this directory became "the last
    # session", and the header still said so, which is how it read as real. `prune()` already
    # treats the filename date as the authority; this did not. Dated records first, newest first;
    # anything undated sorts behind all of them rather than in front.
    #
    # 🐛 Two records filed the SAME day still sorted by the rest of the filename as plain text --
    # `2026-09-02-morning-cleanup.md` beat `2026-09-02-evening-fix-the-thing.md` because "morning"
    # > "evening" alphabetically, regardless of which was actually written later. `latest()` then
    # handed the next session a stale "all done" instead of the real blocker written that evening.
    # mtime only breaks a tie between two records whose filename DATE is identical -- different
    # days are still ordered purely by the date in the name, unaffected by a clone or checkout
    # resetting mtimes, which is the failure mode the rest of this file already treats as real
    # (see `prune()`'s own fallback below).
    def _key(p):
        m = _SESSION_DATE.match(p.name)
        try:
            mtime = p.stat().st_mtime
        except OSError:
            mtime = 0.0
        return (bool(m), m.group(0) if m else "", mtime)
    # Same refusal as threads/, candidates/ and memory/. This one is the worst of the four: a
    # session record is read by the SessionStart hook with no user action at all, so a planted link
    # put a file's title and structure into every session's block automatically.
    return sorted((p for p in d.glob("*.md")
                   if p.is_file() and not ws.is_store_index(p) and ws.inside(p, root)),
                  key=_key, reverse=True)


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
    text = text if text is not None else path.read_text(encoding="utf-8-sig", errors="replace")
    for line in text.splitlines():
        # See timeline.title_of — one definition of what a heading is, in mdblock.
        title = mdblock.heading_title(line)
        if title is not None:
            return title
    return path.stem


def where_git_says_you_stopped(root, limit=6, name_files=True):
    """What the repository itself says about the last session, when nobody wrote a record.

    `name_files=False` keeps the sentence and the count and drops the list of names. Pass it when
    the reader has already been handed the same list by something else -- see the measurement in
    the block below. It is a CALLER's decision, deliberately, and not read from the environment:
    `chamnan-context --write cursor` run from inside a Claude Code session would look like Claude
    Code to any env check, and would then starve Cursor of filenames it has no other source for.
    The hook knows who it is writing for; this function cannot.

    `carry_forward` returns "" unless somebody ran `/chamnan:resume`, and measured across 18 real
    sessions on this machine exactly one did — 5.6%. So the section a session most wants, "where did
    I stop", is absent from nineteen sessions in twenty, and the reason is a command nobody
    remembers rather than an absence of anything to say.

    git already knows. An uncommitted working tree IS where the last session stopped, it needs
    nothing from the user, and it cannot go stale — it is read fresh every time.

    Deliberately weaker than a written record and says so in its own wording: it reports what is
    unfinished, never why, and a real record supersedes it entirely. This is the floor, not a
    replacement.
    """
    # 🐛 [2026-09-07] A missing git and a directory that is not a repository both made `git_owns`
    # answer False, and this returned "" for either — so on a machine without git the section that
    # tells a session where it stopped just vanished, with nothing anywhere saying why. The two need
    # different answers: not-a-repository is correctly silent (there is genuinely nothing to say),
    # while git-not-installed is a thing the reader can fix and would want to (R10 agent 1).
    if not ws.git_is_installed():
        return ("**Where the last session stopped** — not available: `git` is not on this machine's "
                "PATH, and this section is read from the working tree. Everything else in this "
                "block works without it.")
    # `git_can_speak_for`: the query below is `status --porcelain -- . :(exclude)<ws>`, already
    # scoped to this directory, so a workspace in a monorepo subproject gets its own answer rather
    # than an empty section. See that function.
    if not ws.git_can_speak_for(root):
        # A git old enough to reject `-C` fails the call above, and "not a repository" is the wrong
        # thing to tell that reader — the two are indistinguishable from a return code, which is
        # why `git_can_speak_for` records which one it saw. `-C` arrived in git 1.8.5 (2013) and
        # RHEL 7 and CentOS 7 shipped 1.8.3.1 for years, so this is reachable; and "install git" is
        # useless advice to somebody who already has it (R13 agent 1).
        if ws.git_is_too_old():
            return ("**Where the last session stopped** — not available: the `git` on this machine "
                    "is too old for `git -C`, which arrived in git 1.8.5 (2013) and is what every "
                    "query here uses. Upgrading git restores this section; everything else in this "
                    "block already works without it.")
        # 🐛 [2026-09-06] Without this, a directory holding a `.git` git itself refuses -- an
        # interrupted `git init`, a copied-without-contents `.git` -- made every call below walk up
        # and answer about the nearest REAL repository above it. Reproduced: this section reported
        # "10 uncommitted file(s)" and named a branch, for a directory containing one file and no
        # commits at all; both numbers were the ancestor's (R6 acc3, 2026-09-06, first ten minutes).
        return ""
    try:
        # 🐛 [2026-09-06] chamnan's OWN workspace was counted as the user's uncommitted work. git
        # folds an entirely-untracked directory into one `??` line, so the scaffold this plugin
        # creates on its first run -- .gitattributes, .gitignore, .version, config.json, no user
        # content at all -- added exactly +1 to the count on every session until somebody committed
        # `.chamnan/`, which nothing ever tells them to do. On a clean tree it did worse than
        # inflate: it produced the whole section, reading "1 uncommitted file(s), and nobody
        # recorded what for", which is flatly false (R15 agent 6).
        #
        # Excluded rather than counted, and that is the right direction even once `.chamnan/` IS
        # committed: this section answers "where did I stop", and STATE.md changing every session
        # is not an answer to it.
        _ws_rel = ws.workspace(root).name
        st = subprocess.run(["git", "-C", str(root), "-c", "core.quotePath=false",
                             "status", "--porcelain", "--", ".", f":(exclude){_ws_rel}"],
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace",
                            timeout=5)
        if st.returncode != 0:
            return ""
        lines = [l for l in st.stdout.splitlines() if l.strip()]
        if not lines:
            return ""          # a clean tree has nothing to carry forward, which is the good case
        br = subprocess.run(["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace",
                            timeout=5)
        branch = br.stdout.strip() if br.returncode == 0 else ""
        # 🐛 `--abbrev-ref HEAD` returns the literal string "HEAD" when the checkout is DETACHED,
        # so the block said "on `HEAD`" as though that were a branch — in every CI checkout, every
        # `git bisect`, and every checkout of a tag. A reader has no way to tell that from a branch
        # somebody really named HEAD, and the whole point of this line is that it is git's answer
        # rather than a guess.
        #
        # The short sha is what is actually true there, and it is also the thing you would type to
        # come back to it. Best-effort: if that call fails too, the line simply says nothing about
        # where you are, which is better than saying something false.
        if branch == "HEAD":
            sha = subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                                 stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=5)
            short = sha.stdout.strip() if sha.returncode == 0 else ""
            branch = f"a detached HEAD at {short}" if short else ""
    except ws.git_cannot_answer():
        return ""

    # 🐛 [2026-09-06] A session resumed in the middle of a rebase or a conflicted merge was told it
    # had an ordinary dirty tree -- a file count and a branch name -- and the one fact that changes
    # what the reader should do next was dropped: you are stuck, and the way out is `--continue` or
    # `--abort` (R6 acc3, 2026-09-06, unusual repositories). git records the state in its own directory rather
    # than in `status --porcelain`'s first two columns, so it has to be asked separately. Read from
    # disk, not from another `git` call: this is a section that already costs three subprocesses.
    interrupted = _interrupted_by(root)

    # Paths come from the repository, so they are made inert the way every other repository-authored
    # string in the injected block is. The caller scrubs.
    names, more = [], max(0, len(lines) - limit)
    for line in lines[:limit]:
        names.append(f"`{mdblock.as_quoted(line[3:].strip(), 60)}`")
    tail = f" _+{more} more_" if more else ""
    # A detached HEAD is described in words rather than quoted as a name -- backticks around
    # "a detached HEAD at 1a2b3c4" would read as a branch with that name, which is the same
    # mistake one level down.
    if branch.startswith("a detached HEAD"):
        where = f" on {mdblock.as_quoted(branch, 40)}"
    else:
        where = f" on `{mdblock.as_quoted(branch, 40)}`" if branch else ""
    lead = (f"**Where the last session stopped**, as the working tree has it{where} — "
            f"nobody recorded it, so this is git's answer rather than anyone's:\n")
    if interrupted:
        lead = (f"**This repository is in the middle of {interrupted[0]}**{where} — that is why the "
                f"tree looks like this. Finish it with `{interrupted[1]}` or undo it with "
                f"`{interrupted[2]}` before treating anything below as work in progress:\n")
    if not name_files:
        # 🐛 Claude Code injects its own `gitStatus` block once per session, and on a dirty tree it
        # already lists every changed file with no truncation, before any hook runs. Measured on
        # this repository with 21 files changed: chamnan's own list is 216.37 tokens against 82.71
        # for the sentence and the count alone -- 133.66 tokens, 61.8% of the section, spent
        # restating names the reader is holding. This section fires when no `/chamnan:resume`
        # record exists, which its own docstring measures at 17 of 18 real sessions.
        #
        # The COUNT stays. It is the one thing the harness's block does not say in a sentence, and
        # it is what makes the line worth reading at a glance.
        return f"{lead}{len(lines)} uncommitted file(s), and nobody recorded what for.\n"
    return lead + f"{len(lines)} uncommitted file(s): " + ", ".join(names) + tail + "\n"


# How many same-day records carry forward at once. One is the single-developer case and the
# common one; the cap exists so a busy shared day cannot push the whole injected block over its
# budget, and it is small because MAX_CARRY_TOKENS is shared across all of them.
MAX_CARRIED_RECORDS = 3


def _outstanding(path):
    """(title, body) of what one record leaves unfinished, or None when it leaves nothing."""
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return None
    found = _sections(text)
    parts = []
    for name in CARRIED:
        body = found.get(name, "").strip()
        if body and not _is_nothing(body):
            # Demoted the same way a rule's body is: this text is free prose someone wrote in a
            # `## Remaining` / `## Blockers` section, dropped here under the hook's own `###`
            # heading, and an untouched `#` in it reads as a NEW section of the injected block
            # rather than a line inside this one.
            parts.append(f"**{name}**\n{mdblock.demote_headings(body)}")
    return (title_of(path, text), "\n\n".join(parts)) if parts else None


def carry_forward(root):
    """The part of the newest day's records the next session needs: unfinished work, and blockers.

    Returns "" when there is no record, when nothing is outstanding, or when the files cannot be
    read. An empty return means the hook injects nothing at all, which is the right outcome for a
    repository where the last session finished what it started.

    🐛 This read exactly ONE record — `latest()`, which is `records()[0]`. `records()` already
    tie-breaks two same-day records by mtime, and mtime is reset by a clone or a checkout, which is
    precisely the situation where a second record exists: two people working the same repository
    on the same day. Their files merge cleanly in git, so nothing looks wrong, and one person's
    "Remaining" then never reaches the next session at all. Reproduced through the real
    `records()`/`latest()` calls.

    So the unit is the DAY, not the file. Every record sharing the newest date is carried, each
    under its own title, and the single-record case renders exactly as it did before — that is the
    common case and it must not pay for this.
    """
    found = records(root)
    if not found:
        return ""
    newest = _DATE.match(found[0].name)
    same_day = [p for p in found
                if newest and (m := _DATE.match(p.name)) and m.group(1) == newest.group(1)]
    group = (same_day or [found[0]])[:MAX_CARRIED_RECORDS]

    carried = [c for c in (_outstanding(p) for p in group) if c]
    if not carried:
        return ""

    when = newest.group(1) if newest else found[0].stem
    if len(carried) == 1:
        # 🐛 The title went in raw HERE and through `one_line` in the branch below -- the same
        # value, two lines apart, guarded on one path and not the other. A record whose `# Title`
        # carried an ESC/OSC terminal-title sequence and a bidi override reached the injected
        # block byte-for-byte, and only when the repository had exactly ONE unfinished record,
        # which is the common case. The suite never saw it because the hostile fixture's record
        # was dated old enough for retention to delete it before the hook read anything.
        # The BODY below is bounded by MAX_CARRY_TOKENS; this head was not bounded by anything,
        # and it is the same free-text `# Title` off the same kind of file.
        head = f"_Last session ({when}) — {mdblock.one_line_capped(carried[0][0])}_"
        body = carried[0][1]
    else:
        head = f"_Last session ({when}) — {len(carried)} records, all unfinished_"
        body = "\n\n".join(f"**{mdblock.one_line_capped(title)}**\n\n{text}"
                           for title, text in carried)
    if tokens.estimate(body) > MAX_CARRY_TOKENS:
        # 🐛 [2026-09-09] A flat prefix cut, and `CARRIED` puts Remaining before Blockers — so the
        # part that always survived was the first one and the part always lost was the same one
        # every time. Measured on this repository's only real record: 582 tokens against a 500
        # budget, the cut landing inside Remaining's own bullet list, and Blockers dropped whole,
        # including the line saying STATE.md was over ITS budget. Two purposes are declared in
        # `CARRIED`; one of them could never reach a session on any record above the cap.
        #
        # A share each, the way `memory.rules_text` divides its budget between rules, so both
        # arrive shortened rather than one arriving intact and the other not at all. Under the cap
        # nothing changes — that is the common case and it must not pay for this (R5 agent1, 2026-09-09).
        parts = re.split(r"(?m)^(?=\*\*)", body)
        parts = [x for x in parts if x.strip()]
        if len(parts) > 1:
            # EQUAL, not proportional, and that is the design rather than an accident of the
            # arithmetic. Measured on the one real record: `Remaining` keeps 25.4% of itself and
            # `Blockers` 35.1%, because the smaller part gets the same raw budget as the larger and
            # therefore keeps more of what it had. That is the outcome wanted — "a summary that
            # drops the blocker is worse than one that drops the prose" — and a proportional split
            # would reverse it, giving the verbose part more room precisely because it is verbose.
            #
            # Written down because it was produced as a side effect and named nowhere, which is how
            # a good property gets "fixed" by somebody tidying an asymmetry they think is a bug
            # (R7 agent 1).
            share = max(60, MAX_CARRY_TOKENS // len(parts))
            trimmed = []
            for part in parts:
                if tokens.estimate(part) <= share:
                    trimmed.append(part.rstrip())
                    continue
                cut = mdblock.cut_outside_a_fence(part, tokens.cut_at(part, share))
                trimmed.append(part[:cut].rstrip().rsplit("\n", 1)[0] + "\n\n_…cut here._")
            body = "\n\n".join(trimmed) + \
                f"\n\n_Every part above is shortened — read " \
                f"`{mdblock.as_quoted(group[0].name)}` for any of them in full._"
        else:
            body = body[:mdblock.cut_outside_a_fence(
                body, tokens.cut_at(body, MAX_CARRY_TOKENS))].rsplit("\n", 1)[0] + \
                f"\n\n_…truncated — read `{mdblock.as_quoted(group[0].name)}` for the rest._"
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

    ONE FILE IS ALWAYS SPARED when the pass would take every one -- `keep_the_newest`. That is
    deliberate and it is the difference between this docstring and the truth: a directory holding
    nothing but aged files keeps its newest, however far past the window it is, and a directory
    holding exactly one aged file never empties at all. The guard cannot tell "a clock jumped 400
    days and doomed everything at once" from "this directory went quiet a month ago", because from
    the mtimes alone those look identical. Judged from the user's side, the trade is not close: one
    stale file left behind is invisible, and a whole retention store wiped by a clock glitch is not.
    Reproduced 2026-09-08 (R7 agent 3); the claim above used to be stated without this paragraph.
    """
    d = directory(root)
    if not d.is_dir() or not days:
        return 0
    cutoff = time.time() - days * 86400
    removed = 0
    candidates = [q for q in d.glob("*.md") if q.is_file() and not ws.is_store_index(q)]
    doomed = []
    for path in candidates:
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
                    _ts = calendar.timegm((y, m, dd, 12, 0, 0))
                    # 🐛 [2026-09-10] `ledger._ymd_to_ts` refuses a date in the FUTURE and this
                    # copy — the one that DELETES — never got that half. A record named
                    # `2099-01-01` gets a negative age, is never doomed, and is therefore always
                    # the file `keep_the_newest` spares when the pass would take every one: a
                    # single typo'd filename makes the "always spare one" promise protect the
                    # wrong file and delete the genuinely newest. A day of slack, so a record
                    # written in a timezone ahead of this one is not refused for being an hour
                    # early (R4 agent 3, finding 5). Third copy of this parser, third time this
                    # exact pair has been half-applied.
                    if _ts > time.time() + 86400:
                        raise ValueError("a date in the future is not an age")
                    age = time.time() - _ts
                except (ValueError, OverflowError):
                    age = None      # an impossible date is not a date; fall back to mtime
            if age is not None:
                if age > days * 86400:
                    doomed.append(path)
            elif path.stat().st_mtime < cutoff:
                doomed.append(path)
        except OSError:
            continue
    # See workspace.keep_the_newest: a pass that would take EVERY record is a clock fault, not
    # retention, and a session record is committed work rather than cache.
    for path in ws.keep_the_newest(candidates, doomed):
        try:
            path.unlink()
            removed += 1
        except OSError:
            continue
    return removed


def slug(title):
    """A filename fragment from a title. ASCII-only and short, because these names are read in a
    directory listing and in git diffs."""
    # 🐛 `mdblock.filename_safe` exists because a record titled "CON" or "nul" becomes
    # `con.md` or `nul.md`, which on Windows are the console and the bit-bucket: the write
    # does not fail, it goes to the DEVICE, and the record is gone. Its own docstring says
    s = mdblock.ascii_stem(title)
    return mdblock.filename_safe(s[:40].rstrip("-")
                                 or mdblock.fallback_name(title, "session"))


def filename(date, title):
    """The name a NEW record would take, ignoring what the directory already holds. A writer must
    use `distinct_filename` — see below."""
    return f"{date}-{slug(title)}.md"


def distinct_filename(root, date, title):
    """`filename(date, title)`, disambiguated against the records already written.

    \U0001f41b [2026-09-09] `slug()` cuts at 40 characters here — the shortest of the four stores —
    and the date prefix narrows the collision to one day without closing it. Two records written on
    the same day whose titles agree for 40 characters landed on one file and the second overwrote
    the first, which is a whole session's handoff gone (R10 agent 3, finding 4).

    The date is part of the base rather than of the suffix, so the disambiguating hash still sorts
    inside its own day and a directory listing stays chronological.
    """
    base = f"{date}-{slug(title)}"
    return f"{mdblock.distinct_stem(directory(root), base, title, title_of)}.md"
