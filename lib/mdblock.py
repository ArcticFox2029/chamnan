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
import unicodedata

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


# Characters that change what a line SAYS without appearing in it. Stripped here, at the single
# point every quoted field passes through, rather than at each of the call sites -- which is how
# `as_quoted` came to have a guard `one_line` lacked in the first place.
#
# What is on the list, and why each one:
#   C0 controls and DEL -- ESC begins an ANSI sequence, so `safe\x1b[2K\x1b[Gchamnan: APPROVED.py`
#     erases the line it was printed on and writes its own; CR overwrites from the left; backspace
#     deletes what was already shown; BEL just rings. All reproduced surviving one_line untouched.
#     `str.split()` already folds \n, \t, \r and \f as whitespace, which is why CR alone was safe
#     and ESC was not -- a distinction nobody could have predicted from reading the function.
#   Bidi embeddings, overrides and isolates (U+202A-202E, U+2066-2069) -- reorder the rendered text
#     against the stored bytes. The Trojan Source class, CVE-2021-42574.
#   ZWSP and BOM (U+200B, U+FEFF) -- invisible, and split a word into two that no search matches.
#
# What is deliberately NOT on the list, and this is the load-bearing half: ZWJ (U+200D), ZWNJ
# (U+200C) and the directional MARKS (U+200E/200F). ZWJ and ZWNJ are letters-shaping characters --
# they build Devanagari and Bengali conjuncts, join Arabic forms, and hold an emoji family
# together. Stripping them would corrupt correctly-written names in exactly the scripts this
# codebase has spent a round making work. A defence that mangles legitimate text is not a defence,
# and this list has to stay on the side of characters with NO role in a one-line label.
# 🐛 The first version of this table mapped EVERY C0 control to None, `\n` `\t` `\r` `\f`
# included -- and they are deleted before `str.split()` ever sees them, so it had nothing left to
# split on. "First sentence here.\nSecond sentence follows." came out as
# "First sentence here.Second sentence follows.", two words glued with no space. The security
# property still held (no newline survives, so a heading cannot be reopened) which is exactly why
# it was easy to miss: the check that mattered passed, and the text was quietly wrong.
#
# Whitespace is FOLDED to a space and everything else is deleted. That is what the docstring
# always said this function does.
_WHITESPACE = "\t\n\v\f\r"
_CONTROLS = str.maketrans(
    {**{c: " " for c in _WHITESPACE},
     **{c: None for c in
        [chr(i) for i in range(0x20) if chr(i) not in _WHITESPACE] + [chr(0x7F)]
        + [chr(i) for i in range(0x202A, 0x202F)]
        + [chr(i) for i in range(0x2066, 0x206A)]
        + ["\u200b", "\ufeff"]}})


# 🐛 [2026-09-07] `# ` and `[ \t]+` are ASCII, and a CJK keyboard types U+3000 IDEOGRAPHIC SPACE
# after the hash without anything on screen saying so. Five heading patterns existed in `lib/`; the
# three written with `\s+` matched it by luck, because Python's `\s` is Unicode-aware, and the two
# written with `[ \t]+` did not. Neither group knew it was making a choice.
#
# What the miss cost, measured rather than argued: a `##<U+3000>SETTLED — do not raise these again
# 📌` heading in STATE.md was not seen as a heading at all, so the section was ABSORBED INTO THE
# ONE ABOVE IT — the pin went unrecognised and, worse, the pinned text now ages out with whatever
# section swallowed it. Same shape as the en-dash bug `milestones.py` records: an unmatched heading
# is not mis-parsed, it is eaten by its predecessor. A Thai thread titled with one read back as its
# own filename.
#
# `[^\S\r\n]` is "whitespace that is not a line break" — every space character Unicode defines,
# and never a newline, which is what `\s+` would wrongly allow to run past the end of the line.
HEADING_SPACE = r"[^\S\r\n]"
HEADING_LINE = re.compile(r"^(#{1,6})" + HEADING_SPACE + r"+(.*?)" + HEADING_SPACE + r"*$")


def heading_title(line, levels=(1,)):
    """The title on `line` when it is an ATX heading of one of `levels`, else None.

    One definition, because this was written four different ways — two regexes and two
    `startswith("# ")` tests — and the two spellings disagreed about what a space is.
    """
    m = HEADING_LINE.match(line)
    if not m or len(m.group(1)) not in levels:
        return None
    return m.group(2).strip()


