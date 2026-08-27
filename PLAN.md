# chamnan — build plan, 1.5.0 through 1.6.0

> **Read this first if you are a new session, or a different account picking this up.**
> Everything needed to continue is in this file. Nothing important lives only in a conversation.
> Work through the stages in order. Each stage ends with a verification block and a STOP.
> The owner approves each stage before the next one starts.

**Status:** Stage 0 complete. Awaiting the owner's go for Stage 1.
**Stage protocol:** every stage is `do → pause → wait for approval`. Never start the next stage
without the owner saying so, even when the work is obvious and the stage is small.
**Source tree:** `Work-Mode/chamnan/` (this directory), currently v1.4.0.
**Repository root:** `/Users/wasuplao/Documents/Lumin-App`

---

## 1. What 1.5.0 is, and why the scope was cut

1.5.0's only job is to make knowledge capture **actually happen**. It ships no Timeline, no
Knowledge Aging and no Environment Awareness. Those move to 1.6.0.

The reason is one measurement taken on the owner's live workspace on 2026-08-27:

| store | writer | records |
|---|---|---|
| `.chamnan/logs/scratch.jsonl` | hook | 300 |
| `.chamnan/logs/commands.jsonl` | hook | 400 |
| `.chamnan/sessions/` | skill | **0** |
| `.chamnan/memory/decisions/` | skill | **0** |
| `.chamnan/memory/lessons/` | skill | **0** |
| `.chamnan/memory/rules/` | skill | **0** |
| `.chamnan/milestones.md` | skill | **does not exist** |

Building three read-features on top of five empty stores is not a release; it is a way of
discovering in six months that nothing was ever written. So the write path is the release.

**And the 700 are thinner than they look.** Their record shapes are:

```
scratch.jsonl   {at, fp: [word tokens], head: "first line of the script"}
commands.jsonl  {at, sig: "git diff"}
```

No files changed, no exit codes, no errors, no outcomes. They are two narrow mechanical traces
built for one purpose (spotting a repeated scratch script), not evidence of work. Nothing can be
promoted into knowledge from them as they stand. That gap is Stage 2.

### The cause, verified rather than assumed

`hooks/session_start.py:138` injects `(wsdir / "skills").glob("*.md")` — the **workspace's own**
captured procedures. It never names the plugin's eight skills. An agent in a chamnan repository is
never told that `/chamnan:remember`, `/chamnan:resume`, `/chamnan:milestone` or `/chamnan:capture`
exist. That is the leading candidate for the entire 700:0 result, and Stage 1 is one line of code.

### The owner is not someone who refuses to write things down

`.chamnan/STATE.md` on the live workspace is 12,859 characters, hand-maintained, and contains
`### Open on the game` (a milestone log) and `### SETTLED — do not raise these again` (a rules
store). It is the one store whose **contents** come back at session start — 4,111 characters, 60%
of the whole injection. The stores that stayed empty are exactly the stores whose contents are
never injected. The write path is not broken by discipline; it is broken by the absence of a
feedback loop.

---

## 2. Design decisions that are settled

These were argued and closed. Do not re-open them without the owner.

| Decision | Reasoning |
|---|---|
| **Timeline, Aging, Environment → 1.6.0** | Gated on Stage 1–4 producing non-zero counters. If after a month the ledger still reads `0 records`, none of them should be built. |
| **One `Provenance:` field, not `Source:` + `Confidence:`** | Two fields for one concept is how a format rots. Closed enum: `user`, `ai-drafted`, `ai-confirmed`, `ai-inferred`, `imported`. |
| **No Health Score** | A composite "Knowledge: Growing" is a judgement the system cannot ground. Same objection that retired the Confidence Score idea. The ledger already carries the facts. |
| **Evidence extends the existing logs; no `evidence/` store** | What is missing is fields, not a place. A new store is another thing to prune, redact, document and keep in sync. |
| **`state_token_budget: 1700`, never 1200** | 1700 preserves today's slice exactly. 1200 silently deletes 1,120 characters from `STATE.md` — the back half of `### SETTLED — do not raise these again`. Deleting the do-not-re-propose list is how an agent re-proposes banned work. The Thai argument does not apply: STATE.md is 25 Thai characters out of 12,859 (0.2%). |
| **The ledger shows movement, not a static zero** | A number that never changes is what gets ignored, not the word "zero". `3 records (+2 this week) · last write 2 days ago` is information; `0 records · last write: never` repeated forever is guilt. |
| **`Symptom:` stays cut** | Free prose from a nondeterministic writer is not a join key. |
| **Nudge on PostToolUse, never SessionEnd** | SessionEnd output arrives after the agent can act on it. |
| **Human confirm stays in the loop** | This repo has already paid for the lesson: 6 of 17 auto-applied typo rules made text worse, which is why `typo-review` and `router-economy` both stage their proposals. |

