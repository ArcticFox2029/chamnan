"""Cline — `.clinerules/chamnan.md`.

Path read from Kiro's own `AI_ASSISTANT_CONFIGS` table, in the installed agent extension: Cline
reads `.md` and `.txt` under `.clinerules`. `.md` of the two, because the block is markdown and
`.txt` would be lying about it.

`.clinerules` is a DIRECTORY here. Cline also accepts a single `.clinerules` FILE, and that
ambiguity is the trap: writing the directory form into a repository that already has the file form
means `mkdir` fails on an existing file, and writing the file form would destroy rules the user
wrote. So this writes the directory form and `install` is left to the shared writer, whose
`mkdir(parents=True, exist_ok=True)` raises rather than clobbering when `.clinerules` is a file --
loud, at the moment it happens, with the path in the message.
"""

NAME = "cline"
TARGET = ".clinerules/chamnan.md"
CEILING = None


def render(body):
    """The block, unchanged. Cline's rules files carry no frontmatter."""
    return body.rstrip() + "\n"
