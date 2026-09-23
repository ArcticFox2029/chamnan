"""Is this about to write somewhere that is not ours? — the highest-severity rule, with a machine.

ENFORCES: memory/rules/never-touch-the-os-outside-lumin-app.md

🔴 [owner 2026-09-10] A throwaway debug line — `defaults write com.apple.Terminal "Window Settings"
-dict-add "Clear Dark" ""` — replaced the owner's default Terminal profile, a dictionary, with an
empty string. Terminal then aborted before drawing a window, four crash reports in seventy seconds,
and the customised colours were gone permanently: a preference file has no version history and
`tmutil listlocalsnapshots` returned nothing.

That rule has been the loudest line in the store since, and until now it was enforced by nothing at
all. A rule with no machine is NIOSH's fourth control tier of five — it works exactly as well as
the person remembering it, which on 2026-09-10 was not at all.

**The boundary is the repository, not a list of paths.** A write inside the checkout is ordinary
work and reversible; a write outside it is somebody's machine. Two carve-outs, both principled:
scratch directories, which exist to be thrown away, and the agent's own state directory, which is
its data in the same sense the checkout is. Everything else outside the root is read-only.

The second half is a list, unavoidably: the commands that change machine state without touching a
path the hook can see — `defaults`, `launchctl`, `pmset`. That list is the population "verbs that
mutate the machine", taken from the rule's own enumeration, not a sample of one incident.

**It never blocks.** Same contract as every hook here: it says what is about to happen and the
person typing decides. Blocking a write is a decision, and this package does not make decisions.

ENFORCES: memory/rules/which-repositories-this-project-covers.md
"""
import os
import pathlib
import re

# From the rule's own enumeration. Each changes machine or account state and names no path that a
# path test could catch.
_OS_MUTATORS = (
    (r"\bdefaults\s+(?:write|delete|rename|import)\b", "defaults write — an app's preferences are "
     "user data with a schema only that app knows"),
    (r"\bPlistBuddy\b.*-c\s*[\"']?(?:Set|Add|Delete|Merge)", "PlistBuddy writing a plist"),
    (r"\blaunchctl\s+(?:load|unload|bootstrap|bootout|enable|disable|setenv|remove)\b",
     "launchctl changing what the machine runs"),
    (r"\b(?:systemsetup|csrutil|dscl|nvram|scutil)\b", "a system-configuration command"),
    (r"\bpmset\s+(?!-g\b)", "pmset changing power behaviour"),
    (r"\bkillall\b|\bosascript\b.*\bquit\b", "quitting an application the owner may be using"),
    (r"\bchsh\b|\bdseditgroup\b|\bvisudo\b", "an account or privilege change"),
)
# Verbs that write to whatever path follows them. The path itself decides, not the verb.
# 🐛 [2026-09-23] `sed 's/^/    /'` raised "this writes to `/`" — plain `sed` writes nothing, and
# the `/` came out of its SCRIPT. Only `sed -i` edits a file, and a one-character path is never a
# target anybody typed.
_WRITERS = re.compile(
    r"(?:^|[|;&]\s*)(?:sudo\s+)?(rm|mv|cp|tee|install|truncate|chmod|chown|ln|mkdir|touch"
    r"|sed\s+-i)\b([^|;&]*)", re.MULTILINE)
_REDIRECT_OP = re.compile(r"(?<![0-9<>])>{1,2}(?![>&])")
# 🐛 [2026-09-23, second correction] `sed -i '' '0,/^import /s//from pathlib import Path/'`
# raised "this writes to `/s//from`" — the slashes came out of the sed SCRIPT, which is quoted.
# A quoted argument is a pattern, a message or a script; the path a writer touches is unquoted.
_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")
_PATHISH = re.compile(r"(?:^|(?<=\s))(?:~|/)[^\s'\"]*")