### Known 1.4.0 defects to fix along the way

| Where | Defect | Stage |
|---|---|---|
| `lib/workflows.py` `signature()` | A `for … ; do …; done` splits at `;` and records `do` as a program name. `commands.jsonl` currently holds `do`, `printf`, `cut`, `tr` as if they were steps. | 2 |
| `lib/milestones.py` `_ENTRY` | `[—-]` accepts em-dash and hyphen; an entry written with an **en-dash** is silently dropped. An unrecognised `##` is absorbed into the previous entry's body. | 4 |
| `lib/memory.py` `render_titles()` | Emits `title_of()` whole — a genuinely unbounded injection channel. | 4 |
| `hooks/session_start.py` `describe()` | All 12 injected skill lines on the live workspace read `no description — add one`: 893 characters buying nothing. Needs a first-sentence fallback. | 4 |
| `hooks/session_start.py` `MAX_STATE_CHARS` | Truncates at 4,000 with **no marker**. 69% of the live STATE.md disappears silently. | 4 |

---

## 3. What the owner and Miki proposed, and what survives

Two rounds of proposals arrived after Stage 0: the owner's **1.5.1 Candidate Intelligence** (five
items) and Miki's **1.5.2 Refinement and Measurement** (three). Assessed against the code:

### The finding that reorders everything

**`lib/workflows.py` already implements the owner's items 1, 2 and 3.** It has `signature()`,
`signatures()`, `record()`, `_runs()`, `repeated()` and `describe()`; `MIN_LENGTH = 3`,
`REPEAT_AT = 3` ("say something on the third occurrence"), `WINDOW = 12`. `scratch_watch.py`'s
`notice_workflow()` fires it on every Bash call. Detecting `git diff → git status → git commit`
recurring **is built and running today.**

It has found nothing. Run against the live 400-record log on 2026-08-27: `repeated()` returns
nothing at all. The reason is in the data:

```
 50  do      ← shell keyword
 38  python3
 31  cut
 14  for     ← shell keyword
 13  kill
 12  tr
 10  done    ← shell keyword
  9  break   ← shell keyword
  5  then    ← shell keyword
```

**About 22% of the log is shell keywords, not programs.** `NOISE` filters thirty ordinary commands
(`cd`, `ls`, `grep`, `sed`…) and contains **no shell keywords at all**, while `_SPLIT` splits on
`;` — so one `for f in *; do cmd; done` deposits three junk signatures. `_runs()` assembles from a
12-record window, and with a fifth of the stream being noise, real sequences never survive intact.

So a feature that already exists has been silently useless for weeks, and the fix is a handful of
words added to one set. **That moves the `signature()` fix from "cleanup in Stage 2" to the thing
that unblocks a shipped feature, and it should be done early.**

### Verdicts

