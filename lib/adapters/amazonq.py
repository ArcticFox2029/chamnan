"""Amazon Q — `.amazonq/rules/chamnan.md`.

Path read from Kiro's own `AI_ASSISTANT_CONFIGS` table, in the installed agent extension: Amazon Q
rules are `.md` under `.amazonq/rules`. That table gives Cursor a `frontMatterSchema` and a parser
and gives Amazon Q neither -- so as far as a product that imports from both is concerned, these
files are plain markdown.

Plain markdown is also the safer half of that uncertainty. A frontmatter block an agent does not
parse renders as a table or as stray dashes at the top of the context; context an agent does not
recognise as frontmatter is still context. Nothing is written that would have to be right.
"""

# 🎯 [2026-09-08] AWS IS WINDING THIS PRODUCT DOWN, and nothing here said so. Checked against
# AWS's own end-of-support announcement, fetched that day, and confirmed a second time by an
# independent round before it was written here
# (aws.amazon.com/blogs/devops/amazon-q-developer-end-of-support-announcement/):
#
#     2026-05-15   new Q Developer signups and subscriptions blocked
#     2026-05-29   Opus 4.6 removed from Q Developer Pro
#     2027-04-30   end of support for the IDE plugins and paid subscriptions
#
# AWS's own migration guidance names Kiro, which `kiro.py` beside this file already adapts for.
# The `.amazonq/rules/` format itself is unchanged, so this adapter is still correct for the
# product as it exists — this is a note about its LIFETIME, not its behaviour.
#
# Kept rather than removed, and the direction matters: somebody who had a subscription before the
# cutoff is a real user until 2027-04-30, and deleting their coverage early costs them for no gain.
# What the absence of this comment cost was different — a maintainer sizing effort against this
# file (a ceiling check, a frontmatter update) had no way to know they were investing in a
# wind-down (R8 agent 1, verified independently by R8 agent 16).
NAME = "amazonq"
TARGET = ".amazonq/rules/chamnan.md"
CEILING = None


def render(body):
    """The block, unchanged. There is no wrapper to add and adding one would be a guess."""
    return body.rstrip() + "\n"
