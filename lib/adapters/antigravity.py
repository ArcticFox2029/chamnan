"""Google Antigravity / Firebase Studio — `.agents/rules/chamnan.md`.

Workspace rules live in `.agents/rules/`; the singular `.agent/rules` is the older spelling and is
still read. Antigravity also reads a root `AGENTS.md` and `GEMINI.md` directly, and has a
`hooks.json` with `PreInvocation`/`PostInvocation`/`Stop` events -- none of which is a session-start
event, so a hook is not the mechanism for this even where one exists.

Launched at Google I/O 2026 with no published adoption numbers, so this adapter is written on the
documented convention and nothing more. If the convention moves, the file it writes becomes inert
rather than wrong -- a rules file nobody reads costs a few kilobytes on disk.

🐛 CEILING was None, and Antigravity's own documentation says "Rules files are limited to 12,000
characters each" (antigravity.google/docs/rules-workflows/, confirmed 2026-09-05). Measured: at the
`large-window` profile -- the one chamnan picks for the large-context Gemini models this tool pairs
with -- the emitted file was 21,388 bytes on a real repository, 1.78x the documented limit, with
nothing shrinking it and nothing warning. Whatever Antigravity does past 12,000 characters, it is
not what chamnan's drop order would have done, and the user is never told which half they lost.

This is the same defect windsurf.py carries a fix for, written two days earlier: same vendor
convention, same file shape, same 12,000. The sibling added on the same day did not get it. Its
comment on bytes-versus-characters applies here unchanged and for the same reason -- one Thai or
Japanese character is three bytes, so a byte ceiling can only ever deliver less than the documented
character limit allows, never more, and erring the other way means a file the vendor silently cuts
with nothing saying where.
"""

NAME = "antigravity"
# This vendor reads the root `AGENTS.md` AS WELL AS its own file, so a repository that has
# run both `--write generic` and `--write <this>` sends the identical block twice, every
# session, and pays for it twice. Declared here rather than listed in `__init__.py`:
# 🐛 [2026-09-10] that list held four names while EIGHT vendors qualified, and the evidence
# for the missing four was sitting in their own docstrings. A set kept beside the thing it
# describes cannot drift from it (R4 agent 1, 2026-09-10, finding 6).
# Evidence: this adapter's own docstring above: Antigravity reads a root `AGENTS.md` and
# `GEMINI.md` directly, as well as `.agents/rules/`.
ALSO_READS_AGENTS_MD = True

TARGET = ".agents/rules/chamnan.md"
CEILING = 12_000


def render(body):
    """The block, unchanged."""
    return body.rstrip() + "\n"
