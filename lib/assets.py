"""An inventory of the material that is NOT source — and the reason it belongs in the index.

A platform of any size carries far more payload than code: scanned paperwork, proof-of-delivery
photos, exports, archives, model weights. None of it should ever be read to understand the system,
and chamnan does not read it. The temptation is therefore to say nothing about it at all.

That is the wrong call, and it costs more than it saves. An agent that is told nothing about a
directory does not conclude the directory is unimportant — it goes and looks. One `find` over a
large mount, a `ls` of a few levels, and two or three files opened to see what they are, costs far
more than the forty tokens it takes to say: attachments/nfs holds 12,400 files totalling 4.2 GB,
mostly PDF and PNG, and it is payload rather than source.

So this section exists to STOP exploration, not to enable it. It reports shape only — counts, total
size, the extensions that dominate — and never opens a file. Directories below a threshold are left
out entirely, because a handful of images beside a README is not a mount and saying so is noise.
"""
from collections import defaultdict
import mdblock

# Below this many non-source files a directory is not an asset store, it is a few loose files.
MIN_FILES = 12
MAX_DIRS_LISTED = 12
MAX_EXTS_SHOWN = 6
# Extensions that carry meaning a reader might want even though chamnan does not parse them. They
# are counted like any other asset but named first, because "this tree is 900 CSVs" is a different
# fact from "this tree is 900 PNGs".
# Formats worth naming when a directory is otherwise just bulk. `.md` is NOT here: this section
# is headed "Payload, not code — do not read these to understand the system", and a docs/ folder of
# hand-written runbooks is the one place a reader most needs to go. Fifteen incident-response
# documents were being labelled as payload to skip. `.sql` is not here either: a migrations
# directory is how a database-backed system is actually defined.
NOTABLE = {".csv", ".json", ".xml", ".parquet", ".avro", ".log"}
# Named separately and never called payload — prose and schema a reader is meant to open.
READABLE = {".md", ".rst", ".adoc", ".txt", ".sql"}
# 🐛 Source code in a language chamnan has no extractor for is not payload, and calling it payload
# is the worst thing this section can do. mojolicious: 151 .pm and 110 .t files -- the entire
# framework -- landed here under "**Payload, not code — do not read these to understand the
# system**", while the Quick Index it left behind was nine minified vendor bundles and test
# fixtures. An empty map at least sends the agent to grep; that one instructs it not to look.
#
# This is the third carve-out of the same shape: .md and .sql went to READABLE and the build
# manifests were dropped entirely, both times because the heading's sentence was FALSE about them.
# It is false about a Perl module for the same reason and at much greater cost, because these can
# be the whole repository rather than a corner of it.
#
# Extensions verified absent from mapper.EXT_LANG when this was written. A few are ambiguous --
# `.cls` is Apex and also LaTeX, `.s` is assembly, `.st` is Smalltalk and also structured text --
# and every one of them fails safe: the worst outcome is telling a reader that a text file is text
# they may read, which is the direction this whole change moves in.
UNEXTRACTED_SOURCE = {
    ".pm", ".pl", ".t", ".pod", ".ps1", ".psm1", ".vue", ".svelte", ".r", ".jl", ".hs", ".lhs",
    ".clj", ".cljs", ".cljc", ".erl", ".hrl", ".groovy", ".gvy", ".sol", ".cr", ".f90", ".f95",
    ".f03", ".for", ".vb", ".vbs", ".pas", ".pp", ".adb", ".ads", ".tcl", ".awk", ".bas", ".asm",
    ".s", ".v", ".sv", ".vhd", ".vhdl", ".fs", ".fsi", ".fsx", ".elm", ".purs", ".rkt", ".scm",
    ".ss", ".lisp", ".lsp", ".el", ".ml", ".mli", ".re", ".res", ".coffee", ".hx", ".st", ".abap",
    ".apex", ".cls", ".trigger", ".rexx", ".ahk", ".au3", ".nut", ".moon",
}
# 🐛 This held a second, hand-maintained copy of mapper.SKIP_DIRS and had drifted from it: `build`,
# `venv`, `tmp` and `coverage` were missing, so this section reported them as "stored material" --
# payload worth knowing about -- on the same repository where mapper had already classified them as
# build noise. One list now, so the two cannot disagree again.
#
# Fetched at call time rather than imported at module level: mapper imports THIS module, so a
# top-level `from mapper import SKIP_DIRS` is a circular import and fails at the first `import
# mapper` anywhere. The cache keeps it to one lookup.
_SKIP_DIRS = None


