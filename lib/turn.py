"""One notice per tool call, across hooks that cannot see each other.

Three PreToolUse hooks run for a single tool call and each is its own process: an `Edit` reaches
`chamnan_file_pointer` and `chamnan_skill_pointer`, a `Read` reaches `chamnan_bulk_read_notice` and
`chamnan_file_pointer`. Every one of them may write `hookSpecificOutput.additionalContext`, none
knows the others exist, and **nothing ranked them** -- whichever process reached its `say()` first
won by accident of code order.

Inside one hook the problem was already solved: `scratch_watch.say`'s own docstring records that
"exactly one object may be written, which is why every check in main() returns immediately after
speaking", and its eight emit sites are mutually exclusive by early return. This is the same rule
across processes, where an early return cannot reach.

**Priority is the order in `hooks/hooks.json`, not a number kept here.** The host runs the hooks in
the order they are declared, so first-come-first-served IS priority order once the file is ordered
deliberately. A ranking kept in two places drifts; this one cannot, because there is only one copy
of it and it is the copy the host reads.

**It fails OPEN, and that is the whole safety argument.** A claim that cannot be made -- no
workspace, an unwritable directory, a race, a surprise from the filesystem -- lets the caller speak.
The worst outcome is then today's behaviour, two notices on one call. The alternative failure mode
is chamnan going quiet with nobody able to tell that it has, which is far worse and much harder to
notice: a plugin that says nothing looks exactly like a plugin with nothing to say.

`os.open(..., O_CREAT | O_EXCL)` rather than read-then-write, because two hooks may run
concurrently and a read-compare-write would let both through. O_EXCL is one syscall and is atomic
on POSIX and on Windows; no lock file and no lock helper is needed, and this package has neither.
"""
import errno
import hashlib
import json
import os
import time

# Claims older than this are somebody else's dead session, or this one's own from a while back.
# Ten minutes is far longer than any single tool call and short enough that the directory stays
# small without a sweeper.
STALE_SECONDS = 600
# A directory that grows without bound is a defect even when each file is empty. This is a ceiling
# on how many claims may sit there before a claim attempt prunes regardless of age.
MAX_CLAIMS = 200


def key(payload):
    """A stable id for ONE tool call, identical in every hook that sees it.

    The host gives no per-call identifier, so it is derived: session, tool name, and the tool's own
    input. Two identical calls in one session therefore share a key -- deliberately. A second
    `Read` of the same file with the same arguments is the case the existing per-session throttles
    already exist to quieten, and letting it through here would undo them.
    """
    try:
        raw = json.dumps([str(payload.get("session_id") or ""),
                          str(payload.get("tool_name") or ""),
                          payload.get("tool_input")],
                         sort_keys=True, default=str)
    except (TypeError, ValueError):
        # An input that will not serialise still deserves a stable key, just a coarser one.
        raw = "%s|%s" % (payload.get("session_id"), payload.get("tool_name"))
    return hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()[:20]


def _prune(d, now):
    try:
        names = os.listdir(d)
    except OSError:
        return
    if len(names) <= MAX_CLAIMS:
        names = [n for n in names
                 if _age(os.path.join(d, n), now) > STALE_SECONDS]
    for n in names:
        try:
            os.unlink(os.path.join(d, n))
        except OSError:
            pass


def _age(p, now):
    try:
        return now - os.stat(p).st_mtime
    except OSError:
        return 0.0


def claim(payload, wsdir):
    """True when this process may speak for this tool call; False when somebody already has.

    Every failure path returns True. See the module docstring: silence is the expensive mistake.
    """
    try:
        if wsdir is None:
            return True
        d = os.path.join(str(wsdir), "logs", "turn")
        os.makedirs(d, exist_ok=True)
        now = time.time()
        _prune(d, now)
        path = os.path.join(d, key(payload))
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except OSError as e:
            if e.errno == errno.EEXIST:
                # Somebody claimed it. Unless the claim is stale, in which case it belongs to a
                # process that died mid-call and holding this one silent would be that crash
                # spreading.
                if _age(path, now) > STALE_SECONDS:
                    return True
                return False
            return True
        os.close(fd)
        return True
    except Exception:
        return True
