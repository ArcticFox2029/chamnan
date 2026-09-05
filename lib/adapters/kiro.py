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


def _fence_safe(text):
    """`text` with any line that is exactly `---` made unable to close the frontmatter early.

    Same hazard as Cursor's `.mdc`, same fix, and deliberately its own copy rather than a shared
    helper: these two agents happen to share a frontmatter convention today, and a shared helper
    would mean a change made for one silently changing the other. `***` renders identically, so
    nothing the writer of the rule intended is lost.
    """
    return "\n".join("***" if line.strip() == "---" else line for line in text.splitlines())


def render(body):
    """The block as a Kiro steering file."""
    return (f"---\n"
            f"inclusion: always\n"
            f"---\n\n"
            f"{_fence_safe(body).rstrip()}\n")
