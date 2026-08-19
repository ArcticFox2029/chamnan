# chamnan

**ชำนาญ** *(cham-nan)* — Thai for the fluency that only comes from doing something again.

A Claude Code plugin that makes a repository know itself, so an agent stops rediscovering it.
It builds an index the agent reads instead of scanning files, keeps work state that survives
compaction, and accumulates the procedures and tools you keep re-deriving.

It is built for codebases you come back to. On a script you write once, it will cost you more
than it returns — see [Who this is not for](#who-this-is-not-for).

---

## The problem it aims at

Most token-saving tools compress what the model *writes*. Measured on one developer's 34 days of
real Claude Code usage, that is the small half:

| | share of cost |
|---|---|
| context read in | **91.2%** |
| output written | 8.8% |

The most popular output-compression plugin advertises 65% savings; [JetBrains benchmarked it across
86 tasks](https://blog.jetbrains.com/ai/2026/07/speak-to-ai-agents-like-cavemen-tosave-tokens/) and
measured 8.5% of output tokens — roughly 0.7% of a bill, with no loss of quality. It does what it
says; it is just aimed at the smaller half.

chamnan aims at the other 91%: not by compressing context, but by making most of it unnecessary.

## What it does

| | |
|---|---|
| **Index** | `MAP.md` — one line per file, generated from the code. The agent reads the index; it greps the detail; it stops reading the tree. |
| **Data model** | Table and model names with a one-line summary, pulled from DDL, migrations and ORM models — instead of a schema dump. Only appears if the repo defines one. |
| **API surface** | Method, path and handler, pulled from route decorators and OpenAPI documents — instead of the whole spec. Only appears if the repo serves one. |
| **Configuration** | The environment variable names the repo reads. **Names only, never values** — and it warns if `.env` is not gitignored. |
| **Deployment** | What actually runs, read from Kubernetes, Ansible, Compose, Helm and CI manifests: kinds and names, images, roles, pipelines. A Secret contributes its name and nothing under it. |
| **Stored material** | The non-source trees — scanned paperwork, exports, archives — as counts, sizes and dominant extensions. It exists to stop an agent going to look, which costs far more than the section does. Never opened, never read. |
| **State** | `STATE.md` — injected at session start, so compaction stops erasing what the last session worked out. |
| **Procedures** | Skills the agent writes *itself* when it hits something complex or repeated. Not a shipped library — a mechanism. |
| **Tools** | Notices when the same scratch script is written a third time, and offers to keep it. |
| **Measurement** | Reports context-per-turn for your repo, before and after. Your number, not ours. |
| **Routing** | Its own agents run on a cheap model, because "read this file, write one line" does not need an expensive one. |

Every part can be switched off independently in `.chamnan/config.json`. They do not depend on each
other, and they do not have equal evidence behind them — see below.

## Install

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

Then, in a repository you actually work in:

```
/chamnan:bootstrap
```

To try it without installing:

```bash
claude --plugin-dir ./chamnan
```

## Evidence

Split by how much weight it can carry. The first tier you can reproduce in your own repo in about
ten seconds; the second is one developer's history and is labelled as such.

### Reproducible — run `chamnan-map` and see your own

The index against the source it indexes, on three real repositories:

| repo | languages | source | Quick Index | ratio |
|---|---|---|---|---|
| a Python app | Python, 33 files | 306,388 tok | 1,395 tok | **0.5%** |
| a JS game | JS + shell + Python, 19 files | 270,466 tok | 863 tok | **0.3%** |
| a small dashboard | JS + shell, 12 files | 19,467 tok | 596 tok | **3.1%** |

Six navigation questions ("where is the shop economy tuned?", "what runs every 10 minutes?",
"where are credentials stored?") were answered from the Quick Index alone, 6 out of 6, without
opening a source file.

### One repository, observed — not a controlled trial

On the repo where this was developed, holding the model constant (Sonnet 5 before and after):

| per API call | before | after | |
|---|---|---|---|
| context carried | 464,191 | 359,466 | **−22.6%** |
| new material read | 7,120 | 4,283 | **−39.8%** |
| output written | 860 | 843 | −2.0% |

The same weeks also brought a model change, different kinds of task, and Claude Code updates of its
own. This is an observation on n=1, not a benchmark. `chamnan-report` computes the same figures for
your repository, which is the number that should actually decide anything.

### The condition this all depends on

The index is built from each file's opening comment. On the three repos above, 92–100% of files had
one — because that codebase requires them. **A repo without them gets an index of filenames and
function counts, which is worth far less.**

`chamnan-map` prints your coverage every run, and `/chamnan:bootstrap` offers to fill in what is
missing. That is not a footnote; it is the difference between this working and not.

## Who this is for

- Developers on a codebase they will be in for months
- Testers re-running the same checks
- Infra and IT work with runbooks and repeated procedures
- Teams where a new session has to pick up where the last one stopped

## Who this is not for

- **One-off scripts and throwaway prototypes.** You pay the setup and never collect. Genuinely
  net-negative; use something else.
- **Writing, chat, fiction, anything without code.** There is no structure here for it to index.
- **Repos with no comments and no intention of adding any.** The index degrades to filenames.
- **Anyone wanting a token discount without changing how they work.** The saving comes from the
  agent reading an index instead of a tree. If it goes back to reading the tree, nothing is saved.

## What it deliberately does not do

- **No shipped skill library.** Someone else's procedures do not match your repo. This ships the
  mechanism that writes yours.
- **No output-style compression.** That lane is taken, and it is aimed at the 8.8%.
- **No large CLAUDE.md.** A plugin about context cost must not become one. The session-start
  injection is bounded and reports when it is truncated.
- **No claimed percentage on your bill.** It measures yours instead.

## Language

chamnan writes the comments and procedures it generates in English by default. Those strings are
re-read on every session, and English carries the same meaning in fewer tokens — measured at 1.53x
for Thai versus English across three matched sentence pairs.

**That figure was measured with a local model's tokenizer, not Claude's.** Take it as a direction,
not a number: the ratio is real, its exact size on Claude is unverified here.

It is a default, not a rule. A team whose reviewers do not read English is better served by
comments they will actually read, and the plugin does not argue:

```json
// .chamnan/config.json
{ "language": "th" }
```

Or just say so — "write the comments in Thai" is enough, and Claude sets it for you. Nothing else
in the plugin changes: replies to you are in whatever language you are speaking, always.

## One file, only what applies, and a ceiling

Everything above is a section inside a single `MAP.md`, not a folder of separate catalogues. A
section is written only when the repo actually has that thing — a directory of plain scripts gets a
code index and nothing else, no empty headings.

The part of `MAP.md` above `## Full Detail` is what gets injected at session start, so it has a
budget: `index_token_budget`, 3,000 tokens by default, well under 1% of a 1M context window.
`chamnan-map` reports against it and says what to do when a repo exceeds it. This is the rule that
stops the plugin becoming the cost it exists to remove — that part is paid on every turn.

Everything below `## Full Detail` — function signatures, table columns — is never injected. It is
grepped for one heading at a time.

When a repo is large enough that even the index exceeds the budget, it is **rolled up by directory
rather than truncated**. Cutting at a byte offset drops whatever sorts last, so on a 196-file repo
everything from roughly `s` onward disappears from the session with nothing to show that an entire
area of the code exists — and the agent greps for it, which is the cost this is meant to remove. The
roll-up keeps every directory visible with its file count and a sample, and the full entry for any
one of them is still a grep away. Measured on that repo: 8,762 tokens of index became 560, with all
seven top-level directories still named.

`chamnan-map src game` indexes several directories into one map when the whole tree is more than you
work in.

## Secrets

`MAP.md` is built by copying source comments, and this README suggests committing it. That
combination is a way to publish a password, so it is handled rather than assumed away.

- **Some files are never opened.** `.pem`, `.key`, `.pfx`, `.crt`, `id_rsa*`, `.htpasswd`, `.netrc`,
  `*.db`, `*.sqlite`, and similar are skipped by the scanner outright. `.gitignore` is not relied
  on: it is often absent, often wrong, and the cost of being wrong is somebody's private key.
- **Everything written passes a redactor**, at one choke point on the finished document rather than
  at each extractor, so a section added later cannot bypass it. Provider tokens (`sk-`, `ghp_`,
  `AKIA…`, `AIza…`, `xox…`, Stripe, GitLab, npm, JWTs), private-key blocks, credentialed URLs, and
  `password = "…"`-style assignments are replaced with `<REDACTED>`.
- **Environment variables are recorded as names only.** No code path here carries a value into the
  output; values are discarded at parse time.

Verified with a repository seeded with a live-looking Stripe key, a `postgres://user:pass@host` in a
comment, and an RSA private key — none reached `MAP.md`, while
`postgres://admin:<REDACTED>@db.internal:5432/main` stayed readable, because *which database on
which host* is exactly what an index should tell you.

The redaction patterns are narrow on purpose. Redacting everything high-entropy would eat commit
hashes, UUIDs and version strings, and a map full of `<REDACTED>` is not a map.

**This protects chamnan's own output, not your whole session.** A plugin hook cannot rewrite what
the Read tool returns — `PostToolUse` exposes only `additionalContext` and `systemMessage` — so no
plugin can filter what Claude reads from your disk. Anything claiming otherwise is describing a
capability Claude Code does not have.

## Bulk reads

Before a `Read` pulls in a lock file, a minified bundle, or a very large file, chamnan says so and
suggests grep. It **never blocks**: the one time someone genuinely needs to read `package-lock.json`
is the one time refusing would be most wrong. Turn it off with `warn_on_bulk_reads: false`.

It does not strip comments or blank lines from files on the way in — partly because hooks cannot,
and partly because comments are the highest-value tokens in a file for a reader trying to understand
intent. This plugin's entire index is built out of them.

## Keeping the index fresh

```bash
chamnan-map --install-git-hook
```

Opt-in, and it appends to an existing `pre-commit` hook rather than replacing it. After that the
index refreshes on any commit that touches tracked files, and never fails a commit if chamnan
errors. Remove it by deleting the block marked `# >>> chamnan`.

A stale index is worse than no index: it is confidently wrong, and the next session believes it.

## Layout

```
.chamnan/
├── MAP.md          architecture index (generated)
├── STATE.md        work in flight — written at milestones, not every edit
├── config.json     which parts are on
├── skills/         procedures the agent recorded
├── tools/          scripts promoted from scratch
└── logs/           bounded, expires
```

## Commands

| | |
|---|---|
| `/chamnan:bootstrap` | first-time setup: index, coverage, fill comments, baseline |
| `/chamnan:remap` | rebuild the index after the repo's shape changed |
| `/chamnan:capture` | record a procedure worth keeping |
| `/chamnan:promote` | keep a scratch script as a tool |
| `/chamnan:report` | show context-per-turn, before and after |
| `chamnan-map` · `chamnan-report` · `chamnan-promote` | the same things from a shell |

## Tests

```bash
python3 tests/run_tests.py
```

87 checks, no dependencies. The redaction cases are the reason the file exists: every other part of
this fails visibly — a wrong map entry sends you to the wrong file and you notice — while a
redaction regression fails silently and writes a credential into a file this README tells you to
commit.

Both directions are covered throughout. A redactor that replaces everything would pass any
"did it hide the secret" test perfectly, so the suite also asserts that commit hashes, UUIDs, RFC
numbers and credential-free URLs come through untouched.

Two real bugs were found by writing it: the scratch-repeat threshold was tuned against long scripts
and silently ignored the short repeated ones it exists to catch, and a Google API key one character
outside the expected length slipped the pattern.

## Limitations

- Python is parsed properly (`ast`); every other language is read with regex, which will miss
  unusual declarations. A map is a navigation index, not a compiler front-end — a miss costs one
  grep. Currently: C, C++, Objective-C, Arduino, C#, Swift, Java/Kotlin, Scala, Go, Rust, Zig, Nim,
  JS/TS, Dart, Ruby, Elixir, Lua, PHP, shell, Terraform, plus Protobuf and GraphQL schemas.
- Measured against sixteen real open-source repositories across C, C++, Java, Kotlin, C#, Swift,
  Go, Rust, Python, Ruby, PHP, Dart, Elixir, Lua and TypeScript, rather than fixtures. Summary
  coverage on them runs 7-100%, and the low end is real: those projects write a licence header
  where a description would go. A licence is not a description, so it is not counted as one —
  which is why these figures are lower, and truer, than the ones this README carried before.
- Nothing here executes the code it reads.
- `chamnan-report` needs history on both sides of installation before it can compare anything.

## License

MIT
