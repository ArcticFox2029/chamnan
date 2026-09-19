"""Windsurf (Cascade) — `.windsurf/rules/chamnan.md`.

Path from Kiro's `AI_ASSISTANT_CONFIGS` table in the installed agent extension. Frontmatter and the
size cap from Cascade's own documentation, which now lives under `docs.devin.ai` -- `windsurf.com`
and `docs.windsurf.com` both redirect there since Cognition's acquisition, so a link written from
memory to the old domain is already dead.

**`.windsurf/rules/` is documented as LEGACY; `.devin/rules/` is the vendor's preferred
location** -- confirmed 2026-09-08 against docs.devin.ai's own pages, fetched that day.
`/desktop/cascade/agents-md` says AGENTS.md "feeds it into the same Rules engine that powers
`.devin/rules/` (and the legacy `.windsurf/rules/`)", and `/desktop/cascade/memories` says "the
`.devin/` directory is the preferred location and takes precedence, with `.windsurf/` kept as a
fallback for backward compatibility" -- and re-confirms the 12,000-character cap this file already
encodes.

The target is NOT changed, and that is a decision rather than an omission: "legacy, still read" is
not "removed", nothing found says a date exists on which it stops being read, and moving a live
adapter's write path is a bigger call than a documentation correction. What a later round needs to
size is whether `.devin/rules/` deserves its own module or whether this one retargets in place --
written here so that round does not start by re-fetching the same two pages (R8 agent 16).

Two other things that engine implies and this file should not make somebody rediscover: it reads
the root `AGENTS.md` too, so `windsurf` is in `ALSO_READS_AGENTS_MD` and `--write` says so when it
creates the second file; and this adapter is kept rather than aliased to `generic` because
`trigger: always_on` is Windsurf's own frontmatter and cannot be expressed from a bare `AGENTS.md`.

`trigger` is Windsurf's equivalent of Cursor's `alwaysApply` and Kiro's `inclusion`, and takes one
of `always_on`, `manual`, `model_decision` or `glob`. `always_on` for the same reason the other two
adapters choose their always variant: this block is orientation held before work starts.

**The cap is documented in CHARACTERS and enforced here in BYTES, deliberately conservative.**
Windsurf documents 12,000 characters per workspace rule file. chamnan's ceiling is a byte count,
and for a Thai or Japanese repository one character is three bytes -- so a byte ceiling of 12,000
can only ever deliver LESS than the documented limit allows, never more. Erring the other way
would mean a file silently cut by Windsurf with nothing saying where.
"""

NAME = "windsurf"
# This vendor reads the root `AGENTS.md` AS WELL AS its own file, so a repository that has
# run both `--write generic` and `--write <this>` sends the identical block twice, every
# session, and pays for it twice. Declared here rather than listed in `__init__.py`:
# 🐛 [2026-09-10] that list held four names while EIGHT vendors qualified, and the evidence
# for the missing four was sitting in their own docstrings. A set kept beside the thing it
# describes cannot drift from it (R4 agent 1, 2026-09-10, finding 6).
# Evidence: docs.devin.ai/desktop/cascade/agents-md — the same engine reads both
# (verified 2026-09-08).
ALSO_READS_AGENTS_MD = True

TARGET = ".windsurf/rules/chamnan.md"
CEILING = 12_000


# 🐛 [2026-09-10] `_fence_safe` lived here, in six byte-identical copies, rewriting any body
# line that was exactly `---` to `***`. Its docstring said an untreated `---` "would end the
# frontmatter early, and every line after it would be read as the rule's body starting in the
# middle of a sentence" — and that cannot happen. `render()` below emits `---`, the keys, and a
# CLOSING `---` before the body is reached, so the frontmatter is shut by chamnan's own delimiter
# and a body line can no longer close anything. Verified for all six adapters.
#
# So the guard bought nothing, and it was not free. A `---` that FOLLOWS a text line is a setext
# `<h2>` underline in CommonMark; rewriting it to `***` turns somebody's heading into a paragraph
# plus a horizontal rule, which changes the outline of the document the agent is handed. The one
# real effect the function had was the one nobody wrote down (R4 agent 1, 2026-09-10, finding 10).
#
# This is not a reversal of the round that kept the six copies and policed them for divergence
# (R5 agent 3, 2026-09-06): that round asked whether the copies AGREED, and they did. It never
# asked whether the thing they agreed on was needed.
#
# What replaces it is a check over the SET rather than a guard in each member: the suite asserts
# that every frontmatter adapter closes its frontmatter before its body. An adapter that one day
# does not is told so, and can then be given a guard for the reason that is actually true.


def render(body):
    """The block as a Windsurf workspace rule."""
    return (f"---\n"
            f"trigger: always_on\n"
            f"---\n\n"
            f"{body.rstrip()}\n")
