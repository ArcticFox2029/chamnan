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

That is this module's own entry point, and its flags are not the plugin command's: chamnan-map
takes --preview, --explain and --install-git-hook. It also accepts --measure without erroring, but
that is only so the name is not rejected as unknown — it is not wired to this module's --measure
output above, and running it prints the same thing plain `chamnan-map` does.

Never imports or executes the code it reads.
"""
import argparse
import ast
import fnmatch
import subprocess
import warnings
import re
import mdblock
import unicodedata
import sys
from pathlib import Path, PurePosixPath

import assets as assets_mod
import catalogs as catalogs_mod
import deploy as deploy_mod
import impact as impact_mod
import redact
import schema as schema_mod
import tokens
from unicode_marks import mark_aware

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
# 🐛 Eight names in SKIP_DIRS are ORDINARY SOURCE DIRECTORY NAMES as well as build-output names,
# and the list could not tell the two apart. Measured: coveragepy's index contained 130 files and
# not one of them was from `coverage/` -- the shipped library, 54 files, 29% of the repository and
# 100% of what anybody opens the map to find. The Quick Index was its tests, its CI scripts and its
# docs. pypa/build lost all 13 files of `src/build/`, 36% of its source, the same way. Neither run
# said anything: no warning, and the coverage bar read "85%" of what remained.
#
# The name cannot decide it. Deleting these entries re-admits `target/` on every Rust repository
# and `build/` on every Gradle tree, which is thousands of generated files and the reason the list
# exists. What separates them is whether git is tracking the directory -- `build/lib/pkg/` produced
# by setuptools is ignored, `src/build/` is committed -- so that is the question asked, per PATH
# rather than per name, and only for these eight. The rest of SKIP_DIRS is unambiguous machinery
# and is never rescued: a committed `vendor/` or `node_modules/` is still noise.
AMBIGUOUS_SKIP = frozenset({"coverage", "build", "out", "target", "dist", "env", "tmp", "logs"})
# Directories skipped under one of those names. Reported by chamnan-map, because the silence was
# the half of this defect that could not be argued about -- and note SKIPPED_TOO_LARGE and
# SKIPPED_BINARY above are written and never read by anything but a test, so "report it the way
# those do" would have been another write-only list.
SKIPPED_BUILD_DIR = set()

# {".svelte": 4540, …} — files whose extension chamnan has no reader for. See indexable().
SKIPPED_UNKNOWN_EXT = __import__("collections").Counter()
_TRACKED_AMBIGUOUS = {}
_GENERATED_GLOBS = {}
SKIPPED_GENERATED = set()


def _generated_globs(root):
    """Path patterns the repository itself declares are machine output, from `.gitattributes`.

    🎯 The only machine-readable statement a repository makes that a human did not write a file.
    Measured against the GitHub trees API: of the files chamnan would index, kubernetes declares
    **1,356 of 13,748 (9.9%)** generated — `**/zz_generated.*.go` — elasticsearch 1,466 (6.2%),
    grafana 654 (4.2%), numpy 12 (1.2%). next.js and prometheus declare patterns that match nothing
    chamnan indexes, so they are unaffected. Those rows cost index bytes and drag down the
    described figure to say that a generated file exists.

    `linguist-generated` only, deliberately. `linguist-vendored` is also declared here and is NOT
    read: a vendored directory is often a fork somebody actually edits, and the machinery
    directories are already covered by SKIP_DIRS.

    Not the same judgement as .gitignore, which this file refuses to read a few lines down and for
    a reason that does not transfer: .gitignore is often absent, often wrong, and never covers a
    nested checkout's build output. `.gitattributes` is narrow, deliberate, and is what GitHub
    itself reads to decide the same question.
    """
    key = str(root)
    if key in _GENERATED_GLOBS:
        return _GENERATED_GLOBS[key]
    pats = []
    for name in (".gitattributes", ".github/.gitattributes"):
        try:
            text = (Path(root) / name).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "linguist-generated" not in line:
                continue
            if "-linguist-generated" in line:      # an explicit un-marking; leave the file alone
                continue
            pats.append(line.split()[0])
    _GENERATED_GLOBS[key] = tuple(pats)
    return _GENERATED_GLOBS[key]


def _is_generated(rel, pats):
    """`rel` against gitattributes-style patterns. `**/` means any depth, and a pattern with no
    slash in it applies at every level -- which is git's own rule, not fnmatch's."""
    for pat in pats:
        bare = pat[3:] if pat.startswith("**/") else pat
        if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(rel, bare) \
                or fnmatch.fnmatch("/" + rel, pat):
            return True
        if "/" not in bare and fnmatch.fnmatch(rel.rsplit("/", 1)[-1], bare):
            return True
    return False


def _tracked_ambiguous(root):
    """Relative paths of AMBIGUOUS_SKIP-named directories that git is tracking files under.

    Empty when there is no git, no repository, or the call fails -- chamnan has to work on a plain
    directory, so this can only ever RESCUE a directory the name list would have dropped. It never
    causes one to be skipped, which keeps the failure direction the same as before.
    """
    key = str(root)
    if key in _TRACKED_AMBIGUOUS:
        return _TRACKED_AMBIGUOUS[key]
    found = set()
    try:
        done = subprocess.run(["git", "-C", key, "ls-files", "-z"],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=20)
        if done.returncode == 0:
            for raw in done.stdout.split(b"\0"):
                if not raw:
                    continue
                parts = raw.decode("utf-8", "replace").split("/")[:-1]
                for i, part in enumerate(parts):
                    if part in AMBIGUOUS_SKIP:
                        found.add("/".join(parts[:i + 1]))
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    _TRACKED_AMBIGUOUS[key] = frozenset(found)
    return _TRACKED_AMBIGUOUS[key]

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
    # `(?<!\{)` because javadoc has an INLINE form -- `{@link Fleet#drivers}` means the words, and
    # JAVADOC_INLINE below unwraps it. This pattern runs first, so without the lookbehind adding
    # `link` to the name list cut the sentence at the brace and threw the target away. Caught by
    # the existing check rather than by reading; it is the reason the name list grows carefully.
    r"(?<!\{)[\\@](?:param(?:\[[^\]]*\])?|returns?|retval|throws?|exception|author|date|version|since|"
    r"copyright|note|warning|deprecated|todo|inheritdoc|tparam|"
    # 🐛 The tags below are the ones that actually occupy the summary slot on real repositories,
    # and they were all missing. Measured over four clones: 33 of psr7's 59 described rows carried
    # a tag (55%), and 28 of those said NOTHING ELSE -- `@covers \GuzzleHttp\Psr7\Integers` is the
    # whole summary for a test file, and nine psr7 sources are described entirely as `@internal`.
    # PHPMailer: 103 of 131 rows (78%), most of them `@package`. CodeIgniter: 118 of 173 (68%),
    # `@package` and `@category`. Those rows all count as DESCRIBED, so the coverage figure -- the
    # number that tells a user whether to run /chamnan:bootstrap -- says the work is done when the
    # index is saying nothing. That is the same failure BOILERPLATE was written for, arriving
    # through a different door.
    #
    # Enumerated rather than generalised, deliberately. The tempting rule is "cut at any @word or
    # \word", and it is wrong twice over: PHPMailer's real summary "Test fixture. Used in the
    # `PHPMailer\LocalizationTest`..." is shared by 12 files and would be truncated mid-sentence,
    # and zod carries prose containing `@zod` and `@standard-schema` that is not a tag at all.
    # A name list cannot make that mistake.
    r"internal|package|subpackage|category|covers\w*|group|requires|api|filesource|uses|see|link|"
    r"example|licen[cs]e|method|property(?:-read|-write)?|mixin|template|extends|implements|"
    r"immutable|readonly|psalm|phpstan|(?:phpstan|psalm)-[\w-]+|type|"
    r"runTestsInSeparateProcesses|runInSeparateProcess|dataProvider|testWith|test|"
    r"backupGlobals|preserveGlobalState|small|medium|large|"
    r"__NO_SIDE_EFFECTS__|__PURE__)\b.*$", re.I | re.S)


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
# Facts about each language, stated by the language, instead of one universal rule with a
# deny-list of exceptions bolted to it.
#
# The deny-list was the shape this file had, and it produced the same bug once per language. `#`
# was read as a comment everywhere except three languages that had been noticed — so Rust's
# `#[cfg(not(windows))]` became a file's DESCRIPTION in 149 of tokio's 555 files, and the index
# said a networking module was "[cfg(not(windows))]". Measured on the polyglot corpus, every one
# of Rust's 79 leading-`#` lines is `#[`; not one is a comment. The next language to be added
# would have arrived with the same defect, because the default was "assume `#` unless told".
#
# Inverting it is the whole point: a language gets `#` only by declaring it. What was a growing
# list of exceptions is now a table of positive statements, and a language missing from it is
# simply a language whose facts nobody has written down yet, which is visible rather than silently
# wrong. The shape follows VS Code's `language-configuration.json`, which is the same split every
# editor that supports many languages arrives at.
LINE_COMMENT = {
    "py": ("#",), "rb": ("#",), "sh": ("#",), "ex": ("#",), "nim": ("#",),
    "tf": ("#", "//"), "graphql": ("#",), "php": ("//", "#"), "lua": ("--",),
    "c": ("//",), "cs": ("//",), "swift": ("//",), "rs": ("//",), "go": ("//",),
    "java": ("//",), "kotlin": ("//",), "scala": ("//",), "js": ("//",),
    "dart": ("//",), "zig": ("//",), "proto": ("//",),
}
# Derived, not maintained by hand. A language that does not declare `#` as one of its line comment
# markers treats a leading `#` as something else -- a preprocessor directive in C, an attribute in
# Rust, a shebang in a language that has no other use for it -- and in every one of those cases it
# describes the compiler's needs rather than the file's job.
HASH_IS_DIRECTIVE = {lang for lang, marks in LINE_COMMENT.items() if "#" not in marks}
# A header that opens by restating the filename, then the licence — the house style of most Swift
# and Objective-C projects. Without stripping it the boilerplate check never fires, because the
# text starts with "AppDelegate.swift" rather than "Copyright".
FILENAME_LINE = re.compile(r"^[\w.-]+\.[a-z]{1,5}\s*$", re.I)
# The dash, colon or pipe that joined a restated filename to the sentence after it. Only ever
# applied immediately after that filename was removed, so a summary that legitimately opens
# with a dash is untouched.
SELF_NAME_SEPARATOR = re.compile(r"^\s*[—–\-:|]+\s*")
# The rest of the Xcode file header, once FILENAME_LINE above has taken the restated filename off
# the front. What remains is the project name and then `Created by <person> on <date>.`, and both
# get harvested as the file's summary: 17 rows of one corpus read `— OrbitalFreightDriver`, the
# app's own name, while the real `///` doc comment two lines below was never reached.
#
# It is not only noise. The attribution line carries a named human being and a date, and chamnan
# writes MAP.md into the repository and injects it at session start — so an Xcode default nobody
# wrote deliberately ends up committed and put in front of a model. That moves this from a density
# defect to one worth fixing on its own.
#
# Anchored on the attribution wording AND on a digit where the date goes, not on "a short line
# with no verb" — a real one-line summary is often exactly that shape, and "Created on demand by
# the scheduler" is a real description that must survive.
XCODE_ATTRIBUTION = re.compile(r"\bcreated\s+by\b.{0,80}?\bon\b\s*\d", re.I | re.S)
# The other attribution convention, and the one that carries an address as well as a name:
# `# Author: Jane Roe <jane@example.com>` sitting above the real summary. Reproduced in four
# shapes — `Author:`, `Author::` (RDoc), `Maintainer:` and `Written by` — each harvested as the
# file's description, so MAP.md published a person and an email while the sentence that actually
# described the file, one line below, was never reached.
#
# Same reasoning as XCODE_ATTRIBUTION above: chamnan commits MAP.md and injects it at session
# start, so this republishes a contact detail nobody chose to put there.
#
# Anchored on the punctuation, not on the word. `# Author model for the blog` is a real summary
# of a real file and has no colon; `# Authors: see AUTHORS` is a pointer and has one.
AUTHORSHIP_HEADER = re.compile(
    r"^\s*(?:@?authors?|maintainers?|contributors?|copyright\s+holder"
    # 🐛 Stepping over `Author:` alone was not enough, and the realistic header is the one that got
    # through: `# Author: Jane Roe` followed by `# Email: jane@example.com` published the address on
    # the next line instead. Contact fields carry exactly what the author line does.
    r"|e-?mails?|contacts?)\s*::?"
    r"|^\s*written\s+by\b", re.I)
# A line that is essentially just an address is a contact line without the label — some headers
# write the address alone under the name. Anchored on the whole line being one address so a summary
# that happens to MENTION an address ("Validates an email address before sending") is untouched.
BARE_EMAIL_LINE = re.compile(r"^\s*<?[\w.+-]+@[\w-]+\.[\w.]+>?\s*$")
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
    r"//\s*SPDX|/\*\s*SPDX|syntax\s*=|option\s+\w+|#\s*(?:include|import|pragma|ifndef|if\s|endif)|"
    # A Go build constraint is a switch spelled as a comment, like `#!` and SPDX above it. Skipped
    # at the line level because it cannot be bounded inside the joined block: `go:build ignore` and
    # `Package tools pins build dependencies.` are the same shape to any regex. It was the
    # description of 12 of gin's ~44 "described" files, putting real coverage at ~31% against 44%.
    r"//\s*(?:go:build|\+build)\b|"
    # 🐛 A prologue is an opener too, and leaving these three out cost more coverage than every
    # other gap in this file put together. `leading_comment` abandons the whole file on the first
    # line that is neither blank, an opener, nor a comment -- so ONE line of prologue between the
    # licence header and the real description threw the description away. Measured on real
    # repositories: express described 1 of 140 files ('use strict' on line 8), CodeIgniter 12 of
    # 289 (defined('BASEPATH') on line 3), and every shell script opening `set -euo pipefail`.
    # These are not statements the file is about; they are the same class of thing as `#!` and
    # `import`, and they belong here rather than in a new branch of the reader.
    r"""['\"]use (?:strict|client|server)['\"]|set\s+[-+][a-zA-Z]|shopt\s|"""
    r"defined\s*\([^)]*\)\s*(?:or|\|\|)\s*(?:exit|die)\b)",
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
    # `\w+` does not match a hyphen, so `@ts-expect-error` — the compiler-recognised spelling, not
    # `@ts-ignore`/`@ts-nocheck`'s single word — only matched up through `@ts-expect`, leaving
    # `-error` behind as the "description". Found while testing the Svelte/Vue/Astro reader below:
    # `// @ts-expect-error` right above an import is common in real `<script setup>` code, and
    # `Marquee.vue` (vuetifyjs/vuetify) came back described as "error". Pre-existing on any plain
    # .ts/.js file with the same opening line — not introduced by the SFC reader, only surfaced by
    # it, since a two-directive stack (`@ts-expect-error` + import) sits far more often at the very
    # TOP of a <script> block than at the top of a whole standalone module.
    r"@ts-[\w-]+|eslint-disable[\w-]*|prettier-ignore|noqa(?::\s*[\w,]+)?|"
    # 🐛 Two more families, both found by running chamnan on repositories this author did not
    # write. A Go BUILD CONSTRAINT is a switch spelled as a comment, exactly like the Ruby magic
    # comments above it: `//go:build linux && !windows` became the description of 12 of gin's ~44
    # "described" files, putting its real coverage at ~31% against the 44% reported. A JSDoc
    # type-only import is the same shape in JavaScript: `@import { Foo } from "./types.js"` was the
    # description of 289 of svelte's 440 "described" files — 66% of them — so 13% coverage was
    # really 4.3%.
    #
    # Both matter more than a bad sentence. A file with a directive as its summary counts as
    # DESCRIBED, so the coverage bar reports work that was never done, and every file in the
    # project ends up sharing one meaningless line. Stripping the directive lets the real comment
    # behind it through, which is what `tools.go` in the fixture demonstrates.
    # A JSDoc type-only import, and it is bounded rather than `.*` on purpose: the comment block
    # reaches here already JOINED, so a greedy tail would eat the real description sitting on the
    # next line. `@import { Foo } from "./types.js"` was the description of 289 of svelte's 440
    # "described" files — 66% of them — putting its real coverage at 4.3% against the 13% reported.
    # A file with a directive as its summary counts as DESCRIBED, so the coverage bar reports work
    # nobody did.
    #
    # Go build constraints are the same defect and are NOT here: they are word-shaped
    # (`go:build ignore`), indistinguishable from a sentence by any character class, so bounding
    # them failed and ate `// Package tools pins build dependencies.` on the line below. They are
    # skipped at the LINE level in SKIP_OPENERS instead, which is where `#!` and SPDX already are.
    r"@import\s*\{[^}]*\}(?:\s*from\s*['\"][^'\"]*['\"])?|"
    r"type\s*:\s*ignore|rubocop:\w+\s+[\w/,\s]+)[\s.,;:-]*""", re.I)
