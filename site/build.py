#!/usr/bin/env python3
"""Copy the modules the site needs out of lib/, and write the manifest it fetches.

The site runs chamnan's REAL modules through Pyodide rather than a JavaScript re-implementation,
so the numbers it reports are the tool's own. That only stays true if this copy is regenerated
when lib/ changes, which is why the set is DERIVED from the import graph rather than listed: a
module added to mapper's dependencies next year is picked up here without anyone remembering.

    python3 site/build.py        # from the repository root
"""
import ast
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "lib"
OUT = Path(__file__).resolve().parent / "lib"

# What the three demos on the page actually call.
SEEDS = {"mapper", "rollup", "workspace", "redact"}


def import_graph():
    local = {p.stem for p in LIB.glob("*.py")}
    graph = {}
    for p in LIB.glob("*.py"):
        edges = set()
        for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                     else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            for name in names:
                top = name.split(".")[0]
                if top in local:
                    edges.add(top)
        graph[p.stem] = edges
    return graph


def closure(graph, seeds):
    seen, stack = set(), list(seeds)
    while stack:
        mod = stack.pop()
        if mod in seen:
            continue
        seen.add(mod)
        stack.extend(graph.get(mod, ()))
    return seen


def main():
    graph = import_graph()
    needed = sorted(closure(graph, SEEDS))
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    total = 0
    for mod in needed:
        src = LIB / f"{mod}.py"
        shutil.copy2(src, OUT / f"{mod}.py")
        total += src.stat().st_size
    # The version travels with the bundle. A number on the page is the only way a visitor can tell
    # WHICH chamnan produced what they are looking at, and the only way a stale copy of the page
    # announces itself instead of quietly reporting a year-old build's behaviour.
    version = "unknown"
    try:
        version = json.loads(
            (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError):
        pass
    (OUT / "manifest.json").write_text(
        json.dumps({"version": version, "modules": [f"{m}.py" for m in needed]}, indent=2) + "\n",
        encoding="utf-8")
    print(f"site/lib: chamnan {version}, {len(needed)} modules, {total:,} bytes")
    for mod in needed:
        print(f"  {mod}.py")


if __name__ == "__main__":
    main()
