"""Aider — `CONVENTIONS.md`, plus a line the user has to add themselves.

**Aider does not auto-discover anything.** This is the one agent here where writing the file is not
enough, and pretending otherwise would be the exact failure this package is built to avoid: a file
on disk, a success message, and an agent that never opens it.

`CONVENTIONS.md` is the name Aider's own documentation uses, and it is loaded in one of two ways --
`/read CONVENTIONS.md` typed in the chat, or a `read:` key in `.aider.conf.yml`. Files loaded that
way are marked read-only and prompt-cached, which is the right treatment for this block.

`.aider.conf.yml` is NOT written. It is the user's file, it is YAML, and chamnan has no YAML parser
-- it depends on nothing outside the standard library and that is a property worth more than this
one convenience. A hand-edited line the user can see beats a rewritten file they cannot check.
"""

NAME = "aider"
TARGET = "CONVENTIONS.md"
CEILING = None

# Printed by the CLI after writing, because writing the file is only half of being installed.
MANUAL_STEP = ("Aider does not auto-discover this file. Add it to `.aider.conf.yml`:\n"
               "    read: CONVENTIONS.md\n"
               "  or type `/read CONVENTIONS.md` in an Aider session.")


def render(body):
    """The block, unchanged. Aider injects the file verbatim."""
    return body.rstrip() + "\n"