# How far into the opening comment to look for a licence. See the use site.
# The generated-file markers, on their own and NOT reused from BOILERPLATE.
#
# 🐛 chamnan already recognised these — `BOILERPLATE` matches "code generated by" and "do not
# edit", and uses that to blank a description so a protoc header does not become a file's summary.
# It never used the same recognition anywhere else, so on a repository of 12 `.pb.go` files beside
# one hand-written module, `chamnan-map` reported `described 1/13 (8%)` and told the user:
# "12 file(s) have no opening comment... Ask Claude: add a one-line opening comment". Following
# that advice writes a comment under a DO NOT EDIT line, which the next `protoc` run discards --
# the tool asking for work it knows will be thrown away, and reporting 8% coverage for a
# repository that is fully described where description is possible.
#
# A SEPARATE pattern rather than BOILERPLATE itself, because BOILERPLATE also matches licence
# headers, and a hand-written file carrying a copyright notice is describable and belongs in the
# nudge. Only these spellings mean "a program wrote this file".
GENERATED_MARKER = re.compile(
    r"(?:code\s+generated\s+by|generated\s+by\s+\S|do\s+not\s+edit|@generated|autogenerated"
    r"|auto-generated|this\s+file\s+is\s+generated)", re.I)

BOILERPLATE_WINDOW = 240
# 🐛 A comment that labels the import block is not a description of the file, and letting one
# through is worse than leaving the file blank -- it counts as described, inflates coverage, and
# every file in the project ends up sharing the same summary. Measured: skipping the JS directive
# prologue took express from 1 described file to 37, and 31 of those 37 read "Module dependencies."
# -- the JSDoc belonging to the `require` block below it. sinatra's 2,173-line core file has been
# described as "external dependencies" all along, with no prologue involved at all.
#
# Matched on the wording rather than on what follows, deliberately. The tempting rule is "reject a
# comment whose next code line is an import", but express's next line is `var Buffer =
# require(...)`, which is an assignment and not an opener -- so that rule does not fire where it is
# needed, and it WOULD fire on `// A small HTTP client.` above a plain `import`, which is a real
# description. The wording is the reliable signal: a comment whose entire content is the word
# "dependencies" is never about the file.
IMPORT_LABEL = re.compile(
    r"^(?:load(?:s|ing)?|require|import|include)?\s*(?:the\s+)?"
    r"(?:module|external|internal|package|third[-\s]party|project|core|npm|node|composer|vendor)?\s*"
    r"(?:dependencies|dependency|imports|requires|includes|autoloader|autoload)\b[\s.:;,-]*$", re.I)
