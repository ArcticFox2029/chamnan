# chamnan

**ชำนาญ** *(cham-nan)* — Thai for the fluency that only comes from doing something again.

A Claude Code plugin that makes a repository know itself, so an agent stops rediscovering it.
It builds an index the agent reads instead of scanning files, keeps work state that survives
compaction, and accumulates the procedures and tools you keep re-deriving.

## Read this before installing

**chamnan is for one main folder you work in over and over, doing work that repeats.**

Everything it does is amortised. It spends tokens once — building the index, writing down a
procedure, keeping a tool — and collects on every session after that. Both halves of the sentence
above are load-bearing, and they are load-bearing for different reasons:

| | why it matters |
|---|---|
| **One main folder** | The index is built once and read at the start of every session in that repo. Across a hundred sessions it is close to free. On a repo you open once, you paid the whole cost and collected nothing. |
| **Work that repeats** | The procedures and tools fill up from things you hit more than once. If nothing recurs, they stay empty and there is nothing to collect. |

If that describes your day, this was built for you. **If it does not, it will cost you more than
it returns, and you should not install it** — that is not modesty, it is arithmetic. There is no
setting that makes a one-off repo pay off.

A five-second test — if you answer no to either, close this page:

- Will you still be working in this same folder next month?
- Have you explained the same thing about this codebase to Claude more than twice?

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

The same folder, most days, and the same shapes of work coming round again. Concretely:

- **A developer on one codebase for months.** The repo is large enough that you cannot hold it in
  your head, so every session starts with the agent re-learning where things are.
- **A tester re-running the same checks.** The steps are the same each time and they live in your
  head, in a note, or in a script you rewrite.
- **Infra, ops and IT.** Runbooks, deploys, the same six procedures, and a deployment tree the
  agent has to re-read before it can say anything useful about it.
- **A team handing sessions to each other.** What the last session worked out has to survive into
  the next one, and today it does not.

The thread is repetition in one place. That is the only thing chamnan converts into savings.

## Who this is not for

Stated plainly, because installing this on the wrong repo makes your bill worse, not better:

- **You move between many repos and rarely return.** The index is paid for on the session that
  builds it and collected on the sessions after. If there are no sessions after, you only paid.
- **One-off scripts and throwaway prototypes.** Same arithmetic, faster. Genuinely net-negative.
- **Every task is different.** Procedures and tools accumulate from recurrence. Nothing recurs,
  nothing accumulates, and two of the six parts never do anything.
- **Writing, chat, fiction, anything without code.** There is no structure here for it to index.
- **Repos with no comments and no intention of adding any.** The index degrades to filenames,
  which the agent could already see.
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
| `chamnan-peek <file>` | the shape of one file instead of the whole thing — columns, sheets, members, schema, pages |
| `chamnan-peek <file> --find X` | only the parts that match, with line numbers |

### Reading an attachment without reading it

The index says a directory holds twelve thousand documents so that nobody goes looking. `peek` is
the other half: when a task genuinely needs one of them, opening it whole is the wrong move and
skipping it is also the wrong move.

A 3.5 MB CSV is about a million tokens. Its column list, row count and three sample rows are 108,
and for almost every question anyone asks of a CSV that is the answer — 9,455x smaller. A SQLite
file gives up its tables and row counts in 39. `--find` narrows further: the matching rows of a
60,000-row file, with their line numbers, in 240.

Understands CSV/TSV, JSON, ZIP-based formats including .xlsx/.docx/.apk, tar archives, SQLite, PDF
(including text extraction via zlib), PNG/JPEG/GIF headers, and plain text. Formats with no
standard-library reader — Parquet, Avro, ORC — are identified and measured, and say so rather than
guessing. A malformed file reports what went wrong instead of raising.

## Tests

```bash
python3 tests/run_tests.py
```

220 checks, no dependencies. The redaction cases are the reason the file exists: every other part of
this fails visibly — a wrong map entry sends you to the wrong file and you notice — while a
redaction regression fails silently and writes a credential into a file this README tells you to
commit.

Both directions are covered throughout. A redactor that replaces everything would pass any
"did it hide the secret" test perfectly, so the suite also asserts that commit hashes, UUIDs, RFC
numbers and credential-free URLs come through untouched.

Two real bugs were found by writing it: the scratch-repeat threshold was tuned against long scripts
and silently ignored the short repeated ones it exists to catch, and a Google API key one character
outside the expected length slipped the pattern.

The rest came out of hardening it against the polyglot system below, which took the suite from 87
checks to 220.

## The chaos test — what it costs on a real polyglot system

