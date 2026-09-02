#!/usr/bin/env python3
"""Which fixes would actually be caught if the fix were reverted?

Written after finding that one of this repository's own security fixes — the symlink escape guard
that stops a plain-prose credential reaching the committed `MAP.md` — had no test at all. It had
been verified by hand and then written up as though it were pinned.

The reason to check is measured: on SWT-Bench Lite the best system produces a genuinely failing
reproducing test in **18.5%** of cases (arXiv:2406.12952), so a test written *after* a fix and never
observed failing cannot be assumed to pin anything. And tests generated with the buggy code in
context assert the buggy behaviour **8.3× more often** than tests written from the fixed code
(arXiv:2607.22883) — which is exactly the position a session is in when it writes a pinning test
straight after making the fix.

**It never touches the repository's own files.** `git show` writes each version into a scratch
directory and both are imported side by side, because the obvious way to do this — reverting the
file in place — left `lib/tree.py` on its pre-fix version when the run timed out mid-way.

    python3 bench/pinned.py <scratch-dir> [<baseline-ref>]

A row reading NOT PINNED means the probe passes against the old code too: either the fix was
already there, or the probe is not testing what it claims. Both are worth knowing.
"""
import importlib.util
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent

# (label, module path, probe). A probe returns True when the FIXED behaviour is present.
CASES = [
    ("redact: XML element text", "lib/redact.py",
     lambda m: "Tr0ub4dor" not in m.scrub("<password>Tr0ub4dorXML</password>")),
    ("redact: hash rocket", "lib/redact.py",
     lambda m: "Tr0ub4dor" not in m.scrub("'password' => 'Tr0ub4dorPHP',")),
    ("redact: key=lambda survives", "lib/redact.py",
     lambda m: m.scrub("key=lambda p: p.name") == "key=lambda p: p.name"),
    ("redact: a copied key is refused", "lib/redact.py",
     lambda m: m.is_never_opened(pathlib.Path("backup.pem.txt"))),
    ("tree: sibling symlink is outside", "lib/tree.py", lambda m: _walk_escape(m)),
    ("ledger: 2026-02-30 is not a date", "lib/ledger.py",
     lambda m: m._ymd_to_ts(2026, 2, 30) is None),
    ("ledger: a future year is not one", "lib/ledger.py",
     lambda m: m._ymd_to_ts(2099, 1, 1) is None),
    ("fit: an outlier line is skipped", "lib/fit.py",
     lambda m: "## Blockers" in m._fit_lines(
         ["## Open", "- a", "  T: " + "x" * 900, "- b", "## Blockers", "- c"], 400)),
    ("rulecheck: nested group refused", "lib/rulecheck.py",
     lambda m: m._quantified_group_over_quantifier("(?:(a+))+$")),
    ("impact: `..` resolves upward", "lib/impact.py",
     lambda m: list(m.build([{"path": "src/shared/u.js"}, {"path": "vendor/shared/u.js"},
                             {"path": "src/a/b.js", "imports": ["../shared/u"]}]))
     == ["src/shared/u.js"]),
    ("pointer: a dot-directory is kept", "lib/pointer.py",
     lambda m: ".github/workflows/ci.yml" in m.needles(".github/workflows/ci.yml")),
    ("memory: a BOM does not hide a title", "lib/memory.py", lambda m: _bom_title(m)),
]


def _walk_escape(m):
    import os
    import shutil
    import tempfile
    d = pathlib.Path(tempfile.mkdtemp())
    try:
        (d / "app" / "src").mkdir(parents=True)
        (d / "app-secrets").mkdir()
        (d / "app-secrets" / "prod_db.py").write_text("# operator / hunter2\n", encoding="utf-8")
        (d / "app" / "src" / "main.py").write_text("# entry\n", encoding="utf-8")
        os.symlink("../../app-secrets/prod_db.py", d / "app" / "src" / "leaked.py")
        return sorted(p.name for p in m.files(d / "app")) == ["main.py"]
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _bom_title(m):
    import shutil
    import tempfile
    d = pathlib.Path(tempfile.mkdtemp())
    try:
        f = d / "e.md"
        f.write_bytes("﻿# Why Postgres over SQLite\n\nbody\n".encode("utf-8"))
        return m.title_of(f) == "Why Postgres over SQLite"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def load(ref, relpath, scratch, alias):
    got = subprocess.run(["git", "-C", str(REPO), "show", f"{ref}:{relpath}"],
                         capture_output=True, text=True)
    if got.returncode:
        return None
    out = scratch / f"{alias}.py"
    out.write_text(got.stdout, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(alias, out)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def main(argv):
    scratch = pathlib.Path(argv[0] if argv else "/tmp/chamnan-pinned")
    baseline = argv[1] if len(argv) > 1 else "HEAD~20"
    scratch.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(REPO / "lib"))
    print(f"{'case':<38}{baseline:>12}{'HEAD':>8}   verdict")
    unpinned = 0
    for i, (label, relpath, probe) in enumerate(CASES):
        before = load(baseline, relpath, scratch, f"b{i}")
        after = load("HEAD", relpath, scratch, f"a{i}")

        def run(mod):
            if mod is None:
                return "n/a"
            try:
                return "pass" if probe(mod) else "FAIL"
            except Exception:
                return "error"

        b, a = run(before), run(after)
        if b in ("FAIL", "error") and a == "pass":
            verdict = "pinned"
        elif b == a == "pass":
            verdict = "NOT PINNED — passes against the old code too"
            unpinned += 1
        else:
            verdict = f"{b} -> {a}"
        print(f"{label:<38}{b:>12}{a:>8}   {verdict}")
    print(f"\n{len(CASES) - unpinned}/{len(CASES)} pinned")
    return 1 if unpinned else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
