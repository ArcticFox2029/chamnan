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
import schema  # noqa: E402
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

(pk / "junk.csv").write_bytes(bytes(range(256)) * 20)
out = peek_mod.peek(pk / "junk.csv")
check("peek survives a malformed file", "could not read" in out or "printable" in out)
check("peek reports the saving", "instead of" in out)
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
      len(big_out) < ws.DEFAULT_CONFIG["index_token_budget"] * 3.6 * 1.5)
check("over-budget index keeps every directory visible",
      all(f"**pkg{i}/**" in big_out for i in range(4)))
check("over-budget index says it rolled up", "Rolled up by directory" in big_out)
check("over-budget index does not silently truncate", "mod399" not in big_out or "pkg3" in big_out)
wide.write_text(rendered, encoding="utf-8")

start_out = run_hook("session_start.py", {})
check("session start injects the index", "Architecture index" in start_out)
check("SESSION START NEVER INJECTS A SECRET", "Hunter2Pass" not in start_out)

# ---------------------------------------------------------------- cleanup
os.chdir(ROOT)
shutil.rmtree(fixture, ignore_errors=True)
shutil.rmtree(nested.parent.parent, ignore_errors=True)

total = PASSED + len(FAILED)
print(f"\n{PASSED}/{total} checks passed")
sys.exit(1 if FAILED else 0)
