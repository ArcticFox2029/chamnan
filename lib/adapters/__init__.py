"""One module per coding agent, and deliberately no shared base class.

Every agent reads its context from a different place, in a different format, under a different
size limit. A single structure parameterised over all of them would have to hold every one of
those differences as a flag, and the first conflict between two of them lands in code that is
about neither -- which is the failure the owner named before any of this was written.

So each adapter is a plain module with the same four names and no inheritance between them:

    NAME      what `host.agents()` calls this agent
    TARGET    the path it writes, relative to the repository root
    CEILING   the byte limit that agent's delivery imposes, or None when there is none
    render()  the block, wrapped in whatever that agent's format needs

A new agent is a new file. Nothing here has to change for one to be added, and nothing an
existing adapter does can be altered by adding one.

**What every adapter writes is generated and per-developer, and none of it should be committed.**
Two people on one repository may use two different agents, and neither wants the other's context
file in their tree. `install()` adds the target to `.chamnan/.gitignore` rather than assuming.
A consequence worth stating: the fence marker inside the block is regenerated on each build, so a
committed adapter file would churn on every rebuild. That is a reason not to commit it, not a bug
to work around -- the marker is unguessable on purpose, and making it stable would hand a
pull-request author the one thing it exists to withhold.
"""
import contextlib
import errno
import os
import stat

import workspace as ws

from . import aider
from . import antigravity
from . import augment
from . import amazonq
from . import cline
from . import codebuddy
from . import continuedev
from . import copilot
from . import cursor
from . import gemini
from . import goose
from . import grok
from . import generic
from . import iflow
from . import junie
from . import kiro
from . import mistral
from . import qwen
from . import replit
from . import roo
from . import trae
from . import hermes
from . import windsurf
from . import zed

# Registry, by the name `host.agents()` uses. `claude` is deliberately absent: its delivery is the
# SessionStart hook, which writes no file, and inventing a file for it would create a second copy
# of the block that nothing reads and nobody updates.
ADAPTERS = {
    aider.NAME: aider,
    antigravity.NAME: antigravity,
    augment.NAME: augment,
    amazonq.NAME: amazonq,
    cline.NAME: cline,
    codebuddy.NAME: codebuddy,
    continuedev.NAME: continuedev,
    copilot.NAME: copilot,
    cursor.NAME: cursor,
    gemini.NAME: gemini,
    goose.NAME: goose,
    grok.NAME: grok,
    generic.NAME: generic,
    iflow.NAME: iflow,
    junie.NAME: junie,
    kiro.NAME: kiro,
    mistral.NAME: mistral,
    qwen.NAME: qwen,
    replit.NAME: replit,
    roo.NAME: roo,
    trae.NAME: trae,
    hermes.NAME: hermes,
    windsurf.NAME: windsurf,
    zed.NAME: zed,
}


# An agent whose context mechanism is ANOTHER agent's file. Not a convenience: `--write codex`
# has to do something, and what Codex actually reads is AGENTS.md -- the same file the generic
# adapter writes, verified in its compiled binary. An alias says that out loud, where a second
# module writing the same path would give one repository two owners for one file.
# `AGENTS.md` turned out to be the shared standard rather than one convention among several:
# every agent below reads it as its project file, verified one by one against each product's own
# documentation. They are aliases rather than modules because a module for each would write eight
# copies of one file into one repository, and the second one to run would be the only one anybody
# read. What they get is exactly what `generic` writes, which is what they actually read.
ALIASES = {
    "amp": generic.NAME,
    "codex": generic.NAME,
    "crush": generic.NAME,
    "devin": generic.NAME,
    "kilo": generic.NAME,
    "opencode": generic.NAME,
    "openhands": generic.NAME,
    "warp": generic.NAME,

    # Model vendors that ship a harness reading the root AGENTS.md rather than a file of their own.
    # Verified one by one against each vendor's docs -- and one claim was verified FALSE on the way:
    # several secondary blogs state that Meta's Muse Code reads `MUSE_CODE.md`, and Meta's own
    # documentation says AGENTS.md. The alias below is the reason that mattered.
    "deepseek": generic.NAME,
    "kimi": generic.NAME,
    "muse": generic.NAME,
}


