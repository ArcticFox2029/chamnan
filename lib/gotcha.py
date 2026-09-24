"""Has this exact thing failed here before? — read from what failed, not from what anybody wrote.

🎯 [owner 2026-09-23] "จดข้อผิดพลาด แล้วต้องให้มันเรียนรู้ ไม่ทำผิดซ้ำๆ". `chamnan_tool_failed.py`
does the remembering; this is the part that acts on it.

**The key starts at its TIGHTEST setting, deliberately.** What counts as "the same failure" cannot
be chosen from data that does not exist yet — `commands.jsonl` has 6,389 rows and carries no
failure signal at all, so there was nothing to learn a key from. Between the two ways of being
wrong, one is recoverable and one is not: a key too tight says nothing and can be loosened when
`failures.jsonl` has a week in it, while a key too loose warns on healthy work until people stop
reading it, and `skill_overlap.py` has that outcome recorded as the reason a feature was dropped.

So the key is the whole subject, exactly: the same tool, the same command or path, and the same
first line of error. Two different `pytest` failures do not match each other. That will miss
repeats it could have caught, and missing them is the intended trade.

**The first failure is not a gotcha.** Everybody's first attempt at a command can fail; that is how
people find out what the flags are. Only a SECOND identical failure is a pattern, which is also
what makes this cheap: nothing is ever said about work that went wrong once.
"""
import json
import re

LOG = "logs/failures.jsonl"
# How many identical failures before this is worth saying out loud. Two, because one is learning.
REPEATS = 2
# Rows past this are not read. A failure from six months ago is not what somebody is about to
# repeat, and the file is bounded at 4,000 records anyway.
WINDOW = 1_000


# What every production error tracker normalises out of a grouping key, and none of them keeps.
# Surveyed 2026-09-23 across Socorro, Sentry, BugSnag, Rollbar, Datadog, New Relic and Buildkite:
# Datadog drops "numbers, punctuation, quoted or parenthesized message values, versions, IDs and
# dates"; New Relic drops "UUIDs, hex values, email addresses"; Rollbar drops line numbers by
# default and the message entirely unless asked; Buildkite keys a flaky test on `scope + name` and
# ignores the failure message outright. The shape is unanimous: the key is DELIBERATELY lossy, and
# what it loses is whatever varies between two occurrences of one problem.
# The one number that is a KIND rather than a detail. Everything after it is detail.
_EXIT_CODE = re.compile(r"Exit code \d+")
_VOLATILE = (
    (re.compile(r"\b[0-9a-fA-F]{7,}\b"), "<hex>"),          # sha, uuid fragment, address
    (re.compile(r"(?<![\w.])\d+(?:\.\d+)*(?![\w])"), "<n>"),  # counts, line numbers, versions
    (re.compile(r"'[^']*'|\"[^\"]*\"|`[^`]*`"), "<q>"),      # quoted values
    (re.compile(r"(?:/[\w.@-]+){2,}"), "<path>"),            # absolute and deep relative paths
)


def normalise(text):
    """An error line with the parts that vary between two occurrences of one problem removed.

    🎯 [2026-09-23, external survey] The first version of this module keyed on the error line
    EXACTLY, reasoning that too tight only costs silence while too loose costs trust. The survey
    says that trade is real and that the tight end is not the safe one it looks like:
    **under-grouping is the field's most-reported complaint** — one fault becomes many entries
    because a line number moved or a path differed — and every system listed above spends effort
    normalising rather than matching literally.

    Applied to the KEY only. The raw first line is what gets shown, because a reader needs the
    actual error and `<n>` helps nobody.
    """
    out = str(text or "")
    # 🐛 [2026-09-23] (self-measured) Normalising every number merged `Exit code 1` with
    # `Exit code 2`, which is over-grouping — the field's SECOND-most-reported complaint, where
    # "different causes share a convenient frame". An exit code is the failure's TYPE, not a value
    # that varies between two occurrences of one problem: 1 is a test failing and 127 is a command
    # that does not exist. Socorro keeps special signatures for OOM, hangs and IPC for the same
    # reason — a few tokens carry the kind rather than the detail, and those are kept whole.
    keep = _EXIT_CODE.match(out)
    if keep:
        return keep.group(0) + (" " + normalise(out[keep.end():]) if out[keep.end():].strip() else "")
    for pattern, token in _VOLATILE:
        out = pattern.sub(token, out)
    return " ".join(out.split())


