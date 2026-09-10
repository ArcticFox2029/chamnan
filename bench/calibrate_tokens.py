#!/usr/bin/env python3
"""Measure the real characters-per-token ratio, per script, with no API key.

chamnan reports its savings in tokens, and every one of those figures rests on a
single constant. That constant was a guess. This measures it instead.

The trick is that a headless run reports exactly how many tokens its prompt cost.
Send a fixed instruction, then send the same instruction with a sample appended,
and the difference is the sample's true token count as counted by Anthropic --
not by a stand-in tokenizer that would disagree most on exactly the non-Latin
scripts this corpus is full of.
"""
import json
import subprocess
from datetime import datetime
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NO_PLUGIN = HERE / "_no_plugin_settings.json"
OUT = HERE / "calibration.json"

# Kept short and identical across runs so the delta is the sample and nothing else.
INSTRUCTION = "Reply with exactly the word OK. Ignore everything after this line.\n"


def measure(prompt, cwd):
    proc = subprocess.run(
        ["claude", "-p", prompt, "--output-format", "json",
         "--settings", str(NO_PLUGIN), "--permission-mode", "bypassPermissions",
         "--disallowedTools", "Write,Edit,NotebookEdit,Read,Grep,Glob,Bash"],
        cwd=str(cwd), capture_output=True, text=True, timeout=300,
    )
    env = json.loads(proc.stdout)
    u = env["usage"]
    return (u.get("input_tokens", 0)
            + u.get("cache_creation_input_tokens", 0)
            + u.get("cache_read_input_tokens", 0))


SAMPLES = {
    "english_prose": "The dispatcher assigns each container to the nearest available vehicle, "
                     "then writes the assignment back to the fleet service so the driver app "
                     "can pick it up on its next poll. Retries are bounded and idempotent. " * 6,
    "english_code": "def assign_container(container_id, fleet):\n"
                    "    candidates = fleet.available_near(container_id)\n"
                    "    if not candidates:\n"
                    "        raise NoVehicleAvailable(container_id)\n"
                    "    chosen = min(candidates, key=lambda v: v.eta_minutes)\n"
                    "    return fleet.assign(container_id, chosen.vehicle_id)\n" * 6,
    "thai": "ตัวจัดคิวจะเลือกรถที่ว่างและอยู่ใกล้ตู้สินค้ามากที่สุด "
            "แล้วบันทึกการมอบหมายกลับไปยังบริการจัดการขบวนรถ "
            "เพื่อให้แอปของคนขับดึงงานไปทำในรอบถัดไป " * 6,
    "japanese": "ディスパッチャは各コンテナを最も近い利用可能な車両に割り当て、"
                "その割り当てをフリートサービスに書き戻します。"
                "ドライバーアプリは次のポーリングでそれを取得します。" * 6,
    "chinese": "调度程序将每个集装箱分配给最近的可用车辆，"
               "然后将分配结果写回车队服务，"
               "以便司机应用在下一次轮询时获取。" * 6,
    "russian": "Диспетчер назначает каждый контейнер ближайшему доступному транспортному "
               "средству, затем записывает назначение обратно в службу автопарка, "
               "чтобы приложение водителя получило его при следующем опросе. " * 6,
    "german": "Der Disponent weist jeden Container dem nächstgelegenen verfügbaren Fahrzeug "
              "zu und schreibt die Zuweisung anschließend an den Flottendienst zurück, "
              "damit die Fahrer-App sie beim nächsten Abruf übernehmen kann. " * 6,
}

# 🐛 [2026-09-10] `lib/tokens.py`'s docstring is the published justification for its per-script
# divisors and it quotes a six-row table — MAP.md's Quick Index and its Full Detail section, a real
# STATE.md, this repository's own Python, JSON, URLs — measured "on the content chamnan actually
# budgets". Not one of those six was in `SAMPLES`, which held seven language rows and nothing else.
# So whoever produced that table did it with something that left no trace in the one file built to
# make such a measurement re-runnable, and the next person to retune those divisors — which the
# docstring says has already happened once — had no way to check they had not regressed the exact
# artefact the module says matters most (R1 agent 5, finding 6).
#
# Read from disk at run time rather than pasted in. Two reasons, and the second is the harder rule:
# a pasted sample is this repository's content frozen into a package that ships to other people's
# repositories, and it stops being the thing it claims to measure the moment MAP.md changes. Read
# live, the script measures the artefacts of WHOEVER runs it, which is what the docstring's phrase
# actually means.
#
# A missing artefact is skipped rather than faked. A row measured against a stand-in is worse than
# an absent row: it prints a number under a name that says "your MAP.md".
ARTEFACTS = {
    # Both halves of the index, because the docstring quotes them separately and they are different
    # shapes: the Quick Index is dense one-line-per-file, the Full Detail is prose and signatures.
    "map_quick_index": (".chamnan/MAP.md", "## Quick Index", "## Full Detail"),
    "map_full_detail": (".chamnan/MAP.md", "## Full Detail", None),
    "state_md": (".chamnan/STATE.md", None, None),
    "json_blob": (".chamnan/tools/index.json", None, None),
}

# 12 KB is enough for a stable characters-per-token ratio and small enough that a full run does not
# turn into real money: this script calls the live `claude` CLI once per sample.
ARTEFACT_CAP = 12_000


