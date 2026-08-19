"""Portable architecture map — the language-agnostic version of claude_system/tools/map_architecture.py.

The original works and is measured (context read per API call fell 22.6% on this machine after
claude_system landed, holding the model constant), but it is welded to this repo: it parses Python
with `ast`, globs `src/*.py`, and special-cases one filename. None of that transfers.

This one takes the same idea to any repository. The trade it makes is deliberate: per-language AST
parsing does not scale past one or two languages, so everything except Python is read with regex.
That is approximate on purpose. A map is a NAVIGATION INDEX, not a compiler front-end — it has to
answer "which file do I open for X" in a few hundred tokens. Missing an edge-case declaration costs
one grep; being unmaintainable across six languages costs the whole tool.

Output has the same two-part shape as the original, and the shape is the point:

  QUICK INDEX  — one line per file. Small enough to read in full, every session.
  FULL DETAIL  — per-file symbols. Never read whole; grepped for the one heading you need.

On this repo the index is 10% of the file, so the habit "read the index, grep the detail" is what
actually saves the context, not the file existing.

  python3 map_project.py <repo> [--out PATH] [--measure]

Never imports or executes the code it reads.
"""
import argparse
import ast
import warnings
import re
import sys
from pathlib import Path

import assets as assets_mod
import catalogs as catalogs_mod
import deploy as deploy_mod
import redact
import schema as schema_mod
import tokens

# Directories that are never source: dependency trees, build output, VCS internals, caches.
SKIP_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "__pycache__", ".venv", "venv", "env",
    "dist", "build", "target", "out", ".next", ".nuxt", "vendor", ".terraform",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "coverage", ".idea", ".vscode",
    "site-packages", ".gradle", ".cache", "tmp", "logs",
}
MAX_FILE_BYTES = 2_000_000

# Filled by extract_python: (path, count, first message). Reported as a total by bin/chamnan-map.
PARSE_WARNINGS = []


# Runs of =, -, * or # used as a visual rule inside a comment. They carry no meaning and eat the
# character budget: a C file's summary came through as "======= Low level networking stuff =======".
DECORATION = re.compile(r"(?:[=*#_~-]\s*){4,}")


def _clip(text, limit=110):
    text = DECORATION.sub(" ", text or "")
    text = " ".join(text.split())
    return text[: limit - 1] + "…" if len(text) > limit else text


COMMENT_PREFIX = re.compile(r"^\s*(?:/\*+!?|\*+/?|//+!?|#+|--+|<!--|;;+)\s?")
# In the C family a leading # is a preprocessor directive, not a comment. Reading it as one gave a
# C file the summary "define _POSIX_C_SOURCE 200112L include <sys/types.h>", which is both wrong
# and the opposite of useful — it describes the compiler's needs, not the file's job.
COMMENT_PREFIX_NO_HASH = re.compile(r"^\s*(?:/\*+!?|\*+/?|//+!?|--+|<!--)\s?")
HASH_IS_DIRECTIVE = {"c", "cs", "swift"}
# A header that opens by restating the filename, then the licence — the house style of most Swift
# and Objective-C projects. Without stripping it the boilerplate check never fires, because the
# text starts with "AppDelegate.swift" rather than "Copyright".
FILENAME_LINE = re.compile(r"^[\w.-]+\.[a-z]{1,5}\s*$", re.I)
# Lines that open a file without saying anything about it — including the import block, which on a
# Java or TypeScript file sits between the licence header and the class doc. Leaving imports out
# meant the reader stopped there: 250 of 268 gson files and 401 of 455 type-fest files came back
# with no summary while a perfectly good one sat a few lines below. Skipping them is what makes a summary
# say what the file is FOR: harvesting them gave every shell script the summary "!/bin/bash", and
# gave PHP nothing at all — a PHP file opens with <?php, which is not a comment, so the reader
# stopped on line one and 132 of 132 guzzle files came back blank.
SKIP_OPENERS = re.compile(
    r"^\s*(?:#!|<\?php\b|<\?=|declare\s*\(|namespace\s|use\s|package\s|@file:|"
    r"import\s|from\s+[\'\"\w.]+\s+import\b|require[\s(]|require_relative\s|using\s\w|"
    r"extern\s+crate|part\s+of\s|library\s\w|@?import\b|open\s+\w+\s*$|"
    r"//\s*SPDX|/\*\s*SPDX|syntax\s*=|option\s+\w+|#\s*(?:include|import|pragma|ifndef|if\s|endif))",
    re.I)