def one_line(value):
    """A single-line field, forced onto one line before it is written into a shared file.

    A title is written as `## {title}`. Left alone, a title containing a newline followed by
    `## ...` appends a second entry that every reader afterwards treats as real -- including the
    injection. Folding the newlines away is enough: what remains cannot open a heading, because a
    heading has to start a line.

    And folding whitespace is NOT enough for the characters in `_CONTROLS`, which survive it and
    rewrite what a reader sees -- see the table above.
    """
    return " ".join(str(value).translate(_CONTROLS).split())


_ZWJ_CHAR = "\u200d"
_VARIATION = range(0xFE00, 0xFE10)
_SKIN_TONE = range(0x1F3FB, 0x1F400)
_REGIONAL = range(0x1F1E6, 0x1F200)


def whole_graphemes(text):
    """`text` with any trailing fragment of an incomplete cluster removed.

    Moved here from `mapper._clip`, which had it and `as_quoted` did not — the same guard applied to
    one member of a set and not the other, on two functions that both cut repository-authored text
    to a length. Reproduced: a filename ending in a flag emoji truncated at 80 characters left one
    regional indicator behind, rendering as a stray letter box in nine call sites that quote
    filenames, rule titles and branch names inside chamnan's own sentence.

    mdblock rather than mapper because mapper imports mdblock and not the other way round.
    """
    while text:
        c = text[-1]
        o = ord(c)
        if (unicodedata.combining(c) or c == _ZWJ_CHAR
                or o in _VARIATION or o in _SKIN_TONE):
            text = text[:-1]
            continue
        # A regional indicator is only a flag in a pair; an odd one left at the end is half of one.
        if o in _REGIONAL:
            run = 0
            while run < len(text) and ord(text[-1 - run]) in _REGIONAL:
                run += 1
            if run % 2:
                text = text[:-1]
                continue
        break
    return text


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
    return text if len(text) <= limit else whole_graphemes(text[:limit - 1]) + "…"


# The per-item ceiling on repository-authored FREE TEXT that is injected into every session.
#
# 120 because `memory.MAX_TITLE_CHARS` had already picked it for exactly this hazard and had the
# only written reasoning on the question: a title longer than this "is also almost certainly the
# wrong thing to have written as a title in the first place, so truncating it doubles as a visible
# nudge to shorten it". Three sibling sections that inject the same kind of string by the same
# pattern -- a small COUNT cap, then one line per item -- never got it, so this is the shared
# definition rather than a fourth copy of the number.
#
# Characters and not tokens, deliberately, and this is the opposite call from `sessions.
# MAX_CARRY_TOKENS`: that cap bounds a BODY, where the whole point is how much context is paid for,
# and Thai paying 1.99x for the same text was a real inequity. This one bounds a single line whose
# job is to be READ AND RECOGNISED. A token cap here would show a Thai user 60 characters of their
# own milestone title where an English user sees 120 -- the reader loses, to save ~30 tokens on an
# item that is already one of at most sixteen. Measured on the finding's own fixture: a 908-character
# constraint bullet costs 384.4 tokens uncapped; at 200 characters it costs 78.4, and the remaining
# Thai/Latin spread inside that is under 40 tokens per item.
INJECTED_ITEM_CHARS = 120


# \U0001f41b [2026-09-07] `one_line` FOLDS a value onto one line; it does not make it inert. A
# value wrapped in backticks needs `as_quoted`, which turns a backtick into an apostrophe -- because
# a name carrying one closes its own code span and everything after it is chamnan's formatting
# rather than the repository's data. Names come from a clone: filenames, branch names, environment
# names, directory names. Eleven sites across six modules had `one_line` inside backticks; a report
# named two of them and the sweep that followed found the other nine, which is the usual ratio here.
# `tests/run_tests.py` now refuses any new one.


