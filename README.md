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

> **Using Kiro instead of Claude Code?** There is a Kiro Power, in its own repository:
> **[→ chamnan for Kiro](https://github.com/ArcticFox2029/chamnan-kiro)**
>
> Same scanner, same artifacts. The context reaches a session through Kiro's steering files rather
> than hooks, and the bulk-read notice arrives at the next `catch-up` rather than before the read.

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
├── candidates/     detected sequences, awaiting review (starts empty; `chamnan-candidates`)
└── logs/           bounded by log_retention_days    (starts empty)
```

Every directory and `config.json` appear on the **first session** in the repository, before you
run anything — so the places to write exist the moment a skill needs one, and the session that
creates them says so. `MAP.md` arrives when the index is first built, `STATE.md` during bootstrap,
the rest when their skills are asked for. The session-start hook skips whatever is absent, so a
repository that only ever builds an index stays exactly that simple.

Nothing is created outside a version-controlled repository: chamnan is for repositories you revisit,
and a folder that is not one is left alone.

Add `.chamnan/logs/` to `.gitignore` if you would rather not carry it. Everything else is worth
committing — that is how the next person, and the next session, gets it.

### Trying it without installing

From the parent directory of a clone:

```bash
git clone https://github.com/ArcticFox2029/chamnan
claude --plugin-dir ./chamnan
```

The plugin is active for that session only. It creates the empty `.chamnan/` scaffold, and
nothing else is written until you run `/chamnan:bootstrap` or `chamnan-map`.

## What's new in 1.7.0

Three changes, all of them about the system being ready and honest rather than about new places to
store things.

**A new repository is set up on its first session.** The workspace used to be created only as a
side effect of running `chamnan-map`, `chamnan-promote` or `chamnan-candidates` — so someone who
installed the plugin and opened a project got no directories, no `config.json`, and no indication
the plugin existed. Every write skill had nowhere to write. The scaffold is now laid down up front,
in a version-controlled repository only, and the session that creates it says what was created.

**`chamnan-map --explain` prices the injection.** Every section, what it cost, and the file or
store it came from — so "why is this in my context?" has a number rather than an argument. The
accounting is a side effect of building the text, so there is no second model of the context to
drift out of step with the real one.

**One tree walk instead of nine.** Building the map ran nine separate full-tree traversals, each
filtering its skip list only *after* descending, so every one paid the full cost of `.venv`,
`node_modules` and `.git` before discarding the results. On a 224-file repository that took
`chamnan-map` from ~92 seconds to ~10.6, with `MAP.md` byte-for-byte identical.

## What's new in 1.6.0

1.5.x made knowledge capture visible and reviewable. 1.6.0 is about context in **time** and
**place**: what has already happened to this file, and what the environment it runs in will not let
you do.

### Threads — one line of work across the sessions it took

    $ chamnan-timeline for src/auth.py
    2 entries naming src/auth.py

      2026-08-14 — second attempt held
               on Auth migration
      2026-08-01 — rolled back — sessions did not survive a node restart
               on Auth migration

"We have tried to fix this three times" is knowledge nobody can reconstruct from a git log: the
three attempts are three unrelated commits weeks apart, and the thing tying them together was only
ever in somebody's head.

**Threading is a pick from a declared list, never a string match** — the one design decision this
feature rests on. Guessing which thread an entry belongs to by matching its words fails on the
first synonym: one session writes "auth", the next writes "login", the third writes "the SSO work",
and a matcher scatters one thread across three. So `chamnan-timeline new` is the only thing that
creates a thread, and `add` refuses a name that was never declared, printing the declared list
instead of quietly starting a fourth.

### `chamnan-impact` — and the join that makes it worth asking

The dependency analysis already existed and already fed `MAP.md`; it simply had no way to be
*asked*. Now it does, and the answer carries the thread history for the same file:

    $ chamnan-impact src/auth.py

      used by   src/api.py
      tested by nothing the index can see — a change here is unguarded
      (from `.chamnan/MAP.md`, built today)

      2 thread entries name this file:
        2026-08-01 — rolled back — sessions did not survive a node restart

An import graph can say what breaks. It cannot say "last time this changed, it needed a rollback",
and that is the half that changes what somebody does next.

It reads `MAP.md` rather than rescanning — a full scan of the repository this plugin is developed
against measured **64 seconds**, which is not a thing to do on an interactive question. The cost is
that the answer is only as fresh as the last `chamnan-map`, so the index's age is printed with
every answer instead of left to be assumed.

### `environments.md` — the constraints nobody writes down

    ## production
    **Platform:** Kubernetes 1.28 on RKE2
    **Versions:** postgres 16, redis 7.2
    **Constraints:**
    - RWO storage only — no ReadWriteMany PVCs
    - no outbound internet from worker nodes
    **Checked:** 2026-08-27

"RWO storage only", "no TPM in UAT", "DR runs different hardware" — each one is discovered the same
way: somebody writes the obvious solution, it fails in one environment and not another, and an
afternoon goes into finding out why. The fact is one line long, and it is in neither the code (the
code is what got written *because* of it) nor the git history (the commit explains the workaround,
not the constraint).

The constraints are injected at session start, and named again the moment a session is
demonstrably working against that environment. **Nothing here contacts an environment** — every
line was typed by somebody who knew it, which is exactly why `Checked:` matters.

### Knowledge aging — never against a clock, and it refuses rather than reassures

A note written two years ago about a version still in production is current. One written last month
about a version replaced last week is already wrong. **Age carries no information about either**,
so `chamnan-age` compares what an entry *claims* against what `environments.md` *declares*.

That makes the check exactly as trustworthy as that file — which is the risk it is built around:

    $ chamnan-age
    chamnan: not checked — every declared environment has gone cold (uat, production) —
    nothing here is checked, because an unconfirmed entry is evidence nobody looked, not
    evidence nothing changed.

An environment nobody has confirmed in six months is not an authority. Reporting "your knowledge is
current" on the strength of it is a **false all-clear**, which is worse than no check at all,
because it is the answer that stops somebody looking. So when every environment has gone cold this
reports nothing and says why. There is a third outcome too — a claim matched only by a cold
environment is reported as *unverifiable*, not as a finding, because nobody knows.

Equality only, never ordering: `3.9` versus `3.11` is exactly the comparison a version comparator
gets wrong, and it is the one Python repositories hit most.

## What's new in 1.5.2

1.5.1 closed the loop from evidence to a kept tool. 1.5.2 asks what happens after — does a promoted
tool actually keep working, and is any of this actually being used.

### Tool health, without an exit code

A Bash `tool_response` carries `stdout`, `stderr` and `interrupted` — never a numeric status, so a
promoted tool exiting non-zero cannot be observed directly. What CAN be observed: whether the call
was interrupted, and whether it wrote to stderr. Neither means "it failed" on its own — plenty of
correct commands write warnings to stderr — so neither is ever reported as one. Three occurrences of
either flags the tool once, quietly:

    chamnan: `.chamnan/tools/deploy-check.sh` has been interrupted or written to stderr 3 times in
    its last 11 run(s) — worth a look. `chamnan candidates demote deploy-check.sh` sends it back for
    review if it no longer does what you expect.

Silent before the third occurrence, silent after — the same restraint every other notice in this
plugin already uses. `chamnan-candidates demote <tool-name>` undoes a promotion: removes it from
`tools/index.json`, deletes the file, and writes a fresh candidate from its own description, so the
routine goes back through review instead of just disappearing.

**Skills are out of scope, on purpose.** A tool is a script a hook can watch run; a skill is a
markdown file Claude reads on its own judgement, and nothing here can see that the read happened at
all, let alone whether following it went well. There is no smaller version of skill feedback that
stays honest about what a hook can actually see — so none is attempted.

### Usage counts, never a savings figure

`chamnan-report` now opens with a Usage section, right after the knowledge inventory:

    Usage
      chamnan-candidates     3 times
      chamnan-map            14 times
      chamnan-peek            0 times
      chamnan-promote         2 times
      chamnan-report           6 times
      (from the calls currently logged, 2026-08-01 to 2026-08-27 — commands.jsonl holds the
      most recent 400, not a calendar window)

    Promoted tools
      deploy-check.sh        12 runs

Both halves were already being written before this had a reader: the command counts come from
`commands.jsonl`, the same bounded log the workflow detector keeps; the tool counts come from the
`runs` field `chamnan-candidates demote`'s neighbour above has been incrementing since 1.5.2's tool
health tracking shipped. This reports **counts, never a savings figure** — a number of tokens or
hours saved would be invented, and this project already retired an "Engineer Scoreboard" for
measuring what is easy instead of what matters.

## What's new in 1.5.1

1.5 made a detected sequence survive as a **candidate** instead of a notice that scrolls away.
1.5.1 is what to do with one — a review CLI, and a promotion path honest about what it cannot know.

### `chamnan-candidates` — the review CLI

    $ chamnan-candidates
    2 candidate(s) waiting

    [1] docker compose · alembic · pytest
        observed 4 time(s) · last seen 2026-08-26 · ai-inferred
    [2] git add · git commit · git push
        observed 3 time(s) · last seen 2026-08-27 · ai-inferred

`confirm <id>`, `reject <id>`, `edit <id>` — `<id>` is either the number shown above (computed
fresh each call, never cached) or the candidate's own slug. `confirm` only moves `Provenance` from
`ai-inferred` to `ai-confirmed`; it never writes into `skills/` or `tools/` on its own.

### `chamnan-candidates promote` — and the honest ceiling on it

Refuses a candidate that has not been confirmed — the pipeline is *evidence → candidate → human
confirm → memory*, and this enforces the order rather than assuming it.

With no destination, it only suggests, and writes nothing:

    Suggested: tool — this is a sequence of shell commands, which is what a tool is.
    Choose skill instead if the real value is explaining WHY, or a judgement call at
    one of the steps — chamnan cannot tell that from the sequence alone; you can.

That is the whole classifier, stated as a default with its reasoning printed next to it, not a
computed score. A candidate stores what ran — `git commit`, never the literal command with its
real arguments, and never why the routine mattered. There is no signal in that to choose
confidently from, and a project that has already retired a Health Score and a Confidence Score for
being judgements no evidence backs was not going to invent a third one here.

**`promote <id> tool <name>`** writes an executable *skeleton* — one labelled placeholder per step
— and it fails loudly if you run it before filling those in, rather than silently doing nothing
while looking like it worked:

    echo "TODO step 1: docker compose" >&2; exit 1  # replace this line

Registered through the same `tools/index.json` machinery `chamnan-promote` already uses — the two
now share one implementation (`lib/tools_index.py`) rather than two that could drift apart. Once
installed, the candidate is removed; its finding now lives in the tool file, not duplicated in both.

**`promote <id> skill`** writes nothing at all. A skill's value is the prose explaining *why*,
which cannot be honestly generated from a signature list — this prints the sequence as a starting
point and names `/chamnan:capture`, and leaves the candidate exactly where it was, because nothing
has actually been captured yet.

## What's new in 1.5

Measured on a real workspace: `.chamnan/sessions/` and every `.chamnan/memory/` category held
**zero entries** after five weeks of daily use, while the hook-written activity logs held **700**
records. The stores 1.3 added were built correctly; nothing was making writing to them happen. 1.5
is entirely about that gap — no new store, one new record type, and four small mechanisms that
turn absence into something visible instead of something silent.

### Two lines that name what already exists

Every session now opens with two short lines, **~112 tokens together on an empty workspace, ~128
once something has actually been written** — this plugin's entire always-on price for the release:

    _Write with `/chamnan:resume` (session record), `/chamnan:remember` (decision, lesson, or
    rule), `/chamnan:milestone`, or `/chamnan:capture` (a procedure worth keeping). Nothing writes
    here unless you ask._
    _chamnan · 0 records · 0 memory entries · nothing written yet_

The first line exists because `session_start.py` had never once named the plugin's own write
skills — it injected the *workspace's* recorded procedures and stopped there, so an agent had no
way to discover `/chamnan:remember` short of reading the plugin's source. The second is the
ledger: a count for every store, always printed, always showing **movement** rather than a static
number — `3 records (+2 this week) · last write 2 days ago`, once there is something to compare
against. A number that never changes is what gets tuned out; the word "zero" printed plainly is not.

### `STATE.md` stops losing what you pinned

The injection cap changed from a flat 4,000 characters with no notice when something was cut, to a
**token budget** (`state_token_budget`, default `1700`) with a visible marker — `_…9.1k more —
read .chamnan/STATE.md_` — so a truncated file says so instead of quietly dropping 69% of itself.

A heading can also be **pinned**, by ending it with 📌. A pinned section is injected in full,
first, regardless of where in the file it falls — so a standing instruction like `### SETTLED — do
not raise these again 📌` cannot lose a race for the top of the file as the file grows.

### The repeated-workflow detector actually detects something

1.3's sequence detector (`git diff → git status → git commit`, recurring across separate days) had
a bug that made it find nothing on a real, active workspace: shell keywords — `do`, `for`, `done`,
`then`, `break` — were being recorded as if they were program names, because a chained command
splits on `;` and the detector only ever looked at a fragment's first word. On one measured log,
**26% of it was shell syntax**, not workflow steps. Keywords are now excluded as their own
category, distinct from ordinary commands too common to mean anything.

### A finding that survives past the moment it was noticed

When a sequence crosses the threshold, it no longer just prints once and disappears — it is kept
as a **candidate**, one file under `.chamnan/candidates/`, keyed on the sequence itself so the same
routine detected again updates the one file instead of creating another:

    # docker compose · alembic · pytest
    **Sequence:** docker compose, alembic, pytest
    **Observed:** 3
    **Last seen:** 2026-08-27
    **Provenance:** ai-inferred

A candidate is evidence, never itself knowledge — nothing injects one into a session; only its
**count** reaches the ledger (`4 awaiting review`), and only `/chamnan:capture`, run by you,
promotes one into something a session actually reads. A companion **resume nudge** fires at most
once per Claude Code session — tracked by `session_id`, not by calendar day, so two sessions on
the same day each get their own chance — when real work has happened and nothing is recorded for
today yet.

### Knowledge inventory, and two questions nobody was asking

`chamnan-report` now opens with what actually exists, store by store, zeros printed plainly:

    Knowledge inventory
      sessions/             0 entries    last write never
      memory/decisions/     0 entries    last write never
      ...
      1 of 5 decisions have no `Rejected:` — a trade-off nobody wrote down

Decisions gain a named `**Rejected:**` field — a heading you fill in rather than a sentence that
was easy to skip while writing quickly — and every memory entry is automatically stamped with
`**As-of:**` (today's date) and `**Provenance:**` (`ai-drafted` by default) the moment it is
written, by a hook rather than by asking the `remember` skill to remember to include them. An
existing `Provenance` is never overwritten, so a value you set by hand stays exactly what you set.

### Three defects closed along the way

- An en-dash (`–`, which editors autocorrect `--` into) in a milestone heading was silently
  absorbed into the *previous* entry's body rather than becoming its own entry — the character
  class only recognised em-dash and hyphen. Fixed, and covered for all three.
- A decision or lesson title had no length limit on its way into the session-start listing —
  capped at 120 characters, with a visible `…` rather than a silent cut.
- A skill's registry line fell back to `no description — add one` whenever the file had no YAML
  frontmatter, which was true of every skill on the workspace this was measured against. It now
  falls back to the first real line of body text instead of staying empty.

**The honest ceiling, unchanged by any of this:** writing still depends on choosing to write.
Nothing here can see a session's conversation and decide something is worth keeping. What changed
is that not writing anything is now a fact printed in front of you every session, instead of a
silent absence nobody had reason to notice.

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

### A checkout inside your checkout is not your code

If another repository is checked out inside this one — a vendored dependency, a sample project, a
sibling you keep side by side — chamnan leaves it alone. Its files are not indexed, its size is not
reported as yours, and its Kubernetes resources and Protobuf services do not appear in your
architecture map.

The signal is the nested `.git`, not `.gitignore`. chamnan does not read `.gitignore` anywhere —
it is often absent, often wrong, and never covers a nested checkout's own build output.

Running chamnan from *inside* such a checkout builds that repository's index, not its host's. It
also says which repository it measured whenever that is not the directory you ran it from:

```
chamnan: run from vendor/thing/ — scanning the repository above it, myapp/
```

Silence there was the dangerous default. A directory that is not itself a repository resolves to
whatever repository contains it, and every number printed afterwards is about the wrong tree.

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
| `ledger` | `true` | `true` / `false` | The write-skills line and the ledger line at the top of every session — naming the plugin's write skills, and a count of what each store holds. ~112–128 tokens together. Also gates the once-per-session resume nudge. |
| `state_token_budget` | `1700` | integer, tokens | Ceiling on `STATE.md`'s injection, in tokens rather than characters. A section whose heading ends in 📌 is injected in full first, regardless of this budget or where in the file it falls. |

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
| `chamnan-map --explain` | what this session's context is made of: every section, what it cost in tokens, and the file or store it came from. Answers "why is this in my context?" with a number instead of an argument |
| `chamnan-map --install-git-hook` | opt-in: refresh the index on commit. Appends to an existing `pre-commit` hook rather than replacing it |
| `chamnan-peek <file>` | the shape of one file instead of the whole thing — columns, sheets, members, schema, pages |
| `chamnan-peek <file> --find PATTERN` | only the parts that match, with their line numbers |
| `chamnan-peek <file> --budget 800` | raise the output ceiling from its default of 400 tokens |
| `chamnan-promote <file> <name> --desc "…"` | install a scratch script as a permanent tool in `.chamnan/tools/` |
| `chamnan-promote --list` | what this repo already keeps |
| `chamnan-candidates` | list detected sequences waiting for review — same as `chamnan-candidates list` |
| `chamnan-candidates confirm/reject/edit <id>` | mark a candidate worth keeping, discard it, or print its file path |
| `chamnan-candidates promote <id> [tool\|skill]` | with no destination, suggest one and write nothing; `tool <name>` installs an executable skeleton; `skill` prints the sequence for `/chamnan:capture` |
| `chamnan-candidates demote <tool-name>` | undo a promotion — removes it from `tools/index.json`, deletes the file, and writes a fresh candidate from its description so it goes through review again |
| `chamnan-timeline` | list declared threads — a line of work followed across the sessions it took |
| `chamnan-timeline new <title>` | DECLARE a thread; nothing else creates one, so a synonym cannot start a second thread for the same subject |
| `chamnan-timeline add <id> <note> [--files a.py,b.py]` | append an entry to a declared thread, naming what it touched |
| `chamnan-timeline for <path>` | every thread entry that named this file |
| `chamnan-impact <path>` | who depends on it, what tests cover it, and what happened last time it changed |
| `chamnan-env` | declared environments and the constraints nobody writes down |
| `chamnan-env set <name> --platform … --constraint …` | declare or update one environment; replaces in place |
| `chamnan-env check` | which environment entries nobody has confirmed lately |
| `chamnan-age` | which stored knowledge names a version no environment declares any more |
| `chamnan-report` | opens with the knowledge inventory (every store's count and last write, zeros included), then Usage (chamnan's own commands and any promoted tool, counts only, zeros included), then weekly context-per-turn. On a repo with no Claude Code history it still shows the first two sections, then says so instead of inventing a trend |

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

The corpus itself is published, so none of it has to be taken on trust:
**[→ chamnan-corpus](https://github.com/ArcticFox2029/chamnan-corpus)**. Steps, exact
output and the two things to get right first are under **Try it on the test corpus** below.

chamnan is an amortising tool: it spends once and collects on every session afterwards. On a
four-file repository it costs more than it saves. On 2,365 files the index is 0.4% of the source.
Which side of that your repository sits on is the whole question, and it is the first section of
this README.

## Try it on the test corpus

Every corpus figure above — in **Evidence**, and every token count in **The chaos test** —
came from one synthetic corpus, and that corpus is published, so none of it has to be taken on
trust:
**[→ chamnan-corpus](https://github.com/ArcticFox2029/chamnan-corpus)** — 800 files,
72 file types, comments in eight writing systems, three SQL dialects, and one corner of
deliberately careless code with no comments at all.

Roughly two minutes, and it touches nothing you own:

```bash
# 1. the corpus and this repository, side by side — see the note below about "side by side"
git clone https://github.com/ArcticFox2029/chamnan-corpus.git
git clone https://github.com/ArcticFox2029/chamnan.git

# 2. fill in the planted credentials. They ship as __PLANTED_…__ placeholders, because
#    GitHub's secret scanning cannot tell an invented AKIA string from a real one.
cd chamnan-corpus
python3 plant_secrets.py

# 3. index it
../chamnan/bin/chamnan-map
```

```
529 source file(s), 1,373,242 tokens of code
Quick Index    53,652 tokens  (3.9% of the source)
Full Detail   132,999 tokens  (grep this, never read it whole)
described    [###################.] 517/529 files (98%)

Over the 3,000-token session budget, so session start will roll this up by
directory: ~2,970 tokens injected per session instead of 53,652
```

Then the test that matters more than the ratio — whether any of the credentials you just planted
came out the other end:

```bash
grep -cE 'AKIA[A-Z0-9]{16}|sk_live_|ghp_|glpat-|SG\.|xoxb-|sk-ant-|BEGIN [A-Z ]*PRIVATE KEY' .chamnan/MAP.md
```

`0`. Eleven credential shapes, plus the generated database password read straight out of the DSN it
was planted in.

### Two things to get right before you run it

**Clone the corpus beside your own repositories, never inside one.** `find_root` walks up from the
working directory looking for `.chamnan/`, then for a `.git`. Nested inside a repository of yours,
that walk finds *yours* — so the scan measures your code, writes `.chamnan/` into your tree, and
reports a number that has nothing to do with the corpus. The corpus clone brings its own `.git`,
which is what keeps the boundary where you expect it.

**Run `python3 plant_secrets.py --revert` before committing anything**, if you keep the corpus
around in a repository of your own. A planted corpus is rejected by GitHub push protection, and an
`AKIA` string is forwarded to AWS by partner scanning within minutes — for a fixture that
corresponds to no account anywhere. `--check` says which state a working copy is in.

### Read one number carefully

The published corpus omits the 1,192 binary attachments and five bulk seed-data SQL files — 20 MB
that git stores badly and that test nothing the schema files do not. Those are most of the
11,560,484 tokens quoted above, so the ratio you will measure is **26×, not 223×**.

The index barely moves (53,652 against 51,937), because attachments were never *described* in it —
they were listed as stored material, which is the entire point of that section. 223× is the honest
figure for a repository that carries its payload beside its source; 26× is the honest figure for
source alone. Same tool, same corpus; the difference is what you keep in your repository, not what
chamnan does with it.

## Troubleshooting

**Start here.** `chamnan-map --preview` runs the session-start hook and prints its output verbatim,
so "is anything being injected, and how much" stops being a guess:

```bash
chamnan-map --preview
```

| Symptom | What it means | What to do |
|---|---|---|
| `/chamnan:bootstrap` is not offered | The plugin is not loaded in this session | `claude plugin list` — if chamnan is absent, install it again; if it is present but disabled, enable it. A newly installed plugin is picked up by a **new** session, not the running one |
| Nothing appears at session start | Either no index yet, or the hook is not running | The first session in a repository creates `.chamnan/` and says so. If even that did not appear, run `chamnan-map --preview`: if it prints nothing, the plugin is not loaded — see the row above. If it prints the ledger line but no index, build one with `chamnan-map` |
| Sessions feel expensive and you cannot see why | Nothing reported what the injection was made of | `chamnan-map --explain` prices every section and names where it came from |
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
- **Writing still depends on choosing to write.** A hook cannot see a session's conversation, so
  nothing here decides on its own that something is worth keeping — that has not changed since 1.0
  and cannot change within this plugin's model. What 1.5 adds is visibility: the ledger line and
  the knowledge inventory turn "nothing has been written" into a fact printed in front of you every
  session, instead of a silent absence with no reason for anyone to notice it.
- **Tool health tracking (1.5.2) covers `tools/` only, never `skills/`.** A promoted tool is run as
  a Bash call, which a hook can see; a skill is a markdown file Claude reads on its own judgement,
  and nothing logs that the read happened at all, let alone whether following it went well or
  badly. There is no way to build skill feedback within a plugin hook's actual visibility, so it is
  not attempted — not a smaller version of it, not a heuristic standing in for it.
- **There is no per-command environment guard, and that is a verified decision rather than an
  omission.** Intercepting a command before it runs needs a PreToolUse `permissionDecision`. The
  documented enum is `allow` / `deny` / `escalate` — there is no `ask` — and whether `escalate`
  reaches a prompt under `defaultMode: "auto"` is documented nowhere, in either direction; the
  routing of plain stdout from a PreToolUse hook is undocumented too. A guard that might silently
  fail to fire is worse than no guard, because it is trusted. So the constraints are put in front
  of the agent by two mechanisms that *are* proven — injected at session start, and named again
  once per session when a command demonstrably targets that environment — and nothing here blocks,
  prompts, or claims it will.
- **Knowledge aging is only as good as `environments.md`, and says so out loud.** It compares
  claims against declared versions, never against a clock, so it inherits that file's accuracy
  completely. When every declared environment has gone cold it reports nothing and explains why
  rather than returning an empty result that reads like a pass.
- **Even tool health tracking has no exit code to work with.** A Bash `tool_response` carries
  `stdout`, `stderr` and `interrupted` — never a numeric status. What is tracked is exactly those
  two real signals, `interrupted` (a fact) and non-empty `stderr` (a weak one, since plenty of
  correct commands write to it too), and neither is ever reported as "the tool failed". Three
  occurrences of either flags the tool once, quietly, for you to look at — it does not decide
  anything on its own.

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

- **[→ chamnan-corpus](https://github.com/ArcticFox2029/chamnan-corpus)** — the synthetic codebase the Evidence and chaos-test figures were measured on: 800 files, 72 file types, comments in eight writing systems. Download it and reproduce them rather than take them on trust; steps are under [Try it on the test corpus](#try-it-on-the-test-corpus) above.

| | |
|---|---|
| [docs/architecture.md](docs/architecture.md) | How the parts fit together — what runs locally, what is generated, what a session receives |
| [docs/data-flow.md](docs/data-flow.md) | Where your code goes when chamnan runs, and where it does not |
| [docs/verification.md](docs/verification.md) | What to run before tagging a release, and what a good result looks like |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development setup, adding language support, what a pull request is expected to include |


## License

MIT
