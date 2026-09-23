#!/usr/bin/env python3
"""Scan what is staged, at the moment somebody commits it.

WRITES: logs/commit_guard.jsonl per logs/commands.jsonl

🐛 [2026-09-23] `chamnan-guard` scans a staged diff for anything shaped like a secret. It works —
fed a staged AWS key it names the file and the line, and deliberately prints none of the matched
text, because reading a secret out loud copies it into the terminal and the transcript. It had
been installed for thirteen days and had **never once run**, against 294 `git commit` calls
recorded in the same window.

🔴 The whole process was missing, not one piece of it: no hook called the command, its own
docstring said `--strict` was "for a hook somebody opted into", and there was no config key to
opt in WITH. A capability nobody can reach is not a capability — it is the same shape as a store
nothing reads, which this workspace spent the day asserting against.

**It warns and never blocks.** That is the command's own documented default and it is the right
one here: the field's practice (R4.3, 2026-09-23) is that a tool may act automatically on a
derived artefact but a developer's own commit is theirs. `chamnan-guard --strict` still exists
for anybody who wants the harder version in a pre-commit hook they installed themselves.
"""
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
import workspace as ws                                            # noqa: E402

# 🐛 [2026-09-23] (self-measured) The first version matched `git` anywhere in the command, so `echo git commit`
# fired it. That is the mention-is-not-use error this workspace has recorded six times, made here
# in a function written to close another instance of it — and `lib/canonical.py` already carries
# the fix, in a comment dated the same day: a name is an invocation only in COMMAND POSITION, the
# first word of a segment or straight after an interpreter. Reused rather than rewritten, because
# a fourth copy of this idea is how the copies drift apart.
_INTERPRETERS = {"nohup", "caffeinate", "exec", "command", "time", "env", "xargs", "sudo"}
_SEGMENT = re.compile(r"\s*(?:\|\||&&|[;|&\n])\s*")


def _is_commit(command):
    """True when this command line actually RUNS `git commit`, not merely contains the words."""
    for segment in _SEGMENT.split(command):
        try:
            words = shlex.split(segment)
        except ValueError:            # unbalanced quotes — fall back to whitespace
            words = segment.split()
        while words and (Path(words[0]).name in _INTERPRETERS or "=" in words[0]):
            words = words[1:]
        if not words or Path(words[0]).name != "git":
            continue
        # The subcommand is the first word after `git` that is not a flag and not the value of
        # one: `git -C <dir> commit` is the shape this repository uses constantly.
        rest, skip = words[1:], False
        for w in rest:
            if skip:
                skip = False
                continue
            if w in ("-C", "-c", "--git-dir", "--work-tree", "--namespace"):
                skip = True
                continue
            if w.startswith("-"):
                continue
            return w == "commit"
    return False


def main():
    try:
        payload = json.load(sys.stdin)
        payload = payload if isinstance(payload, dict) else {}
    except (ValueError, OSError):
        return 0
    if (payload.get("tool_name") or "") != "Bash":
        return 0
    command = str((payload.get("tool_input") or {}).get("command") or "")
    if not _is_commit(command):
        return 0
    root = ws.hook_root(payload)
    if root is None or not ws.workspace(root).is_dir():
        return 0
    if not ws.load_config(root).get("commit_guard", True):
        return 0
    guard = Path(__file__).resolve().parent.parent / "bin" / "chamnan-guard"
    if not guard.is_file():
        return 0
    try:
        # 🔴 Never fails the commit and never blocks it: a non-zero exit here, or a timeout, or a
        # guard that is not there, all mean the same thing — say nothing and let the work happen.
        # \U0001F41B [2026-09-23] Read from stdout alone at first, and `chamnan-guard` writes its
        # warning to STDERR — so the hook ran, the guard found the staged key, and nothing was
        # shown. A false success made while wiring up the fix for false successes. Both streams
        # are read, because which one a warning uses is the guard's choice, not this hook's.
        _r = subprocess.run([sys.executable, str(guard)], cwd=str(root), capture_output=True,
                            text=True, timeout=20, env=dict(os.environ))
        out = ((_r.stdout or "") + (_r.stderr or "")).strip()
    except Exception:                                             # noqa: BLE001
        return 0
    if out:
        print(out, file=sys.stderr)
        try:
            ws.append_jsonl(root, "logs/commit_guard.jsonl",
                            {"at": ws.now_iso() if hasattr(ws, "now_iso") else "",
                             "flagged": True}, 500)
        except Exception:                                         # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    sys.exit(ws.never_fail(main))
