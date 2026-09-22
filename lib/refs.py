"""Every place a name is actually USED, for the languages where that can be answered exactly.

The tool for this repository's most-recorded defect: a fix applied to one member of a set and
forgotten in the identical ones beside it, eighteen recorded instances. The rule
`the-set-not-the-member` tells you to find the whole population; it never gave you anything to find
it with, and `grep` is not that thing.

Measured on one file holding every hard case -- a docstring, an import, a string literal, a comment,
a method of the same name, a shadowed local, and three real calls: **grep reports nine lines, this
reports three.** Six of grep's nine are noise, and one of the two it cannot distinguish at all is
the shadowed local, where the name means something else entirely.

**Python only, and that is stated rather than implied.** The adapters extract DECLARATIONS by
pattern, which is durable because a declaration has a fixed shape. A call site does not: `foo()`
appears in comments, in strings, in a different language embedded in the same file. A regex sweep
across twenty-two languages is the false-positive machine this project has refused fifteen times,
so the answer here is "exact where exactness is possible, and named as incomplete everywhere else"
-- the same thing `mapper`'s own coverage line already says when it reports how many rows carried a
claim nothing checked.
"""
import ast
import os

# 🐛 [2026-09-22] (self-measured) This was 800,000 and the first real run proved the number wrong.
# `tests/run_tests.py` in this package is 2.8 MB, so it landed in "not judged" -- and it is exactly
# where the references were that this module exists to find: the two checks reaching
# `whole_graphemes` through `mapper._clip` that a grep by function name missed by hand the day
# before. A cap chosen for cost had hidden the defect the tool was written for.
#
# Parsing it costs 2.7 s and finds 29 references. This is a command somebody asked for, not a hook
# on every keystroke, and a few seconds is the right trade against a wrong answer. 4 MB matches
# what `chamnan_file_pointer` already refuses to read of `MAP.md`, so the pathological case -- a
# fifty-megabyte bundle -- is still refused, and refusing it is still COUNTED rather than hidden.
MAX_BYTES = 4_000_000


def _bound_locally(fn):
    """Names this function binds itself: arguments, assignments, imports, comprehension targets.

    A call to one of these is a call to something else that happens to share a name, and reporting
    it is the difference between an answer and a list of coincidences.
    """
    out = set()
    a = getattr(fn, "args", None)
    if a is not None:
        for x in list(a.posonlyargs) + list(a.args) + list(a.kwonlyargs):
            out.add(x.arg)
        if a.vararg:
            out.add(a.vararg.arg)
        if a.kwarg:
            out.add(a.kwarg.arg)
    for n in ast.walk(fn):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                for nn in ast.walk(t):
                    if isinstance(nn, ast.Name):
                        out.add(nn.id)
        elif isinstance(n, (ast.AnnAssign, ast.AugAssign)):
            if isinstance(n.target, ast.Name):
                out.add(n.target.id)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for al in n.names:
                out.add((al.asname or al.name).split(".")[0])
        elif isinstance(n, (ast.For, ast.AsyncFor, ast.comprehension)):
            tgt = getattr(n, "target", None)
            for nn in ast.walk(tgt) if tgt is not None else ():
                if isinstance(nn, ast.Name):
                    out.add(nn.id)
        elif isinstance(n, ast.withitem) and n.optional_vars is not None:
            for nn in ast.walk(n.optional_vars):
                if isinstance(nn, ast.Name):
                    out.add(nn.id)
    return out


def in_source(text, symbol):
    """[(lineno, kind)] for every real use of `symbol` in one module's source.

    `kind` is "call", "attribute" or "def". A name inside a string, a comment or a docstring is
    none of those, and a call inside a function that binds the same name is not this symbol.
    """
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return None                      # unparseable is not the same as "no references"
    shadowed = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            if symbol in _bound_locally(n):
                for inner in ast.walk(n):
                    shadowed.add(id(inner))
    out = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == symbol:
            out.append((n.lineno, "def"))
        elif isinstance(n, ast.Call) and id(n) not in shadowed:
            f = n.func
            if isinstance(f, ast.Name) and f.id == symbol:
                out.append((n.lineno, "call"))
            elif isinstance(f, ast.Attribute) and f.attr == symbol:
                out.append((n.lineno, "attribute"))
    return sorted(set(out))


def find(root, symbol, skip=("__pycache__", ".git", "node_modules", ".venv", "site-packages")):
    """[(relpath, lineno, kind)] across the repository, plus the count of files not judged.

    The second number is the honest half: a file that could not be parsed, or was too big, is not
    evidence of absence, and an answer that hides them is the false all-clear this package refuses
    elsewhere.
    """
    found, unjudged = [], 0

    def _unreadable(err):
        # Without this a directory the walk cannot open is simply ABSENT from the result, and the
        # caller counts what it got as what is there -- the false all-clear this module's own
        # `unjudged` count exists to prevent, one level further out.
        nonlocal unjudged
        unjudged += 1

    for base, dirs, names in os.walk(str(root), onerror=_unreadable):
        dirs[:] = [d for d in dirs if d not in skip and not d.startswith(".")]
        for name in names:
            if not name.endswith(".py"):
                continue
            p = os.path.join(base, name)
            try:
                if os.path.getsize(p) > MAX_BYTES:
                    unjudged += 1
                    continue
                with open(p, "r", encoding="utf-8", errors="replace") as fh:
                    hits = in_source(fh.read(), symbol)
            except OSError:
                unjudged += 1
                continue
            if hits is None:
                unjudged += 1
                continue
            rel = os.path.relpath(p, str(root)).replace(os.sep, "/")
            for lineno, kind in hits:
                found.append((rel, lineno, kind))
    return sorted(found), unjudged