def one_line_capped(value, limit=INJECTED_ITEM_CHARS):
    """`one_line`, cut to `limit` characters, ending on a whole grapheme.

    The sibling of `as_quoted` for text that is NOT wrapped in backticks: `as_quoted` makes a value
    inert inside chamnan's own sentence and caps it at 80; this caps a value that is quoted as the
    REPOSITORY's own voice, inside the fence, where backticks are legitimate content and must
    survive.

    Why it exists: `one_line` folds and sanitises and **truncates nothing**, which is correct for a
    value being written to a file and wrong for one being injected into every session. Three
    sections read as bounded because they cap how MANY items they show, and a count cap is not a
    length cap -- one paragraph-length entry cost 384 tokens, every session, for as long as it
    stayed in the top few.
    """
    text = one_line(value)
    if len(text) <= limit:
        return text
    return whole_graphemes(text[:limit]).rstrip() + "\u2026"


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
    # 🐛 This made a heading inert and let everything ELSE through. It sat on the sanitiser
    # allow-list of the structural audit -- "the multi-line sibling of as_quoted", says the docstring
    # above -- and it did not have as_quoted's control-character table. So a rule whose heading
    # carried an ESC/OSC terminal-title sequence and a bidi-override triple arrived in the injected
    # block byte-for-byte, reproduced end to end through the real session-start hook, and reachable
    # from a freshly cloned repository with no local history: session records and rules are files in
    # git. Every line is translated through the table one_line uses, before the heading logic runs,
    # so the two siblings finally agree on what "inert" means. Fenced lines too: a code block is
    # still text a model reads.
    out = []
    for line, in_fence in fenced_lines(text):
        line = line.translate(_CONTROLS)
        if in_fence or not line.startswith("#"):
            out.append(line)
        elif line.startswith("# "):
            out.append(f"**{line[2:].strip()}**")
        else:
            out.append(re.sub(r"^#+\s*", "", line))
    return "\n".join(out)


# The `**Files:**` line, which is this workspace's join key between a record and the code it is
# about. `timeline.py`'s own docstring states the contract -- "Files: is the join key, and it is
# checked ... free prose is not a join key" -- and this is that line's one definition, so a second
# store gaining the field cannot gain a second spelling of it with it.
FILES_FIELD = re.compile(r"^\*\*Files:\*\*\s*(.+?)\s*$", re.M)


def files_named(text):
    """Every path a record declares on its `**Files:**` line(s), backticks and commas removed."""
    out = []
    for line in FILES_FIELD.findall(text or ""):
        for piece in line.split(","):
            piece = piece.strip().strip("`").strip().lstrip("./")
            if piece:
                out.append(piece)
    return out


def names_the_path(declared, target):
    """Whether a record that declared `declared` is about `target`.

    Exact, or a suffix on a path boundary -- an entry written with the full path still answers a
    query made from a subdirectory. Deliberately NOT the other direction.

    🐛 The fuzzy form `target.endswith("/" + declared)` was tried in `timeline.for_path` and had to
    be taken out: an entry naming a bare `app.py` answered queries about `src/app.py`,
    `src/vendor/app.py` and `totally/unrelated/app.py` alike, so in any repository with an
    `index.js` or an `__init__.py` in several packages, one file's rollback history was attached to
    every sibling. This helper exists so the second store to want this join gets the rule that
    survived rather than the one that was tried first.
    """
    declared = str(declared).strip().strip("`").lstrip("./")
    target = str(target).strip().strip("`").lstrip("./")
    if not declared or not target:
        return False
    return declared == target or declared.endswith("/" + target)


