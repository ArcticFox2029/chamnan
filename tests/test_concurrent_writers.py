#!/usr/bin/env python3
"""Four shared stores, attacked with real concurrent processes rather than a simulation.

All four lost data silently and permanently, and all four were found by measuring rather than by
reading: `tools/index.json`'s run counters lost 53% of 400 increments across 8 processes,
`commands.jsonl` lost 55% of 240 freshly appended signatures when its periodic trim raced the
appends, `logs/edits.jsonl` (the co-edit ledger) lost up to 63% of 240 concurrent edits to its
own unlocked trim, and `logs/scratch.jsonl` (written straight from the PostToolUse hook, not
through a lib/ helper) lost entries to a full read-modify-write on every qualifying call, no lock
at all. None corrupted a file or raised — the numbers were simply wrong afterwards, forever,
because none of the four recompute themselves from scratch on the next read.

Kept out of run_tests.py because it spawns processes and takes seconds; run_tests.py discovers and
runs it like any other file.
"""
import datetime
import json
import os
import pathlib
import subprocess
import time
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


def _coedit_worker(wsdir, tag, n):
    sys.path.insert(0, LIB)
    import coedit
    # MAX_LINES kept well above every entry this race will ever write (200 seed + up to a few
    # hundred worker entries), so a correct run keeps ALL of them -- an entry missing afterwards is
    # a lost update, not the trim doing its designed job of dropping old ones. TRIM_AT is set just
    # above the seed so the trim's rewrite path fires on nearly every record() call.
    coedit.MAX_LINES = 2000
    coedit.TRIM_AT = 205
    for i in range(n):
        coedit.record(pathlib.Path(wsdir), f"{tag}-{i}.py")