def key(row):
    """(tool, subject, NORMALISED error) — the identity two occurrences of one problem share.

    Returns "" for a row that cannot be keyed, and a caller must skip those rather than group them
    together: an empty key would make every unreadable row a repeat of every other.
    """
    if not isinstance(row, dict):
        return ""
    tool, subj, err = row.get("tool"), row.get("subj"), row.get("err")
    if not tool or not subj:
        return ""
    return "\x00".join((str(tool), str(subj), normalise(err)))


def repeats(wsdir, minimum=REPEATS):
    """{key: (count, subject, error, when)} for failures seen at least `minimum` times."""
    seen = {}
    try:
        with (wsdir / LOG).open(encoding="utf-8-sig", errors="replace") as fh:
            rows = fh.readlines()[-WINDOW:]
    except OSError:
        return {}
    for line in rows:
        try:
            row = json.loads(line)
        except (ValueError, RecursionError):
            continue
        k = key(row)
        if not k:
            continue
        count, _s, _e, _w = seen.get(k, (0, "", "", ""))
        seen[k] = (count + 1, row.get("subj", ""), row.get("err", ""), row.get("at", ""))
    return {k: v for k, v in seen.items() if v[0] >= minimum}


# `redact.PLACEHOLDER`, spelled here so the check below costs no redactor import; pool check 258
# fails if the two ever differ.
_PLACEHOLDER = "<REDACTED>"


def might_repeat(wsdir, tool, raw):
    """False when no recorded repeat for `tool` could equal the scrubbed form of `raw`.

    🎯 [2026-09-25] (R80 claudeaccount2, 2026-09-24) Scrubbing the command to compare it compiled
    about 120 patterns in a fresh process: 166 ms of a 250 ms PreToolUse hook, on every Bash call,
    to answer a question whose answer is "no" almost every time. Scrubbing only swaps spans for
    `<REDACTED>`, so every piece of a stored subject between markers is text from the raw command;
    when one is not in `raw`, the scrubbed form cannot match and the scrub is skipped. Measured on
    1,395 real commands: none breaks that, once the half marker a 300-character cut can leave at the
    end is dropped, which this does. A necessary condition only -- True still means "scrub and ask".
    """
    raw = str(raw or "")
    for k, (_count, subj, _err, _when) in repeats(wsdir).items():
        if k.split("\x00")[0] != str(tool):
            continue
        s = str(subj)
        for cut in range(len(_PLACEHOLDER) - 1, 0, -1):
            if s.endswith(_PLACEHOLDER[:cut]):
                s = s[:-cut]
                break
        if all(piece in raw for piece in s.split(_PLACEHOLDER)):
            return True
    return False


def about_to_repeat(wsdir, tool, subject):
    """(count, error, when) when this exact tool and subject has already failed `REPEATS` times.

    None otherwise, which is the answer almost every time — a session runs hundreds of commands and
    this is about the handful somebody is going back to after it already failed twice.

    The ERROR is not part of what the caller knows before running, so the lookup is by tool and
    subject, and the recorded error comes back with the answer. That is the asymmetry that makes
    this usable at all: the key includes the error, but the question cannot.
    """
    if not tool or not subject:
        return None
    best = None
    for k, (count, subj, err, when) in repeats(wsdir).items():
        if k.split("\x00")[0] == str(tool) and subj == str(subject):
            if best is None or count > best[0]:
                best = (count, err, when)
    return best
