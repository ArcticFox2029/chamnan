#!/usr/bin/env python3
"""Generate `llms.txt` — the machine-readable index AI search reads instead of the whole README.

`llms.txt` is the convention for handing a language model a short, structured description of a
project rather than making it parse a rendering meant for people. chamnan's README is well over a
hundred thousand characters; an assistant asked "does chamnan work with Windsurf" should not have to
read it, and in practice will read the first few thousand characters and answer from those.

GitHub Pages serves this repository from `main` at the root, so the file written here is live at
`/llms.txt` on the site as well as in the repository.

**Generated, not written.** The adapter list, the command list and the translated-page list are read
from the code and the tree, so the file cannot drift from what ships the way a hand-written summary
would. `test_llms_txt_is_current.py` fails if it is stale.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lib"))

SITE = "https://arcticfox2029.github.io/chamnan"
REPO = "https://github.com/ArcticFox2029/chamnan"


def _adapters():
    import adapters
    rows = []
    for name in sorted(adapters.ADAPTERS):
        mod = adapters.ADAPTERS[name]
        rows.append((name, getattr(mod, "TARGET", "")))
    return rows


def _models():
    import profiles
    return sorted(profiles.MODEL_WINDOWS), sorted(profiles.AMBIGUOUS)


def _commands():
    out = []
    for p in sorted((ROOT / "bin").iterdir()):
        if p.is_file() and not p.suffix:
            first = ""
            try:
                for line in p.read_text(encoding="utf-8", errors="replace").splitlines()[:6]:
                    m = re.match(r'^"""(\S+)\s*[—-]\s*(.+?)\.?$', line.strip())
                    if m:
                        first = m.group(2).rstrip(".")
                        break
            except OSError:
                pass
            out.append((p.name, first))
    return out


def _languages():
    d = ROOT / "docs" / "i18n"
    return sorted(p.name[len("README."):-len(".md")] for p in d.glob("README.*.md"))


def build():
    known, ambiguous = _models()
    adapters = _adapters()
    langs = _languages()
    cmds = _commands()
    L = [
        "# chamnan",
        "",
        "> A context index for coding agents. It reads a repository once, writes one line per file "
        "plus sections for the data model, API surface, configuration and deployment, and hands "
        "that to an agent at the start of every session — so the agent stops rediscovering the "
        "shape of the codebase and starts from it. Pure Python standard library, no dependencies, "
        "MIT licence.",
        "",
        "chamnan is delivered as a Claude Code plugin and as a plain command-line tool. The index "
        "itself is text and belongs to no vendor: the same file is written for every other agent "
        "that reads project instructions, and the model in use only decides how much of it is "
        "worth sending.",
        "",
        "## Installing",
        "",
        f"- [Quick start]({SITE}#quick-start): install as a Claude Code plugin, then `/chamnan:bootstrap` once.",
        f"- [Installing it, per tool]({SITE}#installing-it-per-tool): the three routes in — a plugin, a session hook, or a file.",
        f"- [Requirements]({SITE}#requirements): Python and nothing else. No packages, no virtualenv.",
        "",
        "## What it works with",
        "",
        f"- **Operating systems**: macOS, Linux, Windows and WSL, all exercised in CI on every commit. "
        f"See [Running it on each operating system]({SITE}#running-it-on-each-operating-system).",
        f"- **Models**: any. `--model` recognises {', '.join('`' + m + '`' for m in known)} by name; "
        f"{' and '.join('`' + a + '`' for a in ambiguous)} ship in several sizes and are deliberately "
        f"left out; anything unrecognised still works and `--window` takes an exact number.",
        f"- **Agents**: {len(adapters)} adapters. Claude Code and Gemini CLI receive a real session "
        f"hook; every other agent receives a file at the path it reads.",
        f"- **Hermes Agent**: writes `.hermes.md`, the project-instruction file Hermes gives highest "
        f"priority. See [Using it with Hermes Agent]({SITE}#using-it-with-hermes-agent).",
        "",
        "### Agents and the file each one receives",
        "",
    ]
    L += [f"- `{n}`: `{t}`" for n, t in adapters if t]
    L += [
        "",
        "## Commands",
        "",
    ]
    L += [f"- `{n}`: {d}" for n, d in cmds if d]
    L += [
        "",
        "## Documentation",
        "",
        f"- [README]({SITE}): everything, including every measurement and its method.",
        f"- [Repository]({REPO}): source, releases and issues.",
        f"- [Changelog]({REPO}/blob/main/CHANGELOG.md): what changed in each release.",
        f"- [Architecture]({REPO}/blob/main/docs/architecture.md) · "
        f"[Data flow]({REPO}/blob/main/docs/data-flow.md) · "
        f"[Verification]({REPO}/blob/main/docs/verification.md)",
        "",
        "## Other languages",
        "",
        f"Translated pages cover what chamnan is, what it works with and how to install it, in "
        f"{len(langs)} languages. They carry no figures by design — every measurement lives in the "
        f"English README, which is the only page rewritten each release.",
        "",
    ]
    L += [f"- [{c}]({REPO}/blob/main/docs/i18n/README.{c}.md)" for c in langs]
    L += [""]
    return "\n".join(L)


def main():
    text = build()
    out = ROOT / "llms.txt"
    if "--check" in sys.argv:
        current = out.read_text(encoding="utf-8") if out.is_file() else ""
        if current == text:
            print("llms.txt is current")
            return 0
        print("llms.txt is STALE — run tools/build_llms_txt.py", file=sys.stderr)
        return 1
    out.write_text(text, encoding="utf-8")
    print(f"llms.txt -> {len(text):,} characters")
    return 0


if __name__ == "__main__":
    sys.exit(main())
