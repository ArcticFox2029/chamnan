"""Every place a name is actually USED, for the languages where that can be answered exactly.

The tool for this repository's most-recorded defect: a fix applied to one member of a set and
forgotten in the identical ones beside it, eighteen recorded instances. The rule
`the-set-not-the-member` tells you to find the whole population; it never gave you anything to find
it with, and `grep` is not that thing.

Measured on one file holding every hard case -- a docstring, an import, a string literal, a comment,
a method of the same name, a shadowed local, and three real calls: **grep reports nine lines, this
reports three.** Six of grep's nine are noise, and one of the two it cannot distinguish at all is
the shadowed local, where the name means something else entirely.

**Two methods, and which one answered is part of the answer.** Python has a parser, so Python is
exact. For the other twenty languages the first version of this module said "nothing", on the
reasoning that a declaration has a fixed shape while a call site does not, and that a regex sweep
across twenty-two languages is the false-positive machine this project has refused fifteen times.
That reasoning is still right about a regex sweep and was wrong about the conclusion: there is a
third option, which is to remove what makes a text search wrong before matching at all.

Comments and string literals are where a text search goes wrong. Blank them, then match on word
boundaries. Measured on `chamnan-corpus` -- 530 files, all 21 languages, 40 identifiers chosen by
how many files carry them -- **34.6% of a text search's lines were comment or string text**, from
12% in Zig to 63% in Terraform. Against the parser's verdict on 40 DECLARED function names in that
corpus's Python: 155 text-search lines, 115 real, 138 reported here, **and nothing the parser found
was missed.**

That last clause is the one that cost the work. The first version blanked interpolation along with
the literal around it, losing five real uses of `_rand` inside Python f-strings -- a false ABSENCE,
which is the failure this module refuses in `in_source` by returning None rather than []. Fixing it
gave back some precision (42% of the text search's excess removed, against 62% before) and that is
the right trade for a tool whose whole job is to find every position.
"""
import ast
import os
import re

# 🐛 [2026-09-22] (self-measured) This was 800,000 and the first real run proved the number wrong.
# `tests/run_tests.py` in this package is 2.8 MB, so it landed in "not judged" -- and it is exactly
# where the references were that this module exists to find: the two checks reaching
# `whole_graphemes` through `mapper._clip` that a grep by function name missed by hand the day
# before. A cap chosen for cost had hidden the defect the tool was written for.
#
# Parsing it costs 2.7 s and finds 29 references. This is a command somebody asked for, not a hook
# on every keystroke, and a few seconds is the right trade against a wrong answer. 4 MB matches
# what `chamnan_file_pointer` already refuses to read of `MAP.md`, so the pathological case -- a
# fifty-megabyte bundle -- is still refused, and refusing it is still COUNTED rather than hidden.
MAX_BYTES = 4_000_000


def _bound_locally(fn):
    """Names this function binds itself: arguments, assignments, imports, comprehension targets.

    A call to one of these is a call to something else that happens to share a name, and reporting
    it is the difference between an answer and a list of coincidences.
    """
    out = set()
    a = getattr(fn, "args", None)
    if a is not None:
        for x in list(a.posonlyargs) + list(a.args) + list(a.kwonlyargs):
            out.add(x.arg)
        if a.vararg:
            out.add(a.vararg.arg)
        if a.kwarg:
            out.add(a.kwarg.arg)
    for n in ast.walk(fn):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                for nn in ast.walk(t):
                    if isinstance(nn, ast.Name):
                        out.add(nn.id)
        elif isinstance(n, (ast.AnnAssign, ast.AugAssign)):
            if isinstance(n.target, ast.Name):
                out.add(n.target.id)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for al in n.names:
                out.add((al.asname or al.name).split(".")[0])
        elif isinstance(n, (ast.For, ast.AsyncFor, ast.comprehension)):
            tgt = getattr(n, "target", None)
            for nn in ast.walk(tgt) if tgt is not None else ():
                if isinstance(nn, ast.Name):
                    out.add(nn.id)
        elif isinstance(n, ast.withitem) and n.optional_vars is not None:
            for nn in ast.walk(n.optional_vars):
                if isinstance(nn, ast.Name):
                    out.add(nn.id)
    return out


