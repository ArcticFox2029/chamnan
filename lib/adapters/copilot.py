"""GitHub Copilot — `.github/instructions/chamnan.instructions.md`.

**Not `.github/copilot-instructions.md`, and the choice is a trade-off worth stating.** That file
is read on every Copilot surface, which is more coverage than this one gets -- but it is a file
people write themselves, and there is exactly one of it. Writing chamnan's block into it means
either destroying what they wrote or editing inside markers in a file whose whole purpose is to be
theirs. A `.instructions.md` file under `.github/instructions/` is chamnan's own, can be deleted
without touching anything of theirs, and is read on most surfaces including VS Code Chat and the
Copilot CLI.

Coverage lost quietly is bad; somebody's instructions deleted is worse.

**The trade-off above is against `copilot-instructions.md`. There is a third source, and it is
`generic.py`'s.** GitHub's own documentation names three: the repo-wide file, path-specific
`.instructions.md` files, and "AGENTS.md files anywhere in the repository" -- and says "all sets of
relevant instructions are provided to Copilot", combined rather than chosen between (fetched
2026-09-08, docs.github.com/en/copilot/concepts/response-customization). So a repository that has
run both `--write generic` and `--write copilot` sends the identical block to this one vendor twice
every session and pays for it twice.

That is warned about where somebody can act on it -- `chamnan-context --write` says so at the
moment it creates the second file, and `ALSO_READS_AGENTS_MD` in `__init__.py` is the list it
checks. It is written here as well because a future round reading this file alone would otherwise
have to re-derive it from GitHub's docs, which is how the same fact gets discovered three times.
Neither file is removed: `.instructions.md` still reaches surfaces a bare `AGENTS.md` does not,
which is the reason this adapter exists and is still true (R8 agent 1).

`applyTo` is the frontmatter key these files take, and `**` is its always-on form.

**Copilot's support is per-surface, not one switch**, which is why no ceiling is declared: the
4,000-character cap that once applied to code review was removed, and GitHub's remaining guidance
is a recommendation about length rather than a limit anything enforces. A ceiling invented to look
careful would cut the block for no measured reason.
"""

NAME = "copilot"
# This vendor reads the root `AGENTS.md` AS WELL AS its own file, so a repository that has
# run both `--write generic` and `--write <this>` sends the identical block twice, every
# session, and pays for it twice. Declared here rather than listed in `__init__.py`:
# 🐛 [2026-09-10] that list held four names while EIGHT vendors qualified, and the evidence
# for the missing four was sitting in their own docstrings. A set kept beside the thing it
# describes cannot drift from it (R4 agent 1, 2026-09-10, finding 6).
# Evidence: docs.github.com/en/copilot/concepts/response-customization — combines,
# not chooses (verified 2026-09-08).
ALSO_READS_AGENTS_MD = True

TARGET = ".github/instructions/chamnan.instructions.md"
CEILING = None


# 🐛 [2026-09-10] `_fence_safe` lived here, in six byte-identical copies, rewriting any body
# line that was exactly `---` to `***`. Its docstring said an untreated `---` "would end the
# frontmatter early, and every line after it would be read as the rule's body starting in the
# middle of a sentence" — and that cannot happen. `render()` below emits `---`, the keys, and a
# CLOSING `---` before the body is reached, so the frontmatter is shut by chamnan's own delimiter
# and a body line can no longer close anything. Verified for all six adapters.
#
# So the guard bought nothing, and it was not free. A `---` that FOLLOWS a text line is a setext
# `<h2>` underline in CommonMark; rewriting it to `***` turns somebody's heading into a paragraph
# plus a horizontal rule, which changes the outline of the document the agent is handed. The one
# real effect the function had was the one nobody wrote down (R4 agent 1, 2026-09-10, finding 10).
#
# This is not a reversal of the round that kept the six copies and policed them for divergence
# (R5 agent 3, 2026-09-06): that round asked whether the copies AGREED, and they did. It never
# asked whether the thing they agreed on was needed.
#
# What replaces it is a check over the SET rather than a guard in each member: the suite asserts
# that every frontmatter adapter closes its frontmatter before its body. An adapter that one day
# does not is told so, and can then be given a guard for the reason that is actually true.


def render(body):
    """The block as a Copilot instructions file that applies everywhere."""
    return (f"---\n"
            f"applyTo: \"**\"\n"
            f"---\n\n"
            f"{body.rstrip()}\n")
