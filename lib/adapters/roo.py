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

Kilo Code is a fork of Roo and reads the same tiers under its own directory name; it gets its own
module rather than an alias, because "a fork today" is not a promise about tomorrow.
"""

NAME = "roo"
TARGET = ".roo/rules/chamnan.md"
CEILING = None


def render(body):
    """The block, unchanged. Roo's rules files carry no frontmatter."""
    return body.rstrip() + "\n"
