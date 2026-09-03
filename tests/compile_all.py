#!/usr/bin/env python3
"""Compile every script in this plugin, including the ones with no extension.

🐛 `python -m compileall lib bin hooks` and a `.py`-only sweep both reported "everything compiles"
while `bin/chamnan-map` was broken -- a duplicated keyword argument, introduced by an automated
edit. Every chamnan command is an extensionless file with a shebang, so a tool that finds source
by suffix walks past all ten of them. That is not a hypothetical: it happened on 2026-09-03 and
the broken file was committed.

Reads and compiles rather than importing: importing runs module-level code, and several of these
files do real work at import time.

    python3 tests/compile_all.py [<dir> ...]      default: lib bin hooks tests install

Shipped with the plugin and run by CI, because the blind spot it covers is the plugin's own
commands — a checker that lives only in a maintainer's workspace protects one clone.
"""
import pathlib
import sys

SKIP_SUFFIXES = (".cmd", ".sh", ".json", ".md", ".txt", ".pyc")


def main(folders):
    bad = []
    seen = 0
    for folder in folders:
        base = pathlib.Path(folder)
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_dir() or "__pycache__" in str(path) or path.suffix in SKIP_SUFFIXES:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue          # a binary or unreadable file is not this tool's business
            seen += 1
            try:
                compile(text, str(path), "exec")
            except SyntaxError as exc:
                bad.append(f"  {path}:{exc.lineno}  {exc.msg}")
    for line in bad:
        print(line)
    print(f"{seen - len(bad)}/{seen} script(s) compile")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["lib", "bin", "hooks", "tests", "install"]))
