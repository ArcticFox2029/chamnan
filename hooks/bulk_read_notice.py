#!/usr/bin/env python3
"""PreToolUse hook — say when a file about to be read is bulk with no reading value.

This is the honest half of "filter the file before it enters the context". The other half is not
possible: hooks cannot rewrite what a tool returns. PostToolUse exposes only `additionalContext`
and `systemMessage`, and PreToolUse can change a tool's INPUT but never its OUTPUT — so nothing in
the plugin system can strip a file's comments or blank lines on the way in. Any design that assumes
it can is describing a feature Claude Code does not have.

What is possible is to notice, before the read happens, that the file is a lock file, a minified
bundle, or a build artefact, and say so. It does NOT block: a lock file is exactly the right thing
to read when diagnosing a dependency conflict, and a plugin that decides otherwise is wrong at the
worst moment. It states the size and suggests grep, and the decision stays where it belongs.

The comment-stripping idea is also rejected on its own terms, not just on feasibility: comments are
the highest-value tokens in a file for a reader trying to understand intent, and this plugin's whole
index is built out of them. Saving tokens by deleting them would be sawing off the branch.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
import workspace as ws  # noqa: E402

LOCKFILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "cargo.lock", "poetry.lock",
    "composer.lock", "gemfile.lock", "go.sum", "pipfile.lock", "flake.lock", "bun.lockb",
}
GENERATED = re.compile(r"\.(min\.(js|css)|bundle\.js|map|pb\.go|generated\.\w+)$", re.I)
GENERATED_DIRS = ("dist", "build", "node_modules", "vendor", "__generated__", ".next", "target")
BIG_BYTES = 200_000        # ~55k tokens; worth a word before it lands in the context
HUGE_BYTES = 1_000_000


def reason_for(path):
    name = path.name.lower()
    if name in LOCKFILES:
        return "a dependency lock file — machine-written, and almost never read for meaning"
    if GENERATED.search(name):
        return "generated or minified output, not source"
    if any(part in GENERATED_DIRS for part in path.parts):
        return "inside a build/vendor directory"
    return ""


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if (payload.get("tool_name") or "") != "Read":
        return 0
    root = ws.find_root()
    if not ws.workspace(root).is_dir() or not ws.load_config(root).get("warn_on_bulk_reads", True):
        return 0

    raw = (payload.get("tool_input") or {}).get("file_path") or ""
    if not raw:
        return 0
    path = Path(raw)
    try:
        size = path.stat().st_size
    except OSError:
        return 0

    why = reason_for(path)
    if not why and size < BIG_BYTES:
        return 0
    # A read that already has a line range is a targeted read; the point has been taken.
    inp = payload.get("tool_input") or {}
    if inp.get("offset") or inp.get("limit"):
        return 0

    est = size / 3.6
    if why:
        note = (f"chamnan: `{path.name}` is {why} (~{est:,.0f} tokens). "
                f"If you need one fact from it, grep instead of reading it whole. "
                f"Reading it is still the right call when the file itself is what you are debugging.")
    else:
        scale = "very large" if size >= HUGE_BYTES else "large"
        note = (f"chamnan: `{path.name}` is {scale} (~{est:,.0f} tokens), and every later turn in "
                f"this session carries it. A grep or a line range costs a fraction of that.")
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "additionalContext": note}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
