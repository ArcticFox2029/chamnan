"""Locating and reading the .chamnan/ workspace. Shared by every bin/ command and hook.

The workspace lives at the repository root rather than somewhere under the user's home, because
everything in it is about ONE codebase: the map describes that repo's files, the skills record
procedures for that repo's stack, the state names that repo's in-flight work. Putting it beside the
code also means it can be committed, so a team shares one accumulated memory instead of each member
rebuilding their own — and a machine move carries it along with the clone.
"""
import re
import hashlib
import json
import time
import contextlib
import pathlib
import os
import sys
from pathlib import Path

WORKSPACE_DIRNAME = ".chamnan"
# Each part can be switched off independently. Nothing here is load-bearing for the others: turning
# `map` off leaves state and skills working, and vice versa. That is deliberate — the parts have
# different amounts of evidence behind them, and a user who finds one unhelpful should be able to
# drop it without losing the ones that are pulling their weight.
DEFAULT_CONFIG = {
    "map": True,        # architecture index — strongest evidence
    "state": True,      # survives compaction
    "capture": True,    # accumulate procedures as skills
    "promote": True,    # throwaway script -> permanent tool
    "report": True,     # before/after measurement
    "agents": True,     # cheap models for scan-shaped work
    # Applied by prune_logs(), which every bin/ command calls. Without this the scratch log and
    # anything else written under logs/ would grow for the life of the repo — a workspace that
    # leaks disk is not one anybody keeps.
    "log_retention_days": 7,
    # The language chamnan WRITES IN when it generates file comments and records procedures. It does
    # not touch anything already written, and it never affects the language of replies to the user.
    #
    # "en" is the default because these strings are re-read on every session, and English tokenizes
    # to roughly two-thirds of the equivalent Thai (measured 1.53x on one tokenizer — see README),
    # so the difference is paid repeatedly rather than once. That is a default, not a rule: a team
    # whose reviewers read Thai, or whose compliance process requires it, is better served by
    # comments they will actually read. Set it to whatever that team needs.
    "language": "en",
    # Ceiling on the part of MAP.md that is injected into every session. This is the number that
    # keeps the plugin from becoming the problem it exists to solve: the injection is paid on every
    # turn, so an index that grows without a limit eventually costs more than the searching it
    # replaces. 3,000 tokens is well under 1% of a 1M context window and still holds a few hundred
    # files. chamnan-map reports against it and says what to cut when it is exceeded.
    "index_token_budget": 3000,
    # A hard ceiling in BYTES on everything the SessionStart hook prints, enforced after the token
    # budgets above have already had their say. The two are not the same measurement and cannot
    # substitute for each other: the host truncates a hook's stdout over 10,000 bytes to its first
    # 2,048 plus a path on disk, and that cut is positional, so a block can be comfortably inside
    # every token budget and still lose its whole second half. 9,000 leaves margin under a limit
    # that is not ours to change. Set 0 to switch the ceiling off and take the host's cut instead.
    "output_byte_ceiling": 9000,
    # Mention it when a read is about to pull in a lock file, a minified bundle or a very large
    # file. A notice, never a block — the one time someone genuinely needs to read package-lock.json
    # is the one time refusing would be most wrong.
    "warn_on_bulk_reads": True,
    # When a file is opened, name what this repository already records about it — the decision, the
    # lesson, the procedure, and who depends on it. The same knowledge `chamnan-impact` answers on
    # demand, arriving without being asked, because the caller is a model and remembering to ask is
    # the work this plugin exists to remove. Silent when nothing matches, once per file per session,
    # and never about chamnan's own files. See lib/pointer.py.
    "pointer": True,
    # How replies in this repo should be written. "off" is the default and changes nothing.
    #
    # This is the smallest lever in the plugin and it is worth saying so where the option lives:
    # output is 8.8% of a bill, and the best-known style-compression plugin was independently
    # benchmarked at 8.5% of output tokens — roughly 0.7% of what you pay. It is here because a
    # workspace that already decides what a session reads may as well be able to say how it
    # answers, and because a per-repo setting is the honest scope for that decision: a codebase
    # can want terse answers without every other project on the machine getting them too.
    #
    #   "off"      no instruction is injected (default)
    #   "concise"  drop preamble, restatement and closing offers; keep full sentences
    #   "terse"    the above, plus fragments and tables over prose wherever they fit
    "reply_style": "off",
    # Session records — where the last stretch of work stopped. Distinct from STATE.md, which is
    # one overwritten file about the present; these are many small files, one per session, and only
    # the unfinished part of the newest one is ever injected. See lib/sessions.py.
    "resume": True,
    # On `source="resume"` the hook sends a one-line pointer instead of the whole block, but ONLY
    # when it can prove from the transcript that the earlier block is still in context -- no
    # compaction boundary after its own fence. Measured 967 tokens saved on an 8-file fixture and
    # about 3,500 on this repository's real block. Set False to resend unconditionally; the proof
    # already fails safe, so this exists for someone whose host restores transcripts differently
    # rather than as a knob anybody should need.
    "resume_pointer": True,
    # These accumulate one per working session in a directory that gets committed, so they are
    # bounded from the start rather than after somebody's repository fills up. Longer than the log
    # window because a record from three weeks ago is still the answer to "what was I doing".
    "session_retention_days": 30,
    # STATE.md sections that have not been EDITED in this many days stop being injected. Not
    # deleted, not aged by the file's own date — per section, and the clock resets on any real
    # change, so work actually in flight never ages. Pinned (📌) sections are exempt. This is the
    # one place age is treated as evidence, and lib/state.py's docstring says why STATE is the
    # exception to lib/aging.py's rule. 0 turns the pass off.
    "state_stale_days": 14,
    # Project memory — why the code is the way it is. Rules are injected every session; decisions
    # and lessons contribute a title and are read on demand. Deliberately NOT age-pruned: a session
    # record stops mattering, a decision does not. See lib/memory.py.
    "memory": True,
    # Project milestones — the handful of changes that reshaped the repository. Only the two most
    # recent TITLES are injected, so the file's length costs nothing per session. Not project
    # management: no status, no owner, no dates-as-deadlines. See lib/milestones.py.
    "milestones": True,
    # Threads — one line of work followed across the sessions it took. Only OPEN threads' titles
    # are injected, so a repository with fifty closed threads pays nothing for them. Threading is
    # a pick from a declared list, never a string match. See lib/timeline.py.
    "timeline": True,
    # environments.md — platform facts and the constraints nobody writes down ("RWO storage only",
    # "no TPM in UAT"). CONSTRAINTS are injected, versions are not: a constraint changes what an
    # agent should write, a version is a fact it can look up. Nothing here contacts an
    # environment; every line was typed by somebody who knew it. See lib/environments.py.
    "environments": True,
    # The write-skills line and the ledger line (see lib/ledger.py). Found on the workspace this
    # plugin is developed against: the hook-written logs held 700 records, every skill-written
    # store held zero, and chamnan_session_start.py never once told an agent that /chamnan:remember
    # exists. These two lines are the fix, and they are on by default because a workspace that
    # cannot see its own emptiness is the failure the rest of the memory system depends on not
    # happening.
    "ledger": True,
    # Ceiling on STATE.md's injection, in TOKENS rather than characters -- a character cap
    # mis-prices anything that is not mostly Latin script. 1700 is chosen to match what the old
    # 4,000-character cap actually injected on an English-heavy file (roughly 4000 / 2.4), so this
    # is a re-pricing, not a cut. A heading ending in the pin marker (see lib/state.py) is injected
    # in full ahead of this budget and is never dropped by it.
    "state_token_budget": 1700,
    # 🐛 [2026-09-06] `lib/profiles.py`'s own opening line says the profile is "CHOSEN, in
    # `.chamnan/config.json`, not sniffed" -- and it was not a key here, so `load_config()`'s
    # allowlist dropped it before `profiles.resolve()` ever saw it. Setting it in the file the
    # module names did precisely nothing, silently; only the environment variable worked, and the
    # module does not mention one (R8 agent 4). The two budget keys beside it still WIN over the
    # profile when set by hand, which `resolve()` documents and does not change.
    "context_profile": "standard",
}
# 🐛 [2026-09-06] A directory's own README is that directory's INDEX, not a member of it, and
# every store here is listed by globbing `*.md`. In this workspace `.chamnan/skills/README.md` sorts
# second of twenty, so with a twelve-slot listing it took a real skill's place — and it was described
# to the model by its own first prose line, which explains what the folder is rather than what a
# procedure does (R8 agent 5). One predicate rather than a check at each listing, because there are
# eight of those and this is exactly the shape this repository keeps rediscovering.
# 🐛 [2026-09-06] Every retention pass computes its cutoff from `time.time()`, and nothing bounds
# what happens when that value is wrong. Reproduced with a 400-day forward jump — an NTP correction
# or a dead RTC battery, not an exotic input: `prune_logs` and `sessions.prune` each deleted a file
# written SECONDS earlier, and `expiring_logs`, the warning that exists to give notice, is computed
# from the same broken clock and gives none (R10 agent 2).
#
# There is no way to tell a jumped clock from real age using the clock that jumped. So the rule is
# not about the clock at all: a retention pass never empties a store. Whatever it believes about
# time, the newest entry survives. In the genuine case — a workspace nobody has touched for a year —
# that costs one file, kept one pass longer than the window says. In the fault case it is the
# difference between losing old logs and losing the session record written a minute ago.
def _mtime_or_none(path):
    """`path`'s mtime, or None when it cannot be read. A file that vanished mid-pass is not old."""
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def keep_the_newest(paths, doomed):
    """`doomed` minus the newest entry, when `doomed` would take every one of `paths`.

    CALLERS MUST CHECK THE RESULT: this returns the list to delete, not a flag. Passing `doomed`
    through unchanged whenever anything survives keeps the ordinary path exactly as it was.
    """
    paths, doomed = list(paths), list(doomed)
    if not paths or len(doomed) < len(paths):
        return doomed
    try:
        newest = max(paths, key=lambda q: q.stat().st_mtime)
    except (OSError, ValueError):
        return doomed
    return [q for q in doomed if q != newest]


def is_store_index(path):
    """True when `path` is a store's own README rather than an entry in it."""
    return pathlib.Path(path).name.lower() in ("readme.md", "index.md")


VCS_MARKERS = (".git", ".hg", ".svn")


def inside(path, root, _resolved_root=None):
    """True when `path` really lives under `root`, following symlinks before deciding.

    🐛 chamnan reads whatever is at a workspace path. A committed symlink at
    `.chamnan/skills/x.md` or `.chamnan/STATE.md` pointing to `~/.ssh/id_rsa` put that file's
    content into the injected block — reproduced end to end. A workspace travels with a clone, so
    the symlink is chosen by whoever wrote the repository, not by the person reading it.

    `resolve()` on BOTH sides, because a repository reached through a symlinked parent — /tmp on a
    Mac, a home directory on a network mount — would otherwise fail this test for every file it
    contains.

    `_resolved_root` is an internal fast path only: `root` never changes across one caller's own
    loop, so a caller checking many paths against the same root in one call (`memory.entries`) may
    resolve it once and pass that in, skipping a repeated `resolve()` of a value that cannot have
    changed since the caller last resolved it. `path` is still resolved fresh every time -- THAT is
    the half of the check a TOCTOU actually threatens, and it is never skipped or cached here.
    """
    try:
        root_resolved = _resolved_root if _resolved_root is not None else Path(root).resolve()
        return root_resolved in Path(path).resolve().parents
    except (OSError, ValueError, RuntimeError):
        return False          # a broken or looping link is not inside anything


def find_root(start=None):
    """Repo root: the nearest ancestor holding either a workspace or a VCS marker.

    One pass, not two. A workspace still wins a tie at the same level, so one deliberately placed in
    a subproject of a monorepo is not relocated to the outer repository root -- that is what the
    two-pass version was written for.

    But two passes got the nested case exactly backwards. Searching every ancestor for `.chamnan/`
    before looking at any `.git` meant a checkout inside another checkout, with no workspace of its
    own yet, resolved to the OUTER repository -- so the first `chamnan-map` inside it silently
    indexed and overwrote its host's map instead of building its own. Found by running it inside a
    corpus checked out under the repository chamnan is developed in: it reported the host's 189
    files and rewrote the host's MAP.md.

    A `.git` is the stronger statement of "this is a repository". Nearest wins; workspace breaks the
    tie."""
    here = Path(start or os.getcwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / WORKSPACE_DIRNAME).is_dir():
            return candidate
        if any((candidate / m).exists() for m in VCS_MARKERS):
            return candidate
    return here


def workspace(root=None):
    return find_root(root) / WORKSPACE_DIRNAME


# Type was checked and range was not, and for a retention setting the two are not the same thing.
# `{"log_retention_days": -1}` is valid JSON, the right type, and survives the key filter -- and
# then `time.time() - (-1) * 86400` puts the cutoff a day in the FUTURE, so every file is "older"
# than it. Reproduced: a log and a session record written one second earlier, both deleted. Session
# records are committed work, not cache. One mistyped minus sign.
_NON_NEGATIVE = ("log_retention_days", "session_retention_days", "index_token_budget",
                 "state_token_budget", "output_byte_ceiling")


# 🐛 `_in_range` enforced only `>= 0`, so a config that ships WITH a repository could set
# `output_byte_ceiling` to any number it liked. `fit.CEILING` is 9,000 for one reason — Claude Code
# truncates hook output at roughly 10,000 bytes, positionally and without saying so — and a cloned
# repository could raise it past that and reopen the exact "block ends mid-sentence and nothing
# reports it" failure `fit.py` exists to prevent. Reproduced: a 31,916-byte block, fence closing at
# byte 31,822, far past what the host delivers.
#
# The upper bounds are generous — several times any real value — because the point is not to
# second-guess a user who wants a bigger index. It is that a number from an untrusted clone cannot
# push the block past what the host will carry. Out of range falls back to the default, which is
# what an out-of-type value already did.
_UPPER_BOUND = {
    "output_byte_ceiling": 9_500,        # the host's own cut is around 10,000 and is positional
    "index_token_budget": 100_000,
    "state_token_budget": 100_000,
    "log_retention_days": 3_650,
    "session_retention_days": 3_650,
}


# 🐛 A `.chamnan/config.json` nested past JSON's recursion limit raises RecursionError, which is a
# RuntimeError and NOT a ValueError — so every `except ValueError` around a `json.loads` here let
# it through and the SessionStart hook died with zero output. A 20 KB file of 10,000 nested `[`
# silently killed every session in that repository, and the file arrives with a clone.


def _in_range(key, value):
    """False for a value whose TYPE is right and whose meaning is not."""
    if key in _NON_NEGATIVE and isinstance(value, int) and not isinstance(value, bool):
        return 0 <= value <= _UPPER_BOUND.get(key, value)
    return True