def for_agent(name):
    """The adapter for `name`, or None. None is an answer -- Claude Code has no file to write."""
    return ADAPTERS.get(ALIASES.get(name, name))


def names():
    """Every agent name that can be written, aliases included, in a stable order."""
    return sorted(set(ADAPTERS) | set(ALIASES))


def safe_target(root, rel):
    """The path `rel` names under `root` — refusing anything that would leave the repository.

    🐛 The READ side has had `ws.inside()` since a committed symlink at `.chamnan/STATE.md` was
    shown reading `~/.ssh/id_rsa` into the injected block. The WRITE side, added with the adapters,
    had no equivalent — so a committed symlink named `.cursor`, `.gemini`, `.roo` or any of the
    other twelve nested targets made `mkdir(parents=True)` and `os.replace` follow it and write
    outside the root. Reproduced: `.cursor -> /tmp/outside` put `rules/chamnan.mdc` there.

    The `gemini` case is worse than a stray file. Its install MERGES a `SessionStart` hook
    registration into `settings.json`; pointed at a settings file outside the repository it
    registers a command that then runs for every future session that config touches, with the
    user's own hooks left intact so nothing looks wrong.

    Checked BEFORE anything is created, by walking the components: `mkdir` through a symlink has
    already written outside by the time a resolve could notice. A symlink ANYWHERE in the chain is
    refused rather than resolved-and-compared, because "resolves inside today" is not a property
    that stays true -- the link is the repository's to change and the write is not.

    This is the ninth time in this project a guard has been added to some members of a set and
    forgotten in the others. It is the only way to a target now, and a test asserts that.
    """
    base = ws.Path(root)
    walked = base
    for part in ws.Path(rel).parts:
        walked = walked / part
        if walked.is_symlink():
            raise ValueError(
                f"{walked} is a symlink, and writing through it would leave the repository. "
                f"chamnan refuses rather than following it. Remove or replace the link.")
    if not str(walked.resolve()).startswith(str(base.resolve())):
        raise ValueError(f"{rel} resolves outside {root}; refusing to write there")

    # 🐛 The check above is about SYMLINKS, and a hardlink is not one — `is_symlink()` is False and
    # `resolve()` reports the path itself, so a hardlinked target passed every test here.
    #
    # For an adapter that only writes, that is harmless: `atomic_write_text` replaces the name
    # rather than writing through it, so the other link keeps its old content. For an adapter that
    # READS THE TARGET FIRST it is not. Rendered end to end: `.gemini/settings.json` hardlinked to
    # a settings file outside the repository, and `--write gemini` merged that file's `apiKey` into
    # a new repository-local file — the secret now sitting in something committable.
    #
    # A chamnan-owned target with a second name is never legitimate: these paths are written by
    # this tool and read by one agent. Refused rather than followed, and refused for every adapter
    # rather than only the ones that read — "this one only writes" is exactly the case-by-case
    # judgement that has been wrong nine times in this repository.
    try:
        if walked.exists() and not walked.is_dir() and walked.stat().st_nlink > 1:
            raise ValueError(
                f"{walked} has more than one name on disk (a hard link). chamnan will not write "
                f"through it: another of its names may be outside the repository, and an adapter "
                f"that merges would copy that file's contents in. Replace it with a plain file.")
    except OSError:
        pass          # unreadable metadata is not a reason to refuse; the checks above still hold
    return walked


# `openat` and friends: every one of these takes the directory to work in as an OPEN HANDLE rather
# than as a name, which is what makes the walk below race-free. Absent on Windows, where the
# fallback is `safe_target`'s check on its own.
#
# `os.replace` is missing from `os.supports_dir_fd` on macOS and Linux both, while `os.rename` --
# the same `renameat` underneath, same signature -- is present. Probed through `os.rename` for
# that reason, and `os.replace(..., src_dir_fd=)` then works. Verified before relying on it; do
# not "correct" this to probe `os.replace` and conclude the platform cannot do it.
_ANCHORED = (
    hasattr(os, "O_NOFOLLOW")
    and hasattr(os, "O_DIRECTORY")
    and {os.open, os.mkdir, os.rename, os.unlink, os.access} <= os.supports_dir_fd)