| Proposal | Verdict | Why |
|---|---|---|
| **1.5.1 · 1** Evidence → candidate detection | **Already built** — persist it | `workflows.repeated()` finds the sequence; `notice_workflow()` prints it once and throws it away. The delta is writing a candidate instead of only speaking. Small. |
| **1.5.1 · 2** Candidate dedup, `observed: N` | **Accept** | `repeated()` already returns `(sequence, count)` — the count *is* the dedup. Command signatures are normalised strings, so match exactly; do not reach for Jaccard here, that is for free-text scripts. |
| **1.5.1 · 3** Threshold 1 / 2 / 3+, deterministic | **Accept, already chosen** | `REPEAT_AT = 3` exists in two modules with the comment "say something on the third one, not the second". Reuse the constant; do not invent a second threshold. |
| **1.5.1 · 4** `chamnan candidates` review CLI | **Accept, with a warning** | `bin/` is **not on PATH** — `CLAUDE.md` invokes these tools by full path. A confirm step the owner cannot type in two seconds will not be used, and human-confirm is the pipeline's last mile. Solve the invocation, not just the output. |
| **1.5.1 · 5** Promote candidate → **skill** | **Accept — the strongest idea in the set** | Closes the loop the owner named at the start: repeated work becomes a skill, so the next time costs no re-derivation. `chamnan-promote` and the `promote` skill already turn a scratch script into a *tool*; what is new is the *procedure* destination. |
| **1.5.2 · 1** Suggest Skill vs Tool at confirm time | **Accept — but merge into 1.5.1** | Splitting these leaves a seam where promotion exists but does not know where to send things. It is the same work as 1.5.1 · 5. |
| **1.5.2 · 2** Feedback when a promoted thing fails | **Accept for tools. Not possible for skills.** | A tool is a script: its non-zero exit is in the Bash payload and is observable. A skill is a markdown file Claude reads — **nothing logs that it was read, and no hook can see whether following it went badly.** Build the half that is real and say plainly that the other half depends on the owner reporting it. |
| **1.5.2 · 3** Value / savings report | **Accept counts. Reject "savings".** | Tool invocations are countable from `commands.jsonl` — the signature *is* the tool name. A number of tokens or hours saved would be invented, and this project already retired an "Engineer Scoreboard" for measuring what is easy instead of what matters. Report *"`chamnan-map` ran 14 times this month"*; never *"saved 40k tokens"*. |
| **1.5.2** Health Score (from the earlier round) | **Still rejected** | `Knowledge: Growing` is a judgement the system cannot ground. |

---

## 4. Stages

**Protocol: `do → pause → wait for approval`.** Every stage ends with a verification block and a
STOP. Do not begin the next stage until the owner says so. A handoff to another session or another
account can happen at any stage boundary — this file is the state.

### 1.5.0 — The Ledger · *make capture happen*

| # | Stage | Status |
|---|---|---|
| 0 | Plan and handoff | ✅ done |
| 1 | The two lines | ⬜ |
| 2 | Evidence, and unblock the workflow detector | ⬜ |
| 3 | Candidates, provenance, and the nudge | ⬜ |
| 4 | Inventory, metadata, and the 1.4.0 defects | ⬜ |
| 5 | Release 1.5.0 | ⬜ |

---

#### Stage 0 — Plan and handoff ✅ COMPLETE
- [x] This file, complete enough to continue from
- [x] `.chamnan/STATE.md` points at it, **above the 4,000-character truncation line**
- **Verify:** slice `STATE.md[:4000]` and confirm the pointer is inside it.

---

#### Stage 1 — The two lines ⬜
Cheapest, highest expected value. ~240 characters per session, and the entire always-on price of
the release.

**Files:** `hooks/session_start.py`, new `lib/ledger.py`, `tests/run_tests.py`

1. **Write-skills line** — a section emitted whenever the workspace exists, naming the plugin's
   write skills. Gate on nothing: an agent that does not know it can write is the failure being
   fixed. Read `skills/` first and name only skills that ship. Payload under 140 characters.
2. **Ledger line** — ~110 characters, always emitted, counting entries per store and the age of the
   newest write. **It must show movement**, because a number that never changes is what gets
   ignored — not the word "zero":
   ```
   _chamnan · 3 records (+2 this week) · 11 memory entries · last write 2 days ago · 4 awaiting review_
   _chamnan · 0 records · 0 memory entries · nothing written yet_
   ```
   Counting lives in `lib/ledger.py` so Stage 4's inventory reuses it. `iterdir()` and one `stat()`
   per store; no file reads.

**Tests:** the skills line names every skill in `skills/` and none that is absent · ledger reports 0
for an empty workspace and survives a missing store · "+N this week" is 0, never negative or
missing · both lines inside budget · neither emitted when there is no workspace.

**Verify:** suite green; run the hook read-only against `/Users/wasuplao/Documents/Lumin-App` and
confirm both lines appear and the total grew by ~240 characters, not more. **STOP.**

---

#### Stage 2 — Evidence, and unblock the workflow detector ⬜
Do the `signature()` fix **first**: it repairs a feature that already ships.

**Files:** `lib/workflows.py`, `hooks/scratch_watch.py`, `tests/run_tests.py`

