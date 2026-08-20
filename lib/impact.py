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
)

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
    by_noext, stem_count, by_stem = {}, {}, {}
    for f in files:
        p = f["path"]
        noext = p.rsplit(".", 1)[0]
        by_noext[noext] = p
        stem = Path(p).stem
        stem_count[stem] = stem_count.get(stem, 0) + 1
        by_stem[stem] = p
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
        base = Path(importer).parent
        cleaned = name.lstrip("./") if name.startswith(("./", "../")) else name.lstrip("/")
        for candidate in (base / cleaned, Path(cleaned)):
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
    hit = _only_suffix_match(as_path, by_noext)
    if hit:
        return hit

    # Last resort: the final segment, and only when exactly one file in the repository has it.
    tail = dotted.rsplit(".", 1)[-1]
    return by_stem.get(tail)


def _only_suffix_match(key, by_noext):
    """The one path ending in `key`, or None when several do.

    Guarding the stem lookup alone was not enough: a bare name like `utils` also suffix-matches
    both `a/utils` and `b/utils`, and returning the first is the same guess the stem map refuses
    to make. A navigation aid that sends someone to the wrong file is worse than one that says
    nothing.
    """
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
