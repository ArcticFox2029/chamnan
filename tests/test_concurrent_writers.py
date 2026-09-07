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
from multiprocessing import Barrier, Process

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


def _tools_worker(root, n, timeout=None, report=None):
    sys.path.insert(0, LIB)
    import tools_index
    import workspace as ws
    if timeout is not None:
        ws.LOCK_TIMEOUT = timeout
    for _ in range(n):
        tools_index.record_call(pathlib.Path(root), "t.sh", False, False)
    # Each process carries its own tally home. A lost update reports a number, and a number cannot
    # say WHY the waiters left -- which is the whole question on a platform nobody here can attach
    # a debugger to.
    if report:
        pathlib.Path(report).write_text(json.dumps(ws.LOCK_GIVEUPS), encoding="utf-8")


def _why_they_left(root):
    """Sum the per-process tallies written by _tools_worker into one line."""
    total = {}
    for f in sorted(pathlib.Path(root).glob("giveups-*.json")):
        try:
            for k, v in json.loads(f.read_text(encoding="utf-8")).items():
                if isinstance(v, list):
                    total.setdefault(k, []).extend(v)
                else:
                    total[k] = total.get(k, 0) + v
        except (OSError, ValueError):
            pass
    if "errors" in total:
        total["errors"] = sorted(set(total["errors"]))[:6]
    return json.dumps(total, sort_keys=True)


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


def _milestone_worker(root, i, gate):
    sys.path.insert(0, LIB)
    import milestones
    gate.wait()
    milestones.append(pathlib.Path(root), f"## 2026-09-0{1 + i % 9} — milestone-{i}\n\n**Why:** m{i}\n")


def _pointer_worker(wsdir, session_id, i, gate):
    sys.path.insert(0, LIB)
    import pointer
    gate.wait()
    pointer.mark_pointed(pathlib.Path(wsdir), session_id, f"src/file-{i}.py")