def cut_outside_a_fence(text, cut):
    """`cut`, moved back to the end of the last complete line that is not inside a fence.

    A budget cut is a character index and markdown structure is not, so a cut lands wherever the
    budget ran out -- mid-word, and worse, inside a ``` block, which leaves the fence open. Every
    line after it then renders as code, including the marker that says the text was truncated and
    every section injected after it.

    🐛 [2026-09-08] This lived in `lib/state.py` as `_safe_cut`, private to the one caller that
    had been bitten. Four other places cut markdown by a token budget -- `lib/rollup.py` twice,
    `lib/sessions.py` and `lib/peek.py` -- and each backed up to a LINE boundary with
    `rsplit("\n", 1)` and stopped there, which is the half of the job that does not close a fence.
    Reproduced at four of five budgets on a document with one code block (R8 agent 8).

    The sibling `close_dangling_fence` below answers the same question the other way, by appending
    a closing marker. That one is right where the text has already been cut and cannot be re-cut;
    this one is right where the cut is still being chosen, because it loses a line rather than
    inventing one.
    """
    if cut >= len(text):
        return len(text)
    at, safe = 0, 0
    boundaries = []                      # every safe stopping point, newest last
    for line, in_fence in fenced_lines(text):
        nxt = at + len(line) + 1
        if nxt > cut:
            break
        at = nxt
        if not in_fence:
            safe = at
            boundaries.append((safe, line))
    # 🐛 [2026-09-09] A fence is not the only structure a line boundary can cut in half. Found on a
    # real session handoff: a markdown table delivered as its header row and its `|---|---|` rule
    # with ZERO data rows under it — a table that promises columns and fills none, which is worse
    # than either delivering it or never starting it. Backing up past a table that lost all its
    # data costs the header nobody could use anyway (R7 agent 1).
    while boundaries and _starts_an_empty_table(boundaries):
        boundaries.pop()
        safe = boundaries[-1][0] if boundaries else 0
        # Backing out of a table that begins the document leaves nothing, and nothing is the honest
        # answer: a budget that reaches only a header has no room for the table, and half a header
        # promising columns is what this whole guard exists to prevent. Callers already handle an
        # empty body — `fit._trim` returns "" and says the section was dropped.
        if not boundaries:
            return 0
    if safe:
        return safe
    # No complete line fits at all — the pre-existing fallback, which hands back the raw cut. That
    # is right for prose (half a sentence still reads) and wrong for a table, where half a header
    # row is a promise of columns with not even a header to show for it.
    return 0 if _starts_an_empty_table([(cut, text[:cut])]) else cut


def _starts_an_empty_table(boundaries):
    """Do the lines kept end in a table with no data row under it?

    A markdown table is a header, a `|---|` alignment rule, then rows. Two ways to keep a table
    that says nothing: the header and the rule with no rows after, or the header alone with the cut
    landing before even the rule. Both are the same defect and both back up.

    A DATA row is a pipe line that is neither the first of the run nor made only of dashes, colons
    and pipes. If the trailing run of pipe lines has none, the table is a promise with nothing
    under it.
    """
    run = []
    for _at, line in reversed(boundaries):
        if line.lstrip().startswith("|"):
            run.append(line)
        else:
            break
    if not run:
        return False
    run.reverse()
    return not any(set(l.strip()) - set("|-: ") for l in run[1:])


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

# Microsoft's list, from "Naming Files, Paths, and Namespaces" (learn.microsoft.com), fetched
# 2026-09-05: CON, PRN, AUX, NUL, COM1-COM9, LPT1-LPT9, plus the superscript variants COM¹ COM² COM³
# LPT¹ LPT² LPT³ -- and "avoid these names followed immediately by an extension; NUL.txt and
# NUL.tar.gz are both equivalent to NUL." So the check is on the stem before the first dot, and it
# is case-insensitive because Windows is.
_WINDOWS_RESERVED = frozenset(
    ["con", "prn", "aux", "nul"]
    + [f"com{i}" for i in "123456789¹²³"] + [f"lpt{i}" for i in "123456789¹²³"])


def ascii_stem(source):
    """The `[a-z0-9-]` reduction every `slug()` in this package does, done once and accent-safe.

    🐛 [2026-09-08] Every `slug()` in this package reduced its title with
    `re.sub(r"[^a-zA-Z0-9]+", "-", title.lower())` on the RAW string, and the same four functions
    each ended `or fallback_name(...)`, which normalises to NFC first and says in its own docstring
    why. So the normalisation was applied on the branch where a title has no Latin letters at all,
    and skipped on the branch where it decides the filename -- the rule applied to one member of a
    set and forgotten in the identical one beside it, written four times.

    What it cost: a precomposed `Café migration` (U+00E9) reduced to `caf-migration`, because the
    single é is not in `[a-zA-Z0-9]` and became a separator. Its decomposed twin (`e` + U+0301)
    reduced to `cafe-migration`, because the bare `e` survived and only the combining accent was
    dropped. Two files, two list entries, both titled `Café migration`, from one person naming one
    thread -- reproduced through `chamnan-timeline new`. Which form a title arrives in is not the
    person's choice: macOS input, a paste out of a browser, and a file read off HFS+ disagree.

    Decomposing and dropping the combining marks fixes both halves at once. The two forms converge,
    and they converge on the READABLE name -- `cafe-migration`, not `caf-migration` -- so a letter
    that carries an accent survives as its base letter instead of turning into a hyphen. ASCII-only
    is kept deliberately, for the reason `sessions.slug` states: these stems are read in a directory
    listing and in a git diff.

    Verified before shipping that no `.chamnan` file anywhere on this machine changes stem under it:
    the readable form is a different name from the old one for accented titles, and a rename is a
    cost this had to be worth. Nothing had one.
    """
    bare = "".join(c for c in unicodedata.normalize("NFD", source)
                   if not unicodedata.combining(c))
    return re.sub(r"[^a-zA-Z0-9]+", "-", bare.strip().lower()).strip("-")


