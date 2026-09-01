"""What is connected to what — the half of a repository that reading one file does not tell you.

The Quick Index answers "what exists". This answers "what breaks if I change this", which is the
question actually asked before an edit.

Deliberately one-directional in emphasis. A file's own imports are already visible at the top of
that file, so listing them again buys little. What a reader cannot get without searching is the
REVERSE edge — who depends on this — and which tests cover it. So that is what this section leads
with, and it is why the output is a fraction of the size a full dependency listing would be.

Not a dependency graph. There is no database, no transitive closure and no cycle analysis:
one hop, capped, per file. Anything deeper is a question for a real static-analysis tool, and
pretending otherwise would cost the index its size advantage for an answer it cannot be trusted on.

Cost. Imports are collected by mapper.scan() while it already has each file's source in hand, so
there is no second read of the repository. Building the reverse map is one pass over the edges,
not a comparison of every file against every other — linear in edges, not quadratic in files.
Measured on a 2,365-file polyglot corpus, the whole map including this section takes about the same
time it did without it.
"""
import os
import re
from pathlib import Path

# One pattern per language family. Group 1 is the imported thing. These are deliberately loose:
# a missed import costs one line of output, while a wrong one sends a reader to the wrong file.
IMPORT_PATTERNS = {
    "py": [r"^\s*from\s+([\w.]+)\s+import\b", r"^\s*import\s+([\w.]+)"],
    "js": [r"""(?:from|import)\s+['"]([^'"]+)['"]""", r"""require\(\s*['"]([^'"]+)['"]"""],
    "go": [r'^\s*"([\w./-]+)"\s*$', r'^\s*\w+\s+"([\w./-]+)"\s*$'],
    "java": [r"^\s*import\s+(?:static\s+)?([\w.]+)"],
    "kotlin": [r"^\s*import\s+([\w.]+)"],
    "rb": [r"""^\s*require(?:_relative)?\s+['"]([^'"]+)['"]"""],
    "rs": [r"^\s*(?:pub\s+)?use\s+((?:crate|super|self)?[\w:]+)"],
    "php": [r"^\s*use\s+([\w\\]+)", r"""^\s*require(?:_once)?\s+['"]([^'"]+)['"]"""],
    "c": [r'^\s*#include\s+"([^"]+)"'],
    "swift": [r"^\s*import\s+(\w+)"],
    "dart": [r"""^\s*import\s+['"]([^'"]+)['"]"""],
    "ex": [r"^\s*(?:alias|import|use)\s+([\w.]+)"],
    "scala": [r"^\s*import\s+([\w.]+)"],
    "cs": [r"^\s*using\s+(?:static\s+)?([\w.]+)"],
    "lua": [r"""require\s*\(?\s*['"]([^'"]+)['"]"""],
}

# A file is a test if its path says so. Convention rather than content, because every ecosystem
# announces this in the path and none of them agree on how.
TEST_MARKERS = (
    re.compile(r"(^|/)tests?/"), re.compile(r"(^|/)spec/"), re.compile(r"(^|/)__tests__/"),
    re.compile(r"(^|/)test_[^/]+$"), re.compile(r"_test\.[a-z]+$"),
    re.compile(r"\.test\.[a-z]+$"), re.compile(r"\.spec\.[a-z]+$"),
    re.compile(r"Tests?\.[a-z]+$"), re.compile(r"Test\.java$"),
    # .NET puts the tests in a sibling PROJECT, not a subdirectory: MyApp/ beside MyApp.Tests/.
    # Every other marker here looks for a directory literally called test(s) or a filename that
    # announces itself, and both miss that shape entirely.
    re.compile(r"(^|/)[^/]+\.[Tt]ests?/"),
)

# Deliberately NOT matched: Perl's `t/`. A bare single-letter directory is too weak a signal to
# spend a false positive on, and the ecosystems that would benefit are a small share of what this
# indexes. Recorded so the omission reads as a decision rather than an oversight.