def _firing_worker(root, hook_path, i, gate):
    sys.path.insert(0, LIB)
    sys.path.insert(0, str(pathlib.Path(hook_path).parent))
    import importlib.util
    spec = importlib.util.spec_from_file_location("sub_start", hook_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    gate.wait()
    mod._record_a_firing(pathlib.Path(root), f"agent-{i}", 100 + i, "ok")


def _ensure_worker(root, _i, gate):
    sys.path.insert(0, LIB)
    import workspace as _ws
    gate.wait()
    _ws.ensure(pathlib.Path(root))


def _candidate_worker(root, sequence, gate):
    sys.path.insert(0, LIB)
    import candidates
    gate.wait()
    candidates.upsert(pathlib.Path(root), sequence, 1, "2026-09-07")


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
    procs = [Process(target=_tools_worker,
                     args=(str(root), 50, None, str(root / f"giveups-{k}.json")))
             for k in range(8)]
    [p.start() for p in procs]
    [p.join() for p in procs]
    runs = json.loads(
        (root / ".chamnan" / "tools" / "index.json").read_text(encoding="utf-8"))[0]["runs"]
    check(f"EVERY ONE OF 400 CONCURRENT INCREMENTS IS RECORDED (got {runs})", runs == 400)
    if runs != 400:
        print(f"[WHY] shipped ceilings: {_why_they_left(root)}")

    # --- the same store, with the ceiling set in this machine's own units -------------------
    # 🐛 [2026-09-08] The check above passed on macOS and ubuntu and failed on Windows at 41 of
    # 400, and nothing on a Mac could see it -- so it cost a push and a CI round trip to learn each
    # time. The mechanism was a waiter holding the lock file open while its owner tried to unlink
    # it, which Windows refuses; `lib/workspace.py` carries the whole account beside the fix.
    #
    # This is the check that finds the NEXT one here instead of there. Squeezing the ceiling is the
    # same experiment as slowing the disk, and it runs anywhere -- but the first version of it
    # pinned an absolute 0.05 s, which is a hard squeeze on the machine it was written on and a
    # brutal one where a turn already costs forty times more. It failed on Windows at 396 of 400
    # and on ubuntu too, for a reason that was not a defect. A threshold in seconds measures the
    # platform; a threshold in multiples of what the platform itself costs measures the code.
    #
    # So: time the REAL operation uncontended -- lock, read the index, edit it, write it back --
    # and give the storm three times what it costs all eight contenders to each take one turn. That
    # is the smallest ceiling under which a fair queue can still make progress, and it is expressed
    # in the machine's own units, so the same sentence is true on a laptop and on a slow runner.
    # An earlier version of this timed an EMPTY lock cycle and recorded 399 of 400 here, because
    # the critical section is most of the cost and it was not in the measurement.
    import tools_index as _tools_index
    import workspace as ws
    CONTENDERS = 8
    _probe = pathlib.Path(tempfile.mkdtemp(prefix="cw-cycle-"))
    (_probe / ".chamnan" / "tools").mkdir(parents=True)
    (_probe / ".chamnan" / "tools" / "index.json").write_text(
        json.dumps([{"name": "t.sh", "desc": "x", "runs": 0}]), encoding="utf-8")
    _cycles = []
    for _ in range(40):
        _t0 = time.perf_counter()
        _tools_index.record_call(_probe, "t.sh", False, False)
        _cycles.append(time.perf_counter() - _t0)
    # Capped at the shipped ceiling, because a machine slow enough that three fair rounds cost
    # more than LOCK_TIMEOUT would otherwise run this at a LOOSER setting than production and call
    # it a squeeze. There the check degenerates to "the shipped configuration holds", which is
    # true, worth knowing, and must say so rather than quietly measure nothing.
    _ceiling = min(max(max(_cycles) * CONTENDERS * 3, 0.002), ws.LOCK_TIMEOUT)
    print(f"[INFO] one uncontended record_call here: {max(_cycles)*1000:.3f} ms, so the squeeze "
          f"runs at {_ceiling*1000:.1f} ms against the shipped {ws.LOCK_TIMEOUT*1000:.0f}"
          + (" — no squeeze: this machine is slower than the shipped ceiling allows for"
             if _ceiling >= ws.LOCK_TIMEOUT else
             f" — {ws.LOCK_TIMEOUT / _ceiling:.0f}x tighter"))

    root = pathlib.Path(tempfile.mkdtemp())
    (root / ".chamnan" / "tools").mkdir(parents=True)
    (root / ".chamnan" / "tools" / "index.json").write_text(
        json.dumps([{"name": "t.sh", "desc": "x", "runs": 0}]), encoding="utf-8")
    procs = [Process(target=_tools_worker,
                     args=(str(root), 50, _ceiling, str(root / f"giveups-{k}.json")))
             for k in range(CONTENDERS)]
    [p.start() for p in procs]
    [p.join() for p in procs]
    slow = json.loads(
        (root / ".chamnan" / "tools" / "index.json").read_text(encoding="utf-8"))[0]["runs"]
    check(f"...AND ON A CEILING OF THREE FAIR ROUNDS, IN THIS MACHINE'S UNITS (got {slow})",
          slow == 400)
    if slow != 400:
        print(f"[WHY] squeezed ceiling: {_why_they_left(root)}")

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

    # ---------------------------------------------------------------- R7: six more of the same
    # Every one of these is the identical shape the four above were fixed for, in a writer nobody
    # had raced yet. They all go through `ws.rewrite_shared` now -- one primitive rather than the
    # same four lines written six more slightly different ways.

    # `milestones.append` had no lock AT ALL, and it loses entries outright rather than thinning
    # them: the last writer's snapshot became the whole file. Six processes, five entries gone.
    _ms = pathlib.Path(tempfile.mkdtemp(prefix="cw-milestones-")) / "r"
    (_ms / ".chamnan").mkdir(parents=True)
    _n_ms = 6
    # 🐛 The first version of these four checks spawned the processes without a barrier and every
    # one of them PASSED with the lock removed -- the workers finished before their siblings were
    # even started, so nothing raced and the checks proved nothing. Caught by running the negative
    # control rather than by reading them. The barrier is what makes them a concurrency test.
    _gate = Barrier(_n_ms)
    _procs = [Process(target=_milestone_worker, args=(str(_ms), i, _gate)) for i in range(_n_ms)]
    for pr in _procs:
        pr.start()
    for pr in _procs:
        pr.join()
    _ms_text = (_ms / ".chamnan" / "milestones.md").read_text(encoding="utf-8")
    _ms_have = sum(1 for i in range(_n_ms) if f"milestone-{i}" in _ms_text)
    check(f"EVERY ONE OF {_n_ms} CONCURRENT MILESTONES SURVIVES ({_ms_have}/{_n_ms})",
          _ms_have == _n_ms)
    # Six racing writers each fall back to "the file is empty, start it with the header", so a
    # duplicated header is the specific way this race shows even when no entry is lost.
    import milestones as _ms_mod
    check("...and the file still opens with its header exactly once",
          _ms_text.count(_ms_mod.HEADER.strip()) == 1
          and _ms_text.startswith(_ms_mod.HEADER.strip()))

    # `pointer.mark_pointed`'s per-session file is not private when a subagent inherits its
    # parent's session_id -- which is what a subagent's hooks actually do. Twelve opens, eleven
    # lost.
    _pt = pathlib.Path(tempfile.mkdtemp(prefix="cw-pointer-")) / ".chamnan"
    (_pt / "logs").mkdir(parents=True)
    _n_pt = 12
    _gate = Barrier(_n_pt)
    _procs = [Process(target=_pointer_worker, args=(str(_pt), "one-shared-session", i, _gate))
              for i in range(_n_pt)]
    for pr in _procs:
        pr.start()
    for pr in _procs:
        pr.join()
    sys.path.insert(0, LIB)
    import pointer as _pointer_mod
    _seen = json.loads(_pointer_mod._seen_path(_pt, "one-shared-session")
                       .read_text(encoding="utf-8-sig"))
    _pt_have = sum(1 for i in range(_n_pt) if f"src/file-{i}.py" in _seen.get("paths", []))
    check(f"A PARENT AND ITS SUBAGENTS SHARE ONE SEEN-FILE AND LOSE NOTHING "
          f"({_pt_have}/{_n_pt})", _pt_have == _n_pt)

    # The subagent firing log: read the tail, append one, write it all back. Subagents are
    # dispatched in batches, so this is the writer with the most concurrent callers by design --
    # and it lost 84% of them.
    _fr = pathlib.Path(tempfile.mkdtemp(prefix="cw-firings-")) / "r"
    (_fr / ".chamnan" / "logs").mkdir(parents=True)
    _n_fr = 30
    _hook = str(ROOT / "hooks" / "chamnan_subagent_start.py")
    _gate = Barrier(_n_fr)
    _procs = [Process(target=_firing_worker, args=(str(_fr), _hook, i, _gate))
              for i in range(_n_fr)]
    for pr in _procs:
        pr.start()
    for pr in _procs:
        pr.join()
    _fr_lines = [ln for ln in (_fr / ".chamnan" / "logs" / "subagent_start.jsonl")
                 .read_text(encoding="utf-8-sig").splitlines() if ln.strip()]
    _fr_types = {json.loads(ln)["agent_type"] for ln in _fr_lines}
    _fr_have = sum(1 for i in range(_n_fr) if f"agent-{i}" in _fr_types)
    check(f"EVERY ONE OF {_n_fr} CONCURRENT SUBAGENT FIRINGS IS RECORDED ({_fr_have}/{_n_fr})",
          _fr_have == _n_fr)
    check("...and the firing log is still valid JSON Lines throughout",
          all(isinstance(json.loads(ln), dict) for ln in _fr_lines))

    # `ensure()` runs at the start of every command and every hook, and both of its self-repairs
    # read-decided-appended without a lock, so each concurrent caller appended the whole block.
    _en = pathlib.Path(tempfile.mkdtemp(prefix="cw-ensure-")) / "r"
    _en.mkdir(parents=True)
    (_en / ".git").mkdir()
    _n_en = 8
    _gate = Barrier(_n_en)
    _procs = [Process(target=_ensure_worker, args=(str(_en), i, _gate)) for i in range(_n_en)]
    for pr in _procs:
        pr.start()
    for pr in _procs:
        pr.join()
    import workspace as _ws_mod
    _gi_lines = [ln for ln in (_en / ".chamnan" / ".gitignore")
                 .read_text(encoding="utf-8-sig").splitlines() if ln.strip()
                 and not ln.lstrip().startswith("#")]
    check(f"{_n_en} CONCURRENT ensure() CALLS DO NOT DUPLICATE AN IGNORE RULE "
          f"({len(_gi_lines)} lines, {len(set(_gi_lines))} distinct)",
          len(_gi_lines) == len(set(_gi_lines)))
    _ga_lines = [ln for ln in (_en / ".chamnan" / ".gitattributes")
                 .read_text(encoding="utf-8-sig").splitlines() if ln.strip()
                 and not ln.lstrip().startswith("#")]
    check(f"...nor a generated-file attribute ({len(_ga_lines)} lines, "
          f"{len(set(_ga_lines))} distinct)", len(_ga_lines) == len(set(_ga_lines)))
    # config.json used to be written with Path.write_text, which truncates on open -- so the
    # failure mode was an empty or half-written file on its real path, not a lost staging file.
    check("...and config.json is whole and parses",
          isinstance(json.loads((_en / ".chamnan" / "config.json")
                                .read_text(encoding="utf-8-sig")), dict))

    # 🐛 `state.age_out` took a lock on `logs/state-ages.json` and never looked at the boolean, so
    # under contention it wrote while a real holder had the file. And the lock could not be
    # created at all in a workspace where `logs/` did not exist yet -- so on a fresh workspace it
    # had NEVER been taken, and the branch that ignored it was the only reason anything was
    # written. Both halves are checked: the lock is takeable, and a caller that cannot take it
    # does not write anyway.
    _ag = pathlib.Path(tempfile.mkdtemp(prefix="cw-ages-")) / ".chamnan"
    _ag.mkdir(parents=True)
    import state as _state_mod
    with ws.exclusive(_ag / _state_mod.AGES_PATH) as _ag_held:
        check("A LOCK IS TAKEABLE BESIDE A FILE WHOSE DIRECTORY DOES NOT EXIST YET",
              _ag_held is True)
        _before = (_ag / _state_mod.AGES_PATH).exists()
        _state_mod.age_out("## a\n\nbody\n", _ag, 30)
        check("...and a second caller that cannot take it does not write the ages file anyway",
              (_ag / _state_mod.AGES_PATH).exists() == _before)
    _state_mod.age_out("## a\n\nbody\n", _ag, 30)
    check("...and does write it once the lock is free",
          (_ag / _state_mod.AGES_PATH).is_file())

    # 🐛 A lock left by a process that DIED was waited on for the full 30-second stale window, the
    # same as one held by a live but slow process. Measured at 29.9s. The PID is in the lock file
    # for exactly this question and only the age rule ever asked it.
    _dl = pathlib.Path(tempfile.mkdtemp(prefix="cw-deadlock-")) / "f.json"
    _dl.parent.mkdir(parents=True, exist_ok=True)
    _dead = subprocess.Popen([sys.executable, "-c", "pass"])
    _dead.wait()
    pathlib.Path(str(_dl) + ".lock").write_text(f"{_dead.pid}\n", encoding="utf-8")
    _t0 = time.time()
    with ws.exclusive(_dl) as _dl_held:
        _dl_took = time.time() - _t0
        check("A LOCK WHOSE HOLDER HAS DIED IS BROKEN AT ONCE, NOT AFTER THE STALE WINDOW",
              _dl_held is True and _dl_took < 1.0)
    if not (_dl_held and _dl_took < 1.0):
        print(f"       took {_dl_took:.1f}s against LOCK_STALE={ws.LOCK_STALE}")

    # ...and the case that must NOT be broken early: a lock created by a live process that has not
    # yet written its PID into it. Two syscalls, so an empty lock is also what a perfectly healthy
    # holder looks like for a moment -- breaking on that hands one file to two writers.
    _el = pathlib.Path(tempfile.mkdtemp(prefix="cw-emptylock-")) / "f.json"
    _el.parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(str(_el) + ".lock").write_text("", encoding="utf-8")
    with ws.exclusive(_el) as _el_held:
        check("...while a lock that names nobody yet is left alone until it is genuinely stale",
              _el_held is False)

    # 🐛 `candidates.upsert`'s merge is a read-modify-write across the whole DIRECTORY -- scan every
    # candidate, then unlink one and write another. Two PostToolUse hooks firing together each
    # scanned, each found nothing to merge with, and each wrote its own file, producing the very
    # "five files for one habit" the merge exists to prevent.
    _cd = pathlib.Path(tempfile.mkdtemp(prefix="cw-cand-")) / "r"
    (_cd / ".chamnan" / "candidates").mkdir(parents=True)
    # The same habit seen at three different offsets: rotations of one cyclic sequence, which is
    # exactly what a sliding window over a command log produces.
    #
    # Pure rotations only, and that is a deliberate narrowing. The first version of this check also
    # included the four-element `python3, git add, git commit, python3` — and got 2 files, which
    # looked like the lock failing. It was not: run SEQUENTIALLY, that set produces 2 files in 18
    # of its 24 orderings, so the check was asserting a property the merge has never had. Three
    # rotations give exactly 1 file in all 6 sequential orderings, so there is a single right
    # answer here and concurrency is the only thing under test.
    #
    # (That the merge is order-dependent for a longer sequence containing a shorter one is a real
    # finding and a separate one. It is not a race, it does not lose data, and folding it in here
    # would make this check fail for a reason that has nothing to do with concurrency.)
    _seqs = [["python3", "git add", "git commit"],
             ["git add", "git commit", "python3"],
             ["git commit", "python3", "git add"]]
    _gate = Barrier(len(_seqs))
    _procs = [Process(target=_candidate_worker, args=(str(_cd), q, _gate)) for q in _seqs]
    for pr in _procs:
        pr.start()
    for pr in _procs:
        pr.join()
    _cd_files = sorted(q.name for q in (_cd / ".chamnan" / "candidates").glob("*.md"))
    check(f"ONE HABIT SEEN AT {len(_seqs)} OFFSETS AT ONCE IS STILL ONE CANDIDATE "
          f"({len(_cd_files)} files)", len(_cd_files) == 1)
    if len(_cd_files) != 1:
        print("       ", _cd_files)

    # 🐛 `prune_logs` decides what to delete from one stat() sweep and unlinks in a later pass. On
    # POSIX, unlinking a file a process holds open for append succeeds in silence and the writer's
    # next lines land in an orphaned inode nothing will ever read from that path again.
    #
    # WHAT IS CHECKED HERE, AND WHY IT IS NOT AN END-TO-END RACE. The reported fix — re-stat before
    # the unlink — does NOT close the case that was reported. Measured, both ways: with a writer
    # that opens the file and delays its first write, the sweep sentences it on an mtime that is
    # still old, the re-stat reads the same old mtime, and the file is deleted with or without the
    # fix. Written the other way, with the writer touching the file first, it is never sentenced at
    # all and the check passes with or without the fix. There is a window between those two where
    # the fix is what saves the file, and it is a few milliseconds wide and not reproducible on
    # demand — so an end-to-end check of it would pass for whichever reason the scheduler picked
    # that run, which is worse than no check.
    #
    # So what the fix DOES is pinned directly instead. It covers the common shape — a session
    # appends, a later session's SessionStart sweep runs, and the file is spared because it is no
    # longer old — and it does not cover a file that is held open and untouched. No amount of
    # stat'ing tells "old" from "old and held open"; that needs the writer to take a lock, and the
    # writer is a session appending to its own note with a plain open(), not chamnan code that
    # could be made to. On the record as open rather than papered over.
    _pl = pathlib.Path(tempfile.mkdtemp(prefix="cw-prune-")) / "r"
    _pl_logs = _pl / ".chamnan" / "logs"
    _pl_logs.mkdir(parents=True)
    _old = time.time() - 10 * 86400
    _u1 = _pl_logs / "touched.md"
    _u1.write_text("x\n", encoding="utf-8")
    check("A FILE TOUCHED SINCE THE SWEEP DECIDED ITS FATE IS SPARED",
          not ws._still_doomed(_u1, time.time() - 86400))
    _u2 = _pl_logs / "untouched.md"
    _u2.write_text("x\n", encoding="utf-8")
    os.utime(_u2, (_old, _old))
    check("...and one that has not been touched is not",
          ws._still_doomed(_u2, time.time() - 86400))
    # End to end, the part that IS deterministic: retention still deletes what it should, and a
    # file whose mtime moved after the sweep started is still there afterwards.
    (_pl_logs / "a-fresh-note.md").write_text("fresh\n", encoding="utf-8")
    _cold = _pl_logs / "a-cold-note.md"
    _cold.write_text("cold\n", encoding="utf-8")
    os.utime(_cold, (_old, _old))
    ws.prune_logs(_pl)
    check("...while a log nobody has touched is still deleted", not _cold.exists())
    check("...and a fresh one beside it is not", (_pl_logs / "a-fresh-note.md").is_file())

    total = PASSED + len(FAILED)
    print(f"\n{PASSED}/{total} checks passed")
    sys.exit(1 if FAILED else 0)