# Used only for the comparison against IMPORT_LABEL: a trailing doc tag of ANY name, not only the
# handful DOC_TAG_TAIL knows. "Module dependencies. @private" and "Module dependencies. @api
# private" are the same label with a visibility marker stapled on, and both have to read as one.
ANY_DOC_TAG_TAIL = re.compile(r"[@\\]\w[\w-]*\b.*$", re.S)
BOILERPLATE = re.compile(
    r"(?:copyright|\(c\)|©|licen[cs]ed?\b|all rights reserved|spdx|permission is hereby|"
    r"this (?:file|program|software|source) (?:is|may)\s+(?:free|provided|distributed|licensed|be)|redistribution|frozen_string_literal|"
    r"encoding\s*[:=]|-\*-|warn_indent|jazzy\b|generated by|do not edit|@generated|"
    r"autogenerated|code generated by|the software is provided|without warranty|"
    r"in no event shall|merchantability)", re.I)
# Elixir puts the file's summary in @moduledoc, which is a module attribute holding a heredoc, not
# a comment — so a comment reader finds nothing. Phoenix scored 16 of 206 until this was handled.
MODULEDOC = re.compile(r'^\s*@(?:module)?doc\s+"""\s*$', re.M)
# A file-level doc marker: the language's own way of saying "this comment is about the FILE", as
# opposed to about the declaration under it. Rust and Zig write `//!`; without preferring it, the
# first ordinary `//` comment wins — and on tokio's crate root that produced "loom is an internal
# implementation detail. Do not show…", an aside about a build flag, in place of 431 lines of `//!`
# describing what the crate is. The one file a newcomer opens first.
FILE_DOC_MARKER = {"rs": "//!", "zig": "//!"}
FILE_DOC = re.compile(r"^[ \t]*//!(.*)$", re.M)


def _is_authorship_line(line):
    """True for `# Author: Jane Roe <jane@example.com>` and its siblings.

    Stepped over as a LINE rather than rejected as a block, which is the difference between this
    and XCODE_ATTRIBUTION. Xcode's header is its own comment block with a blank line under it, so
    rejecting the block reaches the real doc comment below. An `# Author:` line usually sits
    immediately above the summary inside ONE block, and rejecting that block threw the summary
    away with it — measured while writing this: the leak stopped and "Parses dock manifests."
    became nothing, which trades a leak for a blank index row rather than fixing anything.
    """
    body = re.sub(r"^\s*(?:#+|//+|/\*+|\*+|--+|;+|%+)\s?", "", line)
    return bool(AUTHORSHIP_HEADER.match(body)) or bool(BARE_EMAIL_LINE.match(body))


def _skip_continuation(lines, i):
    """Index just past the directive at `lines[i]`, following it across lines if it is unclosed."""
    depth = lines[i].count("(") - lines[i].count(")") + lines[i].count("[") - lines[i].count("]")
    i += 1
    # Bounded: a file whose brackets never balance must not consume the whole file looking.
    limit = min(len(lines), i + 40)
    while depth > 0 and i < limit:
        depth += (lines[i].count("(") - lines[i].count(")")
                  + lines[i].count("[") - lines[i].count("]"))
        i += 1
    return i


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
    doc = _elixir_moduledoc(lines) or _declared_desc(source, lang)
    if doc:
        return doc

    # Preferred over whatever comment happens to come first, because the language itself says this
    # one is about the file. Same reason @moduledoc is read for Elixir above.
    if FILE_DOC_MARKER.get(lang):
        doc_lines = [m.group(1).strip() for m in FILE_DOC.finditer(source)]
        joined = " ".join(x for x in doc_lines if x).strip()
        if joined:
            return _clip(MAGIC_COMMENT.sub("", joined, count=1).strip())

    i = 0
    for _ in range(6):          # at most six boilerplate blocks before giving up on the file
        while i < len(lines):
            line = lines[i]
            if not line.strip() or SKIP_OPENERS.match(line) or _is_authorship_line(line) or (
                    lang in HASH_IS_DIRECTIVE and line.lstrip().startswith("#")):
                # A directive or attribute can span lines, and only its FIRST line looked like one.
                # Rust's crate root opens `#![allow(\n    clippy::…,\n)]`, so line two fell through
                # to the comment reader, which returned "" and made the whole function give up --
                # on the one file in a crate that carries the architecture overview a newcomer
                # reads first. tokio's `src/lib.rs` has 431 lines of `//!` and described nothing.
                i = _skip_continuation(lines, i)
                continue
            break
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
        # 90 characters was enough for the licences that were failing at the time and not for the
        # next one: an ISC notice puts `copyright` and `permission is hereby` past character 90
        # ("Permission to use, copy, modify, and/or distribute this software for any purpose with
        # or without fee is hereby granted, provided that the above copyright notice…"), so the
        # whole licence became a file's description. The window is the first sentence-ish now,
        # which is where a licence announces itself and where a real description has already said
        # what the file is.
        bare = ANY_DOC_TAG_TAIL.sub("", text).strip()
        if text and not BOILERPLATE.search(text[:BOILERPLATE_WINDOW]) \
                and not IMPORT_LABEL.match(bare) \
                and not XCODE_ATTRIBUTION.search(text[:BOILERPLATE_WINDOW]):
            return _clip(text)
    return ""


# A Homebrew formula states its own one-line summary in `desc "..."`. That is not a comment, so the
# comment reader never saw it and every formula in a row came out undescribed -- on files where the
# description is the single most useful thing there is to say. Anchored on the Formula/Cask
# declaration rather than on `desc` alone, because Rake writes `desc "run the tests"` before every
# task and that describes the task, not the file.
DECLARED_DESC_LANGS = ("rb",)
_FORMULA = re.compile(r"^\s*(?:class\s+\w+\s*<\s*(?:Formula|Cask)\b|cask\s+['\"])", re.M)
_DESC = re.compile(r"""^[ \t]*desc\s+(['"])(.+?)\1\s*$""", re.M)


