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
import tree

MAX_ROUTES_LISTED = 60
MAX_ENV_LISTED = 50
SKIP_PARTS = (".git", "node_modules", "vendor", "__pycache__", ".venv", "dist", "build")

def _nested(root):
    """Nested checkouts, shared with mapper so both halves of the map agree on what this repo is.

    Without this the file index excluded a vendored checkout while the catalogues still listed its
    Kubernetes resources and Protobuf services — so the architecture map of a Streamlit app named a
    Namespace belonging to a logistics test corpus, and the two halves of the same document
    disagreed about what the repository contained.
    """
    from mapper import _nested_repo_dirs
    return _nested_repo_dirs(root)


def _outside(path, nested):
    return not nested or not any(parent.resolve() in nested for parent in path.parents)


# (framework, regex) — each must yield a path, and optionally a method in group 1.
# A route decorator says the path RELATIVE to whatever the router was mounted at, and the mount is
# declared somewhere else in the file. Reporting the relative half alone put `GET /{quote_id}` and
# `GET /rates` in the index for endpoints that actually live at /v1/quotes/{quote_id} and
# /v1/fx/rates -- a wrong path is worse than no path, because it is acted on and 404s.
ROUTER_PREFIX = re.compile(
    r"""(\w+)\s*=\s*(?:APIRouter|Blueprint)\s*\([^)]*?"""
    r"""(?:url_)?prefix\s*=\s*["']([^"']*)["']""", re.S)
# Spring puts the shared half on the class, and it is optional -- @RequestMapping(produces=...)
# with no path at all is ordinary, so the path must be a positional string to count.
SPRING_CLASS_PREFIX = re.compile(r"""@RequestMapping\s*\(\s*(?:value\s*=\s*)?["']([^"']+)["']""")