def artefact_samples(root):
    """The real-artefact rows, read from `root`. Absent files are skipped, never substituted."""
    out = {}
    for name, (rel, start, stop) in ARTEFACTS.items():
        try:
            text = (Path(root) / rel).read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        if start:
            i = text.find(start)
            if i < 0:
                continue
            text = text[i:]
        if stop:
            j = text.find(stop, len(start or ""))
            if j > 0:
                text = text[:j]
        text = text.strip()
        if len(text) >= 500:              # below this the per-call overhead swamps the measurement
            out[name] = text[:ARTEFACT_CAP]
    # URLs are the one row with no artefact to read: nothing chamnan writes is URL-dense, and the
    # docstring's row is about what a URL costs, not about a file. Built, and said to be built.
    out["urls_synthetic"] = ("See https://github.com/ArcticFox2029/chamnan/blob/main/lib/tokens.py "
                             "and https://docs.example.com/v2/reference/pagination#cursor-based "
                             "for the details. ") * 12
    return out


def claude_version():
    """The `claude` build these numbers were taken under, or "" — part of the provenance."""
    try:
        out = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=30)
        return out.stdout.strip().split()[0] if out.stdout.strip() else ""
    except (OSError, subprocess.SubprocessError, IndexError):
        return ""


def main():
    """Measure every sample, or explain why the file on disk cannot be extended.

    🐛 Two things made this un-re-runnable, and the second was a footgun rather than an
    inconvenience.

    Every measurement was guarded by `if name not in results`, so once calibration.json existed the
    script measured NOTHING on a second run. "Re-running the calibration" was a no-op, which is why
    a file recorded months ago still described the run that made it and nothing since.

    Worse: the numbers stored are ABSOLUTE token counts, and what the suite uses is the DIFFERENCE
    `sample - _base`. That difference is only meaningful when both were measured in the same
    sitting. `_base` is the cost of a fixed instruction under one Claude Code build, and it moves
    when the build does — measured 34,673 when this file was written and 14,941 today. So adding
    ONE new sample to an existing file subtracted today's measurement from a stale baseline: a
    sample truly costing 500 tokens would be recorded as -19,232, and a smaller drift would record
    a plausible wrong ratio in silence.

    So a measurement run is now all-or-nothing and stamped with when and under what it ran. A file
    whose provenance does not match this machine is not extended; it is re-measured whole, or the
    script says why it will not touch it.
    """
    remeasure = "--remeasure" in sys.argv[1:]
    NO_PLUGIN.write_text(json.dumps({"enabledPlugins": {"chamnan@chamnan": False}}))
    empty = HERE / "_empty"
    empty.mkdir(exist_ok=True)

    results = json.loads(OUT.read_text()) if OUT.exists() else {}
    stamp = results.get("_measured") or {}
    here_version = claude_version()

    complete = "_base" in results and all(n in results for n in SAMPLES)
    if complete and not remeasure:
        print(f"calibration.json is complete, measured {stamp.get('at', 'at an unrecorded time')}"
              + (f" under claude {stamp['claude_version']}" if stamp.get("claude_version") else "")
              + ".\nNothing was measured. Re-run with --remeasure to take the numbers again.\n")
        _report(results, results["_base"])
        return 0
    if results and not remeasure:
        # Incomplete AND already carrying measurements: extending it would subtract a baseline from
        # one sitting off a sample from another, which is the defect described above.
        print("calibration.json is incomplete, and the numbers in it were taken under "
              + (f"claude {stamp['claude_version']} on {stamp.get('at', 'an unrecorded date')}"
                 if stamp.get("claude_version") else "an unrecorded build")
              + f", not the {here_version or 'unknown'} on this machine.\n"
                "A baseline and a sample are only comparable within one sitting, so this will not "
                "add to it.\nRe-run with --remeasure to take every number again.", file=sys.stderr)
        return 1

    # The language rows are literal and travel with the package; the artefact rows are read from
    # whatever repository this is being run in, so the table means "the content chamnan budgets
    # HERE" rather than "the content it budgeted in the repo where this was written".
    import workspace as _ws
    _root = _ws.find_root()
    samples = dict(SAMPLES)
    _live = artefact_samples(_root)
    samples.update(_live)
    if _live:
        print(f"artefacts read from {_root}: {', '.join(sorted(_live))}\n", flush=True)
    _absent = sorted(set(ARTEFACTS) - set(_live))
    if _absent:
        # Named, not silently dropped. A table missing a row is a different statement from a table
        # whose row was measured against a stand-in, and only one of them is honest.
        print(f"not present here, so not measured: {', '.join(_absent)}\n", flush=True)

    results = {}
    print("baseline...", flush=True)
    results["_base"] = measure(INSTRUCTION, empty)
    base = results["_base"]
    print(f"baseline prompt = {base:,} tokens\n")

    for name, text in samples.items():
        results[name] = measure(INSTRUCTION + text, empty)

    # Provenance, so a later reader can tell whether these numbers still describe anything —
    # and the derived ratios beside them, because the ratio is the durable quantity and the raw
    # counts are only meaningful against the baseline they were taken with.
    results["_measured"] = {
        "at": datetime.now().astimezone().strftime("%Y-%m-%d"),
        "claude_version": here_version,
        "note": "raw token counts; subtract _base, and only within this one measurement run",
    }
    results["_ratios"] = {
        name: round(len(text) / (results[name] - base), 2)
        for name, text in samples.items() if results[name] - base > 0
    }
    OUT.write_text(json.dumps(results, indent=2))
    _report(results, base, samples)
    print(f"\nwrote {OUT}")
    return 0


def _report(results, base, samples=None):
    print(f"{'sample':<16}{'chars':>8}{'tokens':>9}{'chars/token':>13}")
    print("-" * 46)
    for name, text in (samples if samples is not None else SAMPLES).items():
        tokens = results.get(name, 0) - base
        chars = len(text)
        if tokens <= 0:
            print(f"{name:<16}{chars:>8,}{'  unusable (cache noise)':>22}")
            continue
        print(f"{name:<16}{chars:>8,}{tokens:>9,}{chars/tokens:>13.2f}")


if __name__ == "__main__":
    sys.exit(main())
