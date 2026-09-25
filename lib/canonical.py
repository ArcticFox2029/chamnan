"""Was this command run in the shape its own script says is right? — asked BEFORE it runs.

🎯 [owner 2026-09-23] Three failures in one
hour, none of which any existing guard could see:

  * a report was dispatched around `research-on-account.sh`, so `round_report.py` never ran and no
    `R<n>` file was ever written;
  * `read_agent_report.py` was run without `--out`, so the local model's extract went to stdout and
    was gone the moment the turn ended;
  * both commands exited 0.

`gotcha.py` remembers what FAILED. Neither of these failed. A command that succeeds while doing
less than it was supposed to is structurally invisible to a failure log, and that is the whole gap
this module fills: it compares what is about to run against what the script itself declares.

**The declaration lives in the script, not in a table here.** A list of known-wrong invocations
kept in one place is the "assert the member, not the set" bug with extra steps — it would cover the
two commands that burned an hour today and silently miss the 109 other tools in this workspace. So
a script opts in by putting one line in its own docstring or header comments, spelled with the
two directive words built in `_REQUIRES_KEY` / `_INSTEAD_KEY` below, followed by a colon and either
the tokens that must be present or the thing to run instead. Two scripts in the development
workspace carry a real one; copy the shape from there.

🐛 [2026-09-23] (self-measured) The first version of this file put a literal example HERE, and the module then read
its own docstring and reported itself as an incorrectly-invoked script. A check that reads source
matches its own source — the directive names are assembled at runtime for exactly that reason, and
the same trap is recorded in `memory/rules/a-passing-check-may-be-a-decoration.md`.

The population this enforces is exactly "every script that declares one", derived from the
command about to run. Nothing is hardcoded, and it works the same in anybody else's repository.

**It never blocks and never rewrites the command.** Same rule as every hook in this package.
"""
import pathlib
import re
import shlex

# Only the head of a file is read. A directive belongs with the docstring or the header comments;
# one buried 400 lines down is not documentation anybody would find either.
HEAD_BYTES = 4_096
_SCRIPT = re.compile(r"[\w./-]+\.(?:py|sh|command)$|(?:^|/)chamnan-[\w-]+$")
# Assembled, never written whole: a literal here would match this file's own text. See the 🐛 above.
_REQUIRES_KEY = "chamnan-" + "canonical"
_INSTEAD_KEY = "chamnan-" + "instead"
_REQUIRES = re.compile(re.escape(_REQUIRES_KEY) + r":\s*(.+)")
_INSTEAD = re.compile(re.escape(_INSTEAD_KEY) + r":\s*(.+)")


def declarations(path):
    """What `path` declares about how it should be called. {} when it declares nothing."""
    try:
        head = pathlib.Path(path).read_bytes()[:HEAD_BYTES].decode("utf-8", "replace")
    except Exception:              # noqa: BLE001 — unreadable is "declares nothing"
        return {}
    out = {}
    m = _REQUIRES.search(head)
    if m:
        # Tokens, not a substring: `--out` must not be satisfied by `--output-dir`.
        out["requires"] = [t for t in m.group(1).split("#", 1)[0].split() if t]
    m = _INSTEAD.search(head)
    if m:
        out["instead"] = m.group(1).split("#", 1)[0].strip().rstrip('"').strip()
    return out


# 🐛 [2026-09-23] (self-measured) Caught live, minutes after this shipped: `git add` of a workspace script
# raised the notice for a script that was being COMMITTED, not run. A script name is an invocation
# only in command position — first word of a segment, or straight after an interpreter.
_INTERPRETERS = {"python", "python3", "py", "bash", "sh", "zsh", "dash", "ksh", "perl", "ruby",
                 "node", "uv", "pipx", "poetry", "nohup", "caffeinate", "exec", "command"}
_SEGMENT = re.compile(r"\s*(?:\|\||&&|[;|&\n])\s*")


def segments(command):
    """`command` cut into the pieces a shell runs separately — at `;`, `&&`, `||`, `|`, `&`, newline.

    Public because a second reader needs exactly this cut: `hooks/chamnan_commit_guard.py` asks
    whether a segment's command position is `git commit`. It carried its own copy of the pattern,
    and two copies of one question drift apart the first time either is fixed.
    """
    return _SEGMENT.split(command)


def _scripts_in(command):
    """Every token of `command` that is a script being INVOKED, not merely named."""
    found = []
    for segment in _SEGMENT.split(command):
        try:
            words = shlex.split(segment)
        except ValueError:         # unbalanced quotes — fall back to whitespace
            words = segment.split()
        for i, w in enumerate(words):
            if not _SCRIPT.search(w):
                continue
            before = [x for x in words[:i] if not x.startswith("-") and "=" not in x]
            if not before or pathlib.PurePath(before[-1]).name in _INTERPRETERS:
                found.append(w)
    return found


def _resolve(word, root):
    """The word as a path, tried where a command would actually find it."""
    p = pathlib.Path(word)
    if p.is_absolute():
        return p if p.exists() else None
    for base in ([pathlib.Path(root)] if root else []) + [pathlib.Path.cwd()]:
        cand = base / p
        if cand.exists():
            return cand
    return None


def advice(command, root=None):
    """One notice, or "" — which is the answer almost every time, and the point.

    A script that declares nothing is silent. A declaring script is checked on every invocation,
    so the guard cannot be applied to one member of a set and forgotten on the rest.
    """
    if not command:
        return ""
    words = set(_scripts_in(command)) | set(command.split())
    lines = []
    for word in _scripts_in(command):
        path = _resolve(word, root)
        if path is None:
            continue
        decl = declarations(path)
        if not decl:
            continue
        name = path.name
        missing = [t for t in decl.get("requires", []) if t not in words]
        if missing:
            lines.append(f"`{name}` is being run without {', '.join('`%s`' % t for t in missing)} "
                         f"— its own header says that is required for the result to land anywhere.")
        instead = decl.get("instead")
        if instead:
            lines.append(f"`{name}`: {instead}")
    # 🐛 [2026-09-23] (self-measured) One command naming the same script three times said the same sentence three
    # times — seen live in the session that wrote this file.
    lines = list(dict.fromkeys(lines))
    if not lines:
        return ""
    return "chamnan: " + " ".join(lines) + " Nothing is blocked."