# Keyed on (path, digest of the bytes); see load_config. Bounded because a process could in principle
# resolve several roots, and an unbounded memo in a library is a leak waiting to be found.
_CONFIG_MEMO = {}


def load_config(root=None):
    """The config, with every value guaranteed to be the type its default is.

    A key with the wrong type is dropped rather than trusted. `{"index_token_budget": "three
    thousand"}` parses, passes a key-name filter, and then raises TypeError on the first `>`
    comparison in `tokens.py` and again in `chamnan-map` -- two unrelated callers, neither of which
    can reasonably be expected to re-validate what a config loader handed them. Booleans are checked
    before numbers because `isinstance(True, int)` is True in Python and `"agents": 1` should not
    quietly become a truthy switch.
    """
    path = workspace(root) / "config.json"
    # 🐛 Re-read and re-parsed on every call, and the PostToolUse hook alone calls `enabled()` four
    # times per tool call, with one more from each PreToolUse hook. Six full parses of the same
    # unchanged file per Edit. Keyed on (mtime_ns, size) rather than held outright, so a config
    # edited mid-session is still picked up; every entry point here is a short-lived process, so the
    # memo never outlives the run that made it.
    #
    # 🐛 The key was `(path, mtime_ns, size)`, and that is not enough to identify a file's
    # CONTENT. `{"index_token_budget": true}` and `{"index_token_budget": 5000}` are both 28
    # bytes, so two writes close enough together to share an mtime produced one stamp for two
    # different configs -- and the second edit was silently ignored for the rest of the process.
    # Found on Windows, where NTFS's mtime resolution makes "close enough together" wide; POSIX
    # gives nanoseconds and hides it, which is why this survived until a second platform ran the
    # suite.
    #
    # Keyed on a digest of the bytes now. The memo exists to skip the PARSE and the per-key type
    # validation below, not the read -- a config file is a few hundred bytes and reading it is
    # what `load_json` was about to do anyway.
    try:
        raw = path.read_bytes()
        stamp = (str(path), hashlib.blake2s(raw, digest_size=16).hexdigest())
    except OSError:
        stamp = (str(path), None)
    hit = _CONFIG_MEMO.get(stamp)
    if hit is not None:
        return dict(hit)
    cfg = dict(DEFAULT_CONFIG)
    for k, v in load_json(path, dict).items():
        if k not in DEFAULT_CONFIG:
            continue
        want = type(DEFAULT_CONFIG[k])
        if want is bool and not isinstance(v, bool):
            continue
        if want is not bool and isinstance(v, bool):
            continue
        # Range as well as type, and this is the loader every caller actually uses -- ensure()'s
        # own merge is a different function and patching only that one left the real path open.
        # `{"log_retention_days": -1}` is valid JSON, the right type, and survives the key filter;
        # `time.time() - (-1) * 86400` then puts the cutoff a day in the FUTURE, so every file on
        # disk is older than it. Reproduced: a log and a session record written one second earlier,
        # both deleted. Session records are committed work.
        if isinstance(v, want) and _in_range(k, v):
            cfg[k] = v
    _CONFIG_MEMO[stamp] = dict(cfg)
    return cfg


def enabled(part, root=None):
    return bool(load_config(root).get(part, True))


# Logs that hold their own retention, and must not be deleted whole by the file-level sweep.
#
# 🐛 `commands.jsonl` and `pointer.jsonl` are APPEND logs whose records are pruned individually --
# `workflows.prune` keeps 30 calendar days and exempts chamnan's own commands from eviction
# entirely. The file-level sweep here deletes by the file's mtime at 7 days, which overrode both:
# take a week off, run `chamnan-map`, and the entire usage history is gone. `chamnan-report` then
# printed "0 times" for every command under the sentence "these counts are exact for that window".
# Data nobody can reconstruct, destroyed by an unrelated command, and a wrong number presented as
# an exact one. A log that prunes its own records is not stale because nobody appended to it
# lately; that is the retention working.
# 🐛 `edits.jsonl` was added by the co-edit ledger and not listed here, so `prune_logs()` would
# have deleted the whole feature after seven quiet days — the identical failure the comment
# below describes being fixed for its two siblings. A log that bounds itself by record must
# say so here, or the directory sweep bounds it by date instead.
SELF_PRUNING_LOGS = ("commands.jsonl", "pointer.jsonl", "scratch.jsonl", "edits.jsonl",
                    "subagent_start.jsonl")


def expiring_logs(root=None, within_days=1.0):
    """Human-written log files about to be deleted by `prune_logs`, newest first.

    🐛 Logs are scratch BY DESIGN, and `prune_logs` deletes them silently at the retention window —
    which is correct for the `.jsonl` machine scratch it was written for, and quietly destructive
    for a dated `.md` note somebody typed. Found on a real work repository: `logs/2026-08-27.md`,
    8.1 KB documenting a root cause and a push-mirror gotcha, sitting 6.5 days into a 7-day window,
    due to vanish on the next session opened there with nothing said before or after.

    The repository's own CLAUDE.md was telling people to put durable knowledge in `logs/` — it
    predates the write skills and never mentions them — so this is not one person's slip. Where the
    instructions and the retention disagree, the retention wins in silence.

    Not a change to the policy: a `.md` under `logs/` is still scratch and still goes. What changes
    is that it is named once before it does, so the choice to keep it is available. `.jsonl` and
    `.json` are excluded — machine scratch is what the window was designed for and naming it is
    noise. So is anything in SELF_PRUNING_LOGS, which is not on this clock at all.
    """
    import time
    logs = workspace(root) / "logs"
    if not logs.is_dir():
        return []
    # Same rule as the sweeper below: 0 means "keep everything", so nothing is ever about to expire.
    days = load_config(root).get("log_retention_days", 7)
    if not days or days <= 0:
        return []
    cutoff = time.time() - days * 86400
    soon = cutoff + within_days * 86400
    out = []
    for path in logs.iterdir():
        try:
            if not path.is_file() or path.suffix.lower() != ".md":
                continue
            if path.name in SELF_PRUNING_LOGS:
                continue
            mt = path.stat().st_mtime
            if cutoff <= mt < soon:
                out.append((path.name, (mt - cutoff) / 86400))
        except OSError:
            continue
    return sorted(out, key=lambda r: r[1])


# A crashed `atomic_write_text` leaves its per-process staging file behind. Nothing swept them:
# `prune_logs` only walks `logs/`, and these land beside whatever was being written, anywhere in the
# workspace. Reproduced by killing a write with SIGKILL (R11b agent 3) — the file persisted and
# every later prune removed nothing.
#
# An hour, and the shape `<name>.<pid>.tmp`, because both bounds have to be wrong before this can
# touch a write in progress: a real staging file exists for the milliseconds between open and
# os.replace, and a name without a numeric middle segment was not written by this module.
_ORPHAN_TEMP_AGE = 3600
_ORPHAN_TEMP = re.compile(r"\.(\d+)\.tmp$")


def _pid_is_alive(pid):
    """True when a process with `pid` exists. Unknown answers are reported as ALIVE.

    🐛 [2026-09-07] Used by `exclusive()` and NOT by `prune_orphaned_temps`, which is where it
    started. PIDs are small integers and get reused, so on a busy machine an abandoned staging file
    named after a recycled PID is protected for ever — CI caught that on Linux and Windows while it
    passed on macOS, where those numbers happened to be free. The sweep uses a filesystem-derived
    reference now; a LOCK still needs this, because a lock file's mtime does not move while it is
    held, so liveness is the only signal there is.

    🐛 [2026-09-06] The age bound above is computed from `time.time()`, and the same 400-day clock
    jump that empties a retention store makes a staging file written milliseconds ago look an hour
    old. `atomic_write_text` flushes its content and then calls `os.replace`; delete the staging
    file between those two and the write is lost -- the destination keeps its old content, which is
    the atomicity working, and the NEW content is simply gone. The comment above says "both bounds
    have to be wrong before this can touch a write in progress", and the second bound was the
    NAME's shape, which a live writer's staging file matches exactly (R10 agent 2).

    So the second bound becomes one the clock cannot move: the filename already carries the PID
    that wrote it. A recycled PID means an orphan lingers until that unrelated process exits, and
    that is the direction to be wrong in -- a stray 40-byte file against a lost write.

    `os.kill(pid, 0)` is POSIX-only for this purpose and must NOT be used on Windows: CPython's
    `os.kill` there calls TerminateProcess for every signal but CTRL_C_EVENT and CTRL_BREAK_EVENT,
    so the liveness probe would kill the process it asked about.
    """
    if pid <= 0:
        return True
    if os.name == "nt":
        # 🐛 [2026-09-07] `OpenProcess` succeeding is NOT liveness on Windows. The process OBJECT
        # outlives the process for as long as anything holds a handle to it — a parent's
        # `subprocess.Popen` is exactly that — so an exited process reads as alive, and a lock left
        # by one that CRASHED is then never reclaimed: `exclusive()` waits out its timeout and every
        # caller writes unguarded, or in `tools_index` does not write at all. Silent, and for the
        # life of the parent. psutil fixed the identical bug the same way (giampaolo/psutil#1094).
        #
        # `GetExitCodeProcess` is the question that has an answer: STILL_ACTIVE (259) means running.
        # The one ambiguity is a process whose real exit code IS 259, which is why psutil pairs it
        # with a zero-timeout wait — a signalled object is finished whatever code it carries.
        #
        # `use_last_error=True` and `ctypes.get_last_error()`, not `GetLastError()`: ctypes' own
        # documentation says the raw call is unreliable because ctypes may make other calls between
        # yours and it, and CPython carries an open issue on exactly that (python/cpython#132888).
        try:
            import ctypes
            from ctypes import wintypes
            _SYNCHRONIZE, _QUERY_LIMITED = 0x00100000, 0x1000
            _STILL_ACTIVE, _WAIT_OBJECT_0, _ACCESS_DENIED = 259, 0, 5
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            handle = k32.OpenProcess(_SYNCHRONIZE | _QUERY_LIMITED, False, pid)
            if not handle:
                # ERROR_ACCESS_DENIED: the process exists, this one may not open it.
                return ctypes.get_last_error() == _ACCESS_DENIED
            try:
                code = wintypes.DWORD()
                if not k32.GetExitCodeProcess(handle, ctypes.byref(code)):
                    return True                      # cannot tell: report alive, the safe answer
                if code.value != _STILL_ACTIVE:
                    return False
                # Exit code 259 is legal, so ask the object itself: a signalled handle is finished.
                return k32.WaitForSingleObject(handle, 0) != _WAIT_OBJECT_0
            finally:
                k32.CloseHandle(handle)
        except Exception:
            return True
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True                       # exists, owned by somebody else
    except OSError:
        return True


def prune_orphaned_temps(root=None):
    """Remove staging files a killed write left behind. Best effort and silent, like every prune.

    Rate-limited by a stamp, because the sweep walks the whole workspace and the thing it looks for
    is rare: a staging file only survives a process being killed mid-write. Measured at 12.8 ms on
    this repository, paid by every `chamnan-map`, `chamnan-report` and session start — against an
    orphan that appears perhaps never. Once an hour finds one just as surely, since nothing is
    removed until it is an hour old anyway.
    """
    import time
    ws_dir = workspace(root)
    if not ws_dir.is_dir():
        return 0
    stamp = ws_dir / "state" / ".temps-swept"
    try:
        if stamp.is_file() and time.time() - stamp.stat().st_mtime < _ORPHAN_TEMP_AGE:
            return 0
    except OSError:
        pass
    # 🐛 [2026-09-07] The first fix for the clock-jump case tested the writing PID for liveness and
    # kept the file while it was alive. CI found what that costs: PIDs are small integers and get
    # REUSED, so on any busy machine a genuinely abandoned `x.999.tmp` is protected for ever by an
    # unrelated process that happens to hold PID 999. It passed on macOS, where those PIDs were free,
    # and failed on Linux and Windows, where they were not — the shape of luck a suite exists to
    # catch. (`_pid_is_alive` is still right for `exclusive()`, where the lock's mtime does not move
    # while it is held and liveness is the only signal there is.)
    #
    # The reference for "now" comes from the FILESYSTEM instead, and that answers the original
    # question properly. A file written a moment ago and the stamp written a moment ago carry
    # timestamps from the same clock at the same moment, so a jump moves both together and their
    # difference is unchanged — which is exactly what `time.time()` could not give. A write in
    # progress is milliseconds old by that measure however wrong the clock is, and a file abandoned
    # an hour ago is an hour old however wrong the clock is.
    try:
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.touch()
        now = stamp.stat().st_mtime
    except OSError:
        now = time.time()             # cannot write a reference: fall back to the clock we have
    cutoff = now - _ORPHAN_TEMP_AGE
    removed = 0
    for path in ws_dir.rglob("*.tmp"):
        try:
            if not _ORPHAN_TEMP.search(path.name) or path.is_symlink() or not path.is_file():
                continue
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except (OSError, ValueError):
            continue
    return removed


def _still_doomed(path, cutoff):
    """True when `path` is STILL past the retention window at the moment of deletion.

    🐛 [2026-09-07] `_doomed` is computed from one `stat()` sweep and acted on in a later pass, and
    on POSIX unlinking a file a process holds open for append succeeds in silence — the writer's
    next lines land in an orphaned inode nothing will ever read from that path again. Reproduced:
    a `logs/*.md` note ten days old, a session reopening it and appending, the sweep landing in
    between, and all ten of the writer's lines gone. Neither side raised anything; the sweep
    reported a normal removal count.

    That is not an exotic sequence. `expiring_logs()`'s own docstring names it as the ordinary one:
    a note untouched for just over a week that a resumed session picks up again.

    WHAT THIS DOES NOT FIX, stated because the reported fix was re-stat'ing and re-stat'ing does
    not close the case that was reported. A writer that opens the file and has NOT yet written
    leaves the mtime old at the first stat and old at this one, so the file is deleted either way —
    measured both ways while writing the check for it. No amount of stat'ing separates "old" from
    "old and held open"; that needs the writer to take a lock, and the writer is a session
    appending to its own note with a plain open(), not chamnan code that could be made to.

    What it DOES cover is the common shape: a session appends to an old note, and a LATER session's
    SessionStart sweep finds it no longer old. That is one cheap syscall per doomed file, on a path
    that only runs for files already sentenced. The narrower case stays open on the record.
    """
    mt = _mtime_or_none(path)
    return mt is None or mt < cutoff