1. **Shell keywords are not programs.** Add `do done then fi else elif for while if case esac
   select until in break continue return function time coproc` to `NOISE` — or better, a separate
   `KEYWORDS` set, so the two reasons for dropping a token stay distinguishable in the code.
   Then re-run `repeated()` against the live log and record in the commit message what it finds
   once the noise is gone. That number is the evidence the fix mattered.
2. **`kind` on every record** in both logs. Without it a second record type in `scratch.jsonl` is
   Jaccard-clustered into the repeated-script families and reported as a repeated script. A record
   with no `kind` — all 300 already on disk — reads as `"scratch"`.
3. **Evidence fields** on the PostToolUse record: tool name, file path when there is one, exit
   status when the payload carries one. **Derived from the hook payload only** — no credential
   file, no subprocess. `KEEP_ENTRIES` stays as it is; this is a hint generator, not an archive.

**Tests:** `for f in *.py; do echo "$f"; done` yields no signature containing a keyword · a 1.4.0
record with no `kind` still reads · new fields are absent rather than `null` when unavailable · no
path in the hook opens a file outside the workspace.

**Verify:** suite green; `repeated()` against the live log now returns something, or explain why
not. **STOP.**

---

#### Stage 3 — Candidates, provenance, and the nudge ⬜
`evidence → candidate → human confirm → memory`. Nothing reaches `memory/` unattended.

**Files:** new `lib/candidates.py`, `hooks/scratch_watch.py`, skills, `tests/run_tests.py`

1. **`.chamnan/candidates/`** — one markdown file per candidate, trailer grammar, every candidate
   carrying `**Provenance:**` from the closed enum `user · ai-drafted · ai-confirmed · ai-inferred
   · imported`. A candidate is never injected as knowledge; only its **count** reaches the ledger.
2. **`notice_workflow()` writes instead of only speaking.** When `repeated()` crosses the
   threshold, upsert a candidate keyed on the signature sequence, carrying `observed:` and
   `last_seen:`. Speak once as it does today; the difference is that the finding now survives.
3. **The nudge** — once per session, marker file in `logs/`, silent when a session record dated
   today exists, silent when off. A nudge that gets tuned out is worse than none.
4. **One skill, not four.** Extend `capture`/`remember`, or add a single classifying `/chamnan:note`
   — decide by reading the existing SKILL.md files. The owner has eight skills and invokes
   approximately none; the answer is not nine unless the classification genuinely cannot live in an
   existing skill.

**Tests:** candidate round-trips with provenance intact · unknown provenance rejected at write time,
not silently stored · the same sequence twice produces one candidate with `observed: 2`, never two
files · nudge fires at most once · nudge silent when today has a record · candidates counted by the
ledger and never injected as knowledge.

**Verify:** suite green, then work one real session and confirm the nudge appears once, early
enough to act on. **STOP.**

---

#### Stage 4 — Inventory, metadata, and the 1.4.0 defects ⬜

**Files:** `bin/chamnan-report`, `lib/memory.py`, `lib/milestones.py`, `hooks/session_start.py`,
`lib/ledger.py`, `tests/run_tests.py`

1. **Knowledge inventory** in `chamnan-report` — store / entries / last written, printing zeros,
   plus *"N of your M lessons name no file in this repository"*. Reuses `lib/ledger.py`.
2. **`as-of` stamped automatically** on every memory entry at write time. `memory/` carries no date
   anywhere today; this is the prerequisite for 1.6.0's aging and costs the owner nothing.
3. **`Provenance:`** on memory entries, same enum as candidates.
4. **`state_token_budget: 1700`** replacing `MAX_STATE_CHARS`, **with a visible truncation marker**.
   The marker matters more than the number.
5. **The four defects:** `milestones._ENTRY` en-dash · `render_titles()` 120-char cap ·
   `describe()` first-sentence fallback · the truncation marker above.

**Tests:** one per fix, both directions. The en-dash test must include em-dash and hyphen entries
that still parse.

**Verify:** suite green; run `chamnan-report` against the live workspace and read it. **STOP.**

---

#### Stage 5 — Release 1.5.0 ⬜
Version bump · README covering the new lines, the candidate flow, and **the honest ceiling**
(chamnan still depends on someone choosing to record; what changed is that not recording is now
visible) · full suite green · **local commit only, GitHub waits for the owner's explicit word** ·
no `Co-Authored-By` trailer. **STOP.**

