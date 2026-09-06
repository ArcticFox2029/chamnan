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
    **Check:** present `PATTERN` in every `GLOB`
    **Check:** absent `PATTERN` in every `GLOB`

PATTERN is a plain regular expression and GLOB is a path pattern relative to the repository root.
Without `every`, both are AGGREGATE across the whole glob: `present` is upheld while at least one
file matches, `absent` while none do. With `every`, they are per-file: `present ... in every`
requires each file to match and `absent ... in every` requires none of them to, and the failure
message names the files rather than a count. Say `every` whenever the rule means "each one" -- the
aggregate form will report a violated per-file invariant as holding, which is the trap this grammar
word exists to remove.

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

# 🐛 [2026-09-06] `present X in GLOB` is an AGGREGATE test -- upheld while at least one file in the
# glob matches -- and that is the wrong quantifier for the commonest real rule there is. Written the
# natural way, "every service config declares a timeout" became
# ``**Check:** present `timeout:` in `config/*.yaml` ``; adding a second config with no timeout at
# all, the exact regression the rule exists to prevent, still reported `holds — 1/2 file(s)`,
# because one OTHER file matched (R8 agent 3). This module's own docstring says collapsing "I could
# not check" into "this is violated" is how a check becomes noise; collapsing "violated" into
# "holds" is the same failure and worse, and it had no name here.
#
# `in every GLOB` is the per-file quantifier. The aggregate form is unchanged, so no existing rule
# moves; a rule author who means "each one" can now say it, and the BROKEN message names the files
# that fail rather than a count they have to go and diff themselves.
CHECK = re.compile(
    r"^\*\*Check:\*\*\s+(present|absent)\s+`(.+?)`\s+in\s+(every\s+)?`(.+?)`\s*$", re.M)

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
    """Every Check trailer in one rule's text, as (mode, pattern, glob, per_file)."""
    return [(m.group(1), m.group(2), m.group(4), bool(m.group(3)))
            for m in CHECK.finditer(text)]


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


# A frozenset, not the string "+*{": `ch in "+*{"` answers True for the EMPTY string, and this
# scanner asks the question about the character after a `)`, which is "" at the end of a pattern.
_QUANTIFIERS = frozenset("+*{")


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
            # 🐛 [2026-09-06] `nxt` is "" at the end of the pattern, and `"" in "+*{"` is TRUE --
            # the empty string is a substring of every string. So a group holding any quantifier
            # and CLOSING the pattern read as a quantified group over a quantifier: `(\d{4})` and
            # `(\d+)`, the most ordinary regexes there are, were refused outright and every
            # `**Check:**` rule written that way had silently never run. A frozenset cannot be
            # asked this question wrongly. Found while checking the sixth ReDoS family's fix for
            # false positives -- the leak and the over-refusal sat in adjacent lines.
            nxt = pattern[i + 1] if i + 1 < n else ""
            if had and nxt in _QUANTIFIERS:
                return True
            if inner and (had or nxt in _QUANTIFIERS):
                inner[-1] = True
        elif ch in _QUANTIFIERS and inner:
            inner[-1] = True
        i += 1
    return False
# The other classic shape, and the one the pattern above is blind to: ambiguous ALTERNATION with
# no inner quantifier at all -- `(a|a)*`, `(x|xy)+`, `(\s|\s)*`. Measured here: `(a|a)*$` against
# 20 identical characters took 0.25s, 24 took 4.2s, and 28 had not finished after five seconds.
# It sailed straight through a guard whose whole reason for existing is that hang.
_AMBIGUOUS_ALTERNATION = re.compile(r"\(([^()|]+(?:\|[^()|]+)+)\)\s*[+*{]")
# 🐛 [2026-09-06] The fifth family, and the module's own comment below predicted one. The same
# alternation with NO quantifier at all -- `(a|aa)(a|aa)(a|aa)…` -- is invisible to every guard
# here, because all four require either a nested quantifier or a trailing `+`/`*`/`{` on the group.
# Concatenation supplies the exponent instead: k groups placed side by side give the backtracking
# engine 2^k parse paths to try when the tail fails. Measured against Python's own `re`, with 52
# `a` characters and a trailing `b` that never matches: k=14 0.004s, k=16 0.018s, k=18 0.078s,
# k=20 0.338s, k=26 over 15 seconds -- roughly 4.4x per +2, which is 2^k. Reproduced end to end
# against the real SessionStart hook, which hung indefinitely on a 157-character `**Check:**` line
# in one committed rule file (R11 agent 2).
_ANY_ALTERNATION = re.compile(r"\(([^()|]+(?:\|[^()|]+)+)\)")


