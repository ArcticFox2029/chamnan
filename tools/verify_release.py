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
    # An hour, and it is a bound rather than an expectation: the regression suite runs through here
    # and takes about seventeen minutes, so anything shorter would make the gate the thing that
    # fails. Unbounded was the previous state, and a gate that waits forever on a hung suite reports
    # nothing at all — which is worse than reporting a timeout, because a person walks away from it.
    # Written at the call rather than through `kw.setdefault`, so it is visible both to a reader
    # and to the check that asserts every subprocess here is bounded — that check reads the AST, and
    # a bound smuggled in through `**kw` is a bound it cannot see. A guarantee the guard cannot
    # verify is the shape this repository keeps finding.
    return subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=str(ROOT), timeout=kw.pop("timeout", 3600), **kw)


def declared_version():
    import json
    try:
        return json.loads((ROOT / ".claude-plugin" / "plugin.json")
                          .read_text(encoding="utf-8")).get("version", "?")
    except Exception:                                    # noqa: BLE001
        return "?"


def _remember_and_compare(total, failing, took):
    """Record this run's size and say how it moved since the last one.

    The owner's ask, 2026-09-09: "when the big suite runs, show the check number too, so I can see
    whether it actually moves after a stretch of fixes." A totals line on its own answers "did it
    pass"; it does not answer "did the work of the last two hours reach the suite at all", and that
    is the question a person watching a long session actually has.

    One line per run in a JSONL beside the other logs. Failure to write it never affects the
    verdict — a gate that cannot record its own history still verifies the release.
    """
    import json
    log = ROOT.parent.parent / ".chamnan" / "logs" / "gate_runs.jsonl"
    prior = None
    try:
        if log.is_file():
            for line in log.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    prior = json.loads(line)
    except (OSError, ValueError):
        prior = None
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "checks": total,
                                 "failing": failing, "seconds": round(took)}) + "\n")
    except OSError:
        pass
    if not prior or "checks" not in prior:
        return f"{total:,} checks — first run recorded; the next one will say how it moved"
    was = prior["checks"]
    if total == was:
        return (f"{total:,} checks — unchanged since the last run. Fixes since then added no new "
                f"coverage to this suite")
    return (f"{total:,} checks — was {was:,}, {'+' if total > was else ''}{total - was} "
            f"since the last run")


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
    # \U0001f41b [2026-09-09] Counted in `stdout` only, and a Python traceback goes to `stderr`. So
    # a run that died mid-suite reported "0 traceback(s)" beside "did not reach its own totals
    # line", and the one piece of evidence saying WHY was captured, held in `r.stderr`, and never
    # looked at. This module's own docstring calls the absence of failures no proof; the same
    # applies to the absence of a traceback nobody read.
    _out = (r.stdout or "") + "\n" + (r.stderr or "")
    tracebacks = _out.count("Traceback (most recent call last)")
    if not totals:
        print(f"  ✗ the suite did not reach its own totals line after {took / 60:.1f} minutes")
        if tracebacks:
            print(f"    it stopped on {tracebacks} traceback(s); the last lines were:")
            for line in _out.rstrip().split("\n")[-8:]:
                print(f"      {line}")
        else:
            # No traceback anywhere is its own finding: the suite ENDED without printing totals and
            # without saying why, which is a killed process or an early exit, not a failing check.
            print(f"    no traceback on either stream — the run ended early rather than failing. "
                  f"{len(r.stdout or '')} byte(s) on stdout, {len(r.stderr or '')} on stderr")
        return None
    passed, total = totals.group(1), totals.group(2)
    _moved = _remember_and_compare(int(total), len(fails), took)
    if _moved:
        print(f"    {_moved}")
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


def the_publication_guard():
    """Nothing about to ship may name the owner's real work.

    Separate from the suite on purpose. The suite's checks look for SHAPES — a home directory, a
    credential format, an address — and the thing that actually shipped was none of those: a real
    operational constraint written as ordinary prose in a test fixture, in a tree four gates had
    already called clean. A list of terms is the only thing that catches what no pattern predicts.

    The list lives outside every repository, so this is skipped rather than failed where it is
    absent — a machine that is not the owner's has nothing to check against. It is reported as
    skipped, never as passed.
    """
    # \U0001f41b [2026-09-09] Named with an underscore, while the registered tool is hyphenated like
    # every other one in that directory. It passed for as long as it did only because the file
    # existed under BOTH spellings -- and the moment the byte-identical duplicate was cleaned up,
    # the one check that stops the owner's real work reaching a shipped repository began reporting
    # "not installed on this machine" and skipping. Silently, and on the release gate.
    #
    # Both spellings are accepted rather than one corrected, because an installed workspace written
    # by an older chamnan carries the underscore name and a gate that skips on THAT machine has the
    # same hole. The set is "however this tool has ever been named", not "what it is called today".
    tool = None
    for _name in ("publication-guard.py", "publication_guard.py"):
        _try = ROOT.parent.parent / ".chamnan" / "tools" / _name
        if _try.is_file():
            tool = _try
            break
    if tool is None:
        return None, "publication guard not installed on this machine"
    r = _run([sys.executable, str(tool)])
    if r.returncode == 2:
        return None, r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "no term list"
    return r.returncode == 0, (r.stdout or r.stderr).strip().splitlines()[-1]


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
    guard, guard_says = the_publication_guard()
    if guard is None:
        print(f"  · {guard_says} — SKIPPED, not passed")
    elif guard:
        print(f"  ✓ {guard_says}")
    else:
        print(f"  ✗ {guard_says}")
    the_duplicates()
    print()
    if suite is None or index is None:
        print("NOT VERIFIED — a check did not produce a result. Nothing above should be quoted.")
        return 2
    if guard is False:
        print("NOT VERIFIED — something about to ship names the owner's real work. "
              "Substitute an invented equivalent; do not quote what you saw.")
        return 1
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
