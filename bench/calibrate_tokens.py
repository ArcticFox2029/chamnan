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


def main():
    NO_PLUGIN.write_text(json.dumps({"enabledPlugins": {"chamnan@chamnan": False}}))
    empty = HERE / "_empty"
    empty.mkdir(exist_ok=True)

    results = json.loads(OUT.read_text()) if OUT.exists() else {}

    if "_base" not in results:
        print("baseline...", flush=True)
        results["_base"] = measure(INSTRUCTION, empty)
        OUT.write_text(json.dumps(results, indent=2))
    base = results["_base"]
    print(f"baseline prompt = {base:,} tokens\n")

    print(f"{'sample':<16}{'chars':>8}{'tokens':>9}{'chars/token':>13}")
    print("-" * 46)
    for name, text in SAMPLES.items():
        if name not in results:
            results[name] = measure(INSTRUCTION + text, empty)
            OUT.write_text(json.dumps(results, indent=2))
        tokens = results[name] - base
        chars = len(text)
        if tokens <= 0:
            print(f"{name:<16}{chars:>8,}{'  unusable (cache noise)':>22}")
            continue
        print(f"{name:<16}{chars:>8,}{tokens:>9,}{chars/tokens:>13.2f}")

    OUT.write_text(json.dumps(results, indent=2))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
