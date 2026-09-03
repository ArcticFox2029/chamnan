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

import mdblock
import impact  # for is_test — see the guard in the file loops below

import redact
import tokens
import tree

# PROTOTYPE (R8 agent A, .../scratchpad/R8A_work/R8_agentA.md): count caps and mdblock.as_quoted's
# per-entry length cap bound quantity and size separately, and nothing bounds their product — 32-60
# ordinary deep REST paths on a real repo (measured: go-gitea/gitea) cost more tokens than the
# entire 3,000-token index budget on their own, while the count cap said 60 was fine. A per-section
# TOKEN budget replaces the count cap as the primary limit; the count cap stays as a floor against a
# wall of very short entries. See R8_agentA.md for the measurements this is based on.
MAX_ROUTES_LISTED = 60
MAX_ENV_LISTED = 50
# 🐛 The prototype used fixed constants, and the agent that wrote it said so. A user who raises
# `index_token_budget` to 6,000 has asked for a bigger index and would still get 1,200 tokens of
# routes; one who lowers it to 1,500 would get a routes section costing most of their whole budget.
# Fractions of the configured budget instead — the constants below are what those fractions come to
# at the 3,000-token default, so the measured behaviour is unchanged where it was measured.
#
# Two fifths and two fifteenths. Routes are the section people go looking for; configuration is a
# list of names. Together they leave more than half the budget for the Quick Index, which is the
# section every other one is a supplement to.
ROUTES_BUDGET_SHARE = 0.40
ENV_BUDGET_SHARE = 2 / 15


def _section_budget(share, configured=None):
    """A section's token budget as a share of the index budget the user actually configured."""
    if configured is None:
        try:
            import workspace as _ws
            configured = _ws.load_config().get("index_token_budget", 3000)
        except Exception:
            configured = 3000
    return max(int(configured * share), 120)
SKIP_PARTS = (".git", "node_modules", "vendor", "__pycache__", ".venv", "dist", "build")


def _fill_by_budget(entries, render_one, token_budget, count_cap):
    """Keep `entries` in order until either the token budget or the count cap is spent.

    Returns (kept_render_lines, kept_count). At least one entry is always kept when the list is
    non-empty, even if it alone exceeds the budget — a budget of zero rows is not a summary, and
    `mdblock.as_quoted`'s own per-entry cap already bounds how bad the single worst case can be.
    """
    lines = []
    spent = 0.0
    for e in entries:
        if len(lines) >= count_cap:
            break
        line = render_one(e)
        cost = tokens.estimate(line)
        if lines and spent + cost > token_budget:
            break
        lines.append(line)
        spent += cost
    return lines, len(lines)

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

