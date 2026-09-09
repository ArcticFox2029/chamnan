"""`environments.md` — the constraints nobody writes down and everybody re-learns.

    "RWO storage only, no ReadWriteMany"      "no TPM in UAT"      "DR runs different hardware"

Every one of those is discovered the same way: somebody writes the obvious solution, it fails in
one environment and not another, and an afternoon goes into working out why. The fact itself is
one line long. It is not in the code — the code is what got written *because* of it — and it is
not in the git history either, because the commit that worked around it explains the workaround
and not the constraint. So it lives in whoever hit it, and the next person pays again.

Four fields per environment, and the last two are what make this more than a README section:

    ## production
    **Platform:** Kubernetes 1.28 on RKE2
    **Versions:** postgres 16, redis 7.2, python 3.11
    **Constraints:**
    - RWO storage only — no ReadWriteMany PVCs
    - no outbound internet from worker nodes
    **Checked:** 2026-08-27

`Versions:` is a declared list of `name version` pairs, and it exists so that Stage 14's aging can
compare a memory entry's claim against something real instead of against a clock. `Checked:` is
the date somebody last confirmed the entry is still true, and it is what keeps this file from
becoming an oracle nobody has verified: `stale_environments()` finds the entries nobody has
touched in a long time, and the aging check REFUSES to report against an environment whose
`Checked:` date has gone cold rather than issue a false all-clear from an unmaintained source.

**Nothing here talks to an environment.** No cluster is contacted, no version is detected, nothing
is inferred. Every fact in this file was typed by a person who knew it, which is exactly why it is
worth keeping — and why a `Checked:` date is the only honest way to say how much to trust it.
"""
import datetime
import re
import mdblock
import redact
import workspace as ws  # noqa: E402

FILENAME = "environments.md"
HEADER = "# Environments\n"

# How long a `Checked:` date stays trustworthy. Deliberately long: this file describes platform
# facts, which move on the order of quarters, not days -- a window short enough to fire constantly
# would train people to ignore it, which is the failure mode this whole release exists to avoid.
STALE_AFTER_DAYS = 180

_ENV = re.compile(r"^##\s+(.+?)\s*$", re.M)
_FIELD = re.compile(r"^\*\*(\w+):\*\*\s*(.*)$", re.M)
_BULLET = re.compile(r"^\s*[-*]\s+(.+?)\s*$", re.M)
# A declared version: a name followed by a dotted or plain number. "postgres 16", "python 3.11",
# "Kubernetes 1.28". Anything that does not match this shape is simply not a version claim, and
# is left alone rather than guessed at.
_VERSION = re.compile(r"([A-Za-z][\w.+-]*)\s+v?(\d+(?:\.\d+)*)")
# The filler word between a name and its number ("postgres version 16") is stripped by
# `aging.version_pairs`, which BOTH sides of this feature go through -- see the note there for what
# each of them got wrong on its own.


def path(root):
    from workspace import workspace
    return workspace(root) / FILENAME


def _ymd_to_ts(text):
    import calendar
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text.strip())
    if not m:
        return None
    # 🐛 `calendar.timegm` does arithmetic, not validation: it turns 2026-02-30 into 2026-03-02 and
    # 2026-06-31 into 2026-07-01, silently, so a typo in a date became a real date two days later
    # and the staleness check it feeds reported an all-clear about a day that does not exist.
    # `datetime.date` refuses instead, which is what a validator is for. Same treatment
    # `sessions.prune()` already applies to the dates it parses.
    #
    # 🐛 [2026-09-06] `lib/ledger.py`'s function of the same name refuses a date in the FUTURE as
    # well, and says why: "a typo'd 2099-01-01 made _age() report today". This copy got the
    # calendar half of that fix and not the future half -- one member of a pair, again. Here it is
    # worse than a wrong count: `**Checked:** 2027-01-01` makes the entry permanently fresh, so
    # `stale_environments()` never names it and the aging check, whose whole job is to REFUSE to
    # report against an unmaintained source, issues an all-clear from one forever (R11 agent 3).
    # A slack of one day, same as ledger, so an entry written in a timezone ahead of this machine
    # is not thrown away.
    try:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        datetime.date(y, mo, d)                      # raises on 2026-02-30, 2026-06-31, 2026-13-01
        ts = calendar.timegm((y, mo, d, 12, 0, 0))
    except (ValueError, TypeError):
        return None
    import time as _time
    return None if ts > _time.time() + 86400 else ts


