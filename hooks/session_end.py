#!/usr/bin/env python3
"""SessionEnd hook — one quiet digest of what repeated today, and nothing else.

The inline nudge in scratch_watch.py speaks once, at the moment the third copy of a script is
written, because that is when the file still exists and promoting it costs one command. This is the
other half: at the end of the session, everything that repeated and was never kept gets summarised
in one place, so a pattern that built up across the day is visible even if the moment was missed.

Deliberately not a second chance to nag. It prints once, lists at most a handful, and says nothing
at all when there is nothing to say.
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


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def main():
    try:
        json.load(sys.stdin)
    except Exception:
        pass
    root = ws.find_root()
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
    print("## chamnan — repeated this session\n")
    for fam in repeated[:MAX_LISTED]:
        print(f"- {fam['n']}x  `{fam['head'][:70]}`")
    print("\nAnything here worth keeping: `chamnan-promote <file> <name> --desc \"...\"`. "
          "Next session it is one command instead of writing it again.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
