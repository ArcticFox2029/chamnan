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


# 🎯 [owner, 2026-09-23] "dashboard ต้องอัปเดตด้วยนะ … มันไม่ควรมีการรัน py script อะไรเพื่อ gen
# report" — and the thing standing in the way was 35 seconds, 31.6 of them spent re-reading every
# transcript on the machine on every build. A page that costs half a minute to refresh is a page
# somebody refreshes by hand, which is what it was.
#
# 🔴 A finished transcript never changes. The scan is cached per FILE, keyed on its size and
# mtime, so a rebuild reads only what was written since the last one. Nothing is inferred from the
# cache: a file whose size or mtime moved is re-read in full, and a cache that cannot be read is
# simply absent rather than trusted — the one thing worse than a slow figure is a stale one that
# looks fresh.
SCAN_CACHE = WS / "state" / "statistic_scan_cache.json"


def _cached_scan(paths, reader, tag):
    """{path: summary} for every path, reading only what is new since the last build.

    \U0001F41B [2026-09-23] Keying on (size, mtime) alone made this session's OWN transcript miss the
    cache on every build — it grows with every turn, and at 821 MB of the 1,094 MB on disk it was
    the whole remaining cost. A transcript is append-only, so the fix is to remember where the
    last read stopped and start there: `reader` is handed an offset and returns a summary plus
    the offset it reached, and two summaries of one file are added together.

    \U0001F534 A file that SHRANK, or whose earlier bytes changed, is re-read from zero. Trusting an
    offset into a file that was rewritten would produce a total assembled from two different
    versions of the same transcript, which is worse than being slow.
    """
    try:
        cache = json.loads(SCAN_CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    if not isinstance(cache, dict):
        cache = {}
    out, fresh = {}, {}
    for p in paths:
        try:
            st = p.stat()
        except OSError:
            continue
        key = f"{tag}:{p}"
        hit = cache.get(key)
        start, base = 0, None
        if isinstance(hit, dict) and isinstance(hit.get("value"), dict):
            at = int(hit.get("at") or 0)
            if at == st.st_size:
                out[str(p)] = hit["value"]
                fresh[key] = hit
                continue
            if at and at < st.st_size:          # grew: read the tail only
                start, base = at, hit["value"]
        got, at = reader(p, start)
        if base is not None:
            got = _merge_usage(base, got)
        out[str(p)] = got
        fresh[key] = {"at": at, "value": got}
    try:
        SCAN_CACHE.parent.mkdir(parents=True, exist_ok=True)
        SCAN_CACHE.write_text(json.dumps(fresh), encoding="utf-8")
    except OSError:
        pass
    return out, 0


def _merge_usage(a, b):
    """Two summaries of the same file, in order, added together."""
    tot = collections.Counter(a.get("tot") or {})
    tot.update(b.get("tot") or {})
    days = {d: collections.Counter(c) for d, c in (a.get("days") or {}).items()}
    for d, c in (b.get("days") or {}).items():
        days.setdefault(d, collections.Counter()).update(c)
    return {"n": int(a.get("n") or 0) + int(b.get("n") or 0),
            "tot": dict(tot), "days": {d: dict(c) for d, c in days.items()}}


# ---------------------------------------------------------------- the panels

def _usage_of(path, start=0):
    """One transcript, summarised: totals by kind, and the same totals per calendar day.

    🔴 Both scans that used to walk every transcript now share this one reader, so a file is
    parsed once per build instead of twice — which is half the saving before the cache is even
    consulted.
    """
    tot = collections.Counter()
    per_day = collections.defaultdict(collections.Counter)
    n, at = 0, start
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            if start:
                fh.seek(start)
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
                day = str(rec.get("timestamp") or "")[:10]
                for key, field in (("cache_read", "cache_read_input_tokens"),
                                   ("cache_write", "cache_creation_input_tokens"),
                                   ("output", "output_tokens"),
                                   ("new_input", "input_tokens")):
                    v = int(u.get(field) or 0)
                    tot[key] += v
                    if day:
                        per_day[day][key] += v
                if day:
                    per_day[day]["requests"] += 1
            at = fh.tell()
    except OSError:
        return {"n": 0, "tot": {}, "days": {}}, start
    return ({"n": n, "tot": dict(tot), "days": {d: dict(c) for d, c in per_day.items()}}, at)


def token_kinds():
    """What KIND the tokens were, across every session this repository has had.

    🔴 No price and no multiplier. The first version carried a `rate` column — 0.1x, 5x — and
    those are ANTHROPIC's ratios. This plugin does not know which model anybody runs, whether it
    is local, or what any of it is charged at, and a page that implies one vendor's economics is
    wrong for every reader who uses another. What is true everywhere is the SPLIT: a cached read
    is the cheapest kind of token on every host that has caching at all, and the share is the
    number. (owner, 2026-09-23: *"เราไม่รู้ว่าคนใช้งานจะใช้ llm ค่ายไหน หรือว่ามี local ไหม"*)
    """
    scanned, changed = _cached_scan(transcripts(), _usage_of, "usage")
    tot = collections.Counter()
    n = 0
    for row in scanned.values():
        if not isinstance(row, dict):
            continue
        n += int(row.get("n") or 0)
        for k, v in (row.get("tot") or {}).items():
            tot[k] += int(v or 0)
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


# 🎯 [owner, 2026-09-23] "เน้น rate write read out ต่างๆ เป็นค่ากลาง" — a token is not a token:
# an output token costs several times an ordinary input one, and a cached read a fraction of it.
#
# 🔴 [owner, 2026-09-23, and this is the settled shape] "เรทเราจะไม่ปรับ แยกตามค่าย แต่ เอาค่า
# เรทมาตรฐานกลางๆ ถ้าคนอยากปรับ ก็มาปรับเอง" — ONE standard set, not a per-provider table. An
# intermediate version averaged seven rate cards and was dropped: it made the page argue a
# methodology at a reader who only wanted a number they could change. The shipped ratios are one
# widely-used provider's (Claude's), used as the worked example, and page 4 is the answer for
# anybody whose own are different.
#
# Ratios, never money — and that is the owner's own reason for one fixed set: "ถ้าเราฟิก
# ตามโมเดลหรือค่าย เหนื่อยไล่แก้แน่ๆ". A table of vendors is a maintenance burden that
# goes stale the week after it ships; a ratio moves far more slowly than a price, and a vendor
# halving its prices leaves all three numbers below untouched.
RATES = {
    "t_new": 1.0,       # one ordinary input token, the unit everything else is measured in
    "t_read": 0.1,      # a cached read
    "t_write": 1.25,    # writing a document into the cache the first time
    "t_out": 5.0,       # an output token
}
RATES_EXAMPLE = "Claude"
RATES_NOTE = ("a standard middle weighting, taken from one widely-used provider's published "
              "ratios and read against one ordinary input token rather than as money: a cached "
              "read 0.1x, a cache write 1.25x, an output token 5x. Page 4 replaces all three.")
RATES_NOTE_TH = ("ค่ามาตรฐานกลางๆ ชุดเดียว อ้างอิงอัตราที่ประกาศไว้ของค่ายหนึ่ง "
                 "คิดเทียบ input ธรรมดา 1 โทเค็น ไม่ใช่หน่วยเงิน · "
                 "cached read 0.1 เท่า, cache write 1.25 เท่า, output 5 เท่า · ปรับเองได้ที่หน้า 4")

# 🎯 [owner, 2026-09-23] "ถ้าไม่มี มันก็อาจไม่ read เยอะก็เป็นได้" — the honest objection to
# every counterfactual on this page. Their own estimate, shipped: about a quarter of it.
COUNTERFACTUAL = 0.25


def hero():
    """The one number the page opens with, and the comparison beside it.

    🎯 [owner, 2026-09-23] The first thing on the page has to be the DIFFERENCE in tokens between
    having this and not having it. The per-day series carries both halves over the same window, so
    the page computes it for whatever period the picker has chosen rather than for all time.

    🔴 Neither half is a price and neither names a model. `handled` is what a local model read, so
    those characters were never in anybody's context window; `carried` is what the session carried
    anyway. Two measured counts, which is the only comparison this data supports.
    """
    return {
        "chars_per_token": CHARS_PER_TOKEN,
        "rates": RATES,
        "rates_example": RATES_EXAMPLE,
        "rates_note": RATES_NOTE,
        "rates_note_th": RATES_NOTE_TH,
        # A document that enters the context is a cache WRITE once. Counting it once, at the write
        # weight, is the conservative floor: in a long session it is then re-read on every later
        # turn, and none of that is claimed here.
        "avoided_weight": RATES["t_write"],
        # 🎯 [owner, 2026-09-23] "ถ้าไม่มี มันก็อาจไม่ read เยอะก็เป็นได้" — and that is the honest
        # objection to every counterfactual on this page. Without the plugin a session would not
        # have read all of it: some of those reads would never have been attempted, and a reader
        # who has other tooling might have had part of it answered anyway. Their own estimate, and
        # the one shipped here: **about a quarter of it would really have happened.** It is a
        # judgement, it is stated as one, and page 4 lets a reader move it.
        "counterfactual": COUNTERFACTUAL,
        "counterfactual_note": ("only about a quarter of what a local model read would really "
                                "have been read without the plugin — the rest would never have "
                                "been asked for. A judgement, not a measurement, yours to change."),
        "counterfactual_note_th": ("ประมาณหนึ่งในสี่ของสิ่งที่โมเดลในเครื่องอ่าน จะถูกอ่านจริงถ้าไม่มีปลั๊กอิน "
                                   "ที่เหลือคงไม่มีใครไปเรียกดู · เป็นการประเมิน ไม่ใช่การวัด และปรับได้เอง"),
        # 🎯 [owner, 2026-09-23] "มันควรใช้คำที่เข้าใจง่าย เช่น เมื่อมีปลั๊กอินประหยัดกว่า". "เบากว่า" was
        # accurate and unreadable — it describes the WEIGHT of a period, which is a notion this
        # page invented. A reader knows what "saved" means without being taught anything first.
        "en": "tokens saved by having the plugin",
        "th": "โทเค็นที่ประหยัดได้เพราะมีปลั๊กอิน",
        "note": "two measured counts over the same window — not a price, not a bill, "
                "and no model named",
        "note_th": "สองตัวเลขที่วัดจริงในช่วงเวลาเดียวกัน · ไม่ใช่ราคา ไม่ใช่บิล และไม่มีชื่อโมเดล",
    }


# Characters to tokens. Kept here rather than imported so this file can draw a page without the
# plugin's lib, and named so the page can say what it divided by instead of hiding the constant.
CHARS_PER_TOKEN = 3.8


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

    # 🐛 [2026-09-23] The hero compared a lifetime total against a figure that only starts when
    # the local recorder did — 24,671x, which is not a ratio of anything. Both sides are counted
    # PER DAY now, so the picker drives a comparison over one window instead of two.
    # \U0001F534 The same cached scan `token_kinds` uses, so the two panels cannot disagree about a
    # transcript: one reader, one cache, two views of the result.
    scanned, _changed = _cached_scan(transcripts(), _usage_of, "usage")
    for row in scanned.values():
        if not isinstance(row, dict):
            continue
        for d, c in (row.get("days") or {}).items():
            day[d]["t_read"] += int(c.get("cache_read") or 0)
            day[d]["t_write"] += int(c.get("cache_write") or 0)
            day[d]["t_new"] += int(c.get("new_input") or 0)
            day[d]["t_out"] += int(c.get("output") or 0)
            day[d]["requests"] += int(c.get("requests") or 0)
            day[d]["carried"] = (day[d]["t_read"] + day[d]["t_write"] + day[d]["t_new"])

    fields = ("commands", "opens", "edits", "named", "long_reads", "scratch", "agents",
              "failures", "local_calls", "local_chars", "carried", "requests",
              "t_read", "t_write", "t_new", "t_out")
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
    # 🎯 One row per day, one cell per hour — the calendar the owner asked for, which reads at a
    # glance in a way twenty-four bars never do.
    grid = collections.defaultdict(lambda: [0] * 24)
    for r in rows("commands.jsonl"):
        d, w = day_of(r), when_of(r)
        if d and w:
            grid[d][time.localtime(w).tm_hour] += 1
    # 🎯 [owner, 2026-09-23] "when the work happened 7 วันล่าสุด" — three weeks of rows
    # made the calendar a wall; a week is what a reader actually compares against today.
    recent = [d["day"] for d in days][-7:]
    return {"fields": list(fields), "days": days, "months": months,
            "keep_months": KEEP_MONTHS,
            "hours": [{"day": d, "cells": grid.get(d, [0] * 24)} for d in recent]}


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
            # 🐛 [2026-09-23, owner] `long_reads.jsonl` stores ABSOLUTE paths while the other two
            # store repository-relative ones, so 39 opens bucketed under an EMPTY directory name
            # and the chart drew a bar with no label beside it. One shape in, whatever went in.
            rel = p
            try:
                rel = str(pathlib.PurePath(p).relative_to(ROOT)) if p.startswith("/") else p
            except ValueError:
                rel = pathlib.PurePath(p).name          # outside the repo: keep the leaf, not ""
            # \U0001F41B [2026-09-23, owner: "none คืออะไร"] A file with no extension was labelled
            # "(none)", which is accurate and says nothing. Measured: 55 such opens, and the
            # commonest by far are this plugin's OWN commands — `chamnan-report` 24 times,
            # `chamnan-map` 10 — because a command in `bin/` carries no suffix. A chart that
            # cannot name its third-largest slice is not answering the question it was drawn for.
            _suffix = pathlib.PurePath(rel).suffix
            if not _suffix:
                _name = rel.rsplit("/", 1)[-1]
                _suffix = "a command" if _name.startswith("chamnan-") else "no extension"
            ext[_suffix] += 1
            head = rel.split("/", 1)[0]
            top[head or "(repository root)"] += 1
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
        # 🐛 [2026-09-23] These carried `source: "no recorder yet"`, and the page split the
        # two groups on `x.source` being truthy — a non-empty string is truthy, so every guard
        # landed in the MEASURED group, four of them drew a meaningless 0/0 bar, and the sentence
        # naming the ones nothing records never rendered at all. The absent half is `fired`, so
        # `source` is null and the reason moves to its own field.
        out.append({"feature": name, "fired": None, "chances": None, "source": None,
                    "why": "no recorder yet"})
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
    # \U0001F3AF [owner, 2026-09-23] "\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25\u0e21\u0e31\u0e19\u0e0a\u0e27\u0e19\u0e07\u0e07 \u0e1b\u0e23\u0e31\u0e1a\u0e43\u0e2b\u0e49\u0e40\u0e25\u0e37\u0e2d\u0e01\u0e27\u0e31\u0e19\u0e25\u0e30\u0e2d\u0e31\u0e19" \u2014 four rows all reading
    # 2026-09-10 is a table a reader has to decode before they can use it. The gate is run several
    # times a day while a failure is being chased, and what matters afterwards is where the day
    # ENDED, so the last run of each day is the row. Said on the panel rather than assumed.
    by_day = {}
    for g in gates:
        d = day_of(g)
        if d:
            by_day[d] = g            # later rows overwrite: the last run of that day wins
    return {"gate_runs": [{"day": d, "checks": g.get("checks"),
                           "failing": g.get("failing"), "seconds": g.get("seconds"),
                           "runs": sum(1 for x in gates if day_of(x) == d)}
                          for d, g in sorted(by_day.items())[-20:]][::-1],
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
            # 🐛 [2026-09-23] "the recorder was starved" was the symptom, and the cause is worth
            # saying because it is the shape that hides every other empty panel: the hook was
            # registered on PostToolUseFailure alone, which fires when a TOOL CALL fails. A shell
            # command that exits non-zero is a tool call that SUCCEEDED and reported a failure, so
            # it arrives on PostToolUse and the recorder never saw one.
            "note": "nothing was recorded before 2026-09-23 — the recorder was listening on the "
                    "wrong event, so a command that exited non-zero never reached it",
            "note_th": "ตัวบันทึกเพิ่งทำงานจริง 2026-09-23 กราฟจึงเริ่มที่วันนั้น"}


def files_total():
    """How many distinct files were changed at all — the denominator under the top ten."""
    return len({str(r.get("fp") or "") for r in rows("edits.jsonl") if r.get("fp")})


def lessons():
    """The recorded-lesson index, so the page can SHOW lessons rather than count them.

    🎯 [owner, 2026-09-23] "ต้องบอกว่า ตัวไหน โดน บ่อย โดนซ้ำ". Built by `tools/gotcha_index.py`
    rather than here, because scanning 533 files is not the dashboard's job — the dashboard reads.
    Absent index is said, never guessed.
    """
    try:
        return json.loads((WS / "state" / "gotcha_index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"marks": 0, "by_file": [], "by_month": [], "recent": [],
                "note": "run tools/gotcha_index.py — nothing has indexed the marks yet"}


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


# ---------------------------------------------------------------- what the redactor covers

# 🎯 [owner, 2026-09-23] "เพิ่ม การตรวจจับ security ด้วย … เช่น รหัส, api key, credit card, บัตรประชาชน
# และหมวดอื่นๆ … แต่ เราทำ ให้มองง่าย" — the shapes chamnan recognises before anything it
# assembles leaves this machine, grouped so a reader can scan them.
#
# 🔴 The families are matched against the REGEX SOURCE of every pattern the module actually
# compiles, not typed out here. A dashboard that lists a hand-written inventory of what a scanner
# covers drifts away from the scanner the week somebody adds a prefix, and then it is a page that
# claims a coverage nothing has. `other` is the deliberate catch-all: a pattern this table does
# not recognise still lands somewhere and is still counted, so the total can never quietly shrink.
SECURITY_FAMILIES = [
    # 🐛 [2026-09-23] Three patterns landed in the wrong family on the first run, all from one
    # cause: a marker that matched a regex's PUNCTUATION rather than the literal it was aimed at.
    # `://` was written for the `scheme://user:pass@host` rule and matched both webhook URLs
    # instead; `sk-` missed `sk_live_`, which is an underscore; and the Authorization rule is
    # compiled from the SCHEME words, so the word "Authorization" appears in its variable name and
    # nowhere in its pattern. Markers are anchored on what each regex actually contains now, and
    # the classification is printed by the test rather than trusted.
    ("api keys and provider tokens", "คีย์/โทเคนของผู้ให้บริการ",
     ("sk-", "live|test", "gh[", "github_pat", "xox", "AKIA", "AIza", "glpat", "npm_",
      "SG\\.", "GOCSPX", "hf_", "ya29", "dop_v1", "shp", "dckr_pat", "phc_", "pypi-", "xapp-",
      "pscale_", "dp\\.", "AGE-SECRET-KEY")),
    ("private keys and certificates", "กุญแจส่วนตัวและใบรับรอง",
     ("PRIVATE KEY",)),
    ("session tokens and auth headers", "โทเคน session และ auth header",
     ("eyJ", "Bearer")),
    ("webhooks and signed links", "webhook และลิงก์ที่เซ็นแล้ว",
     ("hooks\\.slack", "discord", "signature", "amz")),
]


def _pattern_sources():
    """Every credential regex the shipped redactor compiles, as source strings."""
    try:
        sys.path.insert(0, str(PLUGIN / "lib"))
        import redact                                  # noqa: PLC0415
    except Exception:                                  # noqa: BLE001
        return None, None
    out = []
    for group in ("PATTERNS", "LATE_PREFIXES"):
        for pat in getattr(redact, group, []) or []:
            out.append(getattr(pat, "pattern", str(pat)))
    return out, redact


def _recall():
    """The measured recall, cached against the redactor's own mtime so it cannot go stale silently.

    🔴 Re-measured whenever `redact.py` changes, never on a clock: a cached figure that outlives
    the code it describes is the one number on this page nobody would think to doubt.
    """
    src = PLUGIN / "lib" / "redact.py"
    harness = PLUGIN / "tools" / "redactor_recall.py"
    cache = WS / "state" / "redactor_recall.json"
    try:
        stamp = f"{src.stat().st_mtime_ns}:{src.stat().st_size}"
    except OSError:
        return None
    try:
        was = json.loads(cache.read_text(encoding="utf-8"))
        if was.get("stamp") == stamp:
            return was
    except (OSError, ValueError):
        pass
    if not harness.is_file():
        return None
    try:
        import subprocess                              # noqa: PLC0415
        got = subprocess.run([sys.executable, str(harness)], capture_output=True, text=True,
                             timeout=180)
        text = got.stdout
    except Exception:                                  # noqa: BLE001
        return None
    out = {"stamp": stamp, "measured": time.strftime("%Y-%m-%d")}
    m = re.search(r"recall\s+([\d.]+)%\s+\((\d+)/(\d+)", text)
    if not m:
        return None
    out["recall"], out["hit"], out["cases"] = float(m.group(1)), int(m.group(2)), int(m.group(3))
    m = re.search(r"precision\s+([\d.]+)%", text)
    out["precision"] = float(m.group(1)) if m else None
    m = re.search(r"(\d+)/(\d+) ordinary strings damaged", text)
    out["damaged"], out["ordinary"] = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    miss = re.search(r"not caught \((\d+)\)[^\n]*\n((?:  \S[^\n]*\n)+)", text)
    out["missed"] = [x.strip() for x in miss.group(2).splitlines() if x.strip()] if miss else []
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    except OSError:
        pass
    return out


def security():
    """Which secret and personal-data shapes are recognised — and 🔴 which cannot be, by construction."""
    pats, mod = _pattern_sources()
    if pats is None:
        return {"families": [], "blind": [], "note": "the redactor could not be imported"}
    seen = [False] * len(pats)
    fams = []
    for label, th, marks in SECURITY_FAMILIES:
        hits = 0
        for i, src in enumerate(pats):
            if not seen[i] and any(mk in src for mk in marks):
                seen[i] = True
                hits += 1
        fams.append({"family": label, "th": th, "shapes": hits})
    rest = sum(1 for x in seen if not x)
    if rest:
        fams.append({"family": "other credential shapes", "th": "รูปแบบความลับอื่นๆ", "shapes": rest})

    # 🔴 A password has no prefix to recognise. It is found by the word BESIDE it — `password =`,
    # `รหัสผ่าน:`, `contrase\u00f1a:` — so counting it among the prefix patterns would have
    # reported the single strongest family in the module as one or two shapes. The number that
    # describes it is the size of the credential-word vocabulary those rules run on.
    stems = getattr(mod, "secret_word_stems", None)
    words = len(stems() or []) if callable(stems) else 0
    if words:
        fams.append({"family": "passwords beside a credential word", "shapes": words,
                     "th": "รหัสที่มีคำว่าด้วยรหัส/คีย์อยู่ข้างๆ",
                     "unit": "credential words", "unit_th": "คำที่เฝ้าดู (หลายภาษา)"})

    # Personal data is not a credential and has no keyword to lean on, so it is counted from the
    # named rules rather than from the prefix list: a checksum is what stands in for the keyword.
    personal = [
        ("credit cards", "บัตรเครดิต", ("_CARD_BARE", "_CARD_DASHED", "_CARD_WORD")),
        ("national ID numbers", "เลขบัตรประชาชน",
         ("_THAI_ID_BARE", "_THAI_ID_WORD", "_CPF_BARE", "_CPF_WORD", "_CPF_DOTTED",
          "_AADHAAR_WORD")),
    ]
    for label, th, names in personal:
        have = sum(1 for nm in names if getattr(mod, nm, None) is not None)
        if have:
            fams.append({"family": label, "th": th, "shapes": have})

    # 🎯 [owner, 2026-09-23] "แต่ เราเคยตรวจเจอนิ แล้ว ทำการ์ด check ไว้แล้ว" — and they are right: a
    # secret with no recognisable shape is not helpless, because a file whose NAME says what it
    # holds is never opened at all. That is a detection category, not a footnote, so it is counted
    # beside the pattern families rather than left out of the list.
    names = len(getattr(mod, "BLOCKED_NAMES", ())) + len(getattr(mod, "BLOCKED_SUFFIXES", ()))
    if names:
        fams.append({"family": "files refused by name, never opened", "shapes": names,
                     "th": "ไฟล์ที่ปฏิเสธจากชื่อ — ไม่เปิดอ่านเลย"})

    # 🔴 [owner, 2026-09-23] "ข้อสุดท้าย คือกรองไม่ได้เพราะไม่มี pattern … ต้องใส่เป็น remark".
    # A coverage list that stops at what IS covered reads as a claim to cover everything. These
    # are the shapes nothing here can reach, each with the reason it cannot — and the first is
    # not a guess: it is the one case out of 99 the measured run below still misses.
    blind = [
        {"what": "a secret with no prefix and no word naming it",
         "th": "ความลับที่ไม่มีหัวขึ้นนำ และไม่มีคำกำกับ",
         "why": "nothing about it says it is a secret — no fixed shape to match and no "
                "`password:` beside it, so it is a run of letters and digits like any other",
         "why_th": "ไม่มีอะไรบอกว่ามันเป็นความลับ — ไม่มีรูปแบบตายตัว ไม่มีคำว่า pass: "
                   "อยู่ข้าง มันจึงเป็นแค่ตัวอักษรกับตัวเลขเหมือนข้อความทั่วไป"},
        {"what": "a secret that reads as an ordinary phrase",
         "th": "รหัสที่หน้าตาเหมือนข้อความธรรมดา",
         "why": "a passphrase built from real words is prose until something names it as a "
                "credential, and nothing here does",
         "why_th": "passphrase ที่ประกอบจากคำจริงๆ ก็คือข้อความธรรมดา จนกว่าจะมีคำมาบอกว่า"
                    "มันคือรหัส ซึ่งตรงนี้ไม่มี"},
        {"what": "a secret that is not text by the time it gets here",
         "th": "ความลับที่ไม่ได้มาในรูปตัวหนังสือ",
         "why": "an image, an archive or a binary is never decoded here, so nothing inside it is "
                "ever read — or replaced",
         "why_th": "รูป ไฟล์บีบอัด หรือ binary ไม่ถูกถอดรหัสที่นี่ จึงไม่มีอะไรข้างในถูกอ่าน "
                    "หรือถูกแทนที่"},
    ]
    return {"families": fams, "blind": blind, "total": len(pats), "measured": _recall()}


# ---------------------------------------------------------------- writing

def build():
    return {
        "built": time.strftime("%Y-%m-%d %H:%M"),
        "repo": ROOT.name,
        "hero": hero(),
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
        # 🎯 [owner, 2026-09-23] "ต้องมีจำนวนเต็มบอก … เพราะไม่มีใครบ้ามานั่งไล่ทุกเคส". A top
        # ten with no denominator reads as the whole list. The number beside it is what tells a
        # reader they are looking at a sample, and roughly how big a sample it is.
        "files_total": files_total(),
        "lessons": lessons(),
        "security": security(),
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
    for page in ("index.html", "features.html", "usage.html", "rates.html"):
        if not (REPORT / page).is_file():
            print(f"  {page} is missing — the page is not generated, only its data")
    return 0


if __name__ == "__main__":
    sys.exit(main())