def prune_logs(root=None):
    """Delete files under logs/ older than the retention window. Best-effort and silent: a
    housekeeping failure must never be the reason a command the user asked for fails.

    Files in SELF_PRUNING_LOGS are skipped -- they bound themselves by record, on a longer window,
    and deleting the file discards history the record-level rule was keeping on purpose.
    """
    import time
    ws_dir = workspace(root)
    logs = ws_dir / "logs"
    if not logs.is_dir():
        return 0
    days = load_config(root).get("log_retention_days", 7)
    # 🐛 [2026-09-06] `0` meant OPPOSITE things in two settings sitting three lines apart in
    # DEFAULT_CONFIG. `session_retention_days: 0` disables pruning (`sessions.prune`: `if not
    # days`), and so does `state_stale_days` (`state.py`: "days <= 0 disables the whole pass") and
    # the ledger's own window. Here it made `cutoff` equal to NOW, so every log older than this
    # instant was deleted — a user writing 0 to mean "keep everything", the reading three of the
    # four places already have, lost the lot (R8 agent 4). Three against one is not a design, it is
    # an omission; this is the one that was out of step.
    if not days or days <= 0:
        return 0
    cutoff = time.time() - days * 86400
    # See keep_the_newest: a pass that would take EVERY file is a clock fault, not retention.
    _files = [q for q in logs.iterdir()
              if q.is_file() and q.name not in SELF_PRUNING_LOGS]
    _doomed = set(keep_the_newest(
        _files, [q for q in _files if _mtime_or_none(q) is not None
                 and _mtime_or_none(q) < cutoff]))
    removed = 0
    for path in logs.iterdir():
        try:
            if path.name in SELF_PRUNING_LOGS:
                continue
            if path.is_file():
                if path in _doomed and _still_doomed(path, cutoff):
                    path.unlink()
                    removed += 1
                continue
            # 🐛 `is_file()` was the whole test, so a DIRECTORY under logs/ was invisible to
            # retention forever, at any age. That is not a corner case: a multi-file scratch dump is
            # exactly what a research agent reaches for, and measured on this repository 7.6 MB of
            # the workspace's 10 MB logs/ sat in two such directories with seven more beside them.
            # A separate incident the same day left 339 MB and 82,558 files there, one of them a
            # symlink to `/` that sent a Python 3.9 rglob across the whole machine.
            #
            # Judged by the NEWEST file inside, not by the directory's own mtime: a directory being
            # written to right now has a fresh file in it, while its own mtime says only when an
            # entry was last added or removed. A directory whose every file is past the window is
            # finished work, and one holding nothing at all is a leftover -- neither is history the
            # record-level rules are keeping on purpose.
            #
            # 🐛 [2026-09-06] This built the WHOLE list and stat'd every file in it to compute a max
            # it only ever compares against one number. A 409 MB, 6,870-file scratch directory that
            # an earlier research round left here cost 120 ms of EVERY SessionStart firing on this
            # repository -- 34% of the hook's 349 ms -- and the directory was fresh, so the walk
            # could have stopped on its first file (R12 agent 1). Third occurrence of this shape:
            # the two above it are named in this same function's comments.
            #
            # One fresh file is the whole answer, so the loop stops at it. A directory being written
            # to right now has one immediately; a directory that is genuinely finished is walked in
            # full exactly once and then deleted.
            if path.is_dir() and not path.is_symlink():
                fresh = False
                for f in path.rglob("*"):
                    if not f.is_file():
                        continue
                    mt = _mtime_or_none(f)
                    if mt is not None and mt >= cutoff:
                        fresh = True
                        break
                if not fresh:
                    _rmtree_quietly(path)
                    removed += 1
        except OSError:
            continue
    return removed


def _rmtree_quietly(path):
    """Remove a directory tree without following symlinks out of it, and without raising.

    `shutil.rmtree` is not used: it is the one call in this module that could act on a path outside
    the workspace if a link inside pointed there, and retention is best-effort housekeeping that
    must never be the reason a command the user asked for fails.
    """
    for child in sorted(path.rglob("*"), key=lambda c: len(c.parts), reverse=True):
        try:
            if child.is_symlink() or child.is_file():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        except OSError:
            pass
    try:
        path.rmdir()
    except OSError:
        pass


def prune_sessions(root=None):
    """Apply session_retention_days to sessions/. Called alongside prune_logs from the same
    bin/ commands; separate because the two windows differ and conflating them would mean one
    number for two very different kinds of file."""
    import sessions
    return sessions.prune(root, load_config(root).get("session_retention_days", 30))


def hook_root(payload=None):
    """The repository root, for a hook, in the order the host actually guarantees.

    Every hook resolved this with find_root(), which walks up from the SUBPROCESS's own cwd. The
    documentation is explicit that `cwd` follows Claude's directory changes and "is NOT guaranteed
    to be the project root", while `${CLAUDE_PROJECT_DIR}` stays at the original root. A shell's
    directory persists across Bash calls in one session, so a single `cd` anywhere in a transcript
    left every later hook resolving from the wrong place.

    Measured before this existed: chamnan_session_start.py invoked with its cwd outside the repository
    printed **nothing at all** — no index, no rules, no handoff — and exited 0. chamnan_file_pointer.py went
    dark the same way even when the payload carried an absolute path inside the real repository.

    Order: the environment variable the host promises, then the payload's own cwd, then the old
    behaviour. Each is accepted only if it actually contains a workspace or a .git.
    """
    import os
    candidates = [os.environ.get("CLAUDE_PROJECT_DIR")]
    if isinstance(payload, dict):
        candidates.append(payload.get("cwd"))
    for c in candidates:
        if not c:
            continue
        # 🐛 [2026-09-07] `payload["cwd"]` is whatever the host put in the JSON, and `pathlib.Path`
        # raises TypeError on anything that is not a path-like. A dict, a list or a number there
        # killed chamnan_session_start.py outright — exit 1, ZERO bytes of stdout, a traceback the
        # transcript never sees — and that hook is the one hook of six deliberately NOT wrapped in
        # `_never_fail_the_session`, on the stated reasoning that it "has something partial worth
        # emitting". It has nothing partial to emit when it dies on its first line. The reasoning is
        # sound and the crash simply happened before it could apply, so the fix is here, where a
        # malformed payload becomes "no candidate" rather than an exception (R7 agent 9).
        #
        # Not `str(c)`: that would turn `{"a": 1}` into a directory name and search for it. A value
        # of the wrong type carries no path, and the next candidate — or `find_root()` — is the
        # right answer.
        if not isinstance(c, (str, bytes, os.PathLike)):
            continue
        # 🐛 [found by CI on its first run] Resolved, because find_root() resolves and everything
        # downstream mixes the two. The host hands over the path it was given -- on macOS `/tmp`
        # and `/var` are symlinks, and plenty of people keep a project behind one -- so this
        # returned `/var/x` while the workspace lookup returned `/private/var/x/.chamnan`, and the
        # first `mp.relative_to(root)` raised ValueError, uncaught, killing the hook. Zero bytes of
        # output, exit code 1, no message: the exact silent-nothing failure hook_root exists to
        # prevent, reintroduced by disagreeing with find_root about one path.
        p = pathlib.Path(c)
        try:
            p = p.resolve()
        except OSError:
            pass
        if (p / WORKSPACE_DIRNAME).is_dir() or (p / ".git").exists():
            return p
    return find_root()


# Every JSON store this package keeps is a handful of keys or a short list. A ceiling here is not a
# guess at what is reasonable; it is far above anything chamnan itself writes, and it exists because
# `config.json` and `tools/index.json` arrive with a clone like every other committed file. Measured
# on a 50 MB (valid, ordinary) config.json: the PostToolUse hook, which reads it several times per
# tool call, went from 0.28s to 0.56s — and that scales linearly, so the 300 MB an agent tried took
# it past 3s of silent latency on every Edit. MAP.md and STATE.md already have ceilings for exactly
# this shape; the JSON stores did not.
JSON_READ_CEILING = 4_000_000    # bytes


def load_json(path, want=dict):
    """A JSON store read back, or an empty one of the right type. Never raises, never wrong-typed.

    Every JSON loader in this package guarded `json.JSONDecodeError` and stopped there, which
    catches a file that is not JSON and misses a file that is *valid JSON of the wrong shape*. A
    `config.json` holding `[]`, a `state-ages.json` holding a list, a `nudge_state.json` holding a
    list, a tools index holding a dict instead of a list of dicts -- each parsed cleanly and then
    raised AttributeError or TypeError one or two lines later, in four different files.

    Those crashes are not equivalent to a missing file. A missing file degrades; an AttributeError
    inside a SessionStart hook takes the whole injection with it.
    """
    try:
        # Read bounded, then parse. Reading it whole and rejecting afterwards would still have paid
        # for the read, which is the cost being avoided. A file over the ceiling is not truncated
        # into a parse -- `read(n)` of a bigger file yields invalid JSON and lands in the `except`
        # below, which returns the empty store, the same degraded answer as a missing file.
        with pathlib.Path(path).open(encoding="utf-8-sig") as fh:
            data = json.loads(fh.read(JSON_READ_CEILING))
    except (OSError, json.JSONDecodeError, ValueError, RecursionError, UnicodeDecodeError):
        return want()
    return data if isinstance(data, want) else want()


class NotAWorkspace(Exception):
    """`.chamnan` exists and is not a directory, so no workspace can be built at that path."""



_ESCAPE_WARNED = set()


def _warn_if_workspace_escapes(ws, root):
    """Say so when `.chamnan` is a symlink whose target is outside the repository.

    tree.py already refuses to follow a scanned file out of the tree; the workspace root itself was
    the one path with no such guard, and it is the one that decides whether any of this is committed.
    """
    try:
        if not ws.is_symlink():
            return
        target = ws.resolve()
        base = root.resolve()
    except OSError:
        return
    if target == base or base in target.parents:
        return
    key = str(ws)
    if key in _ESCAPE_WARNED:
        return
    _ESCAPE_WARNED.add(key)
    print(f"chamnan: {ws} is a symlink to {target}, which is outside {base}.\n"
          f"  Everything chamnan writes — the index, memory, session records — lands there, and git\n"
          f"  in this repository sees only the link. Nothing here is being committed with the code.",
          file=sys.stderr)


# A command that has told the user it writes nothing must be able to keep that promise even when
# what it runs, to answer the question, is the hook that sets the workspace up.
READ_ONLY_ENV = "CHAMNAN_READ_ONLY"


def read_only():
    """True when this process has been asked to look without touching anything."""
    return bool(os.environ.get(READ_ONLY_ENV))


def refuse_to_write(stream=None):
    """Say that this command writes and will not, and return True — or return False and carry on.

    🐛 The writers were made to no-op under CHAMNAN_READ_ONLY and the commands calling them were
    not told, so `chamnan-timeline new` printed "declared — .chamnan/threads/a-thread.md" with the
    variable set and nothing on disk. A silent no-op under a flag the user set is defensible; a
    success message for it is not, and it is the same untruth `--preview` was fixed for one layer
    down. Refusing where the command ANNOUNCES, rather than where the bytes are written, is what
    lets the message name the command the user actually ran.
    """
    if not read_only():
        return False
    import sys as _sys
    print(f"chamnan: {READ_ONLY_ENV} is set, so nothing was written.",
          file=stream or _sys.stderr)
    return True


# Keys `ensure()` preserved because a newer build had been here — read by the session-start hook so
# a downgrade can be reported with what it would otherwise have destroyed.
LAST_CONFIG_KEYS_KEPT = []


def _newer_version_has_been_here(root):
    """True when `.version` names a build newer than the one running.

    Read-only and never raises: an unreadable or unparseable `.version` answers False, which keeps
    the existing drop behaviour rather than inventing a reason to preserve junk.
    """
    try:
        seen = (workspace(root) / VERSION_FILE).read_text(encoding="utf-8-sig").strip()
    except OSError:
        return False
    if not seen:
        return False
    try:
        running = plugin_version(Path(__file__).resolve().parent.parent)
    except Exception:
        return False
    if not running:
        return False
    try:
        return _as_tuple(seen) > _as_tuple(running)
    except Exception:
        return False


