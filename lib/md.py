"""Markdown structure that a line-anchored regex gets wrong.

A fenced code block may contain any line at all, including lines that look exactly like ATX
headings: `# rebuild the map` inside a bash block is a shell comment, not a section. Every
scanner here that walks headings has to skip those, or a section boundary lands inside a fence
and the block is torn in half.

`state.split_pinned` is why this module exists. Its whole job is that a pinned section is never
dropped, and a `#` comment inside a fenced block ended the pinned span early -- putting the
sentence the pin existed to protect into the droppable pool, and emitting an unterminated fence
into the injected text. The same shape bit `pointer`, which read a `description:` line out of a
document's prose because it never checked that the line was inside real front matter.

Stdlib only, like the rest of the package. This follows CommonMark closely enough for documents
people actually write; it does not attempt to be a parser.
"""
import re

# An ATX heading: up to three spaces of indent, 1-6 '#', then a space. Callers that care about
# the level or the text use their own pattern -- this module's job is only to say which offsets
# are real prose.
_FENCE = re.compile(r"^(?P<indent>[ ]{0,3})(?P<fence>`{3,}|~{3,})(?P<info>[^\n]*)$", re.M)

_FRONT = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", re.S)


def fenced_spans(text):
    """Character ranges covered by fenced code blocks, fence lines included.

    Three or more backticks or tildes, after at most three spaces of indent, open a block; a run
    of the same character at least as long, with nothing but whitespace after it, closes one. A
    backtick fence's info string may not itself contain a backtick, which is what separates an
    opening fence from an inline-code run. An unclosed fence runs to the end of the document --
    what a real parser does, and what makes a half-written file safe to scan.
    """
    spans, open_at, marker = [], None, ""
    for m in _FENCE.finditer(text):
        fence = m.group("fence")
        if open_at is None:
            if fence[0] == "`" and "`" in m.group("info"):
                continue
            open_at, marker = m.start(), fence
        elif fence[0] == marker[0] and len(fence) >= len(marker) and not m.group("info").strip():
            spans.append((open_at, m.end()))
            open_at, marker = None, ""
    if open_at is not None:
        spans.append((open_at, len(text)))
    return spans


def prose_only(text):
    """A predicate: does this character offset sit in ordinary prose rather than inside a fence?

    Built once per document and closed over, so a scanner walking every heading pays for the
    fence sweep once rather than per match.
    """
    spans = fenced_spans(text)
    if not spans:
        return lambda pos: True
    return lambda pos: not any(a <= pos < b for a, b in spans)


def headings(pattern, text):
    """Every match of `pattern` in `text` that is NOT inside a fenced code block.

    The one call every heading scanner in this package should be making instead of
    `pattern.finditer(text)`.
    """
    ok = prose_only(text)
    return [m for m in pattern.finditer(text) if ok(m.start())]


def front_matter(text):
    """The YAML front-matter body, or "" when the document does not open with a `---` line.

    Searching for `key:` anywhere instead is how `pointer` came to title an entry with a sentence
    lifted out of its own prose. Front matter is a delimited block at the very top or it is not
    front matter.
    """
    m = _FRONT.match(text)
    return m.group(1) if m else ""
