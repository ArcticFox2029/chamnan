"""Qwen Code (Alibaba) — `QWEN.md`.

A fork of Gemini CLI that renamed the context file, which is exactly the case that makes forks
worth checking rather than assuming: the tool it forked reads `GEMINI.md`, and inheriting that
answer would have produced a file Qwen Code never opens.

It carries the SessionStart hook machinery from its parent, so a hook is possible here. The file
is written instead for the same reason it is elsewhere: the file convention is documented and the
hook config shape for this fork is not, and a config written from a guessed schema fails silently.

No read-time size cap is documented -- the 16 MB figure that turns up is a write cap on tool
output, which is a different thing.
"""

NAME = "qwen"
TARGET = "QWEN.md"
CEILING = None


def render(body):
    """The block, unchanged."""
    return body.rstrip() + "\n"
