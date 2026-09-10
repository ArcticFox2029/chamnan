# Why every command string in `hooks.json` is prefixed with the plugin name

Moved out of `hooks.json` on 2026-09-10. It had lived there as a `"_comment"` key since
2026-09-01, and Claude Code prints `chamnan: hooks.json: unknown key "_comment" ignored`
on **every session start** because of it. JSON has no comments; a plugin whose whole claim is
that it does not add noise should not be adding a warning line to every startup to hold one.

The record itself, unchanged:

Every command string is prefixed with the plugin name. Claude Code before 2.1.69 deduplicated
hooks by the RAW command string, before ${CLAUDE_PLUGIN_ROOT} was expanded, so two plugins both
registering "${CLAUDE_PLUGIN_ROOT}/hooks/session_start.py" collided and one was silently
dropped (anthropics/claude-code#16954, #21659, #23281; #29724 was a re-report). Fixed in 2.1.69,
changelog line 'silently dropped when two plugins use the same command' -- and the current hooks
reference says outright that a plugin's copy of the same handler stays separate. The prefix is
kept anyway: chamnan declares no minimum Claude Code version, and for the one hook that is its
entire delivery path a filename costs nothing. An earlier version of this comment said the
issue was closed without a fix; that was wrong, and this is the correction (R7 agent 3).
