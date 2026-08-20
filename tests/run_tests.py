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
import assets as assets_mod  # noqa: E402
import deploy as deploy_mod  # noqa: E402
import schema  # noqa: E402
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

# ---------------------------------------------------------------- cleanup
os.chdir(ROOT)
shutil.rmtree(fixture, ignore_errors=True)
shutil.rmtree(nested.parent.parent, ignore_errors=True)

total = PASSED + len(FAILED)
print(f"\n{PASSED}/{total} checks passed")
sys.exit(1 if FAILED else 0)