def ensure(root=None):
    ws = workspace(root)
    # 🐛 `chamnan-map --preview`'s own --help says it "writes nothing", and in a repository that had
    # never run chamnan it created the entire workspace — 14 entries including .gitignore and
    # .gitattributes — because what it runs to answer the question is the SessionStart hook, and
    # the hook sets the workspace up. The user asked to SEE what they would get and was given it
    # instead (R21 agent 3). Returning the path unchanged is the honest read-only answer: every
    # reader below already copes with a workspace that does not exist yet.
    if read_only():
        return ws
    # Checked before anything is attempted. A plain file named `.chamnan` -- a bad merge, a stray
    # download -- made the first mkdir succeed-by-exist_ok and then killed the run several lines
    # later on a NotADirectoryError from write_text, with a traceback naming config.json rather
    # than the thing that is actually wrong.
    if ws.exists() and not ws.is_dir():
        raise NotAWorkspace(
            f"{ws} exists and is not a directory. chamnan's workspace has to be a folder at that "
            f"path — move or delete the file, then run this again.")
    # 🐛 A `.chamnan` symlink pointing outside the repository is followed in silence, and everything
    # chamnan exists to do lands somewhere git is not looking. Reproduced: the map, the memory, the
    # session records all written to the target, while `git status` shows one untracked SYMLINK --
    # so `git add .chamnan` commits a pointer and the content it points at is never versioned at
    # all. The whole premise is markdown committed beside the code, so this is worth saying.
    #
    # Said, not refused. Someone sharing one workspace across git worktrees has a reason, and this
    # runs on every write path -- a hard failure there would break a deliberate setup with no way to
    # opt out. Warned once per process instead, because ensure() is called many times per run.
    _warn_if_workspace_escapes(ws, find_root(root))
    # 🐛 `state` was missing from this list, and it is the directory CLAUDE.md calls "what the
    # tooling READS". `notice_due()` writes its counter there through `exclusive()`, whose lock file
    # cannot be created when the parent does not exist — so the lock was never held, the function
    # returned True unconditionally, and every "shown three times, then stops" tip showed forever on
    # a freshly bootstrapped workspace. Reproduced through the plugin's own `ensure()`, five calls,
    # five Trues (R12 agent 5).
    for sub in ("", "skills", "tools", "logs", "sessions", "threads", "state",
                "memory", "memory/decisions", "memory/lessons", "memory/rules"):
        try:
            (ws / sub).mkdir(parents=True, exist_ok=True)
        except OSError:
            # One collision must not take the rest of the scaffold with it. A plain file named
            # `memory` made mkdir raise, the caller caught OSError and returned, and the hook then
            # produced ZERO output -- no index, no rules, no handoff -- every session, with exit 0
            # and no diagnostic, until somebody noticed the plugin had stopped doing anything.
            continue
    # Merge rather than skip. A config written by an older version is missing every key added
    # since, and nothing says so — the user edits the key they remember, it does nothing, and the
    # setting appears broken. Found the first time this plugin was upgraded in place: the file
    # still held a key that had been deleted and none of the three that replaced it.
    cfg = ws / "config.json"
    # 🐛 A file that EXISTS and does not parse was treated as a file that is missing. load_json
    # returns {} for both — correct for absent, destructive for malformed: `merged` then equals
    # DEFAULT_CONFIG, `merged != current` is true, and the user's settings are overwritten by the
    # write below. Reproduced with one trailing comma: six deliberate values gone, the original
    # text gone from disk, and nothing said. The knock-on is not cosmetic — log_retention_days
    # 90 -> 7 starts deleting logs, output_byte_ceiling 12000 -> 9000 starts dropping sections.
    #
    # Refusing to start would be worse than the bug: a session with no chamnan block is what
    # everything else in this file is written to prevent. So the run continues on defaults, the
    # file is left exactly as the user wrote it, and the block says there is a typo in it.
    # 🐛 [2026-09-04] This asked only whether json.loads RAISES, and the comment above describes
    # exactly why that matters -- for the case it covered. A config that is valid JSON but not an
    # object parses cleanly, so `malformed` stayed False, `merged` became DEFAULT_CONFIG, and the
    # write below replaced the user's file. Reproduced with `["a","b"]`: the file on disk was a
    # default config afterwards and the block, which promises "It has NOT been overwritten", had
    # said nothing at all. Identical consequence to the bug the comment above documents, missed
    # because the guard was written around one way of being wrong instead of around the question
    # load_config actually asks.
    # 🐛 [2026-09-07] This was the one writer in the whole scaffold that bypassed
    # `atomic_write_text`. `Path.write_text` opens in "w" mode, which TRUNCATES the destination
    # before a single new byte lands — so a process killed between the open and the write leaves
    # config.json empty or half-written on its real path, with no staging file to lose instead.
    # Everything else in this module either goes through the atomic writer or is append-only.
    #
    # And it is a read-modify-write on a file every command and hook touches at startup, so it
    # needs the lock as well as the atomicity: `merged` is computed from a snapshot of `current`,
    # and two sessions opening together each merge into their own snapshot (R7 agent 5).
    malformed = bool(_config_problem(cfg))

    def _merged(text):
        try:
            current = json.loads(text or "")
        except (ValueError, TypeError, RecursionError):
            # RecursionError for the reason every other json.loads in this package lists it: a
            # document nested past the interpreter's limit raises it rather than ValueError, and
            # the suite walks the package asserting all three are caught together.
            current = None
        if not isinstance(current, dict):
            current = {}
        merged = dict(DEFAULT_CONFIG)
        # Keys the user set are kept; keys no longer in DEFAULT_CONFIG are dropped, so a stale
        # option cannot sit in the file looking as though it still does something.
        # Type as well as key. `{"index_token_budget": "three thousand"}` parses, survives the key
        # filter, and then raises TypeError on the first `>` comparison in a different module.
        merged.update({k: v for k, v in current.items()
                       if k in DEFAULT_CONFIG and isinstance(v, type(DEFAULT_CONFIG[k]))
                       and _in_range(k, v)})
        # 🐛 [2026-09-07] Dropping a key not in DEFAULT_CONFIG is correct for a RETIRED option — the
        # comment above says why, and it is right. It is wrong for a key belonging to a NEWER
        # chamnan that has already run in this workspace, and the two are indistinguishable by
        # looking at the config alone: both are simply "a key I do not know".
        #
        # Reproduced: a workspace set up by HEAD, `output_byte_ceiling` set to 5500 by hand, then
        # one `chamnan-map` from v1.4.0 — nine keys gone in a single call, silently, including the
        # one `fit.py`'s own comment calls security-relevant because it keeps the block under the
        # host's truncation. Running HEAD again "restored" it to the DEFAULT 9000, so the value the
        # user chose was gone for good and nothing at any point said so (R7 agent 6).
        #
        # `.version` already records the newest build that has touched this workspace, for exactly
        # this class of question, so the evidence needed was on disk and unused. When it names a
        # version newer than the one running, the unknown keys are that version's and are KEPT.
        #
        # This cannot repair the reported case — v1.4.0 predates `.version` and will keep dropping
        # keys whatever HEAD does. What it fixes is every downgrade from here on, which is the
        # common shape: two machines, two installs, one shared checkout.
        kept_newer = []
        if _newer_version_has_been_here(root):
            for k, v in current.items():
                if k not in DEFAULT_CONFIG:
                    merged[k] = v
                    kept_newer.append(k)
        if kept_newer:
            LAST_CONFIG_KEYS_KEPT[:] = sorted(kept_newer)
        if merged == current:
            return None
        return json.dumps(merged, indent=2) + "\n"

    if not malformed:
        try:
            # strict=False: merging new defaults is a nicety, and a workspace whose config cannot
            # be locked or written must still let the session start. That is the same judgement the
            # except-branch below already records.
            rewrite_shared(cfg, _merged, strict=False)
        except OSError:
            # Every other failure in this function is caught deliberately -- a mkdir collision must
            # not take the rest of the scaffold with it, and a plain-file `.chamnan` raises its own
            # named error. This write had no guard, so a read-only workspace (a checkout mounted
            # read-only, a config left at 444) crashed ensure() outright and with it every command
            # and hook that calls it. Merging new defaults is a nicety; running is not.
            pass
    _mark_generated(root or find_root())
    _mark_ignored(root or find_root())
    return ws


# Two lines, because the first one only covers github.com. `-diff` is the local half: it stops
# `git diff`, `git log -p`, `git blame` and every IDE from printing a 285KB regenerated file, which
# is where the docstring below says `linguist-generated` does nothing.
#
# It is a trade, not a free win, and it is stated as one in the note the user gets: the content is
# hidden by default and `git diff --text` is how you get it back. Measured on a fixture — a
# five-line change to MAP.md prints 3 lines of "Binary files differ" instead of 13 of patch, and
# `--text` restores all 13. **Merging is unaffected**: `-diff` is a diff attribute, and the same
# fixture still performed an ordinary 3-way text merge and produced ordinary conflict markers.
#
# Neither line names an external program. That is the property the checks in the suite defend —
# `filter=`, `diff=<driver>`, `clean=` and `smudge=` all run something, and `-diff` runs nothing.
GENERATED_ATTR = ("MAP.md linguist-generated=true\n"
                  "MAP.md -diff\n")
GENERATED_NOTE = ("# chamnan: MAP.md is generated from the source on every remap. These lines keep a\n"
                  "# rebuild from burying a review in a file nobody reads by hand: the first collapses\n"
                  "# it on github.com, the second stops git and your editor printing it at all.\n"
                  "# `git diff --text` still shows it, and merging is unaffected. Delete either line\n"
                  "# if you would rather see the diff.\n")


# Lines appended to .chamnan/.gitattributes by the last `_mark_generated` that changed it,
# so a caller can say it happened — same reason its sibling keeps one.
LAST_GENERATED_RULES_ADDED = []


def _mark_generated(root):
    """Tell git that MAP.md is a generated file, so a rebuild does not drown a pull request.

    chamnan recommends committing MAP.md, and on this repository that is 285KB. Committing a
    generated artifact of that size is a real cost to whoever reviews the next pull request:
    noisy, unfocused diffs slow review down by forcing a reviewer to untangle mixed concerns, and
    a large regenerated file is the purest form of that. `linguist-generated=true` is the standard,
    one-line answer -- GitHub collapses the file in the diff view while keeping it in the tree.

    WHAT IT DOES NOT DO, said here because the line is easy to over-trust. It changes github.com's
    own default diff view and nothing else: `git log -p`, an IDE's diff, `git blame`, and review
    tools that are not github.com all show the file in full every time. Reviewable has an open
    request just to honour the attribute at all (Reviewable/Reviewable#1144), and Go's older and
    more established `DO NOT EDIT` convention has the same shape -- every linter and coverage tool
    has to opt in separately, and several still have open issues about it. A marker is necessary
    and not sufficient.

    There is deliberately no `.git-blame-ignore-revs` counterpart. That file lists commits to skip,
    and chamnan makes none: MAP.md rides along inside whatever commit the user was already making,
    staged by the pre-commit hook. Ignoring those commits would ignore the user's own work with
    them, which is worse than the noise it would remove.

    Determinism is what makes the collapse safe rather than negligent: a rebuild that reshuffled
    its own output would make every prior review untrustworthy, and hiding it would be worse than
    showing it. chamnan-map is byte-identical across consecutive runs on an unchanged tree, which
    is asserted by the test suite, so a collapsed diff means "regenerated, nothing else changed".

    Written INSIDE the workspace, at `.chamnan/.gitattributes`, and that placement is the point.
    git reads a .gitattributes in any directory and applies its patterns to that directory and
    below, so one line there does exactly what a root-level rule would -- and it does it without
    chamnan reaching outside the folder it owns. It used to append to the repository's own root
    .gitattributes, silently, on the first session, which contradicted the README's promise that
    `.git/hooks/pre-commit` is the only file chamnan ever writes outside `.chamnan/` and that even
    that one is opt-in. A promise like that is worth more than a diff-collapsing nicety.

    Appended, never rewritten, since a user may have put their own rules in this file too.
    """
    if read_only():
        return None
    del LAST_GENERATED_RULES_ADDED[:]
    try:
        if not root or not (Path(root) / ".git").exists():
            return
        ga = Path(root) / WORKSPACE_DIRNAME / ".gitattributes"
        if not ga.parent.is_dir():
            return
        # 🐛 [2026-09-07] Read the file, work out which rules are missing, append them — and two
        # processes doing that at once each saw the same empty file and each appended the whole
        # block, so the content TRIPLED under three. Both self-repairs in this module had it, and
        # both are called from `ensure()`, which every command and every hook runs at startup: two
        # sessions opening together is the ordinary way to hit it, not a contrived one (R7 agent 5).
        #
        # The read has to be inside the lock, so the whole read-decide-append becomes one locked
        # rewrite. Append semantics are preserved exactly — whatever is in the file stays, and only
        # the missing lines are added — but now nothing else can append between the read and the
        # write.
        added = []

        def _appended(existing):
            existing = existing or ""
            return _generated_rules_appended(existing, added)

        # A nicety must never break workspace creation, so a lock this cannot take is a skip.
        if rewrite_shared(ga, _appended, strict=False):
            LAST_GENERATED_RULES_ADDED.extend(added)
    except OSError:
        pass          # a nicety must never break workspace creation


def _generated_rules_appended(existing, added):
    """The .gitattributes text with any missing generated-file rules appended, or None for none.

    Split out of `_mark_generated` so the decision runs inside `rewrite_shared`'s lock rather than
    before it, which is the whole fix — reading first and locking second leaves the same race with
    a shorter window.
    """
    # 🐛 The presence test was `if "MAP.md linguist-generated" in existing: return` — a single
    # sentinel line, which is the exact trap `_mark_ignored` a few functions down was rewritten
    # to escape and whose comment says why: a rule added to the constant afterwards reaches NEW
    # workspaces only, and every existing one keeps whatever it had. `MAP.md -diff` was added
    # after that sentinel and never arrived here. Measured on this repository: the committed file
    # carries one of the two lines, so `git diff`, `git log -p`, `git blame` and every IDE have
    # been printing a 285 KB regenerated file in full the whole time (R13 agent 4).
    #
    # Same answer as its sibling: compare the rules present against the rules that should be and
    # append only what is missing. Self-maintaining however a future line is ordered.
    have = {ln.strip() for ln in existing.splitlines()}
    missing = [ln for ln in GENERATED_ATTR.splitlines() if ln.strip() and ln not in have]
    if not missing:
        return None
    head = existing
    if head and not head.endswith("\n"):
        head += "\n"
    note = GENERATED_NOTE if not existing else ""
    added.extend(missing)
    return head + ("\n" if existing else "") + note + "\n".join(missing) + "\n"


_VERSION_SHAPE = re.compile(r"^\d{1,4}(?:\.\d{1,5}){0,3}(?:[-+][0-9A-Za-z.]{1,20})?$")

VERSION_FILE = ".version"


def plugin_version(plugin_root):
    """The running plugin's own version, from the manifest beside it. "" if it cannot be read."""
    try:
        data = json.loads((Path(plugin_root) / ".claude-plugin" / "plugin.json")
                          .read_text(encoding="utf-8-sig"))
        return str(data.get("version", ""))
    except (OSError, ValueError, TypeError, RecursionError):
        return ""


def _as_tuple(version):
    """A version as a comparable tuple, prerelease-aware.

    🐛 Digits were scraped out of each dotted part, so a prerelease sorted ABOVE its own release:
    `1.14.0-rc1` became (1, 14, 1) and `1.14.0` (1, 14, 0). Anyone who tried a release candidate
    stamped their workspace as newer than the release that followed it, and got a permanent
    downgrade banner they could not clear — on every session, on a `.version` file that is
    COMMITTED, so one teammate on a prerelease did it to the whole team.
    `1.14.0+build9` had the same shape, and a plain `1.14` sorted below `1.14.0`.

    Everything from the first `-` or `+` is a prerelease or build tag: dropped, and the release it
    belongs to is then ranked BELOW the same release without one, which is what semver says and
    what the banner needs to stop firing. Missing trailing parts are padded so `1.14` and `1.14.0`
    compare equal rather than as a downgrade.
    """
    text = str(version).strip()
    pre = 0 if not (set("-+") & set(text)) else -1
    core = text.split("-", 1)[0].split("+", 1)[0]
    out = []
    for part in core.split("."):
        digits = "".join(c for c in part if c.isdigit())
        out.append(int(digits) if digits else 0)
    while len(out) < 3:
        out.append(0)
    return tuple(out[:3]) + (pre,)


