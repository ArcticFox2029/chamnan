"""Grok Build (xAI) — `.grok/rules/chamnan.md`.

Grok Build reads `AGENTS.md` and `CLAUDE.md` variants AND its own `.grok/rules/` directory. The
directory is written because it is chamnan's to own: a file there can be deleted without touching
anything shared, where the root file is contested by every other agent that reads it.

Its documentation states explicitly that there is no size cap, which is worth recording as a
measured absence rather than leaving CEILING to be read as "nobody checked".
"""

NAME = "grok"
TARGET = ".grok/rules/chamnan.md"
CEILING = None


def render(body):
    """The block, unchanged."""
    return body.rstrip() + "\n"
