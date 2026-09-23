"""What this repository has already tried and put down — read from the manifests' own history.

🎯 [owner 2026-09-23, direction F] An agent proposing a library has no idea the team removed it
last quarter and wrote down why. That knowledge is in the repository already, in the commits that
touched `requirements.txt` and its siblings, and nothing has ever read it.

**This is not a vulnerability scanner and must not become one.** It carries no database, makes no
network call, and knows nothing about any package except whether THIS repository once listed it and
stopped. `why-chamnan-was-built-and-what-it-refuses-to-be.md` draws that line; a scanner is a
different product and the outreach rules say so.

🐛 **A diff line is the wrong signal, and the data says so.** The spec for this direction read
removed (`-`) lines out of `git log -p`. Measured over 600 commits of three repositories on the
machine it was written on: **26 such lines, of which zero were removals.** Fifteen came from moving
the app into a subdirectory, ten from one commit that translated the file's comments from Thai to
English and so rewrote every line, and one from a version bump that put the same package straight
back. A reader of `-` lines would have been wrong every single time.

So this compares the SET OF NAMES between two revisions of a manifest. A package counts as removed
when its name was listed before and is not listed after — which reformatting, comment translation,
re-ordering, a version bump and a file move all leave alone.
"""
import re
import subprocess

import workspace as ws

# Where each ecosystem writes down what it depends on. Names only: this never opens a lock file's
# resolved tree, which is generated and would report a transitive package as a decision somebody made.
MANIFESTS = (
    "requirements.txt", "requirements/requirements.txt", "pyproject.toml", "Pipfile", "setup.py",
    "package.json", "go.mod", "Cargo.toml", "Gemfile", "composer.json",
)
# How far back to look. The same window churn uses, for the same reason: far enough to see what a
# project has worked through, near enough that a decision from three years ago is not presented as
# current practice.
WINDOW = 600
MAX_COMMITS_REPORTED = 3

# A requirement line: the name, then whatever constraint follows. Stops at the first character that
# cannot be part of a name, so `ollama>=0.6.0  # comment` yields `ollama`.
_PY_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:[<>=!~\[;]|$)")
_JSON_NAME = re.compile(r'^\s*"([^"]+)"\s*:\s*"')
_GO_NAME = re.compile(r"^\s*([a-z0-9][\w./-]*)\s+v\d")
_TOML_NAME = re.compile(r'^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*=')


def names(text, manifest):
    """The package names a manifest lists, as a set. Unknown shapes return an empty set.

    Comments are dropped before matching for the Python shapes, because this repository's own
    requirements file carries a paragraph of explanation after most entries — in two languages,
    across one commit that rewrote all of them.
    """
    out = set()
    if not text:
        return out
    lower = manifest.lower()
    for raw in text.splitlines():
        line = raw.split("#", 1)[0] if lower.endswith((".txt", ".toml", "Pipfile".lower())) else raw
        if not line.strip() or line.lstrip().startswith(("-", "//")):
            continue
        for pattern in ((_PY_NAME,) if lower.endswith(".txt")
                        else (_JSON_NAME,) if lower.endswith(".json")
                        else (_GO_NAME,) if lower.endswith(".mod")
                        else (_TOML_NAME, _PY_NAME)):
            m = pattern.match(line)
            if m:
                out.add(m.group(1).strip().lower())
                break
    return out


def _run(root, args):
    if not ws.git_can_speak_for(root):
        return ""
    try:
        # Built as one list rather than `[...] + args`: the sweep that proves nothing in this
        # package reaches a shell reads the argv HEAD, and a concatenation is a BinOp it cannot
        # see through — which is the same "an AST check cannot see through a helper" shape this
        # project has recorded before.
        argv = ["git", "-C", str(root), "-c", "core.quotePath=false"]
        argv.extend(args)
        r = subprocess.run(argv,
                           stdin=subprocess.DEVNULL, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=20)
    except ws.git_cannot_answer():
        return ""
    return r.stdout if r.returncode == 0 else ""


def removals(root, window=WINDOW):
    """{package: [(commit subject, date), ...]} for names a manifest listed and then stopped listing.

    Walks each manifest's own revisions newest-first and compares consecutive name sets. `--follow`
    keeps a file's history across the move that this repository's own history contains, and without
    it every entry in the moved file reads as removed on the day of the move.
    """
    found = {}
    for manifest in MANIFESTS:
        log = _run(root, ["log", "--follow", "--no-merges", "-n", str(window),
                          "--format=%H\t%ad\t%s", "--date=short", "--", manifest])
        revs = [line.split("\t", 2) for line in log.splitlines() if line.count("\t") >= 2]
        if len(revs) < 2:
            continue
        for newer, older in zip(revs, revs[1:]):
            after = names(_run(root, ["show", f"{newer[0]}:./{manifest}"]), manifest)
            before = names(_run(root, ["show", f"{older[0]}:./{manifest}"]), manifest)
            # Both sides must be readable. An empty `after` is what a deleted or renamed manifest
            # looks like, and calling every package in it removed on that commit is the same
            # mistake as reading `-` lines.
            if not before or not after:
                continue
            for gone in sorted(before - after):
                found.setdefault(gone, []).append((newer[2][:120], newer[1]))
    return {k: v[:MAX_COMMITS_REPORTED] for k, v in found.items()}
