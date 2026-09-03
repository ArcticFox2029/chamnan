"""Google Antigravity / Firebase Studio — `.agents/rules/chamnan.md`.

Workspace rules live in `.agents/rules/`; the singular `.agent/rules` is the older spelling and is
still read. Antigravity also reads a root `AGENTS.md` and `GEMINI.md` directly, and has a
`hooks.json` with `PreInvocation`/`PostInvocation`/`Stop` events -- none of which is a session-start
event, so a hook is not the mechanism for this even where one exists.

Launched at Google I/O 2026 with no published adoption numbers, so this adapter is written on the
documented convention and nothing more. If the convention moves, the file it writes becomes inert
rather than wrong -- a rules file nobody reads costs a few kilobytes on disk.
"""

NAME = "antigravity"
TARGET = ".agents/rules/chamnan.md"
CEILING = None


def render(body):
    """The block, unchanged."""
    return body.rstrip() + "\n"
