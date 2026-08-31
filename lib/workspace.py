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
    # store held zero, and session_start.py never once told an agent that /chamnan:remember
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
    for sub in ("", "skills", "tools", "logs", "sessions", "threads",
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


VERSION_FILE = ".version"


def plugin_version(plugin_root):
    """The running plugin's own version, from the manifest beside it. "" if it cannot be read."""
    try:
        data = json.loads((Path(plugin_root) / ".claude-plugin" / "plugin.json")
                          .read_text(encoding="utf-8"))
        return str(data.get("version", ""))
    except (OSError, ValueError, TypeError):
        return ""


def _as_tuple(version):
    out = []
    for part in str(version).split("."):
        digits = "".join(c for c in part if c.isdigit())
        out.append(int(digits) if digits else 0)
    return tuple(out)


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
    if not running:
        return ""
    path = workspace(root) / VERSION_FILE
    try:
        seen = path.read_text(encoding="utf-8").strip()
    except OSError:
        seen = ""
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
    """
    try:
        root = Path(plugin_root).resolve()
        running = plugin_version(root)
        if not running:
            return ""
        name = json.loads((root / ".claude-plugin" / "plugin.json")
                          .read_text(encoding="utf-8")).get("name", "")
        for ancestor in root.parents:
            if ancestor.name != "plugins":
                continue
            for entry in sorted((ancestor / "marketplaces").iterdir()):
                manifest = entry / ".claude-plugin" / "plugin.json"
                if not manifest.is_file():
                    continue
                data = json.loads(manifest.read_text(encoding="utf-8"))
                if name and data.get("name") != name:
                    continue
                offered = str(data.get("version", ""))
                if offered and _as_tuple(offered) > _as_tuple(running):
                    return offered
            break
    except (OSError, ValueError, TypeError):
        pass
    return ""
