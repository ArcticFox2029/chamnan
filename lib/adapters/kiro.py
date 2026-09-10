"""Kiro — `.kiro/steering/chamnan.md`.

**Verified against the installed application, not from memory.** Kiro 's agent extension carries
its own steering logic, and reading it settles three things:

  - steering files live under `.kiro/steering/` as `.md`
  - their frontmatter key is `inclusion`, one of `always`, `fileMatch` or `manual`, with
    `fileMatchPattern` alongside when it is `fileMatch`
  - Kiro converts a Cursor rule's frontmatter into its own, mapping `alwaysApply: true` to
    `inclusion: always` -- which independently confirms the choice the cursor adapter makes

`inclusion: always` is the right one here for the same reason `alwaysApply: true` is right for
Cursor: this block is orientation the agent should hold before it starts, not a rule that fires
when a particular file is opened.

Kiro reads the file off disk, so nothing truncates it and `CEILING` is None.
"""

NAME = "kiro"
TARGET = ".kiro/steering/chamnan.md"
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
# real effect the function had was the one nobody wrote down (R4 agent 1, finding 10).
#
# This is not a reversal of the round that kept the six copies and policed them for divergence
# (R5 agent 3, 2026-09-06): that round asked whether the copies AGREED, and they did. It never
# asked whether the thing they agreed on was needed.
#
# What replaces it is a check over the SET rather than a guard in each member: the suite asserts
# that every frontmatter adapter closes its frontmatter before its body. An adapter that one day
# does not is told so, and can then be given a guard for the reason that is actually true.


def render(body):
    """The block as a Kiro steering file."""
    return (f"---\n"
            f"inclusion: always\n"
            f"---\n\n"
            f"{body.rstrip()}\n")