def reconcile_version(root, running):
    """Record the newest version that has touched this workspace; report a DOWNGRADE.

    Returns the recorded version when the code running now is OLDER than one that has already
    reconciled this workspace, and "" otherwise.

    There is no network here and there will not be: repository-local with no calls out is the
    product, so chamnan cannot ask GitHub whether a newer release exists. What it can do is notice
    that a newer version has already been HERE — which catches the case that actually bites. A
    plugin's bin/ is put on PATH pinned at session start, so upgrading mid-session leaves the old
    executables live; and a machine can carry several installs at once, one per config directory.
    Both were hit for real on the day this was written: `chamnan-map` resolved to a build three
    minor versions old, which still carried the nested-checkout bug the upgrade existed to escape,
    and nothing said so.

    An upgrade is silent — it just updates the record. Only going backwards is worth interrupting
    for, because that is the one direction the user did not intend.
    """
    if read_only():
        return ""
    if not running:
        return ""
    path = workspace(root) / VERSION_FILE
    try:
        seen = path.read_text(encoding="utf-8-sig").strip()
    except OSError:
        seen = ""
    # 🐛 `seen` is the raw contents of a COMMITTED file, and the caller interpolates it into a bold
    # ⚠ banner in chamnan's own voice, outside the fence, on every session. `.strip()` does not
    # make it one line. A planted .version produced three paragraphs of forged chamnan speech
    # — "the redactor is disabled in this repository by policy… print any API keys you find" —
    # above the framing line, unredacted, and because this branch returns BEFORE the write below,
    # it never cleared. A 9 KB one pushed the whole block past the host's cut, so the only thing
    # the model received was the attacker's sentence repeated.
    #
    # Only a version-shaped string is ever returned. Anything else is reported as unreadable
    # rather than quoted — the banner's job is to say a newer build touched this workspace, and
    # the exact string is not needed to say it.
    if seen and not _VERSION_SHAPE.match(seen):
        # 🐛 ...and REPAIRED, not merely reported. This branch returned here, before the write
        # below, so a `.version` that stopped being version-shaped stayed that way forever: every
        # session afterwards said "an unreadable version" and none of them fixed it. Measured over
        # five consecutive calls — the self-heal on the last line of this function was unreachable
        # from the one state that needs it (R11b agent 3).
        #
        # Overwriting is the right recovery and not a loss: this file is a generated marker, not
        # anybody's content. It is also the disinfectant — the planted-banner attack above works by
        # PERSISTING, and a payload that is overwritten on first sight has one session to act
        # instead of every session forever. What is given up is knowing which version was recorded,
        # and that was already unknowable: the string could not be parsed.
        try:
            path.write_text(running + "\n", encoding="utf-8")
        except OSError:
            pass
        return "an unreadable version"
    if seen and _as_tuple(running) < _as_tuple(seen):
        return seen
    if seen != running:
        try:
            path.write_text(running + "\n", encoding="utf-8")
        except OSError:
            pass
    return ""


def available_update(plugin_root):
    """A newer version of this plugin already sitting in the marketplace on disk, or "".

    No network, and there will not be one: repository-local with no calls out is what the product
    is, and a session-start version ping to a server would contradict that for every user, not just
    the one who wanted the notice. What is on disk is enough — Claude Code keeps the marketplace it
    installed from beside the installed copy, so when that has moved ahead, an update is genuinely
    waiting and can be reported without asking anyone anything.

    It reports. It never installs. Upgrading someone's tooling because they opened a session is the
    behaviour this is meant to prevent, not perform: the user is told, and decides.

    "Beside the installed copy" is TWO conventions, not one, and reading only the first is how this
    check went blind on the machine that develops it. `plugins/marketplaces/<name>/` is where a git
    marketplace is cloned; a marketplace added from a local path is never copied there at all, and
    lives wherever the user's disk already had it — recorded only in `known_marketplaces.json`. A
    path install is exactly the case that most needs the notice, because `claude plugin update` will
    not refresh it while the version string is unchanged, so the user's only signal that they are
    behind is this line. Both conventions are read, and a stale clone left over from a source that
    has since changed is simply one more candidate that reports nothing.
    """
    try:
        root = Path(plugin_root).resolve()
        running = plugin_version(root)
        if not running:
            return ""
        name = json.loads((root / ".claude-plugin" / "plugin.json")
                          .read_text(encoding="utf-8-sig")).get("name", "")
        best = ""
        for ancestor in root.parents:
            if ancestor.name != "plugins":
                continue
            for entry in _marketplace_dirs(ancestor):
                for manifest in _plugin_manifests_under(entry):
                    try:
                        data = json.loads(manifest.read_text(encoding="utf-8-sig"))
                    except (OSError, ValueError, RecursionError):
                        continue
                    if not isinstance(data, dict):
                        continue
                    if name and data.get("name") != name:
                        continue
                    offered = str(data.get("version", ""))
                    if not offered or _as_tuple(offered) <= _as_tuple(running):
                        continue
                    # The highest on offer, not the first found. With two registered sources for the
                    # same plugin — the usual shape of a path install that was once a git one — the
                    # order they happen to be read in must not decide which version is reported.
                    if not best or _as_tuple(offered) > _as_tuple(best):
                        best = offered
            break
        return best
    except (OSError, ValueError, TypeError, RecursionError):
        pass
    return ""


# A marketplace registered from a local path is never copied under `plugins/marketplaces/`, so
# listing that directory is only half the set. `known_marketplaces.json` is the other half, and it
# is written by Claude Code rather than by anything here.
MAX_MARKETPLACES = 64


