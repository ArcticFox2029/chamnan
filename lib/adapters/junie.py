"""JetBrains Junie — `.junie/AGENTS.md`.

Junie's current project file is `AGENTS.md` inside its own `.junie/` directory, with
`~/.junie/AGENTS.md` as the global one. `.junie/guidelines.md` is the legacy name and is still
read; the current name is written because a repository set up today should not start on the old
one.

**The directory is what makes this its own adapter rather than an alias to AGENTS.md.** Junie
reads `.junie/AGENTS.md`, not the root file, so a repository that only has a root `AGENTS.md`
gives Junie nothing -- and the reverse is also true, which is why writing here cannot conflict
with the root file another agent reads.
"""

NAME = "junie"
TARGET = ".junie/AGENTS.md"
CEILING = None


def render(body):
    """The block, unchanged. Junie's guidelines file carries no frontmatter."""
    return body.rstrip() + "\n"
