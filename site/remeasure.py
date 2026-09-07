"""Re-measure the demo page's sample table without a browser.

The page (site/index.html) lists a repository's blobs, keeps the tracked extensions, drops
anything over 2 MB using the size the listing already carries, takes the first 400 IN THE ORDER
THE LISTING GAVE THEM, fetches them, and runs mapper.render + rollup.collapse over the result.

The order is the part that cannot be guessed. jsDelivr's flat listing and git's own tree walk
disagree about it, and where the 400-file cap binds, a different order is a different 400 files
and a different answer -- facebook/react measured 4,792 KB from a clone's order against 257 KB
from the page's. So this asks jsDelivr for the same listing the page asks for, falls back to the
same GitHub tree API on the same 403, and reads the file contents out of a shallow clone rather
than over the network.

Usage: python3 remeasure.py <owner/repo> [...]
"""
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "lib"))

import mapper            # noqa: E402
import rollup            # noqa: E402
import workspace as ws   # noqa: E402

CAP = 400
TOO_BIG = 2 * 1024 * 1024


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "chamnan-remeasure"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def listing(slug):
    """(path, size) pairs in the page's own order: jsDelivr first, GitHub's tree on a 403."""
    owner, repo = slug.split("/", 1)
    refused = False
    for ref in ("main", "master"):
        try:
            j = _get(f"https://data.jsdelivr.com/v1/packages/gh/{owner}/{repo}@{ref}"
                     "?structure=flat")
        except urllib.error.HTTPError as exc:
            if exc.code == 403:
                refused = True
            continue
        if j.get("files"):
            return "jsdelivr", [(f["name"].lstrip("/"), f.get("size") or 0) for f in j["files"]]
    if not refused:
        pass                      # fall through anyway: an empty listing is the same problem
    tree = _get(f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1")
    # A symlink is `type: blob` too, and its content is its target path. jsDelivr already
    # excludes them; this path is the only one that ever let them through.
    return "github", [(n["path"], n.get("size") or 0) for n in tree.get("tree", [])
                      if n.get("type") == "blob" and n.get("mode") != "120000"]


def measure(slug):
    work = pathlib.Path(tempfile.mkdtemp(prefix="remeasure-"))
    try:
        subprocess.run(["git", "clone", "--depth", "1", "-q",
                        f"https://github.com/{slug}.git", str(work / "r")], check=True)
        repo = work / "r"
        exts = {e.lower() for e in mapper.EXT_LANG}
        via, listed = listing(slug)
        want = [(p, s) for p, s in listed
                if "." in p.rsplit("/", 1)[-1] and ("." + p.rsplit(".", 1)[-1]).lower() in exts]
        take = [(p, s) for p, s in want if s <= TOO_BIG][:CAP]

        # Keep only the chosen files, so mapper.scan sees exactly what the page's MEMFS holds.
        keep = {p for p, _ in take}
        source_bytes = 0
        staged = work / "repo"
        for p in keep:
            src = repo / p
            if not src.is_file():
                continue
            dst = staged / p
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            source_bytes += dst.stat().st_size

        mapper.reset_skips()
        files = list(mapper.scan(staged))
        index = mapper.render(files, staged)
        budget = ws.DEFAULT_CONFIG.get("index_token_budget", 3000)
        try:
            injected = rollup.collapse(index, ".chamnan/MAP.md", budget, staged, 8)
        except Exception:
            injected = index
        inj = len(injected.encode("utf-8"))
        return {
            "repo": slug,
            "via": via,
            "files": len(take),
            "source_kb": round(source_bytes / 1024),
            "injected_b": inj,
            "ratio": round(source_bytes / inj) if inj else 0,
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    for slug in sys.argv[1:]:
        try:
            print(json.dumps(measure(slug)), flush=True)
        except Exception as exc:                      # one repo must not end the run
            print(json.dumps({"repo": slug, "error": str(exc)[:200]}), flush=True)
