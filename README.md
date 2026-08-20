# chamnan

<img src="docs/assets/chamnan.png" alt="chamnan — an index the agent reads instead of scanning files. On the polyglot test corpus, 11,560,484 tokens of source become a 51,937-token index, of which roughly 3,000 reach each session." width="100%">

<sub>The figures above are a summary. Every one of them, and how it was measured, is in
[Evidence](#evidence) and [The chaos test](#the-chaos-test) below — read those rather than the
picture if a number matters to you.</sub>

**ชำนาญ** *(cham-nan)* — Thai for the fluency that only comes from doing something again.

A Claude Code plugin that makes a repository know itself **and preserve the engineering context
built while you work with it**, so an agent stops rediscovering both. It builds an index the agent
reads instead of scanning files, keeps the work state and the decisions that would otherwise be
lost between sessions, and accumulates the procedures and tools you keep re-deriving.

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

## The real problem: agents forget

An agent working in your repository keeps arriving at the same conclusions, because everything it
worked out last time is gone:

- **a new session starts with nothing.** It has your files and no idea which ones matter.
- **a long session compacts.** Whatever it had figured out about the codebase goes with it.
- **the reasoning disappears.** Why a fix took the shape it did, what was ruled out and why —
  none of that is in the diff.
- **the repository does not explain its own experience.** Code says what. Git says when. Neither
  says why, or what has already been tried.

So the same four questions get answered from scratch, over and over: *where does this live · why
was it built this way · how did we solve this before · what happened last session.*

### The core idea

chamnan turns what gets discovered during the work into **repository-local artifacts** — plain
markdown, committed beside the code:

| | |
|---|---|
| `MAP.md` | what exists, and what depends on what |
| `STATE.md` | what is being worked on right now |
| `sessions/` | where the last stretch of work stopped |
| `memory/` | decisions, lessons and standing rules |
| `skills/` · `tools/` | procedures and scripts worth keeping |
| `milestones.md` | the changes that reshaped the repository |

**The agent does not learn.** Nothing is trained, nothing persists outside the directory, and the
next session still starts from zero — it just starts from zero *in a repository that explains
itself*. The continuity is in the artifacts, not in the model.

### Two kinds of cost

| | what it is | what answers it |
|---|---|---|
| **Discovery cost** | finding where code lives and how it connects | `MAP.md`, the Impact section |
| **Re-solving cost** | working out again what was already worked out | procedures, tools, memory, decisions, session records |

**Token reduction is the consequence, not the aim.** An agent that already knows where the payment
logic lives does not grep for it; one that can read why the retry was written that way does not
re-derive it. Fewer tokens is what less repeated work looks like on a bill.

That said, the arithmetic is worth seeing, because it is the reason this approach targets reading
rather than writing. Measured on one developer's 34 days of real Claude Code usage:

| | share of cost |
|---|---|
| context read in | **91.2%** |
| output written | 8.8% |

The most popular output-compression plugin advertises 65% savings; [JetBrains benchmarked it across
86 tasks](https://blog.jetbrains.com/ai/2026/07/speak-to-ai-agents-like-cavemen-tosave-tokens/) and
measured 8.5% of output tokens — roughly 0.7% of a bill, with no loss of quality. It does what it
says; it is just aimed at the smaller half.

## The compounding effect

chamnan spends once and collects on every session afterwards, so what it is worth depends on how
long you stay:

| | what the repository holds |
|---|---|
| **Day 1** | `MAP.md` — the agent stops scanning the tree |
| **Day 30** | `+ STATE.md`, session records, the first procedures and tools |
| **Day 180** | `+ decisions`, `+ lessons`, `+ rules`, `+ milestones`, and the workflows that turned out to repeat |

Nothing here is automatic accumulation of everything that happens. Each artifact is written
deliberately, by you or by Claude at your request, because it was worth keeping. What grows is
**repository-specific knowledge**, and it grows because you keep coming back to the same code.

The same arithmetic cuts the other way, and it is the reason the first section of this README is
about whether your repository is the kind that keeps coming back: **on a four-file repository this
costs more than it saves.** There is nothing to amortise.

## What it does

Four capabilities. Everything listed is shipped and running today.

### Understand — what exists, and what is connected to it

| | |
|---|---|
| **Index** | `MAP.md` — one line per file, generated from the code. The agent reads the index; it greps the detail; it stops reading the tree. |
| **Impact** | Who depends on a file, and which tests cover it. A file's own imports are already at the top of that file; the reverse edge is what costs a search. Grep it for one path before changing it. |
| **Data model** | Table and model names with a one-line summary, pulled from DDL, migrations and ORM models — instead of a schema dump. Only appears if the repo defines one. |
| **API surface** | Method, path and handler, from route decorators, OpenAPI documents and `.proto` service definitions — instead of the whole spec. |
| **Configuration** | The environment variable names the repo reads. **Names only, never values** — and it warns if `.env` is not gitignored. |
| **Deployment** | What actually runs, read from Kubernetes, Ansible, Compose, Helm and CI manifests: kinds and names, images, roles, pipelines. A Secret contributes its name and nothing under it. |
| **Stored material** | The non-source trees — scanned paperwork, exports, archives — as counts, sizes and dominant extensions. It exists to stop an agent going to look, which costs far more than the section does. Never opened, never read. |

### Remember — what was being done, and why

| | |
|---|---|
| **State** | `STATE.md` — what is being worked on right now, injected at session start so compaction stops erasing it. |
| **Resume** | One record per session under `.chamnan/sessions/`. Only what was *unfinished* reaches the next session; a session that finished cleanly injects nothing at all. |
| **Memory** | `decisions/`, `lessons/`, `rules/`. Rules are standing constraints, so they go in front of the agent every session; decisions and lessons contribute a title and are read when the title looks relevant. |

### Reuse — what has already been solved

| | |
|---|---|
| **Procedures** | Skills the agent writes *itself* when it hits something complex or repeated. Not a shipped library — a mechanism. |
| **Tools** | Notices when the same scratch script is written a third time, and offers to keep it. |
| **Workflows** | Notices when the same commands run in the same order on a third separate day, and offers to write the sequence down. |

### Evolve — what the repository has learned about itself

| | |
|---|---|
| **Milestones** | The handful of changes that reshaped the repository: what moved, why it was worth doing, which areas it touched. |

Repeated engineering work becoming reusable repository knowledge — **not model training, and not
automation of the developer.** It is a mechanism for preserving work that would otherwise only
exist in whoever did it.

### Supporting

| | |
|---|---|
| **Measurement** | Reports context-per-turn for your repo, before and after. Your number, not ours. |
| **Routing** | Its own agents run on a cheap model, because "read this file, write one line" does not need an expensive one. |

Every part can be switched off independently in `.chamnan/config.json`. They do not depend on each
other, and they do not have equal evidence behind them — see below.

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
- **Anyone who wants the agent to accumulate context about their project** — weeks or months on the
  same system, repeatedly extending it, tired of explaining the same things.

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

## Requirements

| | |
|---|---|
| **Claude Code with plugin support** | Required. chamnan is a plugin, and it uses four hook events: `SessionStart`, `PreToolUse`, `PostToolUse`, `SessionEnd`. No minimum Claude Code version is declared in `plugin.json`; if your build supports `claude plugin install` and those events, it will run. |
| **Python 3.8 or newer** | Required, and it must be on `PATH` as `python3`. The hooks are launched by path, relying on their `#!/usr/bin/env python3` line and executable bit. 3.8 is the floor because the assignment expression (`:=`) is the newest syntax used; nothing later appears anywhere in the plugin. |
| **Third-party packages** | None. Standard library only — `ast`, `pathlib`, `re`, `json`, `csv`, `sqlite3`, `zipfile`, `tarfile`, `zlib`, `struct`, `subprocess`. Nothing to install, nothing to keep updated, and no virtualenv. |
| **Git** | Not required. The plugin never invokes the `git` binary. The one exception is opt-in: `chamnan-map --install-git-hook` needs a `.git` directory to write into, and the hook it writes is a `/bin/sh` script that calls `git diff` and `git add`. |
| **Disk** | Whatever `.chamnan/` holds — an index, a state file, a config file, and logs pruned on a retention window. Nothing outside the repository. |

### Platforms

| | |
|---|---|
| **macOS** | **Supported and tested.** Developed and exercised on macOS (arm64) with Python 3.12; the test suite and the polyglot run below were both done there. |
| **Linux** | **Expected to work, not tested.** Same launch path as macOS — POSIX shebang, executable bit, standard library only — and nothing in the code is platform-specific. If you hit a problem there, it is a bug worth reporting rather than an expected gap. |
| **Windows** | **Not tested, and not expected to work as-is.** The hooks are invoked as bare paths to `.py` files, which depends on the `#!/usr/bin/env python3` line and the executable bit; Windows honours neither. The optional Git hook is a `/bin/sh` script. Under WSL it is the Linux row above. |

## Quick start

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

Then open Claude Code in a repository you actually work in, and run it once:

```
/chamnan:bootstrap
```

That is the whole setup. What happens next, in order:

| | |
|---|---|
| 1 | **Builds the index.** Scans the repository and writes `.chamnan/MAP.md` — one line per file, plus a section for the data model, API surface, configuration, deployment and stored files, each written only if the repo actually has one. |
| 2 | **Measures how well the code describes itself.** If fewer than 70% of files have an opening comment, it *offers* to fill them in and waits for you to say yes — see [Bootstrap does not rewrite your code](#bootstrap-does-not-rewrite-your-code). |
| 3 | **Records a baseline** with `chamnan-report`. On a fresh repository there is no history yet and it says so. |
| 4 | **Writes the first `.chamnan/STATE.md`** — a short note on what you are working on right now. |
| 5 | **Offers the optional Git hook** that refreshes the index on commit. Opt-in, and it never overwrites a hook you already have. |

Afterwards, every session in that repository starts with the index and the state file already in
context. You do not run anything again until the shape of the repo changes, and then it is
`/chamnan:remap`.

### What it creates

Everything lives in one directory at the repository root, and nothing outside it is touched:

```
.chamnan/
├── MAP.md          the architecture index          (written by chamnan-map)
├── STATE.md        what you are working on         (written by Claude, at milestones)
├── milestones.md   changes that reshaped the repo  (written by /chamnan:milestone)
├── config.json     which parts are on              (written on first run, merged on upgrade)
├── sessions/       where each session stopped      (written by /chamnan:resume)
├── memory/
│   ├── decisions/  a choice, and why               (written by /chamnan:remember)
│   ├── lessons/    something that cost time once
│   └── rules/      standing constraints — injected every session
├── skills/         procedures you chose to keep     (starts empty)
├── tools/          scratch scripts you kept         (starts empty)
└── logs/           bounded by log_retention_days    (starts empty)
```

`MAP.md`, `config.json` and every directory appear the moment the index is first built. The rest
are written when you ask for them: `STATE.md` during bootstrap, the others by their skills. The
session-start hook skips whatever is absent, so a repository that only ever builds an index stays
exactly that simple.

Add `.chamnan/logs/` to `.gitignore` if you would rather not carry it. Everything else is worth
committing — that is how the next person, and the next session, gets it.

### Trying it without installing

From the parent directory of a clone:

```bash
git clone https://github.com/ArcticFox2029/chamnan
claude --plugin-dir ./chamnan
```

The plugin is active for that session only, and nothing is written until you run
`/chamnan:bootstrap` or `chamnan-map`.

## What's new in 1.3

Six additions, all repository-local markdown, all bounded at the injection rather than in the
store. Measured with every one of them populated: **507 tokens** reach a session.

### Better Resume Work

One record per session under `.chamnan/sessions/`, written by `/chamnan:resume`. Only
**`Remaining` and `Blockers`** reach the next session — `Done` is history and the file list is
recoverable from git. A session that finished cleanly injects nothing at all, because an empty
record is worse than none.

It does not replace `STATE.md`. `STATE.md` is one overwritten file about the present; a session
record is one of many about a particular stretch of work.

### Smart Session Memory

`.chamnan/memory/` with three categories, used three different ways:

| | | reaches a session as |
|---|---|---|
| `rules/` | a standing constraint | **the full text**, capped |
| `decisions/` | a choice, and why | its title |
| `lessons/` | something that cost time once | its title |

Titles cost a line each and buy the ability to load the right file; injecting the bodies would cost
everything and buy nothing extra. **Not pruned by age** — a session record stops mattering, a
decision does not, and a timer would delete the oldest entries, which are the ones nobody can
reconstruct.

### Impact Map

Who depends on a file, and which tests cover it — in `MAP.md`, **below the Full Detail marker**, so
it is grepped when you are about to change one path and never injected into sessions that will not
touch it.

    - **`payment/service.py`** — used by `checkout/api.py`; **tested by** `tests/test_payment.py`

One hop, capped. No transitive closure, no cycle analysis, no database. Imports are collected while
the scanner already has each file open, so it adds no second read: measured at **0.673 s across 529
files**, 9.5% of scan time.

### Better Capture

The existing hint noticed the same *script* written a third time. This notices the same **commands,
in the same order, on a third separate day** — the deployment check or debugging routine that
leaves no file behind at all.

Four guards keep it quiet: arguments and paths are discarded so the same routine matches across
branches; 33 commands too common to mean anything are ignored; three distinct steps minimum; three
distinct days, so repeating something three times in one sitting counts once. It speaks once, and
never in the same turn as the script hint.

### Project Milestones

`.chamnan/milestones.md` — the handful of changes that reshaped the repository, with **why** it was
worth doing and **which areas moved together**. A git log rarely says the first and never says the
second.

Not project management: no status, no owner, no due date. Only the two most recent titles are
injected, so forty milestones cost the same per session as two.

### Better Language Support

Prioritised by measuring symbols per thousand lines across a 529-file polyglot corpus, then
inspecting each low number before touching anything:

| | before | after | |
|---|---|---|---|
| PHP | 82 symbols | **163** | the rule matched only a bare `function`, so 66 of 139 declarations were invisible |
| Rust | 66 | **150** | only an optional `pub` was allowed, missing every `async fn` |
| TypeScript / JS | 173 | **191** | class methods are indented; every rule was anchored at `^` |
| shell | 14 | **14** | **left alone** — its scripts are commands, not functions, so the low number is honest |

`MIN_YIELD` now asserts a minimum symbol count for twelve languages against ordinary-code fixtures,
so *a language partially understood beats one falsely claiming full support* is a test rather than
a slogan.


## Bootstrap does not rewrite your code

Worth being precise about, because an indexing tool that quietly edits your files is not one you
would install. There are three categories, and only the middle one touches source.

### Read-only

Scanning is a read. `chamnan-map` opens each source file, takes its opening comment and its
top-level symbols, and writes nothing back. `chamnan-peek` reads the shape of one file on request.
`chamnan-report` reads its own logs. None of these modify anything they read, and none of them can:
they never open a source file for writing.

### Written automatically — all of it inside `.chamnan/`

| | when |
|---|---|
| `.chamnan/` and `skills/`, `tools/`, `logs/` | created on the first index run |
| `.chamnan/config.json` | written on the first run; on a later upgrade it is **merged** — keys you set are kept, keys the plugin no longer has are dropped |
| `.chamnan/MAP.md` | rewritten on every index run |
| `.chamnan/logs/` contents | pruned on every command, per `log_retention_days` |

Nothing outside `.chamnan/` is written without you asking. There is one opt-in exception, below.

### Optional, and only after you say yes

If fewer than 70% of files have an opening comment, `/chamnan:bootstrap` says so and offers to fix
it. The offer is a question, not a step it takes:

> Never edit files for this without asking first. It touches every undocumented file in the repo.
> — `skills/bootstrap/SKILL.md`

Given a yes, it dispatches the `commenter` agent, which is deliberately narrow:

| | |
|---|---|
| Tools | `Read`, `Edit`, `Glob` — and nothing else. No shell, no `Write`, no ability to create or delete a file |
| Model | `haiku` — "read this file, write one line about it" does not need an expensive model |
| Scope | only the specific files it is handed, never the whole repo |
| Rule | one line at the top of files that **have no opening comment**; a file that already has one is left exactly as it was, and code is never changed |

Two honest caveats. The tools list is a hard boundary enforced outside the agent — it genuinely
cannot run a command or delete a file. The "one line, never touch existing comments, never change
code" rules are instructions to a model, and a model following instructions is not the same thing
as a guarantee: review the diff, as you would for any change you did not type. It is one line per
file, so the diff is easy to read.

Prefer it never asks? Set `"agents": false` in `.chamnan/config.json`. chamnan then lists the files
missing a comment and leaves them to you.

### The one write outside `.chamnan/`

`chamnan-map --install-git-hook` writes `.git/hooks/pre-commit`. Opt-in, never automatic, and it
does not clobber a hook you already have — it appends a block marked `# >>> chamnan`, which is also
how you remove it.

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

## Keeping the index fresh

A stale index is worse than no index: it is confidently wrong, and the next session believes it. So
rebuild it whenever the shape of the repo changes — `/chamnan:remap` — or stop having to remember:

```bash
chamnan-map --install-git-hook
```

That refreshes the index on any commit touching tracked files, and never fails a commit if chamnan
errors. It is opt-in, it appends to an existing hook rather than replacing it, and
[Update, disable, uninstall](#update-disable-uninstall) covers taking it back out.

## Bulk reads

Before a `Read` pulls in a lock file, a minified bundle, or a very large file, chamnan says so and
suggests grep. It **never blocks**: the one time someone genuinely needs to read `package-lock.json`
is the one time refusing would be most wrong. Turn it off with `warn_on_bulk_reads: false`.

It does not strip comments or blank lines from files on the way in — partly because hooks cannot,
and partly because comments are the highest-value tokens in a file for a reader trying to understand
intent. This plugin's entire index is built out of them.

## Configuration

Everything lives in `.chamnan/config.json`, written on the first index run with these defaults.
Every value below was read from `lib/workspace.py`, which is the only place defaults are defined.

| Option | Default | Valid values | What it controls |
|---|---|---|---|
| `map` | `true` | `true` / `false` | The architecture index — generating it, and injecting its Quick Index at session start. The part with the strongest evidence behind it. |
| `state` | `true` | `true` / `false` | Injecting `.chamnan/STATE.md` at session start, which is what survives compaction. |
| `capture` | `true` | `true` / `false` | Listing the procedures recorded in `.chamnan/skills/` at session start, by name and description, so the agent can load one on demand. |
| `promote` | `true` | `true` / `false` | Noticing a scratch script written for the third time, offering to keep it in `.chamnan/tools/`, and listing kept tools at session start. |
| `report` | `true` | `true` / `false` | The `chamnan-report` before/after measurement. |
| `agents` | `true` | `true` / `false` | Whether chamnan may dispatch its own cheap-model agents. With `false`, low coverage is reported and the files are left to you. |
| `log_retention_days` | `7` | integer, days | Files under `.chamnan/logs/` older than this are deleted on every command. Best-effort and silent — housekeeping never fails a command you asked for. |
| `language` | `"en"` | any language, e.g. `"th"` | The language chamnan **writes in** when it generates file comments and records procedures. It never rewrites anything already written, and it never affects the language of replies to you. |
| `index_token_budget` | `3000` | integer, tokens | Ceiling on the part of `MAP.md` injected every session. Over budget, the index is rolled up by directory rather than truncated, so nothing disappears silently. |
| `warn_on_bulk_reads` | `true` | `true` / `false` | A notice before a read pulls in a lock file, a minified bundle or a very large file. A notice, never a block. |
| `reply_style` | `"off"` | `"off"` / `"concise"` / `"terse"` | Injects a per-repo instruction on how answers should be written. `off` injects nothing; `concise` drops preamble, restatement and closing offers while keeping full sentences; `terse` adds fragments and tables over prose. An unrecognised value injects nothing. |
| `resume` | `true` | `true` / `false` | Session records under `.chamnan/sessions/`, and injecting the unfinished part of the most recent one. |
| `session_retention_days` | `30` | integer, days | Session records older than this are deleted on the next `chamnan-map` or `chamnan-report`. Longer than the log window, because a record from three weeks ago is still the answer to "what was I doing". |
| `memory` | `true` | `true` / `false` | `.chamnan/memory/`. Rules are injected in full; decisions and lessons contribute a title and are read on demand. **Not pruned by age** — a session record stops mattering, a decision does not. |
| `milestones` | `true` | `true` / `false` | `.chamnan/milestones.md`. Only the two most recent titles are injected, so the file's length costs nothing per session. |

Each part is independent — switching one off does not affect the others.

You rarely need to edit the file by hand. "Use Thai for the comments in this repo" or "keep answers
terse here" is enough, and Claude edits it for you.

### On upgrade

`config.json` is **merged**, not replaced: keys you set are kept, and keys the plugin no longer has
are dropped. So an option that disappears after an upgrade was removed from the plugin — it is not
a lost setting.

## Commands

In Claude Code:

| | |
|---|---|
| `/chamnan:bootstrap` | first-time setup: index, coverage, fill comments, baseline. Once per repo |
| `/chamnan:remap` | rebuild the index after the repo's shape changed |
| `/chamnan:capture` | record a procedure worth keeping |
| `/chamnan:promote` | keep a scratch script as a tool |
| `/chamnan:resume` | write down where this session stopped, so the next one continues |
| `/chamnan:remember` | record why something is the way it is — a decision, a lesson, a rule |
| `/chamnan:milestone` | record a change that reshaped the repository |
| `/chamnan:report` | show context-per-turn, before and after |

From a shell, in the repository:

| | |
|---|---|
| `chamnan-map` | rebuild `.chamnan/MAP.md`, and report how it landed: source tokens, Quick Index size, Full Detail size, comment coverage, and whether the index is inside `index_token_budget` |
| `chamnan-map --preview` | print **exactly** what a session in this repo receives at start-up, followed by its token count. Nothing is written |
| `chamnan-map --install-git-hook` | opt-in: refresh the index on commit. Appends to an existing `pre-commit` hook rather than replacing it |
| `chamnan-peek <file>` | the shape of one file instead of the whole thing — columns, sheets, members, schema, pages |
| `chamnan-peek <file> --find PATTERN` | only the parts that match, with their line numbers |
| `chamnan-peek <file> --budget 800` | raise the output ceiling from its default of 400 tokens |
| `chamnan-promote <file> <name> --desc "…"` | install a scratch script as a permanent tool in `.chamnan/tools/` |
| `chamnan-promote --list` | what this repo already keeps |
| `chamnan-report` | weekly context-per-turn. On a repo with no Claude Code history it says so instead of inventing a trend |

### Reading an attachment without reading it

The index says a directory holds twelve thousand documents so that nobody goes looking. `peek` is
the other half: when a task genuinely needs one of them, opening it whole is the wrong move and
skipping it is also the wrong move.

Measured on the corpus below: a 12,000-row shipment CSV is 418,607 tokens read whole and **204**
read as a shape — its columns, its row count and three sample rows, which is the answer to almost
every question anyone asks of a CSV. A 20,000-row SQLite database gives up every table, column and
row count in **148**, and a plain read cannot open it at all. `--find` narrows further: the matching
rows of a 2,400-row spreadsheet, and nothing else, in **214**.

Understands CSV/TSV, JSON, ZIP-based formats including .xlsx/.docx/.apk, tar archives, SQLite, PDF
(including text extraction via zlib), PNG/JPEG/GIF headers, and plain text. Formats with no
standard-library reader — Parquet, Avro, ORC — are identified and measured, and say so rather than
guessing. A malformed file reports what went wrong instead of raising.

## Secrets

`MAP.md` is built by copying source comments, and this README suggests committing it. That
combination is a way to publish a password, so it is handled rather than assumed away.

- **Some files the scanner never opens.** `.pem`, `.key`, `.pfx`, `.p12`, `.crt`, `.cer`, `.jks`,
  `id_rsa*`, `.htpasswd`, `.netrc`, `*.db`, `*.sqlite`, `*.bak`, `*.dump` and similar are skipped
  outright while building the index. `.gitignore` is not relied on: it is often absent, often
  wrong, and the cost of being wrong is somebody's private key.
- **`chamnan-peek` has its own, narrower refusal list**, because the two are answering different
  questions. The scanner indexes source and has no business opening a database; `peek` is handed
  one file by name, and a database's table and column names are exactly the useful answer — so
  peek shows a schema and never a row. What peek refuses outright is the set whose *contents are*
  the secret: keys, certificates, `.asc`/`.gpg`, and files named `credentials*`, `secrets.yml`,
  `.netrc`, `id_rsa*`. It names the file, says no, and reads nothing.
- **Everything chamnan emits passes a redactor** — both what it writes into `MAP.md` and what
  `peek` prints into a session. One choke point on the finished output rather than one per
  extractor, so a section added later cannot bypass it. Provider tokens (`sk-`, `ghp_`, `AKIA…`,
  `AIza…`, `xox…`, Stripe, GitLab, npm, JWTs), private-key blocks, credentialed URLs, and
  `password = …` assignments — quoted or bare, because no `.env` on earth quotes them — become
  `<REDACTED>`.
- **Environment variable values are never captured in the first place.** The patterns that find
  them match the name and stop at the `=`; a value is not in any capture group, so there is no code
  path that could carry one into the output even by mistake. `.env` files still contribute their
  *names*, because which variables a service reads is exactly what an index should say — and if one
  is not covered by `.gitignore`, chamnan says so in the map.

Verified with a repository seeded with a live-looking Stripe key, a `postgres://user:pass@host` in a
comment, and an RSA private key — none reached `MAP.md`, while
`postgres://admin:<REDACTED>@db.internal:5432/main` stayed readable, because *which database on
which host* is exactly what an index should tell you.

The redaction patterns are narrow on purpose. Redacting everything high-entropy would eat commit
hashes, UUIDs and version strings, and a map full of `<REDACTED>` is not a map.

### What this is not

**chamnan is not a sandbox, and this is not defence in depth for your session.** It defends the one
thing it controls: its own output. A plugin hook cannot rewrite what the `Read` tool returns —
`PostToolUse` exposes only `additionalContext` and `systemMessage` — so no plugin can filter what
Claude reads from your disk. If you ask Claude to open `.env`, it opens `.env`, and chamnan is not
in that path. Anything claiming otherwise is describing a capability Claude Code does not have.

Two more limits worth stating plainly:

- The patterns are **narrow by design**, and narrow means some things get through. A credential in a
  shape nobody has seen before, or a bare high-entropy string with no assignment around it, will not
  match. Widening until nothing escapes would replace commit hashes, UUIDs and version strings too,
  and an index full of `<REDACTED>` is not an index. That trade is chosen deliberately, not
  overlooked.
- **Review `MAP.md` before its first commit**, the same way you would review any generated file you
  are about to publish. On the polyglot corpus below, 92 planted credentials across 13 categories
  produced no values in the map — good evidence, and still not a proof about your repository.

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

## The chaos test

Small repositories flatter an indexing tool. Everything is English, one language, one framework,
comments where you expect them. So before asking anyone to install this, chamnan was pointed at a
repository built to be as hard to index as a real system gets.

**The test subject:** a cross-border logistics platform — IoT firmware on containers, edge
gateways, fourteen backend services, five mobile apps, a web console, an analytics pipeline, and
the infrastructure to deploy all of it.

| | |
|---|---|
| Files | **2,365** · 34 MB |
| Programming languages | **31 file types** — C, C++, Arduino, C#, Go, Rust, Zig, Nim, Java, Kotlin, Scala, Swift, Objective-C, Dart, Python, Ruby, PHP, Elixir, Lua, TypeScript, TSX, JavaScript, JSX, shell, Terraform, Protobuf, GraphQL |
| Comment languages | **8 writing systems** — Latin, Thai, Devanagari, Cyrillic, CJK, Hangul, Arabic, Hiragana |
| Databases | Three SQL dialects (Postgres, MySQL, SQLite) plus SQLAlchemy models and Android Room entities |
| API contracts | Protobuf/gRPC, GraphQL, OpenAPI |
| Infrastructure | Kubernetes, Ansible, Helm, Docker Compose, Terraform, CI pipelines |
| Planted credentials | **92**, in every shape a real codebase leaks them |
| Non-source files | **1,672** — PDFs, spreadsheets, archives, images, logs, a SQLite database |

Nothing in it is a placeholder. Every service cross-references the others by real name against a
written spec, and one corner is deliberately careless code with no comments at all — because real
repositories have one of those too.

**How to read the numbers below.** Counts of files, languages, tables, routes, Kubernetes objects
and credentials are **observed** — they are what chamnan reported when run against the corpus, and
they can be reproduced by anyone holding it. Token figures are **estimates**, produced by chamnan's
own script-aware estimator rather than by an exact API count; the estimator is calibrated against
measured API usage and errs toward over-counting, but a figure like 11,560,484 is an estimate of a
size, not a receipt. And all of it is a **synthetic-corpus result**: the corpus was built to be hard
to index, on one machine, and is not part of this repository. It is evidence that the tool holds up
under load, not a benchmark of your codebase. `chamnan-map` gives you that one.

### What it covered

| | |
|---|---|
| **529 files indexed** across all 31 file types | Each parsed with its own idioms — `fun` and `suspend fun` in Kotlin, `data class`, extension functions, Elixir's `defmodule`, Rust's `impl`, C prototypes in headers, Terraform resources |
| **3,266 symbols extracted** | Functions, classes, structs, traits, protocols, objects, constants |
| **98% described** | 517 of 529 files carry a one-line summary in the index. The remaining 12 genuinely have no opening comment — chamnan lists them by name so you can add one |
| **8 writing systems intact** | Summaries carried through from javadoc, kdoc, docstrings, rustdoc, godoc, doxygen, phpdoc, xmldoc and `@moduledoc` without mangling, and the token budget is counted per script because Thai runs ~1.2 characters per token where English code runs 2.5 |

### What it found in the system

Pointed at the repository once, chamnan produced — with no configuration beyond
`/chamnan:bootstrap`:

| | |
|---|---|
| **94 tables and models** | Across all three SQL dialects plus both ORMs, with columns, and indexed under their real table names rather than their class names. Partitioned tables say so; the eight regional partitions and two swap-staging tables are correctly not listed as separate schema |
| **116 API routes** | 104 HTTP — resolved to their full paths from FastAPI, Flask and Spring prefixes and from five OpenAPI documents — and **12 gRPC methods** read straight out of `.proto` service definitions |
| **74 Kubernetes objects across 27 kinds** | Plus 43 Ansible files, 24 Compose services, 31 container images, 21 CI pipelines, and a Helm chart |
| **64 environment variable names** | Names only, values never recorded — and a warning that one `.env` was not covered by `.gitignore` |
| **1,672 stored files, described not read** | Counts, sizes and dominant extensions per directory, so the agent knows the tree exists and does not go exploring it |

### What it saves

Reading the repository is not an option — at 11.7 million tokens it is twelve times a 1M context
window. So the question is what reaches a session instead.

| | tokens |
|---|---|
| Every source file | **11,560,484** |
| The index chamnan writes | 51,937 |
| **What reaches each session** | **~3,000** |

That last number is the one that matters, and it is roughly constant. Each part of it replaces
something an agent would otherwise have to go and read:

| Instead of reading | tokens | chamnan says it in | |
|---|---|---|---|
| 53 migration and model files, to learn the schema | 154,680 | **889** | **174×** |
| 109 Kubernetes, Ansible and Terraform manifests | 170,871 | **1,583** | **108×** |
| 27 env and config files | 67,994 | **616** | **110×** |
| 44 route files, `.proto` and OpenAPI documents | 148,322 | **2,550** | **58×** |
| 2,365 files, to learn what lives where | 11,560,484 | **51,937** | **223×** |

And for the files that should never be loaded at all, `chamnan-peek` reads their shape on demand:

| Instead of reading | tokens | peek returns | |
|---|---|---|---|
| A 12,000-row shipment CSV | 418,607 | **204** — columns, row count, sample rows | **2,050×** |
| A 9,000-line gateway log | 347,580 | **352** — shape, levels, sample lines | **987×** |
| A 3,000-entry routing JSON | 102,722 | **213** — key structure and depth | **482×** |
| A 20,000-row SQLite database | *a plain read cannot open it* | **148** — every table, column and row count | |
| A 2,400-row tariff spreadsheet | *a plain read cannot open it* | **214** — only the rows matching `--find` | |

Whole scan: **22 seconds**, single-threaded, standard library only.

### What it protects

92 credential-shaped values were planted deliberately — provider tokens, JWTs, private keys,
credentialed database URLs, `.env` files, Kubernetes Secrets, and secrets pasted into comments.

**None of them reached `MAP.md`.** Secrets and SealedSecrets contribute their names so you know
they exist and nothing underneath. `chamnan-peek` refuses key and credential files outright instead
of summarising them, and redacts values while keeping variable *names*, because which variables a
service reads is exactly what an index should say.

It also does not over-redact, which is the failure that would quietly make the index useless: the
six values that look like credentials in the finished index are all identifiers — a TypeScript
parameter named `refreshTokenValue`, a Kotlin function called `buildProperty`, a Kubernetes Secret's
own name, and a Terraform reference whose value is generated at apply time. Commit hashes, UUIDs and
version strings come through untouched.

### What this does not claim

The corpus is synthetic. It was built to be hard to index, which is not the same as being like your
repository — so every figure above is reproducible on your own code, and that is the number to
trust:

```bash
chamnan-map
```

chamnan is an amortising tool: it spends once and collects on every session afterwards. On a
four-file repository it costs more than it saves. On 2,365 files the index is 0.4% of the source.
Which side of that your repository sits on is the whole question, and it is the first section of
this README.

## Troubleshooting

**Start here.** `chamnan-map --preview` runs the session-start hook and prints its output verbatim,
so "is anything being injected, and how much" stops being a guess:

```bash
chamnan-map --preview
```

| Symptom | What it means | What to do |
|---|---|---|
| `/chamnan:bootstrap` is not offered | The plugin is not loaded in this session | `claude plugin list` — if chamnan is absent, install it again; if it is present but disabled, enable it. A newly installed plugin is picked up by a **new** session, not the running one |
| Nothing appears at session start | Either no index yet, or the hook is not running | Run `chamnan-map --preview`. If it prints `nothing to inject yet — run chamnan-map first`, build the index with `chamnan-map`. If it prints the index but sessions still get nothing, the plugin is not loaded — see the row above |
| `python3: command not found` | The hooks are launched by their `#!/usr/bin/env python3` line | `python3 -V` — 3.8 or newer, on `PATH`. There are no packages to install |
| Hooks never fire on macOS or Linux | The hook files need their executable bit and their shebang intact | `ls -l` the four files in `hooks/`; each should be executable and start with `#!/usr/bin/env python3` |
| Hooks never fire on Windows | Not supported — the launch path relies on a shebang and an executable bit that Windows does not honour | Use WSL |
| `no recognised source files under …` | Nothing under that path has an extension chamnan indexes | Check you are at the repository root, not beside it |
| The index is mostly filenames | Files have no opening comment, so there is nothing to summarise them with | `chamnan-map` names the files that are missing one. Ask Claude to add them, or write them yourself — with `"agents": false` chamnan will only ever list them |
| The index describes files that moved or vanished | It is a snapshot, and the repo has changed since | `/chamnan:remap`, or `chamnan-map`. To stop having to remember: `chamnan-map --install-git-hook` |
| `Over the … token budget` | The Quick Index is larger than `index_token_budget` | Nothing is silently dropped — it is rolled up by directory, and every directory stays named. Raise `index_token_budget`, or index less: `chamnan-map <dir> [<dir> …]` |
| `not a git repository — nothing to install into` | `--install-git-hook` found no `.git` directory | Run it from inside the repository. If it genuinely is not a git repo, skip the hook and use `/chamnan:remap` |
| A flag appears to do nothing | `chamnan-map` looks for its flags in the argument list rather than parsing them strictly, so a misspelt one is ignored in silence | Check the spelling against [Commands](#commands) |
| A workspace file looks wrong | Any of it can be rebuilt | `MAP.md` from `chamnan-map`; `config.json` reappears with defaults if deleted; `STATE.md` is yours to edit by hand |

## Update, disable, uninstall

The plugin-manager commands below belong to Claude Code, not to chamnan. They were run against
`claude plugin --help` in the environment this README was written in; if your build differs,
`claude plugin --help` is the authority.

### Updating

```bash
claude plugin update chamnan@chamnan
```

Claude Code applies it on restart, not in the running session — its own help says so.

Your `.chamnan/config.json` is **merged**, not replaced. Verified: a file holding only
`{"reply_style": "terse", "index_token_budget": 9000}` came back with both values intact and the
remaining nine defaults filled in. Options the plugin has dropped are removed, so a setting that
disappears after an update was retired rather than lost. `MAP.md` is untouched until you next run
`chamnan-map`.

### Turning individual parts off

Per repository, in `.chamnan/config.json` — every key is in [Configuration](#configuration).
Switching one off does not affect the others. "Stop injecting the state file in this repo" is enough
said out loud; Claude edits the file for you.

### Stopping in one repository

Either set the keys to `false`, or delete the workspace:

```bash
rm -rf .chamnan
```

That is safe and reversible: the next `chamnan-map` recreates the directory, the three
subdirectories and a default `config.json`, and rebuilds `MAP.md` from the code. The one thing that
does not come back is `STATE.md` — it is written by hand, so copy it first if it holds anything you
want.

### Switching it off everywhere without uninstalling

```bash
claude plugin disable chamnan@chamnan
claude plugin enable  chamnan@chamnan
```

### Uninstalling

```bash
claude plugin uninstall chamnan@chamnan
claude plugin marketplace remove chamnan     # optional, if you added it only for this
```

chamnan never writes outside the repository it is working in, so there is nothing to clean up
elsewhere. Any `.chamnan/` directories stay where they are until you delete them — which is
deliberate: `MAP.md` and `STATE.md` are useful to whoever opens the repo next, plugin or no plugin.

### Removing the Git hook

The hook is a block appended to `.git/hooks/pre-commit`, fenced by markers:

```sh
# >>> chamnan
…
# <<< chamnan
```

Delete those lines and everything between them. If chamnan created the file itself — it did if the
file contains nothing else besides `#!/bin/sh` — deleting the whole file is equivalent.

## What it deliberately does not do

- **No shipped skill library.** Someone else's procedures do not match your repo. This ships the
  mechanism that writes yours.
- **No output-style compression.** That lane is taken, and it is aimed at the 8.8%.
- **No large CLAUDE.md.** A plugin about context cost must not become one. The session-start
  injection is bounded and reports when it is truncated.
- **No claimed percentage on your bill.** It measures yours instead.

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

## Tests

```bash
python3 tests/run_tests.py
```

378 checks, no dependencies. The redaction cases are the reason the file exists: every other part of
this fails visibly — a wrong map entry sends you to the wrong file and you notice — while a
redaction regression fails silently and writes a credential into a file this README tells you to
commit.

Both directions are covered throughout. A redactor that replaces everything would pass any
"did it hide the secret" test perfectly, so the suite also asserts that commit hashes, UUIDs, RFC
numbers and credential-free URLs come through untouched.

Two real bugs were found by writing it: the scratch-repeat threshold was tuned against long scripts
and silently ignored the short repeated ones it exists to catch, and a Google API key one character
outside the expected length slipped the pattern.

The rest came out of hardening it against the polyglot system below, and from the continuity work
in 1.3 — which took the suite from 87 checks to 378.

## More documentation

| | |
|---|---|
| [docs/architecture.md](docs/architecture.md) | How the parts fit together — what runs locally, what is generated, what a session receives |
| [docs/data-flow.md](docs/data-flow.md) | Where your code goes when chamnan runs, and where it does not |
| [docs/verification.md](docs/verification.md) | What to run before tagging a release, and what a good result looks like |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development setup, adding language support, what a pull request is expected to include |


## License

MIT