def in_source(text, symbol):
    """[(lineno, kind)] for every real use of `symbol` in one module's source.

    `kind` is "call", "attribute" or "def". A name inside a string, a comment or a docstring is
    none of those, and a call inside a function that binds the same name is not this symbol.
    """
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return None                      # unparseable is not the same as "no references"
    shadowed = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            if symbol in _bound_locally(n):
                for inner in ast.walk(n):
                    shadowed.add(id(inner))
    out = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == symbol:
            out.append((n.lineno, "def"))
        elif isinstance(n, ast.Call) and id(n) not in shadowed:
            f = n.func
            if isinstance(f, ast.Name) and f.id == symbol:
                out.append((n.lineno, "call"))
            elif isinstance(f, ast.Attribute) and f.attr == symbol:
                out.append((n.lineno, "attribute"))
    return sorted(set(out))


# ---------------------------------------------------------------------------------------------
# The other twenty languages. Lexical, and labelled as lexical.
#
# `in_source` above is exact because Python ships a parser. For everything else the honest options
# were "nothing" -- which is what shipped first, and what the README said -- or a regex sweep, which
# is the false-positive machine this project has refused fifteen times. There is a third, and it was
# measured against the one language where the right answer is already known.
#
# Blank out comments and string literals, then match the identifier on word boundaries. Against the
# AST's verdict on six real symbols in this package (92 true uses, 178 grep hits, 86 of them noise):
#
#     line comments stripped          noise 86 -> 32    63% removed
#     strings stripped as well        noise 86 ->  2    98% removed
#
# 94 reported against the AST's 92. **Strings are the bigger half**, which was not the guess: the
# first version of this idea was going to strip comments only.
#
# Two things it deliberately is not. It is not a parser, so a hit is reported as a `use` and never
# as a `def` or a `call` -- a lexical scan cannot tell a declaration from a call, and labelling a
# use as a call sends a reader looking for a caller that may not exist. And it is not complete:
# NOT handled are nested block comments (Rust permits them, so `/* /* */ */` closes early), shell
# heredocs, and a JavaScript regex literal containing `//`. Each of those leaves a comment or string
# treated as code, which costs a false positive -- the same failure grep has, in the few places this
# does not improve on it, rather than a false absence.
_LEXICAL_USE = "use"
# 🐛 [2026-09-22] (self-measured) String interpolation is EXECUTED CODE, and blanking it with the
# literal around it loses a real reference -- a false absence, which is the one failure this module
# refuses everywhere else. It was fixed for Ruby `#{}` and JS `${}` and forgotten in the eight
# identical cases beside them, which is this repository's most-recorded defect shape and its
# nineteenth recorded instance. Found by a corpus run: five uses of `_rand` inside Python f-strings
# went missing, and Python is the ONE language here that does not depend on this path, so the same
# hole was live for Dart, Kotlin, Swift, Scala, C#, PHP and Elixir, which do.
#
# Derived per language rather than one pattern for all, because the syntaxes genuinely differ and a
# single `[$#]\{` matched three of the ten. `INTERP_PREFIX` is the other half: `{x}` is code only
# inside an f-string or a C# `$"..."`, and treating every brace in every quoted string as code
# would hand back the false positives this scanner exists to remove.
# Interpolation is EXECUTED CODE inside a string literal, so its span has to survive the blanking
# that removes the literal around it. Openers and closers rather than one regex per language: a
# balanced scan has no nesting limit, and the first version of this was a regex with `[^()]*` that
# could not match `\(target())` -- where the parentheses belong to the CALL, which is the whole
# reason somebody interpolates. `\(format(g(x)))` was the case that made the limit unacceptable,
# because a missed reference is a false ABSENCE and this module refuses those everywhere else.
INTERP_SPANS = {
    "js":     (("${", "{", "}"),),
    "sh":     (("${", "{", "}"), ("$(", "(", ")")),
    "rb":     (("#{", "{", "}"),),
    "ex":     (("#{", "{", "}"),),
    "dart":   (("${", "{", "}"),),
    "kotlin": (("${", "{", "}"),),
    "scala":  (("${", "{", "}"),),
    "php":    (("{$", "{", "}"),),
    "swift":  (("\\(", "(", ")"),),
    "py":     (("{", "{", "}"),),
    "cs":     (("{", "{", "}"),),
}
# `$name` with no braces at all. Ruby, Elixir, JS and Python have no such form; shell does, but a
# bare `$name` is a variable read rather than a call and naming it a reference would add noise.
INTERP_BARE = {
    "dart": re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)"),
    "kotlin": re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)"),
    "scala": re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)"),
    "php": re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)"),
}
# Languages where a bare brace means nothing unless the literal is marked. The marker sits
# immediately before the opening quote, and `rb`/`ex`/`js` are absent on purpose: their
# interpolation needs no prefix.
INTERP_PREFIX = {"py": ("f", "rf", "fr", "F", "Rf", "fR"), "cs": ("$", "$@", "@$")}