# Only the /* ... */ family. Python never reaches leading_comment with a docstring — ast handles
# those — so a triple-quote branch here would be dead code carrying its own escaping hazards.
BLOCK_OPEN = re.compile(r"^\s*/\*+!?")
BLOCK_CLOSE = "*/"
# Text that occupies the summary slot without describing the file. Licence headers are the worst
# offender by far: measured on real repositories, 95 okhttp files, 76 gson files and 77 sinatra
# files all carried the SAME summary — the project's licence boilerplate or Ruby's magic comment.
# That is worse than an empty summary, because it counts as described, inflates the coverage
# figure, and spends tokens in every session to say nothing. When the first comment is one of
# these, the reader steps over it and looks for the next.
BOILERPLATE = re.compile(
    r"(?:copyright|\(c\)|©|licen[cs]ed?\b|all rights reserved|spdx|permission is hereby|"
    r"this (?:file|program|software|source) (?:is|may)|redistribution|frozen_string_literal|"
    r"encoding\s*[:=]|-\*-|warn_indent|jazzy\b|generated by|do not edit|@generated|"
    r"autogenerated|code generated by|the software is provided|without warranty|"
    r"in no event shall|merchantability)", re.I)
# Elixir puts the file's summary in @moduledoc, which is a module attribute holding a heredoc, not
# a comment — so a comment reader finds nothing. Phoenix scored 16 of 206 until this was handled.
MODULEDOC = re.compile(r'^\s*@(?:module)?doc\s+"""\s*$', re.M)


def leading_comment(source, lang=None):
    """The file's opening comment, used as its one-line summary.

    Two things this has to get right, both found by running against real repositories rather than
    fixtures:

    Block comments are read as blocks. Requiring every line to carry a marker holds for // and #
    and fails for /* ... */, where the inner lines usually carry nothing — a Rust file opening with
    `/*!` produced the summary "!" and a C file produced none.

    A licence header is not a description. Stepping over boilerplate matters more than it sounds:
    without it, 95 okhttp files shared one summary and 77 sinatra files shared another, so the
    coverage figure read 97% while the index said nothing about almost any of them.
    """
    prefix = COMMENT_PREFIX_NO_HASH if lang in HASH_IS_DIRECTIVE else COMMENT_PREFIX
    lines = source.splitlines()
    doc = _elixir_moduledoc(lines)
    if doc:
        return doc

    i = 0
    for _ in range(6):          # at most six boilerplate blocks before giving up on the file
        while i < len(lines) and (not lines[i].strip() or SKIP_OPENERS.match(lines[i])
                              or (lang in HASH_IS_DIRECTIVE and lines[i].lstrip().startswith('#'))):
            i += 1
        if i >= len(lines):
            return ""
        text, i = _one_comment(lines, i, prefix)
        if not text:
            return ""
        parts = [x for x in text.split("  ") if x.strip()]
        text = " ".join(parts).strip()
        # Strip an opening "SomeFile.swift" line before judging: a header that names the file and
        # then states the licence would otherwise pass the boilerplate check on the filename alone.
        first_word = text.split(" ", 1)[0] if text else ""
        if FILENAME_LINE.match(first_word):
            text = text[len(first_word):].strip()
        # Searched over the opening of the text rather than anchored at its start: a Swift or
        # Objective-C header opens with the file name and the project name before it ever reaches
        # "Copyright", so an anchored match never fired and every file in the project shared the
        # licence as its summary.
        if text and not BOILERPLATE.search(text[:90]):
            return _clip(text)
    return ""


def _elixir_moduledoc(lines):
    """Elixir's @moduledoc heredoc — the language's equivalent of a module docstring."""
    for n, line in enumerate(lines[:40]):
        if MODULEDOC.match(line):
            body = []
            for follow in lines[n + 1: n + 12]:
                if follow.strip().startswith('"""'):
                    break
                body.append(follow.strip())
                if len(" ".join(body)) > 200:
                    break
            return _clip(" ".join(x for x in body if x))
    return ""