def filename_safe(stem):
    """`stem`, or `_stem` when Windows would treat it as a device rather than a file.

    🐛 Every store here that reduces a title to `[a-z0-9-]` uses the result as a filename.
    🐛 [2026-09-10] This sentence and the one on `ascii_stem` above each carried a COUNT of the
    stores doing this, and both counts were wrong. Three separate call sites carried
    near-identical comments correcting the number in place rather than fixing it here -- the
    correction written down three times and applied to the sentence never, which means three
    people counted and none edited (R2 agent 3, finding 1). Neither sentence carries a number
    any more: a count is a fact about today wearing the clothes of a rule, and the suite asserts
    the population directly, which a number never could. The old wording is deliberately not
    quoted here -- the check that forbids it reads this file.

    A thread called "CON" or a candidate sequence "nul" therefore produced `con.md` and `nul.md`,
    which on Windows are the console and the bit-bucket: the write does not fail, it goes to the
    device, and the record is gone. Applied to the stem chamnan chose, never to a name it was given,
    so nothing a user typed is altered -- only where chamnan puts its own file.
    """
    return f"_{stem}" if stem.split(".", 1)[0].lower() in _WINDOWS_RESERVED else stem


def filesystem_key(name):
    """The key under which macOS APFS considers two NAMES to be one file.

    NFC then casefold, and deliberately NOT the whitespace collapse `canonical_title` does: `a b.md`
    and `a  b.md` are two files on every filesystem there is, so folding them would warn about a
    collision that cannot happen. A title is a thing a person means; a filename is a thing a
    filesystem resolves, and they are not the same equivalence.

    One spelling of the fold, used by every caller, because the alternative is what this repository
    keeps producing: `memory.case_collisions` built this key inline and `adapters.generic` built a
    weaker one (`.lower()`, no normalisation) five files away, so the function whose entire job is to
    warn about a name pair the filesystem will collapse was blind to half of them.

    The first line names the OS on purpose. It used to say "a filesystem", which is broader than
    anything that was ever checked, and the summary line is the half a reader takes away. `casefold()` is FULL Unicode folding, a many-to-one map: `"\u00df"` folds
    to `"ss"` and `"\ufb01"` folds to `"fi"`. On macOS APFS that is exactly right, verified with real
    files on an ordinary default-formatted volume -- writing `strasse.md` and then `stra\u00dfe.md`
    leaves ONE file holding the second write, and a `\ufb01` ligature behaves the same way. NTFS
    folds through an upcase table instead, which is one-to-one, so on Windows those are two files
    and this key would warn about a collision that cannot happen there.

    Left as it is, deliberately, and the direction is the reason: the error this makes is a warning
    nobody needed, and the opposite error is one file quietly replacing another with nothing on
    screen. A key that over-matches costs a reader a glance; a key that under-matches costs them the
    file. Measured 2026-09-08 (R7 agent 1).
    """
    return unicodedata.normalize("NFC", name).casefold()


