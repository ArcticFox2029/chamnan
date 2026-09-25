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
# 🐛 [2026-09-06] `redact` and `impact` are imported where they are used rather than on every
# Read: `impact` is only reached when a map exists, and `redact` only on the one path that actually
# emits text. `redact` costs 21.7 ms to import because it compiles 45 regexes doing it (R7 agent
# 2). `pointer` stays here -- it is used immediately after the early returns, on the ordinary path.
import pointer  # noqa: E402
import workspace as ws  # noqa: E402

TOOLS = {"Read", "Edit", "Write", "NotebookEdit"}
# 🎯 [R3.11.5, 2026-09-16] A search is not an open, and the two artefacts this plugin exists for are
# never opened: `MAP.md`'s own header says never to read it whole, and `STATE.md` is scanned for the
# section that applies. Both therefore registered ZERO opens, and `lib/fit.py` carries what that
# cost — ranked on opens alone, the architecture index and the work-in-flight section were the first
# two things dropped from the block.
#
# Separate from TOOLS on purpose: a Grep never renders a pointer, never runs the impact lookup, and
# returns after one cheap comparison. Everything below the pointer machinery stays untouched.
QUERY_TOOLS = {"Grep", "Glob", "Search"}
MAX_MS = 120.0          # after the corpus scan; past this the impact lookup is skipped
MAP_MAX_BYTES = 4_000_000


def _note_query(payload):
    """Record a SEARCH of one of chamnan's own artefacts. Cheap, and never renders anything.

    Only fires when the search is actually pointed at the workspace — a repository-wide grep says
    nothing about whether chamnan's own files were wanted, and counting it would make every session
    look like a reader of everything.
    """
    root = ws.hook_root(payload)
    wsdir = ws.workspace(root)
    if wsdir is None:
        return 0
    inp = payload.get("tool_input") or {}
    target = str(inp.get("path") or inp.get("file_path") or inp.get("glob") or "")
    if not target or wsdir.name not in target:
        return 0
    rel = target.split(wsdir.name + "/", 1)[-1] if wsdir.name + "/" in target else target
    try:
        # The pattern is user text and can carry anything at all, so it goes through the same
        # redactor as every other string this package writes down.
        import redact
        _q = redact.scrub(str(inp.get("pattern") or ""))
    except Exception:                       # noqa: BLE001 — accounting must never break a tool call
        _q = ""
    try:
        pointer.note_query(wsdir, payload.get("session_id") or "", rel, _q,
                           actor=ws.actor(payload))
    except Exception:                       # noqa: BLE001
        pass
    return 0


def main():
    started = time.time()
    try:
        payload = ws.read_hook_payload()
        # A payload that parses but is not an object -- JSON `null`, or an array -- used to
        # crash on .get() with an AttributeError, on every matching call, all session.
        payload = payload if isinstance(payload, dict) else {}
    except Exception:
        return 0
    _tool = payload.get("tool_name") or ""
    if _tool in QUERY_TOOLS:
        return _note_query(payload)
    if _tool not in TOOLS:
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
        # Rendering stays suppressed -- pointing at chamnan's own files while chamnan is the thing
        # talking is noise. But a read of one of its own STORE files (skills/memory/threads) is
        # exactly the event the pointer funnel needs and could not see: every other reader of this
        # file returned here before recording anything, so a session that opened what it was
        # pointed at looked identical to one that never did. See pointer.note_opened.
        inner = rel[len(wsdir.name) + 1:]
        if inner.split("/", 1)[0] in ("skills", "memory", "threads"):
            pointer.note_opened(wsdir, payload.get("session_id") or "", inner,
                                actor=ws.actor(payload))
        return 0

    session_id = payload.get("session_id") or ""
    if pointer.already_pointed(wsdir, session_id, rel):
        return 0

    hits = pointer.related(wsdir, rel)

    edges = None
    import impact as impact_mod  # deferred; see the import block
    if (time.time() - started) * 1000 < MAX_MS:
        mp = wsdir / "MAP.md"
        try:
            if mp.is_file() and mp.stat().st_size <= MAP_MAX_BYTES:
                _, edges = impact_mod.lookup(mp.read_text(encoding="utf-8-sig", errors="replace"), rel)
        except (OSError, ValueError):
            edges = None

    block = pointer.render(rel, hits, edges)

    # What this repository has learned about the file WITHOUT anyone recording anything: which file
    # gets edited right after it. Appended rather than folded into `render`, so a file with no
    # recorded knowledge at all can still say something useful — which on a repository where nobody
    # runs the write commands is every file.
    #
    # Last, and only when the budget above was not already spent: it is the cheapest of the three
    # lookups but it is also the weakest claim, and the impact edges deserve the room first.
    if (time.time() - started) * 1000 < MAX_MS:
        try:
            import coedit
            nxt = coedit.line(wsdir, rel)
        except Exception:
            nxt = ""
        if nxt:
            block = (block + "\n" + nxt) if block else nxt
    # Marked as seen even when nothing matched. Otherwise a file with no knowledge behind it pays
    # the whole scan again on every one of the session's edits to it, which is the case where the
    # cost is least deserved.
    pointer.mark_pointed(wsdir, session_id, rel)
    if not block:
        return 0

    # "look" or "change": the distinction a second reader asked for, taken from the tool the host
    # actually used rather than from anything this code decides. A field derived from a guess
    # would be worse than no field, because a later reader cannot tell the two apart.
    pointer.note(wsdir, session_id, rel, hits, (time.time() - started) * 1000,
                 actor=ws.actor(payload),
                 why="look" if _tool == "Read" else "change")
    # 🐛 Every title in this block is the first line of a committed file, and none of it went
    # through the redactor. That made this the cheapest leak in the plugin to trigger: no command
    # to run and nothing to opt into, just an ordinary `Read` of any file a stored lesson happens
    # to mention. Reproduced with an AWS key in a lesson's own heading, which arrived in
    # `additionalContext` on the first Read of the file that lesson names.
    #
    # Scrubbed here rather than in `pointer.render`, because this is the one place the text leaves
    # the process, and it also covers the `coedit.line` tail appended above it.
    # 🐛 `scrub` removes credentials and has never removed CONTROL characters. `json.dumps`
    # escapes them, so the raw-stdout sweep that guards every other reader sees nothing --
    # and the harness decodes them straight back into the model's context. See
    # `redact.for_a_terminal`.
    import redact  # deferred; see the import block
    # One notice per tool call: a Read reaches this hook AND chamnan_bulk_read_notice, an Edit
    # reaches this one AND chamnan_skill_pointer, and neither could see the other. Fails open.
    try:
        import turn
        if not turn.claim(payload, wsdir):
            return 0
    except Exception:
        pass
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": redact.for_a_terminal(redact.scrub(block))}}))
    return 0


if __name__ == "__main__":
    sys.exit(ws.never_fail(main))