def _skip_dirs():
    """mapper's list, resolved late to keep the import graph acyclic."""
    global _SKIP_DIRS
    if _SKIP_DIRS is None:
        import mapper
        _SKIP_DIRS = mapper.SKIP_DIRS
    return _SKIP_DIRS
# Build and project manifests are not payload. They declare dependencies and project layout, which
# is exactly what someone joining the repo needs, and this section's headline tells the reader not
# to open them to understand the system. Being counted here made that sentence false about go.mod
# and the .csproj files -- so they are left out rather than mislabelled.
BUILD_MANIFESTS = {".csproj", ".fsproj", ".vbproj", ".sln", ".props", ".targets", ".sbt",
                   ".gradle", ".mod", ".sum", ".cabal", ".nimble", ".gemspec", ".podspec",
                   ".cmake", ".bazel", ".bzl", ".lock"}
BUILD_NAMES = {"go.mod", "go.sum", "cargo.toml", "package.json", "pyproject.toml", "setup.cfg",
               "gemfile", "podfile", "config.ru", "rakefile", "makefile", "cmakelists.txt",
               "build.gradle", "settings.gradle", "pom.xml", "composer.json", "mix.exs",
               "pubspec.yaml", "build.zig", "meson.build", "build", "workspace",
               # 🐛 The list held `makefile` and `rakefile` and stopped there, so a project that
               # keeps its entry points anywhere else had them filed under "Payload, not code — do
               # not read these to understand the system." simonw/datasette keeps its build, test
               # and lint commands in a Justfile — `just test` is what its own CONTRIBUTING tells
               # contributors to run — and the injected block described its root directory as
               # "17 files … (none) x8" beneath that heading. The comment four lines up already
               # states the intent: a build manifest is "exactly what someone joining the repo
               # needs", and being counted here "made that sentence false".
               #
               # ledger.py's _EXTENSIONLESS_FILES has carried the right list all along, Justfile
               # included. Two lists answering the same question and disagreeing is the shape of
               # this defect, not the missing name.
               "justfile", "dockerfile", "containerfile", "jenkinsfile", "taskfile.yml",
               "taskfile.yaml", "earthfile", "magefile.go", "tiltfile", "procfile", "vagrantfile",
               "brewfile", "gnumakefile", "tox.ini", "noxfile.py", "justfile.toml"}


def human_bytes(size):
    """A byte count as a person reads it: 134B, 40.0MB, 1.2GB.

    Public, and the only copy. `peek` carried a near-identical `_human` that stopped at GB and
    `mapper` was about to grow a third when the git-lfs pointer summary needed one. Three
    definitions of the same six lines is how they drift: peek's would have printed "41943040.0GB"
    for a terabyte where this one says TB.
    """
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024


def scan(root, source_paths, ext_lang):
    """source_paths: the set mapper already indexed, so nothing is counted twice."""
    groups = defaultdict(lambda: {"count": 0, "bytes": 0, "exts": defaultdict(int)})
    import tree
    # One pruned walk shared with every other scanner — see lib/tree.py. rglob descended into
    # .venv and node_modules and only then discarded them, which cost 19.2s of a 75s map here.
    for path in tree.files(root):
        try:
            if not path.is_file() or path.is_symlink():
                continue
            rel = path.relative_to(root)
        except (OSError, ValueError):
            continue
        if any(p in _skip_dirs() or p.startswith(".") for p in rel.parts[:-1]):
            continue
        if str(rel) in source_paths or path.suffix.lower() in ext_lang:
            continue
        if path.suffix.lower() in BUILD_MANIFESTS or path.name.lower() in BUILD_NAMES:
            continue
        top = rel.parts[0] if len(rel.parts) > 1 else "(root)"
        try:
            size = path.stat().st_size
        except OSError:
            continue
        g = groups[top]
        g["count"] += 1
        g["bytes"] += size
        g["exts"][path.suffix.lower() or "(none)"] += 1
    return {k: v for k, v in groups.items() if v["count"] >= MIN_FILES}


