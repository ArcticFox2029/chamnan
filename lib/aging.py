"""Knowledge aging — against `environments.md`'s declared versions, never against a clock.

A memory entry that says "we are on Postgres 13, so the upsert has to be written this way" stops
being true the day the cluster moves to 17. Nothing about that is visible from the entry's age: a
note written two years ago about a version still in production is perfectly current, and one
written last month about a version replaced last week is already wrong. **Age is not evidence**,
which is why nothing here looks at a date to decide whether knowledge is stale.

What it compares against is `environments.md` — facts a person typed, about environments they knew
(see lib/environments.py). That makes the whole check exactly as trustworthy as that file, and
that is the risk this module is built around rather than around.

**The oracle has to be maintained, or this reports nothing.** An environment nobody has confirmed
in six months is evidence nobody looked, not evidence nothing changed. Treating it as an authority
produces a false all-clear — "your knowledge is current" said on the strength of a file that has
been drifting since January — and a false all-clear is worse than no check at all, because it
stops somebody looking. So `check()` uses ONLY environments whose `Checked:` date is fresh, and
when none are, it refuses and says why instead of returning an empty finding list that reads like
a pass.

Three outcomes, not two, and the third is the honest one:

    flagged        the entry names a version no FRESH environment declares, and no cold one
                   declares it either — the clearest signal available
    unverifiable   the only environment declaring that version has gone cold, so nobody knows
    silent         the version matches something declared and fresh, or the name is not declared
                   in environments.md at all

That last clause is the noise control. `_VERSION` will happily read "issue 13" or "port 8080" as a
version claim, and filtering to names environments.md actually declares is what keeps those out —
so an entry is only ever measured against a subject somebody chose to declare.

**Equality only, never ordering.** `3.9` and `3.11` do not compare as numbers when read as text,
and reading them as tuples raises its own questions (is `1.0` newer than `1.0.0`?). Nothing here
needs an ordering: "does this claim match something declared" is answerable with equality, and a
version comparator that is subtly wrong about `3.9` vs `3.11` would be wrong in exactly the case
Python repositories hit most.
"""
import re

# Same shape environments.py parses declarations with: a name, then a dotted or plain number.
_CLAIM = re.compile(r"([A-Za-z][\w.+-]*)\s+v?(\d+(?:\.\d+)*)")

# 🐛 [2026-09-06] The word immediately before the number is not always the software's name.
# "postgres version 16" read as `("version", "16")`, and both sides of this feature were wrong in
# opposite directions because of it: `chamnan-env set --versions "postgres version 16"` declared an
# environment running `version: 16` and nothing running postgres, while a memory entry phrased
# "Postgres version 13" produced a claim about `version` that no declared name ever matched, so it
# was silently never checked and `chamnan-age` reported an all-clear (R11 agent 3).
#
# Removed rather than special-cased in the pattern, and removed in ONE place used by both sides --
# the declaration parser and the claim parser are deliberately the same shape, and a fix applied to
# one of a matched pair is this repository's most-repeated defect. A bare "version 16" with no name
# before it correctly yields nothing at all.
_FILLER_BEFORE_NUMBER = re.compile(
    r"\b(?:versions?|v|ver|rev|revision|release|build)\s+(?=v?\d)", re.I)


def version_pairs(text):
    """[(name, version)] for every `name <number>` in `text`, ignoring the word "version".

    Shared by `environments.entries()` (what an environment DECLARES) and `claims_in` below (what a
    memory entry CLAIMS), so the two cannot drift into disagreeing about what a version claim is.
    """
    return _CLAIM.findall(_FILLER_BEFORE_NUMBER.sub("", text or ""))


def claims_in(text):
    """[(name, version)] every version-shaped claim in one entry, lowercased by name.

    Deliberately generous — filtering happens against the declared names in `check()`, not here.
    A parser that tried to be selective at this stage would have to guess what counts as a version
    claim without knowing what the repository cares about, and the declared list already knows.
    """
    return [(n.lower(), v) for n, v in version_pairs(text)]


def _covers(declared, claimed):
    """True when a claim is an instance of what the environment declares.

    Equality alone is right about the direction and wrong about precision. An environment declaring
    `python 3.11` is declaring a series, and a lesson saying `python 3.11.2` is talking about a
    member of it -- flagging that as a contradiction is a false positive on exactly the kind of
    entry the check exists to protect. Prefix on the dotted components, and only in that direction:
    a claim of `3.11` against a declared `3.11.2` is NOT covered, because the entry is then vaguer
    than the environment and the vagueness is the thing worth noticing.
    """
    if declared == claimed:
        return True
    d, c = declared.split("."), claimed.split(".")
    return len(c) > len(d) and c[:len(d)] == d


def check(root, now=None):
    """(findings, unverifiable, refusal) — the whole result, and `refusal` decides how to read it.

    `refusal` is a string when the check could not honestly run at all, and None when it did. A
    caller must print the refusal rather than the empty list beside it: "no findings" and "no
    check happened" are different answers, and printing the first when the second is true is the
    false all-clear this module exists to avoid.

    `findings` are [(category, filename, name, claimed, declared)] where `declared` is the list of
    (env, version) pairs that fresh environments actually declare for that name.
    `unverifiable` are [(category, filename, name, claimed, cold_env)].
    """
    import environments
    import memory

    envs = environments.entries(root)
    if not envs:
        return [], [], ("no environments declared — `chamnan-env set <name> …` gives this "
                        "something to compare against. Nothing is checked against a clock.")

    stale = dict(environments.stale_environments(root, now=now, envs=envs))
    fresh = [e for e in envs if e["name"] not in stale]
    if not fresh:
        names = ", ".join(sorted(stale))
        return [], [], (f"every declared environment has gone cold ({names}) — nothing here is "
                        f"checked, because an unconfirmed entry is evidence nobody looked, not "
                        f"evidence nothing changed. `chamnan-env check` says what to re-confirm.")

    fresh_versions = {}
    for env in fresh:
        for name, version in env["versions"].items():
            fresh_versions.setdefault(name, []).append((env["name"], version))
    cold_versions = {}
    for env in envs:
        if env["name"] not in stale:
            continue
        for name, version in env["versions"].items():
            cold_versions.setdefault(name, []).append((env["name"], version))

    # A name declared by nobody is not a subject this repository has an opinion on, so a claim
    # about it is left alone entirely -- see the module docstring's noise-control note.
    declared_names = set(fresh_versions) | set(cold_versions)

    findings, unverifiable = [], []
    for category in memory.CATEGORIES:
        for path in memory.entries(root, category):
            try:
                text = path.read_text(encoding="utf-8-sig", errors="replace")
            except OSError:
                continue
            seen = set()
            for name, claimed in claims_in(text):
                if name not in declared_names or (name, claimed) in seen:
                    continue
                seen.add((name, claimed))
                if any(_covers(v, claimed) for _e, v in fresh_versions.get(name, [])):
                    continue
                cold_match = next((e for e, v in cold_versions.get(name, [])
                                   if _covers(v, claimed)), None)
                if cold_match:
                    unverifiable.append((category, path.name, name, claimed, cold_match))
                else:
                    findings.append((category, path.name, name, claimed,
                                     fresh_versions.get(name, [])))
    return findings, unverifiable, None
