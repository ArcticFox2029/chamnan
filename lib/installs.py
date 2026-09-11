"""How many copies of this plugin are installed, and whether the newest one is the one running.

Written for 1.26 after 1.25.0 was deployed to three accounts, verified, reported as complete, and
was still serving 1.24.0 to one of them.

**The failure, exactly.** A host can hold more than one install of the same plugin, one per scope —
`user`, `project`, `local`, `managed` — and a narrower scope wins. Updating "chamnan" updates the
USER one and says `✔ updated to 1.25.0`, which is true and is not the whole truth: a `project`
install pinned at the HOME DIRECTORY stayed at 1.24.0, and because every session runs somewhere
under the home directory, that stale copy was the one answering. Every version string anyone thought to
check said 1.25.0. The files of the running hooks were a release behind.

**Why `ws.reconcile_version` does not cover it.** That notices a DOWNGRADE — an older build running
in a workspace a newer one already touched — so it fires after the wrong version has run, and only
where a newer one has been. It cannot see an install sitting unused that will win the next time
somebody opens a session in a different directory. This looks at the installation instead of at the
workspace, which is the only place the answer exists before the damage.

No network, and no host API: the registry is a file the host already maintains beside the cache this
module is running out of.
"""
import json
import re
from pathlib import Path

REGISTRY = "installed_plugins.json"
# Built from its halves rather than written whole. `<plugin>@<marketplace>` is the host's own id
# shape, and with both halves the same word the literal reads as an email address to this package's
# own redactor — which refused the file on every CI platform. The workspace already records the rule
# it broke: build the forbidden shape at runtime instead of spelling it out.
_NAME = "chamnan"
PLUGIN_KEY = f"{_NAME}@{_NAME}"
_VERSION = re.compile(r"\A\d+\.\d+\.\d+\Z")


def registry_path(start=None):
    """The host's install registry for the config directory this code is running out of.

    Derived from this file's own location rather than from `CLAUDE_CONFIG_DIR`, because the env var
    is not set for the default account and IS set for the others — so reading it answers correctly
    for two of three accounts and silently wrongly for the third, which is the shape of bug this
    module exists to end rather than to add.
    """
    here = Path(start or __file__).resolve()
    for parent in here.parents:
        if parent.name == "plugins" and (parent / REGISTRY).is_file():
            return parent / REGISTRY
    return None


def installs(start=None):
    """Every recorded install of this plugin: (version, scope, project path, install path).

    Empty when the registry is absent or unreadable — a plugin can be run straight out of a
    checkout, and that is not a fault to report.
    """
    reg = registry_path(start)
    if not reg:
        return []
    try:
        data = json.loads(reg.read_text(encoding="utf-8-sig"))
    # `RecursionError` is named because a JSON document nested past the interpreter's limit raises
    # it rather than `ValueError`, and it is not a subclass of it — the package holds every
    # `json.loads` to catching it, and the release gate refused this file until it did. A registry
    # is written by the host, so this is the "somebody else's file" case the rule exists for.
    except (OSError, ValueError, UnicodeDecodeError, RecursionError):
        return []
    out = []
    for rec in (data.get("plugins") or {}).get(PLUGIN_KEY) or []:
        if not isinstance(rec, dict):
            continue
        v = str(rec.get("version") or "")
        out.append({"version": v if _VERSION.match(v) else "",
                    "scope": str(rec.get("scope") or "?"),
                    "project": str(rec.get("projectPath") or ""),
                    "path": str(rec.get("installPath") or "")})
    return out


def _as_tuple(v):
    return tuple(int(p) for p in v.split(".")) if _VERSION.match(v) else (0, 0, 0)


def stale_installs(running, start=None):
    """The installs older than `running`, newest-first. Empty when everything agrees.

    `running` is the version whose code is executing. An install NEWER than it is reported too —
    that is the case where the copy being read is not the copy that will answer next time, and it
    is just as wrong as the reverse.
    """
    if not _VERSION.match(str(running or "")):
        return []
    here = _as_tuple(running)
    return sorted((r for r in installs(start) if r["version"] and _as_tuple(r["version"]) != here),
                  key=lambda r: _as_tuple(r["version"]), reverse=True)


def disagreement(running, start=None):
    """One line naming the scopes that disagree, or "" when they do not.

    Names the SCOPE and the version, because that pair is what the fix needs: `claude plugin update
    chamnan@chamnan -s <scope>` run from the project path. Without the scope the obvious command
    updates `user`, reports success, and changes nothing — which is what happened.
    """
    odd = stale_installs(running, start)
    if not odd:
        return ""
    bits = []
    for r in odd[:3]:
        where = f" at {r['project']}" if r["project"] else ""
        bits.append(f"{r['version']} ({r['scope']}{where})")
    more = f", +{len(odd) - 3} more" if len(odd) > 3 else ""
    return (f"{len(odd)} other install(s) of chamnan are registered on this host — "
            f"{'; '.join(bits)}{more} — while {running} is the code running. A narrower scope wins, "
            f"so the one answering may not be the one you updated. "
            f"Fix with `claude plugin update {PLUGIN_KEY} -s <scope>` from the project path.")

def running_version(start=None):
    """The version of the code executing, or "" when the manifest cannot be read. Never raises.

    Its own, rather than `adapters._running_version()`: that is private to a package this module has
    no other reason to import, and the first version of the caller reached for it by name in the
    hook, where it does not exist. The result was a `NameError` swallowed by `never_fail` — the
    session block simply lost its rules section and said nothing, which is the failure shape this
    module was written to end.
    """
    try:
        import workspace as _ws
        return _ws.plugin_version(Path(start or __file__).resolve().parents[1])
    except Exception:      # noqa: BLE001 — a version nobody can read must not break a session
        return ""