def _interp_ranges(span, lang):
    """Offsets inside `span` that hold interpolated code, by balanced scan. [] when none."""
    keep = []
    for opener, opn, close in INTERP_SPANS.get(lang, ()):
        at = 0
        while True:
            a = span.find(opener, at)
            if a < 0:
                break
            # Start the count ON the opening bracket, so the scan enters the loop already inside
            # one level. Its position is READ from the opener rather than assumed, which is the
            # whole of the fix below.
            #
            # 🐛 [audit-qa 2026-09-22] This was `a + len(opener) - 1` -- the bracket assumed to be
            # the LAST character of the opener, true of `${`, `#{`, `$(`, `\(` and the bare `{`.
            # PHP's `{$` is the one member of the table where the bracket comes FIRST, so the count
            # started on the `$`, the closing `}` took depth to -1 instead of 0, and the scan fell
            # out of the balanced loop unbalanced: every `"{$obj->target()}"` was blanked with the
            # literal around it. That is the same false ABSENCE the comment above this table was
            # written to record, reintroduced in the table's own reader -- and it is the twentieth
            # instance of this repository's most-recorded defect, a rule landing on one member of a
            # set and missing the one beside it that is spelled differently.
            # An opener that does not carry the bracket at all is entered one level deep from just
            # after it, so a third spelling cannot bring the same defect back a third time.
            at_bracket = opener.find(opn)
            depth, k = ((0, a + at_bracket) if at_bracket >= 0
                        else (1, a + len(opener)))
            while k < len(span):
                if span[k] == opn:
                    depth += 1
                elif span[k] == close:
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            if depth != 0:
                break          # unbalanced: the rest is literal, not a span we can trust
            keep.append((a + len(opener), k))
            at = k + 1
    bare = INTERP_BARE.get(lang)
    if bare:
        keep += [(m.start(1), m.end(1)) for m in bare.finditer(span)]
    return keep


def _ident_in_quotes(lang):
    """True where this language writes DECLARED NAMES inside double quotes.

    Terraform does: `resource "aws_kms_key" "secrets" {` -- the labels are the identity of the
    block, not string data. Blanking quoted spans there destroyed every declaration in the corpus,
    0 of 19 recognised, and the symbol a reader asks for does not survive to be matched at all.

    DERIVED from the declaration patterns rather than named: a rule that captures with `"(` opens
    its capture group immediately after a quote, which is exactly the syntax this is about. `c` also
    mentions a quote -- in a negative lookahead for `extern "C"` -- and is correctly NOT selected,
    which is the discrimination a hand-written list of one language would not have been tested for.

    What it costs, stated: in such a language a genuine string on a code line, `description =
    "target"`, is reported as a use. That is a false positive on a language whose files are mostly
    declarations, against losing every declaration in it.
    """
    import mapper
    return any('"(' in pat for _kind, pat in mapper.REGEX_RULES.get(lang, ()))


