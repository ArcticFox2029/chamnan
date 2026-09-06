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
    try:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        datetime.date(y, mo, d)                      # raises on 2026-02-30, 2026-06-31, 2026-13-01
        return calendar.timegm((y, mo, d, 12, 0, 0))
    except (ValueError, TypeError):
        return None


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
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    found = list(_ENV.finditer(mdblock.masked(text)))
    out = []
    for i, m in enumerate(found):
        end = found[i + 1].start() if i + 1 < len(found) else len(text)
        body = text[m.end():end]
        fields = {k.lower(): v.strip() for k, v in _FIELD.findall(body)}

        versions = {}
        for vname, vnum in _VERSION.findall(fields.get("versions", "")):
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
    name, platform = mdblock.one_line(name), mdblock.one_line(platform)
    versions, checked = mdblock.one_line(versions), mdblock.one_line(checked)
    parts = [f"## {name}", ""]
    if platform:
        parts.append(f"**Platform:** {platform}")
    if versions:
        parts.append(f"**Versions:** {versions}")
    bullets = [b for b in (mdblock.one_line(c) for c in constraints) if b]
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
    p = path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    text = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""
    if not text.strip():
        text = HEADER + "\n"

    found = list(_ENV.finditer(mdblock.masked(text)))
    for i, m in enumerate(found):
        if m.group(1).strip().lower() != name.strip().lower():
            continue
        end = found[i + 1].start() if i + 1 < len(found) else len(text)
        text = text[:m.start()] + entry_text.strip() + "\n\n" + text[end:]
        ws.write_or_raise(p, text.rstrip("\n") + "\n")
        return p, True

    ws.write_or_raise(p, text.rstrip("\n") + "\n\n" + entry_text.strip() + "\n")
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
    return (f"chamnan: that command targets `{mdblock.one_line(name)}`, which declares — "
            f"{bullets}. (from `.chamnan/{FILENAME}`, checked {checked})")


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
    lines = []
    for env in found[:max_envs]:
        head = f"- **{mdblock.one_line(env['name'])}**"
        if env["platform"]:
            head += f" ({mdblock.one_line(env['platform'])})"
        lines.append(head)
        for bullet in env["constraints"][:max_bullets]:
            lines.append(f"  - {mdblock.one_line(bullet)}")
        if len(env["constraints"]) > max_bullets:
            lines.append(f"  - _…{len(env['constraints']) - max_bullets} more_")
    if len(found) > max_envs:
        lines.append(f"- _…and {len(found) - max_envs} more in `.chamnan/{FILENAME}`_")
    return "\n".join(lines)
