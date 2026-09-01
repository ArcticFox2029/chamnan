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
import fnmatch
import json
import pathlib
import re
import subprocess
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


# 🐛 A path's components are tested RELATIVE to the repository root, never absolute. Testing the
# absolute path means one directory ABOVE the checkout named `vendor`, `node_modules`, `build`,
# `dist` or `.venv` skips every file in the repository -- and each of these renderers returns "" on
# an empty result, so whole sections simply vanish with no hedge. `assets.scan` already tested
# `rel.parts`, which is what made the asymmetry findable. Two harms beyond the missing sections:
# `mapper.scan` is unaffected, so the index and the catalogues then disagree about the same
# repository; and the unignored-`.env` warning goes silent, which is the false-calm direction.
def _rel_parts(path, root):
    """`path`'s components below `root`, or its own components when it is not below root."""
    try:
        return pathlib.Path(path).relative_to(root).parts
    except (ValueError, TypeError):
        return pathlib.Path(path).parts


def _outside(path, nested):
    return not nested or not any(parent.resolve() in nested for parent in path.parents)


# (framework, regex) — each must yield a path, and optionally a method in group 1.
# A route decorator says the path RELATIVE to whatever the router was mounted at, and the mount is
# declared somewhere else in the file. Reporting the relative half alone put `GET /{quote_id}` and
# `GET /rates` in the index for endpoints that actually live at /v1/quotes/{quote_id} and
# /v1/fx/rates -- a wrong path is worse than no path, because it is acted on and 404s.
# `[^)]` used to end the search at the first ")" in the argument list, so a perfectly ordinary
# `APIRouter(dependencies=[Depends(get_current_user)], prefix="/v1/quotes")` lost its prefix and
# put `GET /{quote_id}` in the index for an endpoint at /v1/quotes/{quote_id}. Bounded by length
# instead of by a paren -- a constructor call is not a language this can parse, and a bound keeps
# it from running away across a whole file looking for the word.
ROUTER_PREFIX = re.compile(
    r"""(\w+)\s*=\s*(?:APIRouter|Blueprint)\s*\((?:[^()]|\([^()]*\)){0,400}?"""
    r"""(?:url_)?prefix\s*=\s*["']([^"']*)["']""", re.S)
# Every Blueprint and APIRouter, prefix or not. Registering the VARIABLE is what lets a route
# decorated with it be found at all -- `orders_bp = Blueprint("orders", __name__)` followed by
# `@orders_bp.route(...)` produced no routes whatsoever, because the flask pattern below only
# knew the names app/bp/blueprint and this pattern only registered a router that declared a
# prefix. Naming a blueprint after its feature is the standard way to keep them apart across
# files, so this blanked whole applications.
ROUTER_ANY = re.compile(r"""(\w+)\s*=\s*(?:APIRouter|Blueprint)\s*\(""")
# Spring puts the shared half on the class, and it is optional -- @RequestMapping(produces=...)
# with no path at all is ordinary, so the path must be a positional string to count.
# 🐛 This used to be a bare search for the first @RequestMapping anywhere in the file, and the
# result was concatenated onto every @GetMapping in it. A controller whose health check uses the
# method-level form -- ordinary in any Spring codebase older than 4.3 -- had `/internal/health`
# taken as the class prefix, so `/v1/orders` was published as `/internal/health/v1/orders` and the
# real `/internal/health` was dropped, because ROUTE_PATTERNS never matched bare @RequestMapping at
# all. Every path in the section fabricated, and a real one missing. ROUTER_PREFIX's own comment
# says it: "a wrong path is worse than no path, because it is acted on and 404s."
#
# Anchored on what follows: only an annotation that reaches a `class` declaration through nothing
# but other annotations and whitespace is a class-level mapping.
SPRING_CLASS_PREFIX = re.compile(
    r"""@RequestMapping\s*\(\s*(?:value\s*=\s*)?["']([^"']+)["'][^\n]*\n"""
    r"""(?:[ \t]*(?:@[^\n]*|//[^\n]*)?\n)*"""
    r"""[ \t]*(?:public\s+|final\s+|abstract\s+)*class\b""")
