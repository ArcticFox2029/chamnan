"""Replit Agent — `replit.md`.

One file at the project root, plain markdown, no frontmatter, read fresh each session. Replit's
own documentation organises it under headings such as `## Coding Style`; chamnan's block is
already sectioned that way, so it is written as-is.

`replit.md` is a root file with a fixed name, like Trae's, and the same reasoning applies: it is
chamnan-shaped enough that a user is unlikely to have written one by hand, and `--write replit` is
not run by accident.
"""

NAME = "replit"
TARGET = "replit.md"
CEILING = None


def render(body):
    """The block, unchanged."""
    return body.rstrip() + "\n"
