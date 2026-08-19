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
}
VCS_MARKERS = (".git", ".hg", ".svn")


def find_root(start=None):
    """Repo root: the nearest ancestor holding .chamnan/, else the nearest holding a VCS marker.

    An existing workspace wins over the VCS marker so a workspace deliberately placed in a
    subproject of a monorepo is not silently relocated to the outer repository root."""
    here = Path(start or os.getcwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / WORKSPACE_DIRNAME).is_dir():
            return candidate
    for candidate in (here, *here.parents):
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


def ensure(root=None):
    ws = workspace(root)
    for sub in ("", "skills", "tools", "logs"):
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
