#!/usr/bin/env python3
"""Build the statistic site from what is already on disk. Reads everything, writes only `data/`.

READS: .chamnan/logs/*.jsonl via {

🎯 [owner, 2026-09-23] A folder in chamnan for statistics, split into `data/` and `report/`,
rendered as a page you click through. **No money and no model names.** Page one is what using this
repository looks like and what difference chamnan makes; page two is which features actually fire,
how often something is found, where the model's own mistakes are, and which files keep being
edited. Newest at the top.

**Every number names the file it came from, and a panel with no source is marked and greyed out.**
A dashboard that invents a figure is worse than one that says it cannot — three panels are in that
state today and the page says which, because an empty panel that explains itself is how a missing
recorder gets built.

    build_statistic.py            write data/ and report/
    build_statistic.py --data     data only, for a machine

The data is written twice on purpose: as JSON under `data/` for anything that wants to read it, and
inlined into the HTML so the page opens from the filesystem with no server. A `fetch()` of a local
JSON file is blocked by the browser's own origin rules, and a dashboard that needs a server running
is a dashboard nobody opens.
"""
import argparse
import collections
import json
import os
import pathlib
import re
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
PLUGIN = HERE.parent
ROOT = PLUGIN.parent.parent
WS = ROOT / ".chamnan"
LOGS = WS / "logs"
DATA = HERE / "data"
REPORT = HERE / "report"

sys.path.insert(0, str(PLUGIN / "lib"))
try:
    import tokens as _tok
except Exception:                       # noqa: BLE001 — the estimator is a nicety, not a need
    _tok = None

DAYS = 30
BUG = "\U0001F41B"


# ---------------------------------------------------------------- reading what is already there

def rows(name):
    """One log, as a list of dicts. Missing or unreadable is an empty list, said once by caller."""
    path = LOGS / name
    if not path.is_file():
        return []
    out = []
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        return []
    return out


def when_of(row):
    """Seconds since the epoch for a row, whichever of the four stamp spellings it uses."""
    for key in ("at", "t", "ts", "when"):
        v = row.get(key)
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str) and len(v) >= 19:
            try:
                return time.mktime(time.strptime(v[:19], "%Y-%m-%dT%H:%M:%S"))
            except ValueError:
                continue
    return None


def day_of(row):
    w = when_of(row)
    return time.strftime("%Y-%m-%d", time.localtime(w)) if w else None