Small repositories flatter an indexing tool. Everything is English, one language, one framework,
comments where you expect them. So chamnan was pointed at a repository built to be hostile: a
cross-border logistics platform of **2,367 files and 34 MB**, written in **30 file types** with
comments in **eight writing systems**, three SQL dialects, gRPC and REST side by side, a full
Kubernetes and Ansible tree, and 1,687 non-source files.

If your repository looks nothing like that, good — this is the upper bound, and it still fits.

### The whole system, in 2,998 tokens per session

| | tokens |
|---|---|
| Every source file in the repository | **11,721,535** |
| The index chamnan writes from them | 50,405 |
| **What actually reaches a session** | **2,998** |

Reading the repository is not an option — it is twelve times a 1M context window. Reading the index
is not necessary either: at session start the agent receives a **2,998-token** roll-up naming every
directory, and greps `MAP.md` for the one entry it needs. That is **0.02% of the source**, and it
is the same number every session, on a repository of any size in this range.

### Where the saving comes from

Each part of the index replaces something the agent would otherwise have to read. All measured on
the corpus above:

| Instead of reading | tokens | chamnan says it in | |
|---|---|---|---|
| 53 migration and model files, to learn the schema | 154,680 | **889** — 94 tables and models, with columns | **174×** |
| 109 Kubernetes, Ansible and Terraform manifests | 170,871 | **1,583** — 74 objects across 27 kinds, 43 Ansible files, 31 images | **108×** |
| 27 env and config files, to learn what it reads | 67,994 | **616** — 64 variable names, values never recorded | **110×** |
| 44 route files, `.proto` and OpenAPI documents | 148,322 | **2,550** — 116 routes, 104 HTTP and 12 gRPC, full paths | **58×** |
| 2,367 files, to learn what lives where | 11,721,535 | **44,282** — one line per file, grep-addressable | **265×** |

And for the things an agent should never load at all:

| Instead of reading | tokens | `chamnan-peek` returns | |
|---|---|---|---|
| A 12,000-row shipment CSV | 418,607 | **204** — columns, row count, three rows | **2,050×** |
| A 9,000-line gateway log | 347,580 | **352** — shape, levels, sample lines | **987×** |
| A 3,000-entry routing JSON | 102,722 | **213** — key structure and depth | **482×** |
| A 20,000-row SQLite database | *cannot be read at all* | **148** — every table, column and row count | — |
| A 2,400-row tariff spreadsheet | *cannot be read at all* | **214** — the rows matching your `--find` | — |

The last two matter differently: a plain read cannot open a database or a spreadsheet, so this is
not a saving over reading them — it is the only way to see inside them without leaving the session.

### Eight writing systems, unbothered

The corpus documents itself in Thai, Devanagari, Cyrillic, Japanese, Korean, Chinese, Arabic and
Latin, each in its own language's documentation convention — javadoc, kdoc, docstrings, rustdoc,
godoc, doxygen, phpdoc, xmldoc, `@moduledoc`. Every summary is carried through to the index intact,
and the token budget is counted per script, because Thai runs about 1.2 characters per token and
Chinese under 1.0 where English code runs 2.5. A budget calibrated on English overruns by three
times on a Thai index; chamnan measures the script it actually has.

Coverage came out at **93%**. The missing 7% are files with no opening comment at all — chamnan
lists them by name so you can fix them, and `/chamnan:bootstrap` offers to write them.

### 92 planted credentials, none of them in the map

Every shape a real codebase leaks a secret was planted deliberately: provider tokens, JWTs, private
keys, credentialed database URLs, `.env` files, Kubernetes Secrets, and secrets sitting in comments
where someone pasted them "temporarily". **92 distinct values across 13 categories, and not one
reached `MAP.md`.** Secrets and SealedSecrets contribute their names so you know they exist, and
nothing under them. `chamnan-peek` refuses key and credential files outright rather than
summarising them.

Nor does it over-redact, which is the failure that would make the index useless: five values that
looked like credentials turned out to be a TypeScript parameter called `refreshTokenValue`, a
Kubernetes Secret's own name, and a Terraform reference whose value is generated at apply time.
Commit hashes, UUIDs and version strings come through untouched.

### Speed

**22 seconds** for the whole 2,367-file scan, single-threaded, standard library only. Re-running
after a change is the same command; on a repository this size it is short enough to put in a git
hook, which `/chamnan:remap` will do for you.

### What this does not claim

The corpus is synthetic. It was written to be hard to index, which is not the same as being like
your repository — so every figure here is reproducible on your own code:

```bash
chamnan-map --measure
```

That number is the one to trust. And chamnan is an amortising tool: it spends once and collects
every session afterwards, so on a four-file repository it costs more than it saves. On 2,367 files
the index is 0.02% of the source. Somewhere between those, it starts paying for itself — which is
why the first section of this README is about whether your repository is the kind that keeps
coming back.

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
