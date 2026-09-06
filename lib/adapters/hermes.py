"""Hermes Agent — `.hermes.md`.

Hermes Agent (Nous Research, MIT) is a self-hosted agent that also acts as a control plane for other
coding agents — its own documentation names Codex, Claude Code, Gemini CLI and OpenCode as things it
drives. So a repository indexed for Hermes is often a repository indexed for several tools at once,
which is exactly the case chamnan's adapter set exists for.

Its context-file precedence, from `hermes-agent.nousresearch.com` (fetched 2026-09-05, the full docs
via `llms-full.txt` rather than the rendered page):

    SOUL.md                  the AGENT's identity, ~/.hermes/SOUL.md — not a project file
    .hermes.md / HERMES.md   project-specific instructions, HIGHEST priority, walks to the git root
    AGENTS.md                project-specific instructions, recursive directory walk
    CLAUDE.md                also detected, working directory only
    .cursorrules             also detected, working directory only

That list is a PRECEDENCE, and the correction matters: first match wins, they are not combined
(R8 agent 1, against the same docs). So writing `AGENTS.md` did not mean Hermes was also reading it
wherever a higher entry existed — and `install()` below, which refuses a `.hermes.md` it did not
write, has always had this right while these opening lines implied the tiers stacked.

This adapter exists for the entry above all the others: `.hermes.md` is what Hermes reads first and
stops at, and nothing was writing it.

`.hermes.md` and not `HERMES.md`, though the docs list both: the dotted name keeps it out of the way
in a repository that already has a README and an AGENTS.md at the root, and Hermes treats the two
identically.

**SOUL.md is deliberately not written.** It is the agent's identity, it lives in `~/.hermes/` rather
than the repository, and an index of somebody's code is not a personality. Writing it would also put
chamnan outside the workspace it was pointed at, which no adapter here does.
"""

NAME = "hermes"
TARGET = ".hermes.md"

# Hermes truncates every automatic context file at `context_file_max_chars`, which defaults to "a
# dynamic cap scaled to the model's context window (floor 20K, ceiling 500K chars)". The FLOOR is
# what a ceiling has to respect: on a small-context model the cap really is 20,000 characters, and a
# file over it is head/tail truncated with nothing saying where. Characters there, bytes here, and
# deliberately conservative for the same reason windsurf.py is -- one Thai or Japanese character is
# three bytes, so a byte ceiling can only ever deliver less than the documented character limit
# allows, never more.
CEILING = 20_000

MARKER = "<!-- chamnan:hermes -->"


def render(body):
    """The block, marked so a later run can tell its own file from somebody else's."""
    return f"{MARKER}\n{body.rstrip()}\n"


def install(root, body, command=""):
    """Write `.hermes.md`, unless somebody else's is already there.

    `command` is unused; it is in the signature because that is the shape every adapter's install
    has.

    Refusing rather than replacing, for the same reason zed.py refuses: this is the file Hermes
    reads FIRST and stops at, so overwriting a hand-written one silently replaces a repository's
    own instructions with an index. A file carrying chamnan's marker is this adapter's previous run
    and is replaced, which is the point of running again.
    """
    from . import held_target, read_target, write_target

    with held_target(root, TARGET) as target:
        existing = read_target(target)
        if existing is not None and not existing.lstrip().startswith(MARKER):
            raise ValueError(
                f"{target.path} exists and was not written by chamnan. Hermes gives this file the "
                f"highest priority of any project context file, so replacing it would silently "
                f"substitute an index for whatever it says. Move it aside first, or delete it if "
                f"it is stale.")
        write_target(target, render(body))
        return target.path
