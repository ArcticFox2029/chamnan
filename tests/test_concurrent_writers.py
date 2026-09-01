#!/usr/bin/env python3
"""Two shared stores, attacked with real concurrent processes rather than a simulation.

Both lost data silently and permanently, and both were found by measuring rather than by reading:
`tools/index.json`'s run counters lost 53% of 400 increments across 8 processes, and
`commands.jsonl` lost 55% of 240 freshly appended signatures when its periodic trim raced the
appends. Neither corrupted a file or raised — the numbers were simply wrong afterwards, forever,
because both are running totals that nothing recomputes.

Kept out of run_tests.py because it spawns processes and takes seconds; run_tests.py discovers and
runs it like any other file.
"""
import datetime
import json
import pathlib
import sys
import tempfile
from multiprocessing import Process

ROOT = pathlib.Path(__file__).resolve().parent.parent
LIB = str(ROOT / "lib")
sys.path.insert(0, LIB)

PASSED = 0
FAILED = []


def check(name, condition):
    global PASSED
    if condition:
        PASSED += 1
        print(f"[OK] {name}")
    else:
        FAILED.append(name)
        print(f"[FAIL] {name}")


def _tools_worker(root, n):
    sys.path.insert(0, LIB)
    import tools_index
    for _ in range(n):
        tools_index.record_call(pathlib.Path(root), "t.sh", False, False)


def _log_worker(path, tag, n):
    sys.path.insert(0, LIB)
    import workflows
    workflows.TRIM_SLACK = 1          # force the rewrite path on every call
    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    for i in range(n):
        workflows.record(pathlib.Path(path), [f"{tag}-{i}"], now)


if __name__ == "__main__":
    # --- the shared tool registry ----------------------------------------------------------
    # pointer.py met the same lost-update problem and answered it with one file per session, no
    # lock. That answer is unavailable here: this is a registry every session has to agree on.
    root = pathlib.Path(tempfile.mkdtemp())
    (root / ".chamnan" / "tools").mkdir(parents=True)
    (root / ".chamnan" / "tools" / "index.json").write_text(
        json.dumps([{"name": "t.sh", "desc": "x", "runs": 0}]), encoding="utf-8")
    procs = [Process(target=_tools_worker, args=(str(root), 50)) for _ in range(8)]
    [p.start() for p in procs]
    [p.join() for p in procs]
    runs = json.loads(
        (root / ".chamnan" / "tools" / "index.json").read_text(encoding="utf-8"))[0]["runs"]
    check(f"EVERY ONE OF 400 CONCURRENT INCREMENTS IS RECORDED (got {runs})", runs == 400)

    # --- the command log ---------------------------------------------------------------------
    # The append path is safe on its own; the periodic trim is a truncate-and-overwrite built from
    # a snapshot another process can have appended to since.
    log = pathlib.Path(tempfile.mkdtemp()) / "commands.jsonl"
    procs = [Process(target=_log_worker, args=(str(log), f"p{k}", 40)) for k in range(6)]
    [p.start() for p in procs]
    [p.join() for p in procs]
    on_disk = {json.loads(line)["sig"]
               for line in log.read_text(encoding="utf-8").splitlines() if line.strip()}
    wanted = {f"p{k}-{i}" for k in range(6) for i in range(40)}
    check(f"A TRIM RACING APPENDS DELETES NONE OF THEM ({len(wanted & on_disk)}/240)",
          not (wanted - on_disk))
    check("...and the log is still valid JSON Lines throughout",
          all(json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()
              if line.strip()))

    # --- the lock itself ---------------------------------------------------------------------
    import workspace as ws
    target = pathlib.Path(tempfile.mkdtemp()) / "x.json"
    with ws.exclusive(target) as held:
        check("the lock is acquired when nothing holds it", held is True)
        check("...and is visible on disk while held",
              pathlib.Path(str(target) + ".lock").exists())
    check("...and released afterwards", not pathlib.Path(str(target) + ".lock").exists())
    # A lock left behind by a killed process must not block forever.
    stale = pathlib.Path(str(target) + ".lock")
    stale.write_text("", encoding="utf-8")
    import os
    import time
    os.utime(stale, (time.time() - ws.LOCK_STALE - 5,) * 2)
    with ws.exclusive(target) as held:
        check("A LOCK LEFT BY A KILLED PROCESS IS BROKEN, NOT WAITED ON", held is True)

    total = PASSED + len(FAILED)
    print(f"\n{PASSED}/{total} checks passed")
    sys.exit(1 if FAILED else 0)
