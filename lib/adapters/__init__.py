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

from . import cursor
from . import gemini
from . import kiro

# Registry, by the name `host.agents()` uses. `claude` is deliberately absent: its delivery is the
# SessionStart hook, which writes no file, and inventing a file for it would create a second copy
# of the block that nothing reads and nobody updates.
ADAPTERS = {
    cursor.NAME: cursor,
    gemini.NAME: gemini,
    kiro.NAME: kiro,
}


def for_agent(name):
    """The adapter for `name`, or None. None is an answer -- Claude Code has no file to write."""
    return ADAPTERS.get(name)


def names():
    """Every agent that has an adapter, in a stable order."""
    return sorted(ADAPTERS)


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
    target = ws.Path(root) / adapter.TARGET
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
