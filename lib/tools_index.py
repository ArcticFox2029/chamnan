"""`.chamnan/tools/index.json` — the registry `chamnan-promote` writes and session_start.py reads.

Extracted out of `bin/chamnan-promote` so a second writer (`chamnan-candidates promote`, which
installs a tool skeleton from a confirmed candidate rather than copying an existing script) reuses
the exact same read/append/format logic instead of a second, slightly different copy of it. Two
JSON-append implementations drifting apart is exactly the kind of bug this repo has been burned by
before with concurrent writers of a shared file — see `main_app_concurrent_file_writes.md` in the
repo this plugin is developed against, though that specific failure mode (two threads writing at
once) does not apply here, since both callers are short-lived CLI invocations, never long-running.

The schema is deliberately small: `name`, `desc`, `added` (ISO timestamp), `origin` (where the
content came from — a file path for a promoted script, `"candidate:<slug>"` for one generated from
a detected sequence), `runs` (a usage counter nothing in 1.5.0 increments yet — reserved for 1.5.2's
usage counts, so the field exists before anything writes it, matching Stage 4's `as-of` reasoning:
add the column, wire the writer later).
"""
import json


def path(root):
    from workspace import workspace
    return workspace(root) / "tools" / "index.json"


def load(root):
    try:
        return json.loads(path(root).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def register(root, entry):
    """Append one entry and write the index back. `entry` must have `name`; every other field is
    optional and defaults sensibly. Returns the full, updated list."""
    entries = load(root)
    entries.append({
        "name": entry["name"],
        "desc": entry.get("desc", ""),
        "added": entry.get("added", ""),
        "origin": entry.get("origin", ""),
        "runs": entry.get("runs", 0),
    })
    p = path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(entries, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return entries
