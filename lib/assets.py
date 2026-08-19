"""An inventory of the material that is NOT source — and the reason it belongs in the index.

A platform of any size carries far more payload than code: scanned paperwork, proof-of-delivery
photos, exports, archives, model weights. None of it should ever be read to understand the system,
and chamnan does not read it. The temptation is therefore to say nothing about it at all.

That is the wrong call, and it costs more than it saves. An agent that is told nothing about a
directory does not conclude the directory is unimportant — it goes and looks. One `find` over a
large mount, a `ls` of a few levels, and two or three files opened to see what they are, costs far
more than the forty tokens it takes to say: attachments/nfs holds 12,400 files totalling 4.2 GB,
mostly PDF and PNG, and it is payload rather than source.

So this section exists to STOP exploration, not to enable it. It reports shape only — counts, total
size, the extensions that dominate — and never opens a file. Directories below a threshold are left
out entirely, because a handful of images beside a README is not a mount and saying so is noise.
"""
from collections import defaultdict

# Below this many non-source files a directory is not an asset store, it is a few loose files.
MIN_FILES = 12
MAX_DIRS_LISTED = 12
MAX_EXTS_SHOWN = 6
# Extensions that carry meaning a reader might want even though chamnan does not parse them. They
# are counted like any other asset but named first, because "this tree is 900 CSVs" is a different
# fact from "this tree is 900 PNGs".
NOTABLE = {".csv", ".json", ".xml", ".parquet", ".avro", ".sql", ".log", ".md"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "vendor", ".terraform", "dist"}


def _human(size):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024


def scan(root, source_paths, ext_lang):
    """source_paths: the set mapper already indexed, so nothing is counted twice."""
    groups = defaultdict(lambda: {"count": 0, "bytes": 0, "exts": defaultdict(int)})
    for path in root.rglob("*"):
        try:
            if not path.is_file() or path.is_symlink():
                continue
            rel = path.relative_to(root)
        except (OSError, ValueError):
            continue
        if any(p in SKIP_DIRS or p.startswith(".") for p in rel.parts[:-1]):
            continue
        if str(rel) in source_paths or path.suffix.lower() in ext_lang:
            continue
        top = rel.parts[0] if len(rel.parts) > 1 else "(root)"
        try:
            size = path.stat().st_size
        except OSError:
            continue
        g = groups[top]
        g["count"] += 1
        g["bytes"] += size
        g["exts"][path.suffix.lower() or "(none)"] += 1
    return {k: v for k, v in groups.items() if v["count"] >= MIN_FILES}


def render(groups):
    if not groups:
        return ""
    ranked = sorted(groups.items(), key=lambda kv: -kv[1]["bytes"])
    total_n = sum(g["count"] for _, g in ranked)
    total_b = sum(g["bytes"] for _, g in ranked)
    out = ["## Stored material (not source)", "",
           f"{total_n:,} files, {_human(total_b)}. **Payload, not code — do not read these to "
           f"understand the system.** Listed so that their shape is known without anyone going "
           f"looking, which costs more than this section does.", ""]
    for name, g in ranked[:MAX_DIRS_LISTED]:
        exts = sorted(g["exts"].items(), key=lambda kv: -kv[1])[:MAX_EXTS_SHOWN]
        notable = [e for e, _ in exts if e in NOTABLE]
        shown = ", ".join(f"{e} ×{n:,}" for e, n in exts)
        tail = "  _(machine-readable: " + ", ".join(notable) + ")_" if notable else ""
        out.append(f"- **`{name}/`** — {g['count']:,} files, {_human(g['bytes'])} — {shown}{tail}")
    if len(ranked) > MAX_DIRS_LISTED:
        out.append(f"- _…and {len(ranked)-MAX_DIRS_LISTED} more directories_")
    out.append("")
    return "\n".join(out)
