"""Zed — `.rules`, and only when writing it would not hide something else.

Zed takes the FIRST match from a fixed list of nine filenames and does not merge them:

    .rules  .cursorrules  .windsurfrules  .clinerules  .github/copilot-instructions.md
    AGENT.md  AGENTS.md  CLAUDE.md  GEMINI.md

`.rules` is first. So writing it always works -- and always SHADOWS whatever the repository was
using before, silently, because Zed reads one file and stops. A repository with a `.cursorrules`
somebody wrote would lose it to a chamnan file that says nothing about their conventions.

So `install()` looks before it writes. With none of the nine present it writes `.rules`. With one
present it REFUSES and names the file Zed is reading today, because the alternatives are both
worse: writing `.rules` hides their file, and writing further down the list produces a file Zed
will never look at while reporting success.

The exception is `.rules` itself already carrying chamnan's own marker -- that is this adapter's
previous run, and replacing it is the whole point of running again.
"""

NAME = "zed"
TARGET = ".rules"
CEILING = None

# Zed's own precedence order, from its documentation source. First match wins; nothing is merged.
PRECEDENCE = (".rules", ".cursorrules", ".windsurfrules", ".clinerules",
              ".github/copilot-instructions.md", "AGENT.md", "AGENTS.md",
              "CLAUDE.md", "GEMINI.md")

MARKER = "<!-- chamnan:zed -->"


def render(body):
    """The block, marked so a later run can tell its own file from somebody else's."""
    return f"{MARKER}\n{body.rstrip()}\n"


def install(root, body, command=""):
    """Write `.rules`, unless doing so would hide a file Zed is already reading.

    `command` is unused; it is in the signature because that is the shape every adapter's install
    has.

    The check on what is already there and the write that follows it go through ONE held handle:
    this adapter reads the target before deciding whether to replace it, and resolving the path a
    second time is the window a swap-after-the-check race walks through. One function rather than
    a helper, so the guard call and the write stay where the structural check can see them both.
    """
    import workspace as ws

    from . import held_target, read_target, write_target

    base = ws.Path(root)
    with held_target(root, TARGET) as target:
        first = read_target(target)
        if first is not None:
            if not first.lstrip().startswith(MARKER):
                raise ValueError(
                    f"{target.path} exists and was not written by chamnan. Zed reads the first of "
                    f"its nine candidate files and stops, so replacing this would hide it. Move it "
                    f"aside first, or delete it if it is stale.")
        else:
            for candidate in PRECEDENCE[1:]:
                # 🐛 `.exists()` FOLLOWS a symlink, and this loop then names the file it found. A
                # committed `AGENTS.md -> /etc/hosts` made the refusal message a boolean oracle for
                # "does that absolute path exist on this machine" -- repeatable across all nine
                # candidate names and across pull requests, and landing wherever the run's output
                # lands. It leaks existence only, never content, but the report it lands in is
                # often somewhere the person who wrote the symlink can read.
                #
                # A candidate that is a symlink is treated as PRESENT without asking where it goes:
                # Zed would read whatever is there, which is the thing this loop is about, and no
                # question is put to the far side.
                probe = base / candidate
                if probe.is_symlink():
                    raise ValueError(
                        f"{candidate} in this repository is a symlink. Zed reads the first of its "
                        f"nine candidate files and stops, so what it would read is not this "
                        f"repository's to say. Nothing written.")
                if probe.exists():
                    raise ValueError(
                        f"Zed is reading {candidate} in this repository. Writing .rules would take "
                        f"precedence and hide it, and writing anything lower in Zed's list would be "
                        f"a file it never opens. Nothing written.")

        write_target(target, render(body))
        return target.path
