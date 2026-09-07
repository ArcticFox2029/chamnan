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

    results = {}
    print("baseline...", flush=True)
    results["_base"] = measure(INSTRUCTION, empty)
    base = results["_base"]
    print(f"baseline prompt = {base:,} tokens\n")

    for name, text in SAMPLES.items():
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
        for name, text in SAMPLES.items() if results[name] - base > 0
    }
    OUT.write_text(json.dumps(results, indent=2))
    _report(results, base)
    print(f"\nwrote {OUT}")
    return 0


def _report(results, base):
    print(f"{'sample':<16}{'chars':>8}{'tokens':>9}{'chars/token':>13}")
    print("-" * 46)
    for name, text in SAMPLES.items():
        tokens = results.get(name, 0) - base
        chars = len(text)
        if tokens <= 0:
            print(f"{name:<16}{chars:>8,}{'  unusable (cache noise)':>22}")
            continue
        print(f"{name:<16}{chars:>8,}{tokens:>9,}{chars/tokens:>13.2f}")


if __name__ == "__main__":
    sys.exit(main())
