"""Gemini CLI — a real SessionStart hook, not a file of text.

**Verified against the installed CLI rather than from memory.** Gemini CLI 0.57.0 ships its own
documentation inside the npm bundle, and every claim below is read from it:

  - `SessionStart` fires on startup, resume and `/clear`, and is "used for loading initial context"
  - its output field is `hookSpecificOutput.additionalContext`, injected as the first turn in an
    interactive session and prepended to the prompt in a non-interactive one
  - hooks are configured in `.gemini/settings.json` at the project level, merged over the user's
    `~/.gemini/settings.json`
  - the default per-hook timeout is 60000 ms, and their own best-practices page asks for a stricter
    one on a fast hook

So this agent gets the same treatment Claude Code gets -- context injected at session start, fresh
every time -- rather than a static file that goes stale the moment anything changes. That is the
whole reason adapters are separate modules: Cursor's answer is a file and Gemini's is a hook, and
no single structure holds both without one of them being a special case inside the other.

**Two differences from Claude Code that matter.** Gemini wants JSON on stdout, where Claude Code
takes the text directly -- so `render()` wraps rather than formats. And no byte truncation of hook
output is documented anywhere in the shipped docs, which is why `CEILING` is None; that is "not
documented", not "measured to be absent", and the difference is worth keeping straight.

**`settings.json` belongs to the user.** It carries their IDE preferences, their security policy
and any hooks they wrote themselves. `install()` merges and never replaces, and it refuses rather
than guesses when the file will not parse.
"""
import json

NAME = "gemini"
TARGET = ".gemini/settings.json"
CEILING = None

# Generous against a hook measured at 0.78s, and far below the 60s default, which their own
# best-practices page asks callers to tighten. A hook that hangs should cost a session a second,
# not a minute.
TIMEOUT_MS = 15000

HOOK_NAME = "chamnan-context"


def render(body):
    """The block as the JSON Gemini CLI expects on a SessionStart hook's stdout.

    `ensure_ascii=False` so Thai, Japanese and every other non-Latin repository keeps its own
    characters rather than being expanded into escapes that cost three times the bytes and cannot
    be read by a person debugging the hook.
    """
    return json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": body,
        }
    }, ensure_ascii=False)


def _entry(command):
    return {
        "matcher": "startup",
        "hooks": [{"name": HOOK_NAME, "type": "command", "command": command,
                   "timeout": TIMEOUT_MS}],
    }


def _is_ours(group):
    """Whether a configured SessionStart group is one chamnan wrote.

    By the hook's NAME, not by the command string: the command carries an absolute path that
    changes when the plugin is upgraded or the repository is moved, and matching on it would leave
    a second copy behind on every such change until the user had four of them.
    """
    if not isinstance(group, dict):
        return False
    return any(isinstance(h, dict) and h.get("name") == HOOK_NAME
               for h in group.get("hooks", []) if True)


def install(root, body, command):
    """Register the SessionStart hook in `.gemini/settings.json`, preserving everything else.

    `body` is unused here and is accepted so every adapter's install has one shape -- Gemini's
    context is produced by running `command` at session start, not by writing text now, which is
    exactly the difference this adapter exists to express.

    Raises ValueError when the file exists and does not parse. Merging into a file whose contents
    could not be read means writing a fresh one, which silently discards a user's IDE settings and
    security policy -- and they would have no reason to look here for them.
    """
    import workspace as ws

    from . import safe_target

    path = safe_target(root, TARGET)
    settings = {}
    if path.exists():
        try:
            settings = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise ValueError(f"{path} does not parse ({exc}); refusing to replace it") from exc
        if not isinstance(settings, dict):
            raise ValueError(f"{path} is not a JSON object; refusing to replace it")

    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError(f"{path} has a `hooks` key that is not an object; refusing to change it")
    groups = hooks.setdefault("SessionStart", [])
    if not isinstance(groups, list):
        raise ValueError(f"{path} has a `hooks.SessionStart` that is not a list")

    # Replace ours in place rather than appending, so re-running install is idempotent and an
    # upgraded plugin path is corrected instead of duplicated.
    replaced = False
    for i, group in enumerate(groups):
        if _is_ours(group):
            groups[i] = _entry(command)
            replaced = True
            break
    if not replaced:
        groups.append(_entry(command))

    path.parent.mkdir(parents=True, exist_ok=True)
    ws.atomic_write_text(path, json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
    return path
