"""50 randomised skill trees, each with a known answer, run against `skill_overlap.overlaps`.

Both directions, because a detector that returns everything passes a one-directional check just as
easily as a correct one: every planted overlap must be FOUND, and every pair that was deliberately
left clean must NOT be reported. The population is asserted, not a sampled instance -- the set the
detector returns is compared to the set that was planted, as a set.
"""

import json
import random
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import skill_overlap as so

PASS = FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"FAIL: {name}")


BODY = ("Scope: {n}. This skill covers {n} and the traps it has hit.\n\n"
        "It exists because the same mistake was made three times.\n"
        "Read it before starting that kind of work, not afterwards.\n"
        "Related files: lib/{n}.py, tests/test_{n}.py\n")


def build(seed):
    """One random workspace. Returns (root, home, expected) where expected is a set of
    (kind, name) that MUST be reported and nothing else may be."""
    rnd = random.Random(seed)
    tmp = Path(tempfile.mkdtemp(prefix=f"skov{seed}_"))
    root, home = tmp / "repo", tmp / "home"
    (root / ".chamnan" / "skills").mkdir(parents=True)
    cache = home / ".claude" / "plugins" / "cache" / "acme" / "acme" / "2.0.0"
    snap = home / ".claude" / "plugins" / "marketplaces" / "acme"
    (cache / "skills").mkdir(parents=True)
    (snap / "skills").mkdir(parents=True)
    (home / ".claude" / "plugins").joinpath("installed_plugins.json").write_text(json.dumps(
        {"version": 2, "plugins": {"acme@acme": [{"scope": "user", "installPath": str(cache),
                                                  "version": "2.0.0"}]}}))

    expected = set()
    names = [f"task_{i}" for i in range(rnd.randint(3, 9))]
    for n in names:
        (root / ".chamnan" / "skills" / f"{n}.md").write_text(f"# Skill: {n}\n\n" + BODY.format(n=n))

    shipped = [f"plug_{i}" for i in range(rnd.randint(2, 6))]
    for n in shipped:
        d = cache / "skills" / n
        d.mkdir()
        text = f"---\ndescription: does {n}\n---\n\n" + BODY.format(n=n)
        d.joinpath("SKILL.md").write_text(text)
        s = snap / "skills" / n
        s.mkdir()
        # By default the snapshot agrees with the loaded copy. Divergence is planted, not incidental.
        s.joinpath("SKILL.md").write_text(text)

    # plant: a snapshot that drifted from the loaded plugin
    if shipped and rnd.random() < 0.6:
        n = rnd.choice(shipped)
        p = snap / "skills" / n / "SKILL.md"
        p.write_text(p.read_text().replace("---\n\n", "---\nextra: true\n\n", 1) + "\ndrifted\n")
        expected.add(("divergent", n))

    # plant: a workspace file answering to a shipped skill's own name
    if shipped and rnd.random() < 0.5:
        n = rnd.choice([s for s in shipped if ("divergent", s) not in expected] or [None])
        if n:
            (root / ".chamnan" / "skills" / f"{n}.md").write_text(f"# Skill: {n}\n\nsomething else\n")
            expected.add(("divergent", n))   # different bytes -> divergent wins over shadowed

    # plant: a workspace file that restates a shipped skill verbatim under its own name
    if shipped and rnd.random() < 0.5:
        src = rnd.choice(shipped)
        n = f"copy_of_{src}"
        core = (cache / "skills" / src / "SKILL.md").read_text()
        (root / ".chamnan" / "skills" / f"{n}.md").write_text(f"# Skill: {n}\n\n{core}\n")
        expected.add(("restates", n))

    return root, home, expected


def main():
    for seed in range(50):
        root, home, expected = build(seed)
        got = {(o["kind"], o["name"]) for o in so.overlaps(root, home)}
        check(f"seed {seed}: found every planted overlap", expected <= got)
        check(f"seed {seed}: reported nothing that was not planted", got <= expected)
        shutil.rmtree(root.parent, ignore_errors=True)

    # mutation, the other direction: a detector that answers "everything" must not pass above
    root, home, expected = build(101)
    everything = {("divergent", p.stem) for p in (root / ".chamnan" / "skills").glob("*.md")}
    check("a detector that reported every skill would be caught", not (everything <= expected)
          or not everything)
    shutil.rmtree(root.parent, ignore_errors=True)

    # a tree with no plugins at all must be silent, not crash
    tmp = Path(tempfile.mkdtemp(prefix="skov_empty_"))
    (tmp / "repo" / ".chamnan" / "skills").mkdir(parents=True)
    check("no plugin manifest -> no findings, no exception", so.overlaps(tmp / "repo", tmp / "home") == [])
    shutil.rmtree(tmp, ignore_errors=True)

    print(f"{PASS}/{PASS + FAIL} checks passed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
