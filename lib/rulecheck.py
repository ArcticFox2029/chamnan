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
import mdblock
import re

from pathlib import Path

CHECK = re.compile(r"^\*\*Check:\*\*\s+(present|absent)\s+`(.+?)`\s+in\s+`(.+?)`\s*$", re.M)

# 🐛 CHECK's grammar is exact: wrong case (`**check:**`), the wrong keyword ("for" instead of
# "in"), a missing backtick -- any of it makes `CHECK.finditer()` find nothing, and `parse()`
# returns [] exactly as it would for a rule that never had a Check trailer at all. A typo and "not
# meant to be checked" were indistinguishable in the one line a session ever sees (`line()`),
# which is worse than the check simply failing: a failing check says the rule is broken, a typo'd
# one says nothing and looks like a check that passed. `_CHECK_LIKE` is deliberately loose --
# case-insensitive, no keyword or backtick requirements -- so it catches an attempted trailer that
# CHECK's strict grammar rejects, without trying to guess what was meant.
_CHECK_LIKE = re.compile(r"^\*\*check:\*\*.*$", re.M | re.I)

# Bounded on purpose: a rule check runs at session start, and a glob that matches the whole tree
# would turn a health report into a reason to uninstall.
MAX_FILES = 400
MAX_BYTES = 400_000


def parse(text):
    """Every Check trailer in one rule's text, as (mode, pattern, glob)."""
    return [(m.group(1), m.group(2), m.group(3)) for m in CHECK.finditer(text)]


def malformed(text):
    """Lines that look like an attempted `**Check:**` trailer but do not match CHECK's grammar.

    Stripped on both sides before comparing: `CHECK`'s trailing `\\s*$` can match right up to (but
    not past) the line's own newline, and comparing an unstripped `_CHECK_LIKE` match against an
    unstripped `CHECK` match must not report a well-formed trailer as malformed just because the
    two patterns consumed a different amount of trailing whitespace on the same line.
    """
    well_formed = {m.group(0).strip() for m in CHECK.finditer(text)}
    return [m.group(0).strip() for m in _CHECK_LIKE.finditer(text)
            if m.group(0).strip() not in well_formed]


# A quantified group that is itself quantified -- (a+)+, (\w*)*, (x|y+)* -- is the classic shape
# that makes Python's backtracking engine exponential. This is not a hypothetical for chamnan: a
# rule's `**Check:**` trailer is a pattern someone writes by hand, compiled and run against every
# matching file at EVERY session start. Measured on this machine with `(a+)+$`: 24 characters of
# input took 2.15s, and 30 characters had to be killed after two minutes. One rule pasted from a
# search result would hang every future session in that repository, permanently, with no error.
#
# `re` has no timeout and this package may not add a dependency, so the guard is at compile time:
# a pattern of this shape is refused and the check reports UNVERIFIABLE rather than running. That
# is the same outcome as a syntactically invalid pattern, which the caller already handles, and
# unverifiable is already kept distinct from BROKEN.
# 🐛 `[^()]*` cannot look inside a group that contains another group, so `((a+)b?)+$`,
# `(([a-z])+)+$` and `(?:(a+))+$` all passed the guard and then took 3.1s, 3.6s and 7.6s on
# twenty-odd characters, growing exponentially. A `**Check:**` trailer arrives with a clone and is
# compiled and run at EVERY SESSION START, and `re` has no timeout — the hang this guard exists to
# prevent, reachable through one extra pair of brackets.
#
# Two patterns now: the original flat shape, and a quantified group that contains any quantifier
# anywhere inside it, however deeply nested. The second is broader than strictly necessary — it
# will refuse some safe patterns — and that is the right direction for a check whose failure mode
# is a session that never starts.
_NESTED_QUANTIFIER = re.compile(r"\([^()]*[+*][^()]*\)\s*[+*{]")


