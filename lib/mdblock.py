"""Reading markdown structure out of text that a person -- or an agent -- wrote freely.

Four modules in this package find their structure by scanning for lines that start with `#`:
session records split on `##`, milestones and environments parse entries back out of one appended
file, and memory demotes an entry's own headings before injecting it. Every one of them was a
plain per-line regex, and a plain per-line regex cannot tell a heading from a line of a fenced
code block that happens to begin with `#` -- which is what a shell comment, a Python comment and
a markdown example all look like.

That is not cosmetic in this package, because the results are injected. A `## Done` section whose
body quoted a snippet containing `## Remaining` parsed as two sections, and `carry_forward()` --
which is read at the top of the next session -- delivered the fabricated one and silently dropped
the real section that followed it. The same gap in reverse let a milestone title carrying a
newline write a second, complete-looking milestone into the file underneath the real one.

So: `fenced_lines` for reading, `one_line` for writing. Both are deliberately small. A markdown
parser is not being added to a plugin whose whole deployment story is the standard library.
"""
import re

import md

# ``` or ~~~, at least three, optionally indented and optionally carrying an info string.
_FENCE = re.compile(r"^(`{3,}|~{3,})")


def fenced_lines(text):
    """Yield `(line, in_fence)` for every line of `text`.

    A fence opens on the first ``` or ~~~ and closes on the next one of the same character that is
    at least as long -- which is the rule that lets a fence containing ``` be written with ````.
    The fence markers themselves are reported as inside, since neither is ever structure.
    An unclosed fence swallows the rest of the text on purpose: that is what a renderer does, and
    guessing otherwise would put the structure back in the hands of the malformed input.
    """
    fence = None
    for line in text.splitlines():
        m = _FENCE.match(line.lstrip())
        if m:
            mark = m.group(1)
            if fence is None:
                fence = mark
                yield line, True
                continue
            if mark[0] == fence[0] and len(mark) >= len(fence):
                fence = None
                yield line, True
                continue
        yield line, fence is not None


def one_line(value):
    """A single-line field, forced onto one line before it is written into a shared file.

    A title is written as `## {title}`. Left alone, a title containing a newline followed by
    `## ...` appends a second entry that every reader afterwards treats as real -- including the
    injection. Folding the newlines away is enough: what remains cannot open a heading, because a
    heading has to start a line.
    """
    return " ".join(str(value).split())


def as_quoted(value, limit=80):
    """Repository-authored text, made safe to print inside chamnan's OWN sentence.

    🐛 Two warning lines built themselves from repository-controlled strings with raw f-strings —
    the stale-index notice interpolates filenames, and the broken-rule notice interpolates rule
    titles and their `**Check:**` trailers. Both land OUTSIDE the `[repo:nonce]` fence, in chamnan's
    voice rather than the repository's, and neither passed through the redactor. A filename is
    chosen by whoever wrote the clone.

    Backticks are the specific hazard: the caller wraps these in `…`, and a value containing one
    closes the span early and lets everything after it render as chamnan speaking. Newlines are the
    other, for the reason `one_line` exists. Both are removed rather than escaped — a filename that
    contains a backtick is already unusual enough that showing it inert is the right trade.

    The caller still has to scrub the finished line. This makes the value inert; it does not make
    it non-secret.
    """
    text = one_line(value).replace("`", "'")
    return text if len(text) <= limit else text[:limit - 1] + "…"


def demote_headings(text):
    """`text` with every non-fenced ATX heading turned into inert text.

    A rule, a session record or any other entry is written as a standalone file, so it opens with
    its own `# Title` and may use `##`/`###` freely in its body. The caller drops it inside ITS
    OWN `### Section` heading -- and a `#` that survives that trip does not read as a line inside
    that section, it reads as a NEW one: `### Recorded decisions and lessons` typed into a rule's
    body, uncaught, renders as if chamnan itself had opened that heading, with whatever text
    follows it looking like the start of a fresh, legitimate part of the injected block.

    This is the multi-line sibling of what `mdblock.as_quoted` does for a single-line value: make
    repository-authored text incapable of opening a heading before it is embedded in chamnan's own
    structure. A `#` inside a fenced code block is left alone -- it is a comment in the example,
    not a heading of the entry.
    """
    out = []
    for line, in_fence in fenced_lines(text):
        if in_fence or not line.startswith("#"):
            out.append(line)
        elif line.startswith("# "):
            out.append(f"**{line[2:].strip()}**")
        else:
            out.append(re.sub(r"^#+\s*", "", line))
    return "\n".join(out)


def close_dangling_fence(text):
    """`text`, with a closing fence appended if it ends still inside one left open.

    A body that opens a ``` or ~~~ block and never closes it swallows everything injected after
    it -- for `section()`'s callers, that includes the marker that closes the surrounding
    `[repo:nonce]` fence itself and every section that follows -- into what a renderer treats as
    one unterminated code block. A no-op when the fence was already balanced.
    """
    marker = md.unclosed_fence_marker(text)
    if not marker:
        return text
    return text.rstrip("\n") + "\n" + marker + "\n"


def masked(text):
    """`text` with every fenced line blanked to spaces, same length, same offsets.

    For the two callers that scan a whole file with `finditer` rather than line by line: run the
    pattern over this and every `.start()` still indexes into the original string, so the match
    offsets can be used against the real text unchanged.
    """
    out = []
    for line, in_fence in fenced_lines(text):
        out.append(" " * len(line) if in_fence else line)
    tail = "\n" if text.endswith("\n") else ""
    return "\n".join(out) + tail
