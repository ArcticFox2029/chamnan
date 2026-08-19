#!/usr/bin/env python3
"""Measure what chamnan actually costs and saves, by running the real CLI.

Every number this prints comes from Claude Code's own usage accounting for a real
headless run -- not from a tokenizer approximation. Each question is asked twice
against the same corpus: once with no plugin at all (the model must search for
itself) and once with the local chamnan checkout loaded. The difference between
those two runs is the claim.

Results are appended to results.json and already-completed cells are skipped, so
an interrupted run can simply be started again.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
RESULTS = HERE / "results.json"

# Both arms disable the chamnan release that is installed user-wide, so the only
# difference between them is whether THIS checkout gets loaded. --bare would have
# been the obvious way to strip the plugin, but it also skips the keychain read
# and the run comes back "Not logged in"; a settings override leaves hooks, LSP
# and auth identical and removes nothing but the plugin.
NO_PLUGIN = HERE / "_no_plugin_settings.json"

ARMS = {
    "bare": ["--settings", str(NO_PLUGIN)],
    "chamnan": ["--settings", str(NO_PLUGIN), "--plugin-dir", str(PLUGIN)],
}

# Asked in an empty directory to establish what a run costs before any of the
# work starts, so the per-question figures can be reported net of it.
BASELINE_PROMPT = "Reply with exactly the word OK and nothing else."


def load_results():
    if RESULTS.exists():
        return json.loads(RESULTS.read_text())
    return {"baseline": {}, "runs": {}}


def save_results(data):
    RESULTS.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def run_once(prompt, cwd, arm_flags, timeout=900):
    """One headless invocation. Returns the parsed result envelope or an error."""
    cmd = [
        "claude", "-p", prompt,
        "--output-format", "json",
        "--permission-mode", "bypassPermissions",
        "--disallowedTools", "Write,Edit,NotebookEdit",
        *arm_flags,
    ]
    started = time.time()
    try:
        proc = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "wall_s": timeout}
    if proc.returncode != 0:
        return {"error": f"exit {proc.returncode}", "stderr": proc.stderr[-2000:]}
    try:
        env = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"error": "unparseable stdout", "stdout": proc.stdout[-2000:]}
    env["wall_s"] = round(time.time() - started, 1)
    return env


def slim(env):
    """Keep only what the report needs; the raw envelope is large and noisy."""
    if "error" in env:
        return env
    u = env.get("usage", {})
    return {
        "input_tokens": u.get("input_tokens", 0),
        "cache_creation": u.get("cache_creation_input_tokens", 0),
        "cache_read": u.get("cache_read_input_tokens", 0),
        "output_tokens": u.get("output_tokens", 0),
        "context_total": (
            u.get("input_tokens", 0)
            + u.get("cache_creation_input_tokens", 0)
            + u.get("cache_read_input_tokens", 0)
        ),
        "cost_usd": env.get("total_cost_usd", 0.0),
        "num_turns": env.get("num_turns", 0),
        "wall_s": env.get("wall_s"),
        "answer": env.get("result", ""),
    }


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: run_bench.py <corpus-dir> [question-id ...]")
    corpus = Path(sys.argv[1]).resolve()
    if not corpus.is_dir():
        sys.exit(f"no such directory: {corpus}")
    only = set(sys.argv[2:])

    questions = json.loads((HERE / "questions.json").read_text())["questions"]
    if only:
        questions = [q for q in questions if q["id"] in only]

    data = load_results()
    data.setdefault("corpus", str(corpus))

    NO_PLUGIN.write_text(json.dumps({"enabledPlugins": {"chamnan@chamnan": False}}))

    empty = HERE / "_empty"
    empty.mkdir(exist_ok=True)

    for arm, flags in ARMS.items():
        if arm in data["baseline"]:
            print(f"baseline/{arm}: cached")
            continue
        print(f"baseline/{arm}: running...", flush=True)
        data["baseline"][arm] = slim(run_once(BASELINE_PROMPT, empty, flags, timeout=180))
        save_results(data)
        b = data["baseline"][arm]
        print(f"  context={b.get('context_total')} cost=${b.get('cost_usd', 0):.4f}")

    for q in questions:
        for arm, flags in ARMS.items():
            key = f"{q['id']}::{arm}"
            if key in data["runs"] and "error" not in data["runs"][key]:
                print(f"{key}: cached")
                continue
            print(f"{key}: running...", flush=True)
            data["runs"][key] = slim(run_once(q["q"], corpus, flags))
            data["runs"][key]["dimension"] = q["dimension"]
            save_results(data)
            r = data["runs"][key]
            if "error" in r:
                print(f"  ERROR {r['error']}")
            else:
                print(
                    f"  context={r['context_total']:>8}  turns={r['num_turns']:>2}"
                    f"  {r['wall_s']:>6}s  ${r['cost_usd']:.4f}"
                )

    print(f"\nwrote {RESULTS}")


if __name__ == "__main__":
    main()
