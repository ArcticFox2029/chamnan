"""Repeated sequences of commands — the workflow behind the scripts.

scratch_watch already catches the same SCRIPT being written a third time. This catches the thing
that happens more often and leaves no file behind at all: the same half-dozen commands, in the same
order, run again three weeks later because nobody wrote down what the sequence was.

    docker compose up · alembic upgrade · pytest tests/integration · docker compose down

That is a deployment check, or a debugging routine, or the steps to reproduce one bug. It is
knowledge, and today it survives only in whoever ran it.

**A high bar, deliberately.** Sequence detection is far noisier than comparing two script bodies:
any two working sessions share `git status` and `ls`. Four guards keep it quiet —

  1. commands are reduced to a SIGNATURE (`pytest`, `docker compose`) so arguments and paths do
     not have to match, but the tool and its subcommand do;
  2. commands too common to mean anything are dropped entirely (see NOISE);
  3. a run has to be at least MIN_LENGTH distinct signatures long;
  4. it has to have happened REPEAT_AT times.

It speaks once, at the threshold, the same restraint scratch_watch uses. A hint that fires on
every repetition is a hint people learn to scroll past.
"""
import json
import re

# Reduced to "program" or "program subcommand". `git status`, `pytest`, `docker compose`,
# `npm run`. Arguments and paths are discarded on purpose: the same workflow across two branches
# will not share filenames, but it will share this.
_SUBCOMMAND_TOOLS = {
    "git", "docker", "npm", "yarn", "pnpm", "cargo", "go", "kubectl", "terraform", "helm",
    "poetry", "pip", "brew", "gh", "make", "bundle", "rails", "python3", "python", "node",
    "ansible-playbook", "systemctl", "claude",
}

# Too common to carry meaning. A sequence made only of these is two people both using a shell.
NOISE = {
    "cd", "ls", "pwd", "echo", "cat", "clear", "which", "whoami", "export", "source",
    "head", "tail", "wc", "sort", "uniq", "cp", "mv", "mkdir", "touch", "chmod", "sleep",
    "grep", "find", "sed", "awk", "less", "more", "man", "history", "env", "date",
}

MIN_LENGTH = 3        # distinct signatures before a run counts as a workflow
REPEAT_AT = 3         # say something on the third occurrence, matching scratch_watch
WINDOW = 12           # how far back a run is assembled from
KEEP_ENTRIES = 400    # bounded log; a hint generator, not an archive

_SPLIT = re.compile(r"\s*(?:&&|\|\||;|\|)\s*")
_WORD = re.compile(r"^[A-Za-z_][\w.-]*$")


def signature(command):
    """A stable name for what a command DOES, or "" when it is not worth remembering.

    `pytest tests/payment -x` and `pytest tests/fleet` are the same step of the same workflow, and
    a fingerprint that disagreed would never match anything twice.
    """
    parts = command.strip().split()
    if not parts:
        return ""
    # Leading environment assignments: FOO=bar cmd ...
    while parts and "=" in parts[0] and not parts[0].startswith("-"):
        parts = parts[1:]
    if not parts:
        return ""
    prog = parts[0].rsplit("/", 1)[-1]
    if not _WORD.match(prog) or prog in NOISE:
        return ""
    if prog in _SUBCOMMAND_TOOLS:
        # Known limitation: a global flag that takes a VALUE before the subcommand
        # (`docker --context prod compose up`) yields `docker prod`, because telling
        # `--context prod` apart from `--debug compose` needs each tool's flag grammar. Left
        # alone rather than guessed at — the consequence is that such a command does not match
        # its own sequence and the workflow simply is not detected. Failing quiet is the right
        # direction for a hint; a heuristic wrong the other way would suggest the wrong routine.
        for arg in parts[1:]:
            if _WORD.match(arg) and not arg.startswith("-"):
                return f"{prog} {arg}"
            if arg.startswith("-"):
                continue
            break
    return prog


def signatures(command_text):
    """Every meaningful signature in one shell invocation, in order, de-duplicated consecutively.

    A single Bash call is often a pipeline or a chain; each part is a step. Consecutive duplicates
    collapse because `git add && git commit` twice in a row is one step repeated, not two.
    """
    out = []
    for part in _SPLIT.split(command_text):
        sig = signature(part)
        if sig and (not out or out[-1] != sig):
            out.append(sig)
    return out


def record(log_path, sigs, when):
    """Append signatures to the bounded log and return the full history."""
    prior = []
    if log_path.is_file():
        for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                prior.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    for sig in sigs:
        prior.append({"at": when, "sig": sig})
    prior = prior[-KEEP_ENTRIES:]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(json.dumps(p, ensure_ascii=False) for p in prior) + "\n",
                        encoding="utf-8")
    return prior


def _runs(history):
    """Split the flat history into runs, one per calendar day.

    A workflow is a sequence performed in one sitting. Joining across days would stitch the end of
    Tuesday to the start of Wednesday and call it a routine.
    """
    runs, current, day = [], [], None
    for entry in history:
        d = (entry.get("at") or "")[:10]
        if d != day:
            if current:
                runs.append(current)
            current, day = [], d
        current.append(entry.get("sig", ""))
    if current:
        runs.append(current)
    return runs


def repeated(history):
    """The longest sequence that has occurred REPEAT_AT times on distinct days, or None.

    Returns (sequence, count). Ordered and contiguous within a day — "these steps, in this order",
    which is what makes it a workflow rather than a set of tools somebody happens to use.
    """
    runs = _runs(history)
    if len(runs) < REPEAT_AT:
        return None

    seen = {}
    for i, run in enumerate(runs):
        window = run[-WINDOW:]
        # Every contiguous slice of at least MIN_LENGTH, recorded once per day so a sequence
        # repeated twice in one sitting does not count as two days' evidence.
        local = set()
        for start in range(len(window)):
            for end in range(start + MIN_LENGTH, len(window) + 1):
                slice_ = tuple(window[start:end])
                if len(set(slice_)) < MIN_LENGTH:
                    continue
                local.add(slice_)
        for slice_ in local:
            seen.setdefault(slice_, set()).add(i)

    qualifying = [(s, days) for s, days in seen.items() if len(days) >= REPEAT_AT]
    if not qualifying:
        return None
    # Longest wins: the fuller sequence is the more useful thing to write down, and a shorter one
    # contained inside it says less.
    best, days = max(qualifying, key=lambda kv: (len(kv[0]), len(kv[1])))
    return list(best), len(days)


def describe(sequence, count):
    steps = " → ".join(f"`{s}`" for s in sequence)
    return (f"chamnan: this sequence has come round {count} times now — {steps}. "
            f"If it is a routine worth keeping, run /chamnan:capture and write it down as a "
            f"procedure; the next session reads it instead of rediscovering the order.")