def entries(root):
    """[{name, platform, versions, constraints, checked, checked_ts}] in file order.

    `versions` is {name: version} parsed from the `Versions:` line, `versions_raw` that line
    verbatim. `constraints` is the list of
    bullets under `Constraints:`. `checked_ts` is None when the entry has no parseable `Checked:`
    date — which `stale_environments()` treats as never checked, not as fine.
    """
    p = path(root)
    if not p.is_file():
        return []
    # 🐛 [2026-09-09] Opened with no containment check at all, while five DIRECTORY stores got
    # exactly this guard on 2026-09-08 and the three single-FILE stores beside them did not. A
    # workspace travels with a clone, so `environments.md` arriving as a symlink to `~/.ssh/id_rsa` is
    # chosen by whoever wrote the repository, not by the person reading it — and its content lands
    # in the injected block. The set was "stores this reads"; the fix reached the members that
    # happened to be directories. (R3 agent 2, reproduced.)
    import workspace as _ws
    if not _ws.inside(p, root):
        return []
    try:
        text = p.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return []

    found = list(_ENV.finditer(mdblock.masked(text)))
    out = []
    for i, m in enumerate(found):
        end = found[i + 1].start() if i + 1 < len(found) else len(text)
        body = text[m.end():end]
        fields = {k.lower(): v.strip() for k, v in _FIELD.findall(body)}

        versions = {}
        import aging as _aging          # deferred: aging imports nothing local, so no cycle
        for vname, vnum in _aging.version_pairs(fields.get("versions", "")):
            versions[vname.lower()] = vnum

        constraints = []
        cut = body.find("**Constraints:**")
        if cut >= 0:
            # Only the bullets that follow Constraints:, never bullets belonging to a later field.
            after = body[cut:]
            nxt = _FIELD.search(after[len("**Constraints:**"):])
            region = after[:nxt.start() + len("**Constraints:**")] if nxt else after
            constraints = [b.strip() for b in _BULLET.findall(region)]

        checked = fields.get("checked", "")
        out.append({
            "name": m.group(1).strip(),
            "platform": fields.get("platform", ""),
            "versions": versions,
            # The `Versions:` line exactly as written. `versions` above is lossy -- it keeps only
            # what _VERSION could parse -- and `chamnan-env set` has to be able to carry the line
            # forward unchanged when the caller did not retype it.
            "versions_raw": fields.get("versions", ""),
            "constraints": constraints,
            "checked": checked,
            "checked_ts": _ymd_to_ts(checked),
        })
    return out


def declared_versions(root):
    """{name: [(env, version), ...]} across every environment.

    A list per name rather than one value, because two environments legitimately run different
    versions of the same thing — that is usually the entire reason somebody wrote this file. A
    caller comparing a claim against this has to decide what a disagreement means; this only
    reports what was declared where.
    """
    out = {}
    for env in entries(root):
        for name, version in env["versions"].items():
            out.setdefault(name, []).append((env["name"], version))
    return out