def _declared_desc(source, lang):
    if lang not in DECLARED_DESC_LANGS or not _FORMULA.search(source):
        return ""
    m = _DESC.search(source)
    return _clip(m.group(2).strip()) if m else ""


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


_PARSE_MEMO = (None, None)

# The keyword(s) in front of the name, on the ONE line a def/class node's col_offset points to.
# Only the keyword -- the name itself is walked off character by character below, NOT captured
# with `\w+`: Thai tone marks and vowel signs (U+0E48 MAI EK, U+0E39 SARA UU, ...) are legal
# inside a Python identifier (PEP 3131 allows Unicode category Mn/Mc after the first character)
# but `\w` in Python's `re` follows `str.isalnum()`, which excludes combining marks. `\w+` on
# "ลูกค้า" stops after the first letter -- it matches Lo but not the Mn tone mark right after it --
# so a regex "fix" here would have replaced one silent truncation with another.
_DEF_KEYWORD = re.compile(r"^(?:async\s+)?(?:def|class)\s+")


def _verbatim_name(source_lines, node):
    """`node.name` re-read from the source line instead of trusted as `ast` reports it.

    CPython's parser NFKC-normalises non-ASCII identifiers before `ast` ever sees them (PEP 3131),
    so `node.name` is not always what the file spells. Thai's SARA AM (U+0E33) is the common case:
    it normalises to NIKHAHIT + SARA AA, two codepoints for one, so a name that is 9 codepoints in
    the source comes back 10 codepoints long from `ast` -- visually identical, and a literal `grep`
    for either spelling misses the other. MAP.md's own header tells the reader to grep it, so this
    silently broke the documented workflow.

    `node.lineno`/`node.col_offset` name the exact `def`/`class` keyword regardless -- normalisation
    only touches the identifier text, not where the parser says it starts. `col_offset` is a UTF-8
    BYTE offset, not a character offset, so the line is encoded before slicing and decoded after;
    slicing the `str` directly would cut mid-character on any line with non-ASCII text before the
    keyword (a preceding decorator never applies -- it is always a separate node on its own line).

    The name is then walked off one character at a time, using `str.isidentifier()` -- the same
    XID_Start/XID_Continue rule the parser itself used to accept it -- rather than a regex class,
    because no fixed regex character class matches exactly what CPython accepts as an identifier.

    Falls back to `node.name` if the source line cannot be re-read (should not happen for a node
    `ast` just produced from this exact `source`, but a fallback beats a crash on a well-formed
    file for something that is a display nicety, not correctness-critical).
    """
    try:
        line = source_lines[node.lineno - 1]
        after = line.encode("utf-8")[node.col_offset:].decode("utf-8")
    except (IndexError, UnicodeDecodeError):
        return node.name
    m = _DEF_KEYWORD.match(after)
    if not m:
        return node.name
    name = ""
    for c in after[m.end():]:
        candidate = name + c
        if not candidate.isidentifier():
            break
        name = candidate
    return name or node.name



def _verbatim_arg(source_lines, arg):
    """An argument's name as the SOURCE spells it, not as `ast` normalised it.

    The sibling of `_verbatim_name` for `ast.arg`, and simpler: an `arg` node's position points at
    the identifier itself, so there is no keyword to skip past.

    The same PEP 3131 normalisation applies here — `def คำนวณ(จำนวน)` came back with the parameter
    spelled `จํานวน`, ten codepoints where the source has nine, so a reader grepping MAP.md for the
    parameter as written found nothing. The function name was fixed first and the arguments were
    left, which meant one line of the signature was greppable and the rest of it was not.

    `col_offset` is a UTF-8 BYTE offset, so the line is encoded before slicing — a Thai parameter
    is almost always preceded on its line by a Thai function name, which is exactly the case where
    slicing the `str` directly cuts mid-character.
    """
    try:
        line = source_lines[arg.lineno - 1]
        after = line.encode("utf-8")[arg.col_offset:].decode("utf-8")
    except (IndexError, UnicodeDecodeError, AttributeError):
        return arg.arg
    name = ""
    for c in after:
        candidate = name + c
        if not candidate.isidentifier():
            break
        name = candidate
    return name or arg.arg


def _parse_py(source, path):
    """Parse a Python file once, not twice.

    `extract_python` parsed the source, and then `_is_empty_module` parsed the same string again a
    few lines later in `scan`'s loop — measured at 5.38 ms per file over a 399-file corpus, with
    roughly half of it redundant. The memo holds one entry because `scan` handles one file at a
    time, and it is keyed by object identity rather than equality: an identity check can only ever
    miss the cache, never hit it for a different string, so the worst case is the behaviour that
    existed before.
    """
    global _PARSE_MEMO
    key, cached = _PARSE_MEMO
    if key is source:
        return cached
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = (ast.parse(source, filename=str(path)), list(caught))
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        result = (None, [])
    _PARSE_MEMO = (source, result)
    return result


