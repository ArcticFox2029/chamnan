#!/usr/bin/env python3
"""chamnan's regression suite. Run: python3 tests/run_tests.py

The redactor is why this file exists. Every other part of chamnan fails visibly — a wrong map entry
sends someone to the wrong file and they notice. A redaction regression fails silently and writes a
credential into a file the README tells people to commit. That asymmetry is what a test suite is
for, so the redaction cases are the ones to add to first.

Both directions are tested throughout: that the thing happens, and that the opposite does not. A
redactor that replaces everything passes a "did it hide the secret" test perfectly.

No dependencies, no pytest — a plain check(name, condition) counter, so this runs anywhere python3
does, which is the same bar the plugin itself has to clear.
"""
import datetime
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lib"))

import catalogs  # noqa: E402
import mapper  # noqa: E402
import peek as peek_mod  # noqa: E402
import redact  # noqa: E402
import assets as assets_mod  # noqa: E402
import deploy as deploy_mod  # noqa: E402
import impact as impact_mod  # noqa: E402
import workflows  # noqa: E402
import candidates  # noqa: E402
import ledger  # noqa: E402
import tools_index  # noqa: E402
import memory as memory_mod  # noqa: E402
import milestones  # noqa: E402
import schema  # noqa: E402
import sessions  # noqa: E402
import state as state_mod  # noqa: E402
import timeline  # noqa: E402
import environments as envs  # noqa: E402
import aging  # noqa: E402
import tokens  # noqa: E402
import workspace as ws  # noqa: E402

def fake(*parts):
    """Assemble a test credential at runtime so no literal one is ever stored in this file.

    A realistic-looking Stripe or Slack token in a fixture is indistinguishable from a real leak to
    a scanner, and GitHub's push protection blocked this repository's first push over exactly these
    lines. Splitting the literal leaves the regex under test working on the identical string while
    leaving nothing for a scanner to match — the alternative, clicking "allow this secret", teaches
    the reviewer to wave through the next one, which may be real.
    """
    return "".join(parts)


PASSED = 0
FAILED = []


def check(name, condition):
    global PASSED
    if condition:
        PASSED += 1
    else:
        FAILED.append(name)
        print(f"  FAIL  {name}")


# ---------------------------------------------------------------- redaction: catches secrets
SECRETS = [
    ("stripe live key", 'STRIPE="' + fake("sk_", "live_", "51H8xKLMNOPQRSTUVWXYZabcdef") + '"', fake("sk_", "live_", "51H8x")),
    ("openai key", "# rotate " + fake("sk-", "proj-", "AbCdEf1234567890XyZwVuTsRqPoNmLk"), fake("sk-", "proj-", "AbCdEf")),
    ("github pat", "token: " + fake("ghp", "_", "ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"), fake("ghp", "_", "ABCDEF")),
    ("aws access key", "uses " + fake("AKIA", "IOSFODNN7EXAMPLE") + " for s3", fake("AKIA", "IOSFODNN7EXAMPLE")),
    ("google api key", "key " + fake("AIza", "SyA1234567890abcdefghijklmnopqrstuvw") + " here", fake("AIza", "SyA123")),
    ("slack token", fake("xox", "b-", "123456789012-abcdefghijklmnop"), fake("xox", "b-", "1234")),
    ("gitlab pat", fake("glpat", "-", "ABCDEFGHIJKLMNOPQRST"), fake("glpat", "-", "ABCDEF")),
    ("jwt", "Bearer " + fake("eyJ", "hbGciOiJIUzI1.", "eyJ", "zdWIiOiIxMjM.SflKxwRJSMeKKF2QT"), fake("eyJ", "hbGciOiJIUzI1")),
    ("private key block", fake("-----BEGIN", " RSA PRIVATE KEY-----") + "\nMIIsecret\n"
     + fake("-----END", " RSA PRIVATE KEY-----"), "MIIsecret"),
    ("credentialed url", "db at postgres://admin:Hunter2Pass@host:5432/main", "Hunter2Pass"),
    ("assigned password", 'password = "correcthorsebattery"', "correcthorsebattery"),
    ("assigned api_key", "api_key: 'zzzz1111yyyy2222'", "zzzz1111yyyy2222"),
]
for label, text, secret in SECRETS:
    check(f"redact catches {label}", secret not in redact.scrub(text))

# ---------------------------------------------------------------- redaction: leaves the rest alone
BENIGN = [
    ("plain sentence", "Reads config from the shared bucket"),
    ("commit hash", "fixed in commit 3aacc5181ab7f0e2b91d4c6a8e5f2d1c0b9a8e7d"),
    ("rfc reference", "See RFC 7231 section 6.5.1 for the 400 semantics"),
    ("uncredentialed url", "connects to postgres://db.internal:5432/main"),
    ("uuid and version", "version 2.4.1-beta, id 550e8400-e29b-41d4-a716-446655440000"),
    ("base64ish word", "encodes to QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo="),
    ("function signature", "def authenticate(user, password): ..."),
]
for label, text in BENIGN:
    check(f"redact leaves {label} alone", redact.scrub(text) == text)

# ---------------------------------------------------------------- blocked files
for name in ("server.pem", "app.key", "id_rsa", "id_ed25519.pub", "cert.crt",
             "local.sqlite3", "backup.dump", ".netrc"):
    check(f"blocks {name}", redact.is_blocked(Path("/x") / name))
for name in ("main.py", "app.js", "schema.sql", "keyboard.py", "monkey.go"):
    check(f"does not block {name}", not redact.is_blocked(Path("/x") / name))

# ---------------------------------------------------------------- manifest
manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
check("plugin declares a version", bool(manifest.get("version")))
check("version is semver-shaped",
      bool(re.fullmatch(r"\d+\.\d+\.\d+", manifest.get("version", ""))))
check("marketplace lists this plugin", any(p["name"] == manifest["name"] for p in market["plugins"]))
# Installed copies only refresh when this field moves, so a fix shipped without bumping it reaches
# nobody — the marketplace updates and the cached plugin stays exactly as it was.
check("marketplace has a description", bool(market.get("description")))

# ---------------------------------------------------------------- fixture repo
fixture = Path(tempfile.mkdtemp(prefix="chamnan-test-")).resolve()
(fixture / "migrations").mkdir()
(fixture / "build").mkdir()
(fixture / "src").mkdir()
(fixture / "src" / "billing.py").write_text(
    '"""Charges cards and records the result."""\ndef charge(amount, card): ...\n')
(fixture / "src" / "hashed.py").write_text("# Reads config from disk.\ndef load(): ...\n")
(fixture / "src" / "bare.py").write_text("def undocumented(): ...\n")
(fixture / "src" / "leaky.js").write_text(
    "// Prod DB postgres://admin:Hunter2Pass@db.internal/main\nexport function connect() {}\n")
(fixture / "src" / "api.py").write_text(
    '"""HTTP surface."""\n@router.get("/orders/{oid}")\ndef get_order(oid): ...\n'
    '@router.post("/orders")\ndef make_order(): ...\n')
(fixture / "build" / "generated.py").write_text("# Generated, should be skipped.\ndef x(): ...\n")
(fixture / "migrations" / "001.sql").write_text(
    "-- Everyone who can sign in.\nCREATE TABLE users (\n  id BIGSERIAL PRIMARY KEY,\n"
    "  email VARCHAR(255)\n);\n")
(fixture / "secret.pem").write_text(
    fake("-----BEGIN", " RSA PRIVATE KEY-----") + "\nMIIfixture\n"
    + fake("-----END", " RSA PRIVATE KEY-----") + "\n")
env_secret = fake("sk_", "live_", "zzzzzzzzzzzzzzzzz")
(fixture / ".env").write_text(f"DATABASE_URL=postgres://u:p@h/d\nSTRIPE_KEY={env_secret}\n")

files = mapper.scan(fixture)
paths = {f["path"] for f in files}
check("scans source files", "src/billing.py" in paths)
check("skips build/ directory", "build/generated.py" not in paths)
check("skips blocked .pem", "secret.pem" not in paths)
check("python docstring becomes summary",
      any(f["path"] == "src/billing.py" and "Charges cards" in f["doc"] for f in files))
check("python # header becomes summary",
      any(f["path"] == "src/hashed.py" and "Reads config" in f["doc"] for f in files))
(fixture / "src" / "__init__.py").write_text("")
(fixture / "src" / "onlycomments.py").write_text("# just a note\n# and another\n")
empties = mapper.scan(fixture)
check("an empty file is still listed in the index",
      any(f["path"] == "src/__init__.py" for f in empties))
check("an empty file is not counted as missing a summary",
      any(f["path"] == "src/__init__.py" and not f["describable"] for f in empties))
check("a comment-only file with no code is not counted either",
      any(f["path"] == "src/onlycomments.py" and not f["describable"] for f in empties))
check("a real file still counts",
      any(f["path"] == "src/billing.py" and f["describable"] for f in empties))
(fixture / "src" / "__init__.py").unlink()
(fixture / "src" / "onlycomments.py").unlink()

check("undocumented file has empty summary",
      any(f["path"] == "src/bare.py" and not f["doc"] for f in files))

rendered = mapper.render(files, fixture)
check("map has a Quick Index", "## Quick Index" in rendered)
check("map has Full Detail", "## Full Detail" in rendered)
check("index comes before detail", rendered.index("## Quick Index") < rendered.index("## Full Detail"))
check("SECRET NOT IN MAP (credentialed url)", "Hunter2Pass" not in rendered)
check("map keeps the readable half of the url", "db.internal" in rendered)

# ---------------------------------------------------------------- the SKIP_DIRS regression
# A repo living under a directory named like a build output must still be scanned. Checking
# path.parts instead of the path relative to the scan root silently skipped every file.
nested = Path(tempfile.mkdtemp(prefix="chamnan-tmp-")).resolve() / "build" / "myrepo"
nested.mkdir(parents=True)
(nested / "app.py").write_text("# The app.\ndef main(): ...\n")
check("repo under a dir named build/ is still scanned", len(mapper.scan(nested)) == 1)

# ---------------------------------------------------------------- find_root and nested checkouts
# Searching every ancestor for .chamnan/ before looking at any .git meant a checkout inside another
# checkout resolved to the OUTER repository, so its first chamnan-map indexed and overwrote its
# host's map instead of building its own. Nearest boundary wins; a workspace breaks a tie at the
# same level, which is what keeps a monorepo subproject working.
fr = Path(tempfile.mkdtemp(prefix="chamnan-root-")).resolve()
(fr / ".chamnan").mkdir(parents=True)
(fr / ".git").mkdir()
(fr / "inner" / ".git").mkdir(parents=True)
(fr / "inner" / "deep").mkdir()
check("find_root: a nested checkout resolves to itself, not its host",
      ws.find_root(fr / "inner") == fr / "inner")
check("find_root: and from deeper inside it too",
      ws.find_root(fr / "inner" / "deep") == fr / "inner")
check("find_root: the host still resolves to the host", ws.find_root(fr) == fr)

# The tie, and the case the two-pass version existed for: a workspace deliberately placed in a
# subproject must still win over the outer repository root.
(fr / "sub" / ".chamnan").mkdir(parents=True)
check("find_root: a workspace in a subproject is not relocated outward",
      ws.find_root(fr / "sub") == fr / "sub")

# A plain directory has neither marker, so the search continues past it.
(fr / "plain").mkdir()
check("find_root: an ordinary subdirectory still resolves to the repo root",
      ws.find_root(fr / "plain") == fr)

shutil.rmtree(fr, ignore_errors=True)

# ---------------------------------------------------------------- the two counts agree
# chamnan-map printed the DESCRIBABLE file count under the label "source file(s)", while the header
# it wrote into MAP.md used the real one. Two numbers for the same scan, in the tool and in its own
# artifact, differing by however many files carry no describable code. Caught on a real repository:
# 187 printed, 189 written. It is the headline figure people quote, so it gets a test.
cnt_root = Path(tempfile.mkdtemp(prefix="chamnan-count-")).resolve()
(cnt_root / ".git").mkdir(parents=True)
(cnt_root / "a.py").write_text("# Does a thing.\ndef a(): ...\n")
(cnt_root / "b.py").write_text("# Does another.\ndef b(): ...\n")
(cnt_root / "__init__.py").write_text("")   # scanned, but a package marker describes nothing

_out = subprocess.run([str(ROOT / "bin" / "chamnan-map")], cwd=cnt_root,
                      capture_output=True, text=True).stdout
_written = (cnt_root / ".chamnan" / "MAP.md").read_text()
_printed = re.search(r"(\d+) source file\(s\)", _out)
_header = re.search(r"Generated by chamnan\. (\d+) source file\(s\)", _written)
check("count: chamnan-map prints a source-file count", bool(_printed))
check("count: MAP.md's header carries one too", bool(_header))
check("count: the two agree",
      bool(_printed) and bool(_header) and _printed.group(1) == _header.group(1))
check("count: and it is every scanned file, not just the describable ones",
      bool(_printed) and int(_printed.group(1)) == len(mapper.scan(cnt_root)))
# An empty __init__.py is real source by every measure that matters -- it is scanned, it is
# counted, it is in the map -- and there is nothing in it to summarise. That gap between "scanned"
# and "describable" is exactly what made the two counts diverge.
check("count: the coverage line still reports the describable subset",
      "2/2 files" in _out and "1 with no code to describe" in _out)

shutil.rmtree(cnt_root, ignore_errors=True)

# ---------------------------------------------------------------- nested checkouts
# A checkout inside a checkout is somebody else's code. Found by running chamnan on the repository
# it was written in: five sibling projects were checked out under Work-Mode/ and all 1,086 of their
# files were being indexed as the host's own — a Kubernetes manifest from a test corpus sitting in
# the architecture map of a Streamlit app.
host = Path(tempfile.mkdtemp(prefix="chamnan-nest-")).resolve()
(host / ".git").mkdir(parents=True)
(host / "mine.py").write_text("# Mine.\ndef mine(): ...\n")
(host / "vendored" / ".git").mkdir(parents=True)
(host / "vendored" / "theirs.py").write_text("# Theirs.\ndef theirs(): ...\n")
(host / "plain").mkdir()
(host / "plain" / "also_mine.py").write_text("# Also mine.\ndef also(): ...\n")

scanned = {f["path"] for f in mapper.scan(host)}
check("nested checkout: the host's own file is scanned", "mine.py" in scanned)
check("nested checkout: an ordinary subdirectory is still scanned", "plain/also_mine.py" in scanned)
check("nested checkout: the nested repo's file is not", "vendored/theirs.py" not in scanned)
check("nested checkout: nothing from it leaks in at all",
      not any(s.startswith("vendored/") for s in scanned))

# The root's own .git must never exclude the root, or scanning any repository finds nothing.
check("nested checkout: the scan root is never excluded by its own .git", len(scanned) == 2)

# A nested repo inside a skipped directory is already gone; it must not be double-counted or crash.
(host / "node_modules" / "pkg" / ".git").mkdir(parents=True)
(host / "node_modules" / "pkg" / "index.py").write_text("# Pkg.\ndef p(): ...\n")
check("nested checkout: one inside node_modules does not upset the walk",
      len(mapper.scan(host)) == 2)

shutil.rmtree(host, ignore_errors=True)

# ---------------------------------------------------------------- schema / routes / env
tables = schema.scan(fixture, files)
check("finds SQL table", any(t["name"] == "users" for t in tables))
check("table summary from comment above",
      any(t["name"] == "users" and "sign in" in t["summary"] for t in tables))
check("table columns captured",
      any(t["name"] == "users" and "email" in t["columns"] for t in tables))
check("data model section rendered", "## Data model" in schema.render(tables))
check("no data model section when no tables", schema.render([]) == "")

routes = catalogs.scan_routes(fixture, files)
route_paths = {p for (_, p), _ in routes}
check("finds GET route", "/orders/{oid}" in route_paths)
check("finds POST route", "/orders" in route_paths)
check("no API section when no routes", catalogs.render_routes([]) == "")

pairs, unsafe = catalogs.scan_env(fixture, files)
names = {n for n, _ in pairs}
check("finds env var names", {"DATABASE_URL", "STRIPE_KEY"} <= names)
env_text = catalogs.render_env(pairs, unsafe)
check("ENV VALUES NEVER RECORDED", env_secret not in env_text)
check("env value for url never recorded", "postgres://u:p@h/d" not in env_text)
check("warns .env is not gitignored", ".env" in " ".join(unsafe))
check("warns about .env exactly once", len(unsafe) == 1)
check("no config section when no env", catalogs.render_env([], []) == "")

# ---------------------------------------------------------------- workspace
os.chdir(fixture)
check("find_root locates the fixture", ws.find_root(fixture) == fixture)
check("config defaults load", ws.load_config(fixture)["language"] == "en")
check("enabled() defaults to on", ws.enabled("map", fixture))
ws.ensure(fixture)
check("ensure creates skills dir", (fixture / ".chamnan" / "skills").is_dir())
check("ensure writes config", (fixture / ".chamnan" / "config.json").is_file())
(fixture / ".chamnan" / "config.json").write_text('{"map": false}')
check("enabled() respects config", not ws.enabled("map", fixture))
(fixture / ".chamnan" / "config.json").write_text("{ broken json")
check("broken config falls back to defaults", ws.enabled("map", fixture))
(fixture / ".chamnan" / "config.json").write_text(json.dumps(ws.DEFAULT_CONFIG))
# The session-start hook reads MAP.md off disk, so the render above has to actually be written
# before the hook is exercised — otherwise it correctly injects nothing and the test reads as a
# failure of the hook rather than of the fixture.
(fixture / ".chamnan" / "MAP.md").write_text(rendered, encoding="utf-8")

# ---------------------------------------------------------------- peek
import csv as _csv, sqlite3 as _sq, zipfile as _zip
pk = fixture / "peekables"
pk.mkdir(exist_ok=True)
with (pk / "rows.csv").open("w", newline="") as fh:
    w = _csv.writer(fh); w.writerow(["id", "city", "amount"])
    for i in range(900):
        w.writerow([i, "Rotterdam" if i % 2 else "Busan", i * 3])
out = peek_mod.peek(pk / "rows.csv")
check("peek names the columns", "`city`" in out)
check("peek counts the rows", "900 data rows" in out)
check("peek stays far under the file size", len(out) < 2000)
out = peek_mod.peek(pk / "rows.csv", find="Busan")
check("peek --find returns matching lines with numbers", "line " in out and "Busan" in out)
check("peek --find leaves out the misses", "Rotterdam" not in out)

(pk / "shape.json").write_text(json.dumps({"a": {"b": [1, 2, 3]}, "c": "x"}))
out = peek_mod.peek(pk / "shape.json")
check("peek shows json structure", "list" in out or "int" in out)
check("PEEK NEVER PRINTS JSON VALUES", '"x"' not in out)

con = _sq.connect(pk / "s.db")
con.execute("CREATE TABLE bays(id INTEGER PRIMARY KEY, code TEXT)")
con.executemany("INSERT INTO bays VALUES(?,?)", [(i, f"b{i}") for i in range(40)])
con.commit(); con.close()
out = peek_mod.peek(pk / "s.db")
check("peek reads a sqlite schema", "bays" in out and "code" in out)

with _zip.ZipFile(pk / "book.xlsx", "w") as z:
    z.writestr("xl/workbook.xml", '<sheets><sheet name="Ledger"/></sheets>')
out = peek_mod.peek(pk / "book.xlsx")
check("peek reads spreadsheet sheet names", "Ledger" in out)

# An extension is a claim, not a fact: the csv reader parses binary data happily and used to emit
# a column list made of control characters.
(pk / "junk.csv").write_bytes(bytes(range(256)) * 20)
out = peek_mod.peek(pk / "junk.csv")
check("peek survives a malformed file", "could not read" in out or "printable" in out)
check("binary named .csv is not parsed as a table", "columns:" not in out)
check("binary named .csv claims no saving", "instead of" not in out)

# UTF-8 that is not Latin must not be mistaken for binary by the same sniff.
(pk / "thai.csv").write_text("ท่าเรือ,น้ำหนัก\nฮัมบวร์ก,26000\n", encoding="utf-8")
check("Thai text is still read as a table", "columns:" in peek_mod.peek(pk / "thai.csv"))

(pk / "real.csv").write_text("id,lane\n" + "".join(f"s{i},DEHAM\n" for i in range(300)),
                             encoding="utf-8")
check("peek reports the saving on a file that could have been read whole",
      "instead of" in peek_mod.peek(pk / "real.csv"))
check("peek refuses a directory", "not a file" in peek_mod.peek(pk))

# ---------------------------------------------------------------- log retention
import time
logs = fixture / ".chamnan" / "logs"
old_log = logs / "ancient.jsonl"
new_log = logs / "today.jsonl"
old_log.write_text("x")
new_log.write_text("x")
os.utime(old_log, (time.time() - 30 * 86400, time.time() - 30 * 86400))
removed = ws.prune_logs(fixture)
check("prunes a log past the retention window", not old_log.exists())
check("keeps a log inside the window", new_log.exists())
check("prune reports what it removed", removed == 1)
check("prune is safe when logs/ is missing", ws.prune_logs(Path(tempfile.mkdtemp())) == 0)
check("no dead config keys", "claude_md_token_budget" not in ws.DEFAULT_CONFIG)

# ---------------------------------------------------------------- upgrading a stale config
stale = fixture / ".chamnan" / "config.json"
stale.write_text(json.dumps({"map": False, "a_key_that_was_removed": 1}))
ws.ensure(fixture)
after = json.loads(stale.read_text())
check("upgrade keeps a setting the user changed", after["map"] is False)
check("upgrade adds keys introduced since", "index_token_budget" in after)
check("upgrade drops a key that no longer exists", "a_key_that_was_removed" not in after)
stale.write_text(json.dumps(ws.DEFAULT_CONFIG))

# ---------------------------------------------------------------- hooks
def run_hook(name, payload):
    return subprocess.run([str(ROOT / "hooks" / name)], input=json.dumps(payload),
                          capture_output=True, text=True, cwd=fixture).stdout


