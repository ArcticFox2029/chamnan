#!/usr/bin/env python3
"""SessionEnd hook — one quiet digest of what repeated today, left for the next session.

The inline nudge in scratch_watch.py speaks once, at the moment the third copy of a script is
written, because that is when the file still exists and promoting it costs one command. This is the
other half: at the end of the session, everything that repeated and was never kept gets summarised
in one place, so a pattern that built up across the day is visible even if the moment was missed.

Deliberately not a second chance to nag. It writes at most a handful of lines, session_start.py
shows them exactly once and deletes the file, and nothing is written at all when there is nothing
to say.
"""
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
import workspace as ws  # noqa: E402

SIMILAR = 0.55
WINDOW_HOURS = 24
MIN_REPEATS = 2
MAX_LISTED = 4
# Read, shown once and deleted by session_start.py on the next session in this repository.
DIGEST_NAME = "repeat_digest.json"


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    root = ws.hook_root(payload)
    wsdir = ws.workspace(root)
    if not wsdir.is_dir() or not ws.enabled("promote", root):
        return 0
    log = wsdir / "logs" / "scratch.jsonl"
    if not log.is_file():
        return 0

    cutoff = datetime.now().astimezone() - timedelta(hours=WINDOW_HOURS)
    recent = []
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rec = json.loads(line)
            when = datetime.fromisoformat(rec["at"])
        except Exception:
            continue
        # Adopted, not discarded. A naive timestamp — from a hand edit, or a writer that
        # predates the .astimezone() convention — parses fine and then raises TypeError on
        # the comparison below, uncaught, killing the whole hook over one line. Assuming
        # local time is what the record almost certainly meant; dropping it would silently
        # lose real work from the digest, which is the thing this hook exists to produce.
        if when.tzinfo is None:
            when = when.astimezone()
        if when >= cutoff:
            recent.append((set(rec.get("fp", [])), rec.get("head", "")))

    # Single-pass clustering: each script joins the first family it is close enough to. Good enough
    # for a digest — the alternative is a clustering algorithm nobody will tune.
    families = []
    for fp, head in recent:
        for fam in families:
            if jaccard(fp, fam["fp"]) >= SIMILAR:
                fam["n"] += 1
                break
        else:
            families.append({"fp": fp, "n": 1, "head": head})

    repeated = sorted((f for f in families if f["n"] > MIN_REPEATS), key=lambda f: -f["n"])
    if not repeated:
        return 0

    # Handed to the next session rather than printed. SessionEnd is not one of the four events
    # whose stdout Claude Code shows the model -- and by then the session it would be speaking to
    # is over anyway, so a `print()` here reached nobody at all. Writing the digest turns the same
    # finding into something SessionStart can say at the one moment it can still be acted on.
    digest = {
        "at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "lines": [f"{fam['n']}x  `{fam['head'][:70]}`" for fam in repeated[:MAX_LISTED]],
    }
    out = wsdir / "logs" / DIGEST_NAME
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(digest, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