---

### 1.5.1 — Candidate Intelligence · *see what should be learned*

Gated: **do not start unless Stage 1–4 produced non-zero counters.** If the ledger still reads
`0 records` after a month of real use, the pipeline has no input and this release has nothing to be
intelligent about.

| # | Stage | What |
|---|---|---|
| 6 | Candidate dedup and counters | `observed: N`, `last_seen:`, exact-match on normalised signature sequences. Upsert, never a second file. **STOP.** |
| 7 | The review CLI | `chamnan-candidates`: list, `confirm`, `reject`, `edit`. **Solve invocation as well as output** — `bin/` is not on PATH and a confirm step that takes more than a few seconds will not be used. **STOP.** |
| 8 | Promotion → Skill or Tool | Confirm sends a candidate to `skills/` (a procedure) or `tools/` (a script), reusing `chamnan-promote`'s machinery. The classifier **suggests**; the owner decides. Merges Miki's 1.5.2 · 1. **STOP.** |
| 9 | Release 1.5.1 | Local commit only. **STOP.** |

---

### 1.5.2 — Feedback and Measurement · *did it help*

| # | Stage | What |
|---|---|---|
| 10 | Tool failure feedback | A promoted **tool** exiting non-zero is recorded against it; repeated failure flags it quietly for review or demotion to candidate. **Skills are out of scope and the README must say so** — nothing logs that a skill was read, and no hook can see whether following it went badly. **STOP.** |
| 11 | Usage counts | *"`chamnan-map` ran 14 times this month"*, counted from `commands.jsonl`. **Counts, never a savings figure** — a tokens-saved number would be invented, and this project already retired an "Engineer Scoreboard" for measuring what is easy rather than what matters. **STOP.** |
| 12 | Release 1.5.2 | Local commit only. **STOP.** |

---

### 1.6.0 — The Intelligence · *context in time and place*

Gated on 1.5.x producing a corpus. Design already argued and recorded in the concept document;
re-read it before starting, and re-check its assumptions against what 1.5.x actually accumulated.

| # | Stage | What |
|---|---|---|
| 13 | Timeline | One file per thread. The canonical-vocabulary problem is solved by making threading a **pick from a declared list**, not a string match. **STOP.** |
| 14 | Knowledge Aging | Compared against `environments.md`'s declared versions — never a clock. Ships only if that file is shown to be *maintained*; a false all-clear from an unmaintained oracle is worse than shipping nothing. **STOP.** |
| 15 | Environment Awareness | Advisory by default. Verify `permissionDecision: "ask"` reaches the prompt under `defaultMode: "auto"` **before writing the guard** — and note that `Bash(python3 *)` is allowlisted on this machine, so the one command family that skips confirmation is the one the guard cannot parse. **STOP.** |
| 16 | Release 1.6.0 | Local commit only. **STOP.** |

---

## 5. Standing constraints — do not violate these

- **A hook cannot see conversation content.** Anything claiming automatic knowledge capture from a
  hook is proposing to write a log and call it memory. `lib/sessions.py`'s docstring says so.
- **Markdown is the truth.** Any index must be regenerable and deletable without loss.
- **No new runtime dependency, no always-on process, no network call, no subprocess in a hook.**
- **Never open a credential file.** `redact.is_never_opened` exists to make that impossible.
- **Backward compatible.** A 1.4.0 workspace must keep working with no migration that can fail.
  Every new field is additive; a missing field means "not recorded", never an error.
- **Injection budget is small.** Measured live: 6,901 characters / ~2,875 tokens today. Every new
  section is `""` until the store it reads has content — `section()` already returns `""` for an
  empty body.
- Tests use a plain `check(name, condition)` counter. No pytest, no dependencies.

## 6. Blocked on the owner

- **The installed plugin is 0.1.4**, not 1.4.0. Its pre-fix two-pass `find_root` resolves a nested
  checkout to the **outer** repository and overwrites its `MAP.md`. Everything in this plan is
  written against the 1.4.0 source and is safe to build, but **the upgrade must land and be
  verified before 1.5.0 is installed anywhere.**
- Whether `.chamnan/` is pushed to GitHub for customer projects — decides how much of §3 Stage 3's
  candidate content can be committed.