def extract_python(source, path, lang='py'):
    """Parses one file. Warnings raised BY THE FILE are captured, not printed.

    An indexing tool that echoes the parse warnings of the code it reads looks broken — the output
    is chamnan's, the warning is somebody else's file, and the reader has no way to tell. They are
    counted and reported as a total instead, which is the useful half: a real invalid escape
    sequence in a 3,000-line file had gone unnoticed here because py_compile stays silent about it,
    and it becomes a hard SyntaxError in a future Python.
    """
    tree, caught = _parse_py(source, path)
    if caught:
        PARSE_WARNINGS.append((str(path), len(caught), str(caught[0].message)))
    if tree is None:
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
    source_lines = source.splitlines()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = ", ".join(_verbatim_arg(source_lines, a) for a in node.args.args)
            name = _verbatim_name(source_lines, node)
            funcs.append((f"{name}({args})", _clip(ast.get_docstring(node) or "", 90)))
        elif isinstance(node, ast.ClassDef):
            methods = [_verbatim_name(source_lines, n) for n in node.body
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            classes.append((_verbatim_name(source_lines, node),
                             _clip(ast.get_docstring(node) or "", 90), methods))
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id.isupper() and len(t.id) > 2:
                    consts.append(t.id)
    # 🎯 Last resort, and the largest measured gap in the whole map. chamnan prints its own verdict
    # on a fresh pallets/flask clone -- "described 5/81 files (6%) ... 76 file(s) have no opening
    # comment, so the index cannot say what they do. That is the single biggest lever on this map's
    # usefulness" -- and the 79 rows ending in `— —` spend 4,553 of the Quick Index's 9,549 bytes
    # saying a path exists and how long it is. src/flask/app.py, 1,628 lines, is one of them.
    #
    # The description is already inside the file. Measured with ast across that clone: 1 module
    # docstring in 83 Python files (1%), against 256 of 442 functions and classes documented (57%).
    #
    # The objection is real and this is shaped around it: a symbol's docstring describes a SYMBOL,
    # and a utility module whose first documented thing is a private helper would get a summary
    # confidently about the wrong subject -- the failure this project says is worse than silence.
    # Three things answer that. Only PUBLIC names are considered, so `_slugify` cannot be picked.
    # A class is preferred over a function, because a file usually holds one class and many
    # functions. And the symbol is NAMED in the summary, so the row reads "`Flask`: The flask
    # object implements a WSGI application" -- which cannot be read as a claim about the file,
    # only as a pointer to what is in it.
    if not doc:
        # 🐛 The FIRST documented class is usually not the file's subject. Measured by reading
        # flask's own rows: cli.py came out as `NoAppException` rather than `FlaskGroup`,
        # config.py as `ConfigAttribute` rather than `Config`, blueprints.py as
        # `BlueprintSetupState` rather than `Blueprint` -- in each case an exception or a helper
        # that happens to be defined above the thing the file is named after. Ranking by method
        # count fixes all three and costs nothing: the list is already collected two lines up, and
        # "the class with the most methods" is a good proxy for "the class this file is about".
        cands = [c for c in classes if c[1] and not c[0].startswith("_")]
        pick = max(cands, key=lambda c: len(c[2])) if cands else \
            next((f for f in funcs if f[1] and not f[0].startswith("_")), None)
        if pick:
            name = pick[0].split("(")[0]
            doc = f"`{name}`: " + _clip(pick[1].split(". ")[0], 100)
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
        # `.ts` shares this rule set, and TypeScript's declarations are mostly neither functions
        # nor classes. A real 4,133-line `.d.ts` declaring 91 exported interfaces and type aliases
        # reported "100% described" -- it had a leading doc comment -- with zero symbols: a file
        # that looks answered and is not, which is worse than one that looks empty.
        ("class", r"^(?:export\s+)?(?:declare\s+)?interface\s+(\w+)"),
        ("class", r"^(?:export\s+)?(?:declare\s+)?type\s+(\w+)\s*(?:<[^=]*>)?\s*="),
        ("class", r"^(?:export\s+)?(?:declare\s+)?enum\s+(\w+)"),
        ("const", r"^(?:export\s+)?const\s+([A-Z][A-Z0-9_]{2,})\s*="),
    ],
    "go": [
        ("func", r"^func\s+(?:\([^)]*\)\s*)?(\w+)\s*\(([^)]*)\)"),
        ("class", r"^type\s+(\w+)\s+struct"),
        ("const", r"^(?:const|var)\s+([A-Z][A-Za-z0-9_]{2,})\s*="),
    ],
    "sh": [("func", r"^(?:function\s+)?(\w+)\s*\(\)\s*\{")],
    # `\w+` is wrong for Ruby specifically, and in three separate ways that a generic rule cannot
    # know. A method name may END in `?`, `!` or `=` -- `def boot!` came back as `boot`, and
    # `def owner=(owner)` came back as `owner`, colliding with the getter of the same name. A
    # method name may also be an OPERATOR, with no word character in it at all: `def ==(other)`,
    # `def <=>(other)`, `def [](key)` matched nothing and were invisible. And a module is Ruby's
    # actual namespacing keyword, with no rule at all -- every `module Portal` was unindexed.
    # 🐛 The first character class was `[A-Za-z_]`, so a Ruby method with a non-ASCII name was not
    # captured AT ALL — not mis-spelled, invisible. Ruby has accepted UTF-8 identifiers since 1.9.
    # Measured across seven languages with the same Thai method name: go, c, js, rs, php and kotlin
    # all found it; only Ruby did not, so this is one gap rather than the "fixed in some members of
    # a set" shape it looked like.
    #
    # `[^\W\d]` is a word character that is not a digit — a Unicode letter or underscore, which is
    # what the ASCII class was trying to say. A name starting with a digit is still refused.
    "rb": [("func", r"^\s*def\s+(?:self\.)?([^\W\d]\w*[?!=]?)"),
           ("func", r"^\s*def\s+(?:self\.)?(\[\]=?|<=>|===?|!=|[<>]=?|[+\-*/%]|<<|>>|\*\*|=~|!)\s*\("),
           ("class", r"^\s*(?:class|module)\s+(\w+(?:::\w+)*)"),
           # attr_accessor and friends define real callable methods with no `def` anywhere. A
           # class can be almost entirely these -- one real file declares six on a single line and
           # the index showed none of them, understating its whole public surface.
           #
           # Known limit, recorded rather than hidden: this captures the FIRST symbol of such a
           # line, not all of them, because the shared extractor reads a rule's first group as the
           # name and a repeated group cannot express a list. One of six beats none of six -- the
           # class is at least shown to have an attribute surface -- and closing it properly means
           # the extractor learning about list-valued rules, which is a change to every language.
           ("func", r"^\s*attr_(?:accessor|reader|writer)\s+:(\w+)")],
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
    # A `data` block has TWO names and the second is its identity. Capturing only the first meant
    # every data source of the same TYPE deduped into one entry: a real production module declaring
    # nine distinct `data "aws_iam_policy" "..."` blocks showed a single row, `aws_iam_policy()`,
    # and eight real objects were gone. universal-ctags' own shipped Terraform rule captures both
    # groups and tags on the second for exactly this reason. Joined here rather than replaced,
    # because type and name together are what a reader needs from an index.
    "tf": [("class", r'^resource\s+"([^"]+)"\s+"([^"]+)"'),
           ("class", r'^data\s+"([^"]+)"\s+"([^"]+)"'),
           ("func", r'^module\s+"([^"]+)"')],
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


# 🐛 Every table above spelled an identifier `\w`, and `\w` in Python's `re` does not match the
# Mn/Mc categories — combining marks. `ชื่อ` is four codepoints of which two are marks, so it is
# not a `\w+` match, and an ordinary Thai method name was invisible in TWELVE languages. Measured
# with one name in each, before and after:
#
#     go c js ts rs php kotlin java cs swift sh   ราคา found      ชื่อ NOTHING
#     rb                                          ราคา found      ชื่อ -> `ช`   (truncated!)
#
# Ruby's is the worse outcome of the two: `[^\W\d]\w*` starts correctly and then stops at the
# first mark, so the index published a one-character name that is not the method's name — a fix I
# landed for Ruby last round that traded invisibility for a wrong answer.
#
# **And the commit that landed it said the opposite.** It recorded "measured across seven languages
# with the same Thai method name: go, c, js, rs, php and kotlin all found it; only Ruby did not, so
# this is one gap rather than the 'fixed in some members of a set' shape it looked like." That
# conclusion was an artefact of the name chosen for the test: `ราคา` has no combining marks, and
# with one that does, every language fails. Tenth occurrence of that shape here, ruled out by a
# measurement that could not see it.
#
# Rewritten over the WHOLE table in one pass rather than pattern by pattern, which is the only
# form of this fix that cannot be applied to some languages and forgotten in others. The scanner
# tracks whether it is inside a character class, because `[\w:]` has to become `[\w<marks>:]` and
# a bare `\w*` has to become `[\w<marks>]*` — substituting the same text in both places produces
# a nested bracket and a pattern that means something else entirely.
REGEX_RULES = {lang: [(kind, mark_aware(pat)) for kind, pat in rules]
               for lang, rules in REGEX_RULES.items()}
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
    # R6 experiment: single-file components. Each is mostly markup (a <template>, plain HTML, or a
    # `---` frontmatter fence) wrapped around one real JS/TS block, so the WHOLE FILE is never fed
    # to the "js" extractor — see _sfc_extraction_source, which pulls just that block out first.
    # Mapped to "js" rather than a new lang because that block IS JavaScript or TypeScript, and the
    # existing REGEX_RULES/LINE_COMMENT/FILE_DOC_MARKER entries for "js" already cover TS syntax.
    ".svelte": "js", ".vue": "js", ".astro": "js",
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


# `#ifndef X` immediately followed by `#define X` is an include guard: a name that exists to stop
# the file being included twice and describes nothing about what the file does. Every C and C++
# header has one, so listing it as a constant put one pure-noise entry in every header's row --
# `BOARD_ESP32_H` beside `LED_PIN` and `I2C_SDA`, which are the real ones a reader wants.
_INCLUDE_GUARD = re.compile(r"^[ \t]*#\s*ifndef[ \t]+(\w+)[ \t]*\r?\n[ \t]*#\s*define[ \t]+\1\b",
                            re.M)


def _guard_names(source):
    return {m.group(1) for m in _INCLUDE_GUARD.finditer(source)}


def extract_regex(source, lang):
    funcs, classes, consts = [], [], []
    guards = _guard_names(source) if lang == "c" else set()
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
                # Two capture groups on a class rule mean the declaration carries two names, and
                # both are part of its identity: Terraform's `data "aws_iam_policy" "eks_admin"`
                # is one object, not nine of type `aws_iam_policy`.
                label = ".".join(groups) if len(groups) > 1 else name
                if label not in [c for c, _, _ in classes]:
                    classes.append((label, "", []))
            elif name not in consts and name not in guards:
                consts.append(name)
    return leading_comment(source, lang), funcs, classes, consts


def _is_empty_module(source, lang):
    """True when the file declares nothing. Python is checked properly; other languages fall back to
    "is there anything that is not blank or a comment", which is all a regex can honestly claim."""
    if lang == "py":
        # Reuses the tree `extract_python` just built for this same string; see `_parse_py`.
        tree, _ = _parse_py(source, "<empty-check>")
        return False if tree is None else not tree.body
    # The comment markers come from LINE_COMMENT, not from one list for every language. A fixed
    # list said `#` is a comment everywhere -- so `#![no_std]` and `#![allow(unused_imports)]`, a
    # real Rust crate header, read as an empty file and the whole module was marked as having
    # nothing to describe. The same list said `*` opens a comment, so two lines of C pointer
    # dereference (`*p = 5;`) read as empty too. This file builds LINE_COMMENT two hundred lines
    # above for exactly this reason and this function was not using it.
    marks = tuple(LINE_COMMENT.get(lang, ("//", "#")))
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Block comment continuation is a shape, not a language fact: a leading `*` is a comment
        # only INSIDE /* ... */, which a line-at-a-time reader cannot see. Treated as one only for
        # languages whose block comment is the C family's, and never where `*` can start a
        # statement -- which is every one of them, so it costs a file being called non-empty when
        # it is empty. That direction is the safe one: an empty file described is a wasted line,
        # a real file called empty is a file the index never mentions.
        if stripped.startswith(marks) or stripped.startswith(("/*", "<!--")):
            continue
        return False
    return True


