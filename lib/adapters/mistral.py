"""Mistral Vibe CLI — `.vibe/AGENTS.md`.

The path is the notable part: `AGENTS.md`, but inside `.vibe/` rather than at the repository root.
So a repository whose root `AGENTS.md` is set up for eight other agents gives Vibe nothing, and
this is a module rather than a ninth alias to `generic` for exactly that reason.

Named `mistral` rather than `vibe` because that is the name a user reaches for, and the tool's own
name is one release away from being something else.
"""

NAME = "mistral"
TARGET = ".vibe/AGENTS.md"
CEILING = None


def render(body):
    """The block, unchanged."""
    return body.rstrip() + "\n"
