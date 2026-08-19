"""Two more index sections, built the same way as the data model: routes, and configuration.

Both follow the rules the whole map follows — one file, sections only when the repo has that thing,
and a bounded size. A repo of plain scripts sees neither of these sections exist.

Routes: an OpenAPI document for a real service runs to thousands of tokens of parameter and response
schemas, to answer a question that is usually "does an endpoint for X exist and where is it
handled". Method, path and handler answer that.

Configuration: VARIABLE NAMES ONLY, NEVER VALUES. This reads .env files, which hold live
credentials. A tool that indexes a codebase must not be the thing that copies a secret into a file
the user then commits, so values are discarded at parse time rather than filtered later — there is
no code path here that can carry one into the output.
"""
import json
import re
from pathlib import Path

import redact

MAX_ROUTES_LISTED = 60
MAX_ENV_LISTED = 50
SKIP_PARTS = (".git", "node_modules", "vendor", "__pycache__", ".venv", "dist", "build")

# (framework, regex) — each must yield a path, and optionally a method in group 1.
ROUTE_PATTERNS = [
    (re.compile(r"@(?:app|router|api|bp|blueprint)\.(get|post|put|patch|delete|head|options)\s*\(\s*[\"']([^\"']+)", re.I), "decorator"),
    (re.compile(r"@(?:app|bp|blueprint)\.route\s*\(\s*[\"']([^\"']+)[\"'](?:[^)]*methods\s*=\s*\[([^\]]*)\])?", re.I), "flask"),
    (re.compile(r"\b(?:app|router)\.(get|post|put|patch|delete|all)\s*\(\s*[\"'`]([^\"'`]+)", re.I), "express"),
    (re.compile(r"@(Get|Post|Put|Patch|Delete)Mapping\s*\(\s*[\"']([^\"']+)", re.I), "spring"),
    (re.compile(r"^\s*path\s*\(\s*[\"']([^\"']*)[\"']", re.M), "django"),
]
ENV_IN_CODE = re.compile(
    r"""(?:os\.environ(?:\.get)?\s*\(\s*["']([A-Z][A-Z0-9_]{2,})["']"""
    r"""|os\.getenv\s*\(\s*["']([A-Z][A-Z0-9_]{2,})["']"""
    r"""|process\.env\.([A-Z][A-Z0-9_]{2,})"""
    r"""|process\.env\[\s*["']([A-Z][A-Z0-9_]{2,})["']"""
    r"""|ENV\[\s*["']([A-Z][A-Z0-9_]{2,})["'])""")
ENV_FILE_KEY = re.compile(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]{2,})\s*=", re.M)


def _readable(root, patterns):
    # Deduplicated across patterns: ".env" matches the ".env", ".env.*" and "*.env" globs all three
    # times, which listed the same file repeatedly in the gitignore warning.
    seen = set()
    for pat in patterns:
        for path in sorted(root.rglob(pat)):
            if path in seen or any(p in SKIP_PARTS for p in path.parts) \
                    or not path.is_file() or redact.is_blocked(path):
                continue
            seen.add(path)
            try:
                yield path, path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue


# --- routes -----------------------------------------------------------------------------------
def scan_routes(root, files):
    routes = {}

    def add(method, path_, source):
        if not path_.startswith(("/", "{", ":")) and "/" not in path_:
            return
        routes[(method.upper(), path_)] = source

    for f in files:
        if f["lang"] not in ("py", "js", "go", "rb", "java", "php"):
            continue
        path = root / f["path"]
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for pattern, kind in ROUTE_PATTERNS:
            for m in pattern.finditer(text):
                g = [x for x in m.groups() if x is not None]
                if kind == "flask":
                    methods = re.findall(r"[\"'](\w+)[\"']", g[1]) if len(g) > 1 else ["GET"]
                    for meth in methods or ["GET"]:
                        add(meth, g[0], f["path"])
                elif kind == "django":
                    add("ANY", "/" + g[0].lstrip("/"), f["path"])
                elif len(g) >= 2:
                    add(g[0], g[1], f["path"])

    for path, text in _readable(root, ("openapi.json", "openapi.yaml", "openapi.yml",
                                       "swagger.json", "swagger.yaml", "swagger.yml")):
        rel = str(path.relative_to(root))
        if path.suffix == ".json":
            try:
                for p, ops in (json.loads(text).get("paths") or {}).items():
                    for meth in ops:
                        if meth.lower() in ("get", "post", "put", "patch", "delete"):
                            add(meth, p, rel)
            except (json.JSONDecodeError, AttributeError):
                continue
        else:
            # No yaml in the stdlib; the path keys are indented two spaces under `paths:` and that
            # is all this needs. Anything more would mean shipping a parser for one section.
            in_paths = False
            for line in text.splitlines():
                if re.match(r"^paths:\s*$", line):
                    in_paths = True
                    continue
                if in_paths:
                    if line and not line[0].isspace():
                        break
                    m = re.match(r"^\s{1,4}(/[^\s:]*):\s*$", line)
                    if m:
                        add("ANY", m.group(1), rel)
    return sorted(routes.items(), key=lambda kv: (kv[0][1], kv[0][0]))


def render_routes(routes):
    if not routes:
        return ""
    out = ["## API surface", "", f"{len(routes)} route(s)."]
    if len(routes) > MAX_ROUTES_LISTED:
        out.append(f"Showing {MAX_ROUTES_LISTED}; grep the source files for the rest.")
    out.append("")
    for (method, path_), source in routes[:MAX_ROUTES_LISTED]:
        out.append(f"- `{method:<6} {path_}`  _({source})_")
    out.append("")
    return "\n".join(out)


# --- configuration ----------------------------------------------------------------------------
def scan_env(root, files):
    """Variable NAMES. Values are never captured — see this module's docstring."""
    names, sources, unsafe = {}, {}, []
    for path, text in _readable(root, (".env", ".env.*", "*.env", "env.example")):
        rel = str(path.relative_to(root))
        for m in ENV_FILE_KEY.finditer(text):
            names.setdefault(m.group(1), rel)
        if path.name == ".env":
            gi = root / ".gitignore"
            ignored = gi.is_file() and ".env" in gi.read_text(encoding="utf-8", errors="replace")
            if not ignored:
                unsafe.append(rel)
    for f in files:
        try:
            text = (root / f["path"]).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in ENV_IN_CODE.finditer(text):
            name = next(g for g in m.groups() if g)
            names.setdefault(name, f["path"])
            sources.setdefault(name, f["path"])
    return sorted(names.items()), unsafe


def render_env(pairs, unsafe):
    if not pairs:
        return ""
    out = ["## Configuration", "",
           f"{len(pairs)} environment variable(s) this repo reads. **Names only — no values are "
           f"ever recorded here.**"]
    if len(pairs) > MAX_ENV_LISTED:
        out.append(f"Showing {MAX_ENV_LISTED} of {len(pairs)}.")
    out.append("")
    out.append(", ".join(f"`{n}`" for n, _ in pairs[:MAX_ENV_LISTED]))
    if unsafe:
        out.append("")
        out.append(f"> ⚠️ `{', '.join(unsafe)}` is not matched by .gitignore. That file usually "
                   f"holds live credentials; committing it publishes them.")
    out.append("")
    return "\n".join(out)
