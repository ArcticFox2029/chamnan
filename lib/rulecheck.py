"""Rules that a tool can verify, instead of rules the model has to keep remembering.

Instruction adherence decays. Models are measured 39% worse and 112% less reliable in multi-turn
settings than on the same task single-turn (Laban et al. 2025), and adherence to an instruction
given in an earlier turn falls monotonically with turn count -- o1-preview from 88% to 71% between
the first and third turn on Multi-IF. The decay shape differs by model (linear for claude-sonnet-4,
exponential for others) but the direction does not.

A rule injected once at session start is exactly the instruction those studies measure decaying. The
engineering answer is not to inject it harder. It is to stop relying on the model remembering, and
have something check the repository instead.

So a rule may carry an optional trailer:

    **Check:** present `PATTERN` in `GLOB`
    **Check:** absent `PATTERN` in `GLOB`

PATTERN is a plain regular expression and GLOB is a path pattern relative to the repository root.
`present` means the rule is upheld while at least one match exists; `absent` means it is upheld
while none does. A rule with no Check is unchanged and unaffected -- most rules are about judgement
and cannot be reduced to a grep, which is the reason this is optional and always will be.

Deliberately narrow. It reports; it never edits, and it never fails a command. A rule whose check
cannot run (bad pattern, glob matching nothing) is reported as UNVERIFIABLE rather than as broken,
because "I could not check" and "this is violated" are different facts and collapsing them is how a
check becomes noise that gets ignored.
"""
import re
from pathlib import Path

CHECK = re.compile(r"^\*\*Check:\*\*\s+(present|absent)\s+`(.+?)`\s+in\s+`(.+?)`\s*$", re.M)

# Bounded on purpose: a rule check runs at session start, and a glob that matches the whole tree
# would turn a health report into a reason to uninstall.
MAX_FILES = 400
MAX_BYTES = 400_000


def parse(text):
    """Every Check trailer in one rule's text, as (mode, pattern, glob)."""
    return [(m.group(1), m.group(2), m.group(3)) for m in CHECK.finditer(text)]


def _matches(root, pattern, glob):
    """(files_scanned, files_matching) or None when the check cannot be run at all."""
    try:
        rx = re.compile(pattern)
    except re.error:
        return None
    try:
        paths = [p for p in sorted(root.glob(glob)) if p.is_file()][:MAX_FILES]
    except (ValueError, OSError):
        return None
    if not paths:
        return None
    hits = 0
    for p in paths:
        try:
            if p.stat().st_size > MAX_BYTES:
                continue
            if rx.search(p.read_text(encoding="utf-8", errors="replace")):
                hits += 1
        except OSError:
            continue
    return len(paths), hits


def run(root, rules):
    """Evaluate every rule's checks. `rules` is [(title, text), ...].

    Returns [(title, status, detail)] with status in {"holds", "BROKEN", "unverifiable"}.
    """
    out = []
    for title, text in rules:
        for mode, pattern, glob in parse(text):
            got = _matches(Path(root), pattern, glob)
            if got is None:
                out.append((title, "unverifiable",
                            f"nothing to check: `{glob}` matched no readable file, "
                            f"or `{pattern}` is not a valid pattern"))
                continue
            scanned, hits = got
            ok = hits > 0 if mode == "present" else hits == 0
            if ok:
                out.append((title, "holds",
                            f"{mode} `{pattern}` in `{glob}` — {hits}/{scanned} file(s)"))
            else:
                out.append((title, "BROKEN",
                            f"expected {mode} `{pattern}` in `{glob}`, "
                            f"found {hits} match(es) across {scanned} file(s)"))
    return out


def line(results):
    """One line for the injected block. Silent when every check holds and none is unverifiable.

    Silence is the point. A session that reads "all rules hold" every time learns to skip the line,
    and then does not read it on the day it says something else.
    """
    broken = [r for r in results if r[1] == "BROKEN"]
    if not broken:
        return ""
    named = "; ".join(f"**{t}** — {d}" for t, _, d in broken[:3])
    more = f" _(+{len(broken) - 3} more)_" if len(broken) > 3 else ""
    return (f"\n_⚠ {len(broken)} recorded rule(s) no longer hold against the tree: "
            f"{named}{more}. Verified mechanically, not remembered._\n")