_DIR_FLAGS = (os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_DIRECTORY", 0))


class Target(object):
    """Where an adapter writes: an open handle on the directory, and the name inside it.

    `dir_fd` is None on a platform without `openat`, and then `path` is all a caller has.
    """

    __slots__ = ("dir_fd", "leaf", "path")

    def __init__(self, dir_fd, leaf, path):
        self.dir_fd, self.leaf, self.path = dir_fd, leaf, path


def _is_link_at(dir_fd, name):
    """Whether `name` inside the open directory is a symlink. Asked through the handle, so it is
    the same directory the open just failed in rather than a second resolution of the path."""
    try:
        return stat.S_ISLNK(os.stat(name, dir_fd=dir_fd, follow_symlinks=False).st_mode)
    except OSError:
        return False


def _step(dir_fd, name, rel):
    """One component deeper, creating it if absent. Refuses a symlink at that component."""
    for last in (False, True):
        try:
            return os.open(name, _DIR_FLAGS, dir_fd=dir_fd)
        except FileNotFoundError:
            if last:
                raise
            try:
                os.mkdir(name, dir_fd=dir_fd)
            except FileExistsError:
                pass          # another process created it between our open and our mkdir
        except OSError as exc:
            # A symlink here arrives as one of two errnos and the difference is the PLATFORM's,
            # not the attacker's: `O_NOFOLLOW` alone gives ELOOP, and `O_NOFOLLOW|O_DIRECTORY` on
            # a link that points AT a directory gives ENOTDIR (measured on macOS 3.12). ENOTDIR is
            # also what somebody's own file in the way gives -- `.clinerules` is a directory in
            # some repositories and a plain file in others -- and those two must not get the same
            # message: one is an escape, the other is a file we must not destroy. Asked of the
            # component itself rather than guessed from the errno.
            linked = False
            if exc.errno in (errno.ELOOP, errno.EMLINK, errno.ENOTDIR):
                linked = _is_link_at(dir_fd, name)
            if linked:
                raise ValueError(
                    f"`{name}`, on the way to {rel}, is a symlink. Writing through it would "
                    f"leave the repository; chamnan refuses rather than following it.") from exc
            raise
    raise AssertionError("unreachable")


@contextlib.contextmanager
def held_target(root, rel):
    """`safe_target`'s answer, with the directory it checked HELD OPEN for the write that follows.

    🐛 `safe_target` returns a path, and the caller then acts on that path -- two separate
    resolutions of the same name, with a window between them. Rendered end to end, twice: with
    `.cursor/rules` a real directory at check time and swapped for a symlink immediately after,
    the unmodified rest of `install()` wrote `chamnan.mdc` outside the repository; with `.gemini`
    swapped the same way, `gemini.install()` read an outside `settings.json` and merged its
    `BILLING_API_TOKEN` into a committable file in the repository.

    That second one is the hardlink leak this module already refuses, reached by a race instead of
    by a link -- so the `st_nlink > 1` guard above closed the static half of it and left this half
    open. A reader could reasonably have believed the whole thing was closed. It was not.

    A name can be swapped; an open file descriptor cannot. Every component is opened with
    `O_NOFOLLOW`, each from the handle on the one above it, and the read and the write both happen
    through the final handle -- so a swap after the check reaches a directory nobody is writing to
    any more. The check is no longer separate from the act.

    Preconditions for the attack, stated honestly: it needs write access to the working tree
    CONCURRENT with a run of `--write`, which is a higher bar than the committed symlink and the
    committed hardlink this module already refuses. It is closed here because the outcome is the
    same as those two, and because "narrow" has been the wrong reason nine times in this project.

    Windows has no `openat`; there `dir_fd` is None and `safe_target`'s check is what there is.
    """
    parts = ws.Path(rel).parts
    if not parts:
        raise ValueError(f"{rel!r} names no file to write")
    path = safe_target(root, rel)
    if not _ANCHORED:
        yield Target(None, parts[-1], path)
        return
    fd = os.open(str(ws.Path(root)), _DIR_FLAGS)
    try:
        for part in parts[:-1]:
            deeper = _step(fd, part, rel)
            os.close(fd)
            fd = deeper
        yield Target(fd, parts[-1], path)
    finally:
        os.close(fd)


def read_target(target):
    """The target's current text, or None when it is not there. Refuses to read through a symlink.

    The adapter that merges (`gemini`) reads before it writes, and this is the read half of the
    same window `held_target` closes -- reading by name would resolve the name a second time.
    """
    if target.dir_fd is None:
        try:
            return target.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
    try:
        fd = os.open(target.leaf, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=target.dir_fd)
    except FileNotFoundError:
        return None
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.EMLINK):
            raise ValueError(
                f"{target.path} is a symlink. chamnan will not read through it: it may point "
                f"outside the repository, and this adapter merges what it reads into a file it "
                f"then writes here.") from exc
        raise
    with os.fdopen(fd, "r", encoding="utf-8") as fh:
        return fh.read()