def _quantified_group_over_quantifier(pattern):
    """True when a quantified group contains a quantifier anywhere inside it, at any depth.

    Scanned rather than matched. A regex cannot see into arbitrarily nested brackets, which is why
    the flat pattern above missed `((a+)b?)+`, `(([a-z])+)+` and `(?:(a+))+` — 3.1s, 3.6s and 7.6s
    on twenty-odd characters, growing exponentially. Escapes and character classes are skipped, so
    a backslash-escaped paren is a literal one and `[+*]` is a class of two characters rather than
    two quantifiers.
    """
    depth, i, n = 0, 0, len(pattern)
    starts, inner = [], []
    while i < n:
        ch = pattern[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "[":                      # a character class: quantifier characters are literal
            i += 1
            if i < n and pattern[i] == "^":
                i += 1
            if i < n and pattern[i] == "]":
                i += 1
            while i < n and pattern[i] != "]":
                i += 2 if pattern[i] == "\\" else 1
            i += 1
            continue
        if ch == "(":
            starts.append(i)
            inner.append(False)
            depth += 1
        elif ch == ")" and depth:
            depth -= 1
            starts.pop()
            had = inner.pop()
            nxt = pattern[i + 1] if i + 1 < n else ""
            if had and nxt in "+*{":
                return True
            if inner and (had or nxt in "+*{"):
                inner[-1] = True
        elif ch in "+*{" and inner:
            inner[-1] = True
        i += 1
    return False
# The other classic shape, and the one the pattern above is blind to: ambiguous ALTERNATION with
# no inner quantifier at all -- `(a|a)*`, `(x|xy)+`, `(\s|\s)*`. Measured here: `(a|a)*$` against
# 20 identical characters took 0.25s, 24 took 4.2s, and 28 had not finished after five seconds.
# It sailed straight through a guard whose whole reason for existing is that hang.
_AMBIGUOUS_ALTERNATION = re.compile(r"\(([^()|]+(?:\|[^()|]+)+)\)\s*[+*{]")


def _ambiguous(pattern):
    """True for an alternation whose branches can match the same text under a quantifier."""
    for m in _AMBIGUOUS_ALTERNATION.finditer(pattern):
        branches = m.group(1).split("|")
        # Duplicates are the unmistakable case; a prefix relation ((x|xy)+) is the same hazard,
        # because the engine has two ways to consume the same input and must try both.
        if len(set(branches)) != len(branches):
            return True
        for i, a in enumerate(branches):
            for b in branches[i + 1:]:
                if a.startswith(b) or b.startswith(a):
                    return True
    return False


def _matches(root, pattern, glob):
    """(files_scanned, files_matching) or None when the check cannot be run at all."""
    if (_NESTED_QUANTIFIER.search(pattern) or _quantified_group_over_quantifier(pattern)
            or _ambiguous(pattern)):
        return None
    try:
        rx = re.compile(pattern)
    except re.error:
        return None
    try:
        paths = [p for p in sorted(root.glob(glob)) if p.is_file()][:MAX_FILES]
    except (ValueError, OSError):
        return None
    # Containment, checked here rather than trusted from the glob. `root.glob()` follows `..`
    # segments, so a rule whose Check trailer read ``in `../../../../etc/hosts` `` read a real file
    # outside the repository and reported its match count into the session -- a working oracle for
    # any file the process can open, from a rule file that arrives with a clone. It bypassed
    # redact's never-open list too, which is why that is consulted as well: this module is the one
    # place a path in repository text turns into an open().
    base = root.resolve()
    inside = []
    for q in paths:
        try:
            if q.resolve().parent == base or base in q.resolve().parents:
                # Imported here, not at module scope. `pointer._governs()` reaches `parse()`
                # on every Read, Edit and Write and never comes near this branch, and
                # `import redact` measured 15 ms of that hot path for nothing.
                import redact
                if not redact.is_never_opened(q):
                    inside.append(q)
        except (OSError, RuntimeError):
            continue
    paths = inside
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

    Returns [(title, status, detail)] with status in
    {"holds", "BROKEN", "unverifiable", "malformed"}.
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
        # A distinct status from "unverifiable": that one means "the grammar is fine, the check
        # just can't run right now" (a glob matching nothing yet). This means the grammar itself
        # never parsed, so the check has NEVER run -- closer in spirit to BROKEN, but reported
        # separately so it isn't confused with a rule the tree actually violates.
        for bad_line in malformed(text):
            out.append((title, "malformed",
                        f"looks like an attempted **Check:** trailer but does not match the "
                        f"required form (present|absent `PATTERN` in `GLOB`): `{bad_line}`"))
    return out


def line(results):
    """One line for the injected block. Silent when every check holds and none is unverifiable.

    Silence is the point. A session that reads "all rules hold" every time learns to skip the line,
    and then does not read it on the day it says something else.
    """
    broken = [r for r in results if r[1] == "BROKEN"]
    # 🐛 A typo in a `**Check:**` trailer (wrong case, "for" instead of "in", a missing backtick)
    # made `parse()` find nothing, which is exactly what a rule with no Check trailer at all also
    # produces -- so the typo silently never ran, forever, and looked identical to "this rule isn't
    # meant to be mechanically checked." Reported here under its own line so it can't be confused
    # with either "holds" or "not meant to be checked."
    malformed_ = [r for r in results if r[1] == "malformed"]
    if not broken and not malformed_:
        return ""
    # Rule titles and their `**Check:**` trailers are written by whoever wrote the repository, and
    # this line prints them in chamnan's own voice, outside the fence. Made inert first; the caller
    # scrubs the assembled block.
    parts = []
    if broken:
        named = "; ".join(f"**{mdblock.as_quoted(t)}** — {mdblock.as_quoted(d, 120)}"
                          for t, _, d in broken[:3])
        more = f" _(+{len(broken) - 3} more)_" if len(broken) > 3 else ""
        parts.append(f"⚠ {len(broken)} recorded rule(s) no longer hold against the tree: "
                     f"{named}{more}. Verified mechanically, not remembered.")
    if malformed_:
        named = "; ".join(f"**{mdblock.as_quoted(t)}** — {mdblock.as_quoted(d, 120)}"
                          for t, _, d in malformed_[:3])
        more = f" _(+{len(malformed_) - 3} more)_" if len(malformed_) > 3 else ""
        parts.append(f"⚠ {len(malformed_)} **Check:** trailer(s) do not parse and have never run: "
                     f"{named}{more}. Fix the syntax or the rule is not actually verified.")
    return "\n_" + "_\n\n_".join(parts) + "_\n"