ROUTE_PATTERNS = [
    (re.compile(r"@(\w+)\.(get|post|put|patch|delete|head|options)\s*\(\s*[\"']([^\"']*)", re.I), "decorator"),
    (re.compile(r"@(?:app|bp|blueprint)\.route\s*\(\s*[\"']([^\"']+)[\"'](?:[^)]*methods\s*=\s*\[([^\]]*)\])?", re.I), "flask"),
    # (?<!@) or this also matches the Python decorator above: \b happens after the @, so every
    # FastAPI route was counted twice -- once with its router prefix and once without, and the
    # index carried both the real path and a wrong one for the same endpoint.
    (re.compile(r"(?<!@)\b(?:app|router)\.(get|post|put|patch|delete|all)\s*\(\s*[\"'`]([^\"'`]+)", re.I), "express"),
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


# A repository that keeps its specs together names them after the service, not after the format:
# contracts/openapi/routing-service.yaml is the normal layout and the exact-filename search found
# none of five such documents. Directories are matched first so this never reads every YAML in a
# repo full of Kubernetes manifests, then the head of the file confirms it really is a spec.
SPEC_DIRS = {"openapi", "swagger", "contracts", "contract", "spec", "specs", "apispec",
             "api-spec", "schemas", "api"}
SPEC_HEAD = re.compile(r"^\s*[\"']?(?:openapi|swagger)[\"']?\s*:", re.M)
# proto: `service FleetService {` then `rpc AssignVehicle(Request) returns (Response)`. Reported as
# routes because that is what they are -- an agent asking "what can I call on fleet" gets nothing
# from a REST-only list when half the surface is gRPC.
PROTO_SERVICE = re.compile(r"^\s*service\s+(\w+)\s*\{", re.M)
PROTO_RPC = re.compile(r"^\s*rpc\s+(\w+)\s*\(", re.M)


def _grpc(root):
    """(service, method) for every rpc declared in a .proto file."""
    _nest = _nested(root)
    for path in tree.by_suffix(root, ".proto"):
        if any(q in SKIP_PARTS for q in path.parts) or not _outside(path, _nest):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in PROTO_SERVICE.finditer(text):
            end = text.find("\n}", m.end())
            body = text[m.end(): end if end > 0 else len(text)]
            for r in PROTO_RPC.finditer(body):
                yield m.group(1), r.group(1)


def _grpc_source(root, service):
    for path in tree.by_suffix(root, ".proto"):
        try:
            if re.search(rf"^\s*service\s+{re.escape(service)}\s*\{{", 
                         path.read_text(encoding="utf-8", errors="replace"), re.M):
                return str(path.relative_to(root))
        except OSError:
            continue
    return ""


def _spec_files(root):
    """OpenAPI and Swagger documents, found by shape rather than by filename."""
    _nest = _nested(root)
    seen = set()
    for path in tree.by_suffix(root, ".yaml", ".yml", ".json"):
        if path in seen or any(q in SKIP_PARTS for q in path.parts) or not _outside(path, _nest):
            continue
        named = path.stem.lower() in ("openapi", "swagger")
        in_spec_dir = any(q.lower() in SPEC_DIRS for q in path.parts[:-1])
        if not (named or in_spec_dir):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not SPEC_HEAD.search(text[:4000]):
            continue
        seen.add(path)
        yield path, text


def _readable(root, patterns):
    # Deduplicated across patterns: ".env" matches the ".env", ".env.*" and "*.env" globs all three
    # times, which listed the same file repeatedly in the gitignore warning.
    _nest = _nested(root)
    seen = set()
    for pat in patterns:
        for path in tree.matching(root, pat):
            if path in seen or any(p in SKIP_PARTS for p in path.parts) or not _outside(path, _nest) \
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

    def add(method, path_, source, prefix=""):
        if prefix:
            path_ = "/" + prefix.strip("/") + ("/" + path_.strip("/") if path_.strip("/") else "")
        elif not path_.startswith(("/", "{", ":")) and "/" not in path_:
            return
        routes[(method.upper(), path_ or "/")] = source

    for f in files:
        if f["lang"] not in ("py", "js", "go", "rb", "java", "php"):
            continue
        path = root / f["path"]
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # Mount points declared in this file, by the variable the decorator will name.
        prefixes = {m.group(1): m.group(2) for m in ROUTER_PREFIX.finditer(text)}
        spring = SPRING_CLASS_PREFIX.search(text)
        class_prefix = spring.group(1) if spring else ""

        for pattern, kind in ROUTE_PATTERNS:
            for m in pattern.finditer(text):
                g = [x for x in m.groups() if x is not None]
                if kind == "flask":
                    methods = re.findall(r"[\"'](\w+)[\"']", g[1]) if len(g) > 1 else ["GET"]
                    for meth in methods or ["GET"]:
                        add(meth, g[0], f["path"])
                elif kind == "django":
                    add("ANY", "/" + g[0].lstrip("/"), f["path"])
                elif kind == "decorator" and len(g) >= 3:
                    obj, meth, route = g[0], g[1], g[2]
                    if obj.lower() not in ("app", "router", "api", "bp", "blueprint") \
                            and obj not in prefixes:
                        continue          # not a router; some other decorator that happens to fit
                    add(meth, route, f["path"], prefixes.get(obj, ""))
                elif kind == "spring" and len(g) >= 2:
                    add(g[0], g[1], f["path"], class_prefix)
                elif len(g) >= 2:
                    add(g[0], g[1], f["path"])

    for svc, method in _grpc(root):
        routes[("gRPC", f"{svc}/{method}")] = _grpc_source(root, svc)

    for path, text in _spec_files(root):
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
    """Rendered per protocol, and truncated per protocol.

    A flat alphabetical list cut at a fixed length loses whichever protocol sorts last -- and it
    did: twelve gRPC methods fell off the end behind sixty REST paths beginning with "/", so the
    index described a system with two API surfaces as though it had one. Dropping detail is fine;
    dropping a whole protocol without saying so is not.
    """
    if not routes:
        return ""
    grpc = [r for r in routes if r[0][0] == "gRPC"]
    http = [r for r in routes if r[0][0] != "gRPC"]
    out = ["## API surface", "", f"{len(routes)} route(s)."
           + (f" {len(http)} HTTP, {len(grpc)} gRPC." if grpc and http else "")]

    for label, group, cap in (("", http, MAX_ROUTES_LISTED),
                              ("gRPC", grpc, MAX_ROUTES_LISTED)):
        if not group:
            continue
        if label:
            out += ["", f"**{label}**"]
        if len(group) > cap:
            out.append(f"Showing {cap} of {len(group)}; grep the source files for the rest.")
        out.append("")
        for (method, path_), source in group[:cap]:
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