MAX_USED_BY = 6      # per file; beyond this the count is more useful than the list
MAX_TESTS = 3
MAX_ENTRIES = 120    # whole section; a repo larger than this is navigated by grep anyway


def extract_imports(source, lang):
    """Imported names as written. Resolution to real files happens later, with the whole file list
    in hand — a name means nothing on its own."""
    patterns = IMPORT_PATTERNS.get(lang)
    if not patterns:
        return []
    found = []
    # Only the head of the file: imports live at the top in every language here, and scanning a
    # 5,000-line file to the end for an import that is not there is time spent for nothing.
    head = "\n".join(source.splitlines()[:200])
    for pattern in patterns:
        for m in re.finditer(pattern, head, re.M):
            name = m.group(1).strip()
            if name and len(name) < 200:
                found.append(name)
    return found


def is_test(path):
    return any(p.search(path) for p in TEST_MARKERS)


def _index(files):
    """Lookups from the file list: by full path, by path without extension, and by stem.

    The stem map keeps only unambiguous names. Two files called `utils.py` cannot be told apart
    from an import that says `utils`, and a navigation aid that sends someone to the wrong one is
    worse than one that stays quiet.
    """
    # 🐛 `by_noext[noext] = p` overwrote, so `src/util.js` and `src/util.ts` collided and the last
    # one in scan order won — an import of `./util` was credited to whichever the directory listing
    # happened to yield second, and the other real file was invisible in the Impact section. The
    # stem map immediately below refuses ambiguity with a count; this one did not, and the two sit
    # four lines apart. `impact.py`'s own comment says "an invented edge is worse than a missing
    # one", and a coin-flip between two real files is an invented one half the time.
    by_noext, noext_count, stem_count, by_stem = {}, {}, {}, {}
    for f in files:
        p = f["path"]
        noext = p.rsplit(".", 1)[0]
        noext_count[noext] = noext_count.get(noext, 0) + 1
        by_noext[noext] = p
        stem = Path(p).stem
        stem_count[stem] = stem_count.get(stem, 0) + 1
        by_stem[stem] = p
    by_noext = {n: p for n, p in by_noext.items() if noext_count[n] == 1}
    unambiguous = {s: p for s, p in by_stem.items() if stem_count[s] == 1}
    return by_noext, unambiguous


def resolve(name, importer, by_noext, by_stem):
    """One import name to a repository path, or None.

    None is the common and correct answer: most imports are standard library or third-party, and
    those are not in this repository. Guessing at them would fill the section with noise.
    """
    if not name:
        return None

    # Relative paths, as JS, C, Ruby and Dart write them.
    if name.startswith((".", "/")) or "/" in name:
        # 🐛 `lstrip("./")` strips a character SET, so `../shared/util` became `shared/util` and
        # resolved DOWNWARD from the importer's own directory: `../shared/util` imported from
        # `src/a/b.js` came back as `src/a/shared/util.js`. Where no coincidence rescued it the
        # edge simply vanished — with `src/shared/util.js` and `vendor/shared/util.js` both
        # present, `build()` returned nothing at all and the map said the file has no users. Both
        # failure directions from one call, in a function whose comment says an invented edge is
        # worse than a missing one.
        base = Path(importer).parent
        if name.startswith(("./", "../")):
            candidates = [Path(os.path.normpath(str(base / name))),
                          Path(os.path.normpath(name.lstrip("./")))]
        else:
            cleaned = name.lstrip("/")
            candidates = [base / cleaned, Path(cleaned)]
        for candidate in candidates:
            key = str(candidate).replace("\\", "/")
            if key in by_noext:
                return by_noext[key]
            hit = _only_suffix_match(key, by_noext)
            if hit:
                return hit

    # Dotted module names, as Python, Java, Kotlin and C# write them.
    dotted = name.replace("::", ".").replace("\\", ".")
    as_path = dotted.replace(".", "/")
    if as_path in by_noext:
        return by_noext[as_path]
    # `from pkg import foo` names the PACKAGE, whose file is pkg/__init__.py -- a key of
    # "pkg/__init__", which neither the exact lookup nor the stem map can reach ("__init__" is not
    # a distinguishing stem). So a consumer importing through a re-exporting __init__.py, which is
    # the ordinary way a Python package is arranged, produced no edge at all: the dependency was
    # real and the impact map said the file had no users.
    if f"{as_path}/__init__" in by_noext:
        return by_noext[f"{as_path}/__init__"]
    hit = _only_suffix_match(as_path, by_noext)
    if hit:
        return hit

    # Last resort: the final segment, and only when exactly one file in the repository has it.
    tail = dotted.rsplit(".", 1)[-1]
    return by_stem.get(tail)


