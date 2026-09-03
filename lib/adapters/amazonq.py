"""Amazon Q — `.amazonq/rules/chamnan.md`.

Path read from Kiro's own `AI_ASSISTANT_CONFIGS` table, in the installed agent extension: Amazon Q
rules are `.md` under `.amazonq/rules`. That table gives Cursor a `frontMatterSchema` and a parser
and gives Amazon Q neither -- so as far as a product that imports from both is concerned, these
files are plain markdown.

Plain markdown is also the safer half of that uncertainty. A frontmatter block an agent does not
parse renders as a table or as stray dashes at the top of the context; context an agent does not
recognise as frontmatter is still context. Nothing is written that would have to be right.
"""

NAME = "amazonq"
TARGET = ".amazonq/rules/chamnan.md"
CEILING = None


def render(body):
    """The block, unchanged. There is no wrapper to add and adding one would be a guess."""
    return body.rstrip() + "\n"
