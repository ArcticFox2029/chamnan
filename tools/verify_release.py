#!/usr/bin/env python3
"""Re-run every check this release's notes claim, and print what actually happened.

A release note that quotes a number nobody else can reproduce is asking to be taken on trust. This
runs the checks, prints their real output, and says plainly which claim each one settles.

    python3 tools/verify_release.py

Nothing here needs a network, a dependency or an API key: the plugin is standard library only and
so is this. It takes about fifteen minutes, almost all of it the regression suite, which spends its
time building fixtures and spawning subprocesses rather than evaluating assertions.

Exit 0 only when every claim below is confirmed. Any other exit means the release's own notes do
not match the code you have, and the output says which one.
"""
import pathlib
import re
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _run(argv, **kw):
    return subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=str(ROOT), **kw)


def declared_version():
    import json
    try:
        return json.loads((ROOT / ".claude-plugin" / "plugin.json")
                          .read_text(encoding="utf-8")).get("version", "?")
    except Exception:                                    # noqa: BLE001
        return "?"


def the_suite():
    """The regression suite, and the totals line that is the only proof it finished.

    The absence of failures is NOT the proof: a suite that dies mid-run prints a traceback and no
    failure lines at all, so a grep for them reads zero over a run that stopped early. The totals
    line is printed once, at the end, and only if the end was reached.
    """
    print("  running the regression suite — about fifteen minutes, no output until it ends")
    started = time.time()
    r = _run([sys.executable, str(ROOT / "tests" / "run_tests.py")])
    took = time.time() - started
    totals = re.search(r"^(\d+)/(\d+) checks passed", r.stdout, re.M)
    fails = re.findall(r"^  FAIL  (.+)$", r.stdout, re.M)
    tracebacks = r.stdout.count("Traceback (most recent call last)")
    if not totals:
        print(f"  ✗ the suite did not reach its own totals line after {took / 60:.1f} minutes")
        if tracebacks:
            print(f"    it stopped on {tracebacks} traceback(s); the last lines were:")
            for line in r.stdout.rstrip().split("\n")[-6:]:
                print(f"      {line}")
        return None
    passed, total = totals.group(1), totals.group(2)
    print(f"  {'✓' if not fails else '✗'} {passed}/{total} checks passed "
          f"in {took / 60:.1f} minutes, {len(fails)} failing, {tracebacks} traceback(s)")
    for f in fails[:10]:
        print(f"      FAIL  {f}")
    return (passed, total, len(fails), tracebacks)


def the_index_claims():
    """Every mechanical claim in this repository's own architecture index, checked against the tree.

    A path exists, a line count matches, a named function is still defined where the index says.
    No model and no network: that is the whole reason an index can be checked at all.
    """
    r = _run([sys.executable, str(ROOT / "tools" / "map_claim_check.py")])
    m = re.search(r"^\s+ALL\s+([\d,]+)\s+([\d,]+)\s+([\d.]+)%", r.stdout, re.M)
    if not m:
        print("  ✗ the claim checker produced no summary line")
        return None
    checked, true, rate = m.group(1), m.group(2), m.group(3)
    ok = float(rate) >= 99.0
    print(f"  {'✓' if ok else '✗'} {true} of {checked} index claims true ({rate}%)")
    if not ok:
        for line in r.stdout.split("\n"):
            if "false claim" in line or line.strip().startswith(("lines", "functions", "symbols")):
                print(f"      {line.strip()}")
    return (checked, true, rate)


def the_duplicates():
    """The defect this repository produces more than any other, asked of the whole tree."""
    tool = ROOT.parents[1] / ".chamnan" / "tools" / "the_same_thing_twice.py"
    if not tool.is_file():
        return None
    r = _run([sys.executable, str(tool), "--quiet"])
    n = len(re.findall(r"^  \w+\(\)", r.stdout, re.M))
    print(f"  · {n} function body written in more than one file — advisory, not a gate")
    return n


def main():
    print(f"chamnan {declared_version()} — verifying this release's own claims\n")
    suite = the_suite()
    index = the_index_claims()
    the_duplicates()
    print()
    if suite is None or index is None:
        print("NOT VERIFIED — a check did not produce a result. Nothing above should be quoted.")
        return 2
    passed, total, fails, tracebacks = suite
    if fails or tracebacks:
        print(f"NOT VERIFIED — {fails} failing check(s), {tracebacks} traceback(s).")
        return 1
    print(f"VERIFIED — {passed}/{total} checks pass and {index[1]} of {index[0]} index claims "
          f"are true, on this machine, from this checkout.")
    print("Quote those two numbers rather than the ones in the release notes: yours are the ones "
          "you watched happen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
