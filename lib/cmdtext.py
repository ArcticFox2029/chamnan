"""Which parts of a shell command are the work, and which are prose about it.

Two guards ask this and want DIFFERENT answers, which is why it is a parameter and not two copies:

* `chamnan_skill_pointer.py` routes to a procedure. A commit message naming `2dspeak/` is not
  Live2D work, and a heredoc body is text being handed to a command — neither should route.
* `boundary.py` guards the machine. A heredoc fed to `python3 -` or `bash -s` **is executed**, so
  dropping it there would hide the exact thing that rule exists to catch. It keeps heredocs and
  drops only what is unambiguously commentary.

🐛 [2026-09-23] Both lessons were live incidents an hour apart: the pointer fired on a commit
message, and the boundary guard fired on a heredoc that was WRITING A TEST about `defaults write`.
The first is noise to remove; the second is the guard working, and was left alone.
"""
import re

# Everything after a heredoc marker is body — greedy and un-anchored on purpose. A non-greedy
# `[\s\S]*?$` under re.MULTILINE stops at the first newline and leaves the body matching.
_HEREDOC = re.compile(r"<<-?'?\w+'?[\s\S]*")
_MESSAGE = re.compile(r"(?:-m|--message)\s+(?:\"[^\"]*\"|'[^']*')")
_COMMENT = re.compile(r"#.*$", re.MULTILINE)


def without_prose(command, drop_heredoc=True):
    """`command` with commentary removed: what is being RUN, not what is said about it."""
    if not command:
        return ""
    out = _MESSAGE.sub(" ", command)
    out = _COMMENT.sub(" ", out)
    if drop_heredoc:
        out = _HEREDOC.sub(" ", out)
    return out