def _lang_tables():
    """(EXT_LANG, LINE_COMMENT) from `mapper`, imported only when a non-Python file is judged.

    DERIVED, never copied. A language added to `mapper.EXT_LANG` has to reach this scanner too, and
    a hand-kept second table here is precisely the shape this repository records eighteen times: a
    rule applied to one member of a set and forgotten in the identical ones beside it. The import
    costs 124 ms against `refs` own 0.8 ms, which is why it is lazy -- `chamnan-where` is a command
    somebody typed, and a Python-only repository never pays it at all.
    """
    import mapper
    return mapper.EXT_LANG, mapper.LINE_COMMENT


def code_only(text, lang, line_comments, block=True):
    """`text` with comments and string literals blanked, newlines and column counts preserved.

    Line numbers have to survive, so nothing is deleted -- every suppressed character becomes a
    space. That also means a symbol inside a string cannot reappear as a shorter match by accident.
    """
    out = list(text)
    # Longest first, or `//` inside a language that also has `/` never matches, and `#` would win
    # over `#!` where both are listed.
    markers = sorted(line_comments, key=len, reverse=True)
    quoted_idents = _ident_in_quotes(lang)
    # The C family is identified by its own line-comment marker rather than by a second list of
    # language names, for the same reason `_lang_tables` derives everything else.
    c_family = "//" in line_comments
    n, i = len(text), 0
    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n:                 # an escape outside a string is not our problem
            i += 1
            continue
        # 🐛 Block openers are tested BEFORE line markers, and the order is load-bearing: Lua's
        # line comment is `--` and its block comment opens `--[[`, so a line-first scanner closed
        # the comment at the first newline and read the rest of the block as code. Measured on a
        # three-line fixture: reported line 2 as a use when only line 3 is one.
        if block and c_family and text.startswith("/*", i):
            end = text.find("*/", i + 2)
            end = n if end < 0 else end + 2
            for k in range(i, end):
                if out[k] != "\n":
                    out[k] = " "
            i = end
            continue
        if block and lang == "lua" and text.startswith("--[[", i):
            end = text.find("]]", i + 4)
            end = n if end < 0 else end + 2
            for k in range(i, end):
                if out[k] != "\n":
                    out[k] = " "
            i = end
            continue
        hit = next((m for m in markers if text.startswith(m, i)), None)
        if hit:
            while i < n and text[i] != "\n":
                out[i] = " "
                i += 1
            continue
        if ch == '"' and quoted_idents:
            i += 1          # the labels are the syntax here; see `_ident_in_quotes`
            continue
        if ch in "\"'`":
            # A backtick is a raw string in Go and a template literal in JS; a single quote is raw
            # in POSIX shell. "Raw" only decides whether a backslash escapes the terminator.
            raw = (ch == "`" and lang == "go") or (ch == "'" and lang == "sh")
            # Where a string can carry executed code. A single-quoted literal interpolates in
            # none of these languages, so the DELIMITER decides as much as the language does; and
            # where a prefix is required, the characters before the quote decide as well.
            interp = not raw and lang in INTERP_SPANS
            if ch == "'":
                interp = False     # a single-quoted literal interpolates in none of these
            elif lang in INTERP_PREFIX:
                back = text[max(0, i - 2):i]
                interp = interp and any(back.endswith(pre) for pre in INTERP_PREFIX[lang])
            elif lang == "js" and ch != "`":
                interp = False     # only a template literal interpolates in JavaScript
            j = i + 1
            while j < n:
                if text[j] == "\\" and not raw:
                    j += 2
                    continue
                if text[j] == ch:
                    j += 1
                    break
                # An unterminated quote must not swallow the rest of the FILE. One line is the
                # bound: every language here that allows a newline inside a plain quote (Go and JS
                # backticks, Python triple quotes) either is handled above or goes through the AST.
                if text[j] == "\n" and ch != "`":
                    break
                j += 1
            # 🐛 The whole quoted span used to be blanked, interpolation included -- so
            # `"a #{target} b"` in Ruby and `` `${target}` `` in JS lost a REAL use. That is a
            # false absence in a find-references tool, which is the one failure this module refuses
            # everywhere else (`in_source` returns None rather than an empty list for exactly this
            # reason). The executed span is kept as code; only the literal text around it goes.
            span = text[i:min(j, n)]
            keep = set()
            if interp:
                for a, b in _interp_ranges(span, lang):
                    keep.update(range(i + a, i + b))
            for k in range(i, min(j, n)):
                if out[k] != "\n" and k not in keep:
                    out[k] = " "
            i = max(j, i + 1)
            continue
        i += 1
    return "".join(out)