# 🐛 [2026-09-06] Both alternation detectors captured a group's RAW content and split it on `|`
# straight away, so `(?:a|a)*` produced the branches `["?:a", "a"]` -- not duplicates, no prefix
# relation, and the guard said the pattern was safe. `(?P<x>a|a)*` and `(?i:a|a)*` slipped through
# the same way. That is not an exotic shape: a non-capturing group is what somebody writes when
# they do not want the capture, so this family is MORE likely to be written by accident than the
# five already caught. Measured on the real engine: `(?:a|a)*$` against 20 `a`s and a `b` takes
# 0.088s, 24 takes 1.381s, 26 takes 5.500s, while the capturing twin was refused outright
# (R12 agent 2).
#
# Stripped rather than matched, and stripped in ONE place both detectors go through -- the two are
# deliberately the same question asked about differently-quantified groups, and this repository's
# most-repeated defect is a fix applied to one of a matched pair.
_GROUP_PREFIX = re.compile(r"^\?(?:P<[^>]*>|P=[^|)]*|[aiLmsux]*(?:-[aiLmsux]+)?:|:|=|!|<[=!]|>)")


def _branches(content):
    """The alternation's branches, with any group modifier dropped off the first one.

    `(?:`, `(?P<name>`, `(?i:`, a lookaround -- every one of them puts characters at the front of
    the captured content that belong to the GROUP and not to the first branch. Leaving them there
    made two branches that are the same text look different.
    """
    return _GROUP_PREFIX.sub("", content, count=1).split("|")


def _branches_overlap(branches):
    """True when two branches of one alternation can consume the same text.

    Duplicates are the unmistakable case; a prefix relation (`(x|xy)`) is the same hazard, because
    the engine has two ways to consume the same input and must try both.
    """
    if len(set(branches)) != len(branches):
        return True
    for i, a in enumerate(branches):
        for b in branches[i + 1:]:
            if a.startswith(b) or b.startswith(a):
                return True
    return False


def _ambiguous(pattern):
    """True for an alternation whose branches can match the same text under a quantifier."""
    return any(_branches_overlap(_branches(m.group(1)))
               for m in _AMBIGUOUS_ALTERNATION.finditer(pattern))


def _overlapping_alternations(pattern):
    """How many alternation groups in `pattern` have branches that can match the same text.

    Quantified or not. ONE of these is a single choice point and costs nothing; what turns the
    curve is how many of them the engine has to try together, and concatenation multiplies them
    exactly as a quantifier does. An alternation whose branches are distinct -- `(GET|POST|PUT)`,
    which is what a real `**Check:**` pattern looks like when it has one at all -- is not counted,
    because the engine picks one branch per position and never comes back to it.
    """
    return sum(1 for m in _ANY_ALTERNATION.finditer(pattern)
               if _branches_overlap(_branches(m.group(1))))


# 🐛 The third shape, and the one all three guards above are blind to by construction: they every
# one require a literal `(` before they will look at a pattern, and a flat chain of quantifiers over
# the same atom needs no brackets at all. `a*a*a*a*a*a*a*a*a*a*a*a*b` is 25 characters, passes all
# three, and Python's `re` takes 0.8s on sixteen `a`s -- doubling with each further character, so a
# line of ordinary length never returns. A `**Check:**` trailer arrives with a clone and is compiled
# and run at every session start.
#
# Measured, `('a*' * k) + 'b'` against inputs up to 80 characters:
#
#     k = 3   0.004s        k = 6    2.99s
#     k = 4   0.081s        k = 7   27.43s
#     k = 5   1.311s        k = 8   12.24s (at only 40 characters)
#
# So the cap is on the COUNT of unbounded quantifiers, which is what turns the curve, and it is set
# at 4 -- the last value whose worst case is a rounding error. That is generous against real use:
# every `**Check:**` pattern found in the wild is a literal grep with ZERO quantifiers, which is the
# module's own docstring restated ("most rules are about judgement and cannot be reduced to a grep").
#
# `?` is deliberately not counted. The classic `a?a?a?…aaa` blowup does not reproduce on CPython --
# measured flat at 0.000s out to twenty -- and counting it would refuse ordinary patterns to defend
# against a hazard this engine does not have.
#
# This narrows the hole; it does not prove it closed. Enumerating pathological shapes by reading the
# pattern text is reasoning about the engine's own runtime, so a fifth family nobody has found yet
# is likely. A wall-clock ceiling was the obvious backstop and was measured before being rejected:
# `re` cannot be interrupted in-process, `signal.alarm` is POSIX-only, main-thread-only and holds a
# single global slot, and a subprocess costs 139 ms per spawn against a hook that runs in 750 ms and
# fires up to 82 times a session -- up to 23 seconds a session, on every repository that uses the
# feature, to defend against a regex somebody would have to commit on purpose. Refusing the shape is
# free and is what this module already does with the other three.
MAX_QUANTIFIERS = 4