# Single-file-component fences. Non-greedy and DOTALL: a Vue/Svelte file can carry a <style> block
# after the <script>, and greedy would swallow past the first </script> it should stop at. Matches
# the FIRST block only — a second <script context="module"> in Svelte is real but rare enough that
# reading module context above instance context would need SFC-aware parsing this regex reader
# deliberately does not attempt (see mapper.py's own docstring: "approximate on purpose").
_SFC_SCRIPT = re.compile(r"<script\b[^>]*>(.*?)</script>", re.S | re.I)
# Astro's frontmatter fence: JS/TS between the file's opening `---` line and the next one. Anchored
# at the start of the file (`\A`) because `---` is also valid Markdown (a horizontal rule / YAML-ish
# separator) and can appear again later, inside the template half of the file.
_ASTRO_FRONTMATTER = re.compile(r"\A\s*---\r?\n(.*?)\r?\n---", re.S)


def _sfc_extraction_source(source, path):
    """What a Svelte/Vue/Astro single-file component actually has to offer a JS/TS reader: the one
    fenced block that is real code, not the markup around it.

    Without this, EXT_LANG mapping these three straight to "js" would run the JS extractor over the
    WHOLE file — template markup included — which is wrong in both directions at once. Vue's own
    convention opens with `<template>`, so `leading_comment` never reaches the doc comment sitting
    later inside `<script>` and every describable file reads as having no comment. And an HTML
    comment inside the template (`<!-- accessibility note -->`, common right after `<template>`)
    matches this reader's own comment-prefix regex, so a fair number of files would get a WRONG
    description instead of a missing one — a component's job, not the file's.

    A component with no <script> block (pure markup, common in real Vue/Svelte trees) returns "":
    genuinely nothing to describe, not a reader failure.
    """
    # 🐛 [found running the real suite] `path` was assumed to be a Path, but `_extract_one` never
    # touched it for a non-Python lang before this function existed, so nothing enforced that —
    # test_run_tests.py calls `mapper._extract_one(_hdr, "b.h", "c")` with a bare string, and
    # `"b.h".suffix` doesn't exist. `PurePosixPath(str(path))` accepts either without caring which
    # one the caller had, at the cost of doing that indifferently on every call, not only the three
    # SFC extensions that need it.
    ext = PurePosixPath(str(path)).suffix.lower()
    if ext in (".svelte", ".vue"):
        m = _SFC_SCRIPT.search(source)
        return m.group(1) if m else ""
    if ext == ".astro":
        m = _ASTRO_FRONTMATTER.match(source)
        return m.group(1) if m else ""
    return source


def _extract_one(source, path, lang):
    """Dispatch to the right extractor. Separated from scan() so the caller can wrap exactly this
    in one try and keep a bad file from taking the run down with it."""
    if lang == "py":
        parsed = extract_python(source, path)
        if parsed[0] is None and not parsed[1]:
            return leading_comment(source, lang), [], [], []
        return parsed
    return extract_regex(_sfc_extraction_source(source, path), lang)


def scan(root):
    """One session, so the nested-repo probe and the file walk share a single traversal."""
    import tree
    with tree.session():
        return _scan(root)


_RESOLVED = {}


def _under_nested(path, nested):
    """True when `path` sits inside one of the nested checkouts, without resolving the same
    directory once per file.

    Every file re-resolved every one of its own ancestors, and `Path.resolve()` is a syscall per
    component. Measured on a four-project tree: 12,815 resolve calls over 140 distinct directories,
    91.5x redundant, and `indexable()` at 566.5 ms median.

    Two properties keep the memo honest. It is keyed on the ancestor's own string, so two paths that
    reach the same directory by different routes share one entry rather than disagreeing — which is
    the case symlinks and a repository mounted twice both produce. And it walks upward and stops at
    the first ancestor already known NOT to be nested: everything above that one was checked when
    that entry was made, so the walk gets shorter as the scan proceeds rather than longer.

    A resolve that raises is cached as its own unresolved path rather than re-raised, which is what
    the unguarded comprehension did anyway when a parent vanished mid-scan.
    """
    # 🐛 The memo was unconditional and never cleared, unlike the sibling cache in `tree.py` which
    # is explicitly scoped and says why: a caller that scans, changes the tree, and scans again gets
    # the first answer back for the second scan. A directory created, deleted or re-symlinked
    # between two scans in one process would keep resolving to what it used to be, and a stale
    # answer here decides whether a whole checkout counts as this repository's source.
    #
    # Same rule as `tree._entries`: cache only inside a `tree.session()`, which is the scope the
    # caller has already declared it will not mutate the tree within. Outside one, resolve fresh.
    import tree as _tree
    cache = _RESOLVED if _tree._DEPTH else {}
    for parent in path.parents:
        key = str(parent)
        r = cache.get(key)
        if r is None:
            try:
                r = parent.resolve()
            except (OSError, ValueError):
                # ValueError, not only OSError: a path carrying a null byte raises it out of
                # posixpath.realpath. The unguarded comprehension this replaced raised there too,
                # so this is not a regression it introduces — it is one it closes while passing.
                r = parent
            cache[key] = r
        if r in nested:
            return True
    return False


# `python3`, `python3.12`, `node`, `bash`, `zsh`, `sh`, `ruby`, `perl` — the interpreter's own name,
# with a version suffix stripped. Matched against EXT_LANG's own vocabulary so a language chamnan
# cannot read stays unreadable rather than being smuggled in by its shebang.
_SHEBANG_LANG = {"python": "py", "python2": "py", "python3": "py", "node": "js", "nodejs": "js",
                 "bash": "sh", "sh": "sh", "zsh": "sh", "dash": "sh", "ksh": "sh",
                 "ruby": "rb", "perl": "pl", "php": "php"}


def _lang_from_shebang(path):
    """The language of an extensionless executable, from its first line, or None.

    Only the first 200 bytes are read: a shebang is the first line or it is not a shebang, and this
    runs on every extensionless file in the tree.
    """
    try:
        with path.open("rb") as fh:
            first = fh.read(200).split(b"\n", 1)[0]
    except OSError:
        return None
    if not first.startswith(b"#!"):
        return None
    line = first.decode("utf-8", errors="replace")
    # `#!/usr/bin/env python3` and `#!/bin/bash` both end in the interpreter; `env` is skipped
    # because it is the launcher, not the language.
    words = [w for w in line[2:].replace("\t", " ").split(" ") if w]
    for word in words:
        name = word.rsplit("/", 1)[-1]
        if name in ("env", "-S"):
            continue
        # `python3.12` -> `python3`; a trailing minor version is not a different language.
        base = name.split(".")[0]
        if base in _SHEBANG_LANG:
            return _SHEBANG_LANG[base]
        return None
    return None


# The first line of every git-lfs pointer, fixed by the spec. A pointer is also required to be
# small -- the spec caps it well under this -- and the size guard is what stops a real source file
# that happens to quote the spec URL from being mistaken for one.
_LFS_MAGIC = "version https://git-lfs.github.com/spec/v1"
_LFS_MAX_BYTES = 1024


def lfs_pointer_size(text):
    """Bytes the REAL file holds, when `text` is a git-lfs pointer rather than the file itself.

    🐛 A 41 MB file stored in LFS is checked out as a three-line pointer, and the index described it
    as `(3L) — —`: a trivial, empty file. That is the index stating something untrue about the
    repository, which is worse than omitting the file -- a reader who trusts it will not look, and a
    reader who does look finds three lines of metadata and concludes the file is broken.

    Skipping such files would only turn the lie into a silence. The pointer carries the real size in
    its own `size` line, so the honest answer is available for free: say what the file is and how big
    it actually is. Recommended by an earlier research round and never implemented until the case was
    reproduced -- an LFS-tracked `.py` renders in the Quick Index like any other source file.

    Returns None for anything that is not a pointer.
    """
    if not text.startswith(_LFS_MAGIC) or len(text) > _LFS_MAX_BYTES:
        return None
    for line in text.splitlines():
        if line.startswith("size "):
            try:
                return int(line[5:].strip())
            except ValueError:
                return None
    return None