_DECL_CACHE = {}


def _declares(lang):
    """Compiled declaration patterns for `lang`, from `mapper`'s own rules. () when it has none.

    Reused rather than written: `mapper.REGEX_RULES` already extracts declarations for 20 of the 21
    languages and each pattern is anchored at line start with the declared NAME in group 1, which
    is exactly the two properties this needs. Writing a second set here would be the same defect
    shape the interpolation table already recorded -- and these patterns carry a combining-mark fix
    that a fresh copy would not.
    """
    if lang not in _DECL_CACHE:
        import mapper
        # `re.M` because these patterns are anchored at line start and mapper applies them that
        # way; harmless here, where the subject is one line, and wrong to omit if the subject ever
        # becomes a block.
        # 🐛 The KIND was thrown away here, and it is what decides where the name sits. mapper
        # reads a `func` rule's name from the first group -- the second is the argument list -- and
        # a `class` rule's identity as every group joined with a dot, because Terraform's
        # `data "aws_iam_policy" "eks_admin"` is ONE object and not nine of type `aws_iam_policy`.
        # Dropping the kind and always taking group 0 reported the resource TYPE as the declared
        # name: every Terraform declaration in the corpus came back as a plain use, 0 of 19.
        _DECL_CACHE[lang] = tuple(
            (kind, re.compile(pat, re.M)) for kind, pat in mapper.REGEX_RULES.get(lang, ()))
    return _DECL_CACHE[lang]


def in_text(text, symbol, lang, line_comments):
    """[(lineno, kind)] for a symbol appearing as code rather than in a comment or a string.

    `kind` is "def" only where that language's own declaration pattern matches the line AND names
    this exact symbol; everything else is "use". It is never "call": a lexical scan cannot tell a
    call from a bare mention of the name, and printing one under "call" sends a reader looking for
    a caller that may not exist. Naming the declaration is worth the extra pass because "where is
    this defined" is the first thing somebody asks and the one answer a text search buries.
    """
    if symbol not in text:
        return []
    word = re.compile(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % re.escape(symbol))
    stripped = code_only(text, lang, line_comments)
    decls = _declares(lang)
    out = []
    for k, line in enumerate(stripped.splitlines(), 1):
        if not word.search(line):
            continue
        kind = _LEXICAL_USE
        for decl_kind, pat in decls:
            m = pat.search(line)
            if not m:
                continue
            # 🐛 The name was read from `m.group(1)`, and mapper -- which owns these patterns --
            # reads the first NON-NONE group instead, because several rules carry alternatives
            # where group 1 is None on a match. Copying the table and not its convention is the
            # same defect as copying neither: on the rules where they differ, group 1 is None and
            # every declaration in that language was reported as a plain use.
            groups = [g for g in m.groups() if g is not None]
            if not groups:
                continue
            # mapper's own two rules, and nothing invented beside them.
            if decl_kind == "class" and len(groups) > 1:
                declared = ".".join(groups)
            else:
                declared = groups[0]
            # The name has to be the one asked for -- without that a file's first `func` line is
            # reported as the declaration of every symbol on it. The last dotted component counts
            # too, so `chamnan-where service_secret` finds the Terraform block that declares it
            # while `aws_secretsmanager_secret`, which is the TYPE it instantiates, stays a use.
            if symbol == declared or symbol == declared.rsplit(".", 1)[-1]:
                kind = "def"
                break
        out.append((k, kind))
    return out


