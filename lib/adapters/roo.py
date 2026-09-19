"""Roo Code — `.roo/rules/chamnan.md`.

From Roo Code's own documentation. It reads rules from, in order:

    1. global    ~/.roo/rules/ and ~/.roo/rules-{mode}/
    2. workspace .roo/rules/ and .roo/rules-{mode}/          <- what this writes
    3. legacy    .roorules, .roorules-{mode}, .clinerules    <- only when 2 is absent
    4. AGENTS.md / AGENT.md at the workspace root

Workspace rules take precedence over global ones on conflict, and unlike Zed these are MERGED
rather than first-match-wins -- so writing here adds to what the repository already has instead of
hiding it.

**The legacy tier is why this is a separate adapter rather than reusing cline's.** Roo reads
`.clinerules`, but only when no directory-based rules exist. A repository where chamnan had
written `.clinerules/chamnan.md` for Cline would have that silently stop being read by Roo the
moment anyone added `.roo/rules/`. Writing the modern path directly means Roo's own precedence
never has to be reasoned about.

Kilo Code is a fork of Roo and reads the same tiers under its own directory name. It is an ALIAS
to `generic` (root `AGENTS.md`), not a module of its own -- `ALIASES["kilo"]` in `__init__.py`, and
there has never been a `kilo.py`.

🐛 [2026-09-08] This paragraph used to say the opposite: that Kilo "gets its own module rather than
an alias, because 'a fork today' is not a promise about tomorrow." That was false in the commit
that wrote it -- `55c32f0a` made Kilo an alias and, in this sibling file, claimed it had not, and
its own message even lists Kilo among the eight agents that became aliases. Not staleness from a
later change: wrong the moment it was written, and it sat in the shipped docstring for five days
across several research rounds, because every round checked this file against Roo's behaviour and
none checked its prose against `__init__.py`'s table (R8 agent 1, 2026-09-08).

**The extension was archived on 2026-05-15** (RooCodeInc/Roo-Code, `archived: true`, confirmed via
the GitHub API 2026-09-05). Kept rather than removed: an archived extension still runs for everyone
who has it installed, and deleting the adapter would take chamnan's block away from them to save one
small module. Recorded here so the next vendor sweep does not spend a search rediscovering it.
"""

NAME = "roo"
# This vendor reads the root `AGENTS.md` AS WELL AS its own file, so a repository that has
# run both `--write generic` and `--write <this>` sends the identical block twice, every
# session, and pays for it twice. Declared here rather than listed in `__init__.py`:
# 🐛 [2026-09-10] that list held four names while EIGHT vendors qualified, and the evidence
# for the missing four was sitting in their own docstrings. A set kept beside the thing it
# describes cannot drift from it (R4 agent 1, 2026-09-10, finding 6).
# Evidence: roocodeinc.github.io/Roo-Code/features/custom-instructions — merged by default, opt-OUT
# via `roo-cline.useAgentRules`, since v3.38 (verified 2026-09-08).
ALSO_READS_AGENTS_MD = True

TARGET = ".roo/rules/chamnan.md"
CEILING = None


def render(body):
    """The block, unchanged. Roo's rules files carry no frontmatter."""
    return body.rstrip() + "\n"