def estimate(text):
    return int(_tok.estimate(text)) if _tok else max(1, len(text) // 4)


def transcripts():
    """This project's transcript files, for whichever config directory is in use."""
    home = os.environ.get("CLAUDE_CONFIG_DIR") or str(pathlib.Path.home() / ".claude")
    key = str(ROOT.resolve()).replace("/", "-")
    base = pathlib.Path(home) / "projects" / key
    return sorted(base.glob("*.jsonl")) if base.is_dir() else []


# ---------------------------------------------------------------- the panels

def token_kinds():
    """What KIND the tokens were, across every session this repository has had.

    🔴 No price and no multiplier. The first version carried a `rate` column — 0.1x, 5x — and
    those are ANTHROPIC's ratios. This plugin does not know which model anybody runs, whether it
    is local, or what any of it is charged at, and a page that implies one vendor's economics is
    wrong for every reader who uses another. What is true everywhere is the SPLIT: a cached read
    is the cheapest kind of token on every host that has caching at all, and the share is the
    number. (owner, 2026-09-23: *"เราไม่รู้ว่าคนใช้งานจะใช้ llm ค่ายไหน หรือว่ามี local ไหม"*)
    """
    tot = collections.Counter()
    n = 0
    for path in transcripts():
        try:
            with path.open(encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if '"usage"' not in line:
                        continue
                    try:
                        rec = json.loads(line)
                    except ValueError:
                        continue
                    u = (rec.get("message") or {}).get("usage")
                    if not isinstance(u, dict):
                        continue
                    n += 1
                    tot["cache_read"] += int(u.get("cache_read_input_tokens") or 0)
                    tot["cache_write"] += int(u.get("cache_creation_input_tokens") or 0)
                    tot["output"] += int(u.get("output_tokens") or 0)
                    tot["new_input"] += int(u.get("input_tokens") or 0)
        except OSError:
            continue
    total = sum(tot.values()) or 1
    return {"requests": n,
            "kinds": [{"kind": k, "tokens": v, "share": round(100.0 * v / total, 2)}
                      for k, v in tot.most_common()]}


# ---------------------------------------------------------------- with it, and without it

def impact():
    """The difference the plugin makes, counted as EVENTS rather than claimed as a saving.

    🎯 [owner, 2026-09-23] The page's first question is *what is different with this and without
    it*. The tempting answer — "it saved X tokens" — cannot be had: nothing here knows what a
    session without the plugin would have cost, and the 2026-09-22 comparison recorded that there
    is no way to measure it on one machine with one person's work.

    🔴 What CAN be counted is every moment the plugin changed the course of a session, from the
    logs that already exist. Each row is a thing that happened, and beside it the thing that would
    have happened instead. No vendor, no model, no currency — this is true on any host.
    """
    ptr = rows("pointer.jsonl")
    named = sum(1 for r in ptr if r.get("named"))
    longs = len(rows("long_reads.jsonl"))
    # 🐛 [2026-09-23] This read a `seen` field that scratch.jsonl has never carried, so the count
    # was silently zero. A repeat is a FINGERPRINT that appears more than once — which is what the
    # watcher itself keys on, and the only definition the rows support.
    seen = collections.Counter(tuple(r.get("fp") or ()) for r in rows("scratch.jsonl") if r.get("fp"))
    repeats = sum(v - 1 for v in seen.values() if v > 1)
    fails = rows("failures.jsonl")
    try:
        sys.path.insert(0, str(PLUGIN / "lib"))
        import gotcha as _g
        caught = sum(1 for _k, v in _g.repeats(WS).items() if v[0] >= _g.REPEATS)
    except Exception:                    # noqa: BLE001 — a count is never worth a failed build
        caught = 0
    local = local_model()
    chars = sum(d["chars"] for d in local)
    blocks = rows("block_shape.jsonl")
    block_tok = median([int(b.get("tok") or 0) for b in blocks if b.get("tok")])
    return {
        "rows": [
            {"with": named, "what": "knowledge named before a file was opened",
             "without": "the session opens the file and finds out for itself, or does not",
             "th": "ความรู้ถูกชี้ก่อนเปิดไฟล์", "source": "logs/pointer.jsonl"},
            {"with": longs, "what": "long documents flagged before they were read whole",
             "without": "the whole document enters the context",
             "th": "เอกสารยาวถูกเตือนก่อนอ่านทั้งไฟล์", "source": "logs/long_reads.jsonl"},
            {"with": repeats, "what": "throwaway scripts recognised as written before",
             "without": "the same script is thought up again from scratch",
             "th": "สคริปต์ใช้แล้วทิ้งที่เคยเขียนมาแล้ว", "source": "logs/scratch.jsonl"},
            {"with": caught, "what": "failures about to be repeated, named before the command ran",
             "without": "the same command fails the same way again",
             "th": "ความล้มเหลวที่กำลังจะซ้ำ ถูกทักก่อนรัน", "source": "logs/failures.jsonl"},
            {"with": chars, "what": "characters a local model read so the session did not have to",
             "without": "every one of them enters the context",
             "th": "ตัวอักษรที่โมเดลในเครื่องอ่านแทน", "source": "state/local_assist/"},
        ],
        "block_tokens": block_tok,
        "note": "counted as events, never as a saving — nothing here knows what a session without "
                "this would have cost",
        "note_th": "นับเป็นเหตุการณ์ ไม่ใช่ยอดประหยัด — ไม่มีใครรู้ว่าถ้าไม่มีมันจะกินเท่าไร",
    }


def median(xs):
    xs = sorted(x for x in xs if x)
    return xs[len(xs) // 2] if xs else 0


# ---------------------------------------------------------------- the period series

# 🎯 [owner, 2026-09-23] Daily and monthly, and **twelve months is the ceiling** — a dashboard that
# grows without bound becomes the thing it was measuring. The day rows are what a reader drills
# into; the month rows are what they scan.
KEEP_MONTHS = 12
KEEP_DAYS = 370


def series():
    """One row per day and per month: the counts every page's chart is drawn from."""
    day = collections.defaultdict(lambda: collections.Counter())
    for name, field in (("commands.jsonl", "commands"), ("pointer.jsonl", "opens"),
                        ("edits.jsonl", "edits"), ("long_reads.jsonl", "long_reads"),
                        ("scratch.jsonl", "scratch"), ("subagent_start.jsonl", "agents"),
                        ("failures.jsonl", "failures")):
        for r in rows(name):
            d = day_of(r)
            if d:
                day[d][field] += 1
    for r in rows("pointer.jsonl"):
        d = day_of(r)
        if d and r.get("named"):
            day[d]["named"] += 1
    for p in sorted((WS / "state" / "local_assist" / "daily").glob("*.jsonl")):
        try:
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.strip():
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                day[p.stem]["local_calls"] += 1
                day[p.stem]["local_chars"] += int(r.get("saved_chars") or 0)
        except OSError:
            continue

    fields = ("commands", "opens", "edits", "named", "long_reads", "scratch", "agents",
              "failures", "local_calls", "local_chars")
    days = [{"day": d, **{f: day[d].get(f, 0) for f in fields}}
            for d in sorted(day)][-KEEP_DAYS:]
    month = collections.defaultdict(lambda: collections.Counter())
    for row in days:
        m = row["day"][:7]
        for f in fields:
            month[m][f] += row[f]
        month[m]["days"] += 1
    months = [{"month": m, **{f: month[m].get(f, 0) for f in fields},
               "days": month[m]["days"]} for m in sorted(month)][-KEEP_MONTHS:]
    return {"fields": list(fields), "days": days, "months": months,
            "keep_months": KEEP_MONTHS}


def context_parts():
    """What the context is made of, for the parts a REPOSITORY controls.

    🔴 The host's system prompt and tool definitions are not on disk. They are returned as a row
    with no number and a reason, never estimated — guessing them would invent the denominator of
    every other figure on the page.
    """
    def total(paths):
        n = 0
        for p in paths:
            try:
                n += estimate(p.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                pass
        return n

    agents = sorted((ROOT / ".claude" / "agents").glob("*.md"))
    mds = [p for p in (ROOT / "CLAUDE.md",) if p.is_file()]
    mds += sorted(ROOT.glob("*/CLAUDE.md"))
    skills = sorted((WS / "skills").glob("*.md"))
    shapes = [r for r in rows("block_shape.jsonl") if r.get("tok")]
    block = int(shapes[-1]["tok"]) if shapes else 0
    return [
        {"part": "CLAUDE.md", "files": len(mds), "tokens": total(mds), "owner": "this repository"},
        {"part": "custom agents", "files": len(agents), "tokens": total(agents),
         "owner": "this repository"},
        {"part": "chamnan's session block", "files": 0, "tokens": block,
         "owner": "chamnan, per session"},
        {"part": "skills on disk", "files": len(skills), "tokens": total(skills),
         "owner": "only the routed one is injected"},
        {"part": "system prompt / host tools / messages", "files": 0, "tokens": None,
         "owner": "the host — not on disk, not guessable"},
    ]


def by_hour():
    """When the work happens. Bash is one series; opens and edits are their own — never added."""
    hours = {"commands": [0] * 24, "opens": [0] * 24, "edits": [0] * 24}
    for name, key in (("commands.jsonl", "commands"), ("pointer.jsonl", "opens"),
                      ("edits.jsonl", "edits")):
        for r in rows(name):
            w = when_of(r)
            if w:
                hours[key][int(time.strftime("%H", time.localtime(w)))] += 1
    return hours


def by_kind_and_place():
    """What kind of file is opened, and which part of the repository it sits in."""
    ext = collections.Counter()
    top = collections.Counter()
    for name in ("pointer.jsonl", "edits.jsonl", "long_reads.jsonl"):
        for r in rows(name):
            p = str(r.get("path") or r.get("fp") or "")
            if not p:
                continue
            ext[pathlib.PurePath(p).suffix or "(none)"] += 1
            top[p.split("/", 1)[0]] += 1
    return {"by_extension": ext.most_common(10), "by_directory": top.most_common(10)}


def read_vs_write():
    """Opens against changes, per day. The Write/Edit split is reported only where it exists."""
    opens, edits, with_op = collections.Counter(), collections.Counter(), 0
    for r in rows("pointer.jsonl") + rows("long_reads.jsonl"):
        d = day_of(r)
        if d:
            opens[d] += 1
    for r in rows("edits.jsonl"):
        d = day_of(r)
        if d:
            edits[d] += 1
        if r.get("op"):
            with_op += 1
    days = sorted(set(opens) | set(edits), reverse=True)[:DAYS]
    return {"days": days, "opens": [opens[d] for d in days], "edits": [edits[d] for d in days],
            "op_known": with_op, "op_total": len(rows("edits.jsonl"))}


def block_sections():
    """The last block: what it was made of, and which store each section came from."""
    shapes = [r for r in rows("block_shape.jsonl") if r.get("sec")]
    if not shapes:
        return {"sections": [], "note": "no block has been recorded yet"}
    last = shapes[-1]
    srcs = last.get("srcs") or {}
    return {"bytes": last.get("bytes"), "tok": last.get("tok"),
            "sections": [{"title": k, "bytes": v, "from": srcs.get(k, "")}
                         for k, v in sorted(last["sec"].items(), key=lambda kv: -kv[1])],
            "srcs_known": len(srcs)}


def features():
    """Which chamnan features actually fire, and which cannot answer because nothing records them."""
    ptr = rows("pointer.jsonl")
    sub = rows("subagent_start.jsonl")
    out = [
        {"feature": "file pointer", "fired": sum(1 for r in ptr if r.get("named")),
         "chances": len(ptr), "source": "pointer.jsonl"},
        {"feature": "subagent block",
         "fired": sum(1 for r in sub if r.get("outcome") == "delivered"),
         "chances": len(sub), "source": "subagent_start.jsonl"},
        {"feature": "scratch watcher", "fired": len(rows("scratch.jsonl")),
         "chances": len(rows("commands.jsonl")), "source": "scratch.jsonl"},
        {"feature": "bulk-read notice", "fired": len(rows("long_reads.jsonl")),
         "chances": len(rows("commands.jsonl")), "source": "long_reads.jsonl"},
        {"feature": "gotcha (repeat failures)", "fired": len(rows("failures.jsonl")),
         "chances": len(rows("commands.jsonl")), "source": "failures.jsonl"},
    ]
    # 🔴 Named, not omitted. Four guards shipped on 2026-09-23 print a notice and record nothing,
    # so `silence.py` cannot see them either — a feature with no recorder is invisible to the tool
    # built to find invisible features, which is exactly why the page has to say the name out loud.
    for name in ("boundary guard", "canonical invocation", "sibling sweep", "recorded lesson"):
        out.append({"feature": name, "fired": None, "chances": None, "source": "no recorder yet"})
    return out


def found():
    """How often something is actually found: gates, mutation proofs, recorded lessons."""
    gates = rows("gate_runs.jsonl")
    try:
        proofs = json.loads((WS / "state" / "mutation_proofs.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        proofs = {}
    pool = len(list((WS / "tools" / "checks").glob("*.py")))
    try:
        marks = json.loads((WS / "state" / "gotcha_marks.json").read_text(encoding="utf-8"))
        marks = int(marks.get("marks", 0))
    except (OSError, ValueError, AttributeError):
        marks = 0
    return {"gate_runs": [{"day": day_of(g), "checks": g.get("checks"),
                           "failing": g.get("failing"), "seconds": g.get("seconds")}
                          for g in gates[-20:]][::-1],
            "mutation_proved": len({v.get("check") for v in proofs.values()
                                    if isinstance(v, dict) and v.get("check")}),
            "guard_pool": pool, "recorded_lessons": marks}


def mistakes():
    """The model's own mistakes: what failed, and how much of it was a repeat."""
    fails = rows("failures.jsonl")
    keyed = collections.Counter()
    for r in fails:
        keyed[(str(r.get("tool")), str(r.get("subj"))[:120], str(r.get("err"))[:80])] += 1
    per_day = collections.Counter(day_of(r) for r in fails if day_of(r))
    return {"failures": len(fails),
            "repeats": sum(v - 1 for v in keyed.values() if v > 1),
            "per_day": sorted(per_day.items(), reverse=True)[:DAYS],
            "note": "the recorder was starved until 2026-09-23; the series starts there"}


def busiest_files():
    """Which files keep being edited — and how many recorded lessons each one already carries."""
    edits = collections.Counter()
    opens = collections.Counter()
    last = {}
    for r in rows("edits.jsonl"):
        p = str(r.get("fp") or "")
        if not p:
            continue
        edits[p] += 1
        w = when_of(r)
        if w:
            last[p] = max(last.get(p, 0), w)
    for r in rows("pointer.jsonl"):
        p = str(r.get("path") or "")
        if p:
            opens[p] += 1
    out = []
    for path, n in edits.most_common(30):
        full = ROOT / path
        bugs = 0
        try:
            bugs = full.read_text(encoding="utf-8", errors="replace").count(BUG)
        except OSError:
            bugs = 0
        out.append({"path": path, "edits": n, "opens": opens.get(path, 0), "lessons": bugs,
                    "last": time.strftime("%Y-%m-%d %H:%M", time.localtime(last[path]))
                    if path in last else ""})
    return out


def local_model():
    """What the local model read so a session did not have to — the corrected figure."""
    base = WS / "state" / "local_assist" / "daily"
    days = []
    if base.is_dir():
        for p in sorted(base.glob("*.jsonl"), reverse=True)[:DAYS]:
            calls = chars = 0
            try:
                for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                    if not line.strip():
                        continue
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    calls += 1
                    chars += int(r.get("saved_chars") or 0)
            except OSError:
                continue
            days.append({"day": p.stem, "calls": calls, "chars": chars})
    return days


# ---------------------------------------------------------------- writing

def build():
    return {
        "built": time.strftime("%Y-%m-%d %H:%M"),
        "repo": ROOT.name,
        "impact": impact(),
        "series": series(),
        "token_kinds": token_kinds(),
        "context_parts": context_parts(),
        "by_hour": by_hour(),
        "places": by_kind_and_place(),
        "read_vs_write": read_vs_write(),
        "block": block_sections(),
        "features": features(),
        "found": found(),
        "mistakes": mistakes(),
        "files": busiest_files(),
        "local": local_model(),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", action="store_true", help="write data/ and stop")
    a = ap.parse_args()
    data = build()
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "statistic.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n",
                                         encoding="utf-8")
    print(f"  data/statistic.json  {len(json.dumps(data)):,} bytes")
    if a.data:
        return 0
    # The same data inlined, because a `fetch()` of a local file is blocked by the browser's own
    # origin rules and a dashboard that needs a server running is one nobody opens.
    blob = "window.STAT = " + json.dumps(data, ensure_ascii=False) + ";\n"
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / "data.js").write_text(blob, encoding="utf-8")
    print(f"  report/data.js       {len(blob):,} bytes")
    for page in ("index.html", "features.html", "usage.html"):
        if not (REPORT / page).is_file():
            print(f"  {page} is missing — the page is not generated, only its data")
    return 0


if __name__ == "__main__":
    sys.exit(main())
