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

  python3 lib/mapper.py <repo> [--out PATH] [--measure]

That is this module's own entry point, and its flags are not the plugin command's:
chamnan-map takes --preview and --install-git-hook, and does not accept --measure.

Never imports or executes the code it reads.
"""
import argparse
import ast
import warnings
import re
import unicodedata
import sys
from pathlib import Path

import assets as assets_mod
import catalogs as catalogs_mod
import deploy as deploy_mod
import impact as impact_mod
import redact
import schema as schema_mod
import tokens

# Directories that are never source: dependency trees, build output, VCS internals, caches.
# Wider than tree.PRUNE_DIRS on purpose — see that constant. This list is mapper's own filter,
# applied after the walk; pruning the walk with it would change what the OTHER scanners see.
SKIP_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "__pycache__", ".venv", "venv", "env",
    "dist", "build", "target", "out", ".next", ".nuxt", "vendor", ".terraform",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "coverage", ".idea", ".vscode",
    "site-packages", ".gradle", ".cache", "tmp", "logs",
}
MAX_FILE_BYTES = 2_000_000

# What the last scan left out and why. Populated by indexable(), read by the caller that
# reports coverage, so a skipped file is a number someone can see rather than an absence.
SKIPPED_TOO_LARGE = []
SKIPPED_BINARY = []

def _nested_repo_dirs(root):
    """Directories under `root` that are repositories in their own right.

    A checkout inside a checkout is somebody else's code. It is not this repository's source, its
    files should not appear in this repository's index, and its size should not be reported as this
    repository's size.

    Found by running chamnan on the repository it was written in: five sibling projects were checked
    out under Work-Mode/, and all 1,086 of their files were being indexed as the host's own -- a
    Kubernetes manifest from a test corpus sitting in the architecture map of a Streamlit app. Every
    one of them was already listed in .gitignore, which chamnan deliberately does not read (it is
    often absent, often wrong, and never covers a nested checkout's own build output). Presence of
    `.git` is the signal that does not depend on anyone having written a rule.

    The scan root itself is never excluded, or scanning a repository would find nothing at all.
    """
    found = set()
    # tree records .git while walking, before pruning it — one pass answers both questions.
    import tree
    try:
        entries = tree.git_dirs(root)
    except OSError:
        return found
    for git in entries:
        owner = git.parent
        if owner.resolve() == root.resolve():
            continue
        if any(part in SKIP_DIRS for part in owner.relative_to(root).parts):
            continue
        found.add(owner.resolve())
    return found


# Filled by extract_python: (path, count, first message). Reported as a total by bin/chamnan-map.
PARSE_WARNINGS = []


# Runs of =, -, * or # used as a visual rule inside a comment. They carry no meaning and eat the
# character budget: a C file's summary came through as "======= Low level networking stuff =======".
DECORATION = re.compile(r"(?:[=*#_~-]\s*){4,}")


# Doc-tool markers that carry no information once the summary is in the index. `@file of_crc.h`
# restates the filename the row already shows, and `@brief` is punctuation for a parser, not words
# for a reader -- yet on a firmware tree in doxygen house style those two ate the front of 69 rows
# out of 430. `@param` and friends are dropped with whatever follows them because the index has a
# one-line budget and an argument list is not the file's job. `@ref X` keeps X, which is a real
# cross-reference to another file.
DOC_TAG_HEAD = re.compile(r"^\s*[\\@]file\s+\S+\s*", re.I)
DOC_TAG_MARKER = re.compile(r"[\\@](?:brief|short|summary|ref|see|link|endlink)\b\s*", re.I)
DOC_TAG_TAIL = re.compile(
    r"[\\@](?:param(?:\[[^\]]*\])?|returns?|retval|throws?|exception|author|date|version|since|"
    r"copyright|note|warning|deprecated|todo|inheritdoc|tparam)\b.*$", re.I | re.S)


# C# and VB document with XML rather than @tags, and `<summary>` was reaching the index on 46 of
# 530 rows. Only known tag NAMES are matched: stripping anything between angle brackets would eat
# List<String> and Map<K, V> out of perfectly good prose.
XML_DOC_TAIL = re.compile(
    r"</?(?:param|typeparam|returns|exception|value|example|seealso|permission)\b[^>]*>.*$",
    re.I | re.S)
XML_DOC_WRAP = re.compile(
    r"</?(?:summary|remarks|para|c|code|list|item|term|description|inheritdoc|b|i)\b[^>]*>", re.I)
# <see cref="Thing"/> and <paramref name="thing"/> carry a real reference; keep it, drop the tag.
XML_DOC_REF = re.compile(r"<(?:see|seealso|paramref|typeparamref)\b[^>]*?"
                         r"(?:cref|name)\s*=\s*[\"']([^\"']+)[\"'][^>]*/?>", re.I)
# javadoc's inline markup: {@code fleet.drivers} means the words, not the braces.
JAVADOC_INLINE = re.compile(r"\{@(?:code|link|linkplain|literal|value)\s+([^}]*)\}")


def _strip_doc_tags(text):
    text = DOC_TAG_HEAD.sub("", text)
    text = XML_DOC_TAIL.sub("", text)
    text = DOC_TAG_TAIL.sub("", text)
    text = XML_DOC_REF.sub(r"\1", text)
    text = XML_DOC_WRAP.sub("", text)
    text = JAVADOC_INLINE.sub(r"\1", text)
    return DOC_TAG_MARKER.sub("", text)


# How far back _clip will reach to avoid ending mid-word. Beyond this the hard cut is kept, because
# one very long token should not be allowed to eat a fifth of the description to save itself.
CLIP_BACKOFF = 18

# Code points that are never the end of a well-formed cluster: a cut landing after any of them has
# taken half a character. Slicing by character count is not slicing by what a reader sees --
# "👍🏽"[:1] is a thumbs-up with the skin tone silently removed, and "🇯🇵"[:1] is a lone regional
# indicator that most terminals draw as a boxed letter rather than a flag. The word-boundary
# back-off does not help: from Python's side each half is already a valid, ordinary string.
_ZWJ = "\u200d"
_VARIATION = range(0xFE00, 0xFE10)
_SKIN_TONE = range(0x1F3FB, 0x1F400)
_REGIONAL = range(0x1F1E6, 0x1F200)


def _whole_graphemes(text):
    """`text` with any trailing fragment of an incomplete cluster removed."""
    while text:
        c = text[-1]
        o = ord(c)
        if (unicodedata.combining(c) or c == _ZWJ
                or o in _VARIATION or o in _SKIN_TONE):
            text = text[:-1]
            continue
        # A regional indicator is only a flag in a pair; an odd one left at the end is half of one.
        if o in _REGIONAL:
            run = 0
            while run < len(text) and ord(text[-1 - run]) in _REGIONAL:
                run += 1
            if run % 2:
                text = text[:-1]
                continue
        break
    return text


def _clip(text, limit=110):
    """The description, cut to `limit`, ending on a word rather than inside one.

    A plain character slice was cutting 83% of this repository's truncated entries mid-word --
    `_CASCADE_MIN_ROUND_S…`, `tools/preflig…`, `call_ollama_chat's q…`. That is the worst place to
    cut: identifiers are what sessions actually search for (measured here: 51.1% of the identifiers
    this repository's sessions searched for are answerable from MAP.md), and half an identifier
    matches nothing. Backing up to the last space costs a handful of bytes and keeps the token whole.

    Bounded, because the fix has its own failure mode: a single long unbroken token near the limit
    would otherwise shrink the description by however long it is. Past CLIP_BACKOFF the hard cut
    stands and the token is broken -- worse, but bounded.
    """
    text = DECORATION.sub(" ", text or "")
    text = _strip_doc_tags(text)
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    head = text[: limit - 1]
    space = head.rfind(" ")
    if space >= len(head) - CLIP_BACKOFF and space > 0:
        head = head[:space]
    return _whole_graphemes(head).rstrip(" ,;:-") + "…"


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
# The dash, colon or pipe that joined a restated filename to the sentence after it. Only ever
# applied immediately after that filename was removed, so a summary that legitimately opens
# with a dash is untouched.
SELF_NAME_SEPARATOR = re.compile(r"^\s*[—–\-:|]+\s*")
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
# Pragmas and editor directives that open a file above its real description. Removed from the
# front of the comment before the boilerplate test rather than treated as boilerplate themselves.
MAGIC_COMMENT = re.compile(
    r"^(?:frozen_string_literal\s*:\s*\w+|encoding\s*[:=]\s*[\w-]+|-\*-.*?-\*-|"
    r"coding[:=]\s*[\w.-]+|warn_indent\s*:\s*\w+|shareable_constant_value\s*:\s*\w+|"
    r"@ts-\w+|eslint-disable[\w-]*|prettier-ignore|noqa(?::\s*[\w,]+)?|"
    r"type\s*:\s*ignore|rubocop:\w+\s+[\w/,\s]+)[\s.,;:-]*""", re.I)
BOILERPLATE = re.compile(
    r"(?:copyright|\(c\)|©|licen[cs]ed?\b|all rights reserved|spdx|permission is hereby|"
    r"this (?:file|program|software|source) (?:is|may)\s+(?:free|provided|distributed|licensed|be)|redistribution|frozen_string_literal|"
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
            # 🐛 [2026-08-28] ...and the separator it left behind. `# cve.sh — ตรวจ CVE ชุดนี้`
            # became `— ตรวจ CVE ชุดนี้`, which the index then rendered as `path (137L, 2fn) — —
            # ตรวจ…`: two dashes and no words between them. Found by rebuilding a real repository's
            # map and reading the diff rather than the tests. The name is dropped because the row
            # already shows it; the punctuation that joined it to the sentence has nothing left to
            # join and must go with it.
            text = SELF_NAME_SEPARATOR.sub("", text, count=1)
        # A pragma is not a licence and it is not a description either -- it is a switch that
        # happens to be spelled as a comment, and it sits on the FIRST line, above the real one.
        # `# frozen_string_literal: true` opens virtually every modern Ruby file, and matching it
        # as boilerplate threw away the whole comment block behind it: 26 of 28 Ruby files in a
        # polyglot corpus lost the summary that was sitting two lines further down.
        text = MAGIC_COMMENT.sub("", text, count=1).strip()
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
        ("func", r"^(?:export\s+)?(?:async\s+)?function\s*\*?\s+(\w+)\s*\(([^)]*)\)"),
        ("func", r"^(?:export\s+)?(?:const|let)\s+(\w+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*(?::[^=]*?)?=>"),
        ("func", r"^\s{2,}(?:public\s+|private\s+|protected\s+|static\s+|readonly\s+)*"
                 r"(?:async\s+)?(?!if|for|while|switch|catch|return|constructor\b)"
                 r"(\w+)\s*\(([^)]*)\)\s*(?::\s*[\w<>\[\], |]+\s*)?\{"),
        ("class", r"^(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+(\w+)"),
        ("const", r"^(?:export\s+)?const\s+([A-Z][A-Z0-9_]{2,})\s*="),
    ],
    "go": [
        ("func", r"^func\s+(?:\([^)]*\)\s*)?(\w+)\s*\(([^)]*)\)"),
        ("class", r"^type\s+(\w+)\s+struct"),
        ("const", r"^(?:const|var)\s+([A-Z][A-Za-z0-9_]{2,})\s*="),
    ],
    "sh": [("func", r"^(?:function\s+)?(\w+)\s*\(\)\s*\{")],
    "rb": [("func", r"^\s*def\s+(?:self\.)?(\w+)"), ("class", r"^\s*class\s+(\w+)")],
    "rs": [("func", r"^\s*(?:pub(?:\([\w:]+\))?\s+)?(?:default\s+)?(?:const\s+)?"
                    r"(?:async\s+)?(?:unsafe\s+)?"
                    r"fn\s+(\w+)\s*(?:<[^>]*>)?\s*\(([^)]*)\)"),
           ("class", r"^\s*(?:pub(?:\([\w:]+\))?\s+)?(?:struct|enum|trait|union)\s+(\w+)")],
    "java": [("func", r"^\s*(?:public|private|protected).*?\s(\w+)\s*\(([^)]*)\)\s*\{"),
             ("class", r"^\s*(?:public\s+)?(?:class|interface|enum)\s+(\w+)")],
    # Kotlin borrowed Java's rules and it cost almost everything: a visibility modifier is
    # OPTIONAL in Kotlin (public is the default and `fun` usually carries none), so 31 files
    # yielded 34 symbols where 34 Java files yielded 218 -- and what it did find included
    # `HttpClient(engine)`, a constructor call rather than a declaration. `fun` is the anchor.
    "kotlin": [
        ("func", r"^\s*(?:(?:public|private|protected|internal|override|open|abstract|final|"
                 r"inline|suspend|operator|infix|tailrec|external|expect|actual)\s+)*"
                 r"fun\s+(?:<[^>]*>\s*)?(?:[\w.]+\.)?(\w+)\s*\(([^)]*)\)"),
        ("class", r"^\s*(?:(?:public|private|internal|open|abstract|sealed|data|value|inner|"
                  r"annotation|enum|expect|actual)\s+)*(?:class|object|interface)\s+(\w+)"),
        ("const", r"^\s*(?:(?:private|internal|const)\s+)*val\s+([A-Z][A-Z0-9_]{2,})\s*[:=]"),
    ],
    "tf": [("class", r'^resource\s+"([^"]+)"\s+"([^"]+)"'),
           ("func", r'^(?:module|data)\s+"([^"]+)"')],
    # A method is the normal shape in PHP, and the bare `function` rule caught none of them:
    # measured on a 22-file service, 66 of 139 declarations carried a visibility modifier and were
    # invisible, along with every `final class`.
    "php": [
        ("func", r"^\s*(?:(?:public|private|protected|static|final|abstract)\s+)*"
                 r"function\s+&?(\w+)\s*\(([^)]*)\)"),
        ("class", r"^\s*(?:(?:final|abstract|readonly)\s+)*(?:class|interface|trait|enum)\s+(\w+)"),
    ],
    # C and C++ have no dependable line-anchored declaration form: a definition may return a
    # pointer, span several lines, or sit behind a macro. These catch the common shapes and miss
    # the exotic ones, which is the accepted trade for an index — a miss costs one grep.
    "c": [
        ("func", r"^[A-Za-z_][\w \t\*&:<>,]*?\b(\w+)\s*\(([^;)]*)\)\s*(?:const\s*)?\{"),
        # A header holds prototypes, which end in ";" and never in "{". Matching only definitions
        # meant 11 header files in a firmware tree contributed 2 symbols between them, while the
        # whole point of a header is to declare what the module offers.
        ("func", r"^(?!\s*(?:typedef|return|else|extern\s+\"C\")\b)"
                 r"[A-Za-z_][\w \t\*&]*?\b(\w+)\s*\(([^;{)]*)\)\s*;"),
        ("class", r"^\s*(?:typedef\s+)?(?:struct|class|union|enum)\s+(\w+)"),
        ("const", r"^\s*#define\s+([A-Z][A-Z0-9_]{2,})"),
    ],
    "cs": [
        ("func", r"^\s*(?:(?:public|private|protected|internal|static|async|override|virtual)\s+)+(?!record\s|class\s|struct\s|interface\s)[\w<>\[\],\.]+\s+(\w+)\s*\(([^)]*)\)"),
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
    ".rb": "rb", ".rs": "rs", ".java": "java", ".kt": "kotlin", ".kts": "kotlin",
    ".tf": "tf", ".php": "php",
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
# Control flow reads exactly like a call, and the per-language rules cannot tell them apart: Dart's
# `for (var i = 0; i < 16; i++) {` fits "name(args) {" perfectly, and Kotlin's `= when(status) {`
# backtracks into the Java rule. 57 of 3,013 extracted symbols were statements like these, listed
# in the index as functions of the file. One shared deny-list is cheaper and safer than tightening
# a dozen regexes, and nothing here is ever a real function name in any language chamnan indexes.
NOT_A_FUNCTION = {
    "if", "else", "elif", "for", "foreach", "while", "do", "switch", "when", "case", "match",
    "try", "catch", "except", "finally", "with", "using", "guard", "defer", "return", "yield",
    "throw", "throws", "await", "async", "lock", "synchronized", "unless", "until", "loop",
    "select", "go", "spawn", "assert", "sizeof", "typeof", "instanceof", "new", "delete",
    "print", "printf", "in", "is", "as", "and", "or", "not",
}


# Languages whose function pattern requires a definition keyword -- `fn`, `def`, `func`, `sub`.
# In these, a rule can only ever match a DEFINITION, so the deny-list has nothing to protect against
# and does active harm: it was dropping Rust's `fn new()`, which is the language's standard
# constructor and plausibly the most common function name in any real Rust codebase, because "new"
# is on a list written to filter JavaScript's `new Foo()` object-instantiation expressions.
KEYWORD_DEFINED = {"rs", "rb", "py", "go", "ex", "nim", "php", "swift", "kotlin", "zig", "lua"}


def extract_regex(source, lang):
    funcs, classes, consts = [], [], []
    rules = REGEX_RULES.get(lang, [])
    for kind, pattern in rules:
        for m in re.finditer(pattern, source, re.M):
            groups = [g for g in m.groups() if g is not None]
            name = groups[0]
            if kind == "func":
                if name.lower() in NOT_A_FUNCTION and lang not in KEYWORD_DEFINED:
                    continue
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
    """One session, so the nested-repo probe and the file walk share a single traversal."""
    import tree
    with tree.session():
        return _scan(root)


def indexable(root, nested=None):
    """Yield (path, lang) for exactly the files that belong in this repository's index.

    Factored out of _scan because a second caller needed the same answer and got it wrong. The
    session-start staleness check walked the tree with only the extension filter, so it counted a
    nested checkout's files as this repository's own — and reported the index as stale every time
    chamnan's own source was edited, about 28 files the index was never going to contain. On the
    repository chamnan is developed in that warning was permanently on, which is the same as absent.

    One definition, two callers. A filter this specific will drift the moment it is written twice.
    Must be called inside a tree.session().
    """
    import tree
    if nested is None:
        nested = _nested_repo_dirs(root)
    for path in tree.files(root):
        if not path.is_file():
            continue
        if nested and any(parent.resolve() in nested for parent in path.parents):
            continue          # a checkout inside this checkout is not this repository's source
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
                # Recorded, not merely skipped. A 2.2MB generated file used to disappear from the
                # index while the run reported "1 source file(s)" and 100% coverage of what it saw
                # — false confidence rather than degraded confidence, which is the worse kind.
                SKIPPED_TOO_LARGE.append((path, path.stat().st_size))
                continue
        except OSError:
            continue
        # Binary content under a source extension. A PNG saved as asset.py was read with
        # errors="replace" and indexed as code: 351 "lines" counted from newline bytes inside the
        # image, marked describable, and flagged forever as missing a comment it can never have.
        # A NUL in the first block is the cheap, reliable signal, and no text source contains one.
        try:
            with path.open("rb") as fh:
                if b"\x00" in fh.read(8192):
                    SKIPPED_BINARY.append(path)
                    continue
        except OSError:
            continue
        yield path, lang


def _scan(root):
    SKIPPED_TOO_LARGE.clear()
    SKIPPED_BINARY.clear()
    files = []
    nested = _nested_repo_dirs(root)
    for path, lang in indexable(root, nested):
        try:
            source = path.read_text(encoding="utf-8-sig", errors="replace")
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
            # Forward slashes always, on every platform. str(Path) renders with os.sep, so on Windows
            # this field came out `lib\\mapper` while impact.py normalises its own lookup key to
            # `lib/mapper` -- the two can never be equal, so every relative import resolved to
            # nothing, silently. The same literal `/` is assumed by impact.is_test() and by
            # rollup's path.split("/")[0] grouping, so one normalisation here fixes three things.
            "path": path.relative_to(root).as_posix(), "lang": lang, "chars": len(source),
            "tokens": tokens.estimate(source),
            # Collected while the source is open rather than in a second pass: lib/impact.py then
            # only has to resolve and invert, which is arithmetic on what is already in memory.
            "imports": impact_mod.extract_imports(source, lang),
            # splitlines(), not count("\n") + 1. Nearly every source file ends with a newline, and
            # the arithmetic version counts the empty string after it as a line -- so every entry in
            # the index over-reported by exactly one -- 276 of 277 entries.
            #
            # The check that confirmed it is narrower than it looks, which is worth writing down
            # rather than leaving as an implied guarantee: splitlines() breaks on eleven boundaries,
            # not one, while wc -l counts only newline. They agreed on all 276 files because none of
            # those files contains a form feed, a lone carriage return or a Unicode line separator --
            # not because the two are equivalent. One stray form feed makes them disagree again,
            # silently, and in chamnan's favour: splitlines is the better count of what a reader
            # sees.
            "lines": len(source.splitlines()), "doc": doc,
            "funcs": funcs, "classes": classes, "consts": consts,
        })
    return files


def render(files, root):
    """One session for the whole render — every scanner below shares one walk."""
    import tree
    with tree.session():
        return _render(files, root)


def _render(files, root):
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
    deployed = deploy_mod.scan(root)
    stored = assets_mod.scan(root,
                             {f["path"] for f in files} | deployed.get("claimed", set()),
                             EXT_LANG)
    for section_text in (schema_mod.render(tables),
                         catalogs_mod.render_routes(routes),
                         catalogs_mod.render_env(env_pairs, env_unsafe),
                         deploy_mod.render(deployed),
                         assets_mod.render(stored)):
        if section_text:
            lines += ["", "---", "", section_text]

    lines += ["", "---", "", "## Full Detail", ""]

    # Below the marker, deliberately. Everything above it is injected into every session, and a
    # per-file relationship listing in front of a session that was never going to touch those
    # files is exactly the cost this plugin exists to remove. It is read at the moment of changing
    # one path, by grepping for that path.
    impact_section = impact_mod.render(impact_mod.build(files))
    if impact_section:
        lines += [impact_section, ""]

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