def is_text_file(path):
    """A NUL in the first block means binary, and no text source contains one. Split out of
    `indexable` so a caller that skipped the sniff for speed can apply it to the few files it
    actually cares about."""
    try:
        with path.open("rb") as fh:
            return b"\x00" not in fh.read(8192)
    except OSError:
        return False


def indexable(root, nested=None, with_text=False, sniff=True):
    """Yield (path, lang) for exactly the files that belong in this repository's index, or
    (path, lang, text) when `with_text` asks for the content too.

    Factored out of _scan because a second caller needed the same answer and got it wrong. The
    session-start staleness check walked the tree with only the extension filter, so it counted a
    nested checkout's files as this repository's own — and reported the index as stale every time
    chamnan's own source was edited, about 28 files the index was never going to contain. On the
    repository chamnan is developed in that warning was permanently on, which is the same as absent.

    One definition, two callers. A filter this specific will drift the moment it is written twice.
    Must be called inside a tree.session().

    `with_text=True` exists because `_scan()` re-opened and re-read every file `read_text()` had
    just been sniffed for a NUL byte -- 564 opens for 281 files, measured on this repository, the
    second read discarding nothing the first one hadn't already paid for. The staleness caller
    (`_indexable` in the session-start hook) never wants content, only the path, so it keeps the
    cheap 8 KB sniff and default `with_text=False` -- this does not add a whole-file read to a path
    that used to sniff a prefix.
    """
    import tree
    if nested is None:
        nested = _nested_repo_dirs(root)
    for path in tree.files(root):
        if not path.is_file():
            continue
        if nested and _under_nested(path, nested):
            continue          # a checkout inside this checkout is not this repository's source
        # Only the parts BELOW the scan root. Checking path.parts would test the absolute path, so
        # a repository that happens to live under /tmp, ~/build, or any directory named env/out/
        # target would have every one of its files skipped and report "no source files" — silently,
        # since nothing errors. Found 2026-08-19 by running the tool inside /private/tmp.
        rel_parts = path.relative_to(root).parts
        _gen = _generated_globs(root)
        if _gen and _is_generated("/".join(rel_parts), _gen):
            SKIPPED_GENERATED.add("/".join(rel_parts))
            continue
        tracked = _tracked_ambiguous(root)
        dropped = None
        for i, part in enumerate(rel_parts[:-1]):
            if part not in SKIP_DIRS:
                continue
            here = "/".join(rel_parts[:i + 1])
            if part in AMBIGUOUS_SKIP and here in tracked:
                continue      # committed source that happens to share a build-output name
            dropped = here
            break
        if dropped is not None:
            # `.chamnan/logs` is our own workspace, not the user's build output, and reporting it
            # on every run in every repository is noise that trains the reader to ignore the line.
            if dropped.rsplit("/", 1)[-1] in AMBIGUOUS_SKIP and not dropped.startswith(".chamnan/"):
                SKIPPED_BUILD_DIR.add(dropped)
            continue
        if redact.is_blocked(path):
            continue          # private keys, certificates, local databases — never opened at all
        lang = EXT_LANG.get(path.suffix.lower())
        if not lang and not path.suffix:
            # 🐛 chamnan's own `bin/` was invisible to chamnan's own index, from the first commit.
            # Nine extensionless shebang scripts — every command-line entry point it has — 2,382
            # lines, and the dependency graph was wrong for every `lib/` module because of it:
            # `lib/redact.py` was published as having 7 consumers when it has 16, and all nine
            # missing ones are the CLI tools that print output for a living, which is the exact
            # thing redaction exists to protect.
            #
            # A shebang names the interpreter as reliably as a suffix does, and this is what `file`
            # and every linter use for the same reason. Read only when there is NO extension at all,
            # so nothing that already has an answer is re-decided, and only the first line.
            lang = _lang_from_shebang(path)
        if not lang:
            # 🐛 Silently dropped, and that is the one skip reason with no record. Large, binary,
            # generated and build-directory files are all tracked and reported, on the stated
            # grounds that a file vanishing unannounced is "false confidence rather than degraded
            # confidence, which is the worse kind" — an unreadable EXTENSION got no such treatment.
            #
            # Measured on Svelte's own monorepo: 4,540 `.svelte` files absent from MAP.md, more
            # than the 3,480 files it did index, with nothing anywhere saying so. A three-file
            # fixture reproduces it exactly: `.svelte` + `.vue` + `.js` reports "1 source file(s)"
            # and "100% described".
            #
            # Counted by extension rather than by path: the useful sentence is "4,540 .svelte files
            # were not read", not a list of names, and a repository is full of `.json`, `.lock` and
            # `.png` that nobody expects an index to cover. The caller decides what is worth saying.
            SKIPPED_UNKNOWN_EXT[path.suffix.lower() or "(no extension)"] += 1
            continue
        try:
            size = path.stat().st_size
            if size > MAX_FILE_BYTES:
                # Recorded, not merely skipped. A 2.2MB generated file used to disappear from the
                # index while the run reported "1 source file(s)" and 100% coverage of what it saw
                # — false confidence rather than degraded confidence, which is the worse kind.
                SKIPPED_TOO_LARGE.append((path, size))
                continue
        except OSError:
            continue
        # Binary content under a source extension. A PNG saved as asset.py was read with
        # errors="replace" and indexed as code: 351 "lines" counted from newline bytes inside the
        # image, marked describable, and flagged forever as missing a comment it can never have.
        # A NUL in the first block is the cheap, reliable signal, and no text source contains one.
        if with_text:
            # One open, one read -- `_scan()` was about to `read_text()` the same bytes this sniff
            # already holds. `.decode()` skips `TextIOWrapper`'s universal-newline translation that
            # `read_text()` performs by default, so it is replicated here explicitly: without it, a
            # CRLF-authored file changes its own line count between this path and the sniff-only one.
            try:
                raw = path.read_bytes()
            except OSError:
                continue
            if b"\x00" in raw[:8192]:
                SKIPPED_BINARY.append(path)
                continue
            text = raw.decode("utf-8-sig", errors="replace")
            if "\r" in text:
                text = text.replace("\r\n", "\n").replace("\r", "\n")
            yield path, lang, text
        elif sniff:
            try:
                with path.open("rb") as fh:
                    if b"\x00" in fh.read(8192):
                        SKIPPED_BINARY.append(path)
                        continue
            except OSError:
                continue
            yield path, lang
        else:
            # 🐛 `sniff=False` exists for the staleness check, which asks only "is anything NEWER
            # than the map" and needs an mtime, not a byte of content. It was opening and reading
            # 8 KB of every file in the repository on EVERY session start — a hook that fires up to
            # 82 times a session. Measured on a 6,000-file repository with a CURRENT index:
            # 16-39 seconds per firing, against the docstring's own claim of "0.04s on a 1,478-file
            # repository". The caller re-checks the handful of files that are actually newer.
            yield path, lang


def reset_skips():
    """Empty the five "what did not make it into the index" lists. Call once per REPORT, not per scan.

    🐛 `_scan` used to clear four of them on entry, which is wrong the moment a run scans more than
    one directory: `chamnan-map <a> <b>` calls scan() per target, so the second call wiped the first
    target's skips and the report named only the last one's. Reproduced with a 2.3 MB file under `a`
    — `chamnan-map a` says "not indexed, over the size limit: big.py (2.3MB)", `chamnan-map a b` says
    nothing at all, and the coverage bar still reads 100%. These lists exist because, in this file's
    own words, a silently missing file is "false confidence rather than degraded confidence, which is
    the worse kind"; a multi-directory run had exactly that.

    PARSE_WARNINGS had the mirror bug — cleared by nobody, so warnings leaked from one scan into an
    unrelated later one in the same process. Same list, same lifetime, so it is reset here too.

    Accumulating within a run and resetting between runs is the safe direction for both: the failure
    of over-reporting is a reader seeing a file named twice, and the failure of under-reporting is a
    file vanishing from a report that claims to be complete.
    """
    SKIPPED_TOO_LARGE.clear()
    SKIPPED_BINARY.clear()
    SKIPPED_BUILD_DIR.clear()
    SKIPPED_GENERATED.clear()
    SKIPPED_UNKNOWN_EXT.clear()
    PARSE_WARNINGS.clear()


