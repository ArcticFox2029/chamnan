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
    """
    import workspace as ws

    from . import safe_target

    base = ws.Path(root)
    target = safe_target(root, TARGET)

    if target.exists():
        first = target.read_text(encoding="utf-8", errors="replace").lstrip()
        if not first.startswith(MARKER):
            raise ValueError(
                f"{target} exists and was not written by chamnan. Zed reads the first of its nine "
                f"candidate files and stops, so replacing this would hide it. Move it aside first, "
                f"or delete it if it is stale.")
    else:
        for candidate in PRECEDENCE[1:]:
            # 🐛 `.exists()` FOLLOWS a symlink, and this loop then names the file it found. A
            # committed `AGENTS.md -> /etc/hosts` made the refusal message a boolean oracle for
            # "does that absolute path exist on this machine" -- repeatable across all nine
            # candidate names and across pull requests, and landing wherever the run's output
            # lands. It leaks existence only, never content, but the report it lands in is often
            # somewhere the person who wrote the symlink can read.
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

    ws.atomic_write_text(target, render(body))
    return target
