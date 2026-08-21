"""Locating and reading the .chamnan/ workspace. Shared by every bin/ command and hook.

The workspace lives at the repository root rather than somewhere under the user's home, because
everything in it is about ONE codebase: the map describes that repo's files, the skills record
procedures for that repo's stack, the state names that repo's in-flight work. Putting it beside the
code also means it can be committed, so a team shares one accumulated memory instead of each member
rebuilding their own — and a machine move carries it along with the clone.
"""
import json
import os
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
    # Mention it when a read is about to pull in a lock file, a minified bundle or a very large
    # file. A notice, never a block — the one time someone genuinely needs to read package-lock.json
    # is the one time refusing would be most wrong.
    "warn_on_bulk_reads": True,
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
    # These accumulate one per working session in a directory that gets committed, so they are
    # bounded from the start rather than after somebody's repository fills up. Longer than the log
    # window because a record from three weeks ago is still the answer to "what was I doing".
    "session_retention_days": 30,
    # Project memory — why the code is the way it is. Rules are injected every session; decisions
    # and lessons contribute a title and are read on demand. Deliberately NOT age-pruned: a session
    # record stops mattering, a decision does not. See lib/memory.py.
    "memory": True,
    # Project milestones — the handful of changes that reshaped the repository. Only the two most
    # recent TITLES are injected, so the file's length costs nothing per session. Not project
    # management: no status, no owner, no dates-as-deadlines. See lib/milestones.py.
    "milestones": True,
}
VCS_MARKERS = (".git", ".hg", ".svn")


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


def load_config(root=None):
    path = workspace(root) / "config.json"
    cfg = dict(DEFAULT_CONFIG)
    try:
        cfg.update(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        pass
    return cfg


def enabled(part, root=None):
    return bool(load_config(root).get(part, True))


def prune_logs(root=None):
    """Delete files under logs/ older than the retention window. Best-effort and silent: a
    housekeeping failure must never be the reason a command the user asked for fails."""
    import time
    ws_dir = workspace(root)
    logs = ws_dir / "logs"
    if not logs.is_dir():
        return 0
    cutoff = time.time() - load_config(root).get("log_retention_days", 7) * 86400
    removed = 0
    for path in logs.iterdir():
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            continue
    return removed


def prune_sessions(root=None):
    """Apply session_retention_days to sessions/. Called alongside prune_logs from the same
    bin/ commands; separate because the two windows differ and conflating them would mean one
    number for two very different kinds of file."""
    import sessions
    return sessions.prune(root, load_config(root).get("session_retention_days", 30))


def ensure(root=None):
    ws = workspace(root)
    for sub in ("", "skills", "tools", "logs", "sessions",
                "memory", "memory/decisions", "memory/lessons", "memory/rules"):
        (ws / sub).mkdir(parents=True, exist_ok=True)
    # Merge rather than skip. A config written by an older version is missing every key added
    # since, and nothing says so — the user edits the key they remember, it does nothing, and the
    # setting appears broken. Found the first time this plugin was upgraded in place: the file
    # still held a key that had been deleted and none of the three that replaced it.
    cfg = ws / "config.json"
    current = {}
    if cfg.exists():
        try:
            current = json.loads(cfg.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            current = {}
    merged = dict(DEFAULT_CONFIG)
    # Keys the user set are kept; keys no longer in DEFAULT_CONFIG are dropped, so a stale option
    # cannot sit in the file looking as though it still does something.
    merged.update({k: v for k, v in current.items() if k in DEFAULT_CONFIG})
    if merged != current:
        cfg.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    return ws