def render(groups):
    if not groups:
        return ""
    # Split by EXTENSION rather than by directory, because one directory holds both: mojolicious'
    # `lib/` is 112 .pm modules and 8 .png images. Grouping by directory would have to call the
    # whole of it one thing or the other, and either answer is wrong about most of the files in it.
    payload, unindexed = {}, {}
    for name, g in groups.items():
        for bucket, keep in ((unindexed, True), (payload, False)):
            exts = {e: n for e, n in g["exts"].items()
                    if (e in UNEXTRACTED_SOURCE) is keep}
            if not exts:
                continue
            share = sum(exts.values()) / max(g["count"], 1)
            bucket[name] = {"count": sum(exts.values()),
                            "bytes": int(g["bytes"] * share), "exts": exts}
    out = []
    if payload:
        ranked = sorted(payload.items(), key=lambda kv: -kv[1]["bytes"])
        total_n = sum(g["count"] for _, g in ranked)
        total_b = sum(g["bytes"] for _, g in ranked)
        out += ["## Stored material (not source)", "",
                f"{total_n:,} files, {human_bytes(total_b)}. **Payload, not code — do not read these to "
                f"understand the system.** Listed so that their shape is known without anyone going "
                f"looking, which costs more than this section does.", ""]
        for name, g in ranked[:MAX_DIRS_LISTED]:
            exts = sorted(g["exts"].items(), key=lambda kv: -kv[1])[:MAX_EXTS_SHOWN]
            notable = [e for e, _ in exts if e in NOTABLE]
            readable = [e for e, _ in exts if e in READABLE]
            shown = ", ".join(f"{e} ×{n:,}" for e, n in exts)
            tail = "  _(machine-readable: " + ", ".join(notable) + ")_" if notable else ""
            # Said out loud, because the section's own heading tells the reader not to open any of
            # this. A directory of hand-written runbooks or of schema migrations was being sent past
            # under that instruction — the exact places a reader needs to go, labelled as places to
            # skip.
            if readable:
                tail += ("  _(**written to be read**: " + ", ".join(readable) + ")_")
            out.append(f"- **`{mdblock.one_line(name)}/`** — {g['count']:,} files, {human_bytes(g['bytes'])} — {shown}{tail}")
        if len(ranked) > MAX_DIRS_LISTED:
            out.append(f"- _…and {len(ranked)-MAX_DIRS_LISTED} more directories_")
        out.append("")
    if unindexed:
        ranked = sorted(unindexed.items(), key=lambda kv: -kv[1]["count"])
        total_n = sum(g["count"] for _, g in ranked)
        out += ["## Source chamnan cannot index", "",
                f"{total_n:,} files in languages this index has no extractor for. **These are "
                f"source: read them directly.** They carry no rows above and no symbols in Full "
                f"Detail, so the index is silent about them rather than complete without them — "
                f"which is worth knowing before concluding a repository is small.", ""]
        for name, g in ranked[:MAX_DIRS_LISTED]:
            exts = sorted(g["exts"].items(), key=lambda kv: -kv[1])[:MAX_EXTS_SHOWN]
            shown = ", ".join(f"{e} ×{n:,}" for e, n in exts)
            out.append(f"- **`{mdblock.one_line(name)}/`** — {g['count']:,} files — {shown}")
        if len(ranked) > MAX_DIRS_LISTED:
            out.append(f"- _…and {len(ranked)-MAX_DIRS_LISTED} more directories_")
        out.append("")
    return "\n".join(out)