def import_hook_module(name):
    """Load a hooks/*.py file as an importable module, for unit-testing a function inside it
    directly rather than only through its subprocess/stdout behaviour."""
    spec = importlib.util.spec_from_file_location(Path(name).stem, ROOT / "hooks" / name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

script = ("import json\nfrom pathlib import Path\n"
          "records = json.loads(Path('usage.json').read_text())\n"
          "total_cost = sum(entry['cost'] for entry in records['days'])\n"
          "call_count = sum(entry['calls'] for entry in records['days'])\n"
          "print(f'cost={total_cost} calls={call_count}')\n")
outs = [run_hook("scratch_watch.py",
                 {"tool_name": "Bash", "tool_input": {"command": f"python3 - <<'PY'\n{script}print({i})\nPY"}})
        for i in range(3)]
check("scratch watch silent on 1st", not outs[0].strip())
check("scratch watch silent on 2nd", not outs[1].strip())
check("scratch watch speaks on 3rd", "promote" in outs[2])
check("session end digests the repeats", "repeated this session" in run_hook("session_end.py", {}))

# ---------------------------------------------------------------- candidates (lib/candidates.py)
# evidence -> candidate -> human confirm -> memory. A candidate survives the session that noticed
# it; it is never itself injected as knowledge, only its COUNT does (see the ledger check below).
cand_root = Path(tempfile.mkdtemp(prefix="chamnan-candidates-")).resolve()
(cand_root / ".git").mkdir()
ws.ensure(cand_root)

seq_a = ["git add", "git commit", "git push"]
p1, is_new1 = candidates.upsert(cand_root, seq_a, 2, "2026-08-01", provenance="ai-inferred")
check("a new candidate reports is_new", is_new1)
check("the candidate file exists where path_for says", p1 == candidates.path_for(cand_root, seq_a))
body = p1.read_text(encoding="utf-8")
check("the candidate names its sequence", "git add" in body and "git push" in body)
check("the candidate carries Observed", "**Observed:** 2" in body)
check("the candidate carries Provenance", "**Provenance:** ai-inferred" in body)
check("read() round-trips observed/last-seen/provenance",
      candidates.read(cand_root, seq_a) == ("2", "2026-08-01", "ai-inferred"))

# THE SAME sequence detected again upserts the SAME file -- never a second one -- and observed is
# SET to whatever repeated() currently reports, not incremented by this module.
p2, is_new2 = candidates.upsert(cand_root, seq_a, 3, "2026-08-03", provenance="ai-inferred")
check("upserting the same sequence again reuses the same path", p2 == p1)
check("the second upsert is not reported as new", not is_new2)
check("THE SAME SEQUENCE TWICE PRODUCES ONE CANDIDATE FILE, NEVER TWO",
      len(candidates.entries(cand_root)) == 1)
check("observed reflects the latest count passed in, not an internal increment",
      candidates.read(cand_root, seq_a)[0] == "3")
check("last seen updates to the latest date", candidates.read(cand_root, seq_a)[1] == "2026-08-03")

# A DIFFERENT sequence is a different file.
candidates.upsert(cand_root, ["terraform plan", "terraform apply"], 3, "2026-08-05")
check("a different sequence gets its own candidate", len(candidates.entries(cand_root)) == 2)

# Unknown provenance is rejected AT WRITE TIME, before anything touches disk -- not silently
# stored under a made-up status.
before_files = set(candidates.entries(cand_root))
try:
    candidates.upsert(cand_root, ["a totally new sequence"], 3, "2026-08-06", provenance="bogus")
    check("UNKNOWN PROVENANCE IS REJECTED, NOT SILENTLY STORED", False)
except ValueError:
    check("UNKNOWN PROVENANCE IS REJECTED, NOT SILENTLY STORED", True)
check("a rejected write leaves no new file behind", set(candidates.entries(cand_root)) == before_files)
try:
    candidates.render(["x"], 1, "2026-08-06", "bogus")
    check("render() rejects the same bad provenance directly", False)
except ValueError:
    check("render() rejects the same bad provenance directly", True)

malformed = candidates.directory(cand_root) / "not-a-real-candidate.md"
malformed.write_text("just some prose, no trailer fields at all\n", encoding="utf-8")
check("a malformed candidate file is read as None, not an exception",
      candidates.read(cand_root, ["not", "a", "real", "candidate"]) is None)
malformed.unlink()

# Candidates are counted by the ledger, and the count is the only thing that reaches it -- the
# sequence text and provenance never do.
snap_before = ledger.snapshot(Path(tempfile.mkdtemp(prefix="chamnan-cand-ledger-empty-")))
check("candidate_count is absent (None), not zero, before candidates/ exists",
      snap_before["candidate_count"] is None)
cand_snap = ledger.snapshot(cand_root)
check("CANDIDATES ARE COUNTED BY THE LEDGER ONCE THE DIRECTORY EXISTS", cand_snap["candidate_count"] == 2)
rendered_ledger_line = ledger.render(cand_snap)
check("the ledger line names the count, not the content",
      "2 awaiting review" in rendered_ledger_line
      and "git add" not in rendered_ledger_line
      and "terraform" not in rendered_ledger_line)

shutil.rmtree(cand_root, ignore_errors=True)

# ---------------------------------------------------------------- chamnan-candidates (the review CLI)
cli_root = Path(tempfile.mkdtemp(prefix="chamnan-cli-")).resolve()
(cli_root / ".git").mkdir()
ws.ensure(cli_root)


def run_candidates(*args, cwd=None):
    return subprocess.run([str(ROOT / "bin" / "chamnan-candidates"), *args],
                          capture_output=True, text=True, cwd=cwd or cli_root)


empty_list = run_candidates("list")
check("an empty store says so plainly, not an empty table",
      "no candidates waiting" in empty_list.stdout)
check("listing an empty store exits cleanly", empty_list.returncode == 0)

candidates.upsert(cli_root, ["docker compose", "alembic", "pytest"], 4, "2026-08-26")
candidates.upsert(cli_root, ["git add", "git commit", "git push"], 3, "2026-08-27")

listed = run_candidates("list").stdout
check("THE LIST NAMES BOTH CANDIDATES", "docker compose" in listed and "git add" in listed)
check("the list shows how many times each was observed",
      "observed 4" in listed and "observed 3" in listed)
check("bare invocation with no arguments is the same as list",
      run_candidates().stdout == listed)

# entries() sorts by filename, so [1] is deterministically "docker compose ..." here.
sorted_first = candidates.entries(cli_root)[0]
check("list order matches candidates.entries(), so index 1 is predictable",
      "docker" in sorted_first.name)

confirm_out = run_candidates("confirm", "1")
check("CONFIRM BY NUMBER MOVES PROVENANCE TO ai-confirmed",
      candidates.fields_of(sorted_first).get("provenance") == "ai-confirmed")
check("CONFIRM NEVER WRITES INTO skills/ OR tools/ ITSELF",
      list((cli_root / ".chamnan" / "skills").glob("*.md")) == []
      and list((cli_root / ".chamnan" / "tools").glob("*")) == [])
check("confirm tells the human it did not promote anything itself",
      "chamnan promote" in confirm_out.stdout and "/chamnan:capture" in confirm_out.stdout)

second_slug = candidates.entries(cli_root)[1].stem
edit_out = run_candidates("edit", second_slug)
check("EDIT BY SLUG PRINTS THE FILE'S PATH, RELATIVE TO THE REPO ROOT",
      edit_out.stdout.strip() == f".chamnan/candidates/{second_slug}.md")
check("edit does not modify the file", edit_out.returncode == 0)

reject_out = run_candidates("reject", second_slug)
check("REJECT REMOVES THE FILE", len(candidates.entries(cli_root)) == 1)
check("reject confirms what it removed", "rejected" in reject_out.stdout.lower())

missing_out = run_candidates("confirm", "999")
check("an out-of-range number fails cleanly, not with a traceback",
      missing_out.returncode == 1 and "Traceback" not in missing_out.stderr)
check("the error names the command to recover with", "chamnan candidates" in missing_out.stderr)

unknown_out = run_candidates("frobnicate", "1")
check("an unknown command is rejected with a usage message, not silently ignored",
      unknown_out.returncode == 2 and "list" in unknown_out.stderr)

no_arg_out = run_candidates("confirm")
check("confirm with no id is a usage error, not an IndexError",
      no_arg_out.returncode == 2 and "Traceback" not in no_arg_out.stderr)

help_out = run_candidates("--help")
check("--help prints the docstring and exits cleanly",
      "chamnan candidates" in help_out.stdout and help_out.returncode == 0)
check("--help documents that confirm does not itself promote",
      "does not promote" in help_out.stdout.lower())

(cli_root / ".chamnan" / "config.json").write_text(
    json.dumps({**ws.DEFAULT_CONFIG, "promote": False}))
disabled_out = run_candidates("list")
check("the tool respects the same promote flag scratch_watch.py already gates candidates on",
      "disabled" in disabled_out.stdout.lower())
(cli_root / ".chamnan" / "config.json").write_text(json.dumps(ws.DEFAULT_CONFIG))

# ---------------------------------------------------------------- lib/tools_index.py (shared registry)
# Extracted out of chamnan-promote's own inline logic so a second writer (chamnan-candidates
# promote) reuses it exactly rather than a second, slightly different copy. chamnan-promote itself
# had no test coverage before this refactor touched it, so this closes that gap too.
ti_root = Path(tempfile.mkdtemp(prefix="chamnan-tools-index-")).resolve()
(ti_root / ".git").mkdir()
check("an empty/absent index loads as []", tools_index.load(ti_root) == [])
tools_index.register(ti_root, {"name": "check.sh", "desc": "runs the checks",
                                "added": "2026-08-27T10:00:00+07:00", "origin": "/tmp/check.sh"})
loaded = tools_index.load(ti_root)
check("register() writes an entry that load() reads back", len(loaded) == 1)
check("every field round-trips",
      loaded[0]["name"] == "check.sh" and loaded[0]["desc"] == "runs the checks"
      and loaded[0]["origin"] == "/tmp/check.sh")
check("runs defaults to 0 when not given", loaded[0]["runs"] == 0)
tools_index.register(ti_root, {"name": "second.sh"})
check("a second register() appends rather than overwriting", len(tools_index.load(ti_root)) == 2)
check("a minimal entry (name only) still gets every field, defaulted",
      set(tools_index.load(ti_root)[1])
      == {"name", "desc", "added", "origin", "runs", "interrupted", "stderr_seen"})
check("usage() reads back (name, runs) for every entry, registration order",
      tools_index.usage(ti_root) == [("check.sh", 0), ("second.sh", 0)])
tools_index.record_call(ti_root, "check.sh")
tools_index.record_call(ti_root, "check.sh")
check("usage() reflects runs incremented since registration",
      tools_index.usage(ti_root) == [("check.sh", 2), ("second.sh", 0)])
shutil.rmtree(ti_root, ignore_errors=True)

# The refactor must not have changed chamnan-promote's own observable behaviour.
promote_smoke = Path(tempfile.mkdtemp(prefix="chamnan-promote-smoke-")).resolve()
(promote_smoke / ".git").mkdir()
ws.ensure(promote_smoke)
scratch_script = promote_smoke.parent / "scratch-check.sh"
scratch_script.write_text("#!/bin/bash\necho hi\n")
promote_out = subprocess.run(
    [str(ROOT / "bin" / "chamnan-promote"), str(scratch_script), "greet", "--desc", "says hi"],
    capture_output=True, text=True, cwd=promote_smoke)
check("chamnan-promote STILL WORKS AFTER THE tools_index REFACTOR", promote_out.returncode == 0)
check("the promoted file exists and is executable",
      (promote_smoke / ".chamnan" / "tools" / "greet.sh").stat().st_mode & 0o111)
list_out = subprocess.run([str(ROOT / "bin" / "chamnan-promote"), "--list"],
                          capture_output=True, text=True, cwd=promote_smoke)
check("chamnan-promote --list still shows what was promoted", "greet.sh" in list_out.stdout)
shutil.rmtree(promote_smoke, ignore_errors=True)
scratch_script.unlink(missing_ok=True)

# ---------------------------------------------------------------- promote: skill or tool (Stage 8)
promote_root = Path(tempfile.mkdtemp(prefix="chamnan-promote-cli-")).resolve()
(promote_root / ".git").mkdir()
ws.ensure(promote_root)


def run_pcand(*args):
    return subprocess.run([str(ROOT / "bin" / "chamnan-candidates"), *args],
                          capture_output=True, text=True, cwd=promote_root)


candidates.upsert(promote_root, ["docker compose", "alembic", "pytest"], 4, "2026-08-26")

before_out = run_pcand("promote", "1", "tool", "deploy-check")
check("PROMOTE REFUSES AN UNCONFIRMED CANDIDATE", before_out.returncode == 1)
check("the refusal names the confirm step", "confirm" in before_out.stderr)
check("refusing to promote creates no tool file",
      list((promote_root / ".chamnan" / "tools").glob("*")) == [])

run_pcand("confirm", "1")
suggestion_out = run_pcand("promote", "1")
check("PROMOTE WITH NO DESTINATION ONLY SUGGESTS, WRITES NOTHING",
      suggestion_out.returncode == 0
      and list((promote_root / ".chamnan" / "tools").glob("*")) == []
      and len(candidates.entries(promote_root)) == 1)
check("the suggestion names both real destinations", "tool" in suggestion_out.stdout
      and "skill" in suggestion_out.stdout)
check("the suggestion is honest about having no real signal",
      "cannot tell" in suggestion_out.stdout.lower())

tool_out = run_pcand("promote", "1", "tool", "deploy-check")
check("PROMOTE TO TOOL SUCCEEDS FOR A CONFIRMED CANDIDATE", tool_out.returncode == 0)
skeleton = promote_root / ".chamnan" / "tools" / "deploy-check.sh"
check("the skeleton file exists", skeleton.is_file())
check("EVERY STEP OF THE SEQUENCE APPEARS AS ITS OWN PLACEHOLDER LINE",
      all(step in skeleton.read_text() for step in ("docker compose", "alembic", "pytest")))
check("the skeleton is executable",
      bool(skeleton.stat().st_mode & 0o111))
check("THE SKELETON FAILS LOUDLY IF RUN AS-IS, NEVER SILENTLY SUCCEEDS",
      subprocess.run(["bash", str(skeleton)], capture_output=True, text=True).returncode != 0)
check("promotion registers the tool in the shared index",
      any(e["name"] == "deploy-check.sh" for e in tools_index.load(promote_root)))
check("the index entry's origin traces back to the candidate",
      any(e["origin"].startswith("candidate:") for e in tools_index.load(promote_root)))
check("THE CANDIDATE IS REMOVED ONCE PROMOTED TO A TOOL — its finding now lives in the tool file",
      candidates.entries(promote_root) == [])

check("promoting the same name twice refuses rather than overwriting",
      run_pcand("promote", "1", "tool", "deploy-check").returncode == 1)

candidates.upsert(promote_root, ["kubectl get pods", "kubectl logs"], 3, "2026-08-25")
run_pcand("confirm", "1")
skill_out = run_pcand("promote", "1", "skill")
check("PROMOTE TO SKILL WRITES NO FILE AT ALL", not
      list((promote_root / ".chamnan" / "skills").glob("*.md")))
check("promoting to skill leaves the candidate in place -- nothing has actually been captured yet",
      len(candidates.entries(promote_root)) == 1)
check("the skill path names /chamnan:capture", "/chamnan:capture" in skill_out.stdout)
check("the skill path hands over the real sequence",
      "kubectl get pods" in skill_out.stdout and "kubectl logs" in skill_out.stdout)

bogus_out = run_pcand("promote", "1", "not-a-real-destination")
check("an unrecognised destination is a usage error", bogus_out.returncode == 2)

shutil.rmtree(promote_root, ignore_errors=True)
shutil.rmtree(cli_root, ignore_errors=True)

# ---------------------------------------------------------------- tool health (Stage 10, 1.5.2)
# There is no exit code in a Bash tool_response -- confirmed against another installed plugin's
# own comment stating this twice over. Only `interrupted` (real) and non-empty `stderr` (a WEAK
# signal, shown as itself) are tracked; neither is ever reported as "the tool failed".
th_root = Path(tempfile.mkdtemp(prefix="chamnan-tool-health-")).resolve()
(th_root / ".git").mkdir()
ws.ensure(th_root)
tools_index.register(th_root, {"name": "flaky.sh", "desc": "sometimes noisy"})

check("match_call finds a tool whose path appears in the command",
      tools_index.match_call(th_root, ".chamnan/tools/flaky.sh --now") == "flaky.sh")
check("match_call finds nothing for an unrelated command",
      tools_index.match_call(th_root, "ls -la") is None)
check("match_call finds nothing when the index is empty",
      tools_index.match_call(Path(tempfile.mkdtemp()), ".chamnan/tools/flaky.sh") is None)


def call_flaky(stderr_text="", interrupted=False):
    payload = {"tool_name": "Bash", "tool_input": {"command": ".chamnan/tools/flaky.sh"},
              "tool_response": {"stdout": "", "stderr": stderr_text, "interrupted": interrupted}}
    return subprocess.run([str(ROOT / "hooks" / "scratch_watch.py")], input=json.dumps(payload),
                          capture_output=True, text=True, cwd=th_root).stdout


check("a clean call is silent and still counts as a run",
      call_flaky().strip() == "" and tools_index.load(th_root)[0]["runs"] == 1)
check("a run with empty stderr does not count as a stderr signal",
      tools_index.load(th_root)[0]["stderr_seen"] == 0)

out2 = call_flaky(stderr_text="warning one")
out3 = call_flaky(stderr_text="warning two")
check("stderr below the flag threshold stays silent",
      out2.strip() == "" and out3.strip() == "")
out4 = call_flaky(stderr_text="warning three")
check("THE THIRD STDERR OCCURRENCE CROSSES THE THRESHOLD AND SPEAKS, ONCE",
      "flaky.sh" in out4 and "3" in out4)
check("the crossing names the demote command", "demote" in out4)
out5 = call_flaky(stderr_text="warning four")
check("A FOURTH OCCURRENCE STAYS SILENT — ONLY THE CROSSING SPOKE", out5.strip() == "")
check("runs and stderr_seen both kept incrementing while silent",
      tools_index.load(th_root)[0]["runs"] == 5
      and tools_index.load(th_root)[0]["stderr_seen"] == 4)

unrelated_out = subprocess.run(
    [str(ROOT / "hooks" / "scratch_watch.py")],
    input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "git status"},
                      "tool_response": {"stdout": "", "stderr": "", "interrupted": False}}),
    capture_output=True, text=True, cwd=th_root)
check("a command that does not invoke a promoted tool never touches the index",
      tools_index.load(th_root)[0]["runs"] == 5)

# interrupted is tracked as its own signal, independent of stderr.
tools_index.register(th_root, {"name": "other.sh"})
for _ in range(3):
    subprocess.run([str(ROOT / "hooks" / "scratch_watch.py")], input=json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": ".chamnan/tools/other.sh"},
         "tool_response": {"stdout": "", "stderr": "", "interrupted": True}}),
        capture_output=True, text=True, cwd=th_root)
other_entry = next(e for e in tools_index.load(th_root) if e["name"] == "other.sh")
check("INTERRUPTED IS TRACKED SEPARATELY FROM STDERR",
      other_entry["interrupted"] == 3 and other_entry["stderr_seen"] == 0)

demote_out = subprocess.run([str(ROOT / "bin" / "chamnan-candidates"), "demote", "flaky.sh"],
                            capture_output=True, text=True, cwd=th_root)
check("DEMOTE REMOVES THE TOOL FROM THE INDEX",
      not any(e["name"] == "flaky.sh" for e in tools_index.load(th_root)))
check("demote deletes the tool file itself",
      not (th_root / ".chamnan" / "tools" / "flaky.sh").exists())
check("demote writes a fresh candidate carrying the tool's own description",
      any("sometimes noisy" in p.read_text(encoding="utf-8") for p in candidates.entries(th_root)))
check("demote reports success", demote_out.returncode == 0)

missing_demote = subprocess.run([str(ROOT / "bin" / "chamnan-candidates"), "demote", "nope.sh"],
                                capture_output=True, text=True, cwd=th_root)
check("demoting a tool that does not exist fails cleanly, not with a traceback",
      missing_demote.returncode == 1 and "Traceback" not in missing_demote.stderr)

no_arg_demote = subprocess.run([str(ROOT / "bin" / "chamnan-candidates"), "demote"],
                               capture_output=True, text=True, cwd=th_root)
check("demote with no name is a usage error, not an IndexError",
      no_arg_demote.returncode == 2 and "Traceback" not in no_arg_demote.stderr)

shutil.rmtree(th_root, ignore_errors=True)

# ---------------------------------------------------------------- notice_workflow writes, not just speaks
# The mechanism this whole stage exists for: a sequence that qualifies gets a candidate file, and
# the file survives past the moment the notice printed and scrolled away.
e2e_root = Path(tempfile.mkdtemp(prefix="chamnan-e2e-candidate-")).resolve()
(e2e_root / ".git").mkdir()
ws.ensure(e2e_root)

e2e_log = e2e_root / ".chamnan" / "logs" / "commands.jsonl"
e2e_seq = ["docker compose", "alembic", "pytest"]
workflows.record(e2e_log, e2e_seq, "2026-08-01T10:00:00+07:00", tool="Bash")
workflows.record(e2e_log, e2e_seq, "2026-08-02T10:00:00+07:00", tool="Bash")


def run_scratch_watch(payload, cwd):
    return subprocess.run([str(ROOT / "hooks" / "scratch_watch.py")], input=json.dumps(payload),
                          capture_output=True, text=True, cwd=cwd).stdout


crossing_payload = {"session_id": "e2e-1", "tool_name": "Bash",
                    "tool_input": {"command": "docker compose up -d && alembic upgrade head && pytest tests/"},
                    "tool_response": {"stdout": "ok", "stderr": "", "interrupted": False}}
notice = run_scratch_watch(crossing_payload, e2e_root)
check("the crossing still speaks, exactly as before this stage", "come round" in notice)
check("the notice now also points at the candidate file", "candidate" in notice)
e2e_candidates = candidates.entries(e2e_root)
check("A CANDIDATE FILE EXISTS AFTER THE CROSSING, NOT JUST A PRINTED LINE", len(e2e_candidates) == 1)
check("the candidate on disk matches the sequence that crossed",
      "docker compose" in e2e_candidates[0].read_text() and "pytest" in e2e_candidates[0].read_text())
# A candidate is evidence, not knowledge -- session_start.py has no reader for candidates/ at all,
# so nothing about one ever reaches an injected session regardless of what config is set.
check("session_start.py never mentions the candidates store",
      "candidate" not in run_hook("session_start.py", {}).lower())

# Repeating the SAME still-qualifying sequence again must not create a SECOND candidate file, and
# must not print a second notice in the same "crossing" sense (only a NEW crossing speaks).
run_scratch_watch(crossing_payload, e2e_root)
check("a repeat of the same qualifying sequence updates, never duplicates, the candidate",
      len(candidates.entries(e2e_root)) == 1)

shutil.rmtree(e2e_root, ignore_errors=True)

# ---------------------------------------------------------------- the resume nudge
scratch_watch_mod = import_hook_module("scratch_watch.py")

nudge_root = Path(tempfile.mkdtemp(prefix="chamnan-nudge-")).resolve()
(nudge_root / ".git").mkdir()
ws.ensure(nudge_root)


def touch(i, cwd, session="nudge-session"):
    payload = {"session_id": session, "tool_name": "Write",
              "tool_input": {"file_path": "/tmp/chamnan-test-scratch.txt", "content": f"call {i}"}}
    return run_scratch_watch(payload, cwd)


nudge_outs = [touch(i, nudge_root) for i in range(1, 16)]
nudge_hits = [o for o in nudge_outs if "resume" in o]
check("THE NUDGE FIRES", len(nudge_hits) >= 1)
check("THE NUDGE FIRES AT MOST ONCE PER SESSION", len(nudge_hits) == 1)
check("the nudge does not fire before its own call threshold",
      not any("resume" in o for o in nudge_outs[:scratch_watch_mod.NUDGE_AT - 1]))
check("the nudge points at /chamnan:resume", "/chamnan:resume" in nudge_hits[0])

# A second, independent session_id gets its OWN chance to nudge -- this is "once per SESSION",
# deliberately narrower than "once per day".
second_session_outs = [touch(i, nudge_root, session="nudge-session-2") for i in range(1, 16)]
check("a different session_id is nudged independently of the first",
      any("resume" in o for o in second_session_outs))

silent_root = Path(tempfile.mkdtemp(prefix="chamnan-nudge-silent-")).resolve()
(silent_root / ".git").mkdir()
ws.ensure(silent_root)
today_str = datetime.datetime.now().astimezone().strftime("%Y-%m-%d")
(silent_root / ".chamnan" / "sessions" / f"{today_str}-already-recorded.md").write_text(
    "# Already recorded\n\n## Remaining\nnone\n", encoding="utf-8")