def _one_comment(lines, i, prefix=COMMENT_PREFIX):
    """Reads one comment starting at line i. Returns (text, index of the line after it)."""
    out = []
    opener = BLOCK_OPEN.match(lines[i])
    if opener:
        first = lines[i][opener.end():]
        if BLOCK_CLOSE in first:
            return prefix.sub("", first.split(BLOCK_CLOSE)[0]).strip(), i + 1
        out.append(first)
        j = i + 1
        while j < len(lines) and j < i + 40:
            if BLOCK_CLOSE in lines[j]:
                out.append(lines[j].split(BLOCK_CLOSE)[0])
                j += 1
                break
            out.append(prefix.sub("", lines[j]))
            j += 1
        return " ".join(x.strip() for x in out if x.strip()), j

    j = i
    while j < len(lines) and j < i + 14 and prefix.match(lines[j]):
        text = prefix.sub("", lines[j]).strip()
        if text:
            out.append(text)
        j += 1
    return " ".join(out), j


def extract_python(source, path, lang='py'):
    """Parses one file. Warnings raised BY THE FILE are captured, not printed.

    An indexing tool that echoes the parse warnings of the code it reads looks broken — the output
    is chamnan's, the warning is somebody else's file, and the reader has no way to tell. They are
    counted and reported as a total instead, which is the useful half: a real invalid escape
    sequence in a 3,000-line file had gone unnoticed here because py_compile stays silent about it,
    and it becomes a hard SyntaxError in a future Python.
    """
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            tree = ast.parse(source, filename=str(path))
        if caught:
            PARSE_WARNINGS.append((str(path), len(caught), str(caught[0].message)))
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        # SyntaxError is the expected one. ValueError is a file with a .py extension whose contents
        # are not text at all — a null byte makes ast.parse raise it, and catching only SyntaxError
        # meant one vendored binary blob aborted the scan of an entire repository with a traceback.
        # RecursionError is deeply nested literals. None of these should cost more than one file.
        return None, [], []
    doc = _clip(ast.get_docstring(tree) or "")
    doc = doc.split(". ")[0] if doc else ""
    if not doc:
        # A module docstring is the Python convention, but plenty of real files open with a `#`
        # header instead and mean exactly the same thing. Reading only docstrings scored a file
        # with a perfectly good "# Reads config" header as undescribed, which then drags down the
        # coverage figure the whole design leans on.
        doc = leading_comment(source, lang)
    funcs, classes, consts = [], [], []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = ", ".join(a.arg for a in node.args.args)
            funcs.append((f"{node.name}({args})", _clip(ast.get_docstring(node) or "", 90)))
        elif isinstance(node, ast.ClassDef):
            methods = [n.name for n in node.body
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            classes.append((node.name, _clip(ast.get_docstring(node) or "", 90), methods))
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id.isupper() and len(t.id) > 2:
                    consts.append(t.id)
    return doc, funcs, classes, consts


# --- Everything else: regex. One table, one code path. ----------------------------------------
# Each entry is (kind, pattern). Patterns are anchored at line start so a match is a top-level
# declaration rather than something nested inside a function body.
REGEX_RULES = {
    "js": [
        ("func", r"^(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)"),
        ("func", r"^(?:export\s+)?(?:const|let)\s+(\w+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>"),
        ("class", r"^(?:export\s+)?class\s+(\w+)"),
        ("const", r"^(?:export\s+)?const\s+([A-Z][A-Z0-9_]{2,})\s*="),
    ],
    "go": [
        ("func", r"^func\s+(?:\([^)]*\)\s*)?(\w+)\s*\(([^)]*)\)"),
        ("class", r"^type\s+(\w+)\s+struct"),
        ("const", r"^(?:const|var)\s+([A-Z][A-Za-z0-9_]{2,})\s*="),
    ],
    "sh": [("func", r"^(?:function\s+)?(\w+)\s*\(\)\s*\{")],
    "rb": [("func", r"^\s*def\s+(\w+)"), ("class", r"^\s*class\s+(\w+)")],
    "rs": [("func", r"^(?:pub\s+)?fn\s+(\w+)\s*\(([^)]*)\)"),
           ("class", r"^(?:pub\s+)?(?:struct|enum|trait)\s+(\w+)")],
    "java": [("func", r"^\s*(?:public|private|protected).*?\s(\w+)\s*\(([^)]*)\)\s*\{"),
             ("class", r"^\s*(?:public\s+)?(?:class|interface|enum)\s+(\w+)")],
    "tf": [("class", r'^resource\s+"([^"]+)"\s+"([^"]+)"'),
           ("func", r'^(?:module|data)\s+"([^"]+)"')],
    "php": [("func", r"^\s*function\s+(\w+)\s*\(([^)]*)\)"), ("class", r"^\s*class\s+(\w+)")],
    # C and C++ have no dependable line-anchored declaration form: a definition may return a
    # pointer, span several lines, or sit behind a macro. These catch the common shapes and miss
    # the exotic ones, which is the accepted trade for an index — a miss costs one grep.
    "c": [
        ("func", r"^[A-Za-z_][\w \t\*&:<>,]*?\b(\w+)\s*\(([^;)]*)\)\s*(?:const\s*)?\{"),
        ("class", r"^\s*(?:typedef\s+)?(?:struct|class|union|enum)\s+(\w+)"),
        ("const", r"^\s*#define\s+([A-Z][A-Z0-9_]{2,})"),
    ],
    "cs": [
        ("func", r"^\s*(?:(?:public|private|protected|internal|static|async|override|virtual)\s+)+[\w<>\[\],\.]+\s+(\w+)\s*\(([^)]*)\)"),
        ("class", r"^\s*(?:public\s+|internal\s+)?(?:sealed\s+|abstract\s+|static\s+|partial\s+)*(?:class|struct|interface|record|enum)\s+(\w+)"),
    ],
    "swift": [
        ("func", r"^\s*(?:(?:public|private|internal|open|static|class)\s+)*func\s+(\w+)\s*\(([^)]*)\)"),
        ("class", r"^\s*(?:public\s+)?(?:final\s+)?(?:class|struct|enum|protocol|extension)\s+(\w+)"),
    ],
    "dart": [
        ("func", r"^\s*(?:[\w<>,\?\[\] ]+\s+)?(\w+)\s*\(([^)]*)\)\s*(?:async\s*)?\{"),
        ("class", r"^\s*(?:abstract\s+)?(?:class|mixin|enum|extension)\s+(\w+)"),
    ],
    "lua": [("func", r"^\s*(?:local\s+)?function\s+([\w.:]+)\s*\(([^)]*)\)")],
    "scala": [("func", r"^\s*(?:private\s+|protected\s+)?def\s+(\w+)\s*[\(\[:]"),
              ("class", r"^\s*(?:case\s+)?(?:class|object|trait|enum)\s+(\w+)")],
    "ex": [("func", r"^\s*def(?:p)?\s+(\w+[?!]?)\s*[\(,\s]"),
           ("class", r"^\s*defmodule\s+([\w.]+)")],
    "zig": [("func", r"^\s*(?:pub\s+)?fn\s+(\w+)\s*\(([^)]*)\)"),
            ("const", r"^\s*(?:pub\s+)?const\s+([A-Z][A-Za-z0-9_]{2,})\s*=")],
    "nim": [("func", r"^\s*(?:proc|func|method|iterator)\s+(\w+)\s*[\*]?\s*\(([^)]*)\)"),
            ("class", r"^\s*(\w+)\*?\s*=\s*(?:ref\s+)?object")],
    # An index of what a service exposes. On a repo of handlers the .proto answers "does an endpoint
    # for X exist" in a fraction of the tokens the handlers would cost.
    "proto": [("class", r"^\s*(?:service|message|enum)\s+(\w+)"),
              ("func", r"^\s*rpc\s+(\w+)\s*\(([^)]*)\)")],
    "graphql": [("class", r"^\s*(?:type|input|interface|enum|union)\s+(\w+)")],
}
EXT_LANG = {
    ".py": "py", ".js": "js", ".mjs": "js", ".cjs": "js", ".jsx": "js", ".ts": "js", ".tsx": "js",
    ".go": "go", ".sh": "sh", ".bash": "sh", ".command": "sh", ".zsh": "sh",
    ".rb": "rb", ".rs": "rs", ".java": "java", ".kt": "java", ".tf": "tf", ".php": "php",
    # The C family was missing entirely until a run against real repositories: a C project reported
    # zero files and a C++ one six of 142. Headers are indexed too — in C and C++ the header is
    # usually where the interface a reader came looking for actually lives. .ino is Arduino, which
    # is C++ with a different extension.
    ".c": "c", ".h": "c", ".cpp": "c", ".cc": "c", ".cxx": "c", ".hpp": "c", ".hh": "c",
    ".hxx": "c", ".m": "c", ".mm": "c", ".ino": "c", ".pde": "c",
    ".cs": "cs", ".swift": "swift", ".dart": "dart", ".lua": "lua",
    ".scala": "scala", ".ex": "ex", ".exs": "ex", ".zig": "zig", ".nim": "nim",
    # Interface definitions rather than code, and that is the point: on a service repo the question
    # "what does this expose" is answered by the .proto or the schema, not by the handlers.
    ".proto": "proto", ".graphql": "graphql", ".gql": "graphql",
}
# Leading comment markers stripped when harvesting a file's opening comment as its summary.
def extract_regex(source, lang):
    funcs, classes, consts = [], [], []
    rules = REGEX_RULES.get(lang, [])
    for kind, pattern in rules:
        for m in re.finditer(pattern, source, re.M):
            groups = [g for g in m.groups() if g is not None]
            name = groups[0]
            if kind == "func":
                args = groups[1] if len(groups) > 1 else ""
                sig = f"{name}({_clip(args, 46)})"
                if sig not in [f for f, _ in funcs]:
                    funcs.append((sig, ""))
            elif kind == "class":
                label = ".".join(groups) if lang == "tf" else name
                if label not in [c for c, _, _ in classes]:
                    classes.append((label, "", []))
            elif name not in consts:
                consts.append(name)
    return leading_comment(source, lang), funcs, classes, consts


def _is_empty_module(source, lang):
    """True when the file declares nothing. Python is checked properly; other languages fall back to
    "is there anything that is not blank or a comment", which is all a regex can honestly claim."""
    if lang == "py":
        try:
            return not ast.parse(source).body
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            return False
    for line in source.splitlines():
        s = line.strip()
        if s and not s.startswith(("#", "//", "/*", "*", "--", "<!--")):
            return False
    return True


def _extract_one(source, path, lang):
    """Dispatch to the right extractor. Separated from scan() so the caller can wrap exactly this
    in one try and keep a bad file from taking the run down with it."""
    if lang == "py":
        parsed = extract_python(source, path)
        if parsed[0] is None and not parsed[1]:
            return leading_comment(source, lang), [], [], []
        return parsed
    return extract_regex(source, lang)


def scan(root):
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        # Only the parts BELOW the scan root. Checking path.parts would test the absolute path, so
        # a repository that happens to live under /tmp, ~/build, or any directory named env/out/
        # target would have every one of its files skipped and report "no source files" — silently,
        # since nothing errors. Found 2026-08-19 by running the tool inside /private/tmp.
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if redact.is_blocked(path):
            continue          # private keys, certificates, local databases — never opened at all
        lang = EXT_LANG.get(path.suffix.lower())
        if not lang:
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # One try around everything this file touches, not around each call. Two separate crashes
        # were found the same way — ast.parse raising ValueError on a .py file whose contents were
        # binary — because each new call site had to remember to guard itself. A map missing one
        # line is useful; a traceback is not, and it takes the other 195 files with it.
        try:
            doc, funcs, classes, consts = _extract_one(source, path, lang)
            describable = bool(source.strip()) and not _is_empty_module(source, lang)
        except Exception:
            doc, funcs, classes, consts, describable = "", [], [], [], False
        files.append({
            # A file with no statements at all — an empty __init__.py, a file of only comments —
            # has nothing to describe, so counting it as "missing a summary" both understates the
            # coverage figure and pushes the user to write a sentence about a file with no code in
            # it. It stays in the index (it exists, and the agent should know that) but sits out of
            # the denominator.
            "describable": describable,
            "path": str(path.relative_to(root)), "lang": lang, "chars": len(source),
            "tokens": tokens.estimate(source),
            "lines": source.count("\n") + 1, "doc": doc,
            "funcs": funcs, "classes": classes, "consts": consts,
        })
    return files


def render(files, root):
    total_chars = sum(f["chars"] for f in files)
    lines = [
        f"# Architecture map — {root.name}",
        "",
        f"Generated by chamnan. {len(files)} source file(s), {total_chars:,} characters.",
        "",
        "**Read the Quick Index in full. Do NOT read the Full Detail section end to end** — grep it",
        "for the one heading you need (`## \\`path\\``). That habit is the entire point of this file:",
        "the index is a fraction of the detail, and the detail is a fraction of the source.",
        "",
        "## Quick Index",
        "",
    ]
    for f in files:
        counts = []
        if f["funcs"]:
            counts.append(f"{len(f['funcs'])}fn")
        if f["classes"]:
            counts.append(f"{len(f['classes'])}cls")
        summary = f["doc"] or "—"
        lines.append(f"- **`{f['path']}`** ({f['lines']}L{', ' + '/'.join(counts) if counts else ''}) — {summary}")

    # Optional sections, in one file rather than several: a repo of plain scripts should end up
    # with a code index and nothing else, not a folder of empty catalogues. Each renderer returns
    # "" when the repo has none of that thing, and an empty section is never written.
    #
    # All of these sit ABOVE the Full Detail marker, because that is what the session-start hook
    # injects. Knowing that a table or a route exists is what saves the search; the columns and
    # parameters are grep territory.
    tables = schema_mod.scan(root, files)
    routes = catalogs_mod.scan_routes(root, files)
    env_pairs, env_unsafe = catalogs_mod.scan_env(root, files)
    stored = assets_mod.scan(root, {f["path"] for f in files}, EXT_LANG)
    for section_text in (schema_mod.render(tables),
                         catalogs_mod.render_routes(routes),
                         catalogs_mod.render_env(env_pairs, env_unsafe),
                         deploy_mod.render(deploy_mod.scan(root)),
                         assets_mod.render(stored)):
        if section_text:
            lines += ["", "---", "", section_text]

    lines += ["", "---", "", "## Full Detail", ""]
    detail = schema_mod.render_detail(tables)
    if detail:
        lines += [detail, ""]
    for f in files:
        lines.append(f"## `{f['path']}`")
        if f["doc"]:
            lines.append(f"{f['doc']}")
        lines.append("")
        if f["consts"]:
            lines.append(f"**Constants:** {', '.join(f['consts'][:40])}")
        for name, doc, methods in f["classes"]:
            lines.append(f"- **class {name}**{' — ' + doc if doc else ''}")
            if methods:
                lines.append(f"  - methods: {', '.join(methods[:30])}")
        for sig, doc in f["funcs"]:
            lines.append(f"- `{sig}`{' — ' + doc if doc else ''}")
        lines.append("")
    # One choke point, on the whole document, rather than at each of the dozen places a summary is
    # extracted. Scrubbing per-extractor means every new extractor is a chance to forget; scrubbing
    # the finished text means nothing reaches the file unscanned, including sections added later.
    return redact.scrub("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--out", default=None)
    ap.add_argument("--measure", action="store_true")
    a = ap.parse_args()
    root = Path(a.repo).resolve()
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 1
    files = scan(root)
    if not files:
        print(f"no recognised source files under {root}", file=sys.stderr)
        return 1
    text = render(files, root)
    out = Path(a.out) if a.out else root / "ARCHITECTURE_MAP.md"
    out.write_text(text, encoding="utf-8")

    if a.measure:
        src = sum(f["tokens"] for f in files)
        idx = text.index("## Full Detail")
        langs = {}
        for f in files:
            langs[f["lang"]] = langs.get(f["lang"], 0) + 1
        map_tok = tokens.estimate(text)
        idx_tok = tokens.estimate(text[:idx])
        print(f"{root.name:<22} {len(files):>4} files  {'+'.join(f'{k}:{v}' for k,v in sorted(langs.items(), key=lambda x:-x[1]))}")
        print(f"  whole source     {src:>10,.0f} tokens")
        print(f"  whole map        {map_tok:>10,.0f} tokens   ({map_tok/src*100:>5.1f}% of the source)")
        print(f"  Quick Index      {idx_tok:>10,.0f} tokens   ({idx_tok/src*100:>5.1f}% of the source)")
    else:
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
