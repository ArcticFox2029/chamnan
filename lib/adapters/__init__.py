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
    target = safe_target(root, adapter.TARGET)
    target.parent.mkdir(parents=True, exist_ok=True)
    ws.atomic_write_text(target, adapter.render(body))
    return target


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
