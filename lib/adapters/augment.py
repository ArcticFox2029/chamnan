"""Augment Code — `.augment/rules/chamnan.md`.

Augment reads workspace rules from `.augment/rules/`, with `.augment-guidelines` as the legacy
single-file form and `~/.augment/rules/` as the user-level one. It also honours a root `AGENTS.md`,
but its own directory is written instead: a rules directory takes a file chamnan owns outright,
where the root file is shared with every other agent that reads it.
"""

NAME = "augment"
# This vendor reads the root `AGENTS.md` AS WELL AS its own file, so a repository that has
# run both `--write generic` and `--write <this>` sends the identical block twice, every
# session, and pays for it twice. Declared here rather than listed in `__init__.py`:
# 🐛 [2026-09-10] that list held four names while EIGHT vendors qualified, and the evidence
# for the missing four was sitting in their own docstrings. A set kept beside the thing it
# describes cannot drift from it (R4 agent 1, 2026-09-10, finding 6).
# Evidence: this adapter's own docstring above: Augment honours a root `AGENTS.md` as well as
# `.augment/rules/`.
ALSO_READS_AGENTS_MD = True

TARGET = ".augment/rules/chamnan.md"
# 49,512 characters, from Augment's own documentation: the limit is COMBINED across Workspace
# Guidelines and Rules, and chamnan's rules file counts against it. It was `None`, so nothing shrank
# toward it and nothing warned (R20 agent 1, 2026-09-10). Not a hard reject like CodeBuddy's — no evidence
# either way on what Augment does past it, so the default soft wording stands.
CEILING = 49_512


def render(body):
    """The block, unchanged."""
    return body.rstrip() + "\n"
