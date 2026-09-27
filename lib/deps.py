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
import json
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
# The file names a manifest can have, for a caller that sees one path and must decide whether it
# is a manifest at all.
MANIFEST_NAMES = frozenset(m.rsplit("/", 1)[-1].lower() for m in MANIFESTS)
MAX_COMMITS_REPORTED = 3

# A requirement line: the name, then whatever constraint follows. Stops at the first character that
# cannot be part of a name, so `ollama>=0.6.0  # comment` yields `ollama`.
_PY_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:[<>=!~\[;@(]|$)")
_GO_NAME = re.compile(r"^\s*(?:require\s+)?([a-z0-9][\w./-]*)\s+v\d")
_GEM_NAME = re.compile(r"""^\s*gem\s+["']([^"']+)["']""")
_TOML_LINE = re.compile(r"""^\s*["']?([A-Za-z0-9][A-Za-z0-9._-]*)["']?\s*=\s*(.*)$""")
_STRING = re.compile(r"""["']([^"']+)["']""")
_JSON_TABLES = ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies",
                "require", "require-dev")


def _requirement(text):
    """The package name at the start of a requirement string (`httpx>=0.27; python_version>'3'`)."""
    m = _PY_NAME.match(text.strip())
    return m.group(1).lower() if m else ""


def _strip_toml_comment(line):
    """Cut a TOML line at its comment `#`, ignoring one that sits inside a quoted string.

    Walks the line char by char, tracking whether the cursor is inside a `"..."` (which honours
    a `\\"` escape) or a `'...'` (TOML literal strings have no escapes at all). A `#` is only a
    comment marker outside both.
    """
    quote, escape = "", False
    for i, ch in enumerate(line):
        if quote:
            if quote == '"' and escape:
                escape = False
            elif quote == '"' and ch == "\\":
                escape = True
            elif ch == quote:
                quote = ""
            continue
        if ch in ("\"", "'"):
            quote = ch
        elif ch == "#":
            return line[:i]
    return line


def _array_still_open(line):
    """True while a `]` closing this array has not been seen OUTSIDE a quoted string.

    Mirrors `_strip_toml_comment`'s string tracking so a `]` inside an environment marker
    (`"rich; extra == 'x]'"`) does not read as the array's own closing bracket.
    """
    quote, escape = "", False
    for ch in line:
        if quote:
            if quote == '"' and escape:
                escape = False
            elif quote == '"' and ch == "\\":
                escape = True
            elif ch == quote:
                quote = ""
            continue
        if ch in ("\"", "'"):
            quote = ch
        elif ch == "]":
            return False
    return True


def _toml_names(text):
    """Names from a TOML manifest, read by TABLE rather than by any `key =` line.

    🐛 [2026-09-26] (self-measured) Every `key = value` line counted as a package, so `name`,
    `version` and `requires-python` from `[project]` and `edition` from `[package]` were "listed",
    while PEP 621's `dependencies = ["httpx>=0.27", ...]` -- the form most new Python projects
    use -- contributed only the word `dependencies`. Now: in a table whose name ends in
    `dependencies` (Cargo, Poetry, PDM, `[dependency-groups]`) or is `packages`/`dev-packages`
    (Pipfile), a key is a package -- unless its value is an array, when the key is a group name
    and the array's strings are the packages. In `[project]`, only `dependencies` counts, and
    `[project.optional-dependencies]` holds groups of arrays.

    🐛 [2026-09-27] (R27, 2026-09-27) The comment cut and the array-close check both looked for a
    bare character anywhere in the line, including inside a quoted string. Measured against
    tomllib: `dependencies = ["pkg @ git+https://example.org/r.git#egg=pkg", "httpx>=0.27"]`
    returned an empty set (the `#egg=` truncated the whole line before the array was read), and a
    multi-line array whose first item was `"rich; extra == 'x]'"` returned only `{rich}`, losing
    `click` on the next line, because the `]` inside the marker closed the array early. Both cuts
    now walk the line tracking quote state and only act outside a string.
    """
    out, table, in_array = set(), "", False
    for raw in text.splitlines():
        line = _strip_toml_comment(raw).strip()
        if not line:
            continue
        if in_array:
            out.update(n for n in map(_requirement, _STRING.findall(line)) if n)
            in_array = _array_still_open(line)
            continue
        if line.startswith("["):
            table = line.strip("[]").strip().strip('"').lower()
            continue
        m = _TOML_LINE.match(line)
        if not m:
            continue
        key, value = m.group(1).lower(), m.group(2).strip()
        deps_table = table.endswith("dependencies") or table in ("packages", "dev-packages")
        if value.startswith("[") and (deps_table or (table == "project" and key == "dependencies")):
            out.update(n for n in map(_requirement, _STRING.findall(value)) if n)
            in_array = _array_still_open(value)
        elif deps_table and not (key == "python" and "poetry" in table):
            out.add(key)
    return out


