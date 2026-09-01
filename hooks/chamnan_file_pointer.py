#!/usr/bin/env python3
"""PreToolUse hook — when a file is opened, say what this repository already records about it.

The measurement behind this is in lib/pointer.py: every query command in the plugin except
`chamnan-map` was run zero to one times in ten days, in the repository they were written for. The
conclusion drawn was that the CLI is the wrong surface for knowledge a model needs *before* an
edit, not that the knowledge is unwanted. This is the smaller, safer half of that change — the
half that needs no prompt parsing, no language handling and no per-turn latency, because it fires
on Read/Edit/Write, which are already slow.

Rules it holds itself to, all four of them for the same reason — a hook that fires many times per
session is judged by its worst moment, not its best:

  * **Silent when it has nothing.** No "no related knowledge found" line, ever.
  * **Once per file per session.** The pointer is a fact about the file, not about the edit.
  * **Never about chamnan's own files.** Reading `.chamnan/memory/x.md` and being told about
    `.chamnan/memory/x.md` is noise.
  * **Bounded in time.** MAX_MS is checked between the cheap half and the expensive half, so the
    impact lookup — which parses a section of a MAP.md that is 320k characters on the development
    repository — is skipped rather than paid for when the corpus scan already ran long.

It never blocks and never rewrites the tool input. The most it can do is print.
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
import impact as impact_mod  # noqa: E402
import pointer  # noqa: E402
import workspace as ws  # noqa: E402

TOOLS = {"Read", "Edit", "Write", "NotebookEdit"}
MAX_MS = 120.0          # after the corpus scan; past this the impact lookup is skipped
MAP_MAX_BYTES = 4_000_000


def main():
    started = time.time()
    try:
        payload = json.load(sys.stdin)
        # A payload that parses but is not an object -- JSON `null`, or an array -- used to
        # crash on .get() with an AttributeError, on every matching call, all session.
        payload = payload if isinstance(payload, dict) else {}
    except Exception:
        return 0
    if (payload.get("tool_name") or "") not in TOOLS:
        return 0

    root = ws.hook_root(payload)
    wsdir = ws.workspace(root)
    if not wsdir.is_dir() or not ws.load_config(root).get("pointer", True):
        return 0

    raw = (payload.get("tool_input") or {}).get("file_path") or ""
    if not raw:
        return 0
    try:
        target = Path(raw).resolve()
        rel = target.relative_to(Path(root).resolve()).as_posix()
    except (OSError, ValueError):
        return 0            # outside the repository — nothing here can be about it
    if rel.startswith(wsdir.name + "/"):
        return 0

    session_id = payload.get("session_id") or ""
    if pointer.already_pointed(wsdir, session_id, rel):
        return 0

    hits = pointer.related(wsdir, rel)

    edges = None
    if (time.time() - started) * 1000 < MAX_MS:
        mp = wsdir / "MAP.md"
        try:
            if mp.is_file() and mp.stat().st_size <= MAP_MAX_BYTES:
                _, edges = impact_mod.lookup(mp.read_text(encoding="utf-8", errors="replace"), rel)
        except (OSError, ValueError):
            edges = None

    block = pointer.render(rel, hits, edges)
    # Marked as seen even when nothing matched. Otherwise a file with no knowledge behind it pays
    # the whole scan again on every one of the session's edits to it, which is the case where the
    # cost is least deserved.
    pointer.mark_pointed(wsdir, session_id, rel)
    if not block:
        return 0

    pointer.note(wsdir, session_id, rel, hits, (time.time() - started) * 1000)
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "additionalContext": block}}))
    return 0


def _never_fail_the_session():
    """`main()`, but a hook that hits something it cannot read exits 0 in silence rather than
    exiting 1 with a traceback.

    A hook's stderr never reaches the transcript, so a crash here is invisible: the session simply
    starts without whatever this hook contributes, and nothing says why. Measured with a
    `chmod 000` on `.chamnan/logs` — the ordinary result of a container or CI run touching the
    workspace as root — four of the five hooks died this way. Silence is the correct failure for a
    hook that only writes; `chamnan_session_start.py` does more than this, because it has something
    partial worth emitting.
    """
    try:
        return main()
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(_never_fail_the_session())
