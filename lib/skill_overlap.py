"""Overlap between skill files, found by exact signals only and RECORDED rather than warned about.

The person this exists for is not an engineer. They will never open two skill files and compare
them, and if a created skill quietly contradicts a plugin skill they installed, the only thing they
will ever see is the assistant behaving oddly on a task -- with nothing connecting that to a file.

**This module deliberately does not score similarity.** R13 agent 1 prototyped the cheap version --
`difflib` over 26 real files, 325 pairs -- and measured it as unusable in BOTH directions: over 100
pairs scored above an 0.35 title threshold purely on shared boilerplate ("# Skill: ", "working_"),
while the non-noisy signal (body text) scored every pair below 0.30, i.e. it would also stay silent
on a real conceptual duplicate written in different words. A check that cries wolf a hundred times
teaches the one person it is for to ignore it, which is worse than not having it. So this module
reports only things that are true by construction:

  * `divergent`  -- the same skill name exists in two active stores and the bytes differ. This is
                    the one that has already happened here: the marketplace snapshot of chamnan's
                    own skills is missing `disable-model-invocation: true` on all five write
                    skills, while the loaded cache copy has it (R13 agent 1 finding 7).
  * `shadowed`   -- the same skill name is provided by two DIFFERENT plugins, or by a plugin and by
                    the workspace. Which one the host prefers is not documented and was not
                    testable, so the honest report is "two things answer to this name", not a
                    guess about which wins.
  * `restates`   -- a workspace skill file that contains a shipped skill's body verbatim. Exact
                    containment, not resemblance: no threshold, no false positives.

Nothing here blocks a capture or injects a warning into a session. The findings are written to a
store the owner reads when they choose to, the same shape `candidates.py` already uses for typo and
router-economy staging -- a pattern this workspace has trusted for three other kinds of evidence.
Two reasons it must not be a session-block warning: the skills section of the block is CUT on 41 of
233 real firings and never built at all on 149 more (measured 2026-09-10 against
`logs/block_shape.jsonl`), so a warning placed there is a warning that mostly does not arrive; and
the host silently ignores `disable-model-invocation` (claude-code#22345, open), so a refusal cannot
be enforced at the point it would matter anyway.
"""

import hashlib
import json
import os
import re
from pathlib import Path

STORE = "skill_overlaps"

_FRONT = re.compile(r"^---\s*$")
_DESC = re.compile(r"^description:\s*(.*)$", re.I)


def _home(home=None):
    return Path(home) if home else Path(os.path.expanduser("~"))


def active_plugin_roots(home=None):
    """Only the plugin versions the host has actually LOADED.

    `plugins/cache/<plugin>/<plugin>/<version>/` keeps every version ever installed -- on this
    machine 1.24.0 sits beside 0.1.4, 1.7.1 and 1.20.1, all of chamnan itself. Globbing the cache
    naively makes a plugin look like four conflicting plugins, which is exactly the false alarm
    this module exists to avoid. `installed_plugins.json` names the one that is live.
    """
    out = []
    manifest = _home(home) / ".claude" / "plugins" / "installed_plugins.json"
    try:
        # 🐛 [2026-09-18] (R29.9) Five of twenty-one `json.loads` reads in this package could not
        # strip a leading BOM; three of the five read a file the HOST writes, not chamnan itself --
        # this one, a host's `settings.json`, and the `plugin.json` it points at -- and PowerShell's
        # `Set-Content` writes UTF-8 with a BOM by default. Fixed here and at the other four sites
        # (`hooks/chamnan_skill_pointer.py`, `bin/chamnan-setup` x3); this comment is the one place
        # that records why, per check 185.
        data = json.loads(manifest.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, RecursionError):
        # RecursionError is named because this file is written by the host, not by chamnan, and a
        # deeply nested document raises it rather than a ValueError. A hook that dies here takes the
        # session's whole block with it, so every json read in this package names it.
        return out
    # Shape (version 2): {"plugins": {"<name>@<marketplace>": [ {installPath, version, ...}, ... ]}}
    # The value is a LIST -- one entry per scope (user/project), not a single record. Reading it as
    # a record silently yields nothing, which reads exactly like "no plugins installed".
    plugins = data.get("plugins", data) if isinstance(data, dict) else {}
    if not isinstance(plugins, dict):
        return out
    for key, installs in plugins.items():
        name = str(key).split("@")[0]
        for e in (installs if isinstance(installs, list) else [installs]):
            if not isinstance(e, dict):
                continue
            path = e.get("installPath") or e.get("path") or e.get("root")
            if path:
                out.append((name, Path(os.path.expanduser(str(path)))))
    return out


def snapshot_roots(home=None):
    """Marketplace snapshots -- NOT loaded, but they are what a resync would promote."""
    base = _home(home) / ".claude" / "plugins" / "marketplaces"
    try:
        return [(p.name, p) for p in sorted(base.iterdir()) if p.is_dir()]
    except OSError:
        return []