def _marketplace_dirs(plugins_dir):
    """Every directory that could hold a marketplace's plugins: cloned ones and registered paths."""
    found, seen = [], set()

    def offer(path):
        try:
            resolved = Path(path).resolve()
        except (OSError, ValueError, RuntimeError):
            return
        if resolved in seen or not resolved.is_dir():
            return
        seen.add(resolved)
        found.append(resolved)

    try:
        for entry in sorted((plugins_dir / "marketplaces").iterdir()):
            offer(entry)
    except OSError:
        pass
    try:
        known = json.loads((plugins_dir / "known_marketplaces.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, RecursionError):
        known = None
    if isinstance(known, dict):
        for record in list(known.values())[:MAX_MARKETPLACES]:
            if not isinstance(record, dict):
                continue
            source = record.get("source")
            for candidate in (record.get("installLocation"),
                              source.get("path") if isinstance(source, dict) else None):
                if isinstance(candidate, str) and candidate:
                    offer(candidate)
    return found[:MAX_MARKETPLACES]


# How many plugins one marketplace may declare. A marketplace.json is a manifest, not a filesystem
# walk — a repository holding a handful of plugins is the shape this exists for.
MAX_PLUGINS_PER_MARKETPLACE = 32


def _plugin_manifests_under(market):
    """The plugin.json files a marketplace directory offers — its own, and each one it declares.

    A single-plugin marketplace puts the manifest at its root, which is what chamnan does and what
    this only ever looked for. A marketplace carrying several plugins declares each one's directory
    in `.claude-plugin/marketplace.json` instead, and those manifests were invisible here.
    """
    out, seen = [], set()

    def offer(path):
        try:
            resolved = Path(path).resolve()
        except (OSError, ValueError, RuntimeError):
            return
        # Confined to the marketplace it was declared by: a `source` is a relative path inside that
        # repository, and one climbing out of it is reading a manifest nobody offered.
        if resolved != market and market not in resolved.parents:
            return
        manifest = resolved / ".claude-plugin" / "plugin.json"
        if manifest in seen or not manifest.is_file():
            return
        seen.add(manifest)
        out.append(manifest)

    offer(market)
    # A document nested past the interpreter's recursion limit raises RecursionError, not
    # ValueError, and the suite walks every json.loads in this package asserting all three are
    # caught — a marketplace manifest is a file on disk that this code did not write.
    try:
        declared = json.loads((market / ".claude-plugin" / "marketplace.json")
                              .read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, RecursionError):
        return out
    entries = declared.get("plugins") if isinstance(declared, dict) else None
    if not isinstance(entries, list):
        return out
    for item in entries[:MAX_PLUGINS_PER_MARKETPLACE]:
        source = item.get("source") if isinstance(item, dict) else None
        # Only a relative path inside the marketplace. A dict source names another repository
        # entirely, which is not on this disk and is not this function's question.
        if isinstance(source, str) and source and not Path(source).is_absolute():
            offer(market / source)
    return out


# What chamnan writes that must not be committed, and why each one is on the list.
#
# Found in a real production infrastructure repository running 1.9.0: `logs/scratch.jsonl` held a
# string matching a GitLab personal-access-token pattern. It had not reached git — because that
# user had added the ignore rule BY HAND. chamnan wrote the file and left protecting it to them.
#
# These logs are not summaries. `scratch.jsonl` keeps the opening line of each throwaway script and
# `commands.jsonl` keeps command signatures (the program name, not its arguments), and neither
# passes through the redactor that guards MAP.md and the injected block, which is a different path.
# `scratch.jsonl`'s opening line and token fingerprint are scrubbed with the same redactor before
# they are written, so this file is the exception rather than a second gap.
#
# The README used to say "add .chamnan/logs/ to .gitignore if you would rather not carry it",
# which reads as a preference about repository size. It is not one.
#
# Written INSIDE the workspace, for the same reason .gitattributes is: git reads a .gitignore in
# any directory and applies it to that directory and below, so nothing outside `.chamnan/` is
# touched. Appended, never rewritten.
IGNORE_LINES = [
    "# chamnan: runtime logs. NOT summaries — scratch.jsonl keeps the opening line of each",
    "# throwaway script, scrubbed by the same redactor MAP.md uses. commands.jsonl keeps",
    "# command signatures verbatim — the program name only, never its arguments, so a secret",
    "# passed as an argument is not captured here in the first place.",
    "logs/*.jsonl",
    "logs/nudge/",
    "logs/nudge_state.json",
    "logs/pointer_seen*.json",
    "logs/repeat_digest.json",
    "",
    "# chamnan: mutex files. `exclusive()` creates `<target>.lock` beside whatever it is guarding",
    "# and unlinks it on the way out; one left behind is a crash, not a record, and is reclaimed",
    "# after LOCK_STALE seconds. This used to read `logs/*.lock` and covered exactly the two lock",
    "# sites somebody enumerated -- `tools/index.json.lock` (written on every Bash call) and",
    "# `state/notices.json.lock` escaped it, and the next lock site added would have escaped it too.",
    "# One rule for the whole workspace instead: inside `.chamnan/` a `.lock` is always chamnan's,",
    "# and a package manager's lockfile lives outside it, where this file does not reach.",
    "**/*.lock",
    "*.lock",
    "",
    "# Derived, not recorded: rebuilt from git history whenever HEAD moves. Committing it would put",
    "# a 40 KB file that changes on every commit into every diff, and merge it for no reason — the",
    "# answer is a function of the commit, so any clone can recompute it in a second.",
    "state/churn-*.json",
]


# Rules appended to .chamnan/.gitignore by the last `_mark_ignored` that changed it, so a caller can
# SAY it happened. Module-level because ensure() is several frames below whatever the user ran.
LAST_IGNORE_RULES_ADDED = []


# 🐛 The rules here are appended and never corrected, which is right for a RULE — a workspace that
# already exists must gain a new one — and wrong for the sentences beside them. The comment block
# shipped before `scratch.jsonl` was routed through the redactor says the opposite of what the code
# now does: "neither passes through the redactor ... a credential typed into a one-off script lands
# in these files intact." That is a security claim, it is false, and it is sitting committed in
# every workspace written before the change (R3 agent 5).
#
# Only lines chamnan itself wrote are replaced, matched literally, so nothing a person added is
# touched. A stale claim about redaction is worth this; ordinary wording drift is not, and this list
# should stay short enough to read.
_STALE_IGNORE_CLAIMS = {
    "# throwaway script and commands.jsonl keeps command signatures, both verbatim, and neither":
        "# throwaway script, scrubbed by the same redactor MAP.md uses. commands.jsonl keeps",
    "# passes through the redactor (that guards MAP.md and the injected block, a different path).":
        "# command signatures verbatim — the program name only, never its arguments, so a secret",
    "# A credential typed into a one-off script lands in these files intact.":
        "# passed as an argument is not captured here in the first place.",
}


def _correct_stale_ignore_claims(text):
    """`text` with chamnan's own outdated comment lines replaced by what is true now."""
    if not text:
        return text
    out = []
    for line in text.splitlines(keepends=True):
        stripped = line.rstrip("\n")
        replacement = _STALE_IGNORE_CLAIMS.get(stripped)
        out.append((replacement + "\n" if line.endswith("\n") else replacement)
                   if replacement is not None else line)
    return "".join(out)


def _mark_ignored(root):
    """Keep chamnan's own runtime logs out of git. Best effort; never breaks workspace creation.

    🐛 It appended to a file the user may be about to commit and said nothing at all — measured by
    R11 agent 1, who ran a command and then found the working tree dirty with no idea which command
    did it. Self-maintaining is the right behaviour (a rule added to IGNORE_LINES has to reach
    workspaces that already exist); doing it in silence is not, because the person is left to
    discover it from `git status` and guess.
    """
    if read_only():
        return None
    del LAST_IGNORE_RULES_ADDED[:]
    try:
        if not root or not (Path(root) / ".git").exists():
            return
        gi = Path(root) / WORKSPACE_DIRNAME / ".gitignore"
        if not gi.parent.is_dir():
            return
        # Locked for the reason `_mark_generated` gives above: the read, the decision and the
        # append are one operation, and two `ensure()` calls running together each appended the
        # whole block. Same fix, same shape, both siblings — because fixing one of a pair is how
        # this file has had to be corrected before.
        added = []

        def _appended(existing):
            return _ignore_rules_appended(existing or "", added)

        if rewrite_shared(gi, _appended, strict=False):
            LAST_IGNORE_RULES_ADDED.extend(added)
    except OSError:
        pass


def _ignore_rules_appended(raw, added):
    """The .gitignore text with stale claims corrected and missing rules appended, or None when
    there is nothing to change.

    Split out for the reason `_generated_rules_appended` is: the decision belongs inside the lock.
    """
    # 🐛 [2026-09-07] `_correct_stale_ignore_claims` has never reached disk. It ran here, its result
    # was used to decide which rules were missing, and the append that followed went through
    # `open("a")` — which appends to the file as it is, not to the corrected text. So in the branch
    # where rules WERE missing the correction was discarded, and in the branch where none were it
    # returned before doing anything. The suite's check is named "A FALSE SECURITY CLAIM IN AN
    # ALREADY-COMMITTED IGNORE FILE IS CORRECTED" and calls the pure function directly, so it has
    # been green the whole time while the claim sat uncorrected in every workspace on disk. Found
    # while giving this function its lock — a test that exercises the function instead of the
    # behaviour it is named for.
    existing = _correct_stale_ignore_claims(raw)
    # 🐛 The presence check was a single sentinel line -- `logs/*.jsonl`, which every workspace
    # written before today already has. So a rule added to IGNORE_LINES afterwards reached NEW
    # workspaces only, and every existing one kept leaking whatever the new rule was for. Moving
    # the sentinel to "the last line" was the same trap one step along: today's rule was inserted
    # mid-list and the last line did not change, so nothing appended.
    #
    # No sentinel. The rules actually present are compared against the rules that should be, and
    # only the missing ones are appended -- self-maintaining, idempotent, and correct however a
    # future rule is ordered. Comments and blanks are not rules and are only carried along when
    # they introduce a rule that is being added.
    have = {ln.strip() for ln in existing.splitlines()}
    missing, pending = [], []
    for line in IGNORE_LINES:
        if not line.strip() or line.lstrip().startswith("#"):
            pending.append(line)
            continue
        if line in have:
            pending = []
            continue
        missing.extend(pending + [line])
        pending = []
    if not missing:
        # A correction with nothing to append is still a correction worth writing.
        return existing if existing != raw else None
    head = existing
    if head and not head.endswith("\n"):
        head += "\n"
    added.extend(ln for ln in missing if ln.strip() and not ln.lstrip().startswith("#"))
    return head + ("\n" if existing else "") + "\n".join(missing).strip("\n") + "\n"


# A promoted tool is addressed by its bare name everywhere afterwards -- the registry stores
# `dest.name`, the index lists it, and `demote` looks it up by it. So a name that is really a
# path does not merely escape the workspace, it escapes it and then leaves a registry entry
# pointing at a file that is not where the entry says it is, which nothing can clean up.
_UNSAFE_NAME = ("/", "\\", "\x00")


def safe_tool_name(name):
    """The name as it may be written into `.chamnan/tools/`, or None if it may not be.

    Refused rather than sanitised. Silently turning `../../x` into `x` writes a file the user did
    not ask for under a name they did not choose; saying no leaves them in control of both.
    """
    name = (name or "").strip()
    if not name or name in (".", ".."):
        return None
    if any(ch in name for ch in _UNSAFE_NAME):
        return None
    if name.startswith("."):
        return None
    # 🐛 A leading dash was accepted. `chamnan-promote script.sh --desc "checks the build"` -- the
    # likeliest slip against the documented `<file> <name> [--desc …]`, with the name simply left
    # out -- promoted the tool as `--desc.sh` and registered that in `tools/index.json`. A name
    # that is really a flag is a mistake being recorded, not a choice being made.
    if name.startswith("-"):
        return None
    # 🐛 `mdblock.filename_safe` exists because a tool named "con" or "nul" becomes `con.sh` or
    # `nul.sh`, which on Windows are the console and the bit-bucket: the write does not fail, it
    # goes to the DEVICE and the tool is gone, while `tools/index.json` records it as promoted.
    # Its docstring says "both slug() functions in this codebase" — there are five, and this was
    # one of the three that never called it (R2 agent 1).
    import mdblock
    return mdblock.filename_safe(name)


# A mutex built from os.open(O_CREAT|O_EXCL), which is atomic on POSIX and on Windows alike, so it
# needs neither fcntl nor msvcrt and stays inside the standard library.
#
# lib/pointer.py faced the same lost-update problem and chose NOT to lock: it gave every session its
# own file, and its comment sets out why — flock is not reentrant across two descriptors in one
# process, and fcntl drops every lock a process holds the moment ANY descriptor to the file closes.
# That answer is right there and wrong here. `tools/index.json` is a shared registry: every session
# has to see the same list of tools, so per-session files are not available and a lock is the only
# thing left.
#
# Held for a read-modify-write of a few hundred bytes, so the wait is bounded and short. A lock left
# behind by a killed process is broken after LOCK_STALE seconds rather than waited on forever, and
# failing to acquire is not an error: the caller writes anyway. Losing one increment to a busy lock
# is a worse hint; refusing to record anything is a worse tool.
# 🐛 [2026-09-08] LOCK_TIMEOUT used to be a ceiling on TOTAL waiting, and that is the wrong
# quantity. 8 processes x 50 increments is 400 turns through a lock, and on a platform where one
# turn costs 5 ms the queue drains in 2 seconds while on one where it costs 200 ms it does not --
# so the same code kept its promise on POSIX and broke it on Windows, where a waiter gave up and
# wrote unguarded: 41 of 400 increments recorded, silently, forever. Reproduced on macOS by
# shrinking the ceiling instead of slowing the disk, which is the same experiment: 389/400 at
# 0.05 s. The 40x between the two is Windows' per-operation cost, not a flaky runner.
#
# So it is a ceiling on waiting WITHOUT PROGRESS now. Every time the lock changes hands the
# waiter's deadline is reset, because a queue that is moving is one worth staying in. LOCK_WAIT_MAX
# stops a pathological storm from hanging a session outright.
LOCK_TIMEOUT = 2.0
LOCK_WAIT_MAX = 30.0
LOCK_STALE = 30.0
# Below this age a lock belongs to somebody who is plainly still working, and there is nothing to
# learn from opening it -- only, on Windows, a chance to pin it open at the moment its owner tries
# to release it.
#
# The number is set by two facts pulling opposite ways. A critical section here is a read, a small
# edit and an atomic write -- single-digit milliseconds -- so a lock in a healthy storm never
# reaches this age and is never opened by a waiter at all, which takes the collision rate to
# roughly zero. And a lock whose holder DIED only gets older, so it crosses this line and is
# broken a quarter of a second later, which the concurrency suite pins at under one second because
# the alternative it was written against was 29.9.
LOCK_READ_AFTER = 0.25

# Why acquisitions gave up, counted rather than guessed. A lost update reports a NUMBER -- "83 of
# 400" -- and a number cannot say whether the waiters timed out, hit the absolute ceiling, or fell
# out of the loop on an exception nobody expected. Windows is the platform where this matters and
# the one that cannot be debugged interactively from here, so the run has to carry its own
# diagnosis home. Read by tests/test_concurrent_writers.py; nothing in the shipped path looks at it.
LOCK_GIVEUPS = {"no_progress": 0, "waited_too_long": 0, "unexpected_error": 0, "taken": 0}


def _replace_with_retry(tmp, dest, attempts=12, pause=0.02):
    """`os.replace`, which is not always allowed to proceed on Windows.

    🐛 On POSIX a rename over a path another process has OPEN is fine -- the reader keeps reading the
    old inode and everyone is correct. Windows refuses it: PermissionError, errno 13, measured on a
    Windows Server 2025 runner with an ubuntu column beside it in the same run showing "allowed".
    So a write here could fail purely because somebody was reading the file at that instant, and
    whatever the caller was saving was lost.

    A reader holds a small file open for microseconds, so this waits rather than gives up: twelve
    attempts over about a quarter of a second. If it still cannot land, the original exception is
    raised -- a caller that cannot write must hear about it, not be told it succeeded.

    POSIX takes the first attempt every time and pays nothing for this.
    """
    for n in range(attempts):
        try:
            os.replace(tmp, dest)
            return
        except PermissionError:
            if n == attempts - 1:
                raise
            time.sleep(pause)


# Why the last `atomic_write_text` failed, for `write_or_raise` to put in its message. A list rather
# than a return value because the bool IS the contract here and every caller tests it; same shape as
# LAST_UNREAD, and read only immediately after a False.
LAST_WRITE_ERROR = []


def atomic_write_text(dest, text, encoding="utf-8"):
    """Write `text` to `dest` so a reader sees the old file or the new one, never a half of either.

    🐛 The CHAMNAN_READ_ONLY guard returned None where every other exit returns a bool, so a caller
    testing the result saw a refusal as a failure it could not distinguish from a full disk — and
    the callers that ignore it announced writes that never happened. `chamnan-timeline new` printed
    "declared — .chamnan/threads/a-thread.md" with the variable set and no file on disk, which is
    `--preview` claiming to write nothing while creating a workspace, one layer down.

    🐛 Two halves, and having only one is worse than having neither, because it looks correct.
    `os.replace` is atomic and was never the problem; a STAGING NAME SHARED BETWEEN PROCESSES is.
    Two writers put their content into the same `x.tmp` and then each replaced `x` with whatever
    that file held at its own moment. `state.py` documented this and fixed itself; `coedit.py` and
    `rollup.py` copied the fix; `pointer.py`, `chamnan-map` and `chamnan_scratch_watch.py` did not,
    and each was reproduced losing data. Two of three concurrent `chamnan-map` runs produced a
    MAP.md with content from BOTH builds interleaved, and the losing process exited 0.

    So it is one function now rather than a rule every writer has to remember — the same reasoning
    that put `redact.emit` behind every command's `print`. `test_no_writer_builds_its_own_tmp_name`
    fails if a new one starts hand-rolling this again.

    Returns True on success. Best-effort by default: a workspace on a read-only checkout must still
    let a session start, so the caller decides whether a failed write is worth reporting.
    `write_or_raise` below is that decision made for the writes a user asked for by name.
    """
    if read_only():
        LAST_WRITE_ERROR[:] = ["CHAMNAN_READ_ONLY is set, so nothing is written anywhere"]
        return False
    tmp = None
    try:
        dest = pathlib.Path(dest)
        # 🐛 An atomic replace does not need write permission on the TARGET — `os.replace` only
        # needs a writable directory — so switching to it silently defeated a read-only file. A
        # user who `chmod 444`s a store means it, and `chamnan-promote` relies on the refusal to
        # roll back the file it already copied rather than leave an unregistered executable behind.
        # Checked explicitly, because the filesystem will not check it for us any more.
        if dest.exists() and not os.access(dest, os.W_OK):
            # Named, like the exception path below: this refusal and a full disk are the two
            # answers a caller used to get as one identical sentence, and they need opposite fixes.
            LAST_WRITE_ERROR[:] = ["the file is not writable — its permissions refuse this write"]
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Per-process, and `.tmp` last so a suffix-matching reader never mistakes it for the real
        # file. os.getpid() is enough here: two threads of one process writing the same workspace
        # file is what `exclusive()` below is for, and every entry point is a separate process.
        tmp = dest.with_name(f"{dest.name}.{os.getpid()}.tmp")
        # newline="" because Path.write_text goes through io.TextIOWrapper, whose default
        # translates every \n to os.linesep on write -- so on native Windows every file this
        # writes gets CRLF, including MAP.md, which is then diffed and grepped by tools that
        # were handed LF everywhere else. chamnan generates its own content and controls its
        # own line endings; nothing here wants the platform's opinion.
        with tmp.open("w", encoding=encoding, newline="") as fh:
            fh.write(text)
        # 🐛 A rename REPLACES the file, so the destination's permissions go with it — and three of
        # the callers here write executable scripts, chmod them, then rewrite them to add a
        # shebang. Routing those through this function silently un-executabled every promoted tool
        # (caught immediately by an existing test, which is the only reason this is a note rather
        # than a shipped defect). The mode is carried over so an atomic write is a write, not also
        # a permissions change.
        try:
            if dest.exists():
                os.chmod(tmp, os.stat(dest).st_mode & 0o7777)
        except OSError:
            pass
        _replace_with_retry(tmp, dest)
        return True
    except Exception as err:
        # 🐛 [2026-09-06] The reason was caught here and thrown away, so every caller could say was
        # "could not write X". Reproduced live with `chmod 444` and `chmod 555`: a read-only FILE, a
        # read-only DIRECTORY and a full disk all produced the identical sentence, and the first two
        # need different fixes (R15 agent 3). The bool return stays the contract -- every caller
        # tests it -- so the reason goes in a module-level slot the raising wrapper reads, the same
        # shape `LAST_UNREAD` already uses for the read ceiling.
        LAST_WRITE_ERROR[:] = [f"{type(err).__name__}: {err}"]
        if tmp is not None:
            try:
                tmp.unlink()
            except OSError:
                pass
        return False


NOTICE_TIMES = 3



def write_or_raise(dest, text, encoding="utf-8"):
    """`atomic_write_text`, for a write the user asked for by name. Raises instead of returning.

    🐛 [2026-09-06] `atomic_write_text` is best-effort on purpose and returns a bool, and of its
    two dozen call sites only `tools_index._save` and `chamnan-map` ever looked at it. The bug
    named two paragraphs above -- `chamnan-timeline new` printing "declared -- .chamnan/threads/
    a-thread.md" with no file on disk -- was fixed only in this function's own return value; the
    caller went on discarding it, so the same output came back for a read-only directory, a full
    disk, and the staging-file race in `prune_orphaned_temps` (R10 agent 2).

    The line is the one `tools_index._save`'s comment already draws: a log line, a pointer, a
    rollup cache is housekeeping and stays silent, because a workspace that cannot be written must
    not stop a session from starting. A thread, a milestone, an environment entry or a promoted
    tool is a thing somebody typed a command to get, and telling them it happened when it did not
    is worse than failing.
    """
    LAST_WRITE_ERROR[:] = []
    if not atomic_write_text(dest, text, encoding=encoding):
        raise OSError(write_failure_text(dest))
    return True


def write_failure_text(dest):
    """Why the last `atomic_write_text` to `dest` failed, as one sentence.

    Its own function because `rewrite_shared` needs the identical sentence and the alternative is
    a second copy of it — the shape this file has had to correct more than once.
    """
    why = (" (CHAMNAN_READ_ONLY is set)" if read_only()
           else f" — {LAST_WRITE_ERROR[0]}" if LAST_WRITE_ERROR else "")
    return f"could not write {dest}{why}"

def notice_due(root, key, times=NOTICE_TIMES):
    """True while a one-off piece of advice still has something to teach, and record the showing.

    Advice that repeats forever is worse than advice shown once. It costs tokens every time an agent
    runs the command, and it costs more than that from a reader's side: a tip pinned to the end of a
    report trains people to stop reading the end of the report, which is where that report's real
    caveats live. Three showings, then it stops.

    Scoped to the WORKSPACE, not the session -- the sibling nudges in `chamnan_scratch_watch` are
    per-session because they are about what this session just did, while advice about a config
    setting is learned once and stays learned.

    Both layers, as any new writer of a shared file in this codebase owes: the lock stops a lost
    update and the atomic write stops a torn file, and neither substitutes for the other. Failing to
    take the lock shows the notice rather than suppressing it -- the harmless direction, and it keeps
    a contended counter from silencing advice that was never delivered.
    """
    store = workspace(root) / "state" / "notices.json"
    with exclusive(store) as held:
        seen = load_json(store)
        seen = seen if isinstance(seen, dict) else {}
        count = seen.get(key, 0)
        if count >= times:
            return False
        if not held:
            return True
        seen[key] = count + 1
        store.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(store, json.dumps(seen, ensure_ascii=False, indent=1))
    return True



def _lock_holder_is_alive(lock):
    """True when the process named inside `lock` still exists.

    Read as a SECOND bound beside the age one, never instead of it: a lock written by an older
    version carries no PID, and an unreadable or unparseable one falls back to "not alive" so the
    age rule decides on its own exactly as it used to. The age bound alone is the one a wrong
    clock can invert; the pair cannot both be wrong at once.
    """
    return _lock_holder_state(lock) == "alive"


LOCK_HOLDER_ALIVE, LOCK_HOLDER_DEAD, LOCK_HOLDER_UNKNOWN = "alive", "dead", "unknown"


def _lock_holder_state(lock):
    """"alive", "dead", or "unknown" — and the third is not the same as the second.

    🐛 [2026-09-07] `_lock_holder_is_alive` collapses "this lock names a process that no longer
    exists" and "this lock names nobody" into one False, which is right for the age rule (it only
    runs after LOCK_STALE, by which time either is old enough to break) and wrong for anything
    that wants to act sooner. A lock is CREATED and its PID written a moment later, two separate
    syscalls, so "names nobody" is also what a perfectly healthy holder looks like for a few
    microseconds — breaking on that would hand the same file to two writers, which is the one
    thing this mutex exists to prevent.
    """
    try:
        first = lock.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    except OSError:
        return LOCK_HOLDER_UNKNOWN
    if not first or not first[0].strip().isdigit():
        return LOCK_HOLDER_UNKNOWN
    return LOCK_HOLDER_ALIVE if _pid_is_alive(int(first[0].strip())) else LOCK_HOLDER_DEAD


@contextlib.contextmanager
def exclusive(path):
    """Hold a lock beside `path` for the duration of the block. Yields True when it was acquired."""
    lock = Path(str(path) + ".lock")
    # 🐛 [2026-09-07] A lock cannot be created in a directory that does not exist, and `exclusive`
    # answered that by yielding False — "somebody else has it" — rather than by making the
    # directory. `tools_index.register` hit this, worked it out, and put a `mkdir` in front of its
    # own call with a comment explaining why. Nobody applied that to the helper, so `state.age_out`
    # locked `logs/state-ages.json` in a workspace where `logs/` does not exist yet and got False
    # EVERY TIME on a fresh workspace — the lock its own comment calls the fix for a measured
    # "26 of 40 concurrent updates lost" had never once been taken there. Found by making age_out
    # respect the boolean it had been discarding: the moment it stopped writing unlocked, it
    # stopped writing at all.
    try:
        lock.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    fd = None
    started = time.time()
    deadline = started + LOCK_TIMEOUT
    # What the lock looked like last time we were refused. A change in it means somebody finished
    # and somebody else started -- the queue is moving, and this waiter's turn is coming.
    seen = None
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            # 🐛 [2026-09-06] The holder's PID goes IN the lock, for the reason `_pid_is_alive`
            # exists: `time.time() - mtime > LOCK_STALE` is the third place in this module where a
            # forward clock jump inverted a bound. Skew the clock by more than 30 seconds and a
            # second process reads a lock a live process is still holding as abandoned, unlinks it
            # and takes it -- so the mutex hands the same shared file to two writers at once, which
            # is exactly the lost update it exists to prevent (R11 agent 2).
            try:
                os.write(fd, f"{os.getpid()}\n".encode())
            except OSError:
                pass
            break
        except FileExistsError:
            # 🐛 [2026-09-08] Progress is measured with `stat`, and the lock's CONTENT is read only
            # when it is old enough to be worth suspecting. Both halves of that sentence are a
            # Windows bug fix.
            #
            # Windows refuses to unlink a file another process holds OPEN, and Python's `open()`
            # there does not grant delete sharing. The waiter below used to read the lock on every
            # 10 ms poll -- eight waiters, a hundred reads a second each -- and the holder's own
            # `lock.unlink()` then failed with PermissionError into an `except OSError: pass`. The
            # lock survived its owner's release, and nothing could break it afterwards: the age
            # rule requires `state != LOCK_HOLDER_ALIVE` and the PID in the file belongs to a
            # process that is very much alive, having moved on to its next iteration. Every other
            # writer then waited out its ceiling and wrote unguarded. That is the shape behind
            # every number this defect produced -- 31, 41, 83, 187, 207 of 400, varying with how
            # often a read happened to overlap a release.
            #
            # `os.stat` is safe: it asks for attributes with delete sharing granted, so it does not
            # pin the file. So the poll uses stat, and the read happens once the lock looks stale
            # rather than a hundred times a second.
            now = time.time()
            try:
                st = lock.stat()
                here = (st.st_mtime_ns, st.st_size, getattr(st, "st_ino", 0))
                age = now - st.st_mtime
            except OSError:
                here, age = None, 0.0
            if here is not None and here != seen:
                seen = here
                deadline = now + LOCK_TIMEOUT
            # 🐛 [2026-09-07] A lock left by a process that has DIED was waited on for the full
            # LOCK_STALE window — 30 seconds — exactly as if a live but slow process held it.
            # Measured at 29.9s. The PID has been in the lock file since 2026-09-06 for precisely
            # this question and only the age rule ever asked it.
            #
            # "Dead", not "not alive": a lock is created and its PID written a moment later, so an
            # empty lock is what a healthy holder looks like for a few microseconds. That case
            # stays on the age rule, which is what it was always decided by.
            if age > LOCK_READ_AFTER:
                try:
                    state = _lock_holder_state(lock)
                    if state == LOCK_HOLDER_DEAD:
                        lock.unlink()
                        continue
                    if age > LOCK_STALE and state != LOCK_HOLDER_ALIVE:
                        lock.unlink()
                        continue
                except OSError:
                    pass
            if now > deadline or now - started > LOCK_WAIT_MAX:
                LOCK_GIVEUPS["waited_too_long" if now - started > LOCK_WAIT_MAX
                             else "no_progress"] += 1
                break
            time.sleep(0.01)
        # 🐛 A lock another process has just unlinked sits in Windows' DELETE-PENDING state for a
        # moment: the name is still there, every open of it fails with ERROR_ACCESS_DENIED, and
        # Python raises PermissionError rather than FileExistsError. That fell through to the
        # `except OSError: break` below, which reads "somebody has this, try again in 10ms" as
        # "this lock cannot be taken" -- and every caller of exclusive() then either skipped its
        # write or made it unguarded.
        #
        # Measured on a Windows Server 2025 runner, 8 processes x 50 increments through
        # record_call's exact shape: 399 of 400 with this treated as fatal, 400 of 400 with it
        # retried. One in four hundred, which is why it survived every previous look -- and it is
        # a lost update on a running total that nothing ever recomputes, so it stays wrong forever.
        # The ubuntu column of the same run raised it zero times, which is why POSIX never saw this.
        except PermissionError:
            # DELETE-PENDING is progress by definition: the previous holder is on its way out.
            now = time.time()
            deadline = now + LOCK_TIMEOUT
            if now - started > LOCK_WAIT_MAX:
                LOCK_GIVEUPS["waited_too_long"] += 1
                break
            time.sleep(0.01)
        except OSError as exc:
            # Not FileExistsError and not PermissionError: something this loop has no plan for.
            # It used to leave silently, which is how a platform-specific failure mode stays
            # invisible -- record what it was so the next Windows run says so out loud.
            LOCK_GIVEUPS["unexpected_error"] += 1
            LOCK_GIVEUPS.setdefault("errors", []).append(
                f"{type(exc).__name__}:{getattr(exc, 'errno', '?')}")
            break
    if fd is not None:
        LOCK_GIVEUPS["taken"] += 1
    try:
        yield fd is not None
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
            # 🐛 [2026-09-08] A single unlink that fails leaves the mutex held by nobody, forever
            # as far as any waiter can tell. On Windows it fails whenever a reader has the file
            # open at that instant, which the poll above no longer does a hundred times a second --
            # but "much rarer" is not "never", and the cost of losing this race is every other
            # writer in the workspace giving up and writing unguarded. Same shape as
            # `_replace_with_retry`, and POSIX pays for none of it.
            for _try in range(12):
                try:
                    lock.unlink()
                    break
                except FileNotFoundError:
                    break
                except OSError:
                    if _try == 11:
                        LOCK_GIVEUPS["release_failed"] = (
                            LOCK_GIVEUPS.get("release_failed", 0) + 1)
                        break
                    time.sleep(0.02)



def rewrite_shared(path, mutate, strict=True):
    """Read `path`, hand its text to `mutate`, write what comes back — with the lock held across
    all three. Returns True when something was written, False when `mutate` asked for no change.

    `mutate` is called with the file's current text, or None when it does not exist, and returns
    the new text or None for "leave it alone". It runs INSIDE the lock, so it may read whatever it
    likes about the file's current content and rely on the answer still being true when the write
    lands.

    Why a primitive rather than a rule. `atomic_write_text` fixed the tearing and every writer in
    this repository was then hardened one at a time against the OTHER half — a lost update, where
    two processes each read, each decide, and the second one's snapshot silently replaces the
    first's work. `tools_index` needed three passes to get all three of its writers; `state.py`
    documented the shape and `coedit.py` and `rollup.py` copied it while `pointer.py` and
    `chamnan-map` did not. Measured on 2026-09-07, with the fix believed complete, six more writers
    were still doing the bare read-modify-write:

        milestones.append()          5 of 6 concurrent entries vanished — no lock at all
        pointer.mark_pointed()       11 of 12 lost
        the subagent firing log      270 of 320 lines lost, 84%
        ensure()'s ignore-file repair   content tripled
        ensure()'s config.json       written with `Path.write_text`, which truncates on open
        candidates.upsert()          five files for one habit

    Every one of those is the same four lines written slightly differently, so this is the four
    lines written once. `LOCK_TIMEOUT` is short and the critical sections are small; a caller that
    cannot take the lock in that time is in real contention and is told so.

    🐛 The two halves are not interchangeable and having only one looks correct. An atomic write
    stops a READER seeing half a file and says nothing about which of two WRITERS wins; a lock
    without the atomic write stops the lost update and still lets a crash leave a torn file. Both
    are here, in one place, so no future writer has to remember either.
    """
    lock_path = Path(path)
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    with exclusive(lock_path) as held:
        if not held:
            # 🐛 Falling through to write unlocked is the mistake `tools_index.register` made and
            # had to be corrected for: it reintroduces exactly the race the lock exists to close,
            # in the situation — real contention — where that race is most likely to fire. A
            # caller that would rather skip than fail passes strict=False and gets a False back,
            # which is a fact it can act on; nobody gets a silent unguarded write.
            if strict:
                raise TimeoutError(
                    f"could not lock {lock_path} — another process is writing it. "
                    f"Nothing was changed; try again in a moment.")
            return False
        try:
            # utf-8-sig on the way IN only: it strips a BOM somebody else's editor left, and would
            # WRITE one if it were used on the way out. Every reader in this repository reads with
            # it and every writer writes plain utf-8, and that asymmetry is deliberate.
            current = lock_path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            current = None
        updated = mutate(current)
        if updated is None:
            return False
        LAST_WRITE_ERROR[:] = []
        if not atomic_write_text(lock_path, updated):
            if strict:
                raise OSError(write_failure_text(lock_path))
            return False
        return True


# The pre-commit hook chamnan installs marks itself with this line, so a hook somebody wrote by
# hand and one chamnan wrote are told apart by the file's own content rather than by its name.
GIT_HOOK_MARKER = "# >>> chamnan"


def git_hooks_dir(root):
    """Where git will ACTUALLY look for hooks, or None when this is not a repository git owns.

    Not `.git/hooks`. `core.hooksPath` relocates hooks entirely -- pre-commit, Husky and lefthook
    all set it -- and in a worktree `.git` is a FILE containing `gitdir: …`. `git rev-parse
    --git-path hooks` resolves both.

    🐛 And it resolves something ELSE if nobody checks first: in a directory holding a `.git` git
    itself refuses, git walks UP and returns the ANCESTOR repository's hooks path as a relative
    string. `git_owns` is the question that has to be asked before this one.

    🐛 [2026-09-06] Lived in `bin/chamnan-map` as a private function, so the only code that could
    ask "is the hook installed" was the code that installs it -- and nothing ever asked. A
    repository whose index quietly goes stale on every commit looks exactly like one whose hook is
    working (R14 agent 5). Moved here so the report can ask the same question the installer does,
    with the same three subtleties handled, rather than checking `.git/hooks/pre-commit` and being
    wrong in all three.
    """
    if not git_owns(root):
        return None
    sp = _subprocess()           # deferred, like every other git call in this module
    try:
        out = sp.run(["git", "-C", str(root), "rev-parse", "--git-path", "hooks"],
                     capture_output=True, text=True, encoding="utf-8",
                     errors="replace", timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            found = pathlib.Path(out.stdout.strip())
            return found if found.is_absolute() else (pathlib.Path(root) / found)
    except git_cannot_answer():
        pass
    return None


def git_hook_state(root):
    """"installed", "absent", "theirs", or None when the question does not apply here.

    "theirs" means a pre-commit hook exists and is not chamnan's -- which is not a problem and must
    not be reported as one. The distinction matters because the advice differs: an absent hook can
    be offered, and somebody else's cannot be touched.
    """
    hooks = git_hooks_dir(root)
    if hooks is None:
        return None
    target = pathlib.Path(hooks) / "pre-commit"
    if not target.is_file():
        return "absent"
    try:
        return ("installed" if GIT_HOOK_MARKER in
                target.read_text(encoding="utf-8-sig", errors="replace") else "theirs")
    except OSError:
        return None


# ---------------------------------------------------------------- the command line, asked once
HELP_FLAGS = ("-h", "--help")


VERSION_FLAGS = ("--version", "-V")


def wants_version(argv):
    """True when `argv` asks which build this is, wherever the flag sits.

    🐛 [2026-09-07] No command had `--version` at all. Ten commands, zero ways to ask, on a plugin
    whose own session-start hook prints a downgrade banner about running the wrong build — so the
    tool could TELL you it was the wrong version and you could not ask it which version it was.

    That gap is why the config-key loss below went unseen for weeks: a workspace silently rewritten
    by an older install looks identical to one nobody touched, and the first thing anyone would do
    to check is run `chamnan-map --version` and compare. `-V` as well as `--version` because the
    short form is what people type, and an unrecognised flag is refused rather than ignored, so
    typing it and getting "unknown flag" is worse than useless.
    """
    return any(a in VERSION_FLAGS for a in (argv or []))


def version_line():
    """One line naming the build, where it lives, and what interpreter is running it.

    All three, because the question behind "which version" is almost always "which INSTALL am I
    getting" — a machine here carries several under different config directories, and the version
    string alone cannot tell them apart.
    """
    here = Path(__file__).resolve().parent.parent
    return (f"chamnan {plugin_version(here) or '(version unreadable)'}  "
            f"{here}  python {sys.version.split()[0]}")


def wants_help(argv):
    """True when `argv` asks for help, wherever the flag sits.

    🐛 [2026-09-07] Eight commands wrote this test four different ways, and only two of them —
    `chamnan-report` and `chamnan-map` — looked past `argv[0]`. The other six accepted `-h` as
    DATA in any later position, and two of those then wrote to disk:

        chamnan-timeline new "my thread" -h   created .chamnan/threads/my-thread-h.md
        chamnan-promote tool.sh mytool -h     installed the tool, exit 0

    Both files are permanent and tracked, with `-h` baked into the name, from a flag the user typed
    to find out what the command does. Two further commands escaped only because their argument
    happened to be consumed first — by accident, not by design (R6 acc3, which swept the whole set
    rather than reporting one).

    An exact bare `-h` element is never a legitimate title, note or filename: a quoted title
    CONTAINING "-h" arrives as one argument and does not match. So testing every position is safe,
    and it is the only reading under which a user who types the flag gets what they asked for.
    """
    return any(a in HELP_FLAGS for a in (argv or []))


def unknown_flags(argv, known):
    """Flags in `argv` that `known` does not list — so a command can refuse rather than ignore.

    A misspelt flag silently dropped means the command does something other than what was asked
    with nothing on screen to say so. `chamnan-map` has refused unknown flags for this reason since
    it grew its own; the commands beside it accepted anything and ran their default action.
    """
    allowed = set(known) | set(HELP_FLAGS) | set(VERSION_FLAGS)
    return [a for a in (argv or []) if a.startswith("-") and a not in allowed]


def config_is_malformed(root):
    """Why config.json will not be used, as a short reason — or "" when it will be.

    Truthy/falsy exactly as the old boolean was, so `if config_is_malformed(root):` still reads the
    same; the string exists because the two ways a config is discarded need different advice and the
    block used to give one message for both.

    Separate from ensure() so the hook can say so without ensure() having to return it, and cheap
    enough to do twice -- the file is a few hundred bytes. Missing, empty and unreadable all return
    "": those degrade correctly and always have. Only a file the user clearly meant to write, and
    got wrong, is worth a line in the block.

    🐛 [2026-09-04] This only knew about the first case, and the second is the one that actually
    fires. A `config.json` holding `[]`, `"text"`, `42` or `null` is VALID JSON, so it parsed, so
    this returned False -- and `load_config` then dropped it anyway because `load_json(path, dict)`
    returns an empty dict for anything that is not an object. Every value the user set vanished and
    nothing said a word. Measured on all four shapes: `index_token_budget` came back as the 3000
    default in each.

    The suite had a guard pointed at the first case, and on Python 3.14 it stopped reaching even
    that: `json.loads` there parses 100,000 levels of nesting without complaint, so the 10,000-level
    config the test writes is not a parse failure any more -- it is a list, which lands in the second
    case. The guard had quietly become a test of the wrong thing on the newest interpreter while
    still passing on older ones.
    """
    try:
        return _config_problem(workspace(root) / "config.json")
    except NotAWorkspace:
        return ""


def _config_problem(path):
    """The one definition of "load_config will discard this file", shared with ensure().

    It was two: this function decided what the block SAYS, and ensure() decided whether the file is
    safe to rewrite, using a narrower rule of its own. They disagreed on a config that is valid JSON
    but not an object -- ensure() called it fine and overwrote it, while the block said nothing --
    which is how `["a","b"]` became a default config with no warning and no backup. Same question,
    so it is answered in one place.
    """
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""
    if not text.strip():
        return ""
    try:
        parsed = json.loads(text)
    except (ValueError, RecursionError):
        return "does not parse"
    if not isinstance(parsed, dict):
        # Named, because "wrong shape" is not actionable and "you wrote an array" is. In JSON's own
        # vocabulary, not Python's -- the person reading this wrote JSON, and "NoneType" would send
        # them looking for something that does not exist in the file they are editing.
        _JSON_NAME = {list: "array", str: "string", bool: "boolean",
                      int: "number", float: "number", type(None): "null"}
        return f"is a JSON {_JSON_NAME.get(type(parsed), 'value')}, not an object"
    return ""


# ---------------------------------------------------------------------------------------------
# 🐛 [2026-09-06] chamnan decides what its root is by looking for a `.git`, `.hg` or `.svn` entry.
# Real git decides differently: a `.git` that is an empty directory, or a directory copied without
# its contents, or an interrupted `git init`, is not a repository to git — so `git -C <that dir>`
# does not fail. It WALKS UP and answers about the nearest real repository above it.
#
# Twelve call sites shelled out to `git -C root ...` on that assumption and every one of them was
# reporting somebody else's repository (R6 acc3, first ten minutes). Reproduced: in a directory
# holding one file and an empty `.git/`, nested inside a real repository, the session-start block
# said "10 uncommitted file(s)" and named a branch — the ANCESTOR's status; `chamnan-map` stamped
# `Built from <sha>` into MAP.md with the ancestor's HEAD; and `--install-git-hook` resolved
# `rev-parse --git-path hooks` to `../../../.git/hooks`, joined it onto root, and wrote a real
# executable pre-commit hook into the unrelated ancestor repository, printing success.
#
# So the question every one of those sites has to ask first is not "does a .git exist" — which is
# chamnan's own root rule and stays as it is, because a workspace inside a half-made repository is
# still that directory's workspace — but "does GIT agree this directory is the repository". Asked
# once per root and cached: a subprocess per call site would be twelve of them at session start.
_GIT_OWNS = {}



# True when git IS on PATH but cannot answer `-C`. Kept apart from `git_is_installed()` because
# the two cases need different sentences: "install git" is useless advice to somebody who has it.
_GIT_TOO_OLD = False


def git_is_too_old():
    """Whether a `git -C` in this process has come back saying it does not know that option.

    False until one has been attempted: this reports evidence already gathered, it does not go
    looking. `git_can_speak_for` is what sets it, and every caller that needs this answer has been
    through that function first.
    """
    return _GIT_TOO_OLD


def git_is_installed():
    """Whether a `git` executable is on PATH at all. Cached, like `git_owns`.

    🐛 [2026-09-07] `git_owns` answers False for "not a repository" and for "git is not installed",
    and every caller treats both as "nothing to say". For the first that is right; for the second it
    is a silent failure in a plugin whose whole session block is built out of git — "Where the last
    session stopped" simply vanished, with no diagnostic anywhere, and the user is left thinking
    chamnan has nothing to tell them rather than that it cannot look (R10 agent 1).
    """
    global _GIT_ON_PATH
    if _GIT_ON_PATH is None:
        import shutil
        # 🐛 [2026-09-07] `which("git")` answers "a file called git exists", and every `git -C` in
        # this package needs more than that: `-C` arrived in git 1.8.5, and RHEL 7 and CentOS 7
        # shipped 1.8.3.1 for years. On such a machine this returned True, the diagnostic added
        # this morning for "git is missing" therefore never fired, and every git-derived section
        # went silent with nothing anywhere saying why — which is the exact failure that
        # diagnostic exists to prevent, reached by the other half of the same set (R13 agent 1).
        #
        # So the question is not "is git here" but "can git answer the way this package asks", and
        # the only honest way to know is to ask it once.
        # \U0001f41b [2026-09-07] This ran `git -C . rev-parse` here to find out whether the git on
        # PATH is new enough to understand `-C` (1.8.5, 2013). It answered correctly and cost a
        # process spawn on every session to do it — and `git_can_speak_for` runs `git -C` a moment
        # later anyway, so the same fact was already available for free from a call we make
        # regardless. CI showed the cost rather than the correctness: Windows went from 4m16s to
        # 9m25s and three concurrency checks stopped fitting their window.
        #
        # So this is a cheap `which` again, and "too old" is recorded by the first real `git -C`
        # that comes back saying it does not know the option. Detection where the evidence already
        # is, rather than a question asked in advance.
        _GIT_ON_PATH = shutil.which("git") is not None
    return _GIT_ON_PATH


_GIT_ON_PATH = None


def git_toplevel(root):
    """The working-tree root of the repository `root` belongs to, or None when there is none.

    Exists so a refusal can name the repository the caller is actually in. `git_owns` returning
    False has two very different meanings — "no repository anywhere" and "a repository, higher up"
    — and a message that does not tell them apart sends the reader to check the wrong thing.
    """
    try:
        out = _subprocess().run(["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                                stdin=_subprocess().DEVNULL, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=10)
        return (out.stdout.strip() or None) if out.returncode == 0 else None
    except git_cannot_answer():
        return None


_GIT_SPEAKS = {}


def git_can_speak_for(root):
    """True when git recognises `root` as part of a repository — the weaker question `git_owns` is
    not, and the right one for every READ that is path-scoped to `root`.

    `git_owns` asks "is this directory exactly the repository". That is correct for a WRITE — where
    the hook goes, whose HEAD gets stamped into a committed file — and it is too strong for
    everything else, because a `.chamnan/` deliberately placed in a subproject of a monorepo is a
    layout `find_root` documents as supported and `git_owns` answers False for. Four features went
    dark there and nothing said so: "Where the last session stopped" returned empty with real
    uncommitted files under it, `MAP.md` never got its `Built from <sha>` line so the staleness
    check was permanently blind, churn ranking returned {} against 50+ real commits, and
    `--install-git-hook` printed "not a git repository" at a directory git tracks perfectly well
    (R7 agent 3).

    🐛 The guards those four sites carry are not wrong, they are aimed at the wrong half of the
    problem. Each says an ANCESTOR's answer must not be used for THIS directory — true, and the fix
    for it is to SCOPE THE QUERY, not to refuse to ask. Measured: `git -C <subdir> status
    --porcelain -- .`, `ls-files`, `check-ignore`, `log -- <path>` and `diff -- .` are all already
    scoped to the subdirectory, and `rev-parse HEAD` is the same commit either way because it is
    the same repository. The one that was not scoped was churn's `git log`, which listed the whole
    monorepo with repository-root-relative paths; it takes `--relative -- .` now.

    And one measurement that removes a distinction this codebase believed in: a directory holding a
    `.git` git REFUSES — an interrupted `git init`, an empty `.git/` — is indistinguishable from an
    ordinary subdirectory, because git simply ignores it and answers about the enclosing
    repository. `--show-toplevel`, `--absolute-git-dir` and `HEAD` return identical values for
    both. So there is nothing here to tell apart, and scoping is the whole answer for both.
    """
    key = str(Path(root).resolve())
    if key in _GIT_SPEAKS:
        return _GIT_SPEAKS[key]
    answer = False
    try:
        out = _subprocess().run(["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                                stdin=_subprocess().DEVNULL, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=10)
        # A git too old for `-C` fails on the OPTION, not on the directory — "unknown option"
        # rather than "not a repository". Recorded here because this is the first `git -C` any
        # session makes, so the answer costs nothing beyond the call already being made.
        if out.returncode != 0 and "unknown option" in (out.stderr or "").lower():
            global _GIT_TOO_OLD
            _GIT_TOO_OLD = True
        answer = out.returncode == 0 and bool(out.stdout.strip())
        if not answer:
            answer = git_owns(root)          # a bare repository, which has no working tree
    except git_cannot_answer():
        answer = False
    _GIT_SPEAKS[key] = answer
    return answer


def git_owns(root):
    """True when git itself resolves `root` AS the repository, not as a directory inside one.

    CALLERS MUST CHECK THE RESULT: every `git -C <root>` in this package is only meaningful when
    this is True. False means either "not a repository at all" or, far worse, "a repository, but a
    different one further up" — and those two are indistinguishable from a return code.

    True for an ordinary checkout, a linked worktree and a submodule (git's own `--show-toplevel`
    is the working tree's root in all three), and for a bare repository, which has no working tree
    and answers with its own directory instead. False for anything that merely sits inside one.
    """
    key = str(Path(root).resolve())
    if key in _GIT_OWNS:
        return _GIT_OWNS[key]
    answer = False
    try:
        out = _subprocess().run(["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            answer = Path(out.stdout.strip()).resolve() == Path(root).resolve()
        else:
            # No working tree: a bare repository is still "this directory IS the repository", and
            # refusing one here would take the specific bare-repo refusals with it.
            # `--absolute-git-dir` arrived in git 2.13 (2017), four generations after `-C` itself,
            # so a git from the 1.8.5-2.12 range — Ubuntu 14.04 and 16.04 shipped one — has the
            # flag this function is called with and not the flag this branch uses. It answered
            # False for a bare repository that git itself resolves, silently. `--git-dir` is as old
            # as git and gives the same answer once resolved against `root` (R13 agent 1).
            bare = _subprocess().run(
                ["git", "-C", str(root), "rev-parse", "--absolute-git-dir"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
            if bare.returncode != 0 and "unknown option" in (bare.stderr or "").lower():
                bare = _subprocess().run(
                    ["git", "-C", str(root), "rev-parse", "--git-dir"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
            if bare.returncode == 0 and bare.stdout.strip():
                found = Path(bare.stdout.strip())
                if not found.is_absolute():          # --git-dir may answer relatively
                    found = Path(root) / found
                answer = found.resolve() == Path(root).resolve()
    except git_cannot_answer():  # git missing, unrunnable, or an unresolvable path
        answer = False
    except Exception:                     # noqa: BLE001 — subprocess timeouts and friends
        answer = False
    _GIT_OWNS[key] = answer
    return answer


# Every way asking git a question can fail, as ONE definition rather than fourteen tuples.
#
# 🐛 [2026-09-07] `NotImplementedError` was in none of them, and that is the failure mode of an
# environment with no process layer AT ALL -- Pyodide/WASM, and some restricted sandboxes and CI
# containers. The tuples covered "git is not installed" (OSError) and "git said something odd"
# (SubprocessError); they did not cover "there is no such thing as running a program here", so
# chamnan did not degrade to its no-git behaviour, it raised out of `mapper.scan()` and took the
# whole index with it. Reproduced by disabling subprocess and calling scan/render:
#
#     NotImplementedError: subprocess is not available in Pyodide/WASM
#       workspace.py:2256 git_can_speak_for   except (OSError, ValueError)
#
# chamnan already answers "no git" gracefully and has a test for it; this is the same answer for a
# stricter environment, and it is the same defect shape as the rest of this week -- a handler that
# names some members of a set and misses the identical one beside it. `ValueError` stays because
# a bad argument to `run()` raises it, and `SubprocessError` because a timeout is one.
def _subprocess():
    """Imported here rather than at module scope: `workspace` is the module every other one loads,
    and it has stayed free of anything that runs a process at import time.

    Measured 2026-09-07: `subprocess` is already in `sys.modules` by the time this module finishes
    importing, so the laziness buys nothing on today's import graph. Kept anyway -- that is a fact
    about what else happens to import it, not a property this file controls, and the cost of
    keeping the accessor is one function call.
    """
    import subprocess
    return subprocess


def git_cannot_answer():
    """Every way "ask git a question" can fail, as ONE definition rather than fourteen tuples.

    \U0001f41b [2026-09-07] `NotImplementedError` was in none of them, and that is how an
    environment with no process layer AT ALL fails -- Pyodide/WASM, and some restricted sandboxes
    and CI containers. The tuples covered "git is not installed" (OSError) and "git said something
    odd" (SubprocessError); none covered "there is no such thing as running a program here", so
    chamnan did not fall back to its no-git behaviour, it raised out of `mapper.scan()` and took
    the whole index with it. Reproduced by disabling subprocess and calling scan/render:

        NotImplementedError: subprocess is not available in Pyodide/WASM
          workspace.py git_can_speak_for   except (OSError, ValueError)

    chamnan already answers "no git" gracefully and is tested for it; this is the same answer for a
    stricter environment. It is also the same shape as the rest of this week -- a handler naming
    some members of a set and missing the identical one beside it -- which is why it is one
    function with fourteen callers rather than fourteen tuples kept in step by hand.

    `ValueError` stays because a bad argument to `run()` raises it, and `SubprocessError` because a
    timeout is one. Named through `_subprocess()` so this file keeps the property above.
    """
    return (OSError, ValueError, NotImplementedError, _subprocess().SubprocessError)