def find(root, symbol, skip=("__pycache__", ".git", "node_modules", ".venv", "site-packages")):
    """[(relpath, lineno, kind)], the count of files not judged, and how each answer was reached.

    The second number is the honest half: a file that could not be parsed, or was too big, is not
    evidence of absence, and an answer that hides them is the false all-clear this package refuses
    elsewhere.

    The third is the other honest half, and it is new. Python is answered by a parser and the other
    twenty languages by the lexical scanner above, which is measurably better than a text search and
    measurably worse than a parser. `{"exact": n, "lexical": m}` counts the FILES each way, so a
    caller can say which method produced the answer rather than presenting both as one number --
    the same reason `mapper`'s coverage line reports how many rows carried a claim nothing checked.
    """
    found, unjudged, how = [], 0, {"exact": 0, "lexical": 0}
    ext_lang = line_comments = None

    def _unreadable(err):
        # Without this a directory the walk cannot open is simply ABSENT from the result, and the
        # caller counts what it got as what is there -- the false all-clear this module's own
        # `unjudged` count exists to prevent, one level further out.
        nonlocal unjudged
        unjudged += 1

    for base, dirs, names in os.walk(str(root), onerror=_unreadable):
        dirs[:] = [d for d in dirs if d not in skip and not d.startswith(".")]
        for name in names:
            ext = os.path.splitext(name)[1].lower()
            if ext != ".py":
                # The tables load once, and only if this repository actually holds a file in one of
                # the other languages -- a pure-Python tree never pays `mapper`'s 124 ms.
                if ext_lang is None:
                    ext_lang, line_comments = _lang_tables()
                if ext not in ext_lang:
                    continue
            p = os.path.join(base, name)
            try:
                if os.path.getsize(p) > MAX_BYTES:
                    unjudged += 1
                    continue
                with open(p, "r", encoding="utf-8", errors="replace") as fh:
                    body = fh.read()
                if ext == ".py":
                    hits, method = in_source(body, symbol), "exact"
                else:
                    lang = ext_lang[ext]
                    hits = in_text(body, symbol, lang, line_comments.get(lang, ()))
                    method = "lexical"
            except OSError:
                unjudged += 1
                continue
            if hits is None:
                # 🐛 [2026-09-22] (self-measured) The method counter was incremented beside the
                # call, before this test. `in_source` returns None for a file it cannot parse, so
                # an unparseable Python file was counted BOTH as answered by the parser and as
                # unjudged — the two numbers a caller reads to weigh the answer, contradicting
                # each other about the same file, and `how["exact"] + how["lexical"] + unjudged`
                # summing to more files than were walked.
                #
                # `in_text` has no None return today, so only the Python branch was ever wrong.
                # The increment still moved to the one place both branches pass through, because
                # the defect this repository records most often is a fix applied to one member of
                # a set and forgotten in the identical one beside it — and a lexical scanner that
                # learns to say "I could not read this" would have arrived pre-broken.
                unjudged += 1
                continue
            how[method] += 1
            rel = os.path.relpath(p, str(root)).replace(os.sep, "/")
            for lineno, kind in hits:
                found.append((rel, lineno, kind))
    return sorted(found), unjudged, how