def _scan(root):
    files = []
    nested = _nested_repo_dirs(root)
    for path, lang, source in indexable(root, nested, with_text=True):
        # One try around everything this file touches, not around each call. Two separate crashes
        # were found the same way — ast.parse raising ValueError on a .py file whose contents were
        # binary — because each new call site had to remember to guard itself. A map missing one
        # line is useful; a traceback is not, and it takes the other 195 files with it.
        try:
            doc, funcs, classes, consts = _extract_one(source, path, lang)
            # _sfc_extraction_source is a no-op for every extension but .svelte/.vue/.astro, so this
            # stays the plain `_is_empty_module(source, lang)` everywhere else. For those three, an
            # empty extraction (no <script>, no frontmatter) must count as nothing-to-describe here
            # too, or a markup-only component inflates the "described" denominator with a file
            # _extract_one already gave up on.
            describable = bool(source.strip()) and not _is_empty_module(
                _sfc_extraction_source(source, path), lang)
            # A generated file is real source and stays in the index -- what changes is that it is
            # not counted as missing a summary and is not offered to the commenter agent. Read from
            # the same window BOILERPLATE uses, because a marker further down the file is a
            # sentence about generation rather than a declaration of it.
            generated = bool(GENERATED_MARKER.search(source[:BOILERPLATE_WINDOW]))
        except Exception:
            doc, funcs, classes, consts, describable = "", [], [], [], False
            generated = False
        files.append({
            "generated": generated,
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
            # None for every ordinary file, so callers that never heard of LFS are unaffected.
            "lfs": lfs_pointer_size(source),
            "funcs": funcs, "classes": classes, "consts": consts,
            # Not rendered anywhere -- carried so render()'s later scanners (catalogs.scan_routes,
            # catalogs._django_mounts, catalogs.scan_env) can reuse the read this loop already paid
            # for instead of opening the same 281 files again apiece. Measured on this repository:
            # scan()+render() opened 989 times for 281 files before this field existed. A caller
            # that builds its own `files` list without this key still works -- every reader below
            # falls back to `path.read_text()` when it is absent.
            "_source": source,
        })
    return files


def render(files, root):
    """One session for the whole render — every scanner below shares one walk."""
    import tree
    with tree.session():
        return _render(files, root)


# Twice the default session budget. Below that, reading the Quick Index in full is the habit the
# file is written to encourage; above it, that advice costs more than the file saves and the header
# says so instead. A round number, stated rather than fitted -- the honest claim is "this is large
# enough that reading it whole is the wrong move", not a precise threshold anyone measured.
_READ_IN_FULL_CEILING = 6_000

# The whole paragraph swaps, not just its first sentence. Leaving the rest in place produced a
# header that contradicted itself on a large repository: "the index is a fraction of the detail"
# is false where the index measures larger than the source it summarises.
_HOW_TO_READ = ("**Read the Quick Index in full. Do NOT read the Full Detail section end to end** "
                "— grep it\n"
                "for the one heading you need (`## \\`path\\``). That habit is the entire point of "
                "this file:\n"
                "the index is a fraction of the detail, and the detail is a fraction of the source.")

_TOO_BIG_TO_READ_IN_FULL = (
    "**This index is too large to read in full — grep BOTH sections, never read either whole.**\n"
    "Look for the one heading you need (`## \\`path\\``), or read one directory's block at a time.\n"
    "This repository has enough files that summarising them all costs what reading them would: the\n"
    "session-start block rolls this up to one line per directory, and this file is the place to\n"
    "come when you need one of them in full.")


def _render(files, root):
    total_chars = sum(f["chars"] for f in files)
    lines = [
        f"# Architecture map — {root.name}",
        "",
        f"Generated by chamnan. {len(files)} source file(s), {total_chars:,} characters.",
        "",
        _HOW_TO_READ,
        "",
        "## Quick Index",
        "",
    ]
    _dir_counts = {}
    for _f in files:
        _d = str(PurePosixPath(_f["path"]).parent)
        _dir_counts[_d] = _dir_counts.get(_d, 0) + 1
    cur_dir = None
    for f in files:
        counts = []
        if f["funcs"]:
            counts.append(f"{len(f['funcs'])}fn")
        if f["classes"]:
            # `ty` where the language's declarations are mostly interfaces and type aliases, `cls`
            # where they are classes. Not cosmetic: a `.d.ts` of three exported `type` aliases and
            # no class at all rendered as `3cls`, a count of a thing the file does not contain. The
            # extraction is right -- those ARE the file's declared types and a reader needs them --
            # so the label is what had to change, not what is collected.
            counts.append(f"{len(f['classes'])}{'ty' if f.get('lang') == 'js' else 'cls'}")
        summary = f["doc"] or "—"
        if f.get("lfs") is not None:
            # Overrides the docstring rather than appending to it: a pointer has no docstring, and
            # if some future format ever gave it one it would be describing a file that is not here.
            summary = (f"**not checked out** — a git-lfs pointer to "
                       f"{assets_mod.human_bytes(f['lfs'])} of content")
        # `one_line` on the PATH, not only on the summary. A file name may legally contain a
        # newline, and an index row is a `- ` bullet -- so a file called
        # "safe\n- **INJECTED** (999L) -- ....py" rendered as TWO bullets, the second of which a
        # reader has no way to tell from a real entry, inside the one section every session reads
        # in full. Same class as the milestone-title bug, on a surface the fix had not reached.
        # The directory is stated once per directory rather than once per file. Measured: the
        # repeated prefix was 30.6% of Quick Index tokens on the published corpus, and grouping
        # takes the index down 9.9% on a 283-file monorepo, 2.5% and 1.2% on two flat repositories
        # — the gain scales with how deep the tree is, so a flat repo is barely touched and is not
        # made worse either.
        #
        # This is safe to do to the Quick Index specifically, and NOT to Full Detail, because of
        # what the map tells its reader four lines above: read the Quick Index in full, and grep
        # Full Detail for `## \`path\``. Grepping by full path is a Full Detail workflow and its
        # headings are untouched. A directory with a single file keeps its inline path, since a
        # heading plus one row costs more than the prefix it removes.
        # 🐛 A heading was emitted only for directories holding more than one file, so a root file
        # or a lone file in its own directory kept its full path and rendered UNDERNEATH the
        # previous directory's heading. `root.py` sat under `**`a/`**` and reads as `a/root.py`,
        # which does not exist — the same "names a path that is not there" class as the roll-up bug
        # fixed this morning, reintroduced by the grouping that replaced it.
        #
        # Every directory transition gets a heading now, root included, and every row is a basename.
        # It costs a heading on a single-file directory, which is roughly what the full path cost
        # anyway, and it removes the case where a row cannot be resolved at all.
        here = str(PurePosixPath(f["path"]).parent)
        if here != cur_dir:
            cur_dir = here
            lines.append("")
            lines.append(f"**`{mdblock.one_line(here if here != '.' else '.')}/`**")
        shown = PurePosixPath(f["path"]).name
        lines.append(f"- **`{mdblock.one_line(shown)}`**"
                     f" ({f['lines']}L{', ' + '/'.join(counts) if counts else ''}) — {summary}")

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
            # `type` where the language's declarations are interfaces and aliases, matching the
            # Quick Index's own `ty` counter. Full Detail is what the index tells a reader to grep
            # for symbol-level truth, and it was calling a union type alias a class.
            kind = "type" if f.get("lang") == "js" else "class"
            lines.append(f"- **{kind} {name}**{' — ' + doc if doc else ''}")
            if methods:
                lines.append(f"  - methods: {', '.join(methods[:30])}")
        for sig, doc in f["funcs"]:
            lines.append(f"- `{sig}`{' — ' + doc if doc else ''}")
        lines.append("")
    # One choke point, on the whole document, rather than at each of the dozen places a summary is
    # extracted. Scrubbing per-extractor means every new extractor is a chance to forget; scrubbing
    # the finished text means nothing reaches the file unscanned, including sections added later.
    # 🐛 The header said "Read the Quick Index in full" unconditionally. On a 5,000-file monorepo
    # that index measures ~132,000 tokens — 96% of the source — and the instruction is not merely
    # unhelpful there, it is false: reading it in full every session is precisely the cost this
    # tool exists to avoid. chamnan already writes a self-aware caveat at the SMALL end ("larger
    # than the source — this repository is too small for an index to pay"); this is the matching
    # one at the large end.
    #
    # Measured after the index is built rather than guessed from the file count, because the size
    # that matters is the rendered text and nothing else predicts it: 5,000 tiny files and 500
    # heavily documented ones can land in the same place.
    text = "\n".join(lines) + "\n"
    if _HOW_TO_READ in text:
        quick = text.split("## Quick Index", 1)[-1].split("\n---", 1)[0]
        if tokens.estimate(quick) > _READ_IN_FULL_CEILING:
            text = text.replace(_HOW_TO_READ, _TOO_BIG_TO_READ_IN_FULL, 1)
    return redact.scrub(text)


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
    reset_skips()
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
