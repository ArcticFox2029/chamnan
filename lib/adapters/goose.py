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

**No extension, which is a small trap.** `.goosehints` has no suffix, so an editor that decides
syntax by extension shows it as plain text.

🐛 [2026-09-08] This docstring used to add that a `.gitignore` rule written as `*.goosehints`
"never matches it". That is FALSE and it shipped: git's `*` matches an empty string, so
`*.goosehints` ignores `.goosehints` perfectly well. Measured, four rules against a repository
holding a root and a nested copy:

    *.goosehints     ignores  .goosehints  and  sub/
    .goosehints      ignores  .goosehints  and  sub/
    /.goosehints     ignores  .goosehints
    **/.goosehints   ignores  .goosehints  and  sub/

The leading slash `ignore_line()` returns is still the right answer, for the reason the false claim
was hiding: it is the only one of the four that ignores THIS file and nothing else. The other three
also swallow a `.goosehints` a developer wrote deliberately in a subdirectory -- which Goose reads,
walking up from the working directory -- and `*.goosehints` additionally takes any `team.goosehints`
or `staging.goosehints` beside it. Anchoring is about not ignoring somebody else's file, not about
matching this one.
"""

NAME = "goose"
# This vendor reads the root `AGENTS.md` AS WELL AS its own file, so a repository that has
# run both `--write generic` and `--write <this>` sends the identical block twice, every
# session, and pays for it twice. Declared here rather than listed in `__init__.py`:
# 🐛 [2026-09-10] that list held four names while EIGHT vendors qualified, and the evidence
# for the missing four was sitting in their own docstrings. A set kept beside the thing it
# describes cannot drift from it (R4 agent 1, finding 6).
# Evidence: this adapter's own docstring above: Goose reads a root `AGENTS.md` by default as well
# as `.goosehints` (R8 agent 1).
ALSO_READS_AGENTS_MD = True

TARGET = ".goosehints"
CEILING = None


def render(body):
    """The block, unchanged. Goose injects the hints file verbatim."""
    return body.rstrip() + "\n"
