"""Tencent CodeBuddy Code — `CODEBUDDY.md`.

Its own renamed file, with `AGENTS.md` only as a fallback. The renamed one is written because a
fallback is what a tool reads when the thing it wanted is absent -- relying on it would mean
competing with every other agent that reads the root file, in a repository where CodeBuddy has a
file of its own sitting empty.
"""

NAME = "codebuddy"
TARGET = "CODEBUDDY.md"
# 40,000 characters, and it is a HARD limit: CodeBuddy REJECTS a context file past it rather than
# reading the first 40,000. Taken from the vendor's own unminified `.d.ts` type declarations in the
# `@tencent-ai/codebuddy-code` bundle (`MAX_MEMORY_FILE_SIZE`), cross-read against the matching
# minified implementation — not from documentation (R12 agent 1).
#
# It was `None`, so nothing shrank toward it and nothing warned. Measured on two real repositories
# the emitted block came to 3,922 and 16,473 characters — safe today, and unprotected as a
# repository grows, which is the case a ceiling exists for.
CEILING = 40_000
# Past the ceiling this agent reads NOTHING, where the others read a prefix. The distinction changes
# what the user is told to do, so it is declared rather than assumed.
CEILING_IS_HARD = True


def render(body):
    """The block, unchanged."""
    return body.rstrip() + "\n"
