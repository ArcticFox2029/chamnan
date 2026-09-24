#!/usr/bin/env python3
"""Apply RUBRIC.md to one task result. Deterministic, and allowed to refuse.

🎯 [1.31 queue item 4] The pilot measures whether the MEASUREMENT is reliable, so this file is the
deliverable — not the win rate. It was written before any task ran, because a rubric written after
seeing the outputs scores the outputs it has already seen.

The five questions have forced answers, and `unknown` is not a middle grade: it means the evidence
does not decide, and any `unknown` makes the task INVALID. That is the rule that stops a scorer
inventing a verdict, and it is the reason an INVALID count is a result rather than a nuisance.
"""
import argparse
import json
import pathlib
import subprocess
import sys

PASS, PARTIAL, FAIL, INVALID = "PASS", "PARTIAL", "FAIL", "INVALID"
UNKNOWN = "unknown"
REQUIRED = ("must_change", "must_not_change", "behaviour", "regression", "rejected")


def scoreable(task):
    """A task missing any ground truth is not run. Reported, never treated as a pass."""
    return [k for k in REQUIRED if k not in task]


def _changed(workdir, task):
    """Which of the task's declared files differ from the fixture it started from."""
    base = pathlib.Path(task["_fixture"])
    work = pathlib.Path(workdir)
    out = set()
    for rel in list(task["must_change"]) + list(task["must_not_change"]):
        a, b = base / rel, work / rel
        try:
            if a.read_bytes() != b.read_bytes():
                out.add(rel)
        except OSError:
            return None                # a file that cannot be read decides nothing
    return out


def _behaviour(workdir, task):
    """yes / no / unknown — run the declared expression against the work tree."""
    spec = task["behaviour"]
    if "expr" in spec:
        prog = ("import sys; sys.path.insert(0, %r)\n"
                "from shop import pricing, inventory, report\n"
                "sys.exit(0 if (%s) else 1)\n" % (str(workdir), spec["expr"]))
    else:
        prog = ("import sys; sys.path.insert(0, %r)\n"
                "from shop import pricing, inventory, report\n"
                "try:\n    %s\nexcept %s:\n    sys.exit(0)\nexcept Exception:\n    sys.exit(1)\n"
                "sys.exit(1)\n" % (str(workdir), spec["raises"], spec["exc"]))
    try:
        rc = subprocess.run([sys.executable, "-c", prog], capture_output=True,
                            text=True, timeout=60).returncode
    except (OSError, subprocess.SubprocessError):
        return UNKNOWN
    return "yes" if rc == 0 else "no"


def _regression(workdir, task):
    spec = task["regression"]
    # 🐛 [2026-09-24] (self-measured) This ran `spec["cmd"]` as written, so the harness executed
    # whatever program a task file named — the one call site in the tree the executed-binaries
    # sweep could not read, against a README that says what runs. Every task's command is a Python
    # test, so it runs under THIS interpreter (the one the harness was started with, rather than
    # whichever `python3` is first on PATH), and a task naming anything else is not scored.
    cmd = list(spec.get("cmd") or [])
    if not cmd or pathlib.Path(str(cmd[0])).name not in ("python", "python3"):
        return UNKNOWN
    try:
        rc = subprocess.run([sys.executable, *cmd[1:]], cwd=str(workdir), capture_output=True,
                            text=True, timeout=300).returncode
    except (OSError, subprocess.SubprocessError):
        return UNKNOWN
    return "no" if rc == spec["expect_exit"] else "yes"      # "introduced a regression?"


def _rejected(workdir, task):
    """Did the change reach for an approach this repository has already refused?"""
    seen = []
    for rel in task["must_change"]:
        try:
            body = (pathlib.Path(workdir) / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return UNKNOWN, []
        seen += [p for p in task["rejected"] if p in body]
    return ("yes" if seen else "no"), seen


def answers(workdir, task, corrections=None):
    """The five forced answers, each yes / no / unknown (or a count)."""
    changed = _changed(workdir, task)
    if changed is None:
        right_file = UNKNOWN
    else:
        wanted = set(task["must_change"])
        forbidden = set(task["must_not_change"]) & changed
        right_file = "yes" if (wanted <= changed and not forbidden) else "no"
    rej, hits = _rejected(workdir, task)
    return {
        "changed_correct_file": right_file,
        "satisfied_required_behaviour": _behaviour(workdir, task),
        "introduced_regression": _regression(workdir, task),
        "repeated_rejected_decision": rej,
        "needed_human_correction": UNKNOWN if corrections is None else min(int(corrections), 2),
        "_rejected_hits": hits,
    }


def verdict(ans, drift=False):
    """RUBRIC.md's resolution order, in the order it is written there."""
    if any(v == UNKNOWN for k, v in ans.items() if not k.startswith("_")):
        return INVALID
    if drift:
        return INVALID
    if (ans["introduced_regression"] == "yes" or ans["changed_correct_file"] == "no"
            or ans["repeated_rejected_decision"] == "yes"):
        return FAIL
    if ans["satisfied_required_behaviour"] == "no":
        return PARTIAL
    return PASS


def agree(*verdicts):
    """Two scorers that disagree make the task INVALID — never a forced winner."""
    seen = {v for v in verdicts if v}
    if not seen:
        return INVALID
    return seen.pop() if len(seen) == 1 else INVALID


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("task_id")
    ap.add_argument("workdir")
    ap.add_argument("--fixture", default=str(pathlib.Path(__file__).parent / "fixture"))
    ap.add_argument("--corrections", type=int)
    ap.add_argument("--drift", action="store_true")
    a = ap.parse_args()
    tasks = json.loads((pathlib.Path(__file__).parent / "tasks.json").read_text())
    task = next((t for t in tasks if t["id"] == a.task_id), None)
    if task is None:
        print(f"score: no task {a.task_id}", file=sys.stderr)
        return 2
    missing = scoreable(task)
    if missing:
        print(f"score: {a.task_id} is missing {missing} — not scoreable, not a pass",
              file=sys.stderr)
        return 2
    task["_fixture"] = a.fixture
    ans = answers(a.workdir, task, a.corrections)
    v = verdict(ans, drift=a.drift)
    print(json.dumps({"task": a.task_id, "verdict": v, "answers": ans}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
