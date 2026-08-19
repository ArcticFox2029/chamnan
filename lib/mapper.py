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
import re
import sys
from pathlib import Path

import catalogs as catalogs_mod
import redact
import schema as schema_mod

# Directories that are never source: dependency trees, build output, VCS internals, caches.
SKIP_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "__pycache__", ".venv", "venv", "env",
    "dist", "build", "target", "out", ".next", ".nuxt", "vendor", ".terraform",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "coverage", ".idea", ".vscode",
    "site-packages", ".gradle", ".cache", "tmp", "logs",
}
MAX_FILE_BYTES = 2_000_000
CHARS_PER_TOKEN = 3.6  # rough English/code average; only used for the report, never for logic


def _clip(text, limit=110):
    text = " ".join((text or "").split())
    return text[: limit - 1] + "…" if len(text) > limit else text


COMMENT_PREFIX = re.compile(r"^\s*(?:/\*+|\*+/?|//+|#+|--+|<!--)\s?")


def leading_comment(source):
    """The file's opening comment block, used as its one-line summary.

    Most languages have no docstring, but nearly every file that matters opens with a comment
    saying what it is. Reading three lines of that beats guessing from the filename."""
    out = []
    for line in source.splitlines()[:14]:
        stripped = line.strip()
        # A shebang is a comment to the parser and noise to the reader: harvesting it makes every
        # shell script's summary start with "!/bin/bash" instead of saying what the script does.
        if stripped.startswith("#!"):
            continue
        if not stripped:
            if out:
                break
            continue
        if not COMMENT_PREFIX.match(line):
            break
        text = COMMENT_PREFIX.sub("", line).strip().rstrip("*/").strip()
        if text:
            out.append(text)
        if len(out) >= 3:
            break
    return _clip(" ".join(out))


# --- Python: real parsing, because the stdlib gives it for free -------------------------------
def extract_python(source, path):
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return None, [], []
    doc = _clip(ast.get_docstring(tree) or "")
    doc = doc.split(". ")[0] if doc else ""
    if not doc:
        # A module docstring is the Python convention, but plenty of real files open with a `#`
        # header instead and mean exactly the same thing. Reading only docstrings scored a file
        # with a perfectly good "# Reads config" header as undescribed, which then drags down the
        # coverage figure the whole design leans on.
        doc = leading_comment(source)
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
}
EXT_LANG = {
    ".py": "py", ".js": "js", ".mjs": "js", ".cjs": "js", ".jsx": "js", ".ts": "js", ".tsx": "js",
    ".go": "go", ".sh": "sh", ".bash": "sh", ".command": "sh", ".zsh": "sh",
    ".rb": "rb", ".rs": "rs", ".java": "java", ".kt": "java", ".tf": "tf", ".php": "php",
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
    return leading_comment(source), funcs, classes, consts


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
        if lang == "py":
            parsed = extract_python(source, path)
            if parsed[0] is None and not parsed[1]:
                doc, funcs, classes, consts = leading_comment(source), [], [], []
            else:
                doc, funcs, classes, consts = parsed
        else:
            doc, funcs, classes, consts = extract_regex(source, lang)
        files.append({
            "path": str(path.relative_to(root)), "lang": lang, "chars": len(source),
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
    for section_text in (schema_mod.render(tables),
                         catalogs_mod.render_routes(routes),
                         catalogs_mod.render_env(env_pairs, env_unsafe)):
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
        src = sum(f["chars"] for f in files)
        idx = text.index("## Full Detail")
        langs = {}
        for f in files:
            langs[f["lang"]] = langs.get(f["lang"], 0) + 1
        print(f"{root.name:<22} {len(files):>4} ไฟล์  {'+'.join(f'{k}:{v}' for k,v in sorted(langs.items(), key=lambda x:-x[1]))}")
        print(f"  source ทั้งหมด    {src/CHARS_PER_TOKEN:>10,.0f} โทเคน")
        print(f"  map ทั้งไฟล์      {len(text)/CHARS_PER_TOKEN:>10,.0f} โทเคน   ({len(text)/src*100:>5.1f}% ของ source)")
        print(f"  Quick Index      {idx/CHARS_PER_TOKEN:>10,.0f} โทเคน   ({idx/src*100:>5.1f}% ของ source)")
    else:
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
