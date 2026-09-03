"""Windsurf (Cascade) — `.windsurf/rules/chamnan.md`.

Path from Kiro's `AI_ASSISTANT_CONFIGS` table in the installed agent extension. Frontmatter and the
size cap from Cascade's own documentation, which now lives under `docs.devin.ai` -- `windsurf.com`
and `docs.windsurf.com` both redirect there since Cognition's acquisition, so a link written from
memory to the old domain is already dead.

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
TARGET = ".windsurf/rules/chamnan.md"
CEILING = 12_000


def _fence_safe(text):
    """`text` with any line that is exactly `---` unable to close the frontmatter early.

    Its own copy, as in cursor.py and kiro.py: three agents share a frontmatter convention today,
    and a shared helper would mean a change made for one silently changing the other two.
    """
    return "\n".join("***" if line.strip() == "---" else line for line in text.splitlines())


def render(body):
    """The block as a Windsurf workspace rule."""
    return (f"---\n"
            f"trigger: always_on\n"
            f"---\n\n"
            f"{_fence_safe(body).rstrip()}\n")
