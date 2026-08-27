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
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
import ledger  # noqa: E402
import memory  # noqa: E402
import milestones  # noqa: E402
import redact  # noqa: E402
import rollup  # noqa: E402
import sessions  # noqa: E402
import state  # noqa: E402
import timeline  # noqa: E402
import tokens  # noqa: E402
import workspace as ws  # noqa: E402

# Injected only when .chamnan/config.json asks for it. Off by default: changing how a session
# answers is the user's call, not a side effect of installing an indexing tool.
REPLY_STYLES = {'concise': 'Answer without preamble, without restating the question, and without a closing offer of further help. Lead with the result, then the reasoning only where it changes what the reader would do. Keep full sentences and normal courtesy — this is about removing filler, not about sounding curt.', 'terse': 'Lead with the result. Drop preamble, restatement and closing offers. Prefer a table or a list wherever one carries the content, and sentence fragments where a full sentence adds nothing. Never pad to seem thorough. Say uncertain things once, plainly, and move on.'}
MAX_TOOLS = 12

# The plugin's own write skills, in the order they should be named. `note` is the description
# fragment used only when the skill is present -- kept here rather than read from each SKILL.md so
# the sentence stays a single planned read, not five. Checked against skills/ at runtime (see
# write_skills_line) so a skill that is removed silently stops being named, rather than the line
# going stale.
WRITE_SKILLS = (
    ("resume", "session record"),
    ("remember", "decision, lesson, or rule"),
    ("milestone", None),
    ("capture", "a procedure worth keeping"),
)


def write_skills_line(plugin_root):
    """Name the plugin's own write skills. Nothing else in this hook has ever done this --
    the "Recorded procedures" section below injects the WORKSPACE's own captured skills
    (.chamnan/skills/), never the plugin's, so an agent working in a chamnan repository has had no
    way to discover that /chamnan:remember exists short of reading the plugin's source.

    This is the leading candidate for the finding that decided this whole release: hook-written
    logs held 700 records on the workspace this was measured against, and every skill-written store
    held zero. An agent that does not know it can write is the failure being fixed here, so this
    line is gated on nothing except the skill actually shipping.
    """
    skills_dir = plugin_root / "skills"
    if not skills_dir.is_dir():
        return ""
    parts = []
    for name, note in WRITE_SKILLS:
        if not (skills_dir / name / "SKILL.md").is_file():
            continue
        parts.append(f"`/chamnan:{name}`" + (f" ({note})" if note else ""))
    if not parts:
        return ""
    if len(parts) == 1:
        named = parts[0]
    else:
        named = ", ".join(parts[:-1]) + f", or {parts[-1]}"
    return f"_Write with {named}. Nothing writes here unless you ask._"


_MD_MARKUP = re.compile(r"[*_`]")
_LEADING_MARKUP = re.compile(r"^[>*\-\s]+")


def describe(path):
    """The `description:` line from a skill's frontmatter, which is what makes the registry usable.

    🐛 [2026-08-27] Every skill in the live workspace this hook runs against predates the plugin's
    own frontmatter convention -- none of the twelve had one, so every registry line read "no
    description — add one": 893 characters buying nothing. Falls back to the first real line of
    body text past the title, lightly cleaned of markdown, rather than staying empty just because
    the file was never migrated to `---\\ndescription: ...\\n---`.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    head = text[:1200]
    if head.startswith("---"):
        end = head.find("\n---", 3)
        for line in head[3:end if end > 0 else len(head)].splitlines():
            if line.strip().lower().startswith("description:"):
                return " ".join(line.split(":", 1)[1].split())[:110]
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        cleaned = _MD_MARKUP.sub("", _LEADING_MARKUP.sub("", stripped, count=1))
        if cleaned:
            return " ".join(cleaned.split())[:110]
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

    if cfg.get("ledger", True):
        # Always the first thing in the injection, and gated on nothing but the flag itself --
        # the whole point is that this is visible whether or not there is anything to report.
        skills_line = write_skills_line(HERE.parent)
        if skills_line:
            out.append(skills_line + "\n")
        out.append(ledger.line(root) + "\n")

    if cfg.get("map", True):
        mp = wsdir / "MAP.md"
        if mp.is_file():
            text = mp.read_text(encoding="utf-8", errors="replace")
            cut = text.find("## Full Detail")
            index = text[:cut] if cut > 0 else text
            budget = cfg.get("index_token_budget", 3000)
            if not tokens.fits(index, budget):
                index = rollup.collapse(index, mp.relative_to(root), budget)
            out.append(section("Architecture index", index))
            out.append(f"_Full detail lives in `{mp.relative_to(root)}` — grep it for one heading, "
                       f"never read it whole._\n")

    if cfg.get("memory", True):
        # Rules are standing constraints, so they go in front of the agent before it starts.
        rules = redact.scrub(memory.rules_text(root))
        if rules:
            out.append(section("Rules this repository works under", rules))
        # Decisions and lessons are looked up when the question comes round, so they contribute a
        # title and nothing else — the same economy skills/ and tools/ use.
        listing = memory.render_titles(memory.titles(root))
        if listing:
            out.append(section(
                "Recorded decisions and lessons — read the one that matches before assuming",
                listing + "\n\n_Read a file from `.chamnan/memory/` when its title is relevant; "
                          "do not read them all._"))

    if cfg.get("milestones", True):
        # Titles only, newest first. "The last big thing here was the auth migration" orients a
        # session in about twenty tokens; the bodies are a grep away when a title looks relevant.
        recent = redact.scrub(milestones.recent_titles(root))
        if recent:
            out.append(section("Recent milestones", recent))

    if cfg.get("timeline", True):
        # OPEN threads only, titles only. A closed thread is history -- still readable, still
        # answering `chamnan-timeline for <path>`, but no longer something to hold in mind before
        # starting. "We have tried to fix this three times" is the line nobody can reconstruct
        # from a git log, and it costs about as much to say as a milestone title.
        open_threads = redact.scrub(timeline.open_titles(root))
        if open_threads:
            out.append(section(
                "Open threads — lines of work still in flight",
                open_threads + "\n\n_`chamnan-timeline show <name>` for one thread's history; "
                               "`chamnan-timeline for <path>` for what has happened to one file._"))

    if cfg.get("resume", True):
        # Only the newest record, and only the part of it that is unfinished. "Done" is history and
        # the file list is recoverable from git; what the next session cannot work out for itself is
        # what was left and what was in the way. Empty when the last session finished cleanly, which
        # is the right outcome — nothing is injected to say "nothing outstanding".
        carried = redact.scrub(sessions.carry_forward(root))
        if carried:
            out.append(section("Where the last session stopped", carried))

    if cfg.get("state", True):
        sp = wsdir / "STATE.md"
        if sp.is_file():
            # Scrubbed on the way in, BEFORE the token cut -- STATE.md and the session records are
            # free text written about the repository, which makes them the likeliest place for a
            # hostname or a pasted connection string to end up, and scrubbing after truncation
            # would miss anything sensitive that fell inside a pinned section.
            full = redact.scrub(sp.read_text(encoding="utf-8", errors="replace"))
            budget = cfg.get("state_token_budget", 1700)
            st, marker = state.render(full, budget, sp.relative_to(root))
            if st:
                out.append(section("Work in flight (from the last session)", st))
                out.append(f"_Keep `{sp.relative_to(root)}` current as you go; it is what survives "
                           f"compaction._\n")
                if marker:
                    out.append(marker + "\n")

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
