"""Augment Code — `.augment/rules/chamnan.md`.

Augment reads workspace rules from `.augment/rules/`, with `.augment-guidelines` as the legacy
single-file form and `~/.augment/rules/` as the user-level one. It also honours a root `AGENTS.md`,
but its own directory is written instead: a rules directory takes a file chamnan owns outright,
where the root file is shared with every other agent that reads it.
"""

NAME = "augment"
TARGET = ".augment/rules/chamnan.md"
CEILING = None


def render(body):
    """The block, unchanged."""
    return body.rstrip() + "\n"
