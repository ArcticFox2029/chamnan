# Contributing to chamnan

Thanks for looking. This is a small project with a narrow job, and the bar for a change is
"does it make the index more useful, or the plugin cheaper to run" — not feature count.

## What chamnan is

A Claude Code plugin that reads a repository and writes an index of it, so an agent starts a
session already knowing where things are instead of grepping for them. Everything it produces
lives in `.chamnan/` inside the repository it is pointed at.

Two constraints shape almost every decision here, and a change that breaks either is unlikely
to be accepted:

- **Standard library only.** No third-party packages, in the plugin or in its tests. A plugin
  people install into their own repositories should not drag a dependency tree with it.
- **The index must stay cheap.** It is injected at the start of every session, so anything that
  grows it is paid for repeatedly. If a change adds output, it should say what it costs.

## Development setup

```bash
git clone https://github.com/ArcticFox2029/chamnan
cd chamnan
python3 tests/run_tests.py
```

That is the whole setup. Python 3.8 or newer, no virtualenv, nothing to install.

To use your working copy as a live plugin instead of the published one:

```bash
claude --plugin-dir /path/to/chamnan
```

## Repository structure

| | |
|---|---|
| `lib/` | The implementation. `mapper.py` builds the index; `schema.py`, `catalogs.py`, `deploy.py`, `assets.py` each contribute one section of it; `redact.py` strips credentials; `peek.py` reads the shape of a single file; `tokens.py` estimates cost; `rollup.py` folds an oversized index; `workspace.py` owns `.chamnan/` and the config defaults. |
| `bin/` | The four shell commands: `chamnan-map`, `chamnan-peek`, `chamnan-promote`, `chamnan-report`. |
| `hooks/` | The four Claude Code hooks, wired in `hooks/hooks.json`. `session_start.py` is the one that injects the index. |
| `skills/` | The `/chamnan:*` slash commands, one `SKILL.md` each. |
| `agents/` | Agent definitions. Their `tools:` frontmatter is a real permission boundary, not a suggestion. |
| `tests/` | `run_tests.py` — the entire suite. |
| `bench/` | Measurement harnesses. Not part of the plugin; used to check claims before they go in the README. |
| `docs/` | Architecture and data-flow documentation. |

`lib/workspace.py`'s `DEFAULT_CONFIG` is the single source of truth for configuration. If you add
an option, add it there and nowhere else.

## Running tests

```bash
python3 tests/run_tests.py
```

It prints `N/N checks passed` and exits non-zero if anything failed. There is no pytest, no
fixtures directory and no config file — a test is a call to `check(name, condition)`, and adding
one means adding a line.

**Every behaviour change should arrive with a check.** Not for ceremony: most of what this tool
gets wrong fails silently. A wrong index entry sends someone to the wrong file and they notice,
but a redaction gap writes a credential into a file the README suggests committing, and nothing
announces it. The redaction cases exist for exactly that reason and are the ones to add to first.

Assert both directions. A redactor that replaces everything passes any "did it hide the secret"
test perfectly, so the suite also checks that commit hashes, UUIDs and version strings survive.

## Adding language support

Most languages need two small additions to `lib/mapper.py`:

1. **`EXT_LANG`** — map the file extension to a language key.
2. **`REGEX_RULES`** — add that key with a list of `(kind, pattern)` tuples, where `kind` is
   `"func"`, `"class"` or `"const"`. Group 1 of each pattern is the name; for `"func"`, group 2 is
   the argument list.

`_extract_one` dispatches on the language key: `"py"` goes to `extract_python`, which uses the
`ast` module, and everything else goes to `extract_regex`. Nothing else needs touching.

Two things that have gone wrong before, both worth checking in a new pattern:

- **Do not borrow another language's rules.** Kotlin was mapped to `"java"` for a while. Java's
  pattern requires a visibility modifier, Kotlin usually omits one, and 31 files produced 34
  symbols where they should have produced 254. If the syntax differs, it needs its own entry.
- **Control flow reads exactly like a call.** `for (…) { }` fits a `name(args) {` pattern
  perfectly. There is a shared `NOT_A_FUNCTION` deny-list for this; check your language's keywords
  are on it rather than tightening the pattern.

Then add a test with a realistic snippet — including the awkward forms, not only the tidy one —
and confirm the summary extraction works too: `leading_comment` handles comment markers per
language, and languages where `#` is a preprocessor directive rather than a comment belong in
`HASH_IS_DIRECTIVE`.

## Documentation

The README is checked against the code, and claims in it are expected to be reproducible. If a
change alters behaviour a user can see, update the README in the same pull request.

Two specific rules, both learned the hard way:

- **Numbers must be measured.** Every figure in the README came from a run against a real
  repository. If you add one, say where it came from and label it as measured, observed or
  estimated. An estimate presented as a benchmark is worse than no number.
- **Do not describe chamnan as a security boundary.** It redacts its own output. It cannot filter
  what the `Read` tool returns to Claude, because no plugin hook can. Wording that implies
  otherwise will be asked to change.

Comments in the source are English. Content the plugin generates follows the repository's
`language` setting; that is a different thing.

## Pull requests

There is no CI, no PR template and no review rota — this is a small project, and pretending
otherwise would just waste your time. What is expected:

- `python3 tests/run_tests.py` passes.
- New behaviour has a check.
- The commit message says **why**, not what. The diff already says what.
- One concern per pull request. A language addition and a redaction fix are two.

If a change is large or changes the shape of the index, open an issue first and describe what you
are trying to make possible. It is cheaper than finding out after you have written it.

## Reporting bugs

The useful report has three things:

1. What you ran, and what you expected.
2. What happened instead — the actual output, pasted, not described.
3. Enough of the input to reproduce it. For an index problem, the file that came out wrong is
   usually enough; a whole repository is rarely needed.

**Check for credentials before pasting.** chamnan works on real codebases, and output that looks
harmless can carry a hostname or a connection string.

`chamnan-map --preview` is the most useful thing to include for anything session-related: it
prints exactly what a session in that repository receives, so it turns "the plugin is not working"
into a specific observation.

## Licence

MIT. By contributing you agree your contribution is licensed under it.