def _too_many_quantifiers(pattern):
    r"""True when `pattern` carries more unbounded quantifiers than backtracking can be trusted with.

    Scanned rather than counted with a regex, for the same reason as the group scanner above: an
    escaped `\*` is a literal asterisk and a `[+*]` is a class of two characters, and neither is a
    quantifier. `{` counts, because `{2,}` repeats without an upper bound just as `+` does.
    """
    n, i, end = 0, 0, len(pattern)
    while i < end:
        ch = pattern[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "[":                      # a character class: quantifier characters are literal
            i += 1
            if i < end and pattern[i] == "^":
                i += 1
            if i < end and pattern[i] == "]":
                i += 1
            while i < end and pattern[i] != "]":
                i += 2 if pattern[i] == "\\" else 1
            i += 1
            continue
        if ch in "*+{":
            n += 1
            if n > MAX_QUANTIFIERS:
                return True
        i += 1
    return False


def _matches(root, pattern, glob):
    """(files_scanned, files_matching, files_not_matching), or None when it cannot run."""
    # The count is on CHOICE POINTS, not on any one shape: an unbounded quantifier and an
    # overlapping alternation are the same hazard to a backtracking engine, and the fifth family
    # was found by supplying the exponent through concatenation rather than through repetition.
    # Counting them against one budget closes that dimension for every arrangement of them --
    # nested, quantified, or side by side -- instead of adding a fifth shape and inviting a sixth.
    if (_NESTED_QUANTIFIER.search(pattern) or _quantified_group_over_quantifier(pattern)
            or _ambiguous(pattern) or _too_many_quantifiers(pattern)
            or _overlapping_alternations(pattern) > MAX_QUANTIFIERS):
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
    hits, missing = 0, []
    for p in paths:
        try:
            if p.stat().st_size > MAX_BYTES:
                continue
            if rx.search(p.read_text(encoding="utf-8-sig", errors="replace")):
                hits += 1
            else:
                missing.append(p)
        except OSError:
            continue
    # The files that did NOT match come back too, so a per-file check can name them instead of
    # handing the reader a count and leaving them to diff the glob themselves.
    return len(paths), hits, missing


def run(root, rules):
    """Evaluate every rule's checks. `rules` is [(title, text), ...].

    Returns [(title, status, detail)] with status in
    {"holds", "BROKEN", "unverifiable", "malformed"}.
    """
    out = []
    for title, text in rules:
        for mode, pattern, glob, per_file in parse(text):
            got = _matches(Path(root), pattern, glob)
            if got is None:
                out.append((title, "unverifiable",
                            f"nothing to check: `{glob}` matched no readable file, "
                            f"or `{pattern}` is not a valid pattern"))
                continue
            scanned, hits, missing = got
            where = f"every `{glob}`" if per_file else f"`{glob}`"
            if per_file:
                ok = hits == scanned if mode == "present" else hits == 0
                offenders = missing if mode == "present" else [
                    q for q in Path(root).glob(glob) if q.is_file() and q not in missing]
            else:
                ok = hits > 0 if mode == "present" else hits == 0
                offenders = []
            if ok:
                out.append((title, "holds",
                            f"{mode} `{pattern}` in {where} — {hits}/{scanned} file(s)"))
            elif per_file:
                # Named, not counted: the whole reason to say `every` is that the reader wants to
                # know WHICH file broke it, and a count is the thing they would have to go and
                # work out for themselves.
                _named = ", ".join(f"`{q.name}`" for q in sorted(offenders)[:4])
                _more = len(offenders) - 4
                out.append((title, "BROKEN",
                            f"expected {mode} `{pattern}` in {where} — {hits}/{scanned} file(s); "
                            + (f"{_named}" + (f" +{_more} more" if _more > 0 else "")
                               if _named else "no file matched")))
            else:
                out.append((title, "BROKEN",
                            f"expected {mode} `{pattern}` in {where}, "
                            f"found {hits} match(es) across {scanned} file(s)"))
        # A distinct status from "unverifiable": that one means "the grammar is fine, the check
        # just can't run right now" (a glob matching nothing yet). This means the grammar itself
        # never parsed, so the check has NEVER run -- closer in spirit to BROKEN, but reported
        # separately so it isn't confused with a rule the tree actually violates.
        for bad_line in malformed(text):
            out.append((title, "malformed",
                        f"looks like an attempted **Check:** trailer but does not match the "
                        f"required form (present|absent `PATTERN` in [every] `GLOB`): `{bad_line}`"))
    return out


def contradictions(rules):
    """Pairs of rules whose Check trailers point at the same thing and demand opposite outcomes.

    🐛 [2026-09-06] `memory.py` catches two SYNTACTIC self-contradictions -- a git merge marker
    inside one file, and two filenames colliding by case -- and nothing at all catches two cleanly
    written rules that flatly disagree. "Always run the full suite before every commit" and "Never
    run the test suite locally" are both injected, back to back, as equally authoritative fact
    (R8 agent 3).
    #
    A general contradiction detector needs judgement a grep cannot have, and is not what this is.
    This is the one shape the plugin already holds the data for: two trailers with the same pattern
    and the same glob, one saying `present` and the other `absent`. They cannot both hold, so one
    of them is already reported BROKEN every session -- what was missing is the REASON, which is
    the other rule, and which no amount of staring at the broken one reveals.

    Returns [(title_a, title_b, pattern, glob)], each pair once, in a stable order.
    """
    seen = {}
    for title, text in rules:
        for mode, pattern, glob, _per_file in parse(text):
            seen.setdefault((pattern, glob), {}).setdefault(mode, []).append(title)
    out = []
    for (pattern, glob), by_mode in sorted(seen.items()):
        for a in sorted(set(by_mode.get("present", []))):
            for b in sorted(set(by_mode.get("absent", []))):
                # A rule that contradicts ITSELF -- both trailers in one file -- is a real mistake
                # too, and naming it once is clearer than naming it as a pair with itself.
                out.append((a, b, pattern, glob))
    return out


def line(results, clashes=()):
    """One line for the injected block. Silent when every check holds and none is unverifiable.

    Silence is the point. A session that reads "all rules hold" every time learns to skip the line,
    and then does not read it on the day it says something else.

    `clashes` is `contradictions()`'s output. Optional and defaulting to empty so every existing
    caller keeps working unchanged; a caller that has the rules to hand should pass it, because a
    contradiction is the REASON behind a BROKEN line rather than a second complaint about it.
    """
    broken = [r for r in results if r[1] == "BROKEN"]
    # 🐛 A typo in a `**Check:**` trailer (wrong case, "for" instead of "in", a missing backtick)
    # made `parse()` find nothing, which is exactly what a rule with no Check trailer at all also
    # produces -- so the typo silently never ran, forever, and looked identical to "this rule isn't
    # meant to be mechanically checked." Reported here under its own line so it can't be confused
    # with either "holds" or "not meant to be checked."
    malformed_ = [r for r in results if r[1] == "malformed"]
    if not broken and not malformed_ and not clashes:
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
    if clashes:
        named = "; ".join(
            f"**{mdblock.as_quoted(a)}** vs **{mdblock.as_quoted(b)}** "
            f"(`{mdblock.as_quoted(pattern, 40)}` in `{mdblock.as_quoted(glob, 40)}`)"
            for a, b, pattern, glob in clashes[:3])
        more = f" _(+{len(clashes) - 3} more)_" if len(clashes) > 3 else ""
        parts.append(f"⚠ {len(clashes)} pair(s) of recorded rules demand opposite things about the "
                     f"same files, so one of them cannot be met: {named}{more}. One of the pair is "
                     f"wrong; deciding which is not something this can do for you.")
    return "\n_" + "_\n\n_".join(parts) + "_\n"