def _scratch_hook_worker(fixture_root, hook_path, idx):
    """One real subprocess invocation of the PostToolUse hook, piping a synthetic Write-tool
    payload on stdin -- the actual entry point, not a call into a lib/ function, because the
    unlocked read-modify-write this races lives directly in hooks/chamnan_scratch_watch.py."""
    import os
    content = "\n".join([
        f"# worker {idx} unique scratch script marker alpha{idx}",
        f"def worker_function_{idx}(argument_one, argument_two):",
        f"    result_value_{idx} = argument_one + argument_two",
        f"    return result_value_{idx}",
    ])
    payload = json.dumps({
        "tool_name": "Write",
        "tool_input": {"file_path": f"/tmp/scratch_worker_{idx}.py", "content": content},
    })
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(fixture_root))
    subprocess.run([sys.executable, str(hook_path)], input=payload, text=True,
                    capture_output=True, env=env, timeout=30)


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

    # --- the co-edit ledger -------------------------------------------------------------------
    # _trim() is a read-modify-write guarded with atomic_write_text but (until this fix) with no
    # ws.exclusive() lock around the read+decide+write -- the same shape workflows.record()'s trim
    # had before its own fix. record() itself now takes the lock for the WHOLE append+trim, the
    # same pattern tools_index.record_call already uses, because a lock only around the trim was
    # not enough: a concurrent unlocked append can still hold a descriptor to the inode `_trim`'s
    # os.replace() just swapped out from under it.
    wsdir = pathlib.Path(tempfile.mkdtemp())
    (wsdir / "logs").mkdir(parents=True)
    edits_log = wsdir / "logs" / "edits.jsonl"
    edits_log.write_text(
        "\n".join(json.dumps({"at": 0, "fp": f"seed-{i}.py"}) for i in range(200)) + "\n",
        encoding="utf-8")
    n_per_worker, n_workers = 40, 6
    procs = [Process(target=_coedit_worker, args=(str(wsdir), f"w{k}", n_per_worker))
             for k in range(n_workers)]
    [p.start() for p in procs]
    [p.join() for p in procs]
    edits_text = edits_log.read_text(encoding="utf-8", errors="replace")
    edits_lines = [ln for ln in edits_text.splitlines() if ln.strip()]
    edits_recs = [json.loads(ln) for ln in edits_lines]
    edits_present = {r.get("fp") for r in edits_recs}
    edits_wanted = {f"w{k}-{i}.py" for k in range(n_workers) for i in range(n_per_worker)}
    check(f"A TRIM RACING edits.jsonl APPENDS LOSES NONE OF THEM "
          f"({len(edits_wanted & edits_present)}/{len(edits_wanted)})",
          not (edits_wanted - edits_present))
    check("...and edits.jsonl is still valid JSON Lines throughout",
          len(edits_recs) == len(edits_lines))

    # --- the scratch-script fingerprint log --------------------------------------------------
    # Written directly from hooks/chamnan_scratch_watch.py's main(), not through a lib/ helper --
    # a full read-modify-write on every qualifying Write/Edit PostToolUse call, unlocked until
    # this fix. Raced as real subprocess hook invocations, the actual entry point, rather than a
    # call into a shared function.
    fixture = pathlib.Path(tempfile.mkdtemp())
    (fixture / ".chamnan" / "logs").mkdir(parents=True)
    (fixture / ".git").mkdir()          # find_root()/hook_root() need a VCS marker or workspace
    hook_path = ROOT / "hooks" / "chamnan_scratch_watch.py"
    # 🐛 The volume version of this check could not be made to fail reliably, and two rounds of
    # trying is enough to say so. It ran 40 workers and 40 never collided; raised to 150 it failed
    # 3 runs in 5 against the unfixed hook; raised to 300 it failed 1 in 5, because more processes
    # spread FURTHER apart rather than closer. A check that catches a regression three times in
    # five is one that ships it the other two.
    #
    # Asked deterministically instead, of the property that actually matters: while another writer
    # holds the lock on scratch.jsonl, a hook must not write. That is the whole content of "no
    # concurrent writer can interleave", it needs no timing luck, and it fails immediately against
    # a hook that does a read-modify-write without taking the lock -- which is what the unfixed one
    # did. LOCK_TIMEOUT is 2.0s, so the hook blocks for that long and then proceeds; the assertion
    # is about what it did WHILE the lock was held.
    scratch_log_path = fixture / ".chamnan" / "logs" / "scratch.jsonl"
    scratch_log_path.parent.mkdir(parents=True, exist_ok=True)
    scratch_log_path.write_text("", encoding="utf-8")

    def _hook_payload(idx):
        content = "\n".join([
            f"# worker {idx} unique scratch script marker alpha{idx}",
            f"def worker_function_{idx}(argument_one, argument_two):",
            f"    result_value_{idx} = argument_one + argument_two",
            f"    return result_value_{idx}",
        ])
        return json.dumps({"tool_name": "Write",
                           "tool_input": {"file_path": f"/tmp/scratch_worker_{idx}.py",
                                          "content": content}})

    def _launch_hook(idx):
        proc = subprocess.Popen(
            [sys.executable, str(hook_path)], stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True,
            env=dict(os.environ, CLAUDE_PROJECT_DIR=str(fixture)))
        proc.stdin.write(_hook_payload(idx))
        proc.stdin.close()
        return proc

    sys.path.insert(0, str(ROOT / "lib"))
    import workspace as _ws_probe
    # Two signals, and the second is why this is not a timing check. A fixed hook BLOCKS on the
    # lock for LOCK_TIMEOUT (2.0s); an unfixed one does its work and exits in well under a second.
    # So "did it finish while the lock was held" separates them by roughly a second of margin,
    # where "had it written yet after 1.0s" raced the hook's own interpreter startup and passed
    # 1 run in 5 against the unfixed hook.
    _deadline = 1.5                              # inside LOCK_TIMEOUT, past any plausible startup
    with _ws_probe.exclusive(scratch_log_path) as _held:
        wrote_while_locked = exited_while_locked = None
        if _held:
            blocked_proc = _launch_hook(1)
            _stop = time.time() + _deadline
            while time.time() < _stop and blocked_proc.poll() is None:
                time.sleep(0.02)
            exited_while_locked = blocked_proc.poll() is not None
            wrote_while_locked = scratch_log_path.read_text(encoding="utf-8").strip() != ""
    if _held:
        blocked_proc.wait(timeout=30)
    check("the test could take the lock at all -- without it the checks below prove nothing", _held)
    check("A HOOK WAITS FOR THE LOCK RATHER THAN FINISHING WHILE ANOTHER WRITER HOLDS IT",
          exited_while_locked is False)
    check("...and writes nothing to scratch.jsonl while it is held", wrote_while_locked is False)

    # And it does write once the lock is gone, or "never writes" would pass this too.
    _launch_hook(2).wait(timeout=30)
    check("...and it does write once the lock is released",
          scratch_log_path.read_text(encoding="utf-8").strip() != "")

    n_hooks = 60
    procs = [_launch_hook(i) for i in range(1, n_hooks + 1)]
    [p.wait(timeout=60) for p in procs]
    scratch_log = fixture / ".chamnan" / "logs" / "scratch.jsonl"
    scratch_lines = ([ln for ln in scratch_log.read_text(encoding="utf-8").splitlines() if ln.strip()]
                      if scratch_log.is_file() else [])
    scratch_recs = [json.loads(ln) for ln in scratch_lines]
    scratch_files = {r.get("file") for r in scratch_recs}
    scratch_wanted = {f"/tmp/scratch_worker_{i}.py" for i in range(1, n_hooks + 1)}
    check(f"{n_hooks} CONCURRENT HOOK INVOCATIONS LOSE NO scratch.jsonl ENTRY "
          f"({len(scratch_wanted & scratch_files)}/{n_hooks})",
          not (scratch_wanted - scratch_files))
    check("...and scratch.jsonl is still valid JSON Lines throughout",
          len(scratch_recs) == len(scratch_lines))

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