def _unprefix(path_):
    """`path_` without a leading `./`, and without a leading `/`. A leading dot that is not part of
    `./` belongs to the name -- `.github`, `.env.example` -- and stripping it as a character loses
    the file."""
    while path_.startswith("./"):
        path_ = path_[2:]
    return path_.lstrip("/")


def _only_suffix_match(key, by_noext):
    """The one path ending in `key`, or None when several do.

    Guarding the stem lookup alone was not enough: a bare name like `utils` also suffix-matches
    both `a/utils` and `b/utils`, and returning the first is the same guess the stem map refuses
    to make. A navigation aid that sends someone to the wrong file is worse than one that says
    nothing.
    """
    # A single match is not enough on its own. `from reporting.utils import send`, where
    # `reporting` is a third-party package the repository does not contain, suffix-matches
    # `tests/fixtures/reporting/utils.py` -- an unrelated file that happens to share a path tail --
    # and the map then asserted an edge between two files with nothing to do with each other. An
    # invented edge is worse than a missing one, so the match has to be at least two segments deep
    # before it is trusted; a bare one-segment tail is exactly the coincidence this cannot tell
    # apart from a real relative import.
    if "/" not in key:
        return None
    matches = [f for f in by_noext if f.endswith("/" + key) or f == key]
    return by_noext[matches[0]] if len(matches) == 1 else None


def build(files):
    """{path: {"used_by": [...], "tests": [...]}} for files that something else refers to.

    Only files with an incoming edge or a covering test appear. A leaf nobody imports has nothing
    to say here, and saying "used by: nothing" for hundreds of files is how a useful section
    becomes an unreadable one.
    """
    by_noext, by_stem = _index(files)
    used_by, tests = {}, {}

    for f in files:
        importer = f["path"]
        importer_is_test = is_test(importer)
        for name in f.get("imports", []):
            target = resolve(name, importer, by_noext, by_stem)
            if not target or target == importer:
                continue
            if importer_is_test:
                tests.setdefault(target, [])
                if importer not in tests[target]:
                    tests[target].append(importer)
            else:
                used_by.setdefault(target, [])
                if importer not in used_by[target]:
                    used_by[target].append(importer)

    out = {}
    for path in sorted(set(used_by) | set(tests)):
        out[path] = {"used_by": sorted(used_by.get(path, [])),
                     "tests": sorted(tests.get(path, []))}
    return out


def render(impact):
    """The section written into MAP.md, below the Full Detail marker so it is grepped, not injected.

    It belongs below the marker on purpose: knowing that `payment/service.py` is used by four
    things is worth reading at the moment of changing it, and not before. Injecting it would put a
    per-file relationship listing in front of every session that was never going to touch the file.
    """
    if not impact:
        return ""
    ranked = sorted(impact.items(),
                    key=lambda kv: (-len(kv[1]["used_by"]), -len(kv[1]["tests"]), kv[0]))
    lines = [
        "## Impact",
        "",
        f"{len(impact)} file(s) that something else refers to. **Grep this for one path before "
        "changing it** — it answers what else is affected, which reading the file does not.",
        "",
        "One hop only, and imports resolved within this repository — an import of a third-party "
        "package is not listed, because it is not something a change here can break.",
        "",
    ]
    for path, edges in ranked[:MAX_ENTRIES]:
        parts = []
        if edges["used_by"]:
            shown = ", ".join(f"`{u}`" for u in edges["used_by"][:MAX_USED_BY])
            more = (f" _+{len(edges['used_by']) - MAX_USED_BY} more_"
                    if len(edges["used_by"]) > MAX_USED_BY else "")
            parts.append(f"used by {shown}{more}")
        if edges["tests"]:
            shown = ", ".join(f"`{t}`" for t in edges["tests"][:MAX_TESTS])
            more = (f" _+{len(edges['tests']) - MAX_TESTS} more_"
                    if len(edges["tests"]) > MAX_TESTS else "")
            parts.append(f"**tested by** {shown}{more}")
        lines.append(f"- **`{path}`** — " + "; ".join(parts))
    if len(ranked) > MAX_ENTRIES:
        lines.append(f"- _…and {len(ranked) - MAX_ENTRIES} more with incoming references_")
    return "\n".join(lines)


