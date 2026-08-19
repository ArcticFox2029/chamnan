#!/usr/bin/env python3
"""SessionStart hook — hand the new session the map index, the open state, and the repo's own tools.

This is the part that answers "Claude forgot everything again". Compaction is not an edge case: 259
compaction traces were found across 23 sessions on one machine. After it fires, whatever the agent
had worked out about this codebase is gone, and it goes back to grepping. Injecting the index and
the state file at session start means the rediscovery never has to happen — and it costs a bounded,
known number of tokens rather than an unbounded number of file reads.

Budgeted on purpose. A hook that dumps a large map into every session is the same mistake as a
bloated CLAUDE.md: it would spend on every turn what it saves on a few. The index is truncated to
MAX_INDEX_CHARS and the shortfall is reported, so the fix is obvious (split the repo, or accept a
partial index) rather than silent.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
import rollup  # noqa: E402
import workspace as ws  # noqa: E402

CHARS_PER_TOKEN = 3.6
MAX_STATE_CHARS = 4000
# Injected only when .chamnan/config.json asks for it. Off by default: changing how a session
# answers is the user's call, not a side effect of installing an indexing tool.
REPLY_STYLES = {'concise': 'Answer without preamble, without restating the question, and without a closing offer of further help. Lead with the result, then the reasoning only where it changes what the reader would do. Keep full sentences and normal courtesy — this is about removing filler, not about sounding curt.', 'terse': 'Lead with the result. Drop preamble, restatement and closing offers. Prefer a table or a list wherever one carries the content, and sentence fragments where a full sentence adds nothing. Never pad to seem thorough. Say uncertain things once, plainly, and move on.'}
MAX_TOOLS = 12


def describe(path):
    """The `description:` line from a skill's frontmatter, which is what makes the registry usable."""
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:1200]
    except OSError:
        return ""
    if not head.startswith("---"):
        return ""
    end = head.find("\n---", 3)
    for line in head[3:end if end > 0 else len(head)].splitlines():
        if line.strip().lower().startswith("description:"):
            return " ".join(line.split(":", 1)[1].split())[:110]
    return ""


def section(title, body):
    return f"\n### {title}\n{body.rstrip()}\n" if body.strip() else ""


def main():
    try:
        json.load(sys.stdin)          # hook payload; nothing needed from it yet
    except Exception:
        pass
    root = ws.find_root()
    wsdir = ws.workspace(root)
    if not wsdir.is_dir():
        return 0                      # not a chamnan repo; stay silent
    cfg = ws.load_config(root)
    out = []

    if cfg.get("map", True):
        mp = wsdir / "MAP.md"
        if mp.is_file():
            text = mp.read_text(encoding="utf-8", errors="replace")
            cut = text.find("## Full Detail")
            index = text[:cut] if cut > 0 else text
            budget_chars = int(cfg.get("index_token_budget", 3000) * CHARS_PER_TOKEN)
            if len(index) > budget_chars:
                index = rollup.collapse(index, mp.relative_to(root))
            out.append(section("Architecture index", index))
            out.append(f"_Full detail lives in `{mp.relative_to(root)}` — grep it for one heading, "
                       f"never read it whole._\n")

    if cfg.get("state", True):
        sp = wsdir / "STATE.md"
        if sp.is_file():
            st = sp.read_text(encoding="utf-8", errors="replace")[:MAX_STATE_CHARS].strip()
            if st:
                out.append(section("Work in flight (from the last session)", st))
                out.append(f"_Keep `{sp.relative_to(root)}` current as you go; it is what survives "
                           f"compaction._\n")

    if cfg.get("promote", True):
        try:
            tools = json.loads((wsdir / "tools" / "index.json").read_text(encoding="utf-8"))
        except Exception:
            tools = []
        if tools:
            lines = [f"- `{t['name']}` — {t.get('desc') or 'no description'}"
                     for t in tools[:MAX_TOOLS]]
            if len(tools) > MAX_TOOLS:
                lines.append(f"- _…and {len(tools)-MAX_TOOLS} more in "
                             f"`{(wsdir/'tools').relative_to(root)}/`_")
            out.append(section("This repo's own tools — prefer these over writing a new script",
                               "\n".join(lines)))

    if cfg.get("capture", True):
        skills = sorted((wsdir / "skills").glob("*.md")) if (wsdir / "skills").is_dir() else []
        if skills:
            # Name plus description, never name alone. The point of keeping the bodies out of the
            # session is that the agent loads one on demand — and it cannot decide which one to load
            # from a filename. A registry of bare filenames spends the injection and buys nothing.
            lines = []
            for s in skills[:MAX_TOOLS]:
                lines.append(f"- `{s.name}` — {describe(s) or 'no description — add one'}")
            if len(skills) > MAX_TOOLS:
                lines.append(f"- _…and {len(skills)-MAX_TOOLS} more_")
            out.append(section(
                "Recorded procedures — read the one that matches before starting that kind of task",
                "\n".join(lines) +
                f"\n\nFull text in `{(wsdir/'skills').relative_to(root)}/`. Load one when it applies; "
                f"do not read them all."))

    style = cfg.get("reply_style", "off")
    if style in REPLY_STYLES:
        out.append(section("Reply style for this repo", REPLY_STYLES[style] +
                           "\n\n_Set by `reply_style` in .chamnan/config.json; remove it to "
                           "restore the default voice._"))

    if not out:
        return 0
    print("## chamnan\n" + "".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