# Literals each ROUTE_PATTERNS entry cannot match without, used as a pre-filter. Read off the
# patterns above, not invented: changing a pattern without changing its entry here would make the
# gate skip a file the pattern would have matched, so the two must be edited together.
_ROUTE_NEEDS = {
    "flask": (".route",),
    "express": ("app.", "router."),
    "spring": ("Mapping",),
    "spring_any": ("RequestMapping",),
    "django": ("path(",),
}
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
    r"""|ENV\[\s*["']([A-Z][A-Z0-9_]{2,})["']"""
    # Go and Rust. Measured on real clones before being added, and both numbers reported, because
    # this is the MISSING direction and a pattern that over-matches would turn it into the
    # INVENTED one, which is strictly worse: Go `os.Getenv`/`os.LookupEnv` found 58 true variables
    # and 0 false across four repositories (Caddy, node_exporter, alertmanager,
    # microservices-demo); Rust `env::var`/`env::var_os` found 12 true and 0 false. A real
    # polyglot service repository had 12 Go variables in one service alone, all invisible before.
    #
    # NOT added, and each for its own reason. Java/Kotlin `System.getenv` is the right shape but
    # turned up only two or three call sites on real repositories — too thin to claim. C#
    # `Environment.GetEnvironmentVariable` is correct in principle and had ZERO literal-argument
    # call sites in two real C# repositories, so it is a hypothesis rather than a measurement. And
    # C#'s `Configuration["X"]` scored 14 of 14 true positives and is still refused: `IConfiguration`
    # merges environment variables with JSON, command-line arguments and Key Vault, so the call
    # shape cannot structurally promise an environment read. Clean numbers on one sample are not
    # the same as a rule that holds.
    r"""|os\.(?:Getenv|LookupEnv)\s*\(\s*["`]([A-Z][A-Z0-9_]{2,})["`]"""
    r"""|env::var(?:_os)?\s*\(\s*["]([A-Z][A-Z0-9_]{2,})["])""")
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
                return str(path.relative_to(root).as_posix())
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
        # 🐛 A test fixture is not an API, a schema or a configuration. Measured by running
        # chamnan against repositories it was not tuned for: gin's entire "API surface" was 86
        # routes, every one of them from eight `*_test.go` files — it is a router LIBRARY, so its
        # only routes are the ones its tests build. `bat` produced 19 tables from a syntax
        # highlighter's SQL fixture, and 31 of its 32 environment variables from the same corpus,
        # including a false "this file leaks live credentials" alarm on a fixture that holds none.
        #
        # These sections render inside the auto-injected Quick Index, so an agent reads them as
        # fact and cannot check them. An invented endpoint is worse than a missing one.
        #
        # `impact.is_test` is the signal the repository already trusts for its "tested by"
        # annotations — nine markers covering directories, filename conventions and the .NET
        # sibling-project shape. Neither this module nor schema.py imported it, so nothing new is
        # needed and there is no circular import: impact does not import either of them.
        if impact.is_test(f["path"]):
            continue
        if f.get("lang") != "py":
            continue
        # `mapper._scan()` already read and decoded this file to build `f` -- reuse it rather than
        # opening the file again. Falls back to a fresh read for a `files` list built without that
        # field (a caller that assembled its own, a future test fixture).
        text = f.get("_source")
        if text is None:
            try:
                text = (root / f["path"]).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
        if "include" not in text:
            continue          # DJANGO_INCLUDE requires `include(`; 86.6% of this loop was this file
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
        # 🐛 A test fixture is not an API, a schema or a configuration. Measured by running
        # chamnan against repositories it was not tuned for: gin's entire "API surface" was 86
        # routes, every one of them from eight `*_test.go` files — it is a router LIBRARY, so its
        # only routes are the ones its tests build. `bat` produced 19 tables from a syntax
        # highlighter's SQL fixture, and 31 of its 32 environment variables from the same corpus,
        # including a false "this file leaks live credentials" alarm on a fixture that holds none.
        #
        # These sections render inside the auto-injected Quick Index, so an agent reads them as
        # fact and cannot check them. An invented endpoint is worse than a missing one.
        #
        # `impact.is_test` is the signal the repository already trusts for its "tested by"
        # annotations — nine markers covering directories, filename conventions and the .NET
        # sibling-project shape. Neither this module nor schema.py imported it, so nothing new is
        # needed and there is no circular import: impact does not import either of them.
        if impact.is_test(f["path"]):
            continue
        if f["lang"] not in ("py", "js", "go", "rb", "java", "php"):
            continue
        path = root / f["path"]
        # Same reuse as _django_mounts above -- `mapper._scan()` already holds this text.
        text = f.get("_source")
        if text is None:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
        # `APIRouter` and `Blueprint` are FastAPI and Flask, so these two patterns can only ever
        # match Python — and both are unanchored scans with a 400-character bounded body, which is
        # the expensive shape. Running them over every JavaScript and Go file in a repository is
        # work whose result is known in advance: measured on a four-project tree they cost 1,503 ms
        # of ~1,900 ms of total findall time, roughly half of it spent inside large `.js` files that
        # cannot contain either name. Gated to Python, checked for misses across three repositories
        # with route-carrying files in six languages: none.
        # 🐛 These two were gated by LANGUAGE while the sibling loop below got a literal
        # pre-filter, in the same function, added the same day. Language is much too coarse here:
        # on the real repository 188 `.py` files reach this line and exactly 2 contain either name.
        # `APIRouter` and `Blueprint` are the literals the patterns cannot match without.
        py = f["lang"] == "py" and ("APIRouter" in text or "Blueprint" in text)
        # Mount points declared in this file, by the variable the decorator will name.
        prefixes = {m.group(1): m.group(2) for m in ROUTER_PREFIX.finditer(text)} if py else {}
        # Every router/blueprint variable in the file, prefix or not. A decorator is only trusted
        # when its object is one of these or one of the conventional names -- which is what keeps
        # an unrelated `@retry.route(...)` out of the API surface.
        routers = (set(ROUTER_ANY.findall(text)) if py else set()) | set(prefixes)
        # Same argument, one language over: @RequestMapping on a class is Spring, so Java only.
        spring = SPRING_CLASS_PREFIX.search(text) if f["lang"] == "java" else None
        class_prefix = spring.group(1) if spring else ""

        for pattern, kind in ROUTE_PATTERNS:
            # A literal the pattern cannot match without. `str.find` over a few hundred KB is a
            # memchr; an unanchored alternation over the same bytes is not, and most files cannot
            # match most patterns. Measured across two independent verifications on this tree:
            # render −39.7% and −41.3%, wall clock −21.5% and −24.5%, with the route set proven
            # identical on every corpus checked.
            #
            # Each literal is taken from the pattern's OWN required syntax rather than guessed:
            # flask needs `.route`, express needs `app.` or `router.`, Spring needs `Mapping`,
            # Django needs `path(`. A pattern with no single required literal is not gated.
            need = _ROUTE_NEEDS.get(kind)
            if need and not any(lit in text for lit in need):
                continue
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

    # _grpc_source(root, svc) re-walks and re-reads every .proto file to find which one declares
    # `svc` -- and _grpc(root) yields one (svc, method) pair per RPC, so a service with several
    # methods called it that many times for an answer that cannot change within this loop: the
    # service a given name belongs to is fixed by the .proto tree scan_routes() was called with.
    # Memoized per svc, not across calls -- this cache dies with scan_routes()'s call frame.
    _grpc_src_cache = {}
    for svc, method in _grpc(root):
        if svc not in _grpc_src_cache:
            _grpc_src_cache[svc] = _grpc_source(root, svc)
        routes[("gRPC", f"{svc}/{method}")] = _grpc_src_cache[svc]

    for path, text in _spec_files(root):
        rel = str(path.relative_to(root).as_posix())
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

    def _render_one(route):
        (method, path_), source = route
        # 🐛 Written straight into MAP.md, which the pre-commit hook commits and the hook
        # injects into every session — from a string the repository chose. Several route
        # patterns capture with `[^"']*`, and that class INCLUDES a newline, so a quoted path
        # containing one carried the rest of the file's text into the index as markdown.
        # Reproduced in ordinary, valid JavaScript — a template literal spanning two lines —
        # which put a real `## Injected heading` and a paragraph of an attacker's prose above
        # `## Full Detail`, where an agent reads it as something chamnan published.
        #
        # `mdblock.as_quoted` is the helper this codebase already uses for exactly this, on
        # Quick Index filenames and milestone titles: it folds newlines away, neutralises the
        # backticks that would close the span it sits in, and bounds the length. These four
        # modules extract repository substrings and none of them imported it.
        return (f"- `{mdblock.as_quoted(method, 12):<6} {mdblock.as_quoted(path_, 200)}`"
                f"  _({mdblock.as_quoted(source, 120)})_")

    for label, group, cap in (("", http, MAX_ROUTES_LISTED),
                              ("gRPC", grpc, MAX_ROUTES_LISTED)):
        if not group:
            continue
        if label:
            out += ["", f"**{label}**"]
        # Token-budgeted, not count-capped: `cap` alone used to decide what was "shown", and on a
        # repository whose routes run long (deep REST paths, verbose source annotations) 60 of them
        # cost more tokens than the WHOLE index budget by themselves — count and size are bounded
        # separately and nothing bounded their product. Filling by token cost until the section's
        # own sub-budget is spent makes the count that gets shown depend on how big the entries
        # actually are, the way the number in "Showing K of N" always claimed it did.
        lines, kept = _fill_by_budget(group, _render_one, _section_budget(ROUTES_BUDGET_SHARE), cap)
        if len(group) > kept:
            out.append(f"Showing {kept} of {len(group)}; grep the source files for the rest.")
        out.append("")
        out += lines
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
        rel = str(path.relative_to(root).as_posix())
        for m in ENV_FILE_KEY.finditer(text):
            names.setdefault(m.group(1), rel)
            refs.setdefault(m.group(1), set()).add(rel)
        if path.name == ".env":
            if not _is_ignored(root, path):
                unsafe.append(rel)
    for f in files:
        # 🐛 A test fixture is not an API, a schema or a configuration. Measured by running
        # chamnan against repositories it was not tuned for: gin's entire "API surface" was 86
        # routes, every one of them from eight `*_test.go` files — it is a router LIBRARY, so its
        # only routes are the ones its tests build. `bat` produced 19 tables from a syntax
        # highlighter's SQL fixture, and 31 of its 32 environment variables from the same corpus,
        # including a false "this file leaks live credentials" alarm on a fixture that holds none.
        #
        # These sections render inside the auto-injected Quick Index, so an agent reads them as
        # fact and cannot check them. An invented endpoint is worse than a missing one.
        #
        # `impact.is_test` is the signal the repository already trusts for its "tested by"
        # annotations — nine markers covering directories, filename conventions and the .NET
        # sibling-project shape. Neither this module nor schema.py imported it, so nothing new is
        # needed and there is no circular import: impact does not import either of them.
        if impact.is_test(f["path"]):
            continue
        # Same reuse as _django_mounts/scan_routes above -- every file in `files` was already read
        # once by mapper._scan(). This loop has no language gate at all (env vars can be referenced
        # from any source file), so before this it was the least selective of the three re-reads.
        text = f.get("_source")
        if text is None:
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
    # Token-budgeted, not count-capped — see _section_budget(ROUTES_BUDGET_SHARE)'s comment in render_routes for why:
    # the same product-of-count-and-size gap applies here, just less often, because a variable NAME
    # is short enough that MAX_ENV_LISTED rarely dominates on its own the way route paths do.
    names, kept = _fill_by_budget(pairs, lambda pair: f"`{mdblock.as_quoted(pair[0], 80)}`",
                                  _section_budget(ENV_BUDGET_SHARE), MAX_ENV_LISTED)
    if len(pairs) > kept:
        out.append(f"Showing the {kept} referenced in the most places, of {len(pairs)}. "
                   f"Grep the repository for the rest.")
    out.append("")
    out.append(", ".join(names))
    # 🐛 The list read as complete and is not. It is built from call shapes chamnan knows, and a
    # language whose shape is missing contributes nothing with no sign that anything is absent —
    # measured on a real polyglot service repository, twelve Go variables in one service were
    # invisible while the section printed a short list and said nothing.
    #
    # A numeric "showing N of M" is NOT available and claiming one would be the same mistake in a
    # new place: chamnan cannot know M without a reader for every language, and some real idioms
    # never appear in code at all — Spring's `${VAR}` in a YAML file is a live example. What it can
    # state is its own boundary, which is checkable and does not pretend to a denominator.
    out.append("")
    out.append("_Found by matching `os.environ`/`os.getenv`, `process.env`, `ENV[…]`, Go's "
               "`os.Getenv`/`os.LookupEnv`, and Rust's `env::var`. A variable read some other way "
               "— a config framework, a YAML placeholder, a language with no pattern here — is not "
               "in this list and is not counted as absent either._")
    if unsafe:
        out.append("")
        # Only the LEAF has to be `.env`; every parent directory in the path is a name somebody
        # chose, and it needs no code at all — a `mkdir` is enough. Reproduced breaking out of this
        # blockquote and adding a second, fabricated alert line beneath it.
        out.append(f"> ⚠️ `{mdblock.as_quoted(', '.join(unsafe), 200)}` is not matched by "
                   f".gitignore. That file usually holds live credentials; committing it "
                   f"publishes them.")
    out.append("")
    return "\n".join(out)
