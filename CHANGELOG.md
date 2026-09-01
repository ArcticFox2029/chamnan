# Changelog

Release notes for every version. The newest release is also at the top of the
[README](README.md#whats-new-in-1110), and every one of these is on the
[releases page](https://github.com/ArcticFox2029/chamnan/releases).

Kept here rather than in the README because thirteen of them had grown to a third of that file, and
a version history is the one thing a first-time reader never needs.

---

## What's new in 1.10.0

**Everything chamnan injected was being cut in half, and nothing said so.** Claude Code truncates a
`SessionStart` hook's stdout above **10,000 bytes**, replacing the block with its first 2,048 bytes
and a path to a file — [#70460](https://github.com/anthropics/claude-code/issues/70460),
[#44086](https://github.com/anthropics/claude-code/issues/44086), from v2.1.88 onward. The cut is
positional. Measured across 120 recorded injections on the development repository, **47 were
truncated and each lost 77–86%**.

Because the architecture index is printed first, what survived was the tail of a directory listing.
What went was everything behind it: the repository's rules, its recorded decisions, its open
threads, the session handoff, and every pinned heading — including the ones that exist to stop a
session redoing settled work. `split_pinned()` had protected all of them correctly. The host
discarded them anyway, and the preview ends mid-sentence and reads like a whole block.

**Token budgets could not have caught this**, because they are not measured in the unit the cut is
made in. `index_token_budget` (3,000) and `state_token_budget` (1,700) come to **11,501 bytes** on
real index text — the two defaults exceed the cap by 15% before a single other section is added.
That has been true of every installation since the budgets were set.

So there is a byte ceiling now, `output_byte_ceiling`, default 9,000, enforced where the block is
printed. Over it, chamnan spends resolution before it spends sections — the roll-up steps down
`8 → 4 → 2 → 0` names per directory — and only then drops whole sections, cheapest first, each named
with the file to read it in. A section too large to fit at all is **trimmed with its fence rebuilt**
rather than dropped, because half a session handoff beats none of one. `--explain` now prints the
byte total, the ceiling, what was left out, and the token-to-byte arithmetic.

**The roll-up stopped choosing its filenames alphabetically.** When the index is folded, each
directory line shows eight names, and those eight were `sorted(names)[:8]` — the alphabet, which
knows nothing about the repository. Measured against 12,332 re-read events across six working
sessions: the alphabetical eight named **22.7%** of them, **git-churn-ranked eight named 35.6%**,
and an oracle picking with hindsight reaches 57.0%. Same budget, one `git log`, a third of the
available headroom. A repo with no git, a shallow clone, or under 50 commits falls back to the
alphabet — commit history degrades localization on sparse histories, and names are always printed
sorted so a re-run never reshuffles the line.

**A fenced code block is not structure.** `split_pinned()` matched `#` headings inside fenced
blocks, so a bash comment in a procedure ended the pinned span — the protected payload fell into the
droppable pool and the fence was torn in half. A `description:` line anywhere in a document was read
as front matter and became its title; one entry was titled *"was written by the vendor and could not
be checked."* Both fixed in a new `lib/md.py` that knows what CommonMark actually considers a fence.

**The redactor was replacing the label and leaving the token.** `Authorization: Bearer <token>`
matched the bare-assignment rule, which captured the word `Bearer` as the value and replaced *that*
— emitting a line that read as redacted with the credential intact beneath it. A miss is
recoverable; a reviewer can still see the secret. A miss dressed as a hit is not. Also: a PGP secret
key ends `PRIVATE KEY BLOCK-----`, and the pattern was anchored on `PRIVATE KEY-----`. Against a
labelled corpus of 27 secret shapes and 17 ordinary strings that must survive, **66.7% recall /
81.8% precision → 96.3% / 100%**. The README now carries that pair, the published head-to-head it
should be read against, and the ceiling chamnan cannot reach.

**CJK text is written with CJK punctuation, and it was priced as Latin.** The ideographic comma and
full stop and the fullwidth comma were in none of the token estimator's CJK ranges, so each cost
0.42 tokens where it costs about 1 — 18 of 306 characters in the Chinese calibration sample.
Chinese **−7.7% → +0.4%**. The whole per-script error table is a test now, run offline against the
measurements already on disk.

---

---

## What's new in 1.9.0

**The knowledge arrives with the file, instead of waiting to be asked for.** Measured on the
repository this plugin is developed against, over ten days: `chamnan-impact` — which answers *what
breaks if I change this*, the question actually asked before an edit — was run **zero times**. So
were `chamnan-age`, `chamnan-candidates`, `chamnan-env`, `chamnan-peek` and `chamnan-promote`.
`chamnan-map` 3, `chamnan-report` 1, `chamnan-timeline` 1. By the person who wrote them, in the
repository they were written for.

**What that zero does and does not establish.** Ten days of no uses does not mean the rate is zero.
The one-sided 95% upper bound after `n` observations with no events is `1 - 0.05^(1/n)`, so ten days
bounds the true rate at **0.259 per day - as much as 7.8 uses a month** still fits the data. A
command consistent with weekly use can easily show ten quiet days. The honest statement is "not once
in ten days, which rules out daily use and rules out nothing below it", and 80% of features in a
615-subscription study are rarely used, so a long tail is the ordinary shape rather than a defect.

The reading taken was therefore not that the knowledge is unwanted, and not that the zero proved
anything on its own. It was that a CLI is the wrong surface for it. The caller is a model, and a
model does not pause before an edit and think *"I should run chamnan-impact first"* - remembering to
ask is the work this plugin exists to remove. That argument stands without the zero; the zero is
consistent with it, not evidence for it.

So opening a file now says what the repository already records about it:

```
[chamnan] what this repository already records about command/start_recheckapp.command:
  procedure skills/main_app_machine_migration.md — machine migration & environment repair
  lesson    memory/lessons/statusline-lives-in-two-places.md — the statusline that runs is ~/.claude/
  used by   status_bar_app.py, start_backup.py
  tested by test_recheckapp_installs_what_runs.py
```

Matching is a filename **with its extension**, or a path, appearing in an entry's body — the cheap
design chosen over a required `files:` front-matter field. The extension is the whole guard: a bare
stem would fire on every sentence containing the word "state". Ranking is how often an entry names
the file, which earned its place on the first live run — the skills index, naming a script once
among fifty files, outranked the procedure literally titled after that script, which named it seven
times.

Four rules, because a hook that fires many times per session is judged by its worst moment: silent
when it has nothing (never "no results found"), once per file per session, never about chamnan's own
files, and bounded in time — measured at 12.7–21.5 ms of work per call. Turn it off with
`"pointer": false`.

**A big file hands over its shape, not just a warning.** The same measurement produced the same
verdict twice: `chamnan-peek` — which reads a 40MB CSV's column list, row count and three sample
rows for about two hundred tokens — was also run zero times. The bulk-read notice already fired
before a large read and said *"this is 1.4M tokens, go and grep"*, which leaves the work exactly
where it was. It now includes the shape:

```
chamnan: `orders.csv` is very large (~1,407,846 tokens), and every later turn in this session
carries it. A grep or a line range costs a fraction of that.

chamnan read its shape instead, so you can decide from this rather than from the size alone:

# orders.csv
4.8MB · .csv
6 columns, 120,000 data rows
columns: `order_id`, `customer`, `sku`, `qty`, `unit_price`, `shipped_at`
first rows:
  0 | cust0 | SKU-0 | 1 | 199.03 | 2026-08-01
_[115 tokens instead of about 2,111,769 for the whole file — 18,297× smaller]_
```

Only for formats peek has a real handler for — CSV, JSON, spreadsheets, archives, SQLite, PDF,
images. A 674KB JavaScript file falls through to the binary fallback, whose honest output is a crc32
and five string fragments, measured at 135 tokens of nothing; there the size warning alone is still
the better answer.

Making this possible meant fixing peek itself. Its cost note read the **whole file** to print one
comparison ratio: measured on a 4.8MB CSV, the actual work took 0.14s and the whole call took 7.5s,
all of it tokenizing five megabytes for a decorative number. It is now measured on a 16KB sample and
labelled "about" — **7.48s → 0.164s, a 46× speedup**, with the estimate 2.4% off on ASCII and 0.06%
off on Thai. The Thai figure is why the sample converts bytes to characters rather than assuming
they are the same: scaling a per-character token rate by a byte count would have reported every Thai
file at three times its real cost.

**STATE.md sections age out.** `STATE.md` was trimmed by a token budget, which is a size rule, not a
relevance one — so *"fixed and committed tonight (do not redo)"* was correct for one night and
charged to every session after it. Measured here: 2,367 tokens, 37.8% of the whole injection, 667
over its own budget.

A section now stops being injected once its text has been unchanged for `state_stale_days` (14 by
default, `0` turns it off). Per section, and the clock resets on any real edit — being worked on is
the evidence, so nothing in flight ages. This is the one place chamnan treats age as evidence, and
it is not a contradiction of [knowledge aging](#knowledge-aging--never-against-a-clock-and-it-refuses-rather-than-reassures):
a decision does not rot with time, but *"work in flight"* is a claim about the present.

Three rules keep it from losing anything: a pinned (📌) heading is exempt at any depth, the file
itself is never modified, and what was held back is named in one line saying how to keep it. On
upgrade, nothing is held back for the first 14 days — every section's clock starts the first time it
is seen.

---

## What's new in 1.8.0

**Repository text is fenced.** chamnan's whole job is to take markdown the repository controls and
put it in front of an agent — so a poisoned file in a repository you cloned is a path to
instructing that agent, and until now content from disk sat inline with chamnan's own words with
nothing to tell them apart.

Every section built from a file is now wrapped in a boundary carrying a nonce generated fresh each
session, with one line at the top saying what the boundary means. A fixed marker would simply be
written into a file to close the block early and let what follows read as chamnan speaking; a
per-session nonce cannot be written in advance, and a literal closing mark inside a body is escaped
before the body is wrapped.

It costs 178 tokens on this repository — 3.2% of the injection — and `chamnan-map --explain` prints
that figure rather than leaving you to wonder. It is a mitigation, not a proof: it gives a reliable
answer to *who said this*, which was unanswerable before. It does not make hostile text safe to act
on, and nothing is censored — an attempt is delivered inside the fence where it can be seen.

**How much a fence is worth, measured by people who measured it.** In the spotlighting taxonomy
([arXiv:2403.14720](https://arxiv.org/abs/2403.14720)) this is *delimiting*, the weakest of three
variants, and the paper puts its effect at roughly a **halving** of attack success rate. The two
stronger variants reach far further — *datamarking* takes ASR from ~50% to **under 3%**, *encoding*
to **≈0%** — and neither is available here: both work by making the untrusted text unreadable as
prose, and this untrusted text is a code map whose entire purpose is to be read. And all three are
beaten by an attacker who adapts: against static attacks spotlighting held ASR near 1%, while
adaptive search-based attacks reached **>95%**
([arXiv:2510.09023](https://arxiv.org/abs/2510.09023)).

So the honest claim is narrow, and it is the one made above: the fence answers *who said this*. It
is not a defence against a determined attacker, it was never going to be, and a plugin that told
you otherwise would be selling you something. What it buys is that a poisoned comment arrives
labelled as a poisoned comment.

---

## What's new in 1.7.3

**A restated filename took its separator with it.** A header that opens `# cve.sh — checks the CVE
list` has the filename dropped, because the index row already shows it — but the dash that joined it
to the sentence was left behind, so the row rendered as `path (137L, 2fn) — — checks the CVE list`:
two dashes with nothing between them. Found by rebuilding a real repository's map and reading the
diff rather than by a test, which is why there is now a test.

---

## What's new in 1.7.2

**An update is offered, never taken.** When a newer version is already sitting in the marketplace
Claude Code installed from, the session says so and stops there — nothing is changed until you say
yes. A tool that upgrades itself because you opened a session is doing something you did not ask
for, and doing it quietly is worse than not doing it at all. Once one repository is on the new
version, every other repository brings its own workspace up to date by itself the next time it is
opened.

No network is involved, and there will not be one: repository-local with no calls out is what this
is. The marketplace copy is already on disk, so "is there a newer one" is a local question.
`claude plugin marketplace update` is what refreshes that copy.

**An older build running against a newer workspace is caught.** A plugin's `bin/` goes on `PATH`
pinned at session start, so upgrading mid-session leaves the old executables live — and one machine
can carry several installs, one per config directory. The workspace records the newest version that
has set it up, and says so if something older turns up later. An upgrade is silent; only going
backwards is worth interrupting for.

**A stale index is reported.** If source has changed since `MAP.md` was built, the session says how
far behind it is and names the command that fixes it. Reported rather than rebuilt: rebuilding
unasked at session start spends real time on work nobody requested, and the gap is stated honestly
in minutes or hours rather than rounded up to a day.

---

## What's new in 1.7.1

**An upgrade now reaches the repository, not only the plugin.** 1.7.0 created the workspace when
`.chamnan/` was absent, which left every workspace made by an older version exactly as it was. Two
repositories that had been using chamnan for weeks still had no `memory/`, `sessions/` or
`threads/` directory at all, and a `config.json` holding 10 of the 19 keys — so memory, session
records, threads, timeline, environments, milestones and the ledger had never once worked there,
silently, because the directories those features write into did not exist.

The scaffold is now reconciled on every session: missing directories are created, and the config
gains keys added since it was written while keeping the values you chose. Nothing is overwritten,
and the "workspace created" line still appears only the first time.

---

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

---

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

---

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

---

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

---

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

---

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