def _describe(text):
    head = text[:1200]
    if head.lstrip().startswith("---"):
        body = head.split("---", 2)
        if len(body) > 2:
            for line in body[1].splitlines():
                m = _DESC.match(line.strip())
                if m:
                    return m.group(1).strip()
    for line in text.splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            return s
    return ""


def _record(name, path, store, text):
    return {
        "name": name,
        "path": str(path),
        "store": store,
        "description": _describe(text),
        "digest": hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16],
        "body": text,
    }


def inventory(root, home=None):
    """Every skill reachable from here, labelled by which store it came from.

    Four kinds of store, and the labels matter more than the paths: a name appearing twice inside
    one store is a different problem from the same name appearing in two.
    """
    root = Path(root)
    found = []
    for p in sorted((root / ".chamnan" / "skills").glob("*.md")):
        if p.name.upper() == "README.MD":
            continue
        try:
            found.append(_record(p.stem, p, "workspace", p.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            continue
    for label, base in active_plugin_roots(home):
        for p in sorted(base.glob("skills/*/SKILL.md")):
            try:
                found.append(_record(p.parent.name, p, f"plugin:{label}", p.read_text(encoding="utf-8", errors="replace")))
            except OSError:
                continue
    for label, base in snapshot_roots(home):
        for p in sorted(base.glob("skills/*/SKILL.md")):
            try:
                found.append(_record(p.parent.name, p, f"snapshot:{label}", p.read_text(encoding="utf-8", errors="replace")))
            except OSError:
                continue
    return found


def _core(text):
    """A skill's body with blank lines and headings removed, so two copies of the same text compare
    equal regardless of how they were re-wrapped when pasted."""
    return "\n".join(l.rstrip() for l in text.splitlines()
                      if l.strip() and not l.lstrip().startswith("#"))


def _plugin_of(store):
    return store.split(":", 1)[1] if ":" in store else store


def overlaps(root, home=None, found=None):
    """Every exact overlap, as a list of dicts. Empty list means nothing to report -- and on this
    machine that is the honest answer for `restates`, which is why the check is worth trusting.
    """
    found = inventory(root, home) if found is None else found
    by_name = {}
    for r in found:
        by_name.setdefault(r["name"], []).append(r)

    out = []
    for name, group in sorted(by_name.items()):
        if len(group) < 2:
            continue
        # 🐛 [2026-09-12] `restates` below has always required a `workspace` record. These two did
        # not, so two purely machine-global stores disagreeing with each other were reported as a
        # finding ABOUT THE REPOSITORY the command was pointed at. Reproduced on a brand-new scratch
        # repo whose `.chamnan/skills/` holds zero entries: `chamnan-report` opened with "7 skill(s)
        # exist in two places with DIFFERENT contents", every one of them read out of
        # `~/.claude/plugins/` on the machine running it. For a tool whose pitch is "measure it,
        # trust the numbers", the first number a stranger sees was about somebody else's computer
        # (R1 agent 2, 2026-09-12).
        #
        # The message was also untrue for that case. `snapshot_roots` says in its own docstring that
        # marketplace snapshots are NOT loaded -- they are what a resync WOULD promote -- and the
        # sentence claimed "which copy gets read depends on which one the host resolves first". A
        # copy that is never read cannot be the one that is resolved.
        #
        # What this loses is real and is not being papered over: a repository report no longer
        # notices two plugin copies disagreeing, or a cache drifting from its marketplace. Nothing
        # else reports those today. The trade was made on the owner's word after acc4 was consulted
        # and argued the same way -- a per-repository command answers about that repository, and an
        # installation-level audit needs an audience of its own before it is worth keeping here.
        if not any(r["store"] == "workspace" for r in group):
            continue
        digests = {r["digest"] for r in group}
        plugins = {_plugin_of(r["store"]) for r in group}
        if len(digests) > 1:
            # The same skill, two versions of the truth. Which one is read depends on which store
            # the host resolves first -- and a marketplace resync can change that answer without
            # anyone touching a file.
            out.append({
                "kind": "divergent",
                "name": name,
                "where": sorted((r["store"], r["path"]) for r in group),
            })
        elif len(plugins) > 1:
            out.append({
                "kind": "shadowed",
                "name": name,
                "where": sorted((r["store"], r["path"]) for r in group),
            })

    shipped = [r for r in found if r["store"].startswith("plugin:")]
    for w in [r for r in found if r["store"] == "workspace"]:
        for s in shipped:
            if s["name"] == w["name"]:
                continue  # already reported above as divergent or shadowed
            # Normalise BOTH sides the same way. Comparing a normalised needle against a raw
            # haystack silently never matches -- the shipped body's blank lines survive in the
            # copy and break the substring. Found by the randomised suite, not by reading.
            core = _core(s["body"])
            if len(core) > 200 and core in _core(w["body"]):
                out.append({
                    "kind": "restates",
                    "name": w["name"],
                    "where": sorted([(w["store"], w["path"]), (s["store"], s["path"])]),
                })
    return out