# The method-level form, which is a route in its own right. `method = RequestMethod.GET` names the
# verb; without one Spring accepts every verb, which is what ANY says.
SPRING_METHOD_MAPPING = re.compile(
    r"""@RequestMapping\s*\(\s*(?:value\s*=\s*|path\s*=\s*)?["']([^"']+)["']([^)]*)\)"""
    r"""(?![^\n]*\n(?:[ \t]*(?:@[^\n]*|//[^\n]*)?\n)*[ \t]*(?:public\s+|final\s+|abstract\s+)*class\b)""")

ROUTE_PATTERNS = [
    (re.compile(r"@(\w+)\.(get|post|put|patch|delete|head|options)\s*\(\s*[\"']([^\"']*)", re.I), "decorator"),
    (re.compile(r"@(\w+)\.route\s*\(\s*[\"']([^\"']+)[\"'](?:[^)]*methods\s*=\s*\[([^\]]*)\])?", re.I), "flask"),
    # (?<!@) or this also matches the Python decorator above: \b happens after the @, so every
    # FastAPI route was counted twice -- once with its router prefix and once without, and the
    # index carried both the real path and a wrong one for the same endpoint.
    (re.compile(r"(?<!@)\b(?:app|router)\.(get|post|put|patch|delete|all)\s*\(\s*[\"'`]([^\"'`]+)", re.I), "express"),
    (re.compile(r"@(Get|Post|Put|Patch|Delete)Mapping\s*\(\s*[\"']([^\"']+)", re.I), "spring"),
    (SPRING_METHOD_MAPPING, "spring_any"),
    # Not `re.M`-anchored blindly: a `path(...)` whose second argument is `include(...)` is a MOUNT
    # POINT, not an endpoint. Indexing it as a route published `/api/v2/orders/` as something you
    # could call, and the included module's own paths were then indexed at the site root -- so of
    # three routes listed, two did not exist and `/` was claimed as a real endpoint. `include()` is
    # the only way Django composes URLconfs, so this was every Django project.
    (re.compile(r"^\s*(?:re_)?path\s*\(\s*[\"']([^\"']*)[\"']\s*,(?!\s*include\s*\()", re.M), "django"),
]
ENV_IN_CODE = re.compile(
    # The subscript form was missing while the call forms were matched, which is backwards: in
    # Python `os.environ["X"]` is how you say the variable is REQUIRED, and `.get()` is how you
    # say it is optional. The ones most worth listing were the ones not listed.
    r"""(?:os\.environ\[\s*["']([A-Z][A-Z0-9_]{2,})["']"""
    r"""|os\.environ(?:\.get)?\s*\(\s*["']([A-Z][A-Z0-9_]{2,})["']"""
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
        if any(q in SKIP_PARTS for q in _rel_parts(path, root)) or not _outside(path, _nest):
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


# `servers: [{url: https://api.example.com/v1}]` moves every path in the document under /v1, and
# the spec branch used to ignore it -- the same class of error as a lost APIRouter prefix, and
# the same consequence: a path in the index that 404s. Only the path component is taken; the host
# is not part of what this catalog describes. A templated server ({basePath}) is skipped, because
# a placeholder is not a prefix.
_SPEC_SERVER_JSON = re.compile(r'"servers"\s*:\s*\[\s*\{[^}]*?"url"\s*:\s*"([^"]+)"', re.S)
_SPEC_SERVER_YAML = re.compile(r"^servers:\s*\n\s*-\s+url:\s*[\"']?([^\s\"']+)", re.M)
_SPEC_BASEPATH = re.compile(r"^\s*[\"']?basePath[\"']?\s*:\s*[\"']?(/[^\s\"',]*)", re.M)


def _spec_base(text):
    """The path every route in this spec hangs under, or "" when there is none."""
    for pattern in (_SPEC_SERVER_JSON, _SPEC_SERVER_YAML):
        m = pattern.search(text)
        if m:
            url = m.group(1)
            if "{" in url:
                return ""
            tail = re.sub(r"^[a-zA-Z][\w+.-]*://[^/]*", "", url).rstrip("/")
            return tail if tail.startswith("/") else ""
    m = _SPEC_BASEPATH.search(text)          # OpenAPI 2 / Swagger
    return m.group(1).rstrip("/") if m else ""


def _spec_files(root):
    """OpenAPI and Swagger documents, found by shape rather than by filename."""
    _nest = _nested(root)
    seen = set()
    for path in tree.by_suffix(root, ".yaml", ".yml", ".json"):
        if path in seen or any(q in SKIP_PARTS for q in _rel_parts(path, root)) \
                or not _outside(path, _nest):
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
            if path in seen or any(p in SKIP_PARTS for p in _rel_parts(path, root)) \
                    or not _outside(path, _nest) \
                    or not path.is_file() or redact.is_blocked(path):
                continue
            seen.add(path)
            try:
                yield path, path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue


# --- routes -----------------------------------------------------------------------------------
# `path("api/v2/orders/", include("orders.urls"))` -- the prefix, and the module it mounts. The
# module is resolvable to a file: `orders.urls` is `orders/urls.py`, which is enough to give the
# included file's own paths the prefix they are actually served under.
DJANGO_INCLUDE = re.compile(
    r"""(?:re_)?path\s*\(\s*["']([^"']*)["']\s*,\s*include\s*\(\s*["']([\w.]+)["']""")


def _django_mounts(root, files):
    """{file path: url prefix} for every module mounted with include()."""
    by_module = {}
    for f in files:
        if f.get("lang") != "py":
            continue
        try:
            text = (root / f["path"]).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in DJANGO_INCLUDE.finditer(text):
            by_module[m.group(2)] = m.group(1)
    mounts = {}
    known = {f["path"] for f in files}
    for module, prefix in by_module.items():
        candidate = module.replace(".", "/") + ".py"
        for known_path in known:
            if known_path == candidate or known_path.endswith("/" + candidate):
                mounts[known_path] = prefix
    return mounts


def scan_routes(root, files):
    routes = {}
    mounts = _django_mounts(root, files)

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
        # Every router/blueprint variable in the file, prefix or not. A decorator is only trusted
        # when its object is one of these or one of the conventional names -- which is what keeps
        # an unrelated `@retry.route(...)` out of the API surface.
        routers = set(ROUTER_ANY.findall(text)) | set(prefixes)
        spring = SPRING_CLASS_PREFIX.search(text)
        class_prefix = spring.group(1) if spring else ""

        for pattern, kind in ROUTE_PATTERNS:
            for m in pattern.finditer(text):
                g = [x for x in m.groups() if x is not None]
                if kind == "flask":
                    obj, route = g[0], g[1]
                    if obj.lower() not in ("app", "bp", "blueprint") and obj not in routers:
                        continue
                    methods = re.findall(r"[\"'](\w+)[\"']", g[2]) if len(g) > 2 else ["GET"]
                    for meth in methods or ["GET"]:
                        add(meth, route, f["path"], prefixes.get(obj, ""))
                elif kind == "django":
                    add("ANY", "/" + g[0].lstrip("/"), f["path"], mounts.get(f["path"], ""))
                elif kind == "decorator" and len(g) >= 3:
                    obj, meth, route = g[0], g[1], g[2]
                    if obj.lower() not in ("app", "router", "api", "bp", "blueprint") \
                            and obj not in routers:
                        continue          # not a router; some other decorator that happens to fit
                    add(meth, route, f["path"], prefixes.get(obj, ""))
                elif kind == "spring" and len(g) >= 2:
                    add(g[0], g[1], f["path"], class_prefix)
                elif kind == "spring_any" and len(g) >= 1:
                    _verbs = re.findall(r"RequestMethod\.(\w+)", g[1] if len(g) > 1 else "")
                    for _v in (_verbs or ["ANY"]):
                        add(_v, g[0], f["path"], class_prefix)
                elif len(g) >= 2:
                    add(g[0], g[1], f["path"])

    for svc, method in _grpc(root):
        routes[("gRPC", f"{svc}/{method}")] = _grpc_source(root, svc)

    for path, text in _spec_files(root):
        rel = str(path.relative_to(root))
        base = _spec_base(text)
        if path.suffix == ".json":
            try:
                doc = json.loads(text)
                for p, ops in (doc.get("paths") or {}).items():
                    for meth in ops:
                        if meth.lower() in ("get", "post", "put", "patch", "delete"):
                            add(meth, p, rel, base)
            except (json.JSONDecodeError, AttributeError):
                continue
        else:
            # No yaml in the stdlib; the path keys are indented two spaces under `paths:` and that
            # is all this needs. Anything more would mean shipping a parser for one section.
            # A spec that splits its paths into other files (`paths:\n  $ref: ./paths/index.yaml`)
            # has nothing here to read, and reporting zero routes for it looked identical to a
            # service with no API. Following the ref needs a YAML parser and a resolver, which is
            # not what this is; saying the spec is split is the honest answer.
            if re.search(r"^paths:\s*\n\s+\$ref:", text, re.M):
                add("ANY", "(paths are $ref'd into other files — not resolved)", rel)
                continue
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
                        add("ANY", m.group(1), rel, base)
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


# 🐛 [fixed 2026-08-29] This used to be `".env" in (root/".gitignore").read_text()`, which is wrong
# in both directions and was caught by its own output: it warned that a repo's ai-dev/.env was
# unprotected when a .gitignore inside ai-dev/ had been ignoring it all along.
#
#   false alarm    only the ROOT .gitignore was read, so every nested one was invisible
#   false calm     a substring test says "ignored" for `.envrc`, for `# do not commit .env`,
#                  and for `!.env` — which means the opposite. That direction is the dangerous
#                  one: a genuinely exposed credentials file reported as safe.
#
# git already knows the answer, including nested files, negation, ~/.config/git/ignore and
# .git/info/exclude. Ask it, and fall back to reading the files only when it cannot answer.
def _is_ignored(root, path):
    """Is `path` ignored by git? Authoritative when git can answer, best-effort when it cannot."""
    try:
        r = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", str(path)],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=10)
        if r.returncode in (0, 1):
            return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        pass
    # No git, or not a repository. Walk the .gitignore files from the file's own directory upward,
    # nearest first, and let the last matching rule win the way git does.
    return _ignored_by_files(Path(root), Path(path))


def _ignored_by_files(root, path):
    verdict = False
    chain = []
    d = path.parent
    while True:
        chain.append(d)
        if d == root or d.parent == d:
            break
        d = d.parent
    for d in reversed(chain):                      # outermost first, so nearer rules override
        gi = d / ".gitignore"
        if not gi.is_file():
            continue
        try:
            rel = path.relative_to(d).as_posix()
        except ValueError:
            continue
        for line in gi.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            negated = line.startswith("!")
            pat = line[1:] if negated else line
            pat = pat.rstrip("/")
            if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(path.name, pat):
                verdict = not negated
    return verdict


# --- configuration ----------------------------------------------------------------------------
def scan_env(root, files):
    """Variable NAMES. Values are never captured — see this module's docstring."""
    names, sources, unsafe = {}, {}, []
    # How many distinct places each name is referenced. The list is capped, and it used to be cut
    # alphabetically -- so on a repo with 200 variables the reader saw everything up to about `D`
    # and nothing after, under a line that said only "Showing 50 of 200". An arbitrary slice
    # presented without saying it is arbitrary reads as a ranking, which is worse than a short
    # list. This is a real measurement and it is what the cut is made on.
    refs = {}
    for path, text in _readable(root, (".env", ".env.*", "*.env", "env.example")):
        rel = str(path.relative_to(root))
        for m in ENV_FILE_KEY.finditer(text):
            names.setdefault(m.group(1), rel)
            refs.setdefault(m.group(1), set()).add(rel)
        if path.name == ".env":
            if not _is_ignored(root, path):
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
            refs.setdefault(name, set()).add(f["path"])
    # Most-referenced first, then alphabetical so the order is stable between runs.
    return sorted(names.items(), key=lambda kv: (-len(refs.get(kv[0], ())), kv[0])), unsafe


def render_env(pairs, unsafe):
    if not pairs:
        return ""
    out = ["## Configuration", "",
           f"{len(pairs)} environment variable(s) this repo reads. **Names only — no values are "
           f"ever recorded here.**"]
    if len(pairs) > MAX_ENV_LISTED:
        out.append(f"Showing the {MAX_ENV_LISTED} referenced in the most places, of {len(pairs)}. "
                   f"Grep the repository for the rest.")
    out.append("")
    out.append(", ".join(f"`{n}`" for n, _ in pairs[:MAX_ENV_LISTED]))
    if unsafe:
        out.append("")
        out.append(f"> ⚠️ `{', '.join(unsafe)}` is not matched by .gitignore. That file usually "
                   f"holds live credentials; committing it publishes them.")
    out.append("")
    return "\n".join(out)