# ---------------------------------------------------------------- reading it back
# `render()` above is the only writer of this section, and the two patterns below are its exact
# inverse. They are a pair: a round-trip test feeds render()'s own output straight back into
# parse_section(), so changing the format breaks that test rather than silently breaking every
# query built on it.
#
# Why parse markdown at all, rather than keep a JSON sidecar: a full rescan of the repository this
# plugin is developed against measured 64 seconds, which is not a thing to do on an interactive
# question, and a second machine-readable artifact would be another file to regenerate, prune and
# keep in sync. "Markdown is the truth" is a standing constraint here, and this honours it — the
# rendered section IS the index, and this reads it.
_ROW = re.compile(r"^- \*\*`([^`]+)`\*\*\s+—\s+(.+)$", re.M)
_QUOTED = re.compile(r"`([^`]+)`")
_MORE = re.compile(r"_\+(\d+) more_")


def parse_section(text):
    """{path: {"used_by", "tests", "used_by_more", "tests_more"}} read back out of MAP.md.

    The two `_more` counts are how many were elided by MAX_USED_BY / MAX_TESTS when the section
    was written. They are reported rather than dropped: a caller that printed six of eleven
    dependents without saying so would be quietly answering a different question than the one
    asked, and "what else breaks" is exactly the question where a silent truncation costs most.
    """
    cut = text.find("## Impact")
    if cut < 0:
        return {}
    out = {}
    for m in _ROW.finditer(text[cut:]):
        path, body = m.group(1), m.group(2)
        used_by, tests = [], []
        used_more = tests_more = 0
        # One row holds at most one of each clause, in this order, so splitting on the tests
        # marker is enough to tell the two apart -- no clause can contain the other's marker.
        head, sep, tail = body.partition("**tested by**")
        if "used by" in head:
            used_by = _QUOTED.findall(head)
            um = _MORE.search(head)
            used_more = int(um.group(1)) if um else 0
        if sep:
            tests = _QUOTED.findall(tail)
            tm = _MORE.search(tail)
            tests_more = int(tm.group(1)) if tm else 0
        out[path] = {"used_by": used_by, "tests": tests,
                     "used_by_more": used_more, "tests_more": tests_more}
    return out


def lookup(text, target):
    """One file's row from a rendered section, matched exactly or as a path suffix.

    Suffix so a question asked as `app.py` from inside `src/` still finds `src/app.py`, and
    deliberately only when EXACTLY one row matches: two files sharing a basename cannot be told
    apart from a bare name, and answering "what breaks if I change this" about the wrong one is
    worse than saying it could not tell. Returns (path, edges) or (None, None).
    """
    parsed = parse_section(text)
    # 🐛 `lstrip("./")` again: `.github/workflows/ci.yml` became `github/workflows/ci.yml`, so this
    # could not find a row it had written itself, and a root dotfile like `.env.example` lost its
    # name entirely. Only a leading `./` is a relative-path marker; a leading `.` is part of the
    # name.
    target = _unprefix(str(target).strip().strip("`"))
    if not target:
        return None, None
    if target in parsed:
        return target, parsed[target]
    matches = [p for p in parsed if p.endswith("/" + target)]
    if len(matches) == 1:
        return matches[0], parsed[matches[0]]
    return None, None
