"""Tencent CodeBuddy Code — `CODEBUDDY.md`.

Its own renamed file, with `AGENTS.md` only as a fallback. The renamed one is written because a
fallback is what a tool reads when the thing it wanted is absent -- relying on it would mean
competing with every other agent that reads the root file, in a repository where CodeBuddy has a
file of its own sitting empty.
"""

NAME = "codebuddy"
TARGET = "CODEBUDDY.md"
CEILING = None


def render(body):
    """The block, unchanged."""
    return body.rstrip() + "\n"