def _scratch_roots():
    """Directories whose whole purpose is to be thrown away, plus the agent's own state."""
    out = []
    for var in ("TMPDIR", "TMP", "CLAUDE_CONFIG_DIR", "CLAUDE_PROJECT_DIR"):
        v = os.environ.get(var)
        if v:
            out.append(pathlib.Path(v))
    out += [pathlib.Path("/tmp"), pathlib.Path("/private/tmp"), pathlib.Path("/var/folders"),
            pathlib.Path.home() / ".claude"]
    return out


def _inside(path, root):
    try:
        pathlib.Path(path).resolve().relative_to(pathlib.Path(root).resolve())
        return True
    except Exception:              # noqa: BLE001 — not relative, or unresolvable
        return False


def ours(path, root):
    """True when writing `path` is ordinary work: inside the checkout, or scratch."""
    if root and _inside(path, root):
        return True
    return any(_inside(path, s) for s in _scratch_roots())


def _outside_targets(command, root):
    """Every path this command looks like it will WRITE that is not ours."""
    seen, out = set(), []
    candidates = []
    for m in _WRITERS.finditer(command):
        candidates += _PATHISH.findall(_QUOTED.sub(" ", m.group(2)))
    # 🐛 A redirect INSIDE a quoted string is text, not a redirect: `echo 'hi > /etc/passwd'`
    # writes nothing. Quoted regions are masked to spaces so offsets survive, the operator is found
    # in the masked copy, and the target is then read from the ORIGINAL — because a quoted PATH,
    # `echo x > "/etc/hosts"`, is a real write and must still be seen.
    masked = _QUOTED.sub(lambda m: " " * len(m.group(0)), command)
    for m in _REDIRECT_OP.finditer(masked):
        # 🐛 The masked copy is searched for the OPERATOR only: a quoted target is spaces there, so
        # a pattern that also demands a target finds nothing and `echo x > "/etc/hosts"` goes
        # unseen. The target is then taken from the original, quotes and all.
        raw = re.sub(r"^>{1,2}\s*", "", command[m.start():]).split()
        if raw:
            candidates.append(raw[0].strip("'\""))
    for raw in candidates:
        p = os.path.expanduser(raw.strip().strip("'\""))
        if not p.startswith(("/", "~")) or len(p) < 2 or p in seen:
            continue
        seen.add(p)
        if not ours(p, root):
            out.append(p)
    return out


def advice(tool, tool_input, root):
    """One notice, or "". Silent for every ordinary edit, which is nearly all of them."""
    inp = tool_input if isinstance(tool_input, dict) else {}
    if tool in ("Edit", "Write", "NotebookEdit"):
        target = inp.get("file_path") or inp.get("path") or ""
        if target and not ours(target, root):
            return ("chamnan: 🔴 `%s` is OUTSIDE this checkout. Outside it the rule is read, "
                    "measure, report — a wrong line here is not a revert, it is the owner's "
                    "machine. Nothing is blocked." % target)
        return ""
    if tool != "Bash":
        return ""
    import cmdtext
    # 🐛 [2026-09-23] Fired on a heredoc that was WRITING A TEST about `defaults write`. Only the
    # unambiguous commentary is dropped — a commit message and a `#` comment. Heredocs STAY: one
    # fed to `python3 -` or `bash -s` is executed, and hiding it would blind the rule that matters
    # most. For this guard a false positive costs a sentence; a false negative cost the owner data.
    command = cmdtext.without_prose(inp.get("command") or "", drop_heredoc=False)
    if not command:
        return ""
    for pattern, why in _OS_MUTATORS:
        if re.search(pattern, command):
            return ("chamnan: 🔴 this is %s. Outside this checkout the rule is read, measure, "
                    "report, and hand the finding over — a preference file has no version history. "
                    "Nothing is blocked." % why)
    outside = _outside_targets(command, root)
    if outside:
        return ("chamnan: 🔴 this writes to %s, outside this checkout. Read, measure and report "
                "instead; a write out there is the owner's machine, not a revert. Nothing is "
                "blocked." % ", ".join("`%s`" % p for p in outside[:3]))
    return ""
