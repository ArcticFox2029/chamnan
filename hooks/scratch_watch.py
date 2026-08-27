#!/usr/bin/env python3
"""PostToolUse hook — notice when the same throwaway script keeps being rewritten.

A one-off script is fine. The waste is the analysis re-derived every few days: the same check,
thought up again from scratch, arriving slightly different each time. That is both tokens spent
twice and a check that cannot be trusted to compare runs.

This does not block anything and does not write files anywhere the user did not ask for. It watches
inline scripts, fingerprints them, and when a third near-identical one appears it says so once, then
gets out of the way. Suggesting is the whole job — deciding what deserves to be kept is the user's.

Similarity is a Jaccard overlap of long-ish word tokens. Deliberately crude: a fingerprint that
needed parsing would have to understand every language a user might write a scratch script in.
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
import workflows  # noqa: E402
import workspace as ws  # noqa: E402

HEREDOC = re.compile(r"<<-?\s*'?([A-Za-z_][A-Za-z0-9_]*)'?\s*\n(.*?)\n\1", re.S)
TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")
SIMILAR = 0.55        # Jaccard at or above this counts as "the same script again"
REPEAT_AT = 3         # say something on the third one, not the second
KEEP_ENTRIES = 300    # bounded log; this is a hint generator, not an archive
# Unique identifiers of four characters or more. A real five-line analysis script has about
# eight; 12 was tuned against long scripts and silently ignored exactly the short, repeated
# one-off that this hook exists to catch. Found by the test suite, not in use.
MIN_TOKENS = 8


def body_of(payload):
    name = payload.get("tool_name") or ""
    inp = payload.get("tool_input") or {}
    if name == "Bash":
        cmd = str(inp.get("command") or "")
        blocks = [m.group(2) for m in HEREDOC.finditer(cmd)]
        return max(blocks, key=len) if blocks else ""
    if name in ("Write", "Edit"):
        path = str(inp.get("file_path") or "")
        if "/tmp/" in path or "/scratch" in path:
            return str(inp.get("content") or inp.get("new_string") or "")
    return ""


def fingerprint(text):
    return set(t.lower() for t in TOKEN.findall(text))


SKIP_HEAD = re.compile(r"^\s*(#|//|/\*|\*|import\b|from\b|require\(|use\b|package\b|$)")


def headline(text):
    """The first line that says something. The literal first line is usually `import json`, which
    makes every digest entry look identical and tells the reader nothing about which script it was."""
    for line in text.strip().splitlines():
        if not SKIP_HEAD.match(line):
            return " ".join(line.split())[:80]
    return " ".join(text.strip().splitlines()[0].split())[:80] if text.strip() else ""


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def notice_workflow(payload, wsdir):
    """Record this command's signatures and speak if a sequence has just reached the threshold.

    Returns True when it said something, so the caller does not also fire the script-repeat hint.
    Two notices in one turn is how a useful nudge becomes noise.
    """
    if (payload.get("tool_name") or "") != "Bash":
        return False
    command = str((payload.get("tool_input") or {}).get("command") or "")
    sigs = workflows.signatures(command)
    if not sigs:
        return False
    # There is no exit code in a Bash tool_response -- only stdout, stderr and interrupted -- so
    # this is the one honest piece of evidence about whether the call went cleanly.
    interrupted = bool((payload.get("tool_response") or {}).get("interrupted"))

    log = wsdir / "logs" / "commands.jsonl"
    before = workflows.repeated(workflows.record(
        log, [], datetime.now().astimezone().isoformat(timespec="seconds")))
    history = workflows.record(
        log, sigs, datetime.now().astimezone().isoformat(timespec="seconds"),
        tool="Bash", interrupted=interrupted)
    found = workflows.repeated(history)
    if not found:
        return False
    sequence, count = found
    # Only the crossing speaks. If this exact sequence already qualified before this command, the
    # threshold was passed earlier and saying so again is repetition.
    if before and before[0] == sequence:
        return False
    print(workflows.describe(sequence, count))
    return True


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    root = ws.find_root()
    wsdir = ws.workspace(root)
    if not wsdir.is_dir() or not ws.enabled("promote", root):
        return 0

    # A plain Bash command carries no script body, so the path below ignores it entirely — and a
    # repeated SEQUENCE of them is the thing that leaves no file behind at all. Checked first, and
    # only one of the two ever speaks in a single turn.
    if notice_workflow(payload, wsdir):
        return 0

    text = body_of(payload)
    if not text.strip():
        return 0
    fp = fingerprint(text)
    if len(fp) < MIN_TOKENS:
        return 0

    tool_name = payload.get("tool_name") or ""
    file_path = str((payload.get("tool_input") or {}).get("file_path") or "")

    log = wsdir / "logs" / "scratch.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    prior = []
    if log.is_file():
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                prior.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    # A record with no `kind` predates this field and is a scratch fingerprint by construction --
    # nothing else was ever written here before now -- so missing reads as "scratch". Anything
    # tagged something else must not be treated as one, the same rule workflows._runs() applies to
    # commands.jsonl: a future record shape sharing this log must not silently join a comparison it
    # was not written for.
    matches = [p for p in prior
               if p.get("kind", "scratch") == "scratch" and jaccard(fp, set(p.get("fp", []))) >= SIMILAR]
    entry = {
        "at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "kind": "scratch",
        "tool": tool_name,
        "fp": sorted(fp)[:120],
        "head": headline(text),
    }
    if file_path:
        entry["file"] = file_path
    prior.append(entry)
    log.write_text("\n".join(json.dumps(p, ensure_ascii=False) for p in prior[-KEEP_ENTRIES:]) + "\n",
                   encoding="utf-8")

    # Only the exact threshold speaks. Firing on every later repeat would turn a useful nudge into
    # noise the user learns to scroll past.
    if len(matches) + 1 == REPEAT_AT:
        first = matches[0].get("at", "")[:10]
        print(f"chamnan: that is the {REPEAT_AT}rd near-identical scratch script since {first}. "
              f"If it is worth keeping, save it and run: "
              f"chamnan promote <file> <name> --desc \"what it checks\" — "
              f"then it is one command next time instead of writing it again.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