def stale_environments(root, now=None, window_days=STALE_AFTER_DAYS, envs=None):
    """[(name, days_since_checked_or_None)] for entries whose `Checked:` date has gone cold, or
    that never had one. Empty when every entry is fresh.

    This is the honest half of the file's design. An environment nobody has confirmed in six
    months is not evidence that the platform is unchanged; it is evidence that nobody looked. A
    caller that treats an unmaintained entry as an authority produces a false all-clear, which is
    worse than producing nothing — see `aging.py`, which refuses to report against these.

    `envs`, when given, is the result of a caller's OWN `entries(root)` call — `aging.check()`
    reads and parses `environments.md` once and reuses it here rather than this function parsing
    the same file a second time for the same call. Left None, this reads and parses it itself,
    same as before.
    """
    import time
    now = time.time() if now is None else now
    cutoff = now - window_days * 86400
    stale = []
    for env in (entries(root) if envs is None else envs):
        ts = env["checked_ts"]
        if ts is None:
            stale.append((env["name"], None))
        elif ts < cutoff:
            stale.append((env["name"], int((now - ts) // 86400)))
    return stale


def render_entry(name, platform="", versions="", constraints=(), checked=""):
    """One environment in the canonical shape. A field with nothing in it is left out rather than
    written empty — the same rule milestones.render_entry() follows, and for the same reason: a
    heading followed by nothing reads as an oversight rather than as "not applicable"."""
    # Folded onto one line each, for the reason milestones.render_entry() spells out: this file is
    # read back by its `## ` headings, and a name carrying a newline wrote a second environment
    # that silently absorbed the platform and constraints meant for the first.
# 🐛 [2026-09-08] The READ side of these three stores was hardened and the WRITE side was never
# re-asked. `redact.emit` shadows `print` in `bin/chamnan-env`, `bin/chamnan-timeline` and
# `bin/chamnan-promote`, so an agent reading a command's stdout sees a scrubbed value -- and
# `git add` reads the FILE, not the stdout. Reproduced end to end: `chamnan-timeline add
# deploy-notes "rotated the key, new value is AKIAIOSFODNN7EXAMPLE"` wrote that key verbatim into
# `.chamnan/threads/deploy-notes.md`, which `git check-ignore` confirms is not ignored, and which
# the README tells people to commit. `scrub()` catches it; nothing was calling `scrub()`.
#
# Scrubbed BEFORE the one-line fold, not after: the multi-line rules (a YAML block, a secret-named
# list) need the newlines to see the shape, and folding first destroys exactly the structure they
# match on. R8 agent 2.
    #
    # Every field, not the obvious one: a connection string reaches `--constraint` as readily as
    # `--platform`, and picking which field "could hold a secret" is the judgement that was wrong
    # every previous time this file made it.
    name = mdblock.one_line(redact.scrub(name))
    platform = mdblock.one_line(redact.scrub(platform))
    versions = mdblock.one_line(redact.scrub(versions))
    checked = mdblock.one_line(redact.scrub(checked))
    parts = [f"## {name}", ""]
    if platform:
        parts.append(f"**Platform:** {platform}")
    if versions:
        parts.append(f"**Versions:** {versions}")
    bullets = [b for b in (mdblock.one_line(redact.scrub(c)) for c in constraints) if b]
    if bullets:
        parts.append("**Constraints:**")
        parts.extend(f"- {b}" for b in bullets)
    if checked:
        parts.append(f"**Checked:** {checked}")
    parts.append("")
    return "\n".join(parts)


def upsert(root, name, entry_text):
    """Write one environment, replacing an existing entry of the same name in place.

    Replacing rather than appending: unlike a milestone, an environment is a description of how
    something IS, and two `## production` headings in one file would leave a reader with no way to
    tell which is current. Returns (path, replaced).
    """
    # 🐛 [2026-09-08] Read the whole file, edit in memory, write it back -- with no lock, so the
    # last writer's snapshot became the entire file. `ws.rewrite_shared` was built for exactly this
    # after six writers were found doing it and milestones.py measured five of six entries
    # vanishing; three writers never adopted it, and this was one. Measured here the same way: 2 of
    # 20 concurrent environment entries lost, 10%, valid Markdown throughout and no error anywhere
    # (R2 agent 3).
    #
    # The read happens INSIDE the lock, which is the whole reason this is `rewrite_shared` and not a
    # lock around the write: reading first and locking second leaves the same race with a smaller
    # window, which is the version of this fix that looks right and is not.
    p = path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    replaced = [False]

    def _upserted(existing):
        text = existing if (existing or "").strip() else HEADER + "\n"
        found = list(_ENV.finditer(mdblock.masked(text)))
        for i, m in enumerate(found):
            # Canonical, not `.lower()`: `chamnan-env set préprod` typed with a precomposed
            # é and again with a decomposed one declared TWO environments, both named
            # `préprod`, contradicting each other on platform and versions -- reproduced
            # 2026-09-08. An environment is a fact about a deployment target; two of them
            # is worse than none, because `chamnan-env show` answers with whichever it
            # reaches first.
            if mdblock.canonical_title(m.group(1)) != mdblock.canonical_title(name):
                continue
            end = found[i + 1].start() if i + 1 < len(found) else len(text)
            replaced[0] = True
            return (text[:m.start()] + entry_text.strip() + "\n\n"
                    + text[end:]).rstrip("\n") + "\n"
        return text.rstrip("\n") + "\n\n" + entry_text.strip() + "\n"

    ws.rewrite_shared(p, _upserted)
    if replaced[0]:
        return p, True
    return p, False


# Flags whose VALUE names an environment. Matching only these, and never a bare word anywhere in
# the command, is the whole false-positive control: `grep production deploy.log` mentions the word
# and targets nothing, and attaching production's constraints to it would train somebody to scroll
# past the one time it mattered. Failing quiet is the right direction here, exactly as it is for
# `docker --context prod` in lib/workflows.py -- a missed match costs one unshown notice, a wrong
# one costs the notice's credibility.
# A verb whose NEXT word names the environment. Matched as a word of the command, so
# `grep use-context deploy.log` still targets nothing.
_POSITIONAL_SELECTORS = ("use-context", "select", "use", "set-context")
# The word BEFORE the selector has to make it a selection. Without this, `grep use-context
# deploy.log` returned "deploy.log" -- and this module's whole false-positive control is that a
# bare mention of a word targets nothing, because a notice attached to one is how somebody learns
# to scroll past the notice that mattered.
_SELECTOR_CONTEXT = ("config", "workspace", "context", "env", "environment", "kubectx", "profile")
_TARGET_FLAGS = ("--context", "--namespace", "-n", "--profile", "--env", "--environment",
                 "--stage", "--cluster", "--target")
_ASSIGNED = re.compile(r"\b(?:ENV|ENVIRONMENT|STAGE|TARGET|CONTEXT)=([\w.-]+)", re.I)


def match_command(root, command, envs=None):
    """The declared environment a shell command TARGETS, or None.

    Only a recognised targeting flag's value, or an `ENV=`-style assignment, counts. A bare
    mention of the word somewhere in the command does not — see `_TARGET_FLAGS` for why.

    `envs`, see `stale_environments` — a caller that already parsed `environments.md` for this
    same call (`chamnan_scratch_watch.py`'s `_environment_notice` calls this and
    `constraints_notice` back to back on the same command) passes it through instead of paying
    for a second parse of a file that cannot have changed in between.
    """
    if not command:
        return None
    declared = {e["name"].lower(): e["name"] for e in (entries(root) if envs is None else envs)}
    if not declared:
        return None
    parts = str(command).split()
    for i, part in enumerate(parts):
        value = None
        # The two commonest ways an environment is actually selected are positional, not flags:
        # `kubectl config use-context production` and `terraform workspace select production`.
        # Neither matched, so the constraints notice never fired for either -- against a declared,
        # freshly confirmed environment with real constraints on it.
        if (part in _POSITIONAL_SELECTORS and i + 1 < len(parts)
                and i > 0 and parts[i - 1] in _SELECTOR_CONTEXT):
            candidate = parts[i + 1].strip("\"'")
            if candidate and not candidate.startswith("-"):
                return candidate
        if part in _TARGET_FLAGS and i + 1 < len(parts):
            value = parts[i + 1]
        elif "=" in part and part.split("=", 1)[0] in _TARGET_FLAGS:
            value = part.split("=", 1)[1]
        if value and value.strip("\"'").lower() in declared:
            return declared[value.strip("\"'").lower()]
    for m in _ASSIGNED.finditer(str(command)):
        if m.group(1).lower() in declared:
            return declared[m.group(1).lower()]
    return None


def constraints_notice(root, name, envs=None):
    """The one-shot notice naming an environment's constraints, or "" when it declares none.

    Deliberately not a warning and not a block. It says what was declared and who declared it,
    and leaves the judgement where the knowledge is. See README's Limitations for why there is no
    per-command guard: the PreToolUse `permissionDecision` such a guard would need has no
    documented behaviour under `defaultMode: "auto"`, and a guard that might silently not fire is
    worse than an honest notice that always does.

    `envs`, see `stale_environments`.
    """
    env = next((e for e in (entries(root) if envs is None else envs) if e["name"] == name), None)
    if env is None or not env["constraints"]:
        return ""
    # All three fields come out of environments.md, which is a repository file like any other.
    # This notice is emitted by a THIRD hook (chamnan_scratch_watch.py), which is why it sat outside
    # every audit aimed at the session-start block.
    bullets = mdblock.one_line("; ".join(env["constraints"]))
    checked = mdblock.one_line(env["checked"] or "never confirmed")
    return (f"chamnan: that command targets `{mdblock.as_quoted(name)}`, which declares — "
            f"{bullets}. (from `.chamnan/{FILENAME}`, checked {checked})")


# A constraint gets more room than a title, and the difference is deliberate rather than an
# oversight of the shared default. A title is a NAME -- 120 characters is already past the point
# where it has stopped being one. A constraint is a SENTENCE whose second half is usually the part
# that prevents the wrong work ("RWO only, **so no RollingUpdate on anything mounting a PVC**"),
# and cutting a rule before its consequence delivers the setup without the punchline. Measured on
# the reporting round's own 908-character fixture: 384.4 tokens uncapped, 78.4 at 200, 48.5 at 120
# -- the extra 80 characters cost ~30 tokens per item and buy the half of the sentence that does
# the work.
# The whole section, not one item. Measured before adding it: four environments with four
# paragraph-style constraints each -- an ordinary way to document infra, not an adversarial one --
# rendered 3,689 bytes through the real hook, 41% of the 9,000-byte whole-block ceiling, from a
# fixture that held almost nothing else. This section is ranked next-to-last in `fit.DROP_ORDER`,
# so overflowing on its account does not drop IT: tools, milestones, procedures, decisions, the
# last session, open threads and reply style all go first. That is Finding 1's collateral-damage
# shape in a different file.
#
# 1500 to match `memory.MAX_RULES_CHARS`, which is the only other session-block section with a
# whole-section character cap and is the one section ranked above this. Two sections whose job is
# to stop the wrong work being proposed, given the same room.
MAX_SECTION_CHARS = 1500

MAX_CONSTRAINT_CHARS = 200


def render_constraints(root, max_envs=4, max_bullets=4):
    """The injected block: each environment's constraints, capped. Empty when the file does not
    exist or declares none, so the hook injects no heading rather than an empty one.

    Constraints and not versions, because a constraint is the thing that changes what an agent
    should WRITE ("RWO only" rules out a whole design), while a version number is a fact it can
    look up when it turns out to matter. The injection budget goes to the half that prevents work
    rather than the half that answers a question.
    """
    found = [e for e in entries(root) if e["constraints"]]
    if not found:
        return ""
    lines, spent, shown, clipped = [], 0, 0, False
    for env in found[:max_envs]:
        head = f"- **{mdblock.one_line_capped(env['name'])}**"
        if env["platform"]:
            head += f" ({mdblock.one_line_capped(env['platform'])})"
        block = [head]
        for bullet in env["constraints"][:max_bullets]:
            block.append(f"  - {mdblock.one_line_capped(bullet, MAX_CONSTRAINT_CHARS)}")
        if len(env["constraints"]) > max_bullets:
            block.append(f"  - _…{len(env['constraints']) - max_bullets} more_")
        cost = sum(len(l) + 1 for l in block)
        # At least one environment always renders, even if it alone exceeds the budget: a section
        # of zero rows is not a summary. The per-item cap above already bounds how bad that one is.
        if lines and spent + cost > MAX_SECTION_CHARS:
            clipped = True
            break
        lines.extend(block)
        spent += cost
        shown += 1
    left = len(found) - shown
    if left > 0:
        # Named, never silent -- and it says WHY when the budget rather than the count cap did it,
        # because "4 more" after four entries reads as the count cap doing its documented job while the
        # reader has in fact lost sections they wrote.
        why = " (this section is full)" if clipped else ""
        lines.append(f"- _…and {left} more in `.chamnan/{FILENAME}`{why}_")
    return "\n".join(lines)
