"""GitHub Copilot — `.github/instructions/chamnan.instructions.md`.

**Not `.github/copilot-instructions.md`, and the choice is a trade-off worth stating.** That file
is read on every Copilot surface, which is more coverage than this one gets -- but it is a file
people write themselves, and there is exactly one of it. Writing chamnan's block into it means
either destroying what they wrote or editing inside markers in a file whose whole purpose is to be
theirs. A `.instructions.md` file under `.github/instructions/` is chamnan's own, can be deleted
without touching anything of theirs, and is read on most surfaces including VS Code Chat and the
Copilot CLI.

Coverage lost quietly is bad; somebody's instructions deleted is worse.

`applyTo` is the frontmatter key these files take, and `**` is its always-on form.

**Copilot's support is per-surface, not one switch**, which is why no ceiling is declared: the
4,000-character cap that once applied to code review was removed, and GitHub's remaining guidance
is a recommendation about length rather than a limit anything enforces. A ceiling invented to look
careful would cut the block for no measured reason.
"""

NAME = "copilot"
TARGET = ".github/instructions/chamnan.instructions.md"
CEILING = None


def _fence_safe(text):
    """`text` with any line that is exactly `---` unable to close the frontmatter early."""
    return "\n".join("***" if line.strip() == "---" else line for line in text.splitlines())


def render(body):
    """The block as a Copilot instructions file that applies everywhere."""
    return (f"---\n"
            f"applyTo: \"**\"\n"
            f"---\n\n"
            f"{_fence_safe(body).rstrip()}\n")
