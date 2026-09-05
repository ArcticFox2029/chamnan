"""Goose — `.goosehints`.

Plain text, no frontmatter, read from the project directory and up the git hierarchy, with
`~/.config/goose/.goosehints` as the global one. Goose reads a root `AGENTS.md` by default as well
(R8 agent 1), so a repository that has run `--write generic` was already reaching it; `.goosehints`
is the file Goose's own convention names, and it is what this adapter is for.

Not "(Block)" any more: the project moved to the Linux Foundation's AAIF. Attribution in a docstring
goes stale silently, which is why the sentence above names the FILE and not the vendor. The format supports `@file` references, which
chamnan does not use: the block is already the content, and a reference would make Goose read a
file that says the same thing one indirection away.

Goose also has a `SessionStart`-shaped hook in its extension system. It is not used here for the
same reason Continue's is not: a hook config written from a schema nobody verified fails silently,
and the documented file mechanism does not.

**No extension, which is the trap.** `.goosehints` has no suffix, so an editor that decides syntax
by extension shows it as plain text and a `.gitignore` rule written as `*.goosehints` never
matches it. `ignore_line()` returns the path with a leading slash, which does.
"""

NAME = "goose"
TARGET = ".goosehints"
CEILING = None


def render(body):
    """The block, unchanged. Goose injects the hints file verbatim."""
    return body.rstrip() + "\n"
