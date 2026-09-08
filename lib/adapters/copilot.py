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