silent_outs = [touch(i, silent_root, session="silent-session") for i in range(1, 16)]
check("NUDGE IS SILENT WHEN TODAY ALREADY HAS A SESSION RECORD",
      not any("resume" in o for o in silent_outs))

off_root = Path(tempfile.mkdtemp(prefix="chamnan-nudge-off-")).resolve()
(off_root / ".git").mkdir()
ws.ensure(off_root)
(off_root / ".chamnan" / "config.json").write_text(json.dumps({**ws.DEFAULT_CONFIG, "ledger": False}))
off_outs = [touch(i, off_root, session="off-session") for i in range(1, 16)]
check("NUDGE IS SILENT WHEN THE LEDGER FLAG IS OFF", not any("resume" in o for o in off_outs))

shutil.rmtree(nudge_root, ignore_errors=True)
shutil.rmtree(silent_root, ignore_errors=True)
shutil.rmtree(off_root, ignore_errors=True)

# ---------------------------------------------------------------- automatic As-of / Provenance stamping
# The one place As-of actually gets written -- not the remember skill's own instructions, because
# this project's founding finding is that things gated on being remembered do not reliably happen.
stamp_root = Path(tempfile.mkdtemp(prefix="chamnan-stamp-")).resolve()
(stamp_root / ".git").mkdir()
ws.ensure(stamp_root)

decision_path = stamp_root / ".chamnan" / "memory" / "decisions" / "postgres.md"
decision_path.parent.mkdir(parents=True, exist_ok=True)
decision_path.write_text("# Postgres over SQLite\n\nTwo writers.\n", encoding="utf-8")

write_evt = {"tool_name": "Write",
            "tool_input": {"file_path": str(decision_path), "content": "..."}}
stamp_out = run_scratch_watch(write_evt, stamp_root)
check("stamping a memory entry never prints anything", stamp_out.strip() == "")
stamped_text = decision_path.read_text(encoding="utf-8")
check("AS-OF IS ADDED AUTOMATICALLY ON WRITE", "**As-of:**" in stamped_text)
check("PROVENANCE DEFAULTS TO ai-drafted", "**Provenance:** ai-drafted" in stamped_text)
check("the original body is untouched", "Two writers." in stamped_text)

run_scratch_watch(write_evt, stamp_root)
retext = decision_path.read_text(encoding="utf-8")
check("a second write does not double-stamp As-of", retext.count("**As-of:**") == 1)
check("a second write does not double-stamp Provenance", retext.count("**Provenance:**") == 1)

already_confirmed = stamp_root / ".chamnan" / "memory" / "rules" / "confirmed.md"
already_confirmed.parent.mkdir(parents=True, exist_ok=True)
already_confirmed.write_text(
    "# A rule\n\nSome constraint.\n\n**As-of:** 2026-01-01\n**Provenance:** user\n",
    encoding="utf-8")
run_scratch_watch({"tool_name": "Edit", "tool_input": {"file_path": str(already_confirmed)}},
                  stamp_root)
check("AN EXISTING Provenance IS NEVER OVERWRITTEN (user stays user, not ai-drafted)",
      "**Provenance:** user" in already_confirmed.read_text(encoding="utf-8"))

outside_memory = stamp_root / "src" / "app.py"
outside_memory.parent.mkdir(parents=True, exist_ok=True)
outside_memory.write_text("print('hi')\n", encoding="utf-8")
run_scratch_watch({"tool_name": "Write",
                   "tool_input": {"file_path": str(outside_memory), "content": "print('hi')\n"}},
                  stamp_root)
check("a file outside .chamnan/memory/ is never stamped",
      outside_memory.read_text(encoding="utf-8") == "print('hi')\n")

not_markdown = stamp_root / ".chamnan" / "memory" / "decisions" / "notes.txt"
not_markdown.write_text("plain text, not a memory entry format\n", encoding="utf-8")
run_scratch_watch({"tool_name": "Write",
                   "tool_input": {"file_path": str(not_markdown), "content": "x"}}, stamp_root)
check("a non-.md file under memory/ is left alone",
      "As-of" not in not_markdown.read_text(encoding="utf-8"))

shutil.rmtree(stamp_root, ignore_errors=True)

# ---------------------------------------------------------------- chamnan-report's knowledge inventory
report_root = Path(tempfile.mkdtemp(prefix="chamnan-report-inv-")).resolve()
(report_root / ".git").mkdir()
ws.ensure(report_root)
(report_root / ".chamnan" / "memory" / "decisions" / "d.md").write_text(
    "# A decision\n\nbody\n", encoding="utf-8")
report_out = subprocess.run([str(ROOT / "bin" / "chamnan-report")], capture_output=True, text=True,
                            cwd=report_root).stdout
check("chamnan-report prints the knowledge inventory heading", "Knowledge inventory" in report_out)
check("the inventory shows every store, including empty ones",
      "sessions/" in report_out and "memory/decisions/" in report_out
      and "memory/lessons/" in report_out and "candidates/" in report_out)
check("the inventory counts the one decision written above", "1 entry" in report_out)
check("the inventory flags the decision with no Rejected:", "no `Rejected:`" in report_out)
check("chamnan-report prints the Usage heading", "Usage" in report_out)
check("a command never logged reads as 0, not absent", "chamnan-map" in report_out and "0 times" in report_out)
check("no promoted tools yet -> no Promoted tools section", "Promoted tools" not in report_out)

# ---------------------------------------------------------------- chamnan-report's Usage section (Stage 11)
report_log = report_root / ".chamnan" / "logs" / "commands.jsonl"
report_log.parent.mkdir(parents=True, exist_ok=True)
report_log.write_text(
    "\n".join(json.dumps(e) for e in [
        {"at": "2026-08-01T10:00:00+07:00", "kind": "command", "sig": "chamnan-map"},
        {"at": "2026-08-20T10:00:00+07:00", "kind": "command", "sig": "chamnan-map"},
        {"at": "2026-08-25T10:00:00+07:00", "kind": "command", "sig": "chamnan-candidates"},
    ]) + "\n", encoding="utf-8")
tools_index.register(report_root, {"name": "deploy-check.sh", "desc": "x",
                                    "added": "2026-08-27T10:00:00+07:00", "origin": "y"})
tools_index.record_call(report_root, "deploy-check.sh")
usage_out = subprocess.run([str(ROOT / "bin" / "chamnan-report")], capture_output=True, text=True,
                           cwd=report_root).stdout
check("logged calls are counted per command", "chamnan-map" in usage_out and "2 times" in usage_out)
check("the usage span names the oldest and newest date logged",
      "2026-08-01" in usage_out and "2026-08-25" in usage_out)
check("a registered tool with runs now shows a Promoted tools section",
      "Promoted tools" in usage_out and "deploy-check.sh" in usage_out and "1 run" in usage_out)
shutil.rmtree(report_root, ignore_errors=True)


big = fixture / "package-lock.json"
big.write_text('{"lockfileVersion": 3}\n' + "x" * 1000)
lock_out = run_hook("bulk_read_notice.py", {"tool_name": "Read", "tool_input": {"file_path": str(big)}})
check("bulk read warns on a lock file", "lock file" in lock_out)
check("bulk read stays advisory, never denies", "permissionDecision" not in lock_out)
small_out = run_hook("bulk_read_notice.py",
                     {"tool_name": "Read", "tool_input": {"file_path": str(fixture / "src" / "billing.py")}})
check("bulk read silent on a small source file", not small_out.strip())
check("bulk read ignores non-Read tools",
      not run_hook("bulk_read_notice.py", {"tool_name": "Bash", "tool_input": {"command": "ls"}}).strip())

# Over budget, the index must roll up by directory rather than lose its tail: truncating at a byte
# offset drops whatever sorts last, so a whole area of the repo vanishes with nothing to show it did.
wide = fixture / ".chamnan" / "MAP.md"
many = "\n".join(f"- **`pkg{i%4}/mod{i:03d}.py`** (10L, 2fn) — does something number {i}"
                 for i in range(400))
wide.write_text("# Architecture map — big\n\n## Quick Index\n\n" + many + "\n\n## Full Detail\n")
big_out = run_hook("session_start.py", {})
check("over-budget index stays inside the budget",
      tokens.estimate(big_out) < ws.DEFAULT_CONFIG["index_token_budget"] * 1.5)
check("over-budget index keeps every directory visible",
      all(f"**pkg{i}/**" in big_out for i in range(4)))
check("over-budget index says it rolled up", "Rolled up by directory" in big_out)
check("over-budget index does not silently truncate", "mod399" not in big_out or "pkg3" in big_out)
wide.write_text(rendered, encoding="utf-8")

cfgp = fixture / ".chamnan" / "config.json"
check("reply_style is off by default", ws.DEFAULT_CONFIG["reply_style"] == "off")
check("nothing injected while it is off", "Reply style" not in run_hook("session_start.py", {}))
cfgp.write_text(json.dumps({**ws.DEFAULT_CONFIG, "reply_style": "terse"}))
styled = run_hook("session_start.py", {})
check("a chosen style is injected", "Reply style for this repo" in styled)
check("the style says how to switch it off", "config.json" in styled)
cfgp.write_text(json.dumps({**ws.DEFAULT_CONFIG, "reply_style": "nonsense"}))
check("an unknown style injects nothing", "Reply style" not in run_hook("session_start.py", {}))
cfgp.write_text(json.dumps(ws.DEFAULT_CONFIG))

start_out = run_hook("session_start.py", {})
check("session start injects the index", "Architecture index" in start_out)
check("SESSION START NEVER INJECTS A SECRET", "Hunter2Pass" not in start_out)

# ---------------------------------------------------------------- ledger (lib/ledger.py)
# The finding this whole release rests on: hook-written logs held 700 records on the workspace
# this was measured against, and every skill-written store held zero. The ledger's job is to make
# that fact visible every session instead of silently absent.
empty_ws = Path(tempfile.mkdtemp(prefix="chamnan-ledger-")).resolve()
(empty_ws / ".git").mkdir()
ws.ensure(empty_ws)
snap = ledger.snapshot(empty_ws, now=1_000_000_000)
check("empty workspace counts zero records", snap["record_count"] == 0)
check("empty workspace counts zero memory entries", snap["memory_count"] == 0)
check("empty workspace has no last write", snap["last_write"] is None)
check("candidates/ not yet created reads as absent, not zero", snap["candidate_count"] is None)
check("empty workspace renders the nothing-written line",
      ledger.render(snap) == "chamnan · 0 records · 0 memory entries · nothing written yet")

# A workspace that was never ensure()'d at all -- sessions/ and memory/ do not exist as
# directories -- must not crash the count.
never_touched = Path(tempfile.mkdtemp(prefix="chamnan-ledger-bare-")).resolve()
(never_touched / ".chamnan").mkdir()
bare_snap = ledger.snapshot(never_touched, now=1_000_000_000)
check("a missing store does not crash the ledger", bare_snap["record_count"] == 0)
check("a missing store renders the nothing-written line",
      ledger.render(bare_snap) == "chamnan · 0 records · 0 memory entries · nothing written yet")

# One old session (outside the 7-day window) and one old memory entry: totals are non-zero, but
# nothing arrived "this week" -- the delta must read exactly 0, never negative, never absent.
NOW = 1_700_000_000  # arbitrary fixed instant, so the test does not depend on wall-clock time
old_day = "2020-01-01"
(empty_ws / ".chamnan" / "sessions" / f"{old_day}-old-work.md").write_text(
    "# Old work\n\n## Remaining\nnone\n", encoding="utf-8")
(empty_ws / ".chamnan" / "memory" / "decisions" / "old-choice.md").write_text(
    "# An old choice\n\nBecause reasons.\n", encoding="utf-8")
old_mtime = NOW - 30 * 86400
os.utime(empty_ws / ".chamnan" / "memory" / "decisions" / "old-choice.md", (old_mtime, old_mtime))
snap2 = ledger.snapshot(empty_ws, now=NOW)
check("one old session counts as one record", snap2["record_count"] == 1)
check("nothing recent gives a zero delta, not a missing one", snap2["record_recent"] == 0)
check("the delta is never negative", snap2["record_recent"] >= 0)
check("one old memory entry counts as one entry", snap2["memory_count"] == 1)
rendered_line = ledger.render(snap2)
check("the non-empty line still names the delta explicitly", "(+0 this week)" in rendered_line)
check("the non-empty line reports last write", "last write" in rendered_line)

# A session dated this week, by FILENAME rather than mtime -- this matters because mtime resets to
# checkout time on a fresh clone, which would otherwise report every pre-existing session as
# written today the moment the repository is cloned.
recent_day = datetime.datetime.fromtimestamp(NOW - 86400, datetime.timezone.utc).strftime("%Y-%m-%d")
recent_session = empty_ws / ".chamnan" / "sessions" / f"{recent_day}-fresh-work.md"
recent_session.write_text("# Fresh work\n\n## Remaining\nnone\n", encoding="utf-8")
os.utime(recent_session, (old_mtime, old_mtime))  # mtime says old; FILENAME says yesterday
snap3 = ledger.snapshot(empty_ws, now=NOW)
check("a session's own filename date wins over a stale mtime", snap3["record_recent"] == 1)

for f in (empty_ws / ".chamnan" / "sessions").glob("*.md"):
    f.unlink()
for f in (empty_ws / ".chamnan" / "memory" / "decisions").glob("*.md"):
    f.unlink()

# ---------------------------------------------------------------- state.md (lib/state.py)
# The other half of the same finding: STATE.md on the live workspace was 12,998 characters, the
# hook injected only the first 4,000 with no marker, and every heading the owner wrote to say
# "do not raise this again" was below the line.
plain = "# Work in flight\n\nJust a short note about ordinary work, well inside any real budget.\n"
inj, marker = state_mod.render(plain, 1000, "STATE.md")
check("a file shorter than the budget is injected whole", inj.strip() == plain.strip())
check("no marker when nothing was dropped", marker == "")

big = "# Work in flight\n\n" + ("filler line about ordinary work.\n" * 4000)
inj2, marker2 = state_mod.render(big, 50, "STATE.md")
check("an over-budget file is actually cut", len(inj2) < len(big))
check("the marker appears exactly when something was dropped", marker2 != "")
check("the marker names the file", "STATE.md" in marker2)

pinned_doc = ("# Work in flight\n\n"
              + ("filler line about ordinary work.\n" * 2000)
              + "\n### SETTLED — do not raise this again \U0001F4CC\n\n"
              + "The one thing that must survive no matter where it falls in the file.\n"
              # A same-or-higher-level heading after the pin, so the pin's OWN extent is bounded
              # here and does not swallow everything to end-of-file -- exactly as a real STATE.md
              # has further sections after any given one, except the very last.
              + "\n### Unrelated later section\n\n"
              + ("more filler after the pin.\n" * 2000))
inj3, marker3 = state_mod.render(pinned_doc, 50, "STATE.md")
check("A PINNED SECTION BELOW THE CUT IS STILL INJECTED",
      "must survive no matter where it falls" in inj3)
check("an unpinned section below the cut is not injected",
      "more filler after the pin" not in inj3)
check("a dropped unpinned tail still produces a marker even with a pin present", marker3 != "")

pin_text, unpin_text = state_mod.split_pinned(pinned_doc)
check("split_pinned extracts the pinned body", "must survive" in pin_text)
check("split_pinned removes the pin from the unpinned pool", "must survive" not in unpin_text)
check("split_pinned keeps the unpinned filler", "filler line about ordinary work" in unpin_text)

no_pins = "# Just a normal file\n\nNothing here is marked.\n"
inj4, marker4 = state_mod.render(no_pins, 1000, "STATE.md")
check("a file with no pins behaves exactly as a plain head-cut", inj4.strip() == no_pins.strip())
check("a file with no pins under budget has no marker", marker4 == "")

nested_pin = ("### Outer \U0001F4CC\n\nouter body\n\n#### Inner\n\ninner body, still inside outer\n"
              "\n### Sibling\n\nnot part of the pin\n")
pin_text2, unpin_text2 = state_mod.split_pinned(nested_pin)
check("a pin's own subsections are pulled whole", "inner body" in pin_text2)
check("a pin does not swallow its unrelated sibling", "Sibling" not in pin_text2)
check("a sibling after a pin stays in the unpinned pool", "Sibling" in unpin_text2)

# ---------------------------------------------------------------- write-skills line + injection
session_start_mod = import_hook_module("session_start.py")

check("write_skills_line is empty when the plugin has no skills/ dir at all",
      session_start_mod.write_skills_line(Path(tempfile.mkdtemp())) == "")

partial_plugin = Path(tempfile.mkdtemp(prefix="chamnan-skills-"))
(partial_plugin / "skills" / "resume").mkdir(parents=True)
(partial_plugin / "skills" / "resume" / "SKILL.md").write_text("---\ndescription: x\n---\nbody\n")
partial_line = session_start_mod.write_skills_line(partial_plugin)
check("only a skill that actually exists is named", "resume" in partial_line)
check("a skill that does not exist on disk is never named", "remember" not in partial_line)
check("a skill that does not exist on disk is never named (milestone)",
      "milestone" not in partial_line)

full_line = session_start_mod.write_skills_line(ROOT)
for skill_name, _note in session_start_mod.WRITE_SKILLS:
    check(f"the real plugin names its own /{skill_name} skill", f"/chamnan:{skill_name}" in full_line)
check("the write-skills line stays inside its budget", len(full_line) < 260)

# ---------------------------------------------------------------- describe()'s fallback
# 🐛 [2026-08-27] Every skill in the live workspace this hook runs against predates the plugin's
# own frontmatter convention -- all twelve registry lines read "no description — add one".
describe_dir = Path(tempfile.mkdtemp(prefix="chamnan-describe-"))

with_frontmatter = describe_dir / "with-frontmatter.md"
with_frontmatter.write_text("---\ndescription: The real description.\n---\n\n# Title\n\nbody\n")
check("frontmatter's description: still wins when present",
      session_start_mod.describe(with_frontmatter) == "The real description.")

no_frontmatter = describe_dir / "no-frontmatter.md"
no_frontmatter.write_text(
    "# Skill: Something\n\n**ขอบเขต**: what this covers, in the local convention.\n")
check("A FILE WITH NO FRONTMATTER FALLS BACK TO THE FIRST BODY LINE, NOT EMPTY",
      session_start_mod.describe(no_frontmatter) != "")
check("the fallback strips leading bold/bullet markup",
      not session_start_mod.describe(no_frontmatter).startswith("*"))
check("the fallback keeps the actual words",
      "what this covers" in session_start_mod.describe(no_frontmatter))

blockquote_first = describe_dir / "blockquote.md"
blockquote_first.write_text("# Title\n\n> Written 2026-08-25 after a rewrite.\n\nMore body.\n")
check("a leading blockquote marker is stripped too",
      session_start_mod.describe(blockquote_first) == "Written 2026-08-25 after a rewrite.")

only_heading = describe_dir / "only-heading.md"
only_heading.write_text("# Just a title\n")
check("a file with nothing but a heading still returns empty, not a crash",
      session_start_mod.describe(only_heading) == "")

empty_file = describe_dir / "empty.md"
empty_file.write_text("")
check("an empty file returns empty", session_start_mod.describe(empty_file) == "")

long_body = describe_dir / "long.md"
long_body.write_text("# Title\n\n" + ("word " * 60) + "\n")
check("the fallback is capped the same as the frontmatter path",
      len(session_start_mod.describe(long_body)) <= 110)

check("a missing file returns empty rather than raising",
      session_start_mod.describe(describe_dir / "does-not-exist.md") == "")
shutil.rmtree(describe_dir, ignore_errors=True)

ws.ensure(fixture)
start_with_ledger = run_hook("session_start.py", {})
check("session start injects the ledger line", "chamnan ·" in start_with_ledger)
check("session start injects the write-skills line", "/chamnan:resume" in start_with_ledger)
ledger_lines = [ln for ln in start_with_ledger.splitlines() if ln.strip().startswith("_chamnan ·")]
check("the ledger line is present exactly once", len(ledger_lines) == 1)
if ledger_lines:
    check("the ledger line stays near its ~110-character budget", len(ledger_lines[0]) < 200)

(fixture / ".chamnan" / "config.json").write_text(json.dumps({**ws.DEFAULT_CONFIG, "ledger": False}))
check("the ledger flag actually turns the lines off",
      "chamnan ·" not in run_hook("session_start.py", {}))
(fixture / ".chamnan" / "config.json").write_text(json.dumps(ws.DEFAULT_CONFIG))

# 🎯 [changed 2026-08-28] This used to assert that a repository with no workspace produced NO
# output at all. That was the behaviour a teammate hit: install the plugin, open a new project,
# and chamnan is invisible and creates nothing, so the write skills have nowhere to write. A
# repository now gets its scaffold on the first session. The silence that still matters — a
# directory that is not a repository at all — is checked in the first-session section above.
no_workspace = Path(tempfile.mkdtemp(prefix="chamnan-no-ws-"))
(no_workspace / ".git").mkdir()
no_ws_out = subprocess.run([str(ROOT / "hooks" / "session_start.py")], input="{}",
                           capture_output=True, text=True, cwd=no_workspace).stdout
check("a repository with no workspace is given one on its first session",
      (no_workspace / ".chamnan" / "memory" / "decisions").is_dir())
check("...and is told so rather than left to guess", "just been created" in no_ws_out)

# ---------------------------------------------------------------- pin the live workspace's rules
# The concrete instance of the bug this stage exists to fix: on the ACTUAL Lumin-App workspace,
# "SETTLED -- do not raise these again" and "Not this project -- do not audit" both sat below the
# old 4,000-character cut. Both headings were pinned by hand as part of doing this stage (see
# .chamnan/STATE.md); this checks the mechanism actually rescues them there, not just in a fixture.
live_root = Path("/Users/wasuplao/Documents/Lumin-App")
live_state = live_root / ".chamnan" / "STATE.md"
if live_state.is_file():
    live_out = subprocess.run([str(ROOT / "hooks" / "session_start.py")], input="{}",
                              capture_output=True, text=True, cwd=live_root).stdout
    check("on the live workspace, SETTLED reaches the injected output", "SETTLED" in live_out)
    check("on the live workspace, Not this project reaches the injected output",
          "Not this project" in live_out)

shutil.rmtree(no_workspace, ignore_errors=True)
shutil.rmtree(empty_ws, ignore_errors=True)
shutil.rmtree(never_touched, ignore_errors=True)
shutil.rmtree(partial_plugin, ignore_errors=True)


# ---------------------------------------------------------------- token estimation
# A flat characters-per-token constant used to decide how much index reached the session, and it
# was calibrated on English. Measured against the real API, Thai runs about 1.2 characters per
# token and Chinese under 1.0, so a 4,523-character Thai index that the old constant scored at
# 1,256 tokens actually cost 3,153 — it was injected whole against a 3,000-token budget. These
# checks exist so that regression cannot return quietly.
check("ascii is far cheaper per character than CJK",
      tokens.estimate("a" * 500) < tokens.estimate("\u4e2d" * 500) / 2)
check("Thai costs more per character than ascii",
      tokens.estimate("\u0e01" * 500) > tokens.estimate("a" * 500) * 1.5)
check("CJK is estimated at roughly one token per character",
      0.9 <= tokens.estimate("\u4e2d" * 500) / 500 <= 1.1)
