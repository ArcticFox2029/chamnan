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
# 🐛 [2026-09-23] `drop_heredoc=False` made the boundary guard fire on its OWN commit message,
# which named the rule's command list inside `git commit -F - <<EOF`. A heredoc is only executable
# when an interpreter is reading it; one going to `git commit -F -`, `cat > file` or `tee` is data.
# So the question is not "is there a heredoc" but "is something about to RUN it".
_EXECUTES_STDIN = re.compile(
    r"(?:^|[|;&]\s*)(?:sudo\s+)?(?:python[0-9.]*|bash|sh|zsh|ksh|perl|ruby|node|osascript)"
    r"(?:\s+-[a-zA-Z]*)*\s*(?:-|-s|-c)?\s*<<", re.MULTILINE)
_MESSAGE = re.compile(r"(?:-m|--message)\s+(?:\"[^\"]*\"|'[^']*')")
_COMMENT = re.compile(r"#.*$", re.MULTILINE)


def without_prose(command, drop_heredoc=True):
    """`command` with commentary removed: what is being RUN, not what is said about it.

    `drop_heredoc=True` drops every heredoc body — what the pointer wants, since none of them is a
    command it should route on. `False` keeps only the ones an interpreter is about to execute,
    which is what the boundary guard wants: it must see `python3 - <<EOF` and must not see a commit
    message. Neither guard wants ALL heredocs kept, so there is no third setting.
    """
    if not command:
        return ""
    out = _MESSAGE.sub(" ", command)
    out = _COMMENT.sub(" ", out)
    if drop_heredoc or not _EXECUTES_STDIN.search(out):
        out = _HEREDOC.sub(" ", out)
    return out