def write_target(target, text):
    """Replace the target atomically, through the held handle. Returns True on success.

    Same two properties `ws.atomic_write_text` carries and for the same reasons -- a per-process
    staging name so two writers never share one, and a refusal to replace a file the user has made
    read-only -- expressed against a directory handle instead of a path.
    """
    if target.dir_fd is None:
        # No `openat` here, so the path is all there is -- and the parent has to be created OUT of
        # `atomic_write_text`, which returns False rather than raising. Without this, somebody's
        # own `.clinerules` FILE where a directory belongs stopped the install with a clear error
        # on POSIX and was swallowed into a silent no-op on Windows. Caught by mutating `_ANCHORED`
        # to False, which is the only way to reach this branch on the machine the tests run on.
        target.path.parent.mkdir(parents=True, exist_ok=True)
        return ws.atomic_write_text(target.path, text)
    tmp = f"{target.leaf}.{os.getpid()}.tmp"
    try:
        if os.access(target.leaf, os.W_OK, dir_fd=target.dir_fd, follow_symlinks=False):
            pass
        elif _exists_at(target):
            return False
    except OSError:
        pass
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o644,
                     dir_fd=target.dir_fd)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, target.leaf, src_dir_fd=target.dir_fd, dst_dir_fd=target.dir_fd)
        return True
    except Exception:
        try:
            os.unlink(tmp, dir_fd=target.dir_fd)
        except OSError:
            pass
        return False


def _exists_at(target):
    try:
        os.stat(target.leaf, dir_fd=target.dir_fd, follow_symlinks=False)
        return True
    except OSError:
        return False


def install(root, agent, body, command=""):
    """Write `body` through `agent`'s adapter. Returns the path written, or None.

    Writing bytes to a path is the one thing that genuinely does not vary between agents, so it
    lives here rather than being copied into each of them -- what varies is the FORMAT, and that
    is what each adapter owns.

    Atomic, because a half-written context file is worse than none: the agent reads whatever is
    there, and a truncated block ends mid-sentence with no sign that it was cut.

    **It does not touch any .gitignore, and that is a decision rather than an omission.** The
    target sits outside `.chamnan/`, and git applies a .gitignore to its own directory and below --
    so ignoring it would mean writing into the repository's ROOT .gitignore, which is the user's
    file and would break the README's promise that the only thing chamnan writes outside its own
    workspace is an opt-in pre-commit hook. `ignore_line()` gives the caller the line to print
    instead, and the person whose repository it is decides.
    """
    adapter = for_agent(agent)
    if adapter is None:
        return None
    # An adapter whose install is not "write render() to TARGET" says so by defining its own.
    # Gemini's target is the user's settings.json and has to be MERGED, and forcing that through
    # a shared writer would mean a flag in here that only one agent ever sets -- which is the
    # single-structure failure this package exists to avoid.
    if hasattr(adapter, "install"):
        return adapter.install(root, body, command)
    with held_target(root, adapter.TARGET) as target:
        write_target(target, adapter.render(body))
    return target.path


def ignore_line(agent):
    """The .gitignore line a user would add for `agent`'s target, or "" when there is no adapter.

    Generated and per-developer: two people on one repository may use two different agents, and
    neither wants the other's context file in their tree.
    """
    adapter = for_agent(agent)
    if adapter is None or hasattr(adapter, "install"):
        # An adapter that merges into the user's own file has nothing to ignore -- that file was
        # theirs before chamnan touched it and stays theirs after.
        return ""
    return f"/{adapter.TARGET}"