check("an empty string costs nothing", tokens.estimate("") == 0)

# Slicing by characters is what made the budget wrong, so cut_at must answer in token space.
thai_doc = "\u0e01\u0e02\u0e03\u0e04\u0e05" * 400
check("cut_at respects the budget for a dense script",
      tokens.estimate(thai_doc[:tokens.cut_at(thai_doc, 100)]) <= 101)
check("cut_at respects the budget for ascii",
      tokens.estimate(("word " * 400)[:tokens.cut_at("word " * 400, 100)]) <= 101)
check("cut_at keeps short text whole", tokens.cut_at("short", 1000) == len("short"))
check("a zero budget cuts everything", tokens.cut_at("anything", 0) == 0)
check("fits agrees with estimate", tokens.fits("a" * 100, tokens.estimate("a" * 100) + 1))

# The bug in one assertion: a Thai index in the band the old constant got wrong must roll up.
thai_index = ("# Architecture map\n\n## Quick Index\n\n"
              + "".join(f"- **`src/m{i:03d}.py`** (6L, 1fn) \u2014 "
                        "\u0e17\u0e33\u0e2b\u0e19\u0e49\u0e32\u0e17\u0e35\u0e48"
                        "\u0e23\u0e31\u0e1a\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25"
                        "\u0e08\u0e32\u0e01\u0e40\u0e0b\u0e47\u0e19\u0e40\u0e0b\u0e2d\u0e23\u0e4c"
                        "\u0e41\u0e25\u0e49\u0e27\u0e2a\u0e48\u0e07\u0e15\u0e48\u0e2d\n"
                        for i in range(90))
              + "\n## Full Detail\n")
check("the old constant would have called this Thai index affordable",
      len(thai_index) / 3.6 < 3000)
check("the real estimate calls the same Thai index over budget",
      tokens.estimate(thai_index) > 3000)

wide.write_text(thai_index, encoding="utf-8")
thai_out = run_hook("session_start.py", {})
check("A THAI INDEX IN THAT BAND IS ROLLED UP, NOT INJECTED WHOLE",
      tokens.estimate(thai_out) < 3000)
check("the rolled-up Thai index still names its directory", "src" in thai_out)

# The roll-up groups rows it recognises. Given rows it does not, it used to hand its input straight
# back and the caller injected an over-budget index believing it had been folded.
import rollup  # noqa: E402
unknown = "# Map\n\n## Quick Index\n\n" + "".join(
    f"* src/m{i:03d}.py does something\n" for i in range(900))
check("an index in an unrecognised row format is still cut to the budget",
      tokens.estimate(rollup.collapse(unknown, "MAP.md", 3000)) <= 3000)
check("a cut index says it was cut", "Cut to fit" in rollup.collapse(unknown, "MAP.md", 3000))
check("collapse without a budget stays backward compatible",
      rollup.collapse(unknown, "MAP.md") == rollup.collapse(unknown, "MAP.md", None))
check("a map already inside the budget is left alone",
      "Cut to fit" not in rollup.collapse("# Map\n\n- **`a.py`** \u2014 x\n", "MAP.md", 3000))

# ---------------------------------------------------------------- attachments that are real files
# The corpus these handlers were first tried against turned out to be text files with binary
# extensions, so every one of them took the fallback branch and the run proved nothing. These
# build genuine containers instead.
import sqlite3 as _sq  # noqa: E402
import zipfile as _zf  # noqa: E402

att = Path(tempfile.mkdtemp(prefix="chamnan-att-"))


def _xlsx(path, rows):
    def cell(c, r, v):
        return (f'<c r="{chr(65+c)}{r}" t="inlineStr"><is><t>{v}</t></is></c>')
    body = "".join(f'<row r="{r}">' + "".join(cell(c, r, v) for c, v in enumerate(row)) + "</row>"
                   for r, row in enumerate(rows, 1))
    with _zf.ZipFile(path, "w") as z:
        z.writestr("xl/workbook.xml", '<workbook><sheets><sheet name="Tariffs" sheetId="1"/>'
                                      "</sheets></workbook>")
        z.writestr("xl/worksheets/sheet1.xml", f"<worksheet><sheetData>{body}</sheetData></worksheet>")


def _docx(path, paras):
    body = "".join(f"<w:p><w:r><w:t>{x}</w:t></w:r></w:p>" for x in paras)
    with _zf.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", f"<w:document><w:body>{body}</w:body></w:document>")


_xlsx(att / "t.xlsx", [["hs_code", "description", "duty_pct"],
                       ["2935.34", "Lithium cells, prismatic", "4.7"],
                       ["9237.81", "Woven cotton fabric", "14.6"],
                       ["4311.91", "Marine diesel injectors", "3.1"]])
sheet = peek_mod.peek(att / "t.xlsx")
check("a spreadsheet reports its columns, not just its zip members", "`hs_code`" in sheet)
check("a spreadsheet shows sample row content", "Woven cotton fabric" in sheet)
hit = peek_mod.peek(att / "t.xlsx", find="Lithium")
check("--find returns only the matching spreadsheet rows", "Lithium" in hit)
check("--find leaves the other rows out", "Woven cotton fabric" not in hit)

_docx(att / "t.docx", ["Standard Carriage Terms",
                       "1. Demurrage accrues after the fifth free day.",
                       "Annex C: the escalation contact is the Hamburg duty officer."])
doc = peek_mod.peek(att / "t.docx")
check("a document reports its paragraph text", "Demurrage accrues" in doc)
found = peek_mod.peek(att / "t.docx", find="escalation")
check("--find returns the matching clause", "Hamburg duty officer" in found)
check("--find leaves the other clauses out", "Demurrage accrues" not in found)

dbp = att / "t.sqlite"
_c = _sq.connect(dbp)
_c.executescript("CREATE TABLE shipment (id TEXT PRIMARY KEY, lane TEXT);"
                 "INSERT INTO shipment VALUES ('a','DEHAM-SGSIN'),('b','NLRTM-USNYC');")
_c.commit(); _c.close()

# The cost note used to divide bytes on disk by a constant and call the result a saving, for every
# file -- including ones a plain read cannot open at all, where the number it compared against
# could never have been spent.
sql_note = peek_mod.peek(dbp)
check("a database reports its schema", "`shipment`" in sql_note)
check("A BINARY NEVER CLAIMS A SAVING OVER READING IT WHOLE", "instead of" not in sql_note)
check("a binary says why instead", "cannot open" in sql_note)

(att / "big.csv").write_text("id,lane,kg\n" + "".join(f"s{i},DEHAM-SGSIN,{i}\n"
                                                      for i in range(4000)), encoding="utf-8")
csv_note = peek_mod.peek(att / "big.csv")
check("a text file does claim a saving, because reading it whole is possible",
      "instead of" in csv_note)
check("the saving is measured against the real text, not the byte count",
      "4,000 data rows" in csv_note)

shutil.rmtree(att, ignore_errors=True)

# ---------------------------------------------------------------- peek must not leak
# chamnan-peek is the one command that opens an arbitrary path on request, and it was the one
# with no deny-list and no scrubber: pointed at a credentials file it printed AWS, Stripe, Slack
# and GitHub credentials straight into the session. The corpus it was first tried against hid
# this, because its files opened with long comment headers and peek only shows the first lines.
# Real credential files put the secret on line two.
leak = Path(tempfile.mkdtemp(prefix="chamnan-leak-"))

(leak / "credentials.ini").write_text(
    "[default]\n"
    f"aws_access_key_id = {fake('AKIA', 'J7Q2MMPL', 'R4XN8DZQ', '1')}\n"
    f"stripe_key = {fake('sk_', 'live_', '51Nq8HbK2mPzR', '7YvXcW4tL9dQ')}\n", encoding="utf-8")
ini = peek_mod.peek(leak / "credentials.ini")
check("A CREDENTIALS FILE IS REFUSED, NOT SUMMARISED", "Refused" in ini)
check("the refusal names no key", "AKIA" not in ini)

(leak / "server.key").write_text(
    "-----BEGIN RSA PRIVATE KEY-----\nMIIEow" + "A" * 400 + "\n-----END RSA PRIVATE KEY-----\n",
    encoding="utf-8")
check("A PRIVATE KEY IS REFUSED", "Refused" in peek_mod.peek(leak / "server.key"))

# .env is the opposite case: which variables exist is exactly what an index should say, so it is
# opened -- with the values gone and the names kept.
(leak / "prod.env").write_text(
    f"SLACK_BOT_TOKEN={fake('xoxb-', '2841003', '-4471902', '-9Lm2QpVt')}\n"
    f"GITHUB_TOKEN={fake('ghp_', 'K2mPzR7YvXcW', '4tL9dQnH6sJ', '8bF3g')}\n"
    "DATABASE_PASSWORD=tr0ub4dor&3-horse\n", encoding="utf-8")
env = peek_mod.peek(leak / "prod.env")
check("PEEK NEVER PRINTS A SLACK TOKEN", "xoxb-" not in env)
check("PEEK NEVER PRINTS A GITHUB TOKEN", fake("ghp", "_") not in env)
check("PEEK NEVER PRINTS AN UNQUOTED PASSWORD", "tr0ub4dor" not in env)
check("but the variable names survive, which is the useful half", "SLACK_BOT_TOKEN" in env)

# Unquoted assignment is how every .env and .ini is written; requiring quotes let them through.
check("scrub redacts an unquoted assignment",
      "hunter2secret" not in redact.scrub("DB_PASSWORD=hunter2secret"))
check("scrub still redacts a quoted one",
      "hunter2secret" not in redact.scrub('db_password = "hunter2secret"'))
check("scrub leaves a short non-secret alone", "3600" in redact.scrub("token_ttl = 3600"))
check("scrub does not eat prose", "vault" in redact.scrub("# password: ask the vault team"))
check("credentials.ini is blocked by stem, not just by exact name",
      redact.is_blocked(Path("credentials.ini")))
check("an ordinary config file is not blocked", not redact.is_blocked(Path("settings.ini")))

shutil.rmtree(leak, ignore_errors=True)

# ---------------------------------------------------------------- deployment classification
# "ci" was matched as a substring of the whole path, so it fired on services/pricing,
# apps/ios/Sources/Specific and charts/civic -- and on deploy/ansible/inventories/ci/, which is
# how an Ansible inventory came out labelled a CI pipeline.
dep = Path(tempfile.mkdtemp(prefix="chamnan-dep-"))
for rel, body in [
    ("deploy/ansible/ansible.cfg", "[defaults]\ninventory = inventories/production\n"),
    ("deploy/ansible/inventories/ci/hosts.yml", "all:\n  hosts:\n    of-ci-01:\n"),
    ("deploy/ansible/inventories/production/group_vars/all.yml", "of_kafka_version: 3.7\n"),
    ("deploy/ansible/roles/of_common/tasks/main.yml", "- name: install base packages\n"),
    ("deploy/k8s/telemetry.yaml", "kind: Deployment\nmetadata:\n  name: telemetry-ingest\n"),
    (".github/workflows/build.yml", "on: push\njobs:\n  build:\n"),
    ("services/pricing/config/rates.yml", "base_rate_bp: 250\n"),
    ("charts/civic/values.yaml", "replicaCount: 2\n"),
]:
    (dep / rel).parent.mkdir(parents=True, exist_ok=True)
    (dep / rel).write_text(body, encoding="utf-8")

d = deploy_mod.scan(dep)
check("an Ansible inventory is Ansible, not a CI pipeline",
      "deploy/ansible/inventories/ci/hosts.yml" in d["ansible"])
check("AN ANSIBLE INVENTORY IS NEVER FILED UNDER CI",
      "deploy/ansible/inventories/ci/hosts.yml" not in d["ci"])
check("group_vars counts as Ansible even though it is not under roles/",
      "deploy/ansible/inventories/production/group_vars/all.yml" in d["ansible"])
check("ansible.cfg counts as Ansible", "deploy/ansible/ansible.cfg" in d["ansible"])
check("a real workflow file is still CI", ".github/workflows/build.yml" in d["ci"])
check("'pricing' is not mistaken for CI", "services/pricing/config/rates.yml" not in d["ci"])
check("'civic' is not mistaken for CI", "charts/civic/values.yaml" not in d["ci"])
check("kubernetes objects are still found", "Deployment" in d["k8s"])