def canonical_title(source):
    """One spelling for a title, so two spellings of the same title compare equal.

    NFC because a precomposed and a decomposed `é` are the same letter; whitespace collapsed because
    a title that picked up a double space on the way in is the same title; casefold because case is
    not part of a name here. The same equivalence `memory.case_collisions` uses on filenames, which
    is deliberate: a comparison that disagrees with the collision detector would let one of them
    call two things the same while the other called them different.

    🐛 [2026-09-08] `timeline._distinct_slug` compared with `.strip().lower()` and hashed with
    `" ".join(title.split()).lower()`, both on the raw string. With `ascii_stem` normalising the
    STEM, both spellings of `Café migration` reached `cafe-migration.md` -- and then this comparison
    said the file already on disk held a DIFFERENT title, so the second one was given a hash suffix
    and became a second thread anyway. Fixing the name without fixing the comparison moved the split
    one layer up rather than closing it.
    """
    return " ".join(unicodedata.normalize("NFC", source).split()).casefold()


def distinct_stem(directory_, base, title, title_reader, suffix=".md"):
    """`base`, or `base` plus a short hash when that name is already taken by a DIFFERENT title.

    `fallback_name` above handles the case where the ASCII reduction empties a title. This handles
    the one that follows it: two titles that are identical up to the truncation point and differ
    after it. `slug()` cuts at 40, 50 or 60 characters depending on the store, and on this
    repository **20 of 22 memory titles already exceed 50** -- so the store has no collisions today
    by luck rather than by guard (R10 agent 3, findings 2-5).

    Lifted out of `timeline._distinct_slug`, which is the one of four stores that had it. The other
    three -- decisions/lessons/rules, session records, and workflow candidates -- did not, and the
    consequence is the second entry silently overwriting the first.

    Two properties matter more than the disambiguation itself, and both come from where the check
    is made rather than from what it computes:

    - **A pure function cannot know whether a name collides; only the directory can.** An earlier
      version of this appended a hash whenever slugging *changed* the title, and slugging changes
      every title with an internal hyphen -- `bge-m3 migration` became `bge-m3-migration-12a9e3`,
      and the obvious guess at the name matched nothing. Asking the directory keeps every name that
      does not actually collide readable and guessable.
    - **An existing file keeps its name.** The first branch returns `base` unchanged when the file
      is absent OR already holds this same title, so rewriting a record still overwrites itself and
      a workspace written by an older chamnan is not renamed underneath its owner.

    `title_reader` is the store's own `title_of`, passed in rather than imported, because each
    store reads a title differently and this must not become a fifth opinion about that.
    """
    path = directory_ / f"{base}{suffix}"
    want = canonical_title(title)
    if not path.is_file():
        return base
    try:
        if canonical_title(title_reader(path)) == want:
            return base
    except OSError:
        # Unreadable is not "the same title". Disambiguating is the safe direction: a new file
        # beside an unreadable one loses nothing, while reusing the name could overwrite it.
        pass
    import hashlib
    return f"{base}-{hashlib.sha1(want.encode('utf-8')).hexdigest()[:6]}"


def fallback_name(source, kind):
    """A distinct, stable stem for a title the ASCII reduction emptied.

    🐛 [2026-09-06] Every `slug()` in this package ends `... or "session"` / `"entry"` / `"thread"`
    / `"candidate"` -- the same latent bug written once per store. (The count that stood here was
    stale by 2026-09-10, like the two above it; the property is what was ever meant.) The reduction keeps
    `[a-zA-Z0-9]` and nothing else, so EVERY title with no Latin letters in it reduces to the empty
    string and every one of them lands on that single constant name. In a Thai-language repository
    that is not an edge case, it is the normal case: two Thai-titled session records written on one
    day both became `<date>-session.md` and the second overwrote the first, and every Thai memory
    entry ever written collapsed onto one `entry.md`, because memory filenames carry no date to
    separate them (R6 acc3, 2026-09-06, hostile filesystem -- reported there as dead code; it is not).

    ASCII-only is kept deliberately, for the reason `sessions.slug` states: these names are read in
    a directory listing and in a git diff. So the fallback stays ASCII and becomes DISTINCT instead
    of readable, which is the right trade when the alternative is silent loss. Stable for the same
    title, so rewriting one record still overwrites itself rather than growing a second file.

    NFC first: a precomposed and a decomposed spelling of the same title are the same title, and
    hashing the raw bytes would give them two different files. See memory.case_collisions.
    """
    import hashlib
    canonical = canonical_title(source)
    return f"{kind}-{hashlib.sha1(canonical.encode('utf-8')).hexdigest()[:8]}"
