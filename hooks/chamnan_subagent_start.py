#!/usr/bin/env python3
"""SubagentStart hook — tell a subagent this repository has an index, before it starts grepping.

A subagent begins with none of what the session worked out. It gets a prompt and a repository, and
the first thing it does is rediscover the shape of the codebase the parent session already had
handed to it at SessionStart. This programme recorded that as unfixable -- dead-ends Angle 33,
"subagents and the context they never receive" -- because no event fired at the right moment.

That was wrong, and the correction is quoted rather than inferred. The hooks reference's master
decision-control table (`code.claude.com/docs/en/hooks.md`, line 1024) lists SessionStart,
SubagentStart and PostModelSwitch together as "Context only", and the SubagentStart section says
`additionalContext` is "String added to the subagent's context at the start of its conversation,
before its first prompt". The angle was closed by a documentation page nobody could read: WebFetch
truncates that page before the per-event sections, twice, and `curl` on the `.md` URL returns all
317,647 bytes in one go.

**This is a POINTER, not the session-start block, and the difference is the whole design.** One
session on this machine spawned fifteen subagents in an afternoon. Fifteen copies of a 9,000-byte
block is 135,000 bytes of context bought to save some greps, which is the bloated-CLAUDE.md mistake
with extra steps. What a subagent actually lacks is not the content -- it can read files -- it is
knowing that the content EXISTS and where. So this says where, in a few hundred bytes, and stops.

Two things are deliberately not here:

  * **No agent_type branching yet.** The matcher supports it and an `Explore` agent plausibly wants
    something an `audit-qa` agent does not. One shape, measured, before three shapes guessed at.
  * **No index content.** `.chamnan/MAP.md` is 320,000 characters in this repository. Naming it and
    saying how to grep it is the useful half; pasting any of it into every subagent is not.

Unlike SessionStart, a plain `print()` is NOT context here -- SubagentStart requires the explicit
`hookSpecificOutput.additionalContext` form. Available from Claude Code 2.0.43.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
import mdblock  # noqa: E402
import memory  # noqa: E402
import redact  # noqa: E402
import workspace as ws  # noqa: E402

# A hard cap, and small on purpose: this is paid once per subagent, and a session spawns many.
# Measured against the SessionStart block's own 9,000-byte ceiling, this is under 5% of it.
MAX_BYTES = 1_400


def _block(root):
    """The pointer, or "" when this repository has nothing worth pointing at."""
    parts = []
    map_path = root / ".chamnan" / "MAP.md"
    if map_path.is_file():
        try:
            size = map_path.stat().st_size
        except OSError:
            size = 0
        parts.append(
            f"This repository keeps an architecture index at `.chamnan/MAP.md` "
            f"({size:,} characters). **Grep it for one heading — never read it whole.** "
            "`## `path`` is one file's detail; `## Impact` is what is connected to what, "
            "worth checking before changing a file rather than after.")
        # 🐛 The index deliberately excludes nested checkouts -- somebody else's code is not this
        # repository's source. Said nothing about it, a subagent spawned at the outer root and sent
        # to work on an inner project was pointed at an index with NOTHING about the files it
        # needed: measured here, the outer map mentions `mapper.py` zero times while the inner one
        # is 85,000 characters entirely about it. Naming them is the difference between an index
        # that is silent and one that looks empty.
        try:
            import mapper
            # _nested_repo_dirs returns RESOLVED paths. main() gets `root` from ws.find_root, which
            # resolves, so the two sides match today and this is not a live defect. It is one call
            # site away from being one: any caller that hands _block an unresolved path -- /tmp on
            # macOS, a symlinked checkout -- makes relative_to raise, and the bare except below turns
            # that into "no nested checkouts" rather than an error. Resolve on both sides so the
            # subtraction cannot depend on the caller.
            _base = root.resolve()
            nested = sorted(d.relative_to(_base).as_posix()
                            for d in mapper._nested_repo_dirs(root))
        except Exception:
            nested = []
        if nested:
            # Each name through one_line, for the reason the rule titles below are: a DIRECTORY NAME
            # is repository text too, and redact.scrub strips credentials, not control characters.
            # The sibling line was wrapped and this one was not, which is this repository's own
            # recurring disease -- a fix applied to some members of a set.
            shown = ", ".join(f"`{mdblock.one_line(n)}`" for n in nested[:4])
            parts.append(
                f"That index does NOT cover the checkouts nested inside this one — {shown}"
                + (f" and {len(nested) - 4} more" if len(nested) > 4 else "")
                + ". Each has its own `.chamnan/MAP.md`; use that one if the work is in there.")

    # Rules are the half a subagent is most likely to break without knowing, because they are
    # decisions rather than facts and nothing in the code states them.
    try:
        rules = memory.rules_text(root)
    except Exception:
        rules = ""
    if rules:
        titles = [ln.lstrip("# ").strip() for ln in rules.splitlines()
                  if ln.startswith("# ") or ln.startswith("**")]
        # Each title through one_line: a rule TITLE is repository text, and this is paid into every
        # subagent. redact.scrub below strips credentials, not control characters.
        shown = [mdblock.one_line(t.strip("*")) for t in titles if t][:4]
        if shown:
            parts.append("Rules this repository works under, in `.chamnan/memory/rules/` — "
                         "read the one that matches before assuming: "
                         + "; ".join(shown) + ".")

    if not parts:
        return ""
    parts.append("Recorded decisions and lessons are in `.chamnan/memory/`. "
                 "Read the one whose title matches; do not read them all.")
    return "[chamnan] " + " ".join(parts)


def main():
    try:
        payload = json.load(sys.stdin)
        payload = payload if isinstance(payload, dict) else {}
    except Exception:
        return 0
    # A fork inherits the parent's whole conversation, session-start block included, so the pointer
    # would be a second copy of something already in its context. Measured over 22 historical fork
    # dispatches in this repository: none of them ever opened MAP.md, and none of them needed to.
    if (payload.get("agent_type") or "").lower() == "fork":
        return 0
    root = ws.find_root(Path(payload.get("cwd") or "."))
    if root is None:
        return 0
    # Default-on, switchable off in .chamnan/config.json like every other section.
    if not ws.enabled("subagent_pointer", root):
        return 0

    text = _block(Path(root))
    if not text:
        return 0
    # Scrubbed at the one place it leaves the process, as chamnan_file_pointer.py does: a rule
    # TITLE is repository text, and a title has carried a live credential before.
    text = redact.scrub(text)
    if len(text.encode("utf-8")) > MAX_BYTES:
        text = text.encode("utf-8")[:MAX_BYTES].decode("utf-8", "ignore").rstrip() + " …"
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SubagentStart", "additionalContext": text}}))
    return 0


def _never_fail_the_session():
    """A hook that cannot read something exits 0 in silence rather than 1 with a traceback.

    Same reasoning as the other write-only hooks here: stderr never reaches the transcript, so a
    crash is invisible and the subagent simply starts without this.
    """
    try:
        return main()
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(_never_fail_the_session())