def names(text, manifest):
    """The package names a manifest lists, as a set. Unknown shapes return an empty set.

    Each format is read by its own structure. 🐛 [2026-09-26] (self-measured) It used to match every
    line against a pattern, so `package.json`'s `"name"`, `"version"` and each script were read as
    packages, `setup.py`'s `install_requires=[` became a package called `install_requires`, and a
    `Gemfile` matched nothing at all.
    """
    if not text:
        return set()
    lower = manifest.lower().rsplit("/", 1)[-1]
    if lower.endswith(".json"):
        try:
            data = json.loads(text)
        except (ValueError, RecursionError):
            return set()
        if not isinstance(data, dict):
            return set()
        return {str(k).lower() for t in _JSON_TABLES if isinstance(data.get(t), dict)
                for k in data[t] if k != "php" and not str(k).startswith("ext-")}
    if lower.endswith(".toml") or lower == "pipfile":
        return _toml_names(text)
    if lower == "setup.py":
        block = re.search(r"install_requires\s*=\s*\[(.*?)\]", text, re.S)
        return {n for n in map(_requirement, _STRING.findall(block.group(1)))} - {""} if block else set()
    out = set()
    for raw in text.splitlines():
        line = raw.split("#", 1)[0]
        if not line.strip() or line.lstrip().startswith(("-", "//")):
            continue
        pattern = (_GO_NAME if lower.endswith(".mod") else _GEM_NAME if lower == "gemfile"
                   else _PY_NAME)
        m = pattern.match(line)
        if m:
            out.add(m.group(1).strip().lower())
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


def added_back(root, rel, current, new):
    """{package: (subject, date)} for packages `new` adds to manifest `rel` that it once listed and removed.

    🎯 [2026-09-26] (owner) The delivery `removals` never had. Built on 2026-09-23 from the owner's
    direction -- *an agent proposing a library has no idea the team removed it* -- the reader shipped
    and nothing ever called it, while the README said an agent would be told. The owner, 2026-09-26:
    *"ทำต่อสาย"*. Only the one manifest being edited is walked, and only when the edit adds a name.
    """
    added = names(new, rel) - names(current, rel)
    if not added:
        return {}
    gone = removals(root, manifests=(rel,))
    return {n: gone[n][0] for n in sorted(added) if n in gone}


def removals(root, window=WINDOW, manifests=None):
    """{package: [(commit subject, date), ...]} for names a manifest listed and then stopped listing.

    Walks each manifest's own revisions newest-first and compares consecutive name sets. `--follow`
    keeps a file's history across a move, and each revision is read at the path it had THEN.
    🐛 [2026-09-26] (self-measured) It read every revision at today's path, so across the one move
    this docstring cites -- the app moving into `miki-hybridge-ai/` -- all 19 older revisions of
    its requirements file read as empty and were skipped: 0 removals found in a history that had
    them. `--name-only` gives the path each commit had.
    """
    found = {}
    for manifest in (manifests or MANIFESTS):
        log = _run(root, ["log", "--follow", "--no-merges", "-n", str(window), "--name-only",
                          "--format=%x00%H\t%ad\t%s", "--date=short", "--", manifest])
        revs = []
        for rec in log.split("\x00")[1:]:
            head, _, rest = rec.partition("\n")
            path = next((l.strip() for l in rest.splitlines() if l.strip()), "")
            if head.count("\t") >= 2 and path:
                revs.append(head.split("\t", 2) + [path])
        if len(revs) < 2:
            continue
        for newer, older in zip(revs, revs[1:]):
            after = names(_run(root, ["show", f"{newer[0]}:{newer[3]}"]), manifest)
            before = names(_run(root, ["show", f"{older[0]}:{older[3]}"]), manifest)
            # Both sides must be readable. An empty `after` is what a deleted or renamed manifest
            # looks like, and calling every package in it removed on that commit is the same
            # mistake as reading `-` lines.
            if not before or not after:
                continue
            for gone in sorted(before - after):
                found.setdefault(gone, []).append((newer[2][:120], newer[1]))
    return {k: v[:MAX_COMMITS_REPORTED] for k, v in found.items()}
