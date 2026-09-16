#!/usr/bin/env python3
"""PostToolUse(Agent) — record what a subagent actually cost, and whether it ran on the model it says.

Two questions this answers, and neither had an answer before:

**Did the subagent run on the model its own file declares?** claude-code#89723 (open): a subagent
shipped inside a plugin does not honour the `model:` key in its frontmatter, while the identical file
under a project's `.claude/agents/` does. So an agent pinned to a cheap model silently runs on the
session's model instead, and the bill is the only place it shows. Two chamnan agents pin one today.

**What did it cost?** The owner holds the release of every research round because they are
controlling token spend, and the only instrument for that is watching account meters by hand.

**Why this is a PostToolUse on `Agent` and not a `SubagentStop` hook.** Two independent research
rounds recommended `SubagentStop`, and it would not have worked: its documented payload is
`session_id`, `transcript_path`, `cwd`, `permission_mode`, `hook_event_name`, `stop_hook_active`,
`agent_id`, `agent_type`, `agent_transcript_path`, `last_assistant_message`, `background_tasks`,
`session_crons` -- no model, no tokens. `resolvedModel`, `modelsUsed`, `totalTokens`, `usage`,
`totalDurationMs` are fields of the Agent tool's `tool_response`, read by a PostToolUse hook, and the
hooks reference says so outright: *"To inject context into the parent session after a subagent
returns, use a PostToolUse hook on the Agent tool instead."* A `SubagentStop` hook would have
registered fine, fired on every subagent, read `None` for the field it exists to check, and reported
nothing, silently, for as long as it stood.

**The limitation, stated here rather than discovered later.** Since Claude Code 2.1.198 subagents run
in the background by default, and a background launch returns `status: "async_launched"` with no
usage fields at all -- only `agentId`, `description`, `prompt`, `outputFile` and `resolvedModel`. So
the model check covers both cases and the cost figures cover foreground runs only. Every record says
which it is, because a cost roll-up that quietly omits half its population is worse than none.

**It reports and records. It never blocks.** The owner's instruction on this class of problem, given
about installed plugins that fight the work: do not remove, do not disable -- detect, tell the
person, and keep a record they can refer back to when something turns out to be wrong later.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
import mdblock  # noqa: E402
import redact  # noqa: E402

print = redact.emit_prescrubbed  # noqa: A001
import workspace as ws  # noqa: E402

LOG = "logs/agent_results.jsonl"
RECORDS = "state/agent_model_mismatches.jsonl"

# One line per run, and the file bounds itself by record rather than by age: the whole value of a
# cost history is that it is long enough to compare against. `workspace.SELF_PRUNING_LOGS` names it
# so the file-age sweep leaves it alone.
MAX_RECORDS = 2_000

# Aliases the host accepts in `model:` against what a resolved model id looks like. A pin reading
# `haiku` is satisfied by `claude-haiku-4-5-20251001`, and comparing the two strings directly would
# report every correctly-pinned agent as a mismatch -- which is the failure mode that makes a
# warning worthless.
_FAMILIES = ("haiku", "sonnet", "opus", "fable", "mythos")

# 🐛 [2026-09-17] These were matched with `fam in low`, a substring test, so any longer word that
# CONTAINS a family name resolved to that family. Verified against the pre-fix function: `opuscule`,
# `fabled`, `haikus-and-sonnets`, `unsonnetlike` and `mythoslike` all leaked. The cost was a warning
# accusing a correctly-pinned agent of running the wrong model -- a wrong accusation is worse than a
# missed one here, because the run has already happened either way.
#
# 🐛 The example this was FIRST written around was `opus` inside `corpus`, which is false and was
# never checked: `corpus` is c-o-r-p-u-s, with an `r` between the `o` and the `p`. It was asserted in
# a commit title, in this comment and in a check header before anybody ran `"opus" in "corpus"`. The
# defect class is real and the fix stands; the story attached to it was invented. Run the two-second
# check on the EXAMPLE, not only on the rule.
_SEGMENT = re.compile(r"[^a-z]+")


def _family(name):
    """The model family in a pin or a resolved id, or "" when it names none of them.

    Matched on whole segments rather than as a substring. Every real id separates the family with a
    punctuation character -- `claude-opus-5`, `claude-haiku-4-5-20251001`, `claude-opus-4-5@20251101`,
    `anthropic.claude-opus-4-5-v1:0` -- so splitting loses nothing, while a substring test reads
    `fable` out of `fabled` and accuses a correctly-pinned agent of a mismatch it never had.
    """
    low = (name or "").lower()
    parts = set(_SEGMENT.split(low))
    for fam in _FAMILIES:
        if fam in parts:
            return fam
    return ""


def _declared_model(root, agent_type):
    """The `model:` a subagent's own definition pins, or "" when it pins none.

    Both places an agent can be defined, because the whole defect is that one of them is honoured
    and the other is not: a plugin's `agents/<name>.md` and the project's `.claude/agents/<name>.md`.
    A plugin-namespaced type arrives as `plugin:name`, and the file is named for the second half.
    """
    if not agent_type:
        return ""
    leaf = str(agent_type).split(":")[-1]
    if not leaf or "/" in leaf or "\\" in leaf or leaf.startswith("."):
        return ""
    for base in (HERE.parent / "agents", Path(root) / ".claude" / "agents"):
        f = base / (leaf + ".md")
        try:
            if not f.is_file():
                continue
            head = f.read_text(encoding="utf-8-sig", errors="replace")[:2000]
        except OSError:
            continue
        # 🐛 [2026-09-10] The first version ended the scan with
        # `if s == "---" and line is not head.splitlines()[0]`, which rebuilds the list on every
        # iteration and compares string IDENTITY against a fresh object — always true, so it broke
        # on the OPENING `---` and never read a single key. The hook registered, fired on every
        # subagent, logged every run with `declared: ""`, and could therefore never report a
        # mismatch: exactly the silent-and-confident failure it exists to catch. Caught by driving
        # it with four real payloads rather than by reading it.
        lines = head.splitlines()
        if not lines or lines[0].strip() != "---":
            continue                       # no frontmatter at all
        for s in (ln.strip() for ln in lines[1:]):
            if s == "---":
                break                      # end of frontmatter; no model key
            if s.lower().startswith("model:"):
                return s.split(":", 1)[1].strip()
    return ""


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0

    root = payload.get("cwd") or "."
    if ws.workspace(root) is None or not ws.workspace(root).is_dir():
        return 0                            # not a chamnan workspace; say nothing, write nothing

    tool_in = payload.get("tool_input") or {}
    tool_out = payload.get("tool_response") or {}
    if not isinstance(tool_in, dict) or not isinstance(tool_out, dict):
        return 0

    agent_type = tool_in.get("subagent_type") or payload.get("agent_type") or ""
    asked = tool_in.get("model") or ""
    resolved = tool_out.get("resolvedModel") or ""
    status = tool_out.get("status") or ""
    declared = _declared_model(root, agent_type)

    row = {
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "agent": str(agent_type)[:80],
        "status": str(status)[:24],
        "asked": str(asked)[:60],
        "declared": str(declared)[:60],
        "resolved": str(resolved)[:60],
        # Absent rather than zero when the run was backgrounded: a cost roll-up that reads a missing
        # figure as 0 under-reports and looks precise doing it.
        "tokens": tool_out.get("totalTokens"),
        "ms": tool_out.get("totalDurationMs"),
        "tools": tool_out.get("totalToolUseCount"),
        "models_used": tool_out.get("modelsUsed"),
    }
    ws.append_jsonl(root, LOG, row, MAX_RECORDS)

    # A mismatch is only a mismatch when the agent DECLARED something and the host resolved something
    # else. No pin, or a resolved id the host did not report, is not evidence of anything.
    if declared and resolved and _family(declared) and _family(resolved) \
            and _family(declared) != _family(resolved):
        note = dict(row, kind="model-pin-mismatch",
                    why=("the agent's own file pins %s and the run resolved to %s"
                         % (_family(declared), _family(resolved))))
        ws.append_jsonl(root, RECORDS, note, MAX_RECORDS)
        # Said out loud, once, where the person asking for the subagent is looking. Not a block:
        # the run already happened, and refusing anything here would only lose its result.
        #
        # 🐛 [2026-09-10] Written first as `print(json.dumps(...))`, which is wrong twice over and
        # the suite caught both. The `print` shadowed at the top of this file is
        # `redact.emit_prescrubbed`, so it applies `for_a_terminal` to the DUMPED string — and by
        # then `json.dumps` has escaped every non-ASCII code point to `\uXXXX` text that no
        # character filter matches, which Claude Code decodes back on the other side. The strip has
        # to happen on the TEXT, before the dump. `chamnan_scratch_watch.py` carries the same
        # correction and its comment notes that all three other hooks had this wrong, each in its
        # own way; this was a fourth, written by someone who had read that comment an hour earlier.
        _text = mdblock.as_quoted(
            "chamnan: `%s` declares `model: %s` and this run resolved to `%s`. "
            "The declared model was not honoured — see claude-code#89723 for the plugin-agent "
            "case. Recorded in `.chamnan/%s`; nothing was blocked."
            % (agent_type, declared, resolved, RECORDS), 400)
        sys.stdout.write(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": redact.for_a_terminal(redact.scrub(_text))}}) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(ws.never_fail(main))
