"""Which tool call would read a credential file into the session, so the hook can refuse it.

🎯 [2026-10-07] (owner's direction, 2026-10-07: "การเพิ่มความระมัดระวังในการเรียกใช้ข้อมูลสำคัญ แบบไม่ให้ llm
ได้ไป") chamnan refused credential files in its OWN commands -- `chamnan-peek` declines a real
`.env`, a kubeconfig, a private key -- while the agent's own Read tool, a `cat .env`, or a Grep aimed
at the file still put the values straight into the model's context. The redactor cannot help there:
hooks can refuse a call but cannot rewrite what a tool returns. So the refusal moves to the moment
before the call, through a PreToolUse `deny`. Verified before relying on it: in a scratch project a
`deny` stopped a planted `.env` from reaching the reply in `bypassPermissions` and `acceptEdits`, and
the documentation says it holds in every permission mode.

One list decides what counts: `redact.is_never_opened`, the same one peek uses, so the two can never
disagree about a file. A template (`.env.example`) is read as before. A command that only MOVES a
file (`cp`, `mv`, `source`, `git add`) is not a read and is not refused -- the value never reaches
the screen that way. Check 461.
"""
import re
import shlex
from pathlib import Path

import redact

# Commands that print a file they are given. A pipeline segment starting with one of these, or any
# segment with `<` reading from the file, is a read.
READERS = frozenset({
    "cat", "head", "tail", "less", "more", "bat", "batcat", "nl", "tac", "grep", "egrep", "fgrep",
    "rg", "ag", "sed", "awk", "gawk", "cut", "sort", "uniq", "strings", "xxd", "od", "hexdump",
    "base64", "diff", "jq", "yq", "type", "get-content", "gc", "view", "vim", "vi", "nano", "emacs",
    "column", "paste", "fold", "fmt", "pr", "iconv", "openssl", "keytool",
})
# `git` prints file contents only through these.
GIT_READERS = frozenset({"diff", "show", "log", "blame", "grep", "cat-file"})
_SEGMENTS = re.compile(r"\|\||&&|[|;&\n]")


# 🐛 [2026-10-07] (owner, 2026-10-07: "ก็มันทำงานได้ไหมหละ ถ้าต้องเรียกใช้ข้อมูลในการทำงาน เช่น ssh")
# Measured on 19 real working commands: `cat ~/.ssh/id_rsa.pub` (a PUBLIC key, pasted onto servers)
# and `openssl x509 -in server.crt -noout -enddate` (a certificate's expiry) were refused, because
# peek's refusal list also covers public material. A public key and a certificate are published by
# design, so the guard lets them through; private keys and env files stay refused. Check 461.
PUBLIC_SUFFIXES = (".pub", ".crt", ".cer")
# `openssl` commands that only inspect public material or a connection.
OPENSSL_PUBLIC = frozenset({"x509", "s_client", "verify", "crl", "version", "ciphers", "dgst"})


def _is_credential(token, root):
    token = token.strip().strip("'\"")
    if not token or token.startswith("-") or "=" in token and not token.startswith((".", "/")):
        return None
    if token.lower().endswith(PUBLIC_SUFFIXES):
        return None
    token = str(Path(token).expanduser()) if token.startswith("~") else token
    path = Path(token)
    if not path.is_absolute() and root is not None:
        path = Path(root) / path
    try:
        return token if redact.is_never_opened(path) else None
    except (OSError, ValueError):
        return None


def _words(segment):
    try:
        return shlex.split(segment, posix=True)
    except ValueError:
        return segment.split()


def bash_reads(command, root=None):
    """The credential file a shell command would print, or None."""
    text = str(command or "")
    if not text.strip():
        return None
    for segment in _SEGMENTS.split(text):
        words = _words(segment)
        if not words:
            continue
        # `< .env` and `<.env` feed the file to whatever runs; that is a read whatever the verb.
        for i, w in enumerate(words):
            if w == "<" and i + 1 < len(words):
                hit = _is_credential(words[i + 1], root)
                if hit:
                    return hit
            elif w.startswith("<") and len(w) > 1 and not w.startswith("<<"):
                hit = _is_credential(w[1:], root)
                if hit:
                    return hit
        start = 0
        while start < len(words) and (re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", words[start])
                                      or words[start] in ("sudo", "command", "exec", "env", "time")):
            start += 1
        if start >= len(words):
            continue
        verb = words[start].rsplit("/", 1)[-1].lower()
        args = words[start + 1:]
        if verb == "git":
            sub = next((a for a in args if not a.startswith("-")), "")
            if sub not in GIT_READERS:
                continue
        elif verb == "openssl" and (args[:1] and args[0] in OPENSSL_PUBLIC):
            continue
        elif verb not in READERS:
            continue
        for a in args:
            hit = _is_credential(a, root)
            if hit:
                return hit
    return None


def tool_reads(tool, tool_input, root=None):
    """The credential file this Read, Grep or Bash call would put into the session, or None."""
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    if tool == "Read":
        return _is_credential(str(tool_input.get("file_path") or ""), root)
    if tool == "Grep":
        return _is_credential(str(tool_input.get("path") or ""), root)
    if tool == "Bash":
        return bash_reads(tool_input.get("command"), root)
    return None


def refusal(name):
    """The reason handed back to the model when a read is refused."""
    import mdblock
    return (f"chamnan: `{mdblock.as_quoted(Path(name).name, 80)}` holds credentials or a key, so it is "
            f"not read into the session. Its variable NAMES, never values, are listed under "
            f"`## Configuration` in `.chamnan/MAP.md`. If a value is really needed, ask the user.")