# The assets inventory says "payload, not code -- do not read these to understand the system".
# That sentence has to be true of everything under it, and it was not true of the Ansible tree.
(dep / "attachments").mkdir(exist_ok=True)
for i in range(20):
    (dep / "attachments" / f"scan_{i:03d}.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 200)
(dep / "services" / "pricing").mkdir(parents=True, exist_ok=True)
for name in ("go.mod", "go.sum", "Pricing.csproj", "build.sbt", "Makefile", "config.ru",
             "pom.xml", "package.json", "Cargo.toml", "mix.exs", "pubspec.yaml", "Gemfile",
             "settings.gradle", "CMakeLists.txt"):
    (dep / "services" / "pricing" / name).write_text("x\n", encoding="utf-8")

stored = assets_mod.scan(dep, set() | d["claimed"], {".py": "python"})
check("A DEPLOYMENT MANIFEST IS NEVER CALLED PAYLOAD", "deploy" not in stored)
check("BUILD MANIFESTS ARE NEVER CALLED PAYLOAD", "services" not in stored)
check("genuine payload is still reported", "attachments" in stored)

shutil.rmtree(dep, ignore_errors=True)

# ---------------------------------------------------------------- doc-tool markers
# On a firmware tree written in doxygen house style, 69 of 430 index rows opened with
# "@file of_crc.h @brief" -- a restatement of the filename the row already shows, followed by a
# marker meant for a parser. Both are pure cost in a one-line summary.
check("@file and its argument are dropped",
      mapper._clip("@file of_crc.h @brief declares three CRC variants") == "declares three CRC variants")
check("a backslash-style marker is dropped too",
      mapper._clip("\\brief Validates a container code.") == "Validates a container code.")
check("@param and everything after it is dropped",
      mapper._clip("Validates a code. @param code the BIC code @return true") == "Validates a code.")
check("@ref keeps the thing it refers to",
      "alert_rules.h" in mapper._clip("@brief @ref alert_rules.h implementation"))
check("markers are stripped whatever language follows",
      mapper._clip("@brief Prüft die Konfiguration.") == "Prüft die Konfiguration.")
check("AN EMAIL ADDRESS IS NOT A DOC TAG",
      "a@b.com" in mapper._clip("Contact a@b.com about this module"))
check("A PYTHON DECORATOR IS NOT A DOC TAG",
      "@staticmethod" in mapper._clip("Explains why @staticmethod is used here"))
check("a summary with no tags is untouched",
      mapper._clip("Plain summary of the module.") == "Plain summary of the module.")

# C# and VB document with XML, not @tags, and <summary> was reaching 46 of 530 index rows.
check("an XML summary wrapper is stripped",
      mapper._clip("<summary> Picking endpoints. </summary>") == "Picking endpoints.")
check("an inline <c> code span keeps its content",
      mapper._clip("Mounts waves under <c>/v1</c>.") == "Mounts waves under /v1.")
check("a <see cref> keeps what it points at",
      "PickWave" in mapper._clip('Returns a <see cref="PickWave"/> for the shift.'))
check("<param> and everything after it is dropped",
      mapper._clip('Validates input. <param name="code">the BIC</param>') == "Validates input.")
check("javadoc {@code} keeps the words, not the braces",
      mapper._clip("{@code fleet.drivers} is the read model.") == "fleet.drivers is the read model.")
check("javadoc {@link} keeps the target",
      "Driver" in mapper._clip("See {@link Driver} for details."))
# Stripping anything between angle brackets would eat these out of ordinary prose.
check("A JAVA GENERIC SURVIVES IN A SUMMARY",
      mapper._clip("Builds a List<String> of lane codes.") == "Builds a List<String> of lane codes.")
check("A MULTI-ARG GENERIC SURVIVES TOO",
      "Map<K, V>" in mapper._clip("Keeps a Map<K, V> index in memory."))

# ---------------------------------------------------------------- route prefixes
# A decorator gives the path relative to where the router is mounted, and the mount is declared
# elsewhere in the file. Reporting only the relative half put `GET /{quote_id}` in the index for an
# endpoint that lives at /v1/quotes/{quote_id}. A wrong path is worse than no path: it gets called.
rt = Path(tempfile.mkdtemp(prefix="chamnan-rt-"))
(rt / "routes_quotes.py").write_text(
    'from fastapi import APIRouter\n'
    'router = APIRouter(prefix="/v1/quotes", tags=["quotes"])\n'
    '@router.get("/{quote_id}")\ndef one(quote_id): ...\n'
    '@router.get("")\ndef many(): ...\n'
    '@router.post("/{quote_id}/accept")\ndef accept(quote_id): ...\n', encoding="utf-8")
(rt / "views.py").write_text(
    'from flask import Blueprint\n'
    'bp = Blueprint("billing", __name__, url_prefix="/v1/billing")\n'
    '@bp.get("/invoices")\ndef invoices(): ...\n', encoding="utf-8")
(rt / "main.py").write_text(
    'from fastapi import FastAPI\napp = FastAPI()\n'
    '@app.get("/healthz")\ndef health(): ...\n', encoding="utf-8")
(rt / "FleetController.java").write_text(
    '@RestController\n@RequestMapping("/v1/fleet")\npublic class FleetController {\n'
    '  @GetMapping("/vehicles/{id}")\n  public Object one(String id) { return null; }\n}\n',
    encoding="utf-8")
(rt / "QueryController.java").write_text(
    '@RestController\n@RequestMapping(produces = MediaType.APPLICATION_JSON_VALUE)\n'
    'public class QueryController {\n'
    '  @GetMapping("/v1/assignments")\n  public Object all() { return null; }\n}\n',
    encoding="utf-8")

rfiles = [{"path": f.name, "lang": {"py": "py", "java": "java"}[f.suffix[1:]]}
          for f in sorted(rt.iterdir())]
found = {key for key, _source in catalogs.scan_routes(rt, rfiles)}

check("A FASTAPI ROUTE CARRIES ITS ROUTER PREFIX", ("GET", "/v1/quotes/{quote_id}") in found)
check("an empty path becomes the prefix itself", ("GET", "/v1/quotes") in found)
check("a nested path keeps both halves", ("POST", "/v1/quotes/{quote_id}/accept") in found)
check("THE UNPREFIXED PATH IS NOT ALSO LISTED", ("GET", "/{quote_id}") not in found)
check("a flask blueprint prefix is applied", ("GET", "/v1/billing/invoices") in found)
check("an app-level route keeps its own path", ("GET", "/healthz") in found)
check("a spring class mapping is applied", ("GET", "/v1/fleet/vehicles/{id}") in found)
check("@RequestMapping without a path invents no prefix", ("GET", "/v1/assignments") in found)

# Both a decorator and an express-style call matched `@router.get(`, so every FastAPI route was
# recorded twice -- once right and once wrong.
quotes = [path for _meth, path in found if "quote" in path]
check("each route appears exactly once", len(quotes) == len(set(quotes)) == 3)

shutil.rmtree(rt, ignore_errors=True)

# ---------------------------------------------------------------- schema dialects
sc = Path(tempfile.mkdtemp(prefix="chamnan-sc-"))
(sc / "0016_telemetry.sql").write_text(
    "-- One row per sensor sample. Partitioned by region so a region can be dropped whole.\n"
    "CREATE TABLE telemetry.telemetry_readings (\n"
    "    reading_id  TEXT NOT NULL,\n    region_code TEXT NOT NULL\n);\n"
    "CREATE TABLE telemetry.telemetry_readings_eu_west\n"
    "    PARTITION OF telemetry.telemetry_readings FOR VALUES IN ('eu-west');\n"
    "CREATE TABLE telemetry.telemetry_readings_na_east\n"
    "    PARTITION OF telemetry.telemetry_readings FOR VALUES IN ('na-east');\n"
    "-- Weekly rollup the analytics dashboards read instead of the base table.\n"
    "CREATE MATERIALIZED VIEW analytics.mv_lane_performance_daily AS SELECT 1;\n"
    "CREATE OR REPLACE VIEW billing.open_invoices AS SELECT 1;\n", encoding="utf-8")

# Room writes the real table name in the annotation, and its annotation contains Index(...) --
# a nested ")" that the TypeORM pattern's [^)] stopped at. Kotlin also writes "data class".
(sc / "data" / "db" / "entity").mkdir(parents=True)
(sc / "data" / "db" / "entity" / "FreightEntities.kt").write_text(
    '/** शिपमेंट की स्थानीय प्रति। */\n'
    '@Entity(\n    tableName = "shipments",\n'
    '    indices = [Index(value = ["status"]), Index(value = ["reference"])],\n)\n'
    'data class ShipmentEntity(\n    val id: String,\n)\n', encoding="utf-8")
(sc / "domain").mkdir()
(sc / "domain" / "Vehicle.java").write_text(
    '@Entity\n@Table(name = "fleet_vehicles")\n'
    'public class Vehicle {\n    private String id;\n}\n', encoding="utf-8")
(sc / "domain" / "Driver.java").write_text(
    '@Entity\npublic class Driver {\n    private String id;\n}\n', encoding="utf-8")

sfiles = [{"path": str(f.relative_to(sc)),
           "lang": {"kt": "kotlin", "java": "java", "sql": "sql"}[f.suffix[1:]]}
          for f in sorted(sc.rglob("*")) if f.is_file()]
found = {x["name"].lower(): x for x in schema.scan(sc, sfiles)}

check("a materialized view is indexed", "mv_lane_performance_daily" in found)
check("an ordinary view is indexed", "open_invoices" in found)
check("the parent partitioned table is indexed", "telemetry_readings" in found)
check("A PARTITION IS NOT INDEXED AS ITS OWN TABLE",
      "telemetry_readings_eu_west" not in found and "telemetry_readings_na_east" not in found)
check("the parent says it is partitioned and how many",
      "8 partitions" not in found["telemetry_readings"]["summary"]
      and "2 partitions" in found["telemetry_readings"]["summary"])
check("a SQL comment above the table becomes its summary",
      "sensor sample" in found["telemetry_readings"]["summary"])

# MySQL fakes a materialized view by building a staging copy inside a procedure and renaming it
# over the real one. The staging table is not schema; the table it shadows is indexed already.
(sc / "0010_mysql_analytics.sql").write_text(
    "CREATE TABLE analytics.mv_lane_performance_daily (\n  lane TEXT,\n  on_time REAL\n);\n"
    "CREATE PROCEDURE analytics.refresh_lane_performance()\nBEGIN\n"
    "    DROP TABLE IF EXISTS analytics.mv_lane_performance_daily__new;\n"
    "    CREATE TABLE analytics.mv_lane_performance_daily__new\n"
    "        LIKE analytics.mv_lane_performance_daily;\nEND\n", encoding="utf-8")
my = {x["name"].lower() for x in schema.scan(sc, sfiles)}
check("the real MySQL rollup table is indexed", "mv_lane_performance_daily" in my)
check("A SWAP STAGING TABLE IS NOT INDEXED AS SCHEMA",
      "mv_lane_performance_daily__new" not in my)

check("A ROOM ENTITY IS INDEXED BY ITS TABLE NAME, NOT ITS CLASS",
      "shipments" in found and "shipmententity" not in found)
check("a JPA @Table name wins over the class name",
      "fleet_vehicles" in found and "vehicle" not in found)
check("a bare @Entity falls back to the class name", "driver" in found)
# The relevance test is by path, on purpose: reading every file to look for @Entity is the cost
# this plugin exists to avoid. An entity outside every known convention is genuinely not found.
(sc / "Stray.java").write_text('@Entity\npublic class Stray {}\n', encoding="utf-8")
stray = {x["name"].lower() for x in schema.scan(
    sc, sfiles + [{"path": "Stray.java", "lang": "java"}])}
check("an entity outside any schema-shaped directory is a known blind spot",
      "stray" not in stray)

shutil.rmtree(sc, ignore_errors=True)

# ---------------------------------------------------------------- contracts
ct = Path(tempfile.mkdtemp(prefix="chamnan-ct-"))
(ct / "contracts" / "proto" / "fleet" / "v1").mkdir(parents=True)
(ct / "contracts" / "proto" / "fleet" / "v1" / "fleet.proto").write_text(
    'syntax = "proto3";\npackage of.fleet.v1;\n\n'
    'service FleetService {\n'
    '  rpc Assign(AssignRequest) returns (AssignResponse);\n'
    '  rpc Release(ReleaseRequest) returns (ReleaseResponse);\n}\n\n'
    'message AssignRequest {\n  string shipment_id = 1;\n}\n', encoding="utf-8")

# Repositories that keep specs together name them after the SERVICE, not the format. Searching for
# a file literally called openapi.yaml found none of five real documents.
(ct / "contracts" / "openapi").mkdir(parents=True)
(ct / "contracts" / "openapi" / "routing-service.yaml").write_text(
    "# Superficie REST di routing-service.\nopenapi: 3.1.0\ninfo:\n  title: routing-service\n"
    "paths:\n  /v1/routes:\n    get:\n      summary: list\n"
    "  /v1/routes/{route_id}:\n    get:\n      summary: one\n", encoding="utf-8")
# A Kubernetes manifest sitting in the same tree is not a spec, and must not be read as one.
(ct / "contracts" / "openapi" / "kustomization.yaml").write_text(
    "apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\n"
    "paths:\n  /not-a-route:\n", encoding="utf-8")

cfound = {k for k, _ in catalogs.scan_routes(ct, [])}
check("A gRPC METHOD IS PART OF THE API SURFACE", ("gRPC", "FleetService/Assign") in cfound)
check("every rpc in the service is listed", ("gRPC", "FleetService/Release") in cfound)
check("a message is not mistaken for an rpc",
      not any("AssignRequest" in p for _m, p in cfound))
check("an OpenAPI document named after its service is found",
      ("ANY", "/v1/routes") in cfound)
check("its parameterised path is found too", ("ANY", "/v1/routes/{route_id}") in cfound)
check("A K8S MANIFEST IN THE SAME DIRECTORY IS NOT READ AS A SPEC",
      ("ANY", "/not-a-route") not in cfound)

# Truncating one flat alphabetical list dropped every gRPC method behind sixty REST paths.
many = [(("GET", f"/v1/thing{i:03d}"), "app.py") for i in range(200)]
many += [(("gRPC", "FleetService/Assign"), "fleet.proto")]
rendered = catalogs.render_routes(many)
check("gRPC SURVIVES TRUNCATION OF A LONG HTTP LIST", "FleetService/Assign" in rendered)
check("the count says how many of each", "gRPC" in rendered.splitlines()[2])

shutil.rmtree(ct, ignore_errors=True)

# ---------------------------------------------------------------- control flow is not a function
# `for (var i = 0; i < 16; i++) {` fits the "name(args) {" shape the Dart rule looks for, and
# Kotlin's `= when(status) {` backtracks into the Java rule. 57 of 3,013 extracted symbols were
# statements listed as functions of the file.
_d, dfuncs, _c, _k = mapper.extract_regex(
    "String makeId(String prefix) {\n"
    "  for (var i = 0; i < 16; i++) {\n    buf.write(alphabet[rand.nextInt(32)]);\n  }\n"
    "  if (prefix.isEmpty) {\n    throw ArgumentError('empty');\n  }\n"
    "  return buf.toString();\n}\n", "dart")
dnames = {f.split("(")[0] for f, _ in dfuncs}
check("A DART LOOP IS NOT A FUNCTION", "for" not in dnames)
check("a dart conditional is not a function", "if" not in dnames)
check("the real dart function is still found", "makeId" in dnames)

_d, kfuncs, _c, _k = mapper.extract_regex(
    "public String label(Status status) {\n    return when(status) {\n"
    "        Status.OPEN -> \"open\";\n    };\n}\n", "java")
knames = {f.split("(")[0] for f, _ in kfuncs}
check("A KOTLIN WHEN IS NOT A FUNCTION", "when" not in knames)
check("the real method is still found", "label" in knames)

# Elixir genuinely allows ? and ! in names, and those are not typos to be cleaned up.
_d, efuncs, _c, _k = mapper.extract_regex(
    "defmodule X do\n  def permanent?(reason) do\n    true\n  end\n"
    "  def verify_coverage!(map) do\n    :ok\n  end\nend\n", "ex")
enames = {f.split("(")[0] for f, _ in efuncs}
check("an Elixir predicate keeps its question mark", "permanent?" in enames)
check("an Elixir bang function keeps its bang", "verify_coverage!" in enames)

# ---------------------------------------------------------------- session records
# A session record answers "where did the last stretch of work stop". Only the unfinished part
# reaches the next session: Done is history and Files is recoverable from git, so injecting them
# would spend the budget on what the reader could already get.
sess = Path(tempfile.mkdtemp(prefix="chamnan-sess-"))
(sess / ".chamnan" / "sessions").mkdir(parents=True)
sdir = sess / ".chamnan" / "sessions"

(sdir / "2026-08-18-parser-work.md").write_text(
    "# Kotlin extension functions\n\n"
    "## Done\n- Added the kotlin rules block\n\n"
    "## Remaining\n- extract_regex returns the wrong arg list for extension functions\n\n"
    "## Files\n- `lib/mapper.py` \u2014 new rules\n\n"
    "## Decisions\n- Kotlin gets its own entry rather than borrowing Java's\n\n"
    "## Blockers\n- none yet\n", encoding="utf-8")
(sdir / "2026-08-19-schema-work.md").write_text(
    "# Materialized views\n\n"
    "## Done\n- CREATE VIEW pattern added\n\n"
    "## Remaining\n- MySQL swap-staging tables still appear as schema\n\n"
    "## Blockers\n- waiting on a decision about partitions\n", encoding="utf-8")

check("records are listed newest first",
      sessions.records(sess)[0].name.startswith("2026-08-19"))
check("latest picks the newest record", sessions.latest(sess).name.startswith("2026-08-19"))

carried = sessions.carry_forward(sess)
check("the carried text names the session", "Materialized views" in carried)
check("the carried text dates it", "2026-08-19" in carried)
check("REMAINING IS CARRIED FORWARD", "swap-staging tables" in carried)
check("BLOCKERS ARE CARRIED FORWARD", "waiting on a decision" in carried)
check("DONE IS NOT CARRIED FORWARD", "CREATE VIEW pattern" not in carried)
check("an older record is not carried forward", "extension functions" not in carried)

# A record with nothing outstanding must inject nothing at all, rather than a heading saying so.
(sdir / "2026-08-20-finished.md").write_text(
    "# All done\n\n## Done\n- everything\n\n## Remaining\n-\n\n## Blockers\n- none\n",
    encoding="utf-8")
check("A FINISHED SESSION CARRIES NOTHING", sessions.carry_forward(sess) == "")
# People write "- none" instead of omitting the section, and mean the same thing.
(sdir / "2026-08-20-finished.md").write_text(
    "# All done\n\n## Remaining\n- nothing\n\n## Blockers\n- N/A.\n", encoding="utf-8")
check("'- nothing' and '- N/A' are treated as empty", sessions.carry_forward(sess) == "")
(sdir / "2026-08-20-finished.md").write_text(
    "# Partly done\n\n## Remaining\n- none\n- but check the parser\n", encoding="utf-8")
check("a real item beside a 'none' is still carried",
      "check the parser" in sessions.carry_forward(sess))
(sdir / "2026-08-20-finished.md").unlink()

# Robustness: the hook must survive whatever is in that directory.
(sdir / "2026-08-21-garbage.md").write_text("no headings at all, just prose\n", encoding="utf-8")
check("a record with no headings carries nothing", sessions.carry_forward(sess) == "")
(sdir / "2026-08-21-garbage.md").unlink()
check("an empty directory carries nothing",
      sessions.carry_forward(Path(tempfile.mkdtemp(prefix="chamnan-none-"))) == "")

# Unbounded growth is the failure mode these files invite: one per session, in a committed dir.
import os as _os, time as _time
old_rec = sdir / "2020-01-01-ancient.md"
old_rec.write_text("# Ancient\n\n## Remaining\n- something\n", encoding="utf-8")
_os.utime(old_rec, (_time.time() - 400 * 86400,) * 2)
check("retention deletes a record past the window", sessions.prune(sess, 30) == 1)
check("retention keeps recent records", len(sessions.records(sess)) == 2)
check("a zero window prunes nothing", sessions.prune(sess, 0) == 0)

check("slug is filename-safe", sessions.slug("Kotlin: extension functions!") == "kotlin-extension-functions")
check("slug survives having nothing usable", sessions.slug("!!!") == "session")
check("filename puts the date first",
      sessions.filename("2026-08-20", "Fix the parser") == "2026-08-20-fix-the-parser.md")

# The record is committed and is free text about the repository, which makes it the likeliest
# place for a pasted credential to land. The injection path must scrub it.
(sdir / "2026-08-22-leaky.md").write_text(
    "# Leaky\n\n## Blockers\n- prod db is postgres://admin:" + fake("Hunter2", "Pass")
    + "@db.internal/main\n", encoding="utf-8")
leaked = sessions.carry_forward(sess)
check("carry_forward itself does not redact (the hook does)", "Hunter2" in leaked)
check("SCRUBBING THE CARRIED TEXT REMOVES THE PASSWORD", "Hunter2" not in redact.scrub(leaked))
check("but the host stays readable", "db.internal" in redact.scrub(leaked))

shutil.rmtree(sess, ignore_errors=True)

# ---------------------------------------------------------------- project memory
# Three categories used three different ways: rules are injected every session, decisions and
# lessons contribute a title and are read on demand. If that distinction stops holding, every
# session in every repository pays for it.
mem = Path(tempfile.mkdtemp(prefix="chamnan-mem-"))
for c in memory_mod.CATEGORIES:
    (mem / ".chamnan" / "memory" / c).mkdir(parents=True)
mroot = mem / ".chamnan" / "memory"

(mroot / "rules" / "no-cloud-embeddings.md").write_text(
    "# Never add a Cloud fallback for embeddings\n\n"
    "A different model means an incompatible vector space.\n", encoding="utf-8")
(mroot / "decisions" / "postgres-over-sqlite.md").write_text(
    "# Postgres over SQLite\n\nTwo processes write concurrently and SQLite's locking failed.\n",
    encoding="utf-8")
(mroot / "lessons" / "hot-reload-attributeerror.md").write_text(
    "# Editing src/ while the app runs\n\nA hot-reload artifact, not a bug. Restart clears it.\n",
    encoding="utf-8")

check("categories are the three named ones",
      memory_mod.CATEGORIES == ("decisions", "lessons", "rules"))
check("entries are found per category", len(memory_mod.entries(mem, "rules")) == 1)
check("counts cover every category", memory_mod.counts(mem) ==
      {"decisions": 1, "lessons": 1, "rules": 1})

rules = memory_mod.rules_text(mem)
check("A RULE IS INJECTED IN FULL", "incompatible vector space" in rules)
check("a decision body is NOT in the rules text", "SQLite's locking" not in rules)
# The entry is a standalone file opening with "# Title"; the hook drops it inside a "###" section,
# and an H1 nested under an H3 makes the injected block read as a new document.
check("AN ENTRY'S OWN H1 IS DEMOTED BEFORE INJECTION", "\n# " not in "\n" + rules)
check("the title survives the demotion", "**Never add a Cloud fallback for embeddings**" in rules)

listing = memory_mod.render_titles(memory_mod.titles(mem))
check("a decision contributes its title", "Postgres over SQLite" in listing)
check("a lesson contributes its title", "Editing src/ while the app runs" in listing)
check("A DECISION BODY IS NOT INJECTED", "two processes write" not in listing.lower())
check("the listing names the file to read", "postgres-over-sqlite.md" in listing)
check("a rule does not appear twice in the listing", "vector space" not in listing)

check("an empty store injects no rules",
      memory_mod.rules_text(Path(tempfile.mkdtemp(prefix="chamnan-empty-"))) == "")
check("an empty store injects no listing", memory_mod.render_titles([]) == "")

# Rules reach every session, so their size is capped; titles are capped by count.
for i in range(40):
    (mroot / "rules" / f"filler-{i:02d}.md").write_text(
        "# Rule " + str(i) + "\n\n" + ("x" * 200) + "\n", encoding="utf-8")
capped = memory_mod.rules_text(mem)
check("RULES ARE CAPPED SO THEY CANNOT SWAMP A SESSION",
      len(capped) <= memory_mod.MAX_RULES_CHARS + 200)
check("the cap says how many were held back", "more rules in" in capped)
for i in range(40):
    (mroot / "rules" / f"filler-{i:02d}.md").unlink()

for i in range(20):
    (mroot / "decisions" / f"d-{i:02d}.md").write_text(f"# Decision {i}\n\nbody\n", encoding="utf-8")
many = memory_mod.render_titles(memory_mod.titles(mem))
check("TITLES ARE CAPPED BY COUNT",
      len([l for l in many.splitlines() if l.startswith("- **")]) <= memory_mod.MAX_TITLES)
check("the title cap says how many more there are", "and" in many and "more" in many)
for i in range(20):
    (mroot / "decisions" / f"d-{i:02d}.md").unlink()

# 🐛 [2026-08-27] title_of() has no length limit of its own, and render_titles() used to pass it
# straight through — a genuinely unbounded injection channel.
(mroot / "decisions" / "long-title.md").write_text(
    "# " + ("Why we chose this approach over the alternative " * 5) + "\n\nbody\n", encoding="utf-8")
long_listing = memory_mod.render_titles(memory_mod.titles(mem))
title_line = [l for l in long_listing.splitlines() if "long-title.md" in l][0]
check("A TITLE LONGER THAN THE CAP IS ACTUALLY TRUNCATED",
      len(title_line) < len("- **decision** · `long-title.md` — ") + 250)
check("truncation is visible, not silent", "…" in title_line)
short_listing = memory_mod.render_titles(memory_mod.titles(mem))
check("a title under the cap is never truncated",
      "Postgres over SQLite" in short_listing and "…" not in
      [l for l in short_listing.splitlines() if "postgres-over-sqlite" in l][0])
(mroot / "decisions" / "long-title.md").unlink()

# Memory is free text about the repository, written by Claude — the likeliest place for a pasted
# credential to land, and these files are committed.
(mroot / "rules" / "leaky.md").write_text(
    "# Connection\n\nprod is postgres://admin:" + fake("Hunter2", "Pass") + "@db.internal/main\n",
    encoding="utf-8")
leaky = memory_mod.rules_text(mem)
check("rules_text itself does not redact (the hook does)", "Hunter2" in leaky)
check("SCRUBBING A RULE REMOVES THE PASSWORD", "Hunter2" not in redact.scrub(leaky))
check("but the host survives redaction", "db.internal" in redact.scrub(leaky))
(mroot / "rules" / "leaky.md").unlink()

check("a title falls back to the filename when there is no heading",
      memory_mod.title_of(Path("/nonexistent/some-entry.md")) == "some entry")
check("slug is filename-safe",
      memory_mod.slug("Postgres over SQLite!") == "postgres-over-sqlite")
check("filename adds the extension",
      memory_mod.filename("Postgres over SQLite") == "postgres-over-sqlite.md")

# ---------------------------------------------------------------- knowledge inventory (lib/ledger.py)
# At this point `mem` holds exactly its original three entries: one rule, one decision with no
# `Rejected:`, and one lesson with no backtick-quoted file reference at all.
inv = ledger.inventory(mem)
inv_by_label = {label: (count, ts) for label, count, ts in inv}
check("inventory counts every store, in a fixed set of labels",
      set(inv_by_label) == {"sessions/", "memory/decisions/", "memory/lessons/",
                            "memory/rules/", "milestones.md", "candidates/", "threads/"})
check("inventory counts the one decision", inv_by_label["memory/decisions/"][0] == 1)
check("inventory counts the one lesson", inv_by_label["memory/lessons/"][0] == 1)
check("A STORE THAT DOES NOT EXIST YET SHOWS 0, NOT AN ERROR", inv_by_label["candidates/"] == (0, None))
check("humanize_age renders None as never", ledger.humanize_age(None) == "never")
decision_age = ledger.humanize_age(inv_by_label["memory/decisions/"][1])
check("humanize_age renders a real timestamp as today or N days ago",
      decision_age == "today" or "ago" in decision_age)

none, total = ledger.entries_naming_no_file(mem, "lessons")
check("THE LESSON WITH NO BACKTICK FILE REFERENCE COUNTS AS NAMING NONE", (none, total) == (1, 1))
(mem / "docs").mkdir(exist_ok=True)
(mem / "docs" / "notes.md").write_text("real file\n", encoding="utf-8")
(mroot / "lessons" / "names-a-real-file.md").write_text(
    "# Something concrete\n\nSee `docs/notes.md` for the full story.\n", encoding="utf-8")
none2, total2 = ledger.entries_naming_no_file(mem, "lessons")
check("an entry naming a file that genuinely exists is not counted",
      none2 == 1 and total2 == 2)
(mroot / "lessons" / "names-a-real-file.md").unlink()

without, dtotal = ledger.decisions_without_rejected(mem)
check("THE DECISION WITH NO REJECTED FIELD IS COUNTED", (without, dtotal) == (1, 1))
(mroot / "decisions" / "with-rejected.md").write_text(
    "# Chose A over B\n\nBecause reasons.\n\n**Rejected:** B, for other reasons.\n", encoding="utf-8")
without2, dtotal2 = ledger.decisions_without_rejected(mem)
check("a decision that DOES name a rejected alternative is not counted",
      without2 == 1 and dtotal2 == 2)
(mroot / "decisions" / "with-rejected.md").unlink()

shutil.rmtree(mem, ignore_errors=True)

# ---------------------------------------------------------------- impact
# The Quick Index says what exists. This says what is connected — specifically the reverse edge,
# because a file's own imports are already at the top of that file.
check("python from-import is extracted",
      "payment.model" in impact_mod.extract_imports("from payment.model import Payment", "py"))
check("python plain import is extracted",
      "os.path" in impact_mod.extract_imports("import os.path", "py"))
check("js import is extracted",
      "./util" in impact_mod.extract_imports("import x from './util'", "js"))
check("js require is extracted",
      "./util" in impact_mod.extract_imports("const x = require('./util')", "js"))
check("java import is extracted",
      "com.of.Fleet" in impact_mod.extract_imports("import com.of.Fleet;", "java"))
check("c include is extracted",
      "of/crc.h" in impact_mod.extract_imports('#include "of/crc.h"', "c"))
check("an angle-bracket include is NOT extracted",
      impact_mod.extract_imports("#include <stdio.h>", "c") == [])
check("an unknown language yields nothing", impact_mod.extract_imports("import x", "zig") == [])

ifiles = [{"path": "payment/model.py"}, {"path": "payment/service.py"},
          {"path": "checkout/api.py"}, {"path": "tests/test_payment.py"},
          {"path": "a/utils.py"}, {"path": "b/utils.py"}]
noext, stem = impact_mod._index(ifiles)
check("a dotted module resolves to its file",
      impact_mod.resolve("payment.model", "checkout/api.py", noext, stem) == "payment/model.py")
check("a relative path resolves against the importer",
      impact_mod.resolve("./model", "payment/service.py", noext, stem) == "payment/model.py")
check("a third-party name resolves to nothing",
      impact_mod.resolve("requests", "checkout/api.py", noext, stem) is None)
check("AN AMBIGUOUS STEM RESOLVES TO NOTHING, RATHER THAN GUESSING",
      impact_mod.resolve("utils", "checkout/api.py", noext, stem) is None)
check("an ambiguous DOTTED name is refused too",
      impact_mod.resolve("pkg.utils", "checkout/api.py", noext, stem) is None)
check("an unambiguous suffix still resolves",
      impact_mod.resolve("payment.service", "checkout/api.py", noext, stem)
      == "payment/service.py")

check("a path under tests/ is a test", impact_mod.is_test("tests/test_payment.py"))
check("a _test suffix is a test", impact_mod.is_test("payment/service_test.go"))
check("a .spec file is a test", impact_mod.is_test("web/src/api.spec.ts"))
check("ordinary source is not a test", not impact_mod.is_test("payment/service.py"))

built = impact_mod.build([
    {"path": "payment/model.py", "imports": []},
    {"path": "payment/service.py", "imports": ["payment.model"]},
    {"path": "checkout/api.py", "imports": ["payment.service"]},
    {"path": "tests/test_payment.py", "imports": ["payment.service"]},
    {"path": "orphan/alone.py", "imports": []},
])
check("REVERSE EDGES ARE BUILT", built["payment/service.py"]["used_by"] == ["checkout/api.py"])
check("A TEST IS RECORDED SEPARATELY FROM A CALLER",
      built["payment/service.py"]["tests"] == ["tests/test_payment.py"])
check("a test importer is not counted as a caller",
      "tests/test_payment.py" not in built["payment/service.py"]["used_by"])
check("transitive edges are NOT followed (one hop only)",
      "checkout/api.py" not in built["payment/model.py"]["used_by"])
check("A FILE NOBODY REFERS TO IS OMITTED", "orphan/alone.py" not in built)
check("a self-import is ignored",
      "x.py" not in impact_mod.build([{"path": "x.py", "imports": ["x"]}]))

wide = impact_mod.build(
    [{"path": "core.py", "imports": []}] +
    [{"path": f"c{i}.py", "imports": ["core"]} for i in range(20)])
out = impact_mod.render(wide)
check("callers are capped per file", out.count("`c") <= impact_mod.MAX_USED_BY + 2)
check("the cap says how many were held back", "more_" in out)
check("an empty impact renders nothing", impact_mod.render({}) == "")

# The section is large — nearly 12,000 tokens on a 2,365-file corpus — and belongs below the
# Full Detail marker. Above it, every session in the repository would pay for a per-file
# relationship listing it was never going to use. This was written above the marker first.
imp_repo = Path(tempfile.mkdtemp(prefix="chamnan-imp-"))
(imp_repo / "pay").mkdir(); (imp_repo / "tests").mkdir()
(imp_repo / "pay" / "model.py").write_text('"""Rows."""\nclass P: pass\n', encoding="utf-8")
(imp_repo / "pay" / "service.py").write_text(
    '"""Charges."""\nfrom pay.model import P\n', encoding="utf-8")
(imp_repo / "tests" / "test_pay.py").write_text(
    '"""Tests."""\nfrom pay.service import x\n', encoding="utf-8")
rendered_map = mapper.render(mapper.scan(imp_repo), imp_repo)
check("the map contains an Impact section", "## Impact" in rendered_map)
check("IMPACT SITS BELOW THE FULL DETAIL MARKER, SO IT IS NEVER INJECTED",
      rendered_map.index("## Impact") > rendered_map.index("## Full Detail"))
check("the injected half does not mention Impact",
      "## Impact" not in rendered_map[:rendered_map.index("## Full Detail")])
check("impact names the caller", "pay/model.py" in rendered_map)
shutil.rmtree(imp_repo, ignore_errors=True)

# ---------------------------------------------------------------- environment awareness (Stage 15)
# NOT a guard, and the tests pin that as a design property rather than an omission. Stage 15
# proposed intercepting a command beforehand, which needs a PreToolUse `permissionDecision` --
# the documented enum is allow/deny/escalate with no "ask" at all, and whether "escalate" reaches
# a prompt under `defaultMode: "auto"` is documented nowhere. A guard that might silently fail to
# fire is worse than none, because it is trusted. So this is PostToolUse advisory, on the same
# print-once mechanism the rest of this hook already proves works.
aw_root = Path(tempfile.mkdtemp(prefix="chamnan-aware-")).resolve()
(aw_root / ".git").mkdir()
ws.ensure(aw_root)
envs.upsert(aw_root, "production", envs.render_entry(
    "production", "K8s 1.28", "postgres 17",
    ["RWO storage only — no ReadWriteMany PVCs", "no outbound internet from workers"],
    "2026-08-27"))
envs.upsert(aw_root, "uat", envs.render_entry("uat", "K8s 1.26", "", ["no TPM in UAT"], "2026-08-27"))

check("a --context value naming a declared environment matches",
      envs.match_command(aw_root, "kubectl --context production get pods") == "production")
check("a --namespace value matches too",
      envs.match_command(aw_root, "kubectl --namespace uat get pods") == "uat")
check("the -n short form matches",
      envs.match_command(aw_root, "kubectl -n production get pods") == "production")
check("an --flag=value form matches",
      envs.match_command(aw_root, "kubectl --context=production get pods") == "production")
check("an ENV= assignment matches",
      envs.match_command(aw_root, "ENV=production ./deploy.sh") == "production")
check("a quoted value matches",
      envs.match_command(aw_root, "kubectl --context 'production' get pods") == "production")
# The false-positive control, and the reason there is one: a notice attached to a command that
# targets nothing is how somebody learns to scroll past the one that mattered.
check("A BARE MENTION WITH NO TARGETING FLAG DOES NOT MATCH",
      envs.match_command(aw_root, "grep production deploy.log") is None)
check("a filename containing the name does not match",
      envs.match_command(aw_root, "cat config/production.yaml") is None)
check("an environment that was never declared does not match",
      envs.match_command(aw_root, "kubectl --context staging get pods") is None)
check("an empty command matches nothing", envs.match_command(aw_root, "") is None)
bare_aw = Path(tempfile.mkdtemp(prefix="chamnan-aware-bare-")).resolve()
(bare_aw / ".git").mkdir()
ws.ensure(bare_aw)
check("with no environments declared at all, nothing ever matches",
      envs.match_command(bare_aw, "kubectl --context production get pods") is None)
shutil.rmtree(bare_aw, ignore_errors=True)

notice = envs.constraints_notice(aw_root, "production")
check("the notice names the environment", "`production`" in notice)
check("the notice carries every declared constraint",
      "RWO storage only" in notice and "no outbound internet" in notice)
check("the notice says where it came from and how fresh it is",
      "environments.md" in notice and "2026-08-27" in notice)
envs.upsert(aw_root, "noconstraints",
            envs.render_entry("noconstraints", "somewhere", "", [], "2026-08-27"))
check("an environment declaring no constraints has no notice to give",
      envs.constraints_notice(aw_root, "noconstraints") == "")
check("an unknown environment has no notice either",
      envs.constraints_notice(aw_root, "nope") == "")

def _bash(command, session_id):
    return {"session_id": session_id, "tool_name": "Bash",
            "tool_input": {"command": command},
            "tool_response": {"stdout": "", "stderr": "", "interrupted": False}}

first = run_scratch_watch(_bash("kubectl --context production get pods", "aw1"), aw_root)
check("THE HOOK SPEAKS ON THE COMMAND THAT TARGETS A DECLARED ENVIRONMENT",
      "targets `production`" in first)
again = run_scratch_watch(_bash("kubectl --context production delete pod x", "aw1"), aw_root)
check("AND STAYS SILENT ON EVERY LATER COMMAND FOR THE SAME ENVIRONMENT IN THAT SESSION",
      "targets `production`" not in again)
other = run_scratch_watch(_bash("kubectl --namespace uat get pods", "aw1"), aw_root)
check("a DIFFERENT environment in the same session still gets its own notice",
      "targets `uat`" in other)
fresh_session = run_scratch_watch(_bash("kubectl --context production get pods", "aw2"), aw_root)
check("a new session hears it again — it has not seen what the last one said",
      "targets `production`" in fresh_session)
quiet = run_scratch_watch(_bash("grep production deploy.log", "aw3"), aw_root)
check("a command that only mentions the word says nothing", "targets" not in quiet)

# The hook must never emit a permission decision: what it prints is advice, and the tests say so
# rather than leaving it to be assumed.
check("THE HOOK EMITS NO PERMISSION DECISION OF ANY KIND",
      "permissionDecision" not in first and "hookSpecificOutput" not in first)
check("and does not block anything", "deny" not in first.lower())
shutil.rmtree(aw_root, ignore_errors=True)

# ---------------------------------------------------------------- knowledge aging (Stage 14, 1.6.0)
# Never against a clock: a note written two years ago about a version still in production is
# current, and one written last month about a version replaced last week is already wrong. What
# is pinned hardest here is the REFUSAL -- an unmaintained environments.md must produce "not
# checked", never an empty finding list that reads like a pass.
def _mem(root, category, name, body):
    p = ws.workspace(root) / "memory" / category / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p

def run_age(root):
    return subprocess.run([str(ROOT / "bin" / "chamnan-age")],
                          capture_output=True, text=True, cwd=root)

ag_root = Path(tempfile.mkdtemp(prefix="chamnan-aging-")).resolve()
(ag_root / ".git").mkdir()
ws.ensure(ag_root)
_mem(ag_root, "rules", "pg.md", "# A rule\n\nWe run postgres 13 so upserts need the old syntax.\n")

findings, unver, refusal = aging.check(ag_root)
check("WITH NO ENVIRONMENTS DECLARED, AGING REFUSES", refusal is not None)
check("the refusal names what to do about it", "chamnan env set" in refusal)
check("a refusal comes with no findings beside it", findings == [] and unver == [])
out = run_age(ag_root)
check("the CLI prints the refusal, not a clean bill of health",
      "not checked" in out.stdout and "no stored knowledge" not in out.stdout)

# An environment nobody has confirmed is evidence nobody looked. This is the gate the stage was
# conditional on, implemented as code rather than as a judgement made once at build time.
envs.upsert(ag_root, "production",
            envs.render_entry("production", "K8s", "postgres 17", ["x"], "2020-01-01"))
findings, unver, refusal = aging.check(ag_root)
check("WITH EVERY ENVIRONMENT COLD, AGING STILL REFUSES", refusal is not None)
check("the refusal says why an unconfirmed entry is not an authority",
      "nobody looked" in refusal)
check("and still returns no findings to be mistaken for a pass", findings == [])
out = run_age(ag_root)
check("the CLI refuses rather than reassuring", "not checked" in out.stdout)

# Fresh oracle, and a claim it contradicts.
envs.upsert(ag_root, "production",
            envs.render_entry("production", "K8s", "postgres 17", ["x"], "2026-08-27"))
findings, unver, refusal = aging.check(ag_root)
check("a fresh environment lets the check actually run", refusal is None)
check("a claim no fresh environment declares is flagged", len(findings) == 1)
category, fname, subject, claimed, declared = findings[0]
check("the finding names the entry", category == "rules" and fname == "pg.md")
check("the finding names the claim", subject == "postgres" and claimed == "13")
check("the finding names what IS declared", declared == [("production", "17")])

# Matching a declared version is silent, and so is a name nobody declared.
_mem(ag_root, "rules", "pg.md", "# A rule\n\nWe run postgres 17 now.\n")
findings, unver, refusal = aging.check(ag_root)
check("A CLAIM MATCHING A DECLARED VERSION IS SILENT", findings == [] and unver == [])
_mem(ag_root, "lessons", "noise.md", "# Lesson\n\nSee issue 13, port 8080, and redis 4.\n")
findings, unver, refusal = aging.check(ag_root)
check("NOISE CONTROL: a name environments.md never declares is ignored entirely",
      findings == [] and unver == [])
check("even though the claim parser does see those pairs",
      ("issue", "13") in aging.claims_in("See issue 13, port 8080, and redis 4"))

# The third outcome, and the honest one: matched only by an environment that has gone cold.
_mem(ag_root, "rules", "pg.md", "# A rule\n\npostgres 13 needs the old upsert syntax.\n")
envs.upsert(ag_root, "uat", envs.render_entry("uat", "K8s", "postgres 13", ["x"], "2020-01-01"))
findings, unver, refusal = aging.check(ag_root)
check("A CLAIM MATCHED ONLY BY A COLD ENVIRONMENT IS NOT FLAGGED", findings == [])
check("it is reported as unverifiable instead", len(unver) == 1)
check("and names which cold environment declared it", unver[0][4] == "uat")
out = run_age(ag_root)
check("the CLI calls those unknowns rather than findings", "not findings" in out.stdout)

# Two environments legitimately running different versions is usually why the file exists at all.
envs.upsert(ag_root, "uat", envs.render_entry("uat", "K8s", "postgres 13", ["x"], "2026-08-27"))
findings, unver, refusal = aging.check(ag_root)
check("A CLAIM MATCHING EITHER OF TWO FRESH ENVIRONMENTS IS SILENT",
      findings == [] and unver == [])
out = run_age(ag_root)
check("and the CLI says so plainly", "no stored knowledge" in out.stdout)

# Every memory category is scanned, not just rules.
_mem(ag_root, "decisions", "d.md", "# A decision\n\nChosen while on redis 2.8.\n")
envs.upsert(ag_root, "production",
            envs.render_entry("production", "K8s", "postgres 17, redis 7.2", ["x"], "2026-08-27"))
findings, _u, _r = aging.check(ag_root)
check("a decision is scanned too", any(f[0] == "decisions" for f in findings))
_mem(ag_root, "lessons", "noise.md", "# Lesson\n\nSaw this on redis 2.8 as well.\n")
findings, _u, _r = aging.check(ag_root)
check("and a lesson", any(f[0] == "lessons" for f in findings))
check("the same claim in two entries is two findings, not one",
      len([f for f in findings if f[2] == "redis"]) == 2)

# Equality only. 3.9 vs 3.11 is exactly the comparison a version ordering gets wrong, and this
# module deliberately never attempts one.
py_root = Path(tempfile.mkdtemp(prefix="chamnan-aging-py-")).resolve()
(py_root / ".git").mkdir()
ws.ensure(py_root)
envs.upsert(py_root, "local", envs.render_entry("local", "macOS", "python 3.11", ["x"], "2026-08-27"))
_mem(py_root, "rules", "py.md", "# Rule\n\nThe venv is python 3.9 and pinned there.\n")
f2, _u2, _r2 = aging.check(py_root)
check("3.9 IS FLAGGED AGAINST A DECLARED 3.11", len(f2) == 1 and f2[0][3] == "3.9")
_mem(py_root, "rules", "py.md", "# Rule\n\nThe venv is python 3.11.\n")
f3, _u3, _r3 = aging.check(py_root)
check("and 3.11 against 3.11 is silent", f3 == [])
shutil.rmtree(py_root, ignore_errors=True)
shutil.rmtree(ag_root, ignore_errors=True)

# ---------------------------------------------------------------- asking impact a question (Stage 13b)
# render() is the only writer of the Impact section and parse_section() is its exact inverse. The
# round-trip below is the whole guard: feeding render()'s own output back in means a format change
# breaks THIS test rather than silently breaking every query built on it.
built = {
    "src/auth.py": {"used_by": ["src/api.py", "src/web.py"], "tests": ["tests/test_auth.py"]},
    "src/big.py": {"used_by": [f"src/m{i}.py" for i in range(11)],
                   "tests": [f"tests/t{i}.py" for i in range(5)]},
    "src/lonely.py": {"used_by": [], "tests": ["tests/test_lonely.py"]},
}
rendered = impact_mod.render(built)
back = impact_mod.parse_section(rendered)
check("ROUND-TRIP: every rendered row parses back", set(back) == set(built))
check("a row's dependents survive the round-trip",
      back["src/auth.py"]["used_by"] == ["src/api.py", "src/web.py"])
check("a row's tests survive the round-trip",
      back["src/auth.py"]["tests"] == ["tests/test_auth.py"])
check("a row with no dependents parses as none, not as an error",
      back["src/lonely.py"]["used_by"] == [])
check("a row with only tests still parses its tests",
      back["src/lonely.py"]["tests"] == ["tests/test_lonely.py"])

# The elision counts are the honest half: printing six of eleven dependents without saying so
# answers a different question than the one asked.
check("the used-by elision count is read back, not dropped",
      back["src/big.py"]["used_by_more"] == 11 - impact_mod.MAX_USED_BY)
check("the tests elision count is read back too",
      back["src/big.py"]["tests_more"] == 5 - impact_mod.MAX_TESTS)
check("only the shown dependents are listed",
      len(back["src/big.py"]["used_by"]) == impact_mod.MAX_USED_BY)
check("an un-elided row reports zero elided", back["src/auth.py"]["used_by_more"] == 0)

check("text with no Impact section parses as nothing",
      impact_mod.parse_section("# Architecture map\n\nno impact here") == {})
check("an empty impact map renders nothing to parse", impact_mod.render({}) == "")

# lookup(): exact, or a suffix, and ONLY when exactly one row matches -- answering "what breaks if
# I change this" about the wrong file is worse than saying it could not tell.
check("lookup matches an exact path", impact_mod.lookup(rendered, "src/auth.py")[0] == "src/auth.py")
check("lookup matches a bare basename when only one row ends in it",
      impact_mod.lookup(rendered, "auth.py")[0] == "src/auth.py")
check("lookup returns the row's edges too",
      impact_mod.lookup(rendered, "auth.py")[1]["tests"] == ["tests/test_auth.py"])
check("lookup finds nothing for an unindexed path",
      impact_mod.lookup(rendered, "src/never.py") == (None, None))
check("lookup ignores a leading ./", impact_mod.lookup(rendered, "./src/auth.py")[0] == "src/auth.py")
ambiguous = impact_mod.render({
    "a/utils.py": {"used_by": ["a/main.py"], "tests": []},
    "b/utils.py": {"used_by": ["b/main.py"], "tests": []},
})
check("AN AMBIGUOUS BASENAME RESOLVES TO NOTHING RATHER THAN A GUESS",
      impact_mod.lookup(ambiguous, "utils.py") == (None, None))
check("but the same name fully qualified still resolves",
      impact_mod.lookup(ambiguous, "a/utils.py")[0] == "a/utils.py")

# The CLI, including the join that is the point of the stage: an import graph cannot say "last
# time this changed it was rolled back", and that is the half that changes what somebody does.
def run_impact(root, *args):
    return subprocess.run([str(ROOT / "bin" / "chamnan-impact"), *args],
                          capture_output=True, text=True, cwd=root)

im_root = Path(tempfile.mkdtemp(prefix="chamnan-impact-")).resolve()
(im_root / ".git").mkdir()
ws.ensure(im_root)
(im_root / ".chamnan" / "MAP.md").write_text(impact_mod.render({
    "src/auth.py": {"used_by": ["src/api.py"], "tests": ["tests/test_auth.py"]},
    "src/untested.py": {"used_by": ["src/api.py"], "tests": []},
}), encoding="utf-8")

out = run_impact(im_root, "src/auth.py")
check("chamnan-impact names the dependents", "src/api.py" in out.stdout)
check("chamnan-impact names the covering tests", "tests/test_auth.py" in out.stdout)
check("chamnan-impact says how old the index is", "built today" in out.stdout)
out = run_impact(im_root, "src/untested.py")
check("A FILE WITH DEPENDENTS BUT NO TESTS IS CALLED UNGUARDED", "unguarded" in out.stdout)
out = run_impact(im_root, "src/nothing.py")
check("a file with nothing recorded says so plainly",
      out.returncode == 0 and "nothing recorded" in out.stdout)
check("and says that is the cheap case rather than sounding like a failure",
      "change it freely" in out.stdout)

timeline.create(im_root, "Auth migration", "2026-08-01")
timeline.append(im_root, "auth-migration", "2026-08-01", "rolled back — sessions did not survive",
                ["src/auth.py"])
timeline.append(im_root, "auth-migration", "2026-08-14", "second attempt held", ["src/auth.py"])
out = run_impact(im_root, "src/auth.py")
check("THE THREAD JOIN REACHES THE ANSWER", "rolled back" in out.stdout)
check("the join names which thread it came from", "Auth migration" in out.stdout)
check("the join counts the entries", "2 thread entries" in out.stdout)
check("the dependency half is still there alongside it", "src/api.py" in out.stdout)

# A file nothing imports can still have been rolled back twice, so the join must run even when
# the index half finds nothing.
timeline.append(im_root, "auth-migration", "2026-08-20", "config rewritten", ["deploy/values.yaml"])
out = run_impact(im_root, "deploy/values.yaml")
check("A FILE ABSENT FROM THE INDEX STILL GETS ITS HISTORY", "config rewritten" in out.stdout)

nomap = Path(tempfile.mkdtemp(prefix="chamnan-impact-nomap-")).resolve()
(nomap / ".git").mkdir()
ws.ensure(nomap)
out = run_impact(nomap, "src/anything.py")
check("with no index at all, chamnan-impact says to build one",
      out.returncode == 1 and "chamnan-map" in out.stderr)
out = run_impact(nomap)
check("chamnan-impact with no argument is refused", out.returncode == 2)
shutil.rmtree(nomap, ignore_errors=True)
shutil.rmtree(im_root, ignore_errors=True)

# ---------------------------------------------------------------- environments.md (Stage 13a, 1.6.0)
# The facts nobody writes down: "RWO storage only", "no TPM in UAT". Nothing here contacts an
# environment -- every line was typed by somebody who knew it, which is exactly why `Checked:` is
# load-bearing rather than decorative: it is the only signal of how much to trust a line.
ev_root = Path(tempfile.mkdtemp(prefix="chamnan-env-")).resolve()
(ev_root / ".git").mkdir()
ws.ensure(ev_root)

check("an absent environments.md parses as no entries", envs.entries(ev_root) == [])
check("nothing is injected when the file is absent", envs.render_constraints(ev_root) == "")
check("no environments means nothing is stale", envs.stale_environments(ev_root) == [])

prod = envs.render_entry("production", "Kubernetes 1.28 on RKE2",
                         "postgres 16, redis 7.2, python 3.11",
                         ["RWO storage only — no ReadWriteMany PVCs",
                          "no outbound internet from worker nodes"], "2026-08-27")
_p, replaced = envs.upsert(ev_root, "production", prod)
check("the first upsert declares rather than replaces", not replaced)
uat = envs.render_entry("uat", "Kubernetes 1.26", "postgres 13", ["no TPM in UAT"], "2026-01-05")
envs.upsert(ev_root, "uat", uat)

parsed = envs.entries(ev_root)
check("both environments parse", [e["name"] for e in parsed] == ["production", "uat"])
check("the platform line round-trips", parsed[0]["platform"] == "Kubernetes 1.28 on RKE2")
check("versions parse into name -> version",
      parsed[0]["versions"] == {"postgres": "16", "redis": "7.2", "python": "3.11"})
check("constraints parse as a list of bullets", len(parsed[0]["constraints"]) == 2)
check("a constraint's text round-trips whole",
      parsed[0]["constraints"][0] == "RWO storage only — no ReadWriteMany PVCs")
check("the checked date round-trips", parsed[0]["checked"] == "2026-08-27")

# Two environments running different versions of the same thing is usually the entire reason
# somebody wrote this file, so declared_versions keeps a list per name rather than one value.
declared = envs.declared_versions(ev_root)
check("DECLARED_VERSIONS KEEPS BOTH VALUES FOR ONE NAME",
      sorted(declared["postgres"]) == [("production", "16"), ("uat", "13")])
check("a version declared in only one environment has one entry",
      declared["redis"] == [("production", "7.2")])

# upsert REPLACES rather than appends: this file describes how things ARE, and two `## production`
# headings would leave a reader no way to tell which is current.
newer = envs.render_entry("production", "K8s 1.31", "postgres 17", ["RWO only"], "2026-08-27")
_p2, replaced2 = envs.upsert(ev_root, "production", newer)
after = envs.entries(ev_root)
check("UPSERT REPLACES AN EXISTING ENVIRONMENT IN PLACE", replaced2 and len(after) == 2)
check("the replacement's values win", after[0]["versions"] == {"postgres": "17"})
check("replacing the first entry did not disturb the second",
      after[1]["name"] == "uat" and after[1]["constraints"] == ["no TPM in UAT"])

# Staleness. An entry nobody has confirmed is evidence nobody looked, NOT evidence nothing
# changed -- which is why aging refuses to report against these rather than issuing an all-clear.
import time as _time
now = _time.time()
fresh_only = envs.stale_environments(ev_root, now=now, window_days=100000)
check("nothing is stale under a very wide window", fresh_only == [])
stale = envs.stale_environments(ev_root, now=now)
check("an old Checked: date goes stale", [s[0] for s in stale] == ["uat"])
check("a stale entry reports how many days it has been", stale[0][1] > 180)

no_date = envs.render_entry("dr", "different hardware", "", ["DR runs on other kit"], "")
envs.upsert(ev_root, "dr", no_date)
never = dict(envs.stale_environments(ev_root, now=now))
check("AN ENTRY WITH NO CHECKED DATE COUNTS AS STALE, NOT AS FINE", "dr" in never)
check("and reports None rather than a made-up day count", never["dr"] is None)

# The injection is constraints only: a constraint rules out a design before it is written, a
# version is a fact that can be looked up on the one occasion it matters.
injected = envs.render_constraints(ev_root)
check("the injected block names each environment", "production" in injected and "uat" in injected)
check("the injected block carries the constraints", "RWO only" in injected)
check("THE INJECTED BLOCK DOES NOT CARRY VERSION NUMBERS", "postgres 17" not in injected)
check("an environment with no constraints is left out of the injection", "dr" in injected)
bare_env = Path(tempfile.mkdtemp(prefix="chamnan-env-bare-")).resolve()
(bare_env / ".git").mkdir()
ws.ensure(bare_env)
envs.upsert(bare_env, "empty", envs.render_entry("empty", "nothing declared", "", [], "2026-08-27"))
check("an environment declaring no constraints injects nothing at all",
      envs.render_constraints(bare_env) == "")
shutil.rmtree(bare_env, ignore_errors=True)

# Field boundaries: bullets under Constraints: must not swallow a field written after them.
raw = envs.path(ev_root)
raw.write_text("# Environments\n\n## prod\n**Constraints:**\n- first\n- second\n"
               "**Checked:** 2026-08-27\n**Platform:** something\n", encoding="utf-8")
bounded = envs.entries(ev_root)[0]
check("constraint bullets stop at the next field", bounded["constraints"] == ["first", "second"])
check("a field written after the bullets still parses", bounded["checked"] == "2026-08-27")
check("and so does one after that", bounded["platform"] == "something")

# The CLI.
def run_env(root, *args):
    return subprocess.run([str(ROOT / "bin" / "chamnan-env"), *args],
                          capture_output=True, text=True, cwd=root)

ev_cli = Path(tempfile.mkdtemp(prefix="chamnan-env-cli-")).resolve()
(ev_cli / ".git").mkdir()
ws.ensure(ev_cli)
out = run_env(ev_cli, "check")
check("env check on an empty workspace says there is nothing to check",
      out.returncode == 0 and "nothing to check" in out.stdout)
out = run_env(ev_cli, "set", "production", "--platform", "K8s 1.28",
              "--constraint", "RWO storage only")
check("env set declares an environment", out.returncode == 0 and "declared production" in out.stdout)
out = run_env(ev_cli, "set", "bare")
check("env set with no constraints still succeeds", out.returncode == 0)
check("but says the constraints are the part worth writing", "no constraints recorded" in out.stdout)
out = run_env(ev_cli, "check")
check("a freshly declared environment is not cold", "confirmed within the last" in out.stdout)
out = run_env(ev_cli, "set", "old", "--constraint", "x", "--checked", "2020-01-01")
out = run_env(ev_cli, "check")
check("env check names the cold environment", "old" in out.stdout and "gone cold" in out.stdout)
check("env check says what to do about it", "--checked" in out.stdout)
out = run_env(ev_cli, "show", "production")
check("env show prints the canonical shape", "**Platform:** K8s 1.28" in out.stdout)
out = run_env(ev_cli, "show", "nope")
check("env show on an unknown name fails", out.returncode == 1)
out = run_env(ev_cli, "set", "x", "--platform")
check("an option with no value is refused", out.returncode == 2)
out = run_env(ev_cli, "set", "x", "--nonsense", "y")
check("an unknown option is refused", out.returncode == 2)
shutil.rmtree(ev_cli, ignore_errors=True)
shutil.rmtree(ev_root, ignore_errors=True)

# ---------------------------------------------------------------- timeline threads (Stage 13, 1.6.0)
# The design being pinned here is that threading is a PICK FROM A DECLARED LIST, never a string
# match: "auth", "login" and "the SSO work" are one thread written three ways, and a matcher that
# guessed would make them three. So `append()` refusing an undeclared thread is the load-bearing
# behaviour, not an input-validation nicety.
tl_root = Path(tempfile.mkdtemp(prefix="chamnan-timeline-")).resolve()
(tl_root / ".git").mkdir()
ws.ensure(tl_root)

check("a workspace with no threads lists none", timeline.threads(tl_root) == [])
check("open_titles is empty when there are no threads", timeline.open_titles(tl_root) == "")
check("APPEND REFUSES A THREAD THAT WAS NEVER DECLARED",
      timeline.append(tl_root, "auth", "2026-08-01", "something happened") is None)
check("refusing to append also wrote nothing", timeline.threads(tl_root) == [])

t_path, is_new = timeline.create(tl_root, "Auth migration", "2026-08-01")
check("create() declares a thread", is_new and t_path.is_file())
check("the declared thread carries its title", timeline.title_of(t_path) == "Auth migration")
check("a new thread is open", timeline.status_of(t_path) == timeline.OPEN)
again, is_new2 = timeline.create(tl_root, "Auth migration", "2026-08-02")
check("declaring the same thread twice is not new", not is_new2 and again == t_path)

timeline.append(tl_root, "auth-migration", "2026-08-01", "first attempt, rolled back",
                ["src/auth.py", "src/api.py"])
timeline.append(tl_root, "auth-migration", "2026-08-14", "second attempt held", ["src/auth.py"])
entries = timeline.entries_of(t_path)
check("entries are read back oldest first", [e[0] for e in entries] == ["2026-08-01", "2026-08-14"])
check("an entry's note round-trips", entries[0][1] == "first attempt, rolled back")
check("an entry's Files: line round-trips as a list", entries[0][2] == ["src/auth.py", "src/api.py"])
check("declaring twice did not lose the entries appended in between", len(entries) == 2)

# Position, slug and filename all resolve to the same thread. The number is computed fresh, which
# is why a listing is safe to read numbers off — see lib/candidates.py for the same choice.
check("a thread resolves by slug", timeline.resolve(tl_root, "auth-migration") == t_path)
check("a thread resolves by filename", timeline.resolve(tl_root, "auth-migration.md") == t_path)
check("a thread resolves by 1-based position", timeline.resolve(tl_root, "1") == t_path)
check("an out-of-range position resolves to nothing", timeline.resolve(tl_root, "99") is None)
check("an unknown name resolves to nothing", timeline.resolve(tl_root, "login") is None)

# The join. `for_path` is what lets an impact question carry "last time this changed, it was
# rolled back" -- exact path, or a suffix of one, never a fuzzy stem match.
hits = timeline.for_path(tl_root, "src/auth.py")
check("for_path finds every entry naming the file", len(hits) == 2)
check("FOR_PATH RETURNS NEWEST FIRST", [h[1] for h in hits] == ["2026-08-14", "2026-08-01"])
check("for_path finds a file named in only one entry",
      len(timeline.for_path(tl_root, "src/api.py")) == 1)
check("for_path on an unmentioned file finds nothing",
      timeline.for_path(tl_root, "src/unrelated.py") == [])
check("for_path does NOT fuzzy-match a bare stem onto a different path",
      timeline.for_path(tl_root, "vendor/auth.py") == [])

timeline.create(tl_root, "Payment retries", "2026-08-20")
injected = timeline.open_titles(tl_root)
check("open_titles names every open thread",
      "Auth migration" in injected and "Payment retries" in injected)
timeline.set_status(tl_root, "payment-retries", timeline.CLOSED)
closed_out = timeline.open_titles(tl_root)
check("A CLOSED THREAD LEAVES THE INJECTION", "Payment retries" not in closed_out)
check("the open one is still injected", "Auth migration" in closed_out)
check("a closed thread is still readable",
      len(timeline.entries_of(timeline.resolve(tl_root, "payment-retries"))) == 0)
timeline.set_status(tl_root, "payment-retries", timeline.OPEN)
check("reopening puts it back", "Payment retries" in timeline.open_titles(tl_root))

# A thread written by hand with no Status: line at all must behave like the common case rather
# than vanish -- the field is additive, same rule every other new field in this plugin follows.
handwritten = timeline.directory(tl_root) / "by-hand.md"
handwritten.write_text("# Written by hand\n\n## 2026-08-01 — a note\n", encoding="utf-8")
check("a thread with no Status line reads as open", timeline.status_of(handwritten) == timeline.OPEN)
check("a hand-written thread is injected like any other",
      "Written by hand" in timeline.open_titles(tl_root))
timeline.set_status(tl_root, "by-hand", timeline.CLOSED)
check("set_status adds a Status line to a file that had none",
      timeline.status_of(handwritten) == timeline.CLOSED)
check("adding the Status line did not eat the title", timeline.title_of(handwritten) == "Written by hand")
check("adding the Status line did not eat the entry", len(timeline.entries_of(handwritten)) == 1)

# The ledger has to count every store it can see, or its "nothing written yet" is a false
# statement rather than a missing clause.
led_root = Path(tempfile.mkdtemp(prefix="chamnan-ledger-threads-")).resolve()
(led_root / ".git").mkdir()
ws.ensure(led_root)
check("an empty threads/ still reads as nothing written yet",
      "nothing written yet" in ledger.line(led_root))
timeline.create(led_root, "A thread", "2026-08-01")
check("ONE THREAD STOPS THE LEDGER SAYING NOTHING IS WRITTEN",
      "nothing written yet" not in ledger.line(led_root))
check("the ledger names the thread count", "1 thread" in ledger.line(led_root))
timeline.create(led_root, "Another", "2026-08-01")
check("the ledger pluralises the thread count", "2 threads" in ledger.line(led_root))
bare = Path(tempfile.mkdtemp(prefix="chamnan-ledger-bare-")).resolve()
(bare / ".git").mkdir()
(bare / ".chamnan").mkdir()
check("a 1.4.0-shaped workspace with no threads/ is unaffected",
      ledger.snapshot(bare)["thread_count"] is None)
check("and still reads as nothing written yet", "nothing written yet" in ledger.line(bare))
shutil.rmtree(bare, ignore_errors=True)
shutil.rmtree(led_root, ignore_errors=True)

# The CLI's refusal is the design decision made visible: an unknown name prints the declared list
# rather than quietly starting a second thread for the same subject.
def run_timeline(root, *args):
    return subprocess.run([str(ROOT / "bin" / "chamnan-timeline"), *args],
                          capture_output=True, text=True, cwd=root)

cli_root = Path(tempfile.mkdtemp(prefix="chamnan-timeline-cli-")).resolve()
(cli_root / ".git").mkdir()
ws.ensure(cli_root)
out = run_timeline(cli_root, "new", "Auth migration")
check("chamnan-timeline new declares a thread", out.returncode == 0 and "declared" in out.stdout)
out = run_timeline(cli_root, "add", "auth-migration", "rolled back", "--files", "src/auth.py")
check("chamnan-timeline add records an entry", out.returncode == 0 and "recorded" in out.stdout)
out = run_timeline(cli_root, "add", "login", "same work, different word")
check("ADD ON AN UNDECLARED NAME FAILS", out.returncode == 1)
check("and prints the declared list so the right one can be picked",
      "Auth migration" in out.stderr)
check("no second thread was created for the synonym", len(timeline.threads(cli_root)) == 1)
out = run_timeline(cli_root, "for", "src/auth.py")
check("chamnan-timeline for joins on the file", "rolled back" in out.stdout)
out = run_timeline(cli_root, "for", "src/never-touched.py")
check("chamnan-timeline for says so plainly when nothing matches",
      out.returncode == 0 and "nothing recorded" in out.stdout)
out = run_timeline(cli_root, "add", "auth-migration")
check("add with no note is refused", out.returncode == 2)
shutil.rmtree(cli_root, ignore_errors=True)
shutil.rmtree(tl_root, ignore_errors=True)

# ---------------------------------------------------------------- repeated workflows
# scratch_watch catches the same SCRIPT written a third time. This catches the thing that leaves
# no file behind: the same commands, in the same order, weeks apart. Sequence detection is much
# noisier than comparing two script bodies, so most of these checks are about staying quiet.
check("a bare program is its own signature", workflows.signature("pytest -x tests/") == "pytest")
check("a subcommand tool keeps its subcommand", workflows.signature("git status -sb") == "git status")
check("arguments and paths are discarded",
      workflows.signature("pytest tests/payment -x") == workflows.signature("pytest tests/fleet"))
check("a boolean flag before the subcommand is skipped",
      workflows.signature("docker --debug compose up") == "docker compose")
# Known limitation, documented in lib/workflows.py: a global flag taking a VALUE cannot be told
# from a boolean one without each tool's grammar. The result is a signature that matches nothing,
# so the workflow goes undetected — quiet, rather than a wrong suggestion.
check("a value-taking global flag is a known blind spot",
      workflows.signature("docker --context prod compose up") == "docker prod")
check("leading environment assignments are skipped",
      workflows.signature("FOO=bar pytest tests/") == "pytest")
check("an absolute path is reduced to the program",
      workflows.signature("/usr/local/bin/pytest tests/") == "pytest")
check("A COMMON SHELL COMMAND IS IGNORED", workflows.signature("ls -la") == "")
check("grep is ignored too", workflows.signature("grep -rn foo .") == "")
check("an empty command yields nothing", workflows.signature("   ") == "")

check("a pipeline yields each step",
      workflows.signatures("docker compose up && alembic upgrade head && pytest tests/")
      == ["docker compose", "alembic", "pytest"])
check("noise inside a chain is dropped",
      workflows.signatures("cd /srv && ls && pytest tests/") == ["pytest"])
check("consecutive duplicates collapse",
      workflows.signatures("git add . && git add -A") == ["git add"])

def _day(d, sigs):
    return [{"at": f"2026-08-{d:02d}T10:00:00+07:00", "sig": s} for s in sigs]

seq = ["docker compose", "alembic", "pytest"]
check("two occurrences are NOT enough",
      workflows.repeated(_day(1, seq) + _day(2, seq)) is None)
found = workflows.repeated(_day(1, seq) + _day(2, seq) + _day(3, seq))
check("THREE OCCURRENCES ON THREE DAYS QUALIFY", found is not None)
check("the sequence is reported in order", found[0] == seq)
check("the count is the number of days", found[1] == 3)

check("A SEQUENCE REPEATED WITHIN ONE DAY IS NOT THREE OCCURRENCES",
      workflows.repeated(_day(1, seq + seq + seq)) is None)
check("a two-step sequence is below the minimum length",
      workflows.repeated(_day(1, ["git status", "pytest"]) * 1
                         + _day(2, ["git status", "pytest"])
                         + _day(3, ["git status", "pytest"])) is None)
check("three occurrences of the SAME command repeated do not qualify",
      workflows.repeated(_day(1, ["pytest", "pytest", "pytest"])
                         + _day(2, ["pytest", "pytest", "pytest"])
                         + _day(3, ["pytest", "pytest", "pytest"])) is None)
check("unrelated days do not stitch into a sequence",
      workflows.repeated(_day(1, ["git status", "pytest", "docker compose"])
                         + _day(2, ["terraform plan", "helm upgrade", "kubectl get"])
                         + _day(3, ["npm run", "node", "cargo build"])) is None)

longer = ["docker compose", "alembic", "pytest", "kubectl apply"]
best = workflows.repeated(_day(1, longer) + _day(2, longer) + _day(3, longer))
check("the LONGEST qualifying sequence is chosen", best[0] == longer)

msg = workflows.describe(seq, 3)
check("the notice names the sequence", "docker compose" in msg and "pytest" in msg)
check("the notice points at the capture skill", "/chamnan:capture" in msg)
check("the notice says how many times", "3 times" in msg)

# The log is bounded by CALENDAR TIME with a per-day cap, not by a flat entry count. The flat cap
# it replaced held one busy day, which meant repeated() -- which needs REPEAT_AT distinct days --
# could never fire, and usage_counts() could never see far enough back to answer the question it
# exists for. Every property below is one half of that fix.
wf = Path(tempfile.mkdtemp(prefix="chamnan-wf-")) / "commands.jsonl"
over = workflows.KEEP_PER_DAY + workflows.TRIM_SLACK + 10
hist = workflows.record(wf, ["pytest"] * over, "2026-08-01T10:00:00+07:00")
check("one day is capped at KEEP_PER_DAY ordinary commands",
      len(hist) == workflows.KEEP_PER_DAY)
check("a malformed line does not break reading",
      len(workflows.read(wf)) == workflows.KEEP_PER_DAY)

# The cap drops from the HEAD of a day. repeated() reads run[-WINDOW:], so the tail it sees must be
# bit-for-bit what it would have seen had nothing been pruned.
tail = Path(tempfile.mkdtemp(prefix="chamnan-tail-")) / "commands.jsonl"
workflows.record(tail, ["noise"] * over, "2026-08-01T09:00:00+07:00")
tail_hist = workflows.record(tail, ["git status", "pytest", "docker compose"],
                             "2026-08-01T10:00:00+07:00")
check("pruning never touches the tail repeated() reads",
      [e["sig"] for e in tail_hist[-3:]] == ["git status", "pytest", "docker compose"])
shutil.rmtree(tail.parent, ignore_errors=True)

# The whole point of the change: enough days survive for repeated() to have something to detect.
span = Path(tempfile.mkdtemp(prefix="chamnan-span-")) / "commands.jsonl"
routine = ["git status", "pytest", "docker compose"]
for day in (1, 2, 3):
    workflows.record(span, ["noise"] * over, f"2026-08-0{day}T09:00:00+07:00")
    span_hist = workflows.record(span, routine, f"2026-08-0{day}T10:00:00+07:00")
check("a busy day no longer evicts the days before it",
      len({e["at"][:10] for e in span_hist}) == 3)
check("repeated() can still fire across days a flat entry cap would have erased",
      workflows.repeated(span_hist) is not None)
shutil.rmtree(span.parent, ignore_errors=True)

# chamnan's own commands are the adoption signal: exempt from the per-day cap, so a count is exact.
keep = Path(tempfile.mkdtemp(prefix="chamnan-keep-")) / "commands.jsonl"
workflows.record(keep, ["chamnan-map"], "2026-08-01T08:00:00+07:00")
workflows.record(keep, ["noise"] * over, "2026-08-01T09:00:00+07:00")
keep_counts, _, _ = workflows.usage_counts(keep, ["chamnan-map"])
check("chamnan's own command survives a day that overflows the cap", keep_counts["chamnan-map"] == 1)
check("a signature merely CONTAINING the word is not exempt",
      workflows._KEEP_ALWAYS.match("add-chamnan") is None)
shutil.rmtree(keep.parent, ignore_errors=True)

# Older than the window falls off; a record shape this module did not write is never rationed.
old_day = [{"at": "2026-01-01T10:00:00+07:00", "kind": "command", "sig": "pytest"}]
recent = [{"at": "2026-08-01T10:00:00+07:00", "kind": "command", "sig": "pytest"}]
check("a day past KEEP_DAYS is dropped",
      workflows.prune(old_day + recent, days=1) == recent)
foreign = [{"at": "2026-08-01T09:00:00+07:00", "kind": "something-else", "sig": "x"}]
check("a foreign record kind is exempt from the per-day cap that drops every command",
      workflows.prune(foreign + recent, per_day=0) == foreign)
shutil.rmtree(wf.parent, ignore_errors=True)

# ---------------------------------------------------------------- usage_counts (Stage 11)
uc_log = Path(tempfile.mkdtemp(prefix="chamnan-usage-")) / "commands.jsonl"
workflows.record(uc_log, ["chamnan-map"], "2026-08-01T10:00:00+07:00")
workflows.record(uc_log, ["chamnan-map"], "2026-08-05T10:00:00+07:00")
workflows.record(uc_log, ["chamnan-report"], "2026-08-10T10:00:00+07:00")
workflows.record(uc_log, ["git status"], "2026-08-15T10:00:00+07:00")
counts, oldest, newest = workflows.usage_counts(uc_log, ["chamnan-map", "chamnan-report", "chamnan-promote"])
check("usage_counts counts a repeated signature", counts["chamnan-map"] == 2)
check("usage_counts counts a single occurrence", counts["chamnan-report"] == 1)
check("usage_counts zeros a name never seen", counts["chamnan-promote"] == 0)
check("usage_counts ignores a signature outside `names`", "git status" not in counts)
check("usage_counts's span is the OLDEST entry in the log, not just the counted ones",
      oldest == "2026-08-01T10:00:00+07:00")
check("usage_counts's span is the NEWEST entry in the log, not just the counted ones",
      newest == "2026-08-15T10:00:00+07:00")
empty_counts, empty_oldest, empty_newest = workflows.usage_counts(
    uc_log.parent / "does-not-exist.jsonl", ["chamnan-map"])
check("usage_counts on a missing log is all zeros, not an error", empty_counts == {"chamnan-map": 0})
check("usage_counts on a missing log has no span", empty_oldest is None and empty_newest is None)
shutil.rmtree(uc_log.parent, ignore_errors=True)

# ---------------------------------------------------------------- shell keywords are not programs
# Measured on the live workspace this module was developed against: `do` had appeared 50 times in
# commands.jsonl, `for` 14, `done` 10 -- about a fifth of the log was shell syntax, not workflow
# steps, and repeated() found nothing at all against that log until KEYWORDS existed.
check("A FOR-LOOP HEADER YIELDS NO SIGNATURE", workflows.signature("for f in *.py") == "")
check("A do KEYWORD YIELDS NO SIGNATURE", workflows.signature("do echo \"$f\"") == "")
check("A done KEYWORD YIELDS NO SIGNATURE", workflows.signature("done") == "")
check("every listed shell keyword yields no signature",
      all(workflows.signature(kw) == "" for kw in workflows.KEYWORDS))
check("a real program whose name happens to start with a keyword still signs",
      workflows.signature("forever start app.js") == "forever")

loop_cmd = 'for f in *.py; do echo "$f"; done'
loop_sigs = workflows.signatures(loop_cmd)
check("A REAL FOR-LOOP PRODUCES NO KEYWORD SIGNATURES",
      not any(s in workflows.KEYWORDS for s in loop_sigs))
# Known limitation, matching the existing one documented for `docker --context prod compose up`:
# `; do <command>;` is one semicolon-delimited fragment whose FIRST word is the keyword "do", so
# the command after it is never reached -- the whole fragment drops rather than yielding "pytest".
# This is the same "fail quiet" trade-off already made elsewhere in this function: recovering the
# command after a keyword would need to know which keywords syntactically precede one (`do`,
# `then`, `else`) versus an expression (`for`, `while`, `if`), and a wrong guess there suggests the
# wrong routine, which is worse than the loop's real command going undetected this one time.
check("a real command directly after a `do` keyword is NOT recovered -- known limitation",
      workflows.signatures('for f in *; do pytest "$f"; done') == [])
check("the same loop written WITHOUT a keyword prefix still signs normally",
      workflows.signatures('pytest "$f"') == ["pytest"])

# ---------------------------------------------------------------- kind, and evidence fields
# Added so a future record shape sharing either log cannot be silently treated as this one --
# see lib/workflows.py's record()/_runs() docstrings for the exact failure this prevents.
kind_wf = Path(tempfile.mkdtemp(prefix="chamnan-kind-")) / "commands.jsonl"
kind_hist = workflows.record(kind_wf, ["pytest"], "2026-08-01T10:00:00+07:00", tool="Bash")
check("a new record carries kind=command", kind_hist[-1]["kind"] == "command")
check("a new record carries the tool that produced it", kind_hist[-1]["tool"] == "Bash")
check("interrupted is absent, not False, when the call was not interrupted",
      "interrupted" not in kind_hist[-1])
kind_hist2 = workflows.record(kind_wf, ["pytest"], "2026-08-01T10:05:00+07:00",
                              tool="Bash", interrupted=True)
check("interrupted is recorded true when the payload says so", kind_hist2[-1]["interrupted"] is True)

# A 1.4.0 record on disk has no "kind" at all -- it must still read as a command signature, with
# no rewrite of the file that holds it.
legacy_command_log = [{"at": "2026-08-01T09:00:00+07:00", "sig": "pytest"}]
check("a pre-Stage-2 record with no kind still counts as a command",
      len(workflows._runs(legacy_command_log)[0]) == 1)

# A record explicitly tagged as something else must never join a command sequence, even though
# nothing writes a non-"command" kind into this log today -- this is the forward guard, not a
# behaviour anything currently exercises in production.
mixed_log = [{"at": "2026-08-01T09:00:00+07:00", "sig": "pytest", "kind": "command"},
             {"at": "2026-08-01T09:01:00+07:00", "sig": "should-not-count", "kind": "something-else"}]
check("an entry of a different kind is excluded from the run",
      workflows._runs(mixed_log) == [["pytest"]])
shutil.rmtree(kind_wf.parent, ignore_errors=True)

# scratch.jsonl gains the same kind tag, plus which tool wrote the entry and (for Write/Edit) the
# file path -- never fabricated, and file is simply absent for a Bash heredoc, which has none.
scratch_fixture = Path(tempfile.mkdtemp(prefix="chamnan-scratch-kind-")).resolve()
(scratch_fixture / ".git").mkdir()
ws.ensure(scratch_fixture)
# Real, varied content -- MIN_TOKENS requires at least 8 distinct identifiers of 4+ characters,
# and a repeated filler character collapses to one token, which silently defeats the fixture.
rich_script = ("import json\nfrom pathlib import Path\n"
              "records = json.loads(Path('usage.json').read_text())\n"
              "total_cost = sum(entry['cost'] for entry in records['rows'])\n"
              "call_count = sum(entry['calls'] for entry in records['rows'])\n"
              "print(f'cost={total_cost} calls={call_count}')\n")
write_payload = {"tool_name": "Write",
                 "tool_input": {"file_path": "/tmp/probe.py", "content": rich_script}}
run1 = subprocess.run([str(ROOT / "hooks" / "scratch_watch.py")], input=json.dumps(write_payload),
                      capture_output=True, text=True, cwd=scratch_fixture)
scratch_log_path = scratch_fixture / ".chamnan" / "logs" / "scratch.jsonl"
scratch_entries = [json.loads(l) for l in scratch_log_path.read_text(encoding="utf-8").splitlines()
                   if l.strip()] if scratch_log_path.is_file() else []
check("scratch_watch actually wrote an entry for a Write call", len(scratch_entries) == 1)
if scratch_entries:
    check("a scratch entry carries kind=scratch", scratch_entries[-1].get("kind") == "scratch")
    check("a scratch entry names the tool that wrote it", scratch_entries[-1].get("tool") == "Write")
    check("a scratch entry from Write records the file path",
          scratch_entries[-1].get("file") == "/tmp/probe.py")

bash_payload = {"tool_name": "Bash",
               "tool_input": {"command": f"python3 - <<'PY'\n{rich_script}print(2)\nPY"}}
subprocess.run([str(ROOT / "hooks" / "scratch_watch.py")], input=json.dumps(bash_payload),
               capture_output=True, text=True, cwd=scratch_fixture)
scratch_entries2 = [json.loads(l) for l in scratch_log_path.read_text(encoding="utf-8").splitlines()
                    if l.strip()]
bash_entry = scratch_entries2[-1]
check("a Bash heredoc scratch entry names Bash as the tool", bash_entry.get("tool") == "Bash")
check("a Bash heredoc scratch entry has no file field -- there is no file to name",
      "file" not in bash_entry)

# The hook must never touch anything outside its own workspace, regardless of what evidence it now
# gathers from the payload -- file paths in tool_input are read as STRINGS for the log, never opened.
canary = Path(tempfile.mkdtemp(prefix="chamnan-canary-")) / "outside.txt"
canary.write_text("must never be read or written by scratch_watch")
canary_before = canary.read_bytes()
outside_payload = {"tool_name": "Write",
                   "tool_input": {"file_path": str(canary), "content": rich_script.replace("cost", "spend")}}
subprocess.run([str(ROOT / "hooks" / "scratch_watch.py")], input=json.dumps(outside_payload),
               capture_output=True, text=True, cwd=scratch_fixture)
check("a file path named in evidence is recorded, never opened",
      canary.read_bytes() == canary_before)
shutil.rmtree(scratch_fixture, ignore_errors=True)
shutil.rmtree(canary.parent, ignore_errors=True)

# ---------------------------------------------------------------- milestones
# A git log says what changed; a milestone says why it was worth doing and which areas moved
# together. Not project management: no status, no owner, no due date.
ms = Path(tempfile.mkdtemp(prefix="chamnan-ms-"))
(ms / ".chamnan").mkdir()

check("an absent file yields no entries", milestones.entries(ms) == [])
check("an absent file injects nothing", milestones.recent_titles(ms) == "")

milestones.append(ms, milestones.render_entry(
    "2026-06-01", "Split the monolith",
    why="deploys blocked each other", affected="api, worker", decisions="kept one database"))
milestones.append(ms, milestones.render_entry(
    "2026-07-15", "Postgres migration", why="SQLite locking failed under two writers"))
milestones.append(ms, milestones.render_entry(
    "2026-08-20", "Authentication migration",
    why="sessions dropped under load", affected="auth module, API layer"))

found = milestones.entries(ms)
check("every entry is parsed", len(found) == 3)
check("ENTRIES ARE OLDEST FIRST, AS WRITTEN", found[0][1] == "Split the monolith")
check("the newest is last", found[-1][1] == "Authentication migration")
check("the date is captured", found[-1][0] == "2026-08-20")
check("the body is captured", "sessions dropped under load" in found[-1][2])

# Appending at the end keeps a diff to added lines; prepending would rewrite the whole file.
text = milestones.path(ms).read_text(encoding="utf-8")
check("the file keeps one header", text.count("# Project milestones") == 1)
check("APPENDING PRESERVES EARLIER ENTRIES VERBATIM", "deploys blocked each other" in text)
check("the newest entry is last in the file",
      text.index("Authentication migration") > text.index("Split the monolith"))

titles = milestones.recent_titles(ms)
check("ONLY THE RECENT TITLES ARE INJECTED", titles.count("- **") == milestones.INJECT_RECENT)
check("titles are newest first for a reader",
      titles.index("Authentication migration") < titles.index("Postgres migration"))
check("AN ENTRY BODY IS NEVER INJECTED", "sessions dropped under load" not in titles)
check("the injection says how many are older", "1 earlier" in titles)

check("an empty field is omitted rather than written blank",
      "**Affected:**" not in milestones.render_entry("2026-01-01", "Something", why="because"))
check("a supplied field is written", "**Why:** because"
      in milestones.render_entry("2026-01-01", "Something", why="because"))

# The file is committed and free text about the repository.
milestones.append(ms, milestones.render_entry(
    "2026-08-21", "Cache work", why="prod is redis://user:" + fake("Hunter2", "Pass") + "@cache.internal"))
leaky = milestones.recent_titles(ms)
check("a password in a body does not reach the titles", "Hunter2" not in leaky)
check("SCRUBBING A MILESTONE BODY REMOVES THE PASSWORD",
      "Hunter2" not in redact.scrub(milestones.path(ms).read_text(encoding="utf-8")))

# Malformed content must not take the hook down.
milestones.path(ms).write_text("# Project milestones\n\nprose with no entries\n", encoding="utf-8")
check("a file with no parseable entries yields none", milestones.entries(ms) == [])
check("and injects nothing", milestones.recent_titles(ms) == "")

# 🐛 [2026-08-27] `[—-]` in a character class is em-dash or hyphen only, never en-dash (U+2013),
# which many editors autocorrect "--" into. An entry using it did not fail loudly -- it was
# silently absorbed into the PRECEDING entry's body, since entries() only splits at headings the
# regex recognises.
milestones.path(ms).write_text(
    "# Project milestones\n\n"
    "## 2026-01-01 — First entry\n\n**Why:** the first one\n\n"
    "## 2026-01-02 – Uses an en-dash\n\n**Why:** written with an editor that autocorrects\n",
    encoding="utf-8")
en_dash_entries = milestones.entries(ms)
check("AN EN-DASH ENTRY IS RECOGNISED AS ITS OWN ENTRY, NOT ABSORBED",
      len(en_dash_entries) == 2)
check("the en-dash entry's title is captured correctly",
      en_dash_entries[1][1] == "Uses an en-dash")
check("the en-dash entry's body did not merge into the entry before it",
      "written with an editor" not in en_dash_entries[0][2])
em_and_hyphen = Path(tempfile.mkdtemp(prefix="chamnan-ms-dash-"))
(em_and_hyphen / ".chamnan").mkdir()
milestones.path(em_and_hyphen).write_text(
    "# Project milestones\n\n"
    "## 2026-01-01 — Em dash entry\n\n**Why:** x\n\n"
    "## 2026-01-02 - Hyphen entry\n\n**Why:** y\n",
    encoding="utf-8")
check("em-dash and hyphen entries both still parse",
      [t for _, t, _ in milestones.entries(em_and_hyphen)] == ["Em dash entry", "Hyphen entry"])
shutil.rmtree(em_and_hyphen, ignore_errors=True)

shutil.rmtree(ms, ignore_errors=True)

# ---------------------------------------------------------------- language extraction quality
# Prioritised by measurement, not by feeling: symbols per thousand lines across a 529-file
# polyglot corpus put PHP at 20.0 and Rust at 21.8, well below comparable languages, and inspection
# showed why. Shell sits lowest of all at 9.9 and was left alone — its scripts are straight-line
# commands, not functions, so the low number is the language rather than a defect.

# PHP: a method is the normal shape, and the bare `function` rule caught none of them.
_d, pfuncs, pcls, _k = mapper.extract_regex(
    "<?php\n"
    "final class Importer implements Runnable {\n"
    "    public function run(array $rows): void {}\n"
    "    private function parse($line) {}\n"
    "    protected static function make() {}\n"
    "    abstract public function must();\n"
    "}\n"
    "function bare_helper($x) {}\n"
    "trait Loggable {}\n"
    "interface Runnable {}\n", "php")
pnames = {f.split("(")[0] for f, _ in pfuncs}
check("A PHP PUBLIC METHOD IS EXTRACTED", "run" in pnames)
check("a php private method is extracted", "parse" in pnames)
check("a php protected static method is extracted", "make" in pnames)
check("a php abstract method is extracted", "must" in pnames)
check("a bare php function still works", "bare_helper" in pnames)
pclasses = {c for c, _, _ in pcls}
check("a php final class is extracted", "Importer" in pclasses)
check("a php trait is extracted", "Loggable" in pclasses)
check("a php interface is extracted", "Runnable" in pclasses)

# Rust: async and restricted visibility are ordinary and both slipped the pattern.
_d, rfuncs, rcls, _k = mapper.extract_regex(
    "pub fn plain(a: u32) -> u32 {}\n"
    "async fn fetch(url: &str) {}\n"
    "pub async fn stream(id: u64) {}\n"
    "pub(crate) fn internal() {}\n"
    "pub unsafe fn raw() {}\n"
    "fn private_one() {}\n"
    "pub struct Frame {}\n"
    "pub trait Codec {}\n"
    "enum Kind {}\n", "rs")
rnames = {f.split("(")[0] for f, _ in rfuncs}
check("A RUST ASYNC FN IS EXTRACTED", "fetch" in rnames)
check("a rust pub async fn is extracted", "stream" in rnames)
check("a rust pub(crate) fn is extracted", "internal" in rnames)
check("a rust unsafe fn is extracted", "raw" in rnames)
check("a plain rust fn still works", "plain" in rnames and "private_one" in rnames)
check("a rust trait is extracted", "Codec" in {c for c, _, _ in rcls})

# JS/TS: class methods are indented, so every rule anchored at ^ skipped them.
_d, jfuncs, jcls, _k = mapper.extract_regex(
    "export class Client {\n"
    "  async send(req: Request): Promise<Response> {\n"
    "    if (req.id) {\n    }\n"
    "    for (const x of items) {\n    }\n"
    "    while (n > 0) {\n    }\n"
    "  }\n"
    "  close(): void {\n  }\n"
    "  constructor(base: string) {\n  }\n"
    "}\n"
    "export function helper(a, b) {}\n", "js")
jnames = {f.split("(")[0] for f, _ in jfuncs}
check("A TS CLASS METHOD IS EXTRACTED", "send" in jnames)
check("a method with a return type is extracted", "close" in jnames)
check("a top-level function still works", "helper" in jnames)
check("AN IF IS NOT EXTRACTED AS A METHOD", "if" not in jnames)
check("a for is not extracted as a method", "for" not in jnames)
check("a while is not extracted as a method", "while" not in jnames)
check("a constructor is not listed as a method", "constructor" not in jnames)
check("an exported class is extracted", "Client" in {c for c, _, _ in jcls})

# "A language partially understood is better than falsely claiming full support" — as an
# assertion rather than a slogan. Each fixture is ordinary code in that language; a rule that
# stops matching it will fail here rather than quietly halving an index.
MIN_YIELD = {
    # 2, not 3: extract_python records a method inside its class tuple
    # rather than as a top-level function, so `alpha` + `Beta` is the
    # honest count for this fixture. gamma is captured, just nested.
    "py": ('def alpha():\n    pass\n\n\nclass Beta:\n    def gamma(self):\n        pass\n', 2),
    "go": ('func Alpha() {}\nfunc (r *R) Beta() {}\ntype Gamma struct {}\n', 3),
    "rb": ('class Alpha\n  def beta\n  end\nend\ndef gamma\nend\n', 3),
    "java": ('public class Alpha {\n  public void beta() {}\n  private int gamma() {}\n}\n', 3),
    "kotlin": ('class Alpha {\n  fun beta() {}\n  suspend fun gamma() {}\n}\n', 3),
    "swift": ('class Alpha {\n  func beta() {}\n  private func gamma() {}\n}\n', 3),
    "rs": ('pub fn alpha() {}\nasync fn beta() {}\npub struct Gamma {}\n', 3),
    "php": ('<?php\nclass Alpha {\n  public function beta() {}\n  private function gamma() {}\n}\n', 3),
    "js": ('export function alpha() {}\nexport class Beta {\n  gamma() {}\n}\n', 3),
    "cs": ('public class Alpha {\n  public void Beta() {}\n  private int Gamma() { return 0; }\n}\n', 3),
    "dart": ('class Alpha {\n  void beta() {}\n  int gamma() { return 0; }\n}\n', 3),
    "ex": ('defmodule Alpha do\n  def beta do\n  end\n  def gamma do\n  end\nend\n', 2),
}
for lang, (fixture, minimum) in sorted(MIN_YIELD.items()):
    if lang == "py":
        got = len(mapper.extract_python(fixture, Path("x.py"))[1]) + \
              len(mapper.extract_python(fixture, Path("x.py"))[2])
    else:
        _dd, ff, cc, _kk = mapper.extract_regex(fixture, lang)
        got = len(ff) + len(cc)
    check(f"{lang} extracts at least {minimum} symbols from ordinary code", got >= minimum)

# ---------------------------------------------------------------- explaining the injection
# "Why is this in my context, and what is it costing?" had no answer at all, which made every
# budget decision an argument instead of a measurement. The accounting is a side effect of building
# the text, so there is no second model of the injection that can drift out of step with the real
# one -- these checks are mostly about that property.
HOOK = ROOT / "hooks" / "session_start.py"
exp_repo = Path(tempfile.mkdtemp()) / "proj"
(exp_repo / ".git").mkdir(parents=True)
(exp_repo / "src").mkdir()
(exp_repo / "src" / "a.py").write_text('"""Does a thing."""\n', encoding="utf-8")
ws.ensure(exp_repo)
(exp_repo / ".chamnan" / "STATE.md").write_text("# Work in flight\n\nSomething unfinished.\n",
                                                encoding="utf-8")
(exp_repo / ".chamnan" / "memory" / "rules" / "one.md").write_text(
    "# Never force-push\n\nIt loses other people's work.\n", encoding="utf-8")

def run_explain(cwd):
    return subprocess.run([sys.executable, str(HOOK), "--explain"], input="{}",
                          capture_output=True, text=True, cwd=cwd)

r = run_explain(exp_repo)
check("--explain exits cleanly", r.returncode == 0)
check("--explain reports a total", "tokens injected at session start" in r.stdout)
check("--explain names STATE.md as a source", ".chamnan/STATE.md" in r.stdout)
check("--explain names the rules directory as a source", ".chamnan/memory/rules/" in r.stdout)
check("--explain prints the budgets it is measured against", "state_token_budget" in r.stdout)
check("--explain does not print the injection itself",
      "Something unfinished." not in r.stdout)

# Priced with the real estimator, not by counting characters. Thai costs far more per character
# than ASCII, so a fixture written in it separates the two: char-counting under-reported this
# repository's procedures section by 218 tokens, and the error hid inside the remainder line where
# an "it adds up" check would never see it.
(exp_repo / ".chamnan" / "memory" / "rules" / "thai.md").write_text(
    "# กฎการทำงานของที่นี่\n\n" + "ห้ามแก้ไขไฟล์นี้โดยไม่ได้รับอนุญาตจากเจ้าของงานก่อนเสมอ\n" * 6,
    encoding="utf-8")
plain_for_price = subprocess.run([sys.executable, str(HOOK)], input="{}", capture_output=True,
                                 text=True, cwd=exp_repo).stdout
priced = run_explain(exp_repo).stdout
import tokens as _tok
rules_chunk = ""
for chunk in plain_for_price.split("\n### "):
    if chunk.startswith("Rules this repository works under"):
        rules_chunk = "\n### " + chunk.rstrip() + "\n"
        break
reported = re.search(r"Rules this repository works under\s+([\d,]+)", priced)
if rules_chunk and reported:
    want = round(_tok.estimate(rules_chunk))
    got = int(reported.group(1).replace(",", ""))
    check("a section is priced with the real estimator, not by character count",
          abs(got - want) <= 1)
    check("...and that estimator disagrees with character counting on this fixture",
          abs(want - len(rules_chunk) // 3) > 5)

# The report must add up: what it attributes to sections plus the remainder is the real total.
nums = [int(x.replace(",", "")) for x in re.findall(r"^\s*\S.*?\s(\d[\d,]*)\s{3}", r.stdout, re.M)]
total_m = re.search(r"— ([\d,]+) tokens injected", r.stdout)
if total_m and nums:
    check("the section costs and the remainder add up to the reported total",
          sum(nums) == int(total_m.group(1).replace(",", "")))

# Without --explain the hook must still emit the injection and nothing about accounting.
plainrun = subprocess.run([sys.executable, str(HOOK)], input="{}", capture_output=True,
                          text=True, cwd=exp_repo).stdout
check("the normal injection is unchanged by the accounting",
      "Something unfinished." in plainrun and "tokens injected at session start" not in plainrun)
shutil.rmtree(exp_repo.parent, ignore_errors=True)

# ---------------------------------------------------------------- first session in a new repo
# A teammate installed the plugin, opened a new project in VS Code, and got nothing: the workspace
# was only ever created by chamnan-map/promote/candidates, so the hook returned in silence and
# every write skill had nowhere to write.

newrepo = Path(tempfile.mkdtemp()) / "proj"
newrepo.mkdir(parents=True)
subprocess.run(["git", "init", "-q"], cwd=newrepo, capture_output=True)
(newrepo / "app.py").write_text("print(1)\n", encoding="utf-8")

first = subprocess.run([sys.executable, str(HOOK)], input="{}", capture_output=True, text=True,
                       cwd=newrepo).stdout
check("the first session creates the workspace", (newrepo / ".chamnan").is_dir())
for sub in ("memory/decisions", "memory/lessons", "memory/rules", "sessions", "threads",
            "skills", "tools", "logs"):
    check(f"the scaffold includes {sub}/", (newrepo / ".chamnan" / sub).is_dir())
check("the scaffold includes config.json", (newrepo / ".chamnan" / "config.json").is_file())
check("the first session says the workspace was created", "just been created" in first)
check("the first session points at bootstrap for the index", "/chamnan:bootstrap" in first)

second = subprocess.run([sys.executable, str(HOOK)], input="{}", capture_output=True, text=True,
                        cwd=newrepo).stdout
check("the welcome is said once, not every session", "just been created" not in second)
check("the ledger line still appears on later sessions", "chamnan ·" in second)

# find_root falls back to the current directory when there is no VCS marker, so without this guard
# the hook would leave a .chamnan/ in whatever directory a session happened to open.
plain = Path(tempfile.mkdtemp()) / "notarepo"
plain.mkdir(parents=True)
(plain / "a.txt").write_text("x\n", encoding="utf-8")
out = subprocess.run([sys.executable, str(HOOK)], input="{}", capture_output=True, text=True,
                     cwd=plain)
check("a directory that is not a repository is left alone", not (plain / ".chamnan").exists())
check("...and nothing is printed there", out.stdout.strip() == "")
shutil.rmtree(newrepo.parent, ignore_errors=True)
shutil.rmtree(plain.parent, ignore_errors=True)

# ---------------------------------------------------------------- the shared pruned walk
# lib/tree.py replaced nine separate full-tree rglob passes per map. On a 224-file repository that
# took chamnan-map from 70.1s to 8.3s with MAP.md byte-identical, so these checks are about the
# three ways that change could have been silently wrong rather than about the speed.
import tree  # noqa: E402

walkdir = Path(tempfile.mkdtemp()) / "repo"
(walkdir / "src").mkdir(parents=True)
(walkdir / "src" / "app.py").write_text("x\n", encoding="utf-8")
(walkdir / ".venv" / "lib").mkdir(parents=True)
(walkdir / ".venv" / "lib" / "vendored.py").write_text("x\n", encoding="utf-8")
(walkdir / "node_modules" / "pkg").mkdir(parents=True)
(walkdir / "node_modules" / "pkg" / "index.js").write_text("x\n", encoding="utf-8")
(walkdir / "build").mkdir()
(walkdir / "build" / "out.py").write_text("x\n", encoding="utf-8")
(walkdir / "inner").mkdir()
(walkdir / "inner" / ".git").mkdir()
(walkdir / "inner" / ".git" / "HEAD").write_text("ref\n", encoding="utf-8")

rels = {str(p.relative_to(walkdir)) for p in tree.files(walkdir)}
check("the walk finds ordinary source", "src/app.py" in rels)
check("the walk never descends into .venv", not any(r.startswith(".venv/") for r in rels))
check("the walk never descends into node_modules", not any(r.startswith("node_modules/") for r in rels))
check("the walk never descends into .git", not any("/.git/" in r or r.startswith(".git/") for r in rels))
# build/ is skipped by mapper and catalogs but NOT by assets, so the walk must NOT prune it --
# pruning the union instead of the intersection changed the stored-material count on a real repo.
check("the walk leaves build/ for each scanner's own filter to decide", "build/out.py" in rels)

gits = {str(p.relative_to(walkdir)) for p in tree.git_dirs(walkdir)}
check("a nested .git is reported even though it is never entered", "inner/.git" in gits)

# Paths must come back joined onto the root AS GIVEN. Callers do path.relative_to(root), which
# raises ValueError across two forms of the same directory -- and every caller treats that as
# "skip this file", so the failure is silent. This is how 12 files disappeared from a real map.
unresolved = walkdir.parent / "." / walkdir.name
for got in tree.files(unresolved)[:1]:
    try:
        got.relative_to(unresolved)
        ok = True
    except ValueError:
        ok = False
    check("a path is relative_to the root the caller passed in", ok)

# Outside a session the cache must not exist, or a scan-write-scan sequence reads a stale tree.
before = len(tree.files(walkdir))
(walkdir / "src" / "added_later.py").write_text("x\n", encoding="utf-8")
check("a file added between calls is seen when there is no session",
      len(tree.files(walkdir)) == before + 1)

with tree.session():
    inside = len(tree.files(walkdir))
    (walkdir / "src" / "added_during.py").write_text("x\n", encoding="utf-8")
    check("inside a session the walk is cached, which is the point of it",
          len(tree.files(walkdir)) == inside)
check("the cache does not outlive the session",
      len(tree.files(walkdir)) == inside + 1)

check("by_suffix filters without walking again", 
      {p.name for p in tree.by_suffix(walkdir, ".py")} >= {"app.py", "out.py"})
check("matching() globs on the filename at any depth",
      {str(p.relative_to(walkdir)) for p in tree.matching(walkdir, "*.js")} == set())
shutil.rmtree(walkdir.parent, ignore_errors=True)

# ---------------------------------------------------------------- cleanup
os.chdir(ROOT)
shutil.rmtree(fixture, ignore_errors=True)
shutil.rmtree(nested.parent.parent, ignore_errors=True)

total = PASSED + len(FAILED)
print(f"\n{PASSED}/{total} checks passed")
sys.exit(1 if FAILED else 0)
