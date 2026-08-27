# chamnan 1.5.0 — build plan

> **Read this first if you are a new session, or a different account picking this up.**
> Everything needed to continue is in this file. Nothing important lives only in a conversation.
> Work through the stages in order. Each stage ends with a verification block and a STOP.
> The owner approves each stage before the next one starts.

**Status:** Stage 0 complete. Awaiting the owner's go for Stage 1.
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

## 3. Stages

Each stage is independently completable. A handoff can happen at any stage boundary.

### Stage 0 — Plan and handoff  ✅ COMPLETE

- [x] This file exists and is complete enough to continue from
- [x] `.chamnan/STATE.md` points at it
- **Verify:** a new session reading `.chamnan/STATE.md` finds this plan.

---

### Stage 1 — The two lines  ⬜ NOT STARTED

The cheapest and highest-expected-value change in the release. ~240 characters per session.

**Files:** `hooks/session_start.py`, `tests/run_tests.py`

1. **Write-skills line.** A new section, emitted unconditionally when the workspace exists, naming
   the plugin's write skills. Gate on nothing — an agent that cannot write is the failure being
   fixed. Roughly:

   ```
   _Write with `/chamnan:resume` (session record), `/chamnan:remember` (decision, lesson or rule),
   `/chamnan:milestone`, `/chamnan:capture` (a procedure worth keeping).
   Nothing else writes to this workspace._
   ```

   Keep it under 140 characters of payload. It must name real skills — check `skills/` before
   writing the list, and do not name a skill that does not ship.

2. **Ledger line.** One line, always emitted, ~110 characters. Counts entries per store and the age
   of the newest write. Must show **movement**, not a static number:

   ```
   _chamnan · 3 records (+2 this week) · 11 memory entries · last write 2 days ago_
   ```

   When everything is zero it says so plainly, with no exclamation and no instruction:

   ```
   _chamnan · 0 records · 0 memory entries · nothing written yet_
   ```

   Put the counting in a new `lib/ledger.py` so `chamnan-report` (Stage 4) reuses it rather than
   counting twice. Counting must be cheap: `iterdir()` and one `stat()` per store, no file reads.

**Tests to add** (`tests/run_tests.py`, plain `check(name, condition)`):
- the write-skills line names every skill that exists in `skills/` and no skill that does not
- the ledger reports 0 for an empty workspace and does not crash on a missing store
- the ledger's "+N this week" is 0, not negative or absent, when nothing is recent
- both lines stay inside their character budget
- neither line is emitted when `wsdir` does not exist (not a chamnan repo → still silent)

**Verify:** `python3 tests/run_tests.py` green, and run `hooks/session_start.py` against the live
`/Users/wasuplao/Documents/Lumin-App` workspace read-only, confirming the two lines appear and the
total injection grew by roughly 240 characters and not more.

**STOP.** Report to the owner and wait.

---

### Stage 2 — Evidence  ⬜ NOT STARTED

Make the mechanical logs rich enough that a knowledge candidate can be drafted from them.

**Files:** `hooks/scratch_watch.py`, `lib/workflows.py`, `tests/run_tests.py`

1. **Fix `signature()`'s shell-keyword bug** before anything reads the log. `do`, `done`, `then`,
   `fi`, `else`, `elif`, `esac`, `in` are not programs. Add a keyword skip-list and a test using a
   real `for f in *; do …; done` line.

2. **Add a `kind` discriminator to every record** in both logs. Without it a second record type in
   `scratch.jsonl` gets Jaccard-clustered into the repeated-script families and reported as a
   repeated script. Existing records have no `kind`; readers must treat a missing `kind` as
   `"scratch"` so the 300 records already on disk keep working.

3. **Add evidence fields** to the PostToolUse record: which tool, the file path when there is one,
   and the exit status when the payload carries one. Derive **only** from the hook payload — never
   open a credential file, never run a subprocess. Keep the record bounded; this is a hint
   generator, not an archive, and `KEEP_ENTRIES = 300` stays.

**Tests to add:**
- `for f in *.py; do echo "$f"; done` produces no signature containing `do` or `done`
- a record written by 1.4.0 (no `kind`) is still read as a scratch record
- the new fields are absent, not `null`, when the payload does not carry them
- no code path in `scratch_watch.py` opens a file outside the workspace

**Verify:** suite green; `tail` the live `commands.jsonl` after a `for` loop and confirm no shell
keyword was recorded.

**STOP.**

---

### Stage 3 — The promotion pipeline  ⬜ NOT STARTED

`evidence → candidate → human confirm → memory`. Nothing is written into `memory/` unattended.

**Files:** new `lib/candidates.py`, `hooks/scratch_watch.py`, new skill, `tests/run_tests.py`

1. **`.chamnan/candidates/` store.** One markdown file per candidate, same trailer grammar the rest
   of chamnan uses. Every candidate carries `**Provenance:**` from the closed enum. A candidate is
   never injected as knowledge — only its **count** reaches the ledger.

2. **The nudge, on PostToolUse.** When a session has crossed a substantive-work threshold and
   `sessions/` holds no record dated today, print **once** — a marker file in `logs/` enforces the
   once. Hard caps: at most one nudge per session, silent when the workspace has recorded today,
   silent when the feature is off. A nudge that gets tuned out is worse than no nudge.

3. **One skill, not four.** Extend `capture`/`remember` rather than adding a third verb, or add a
   single `/chamnan:note` that classifies. Decide by reading the existing SKILL.md files — the
   owner has eight skills and invokes approximately none, so the answer is not "make it nine"
   unless the classification genuinely cannot live in an existing skill.

**Tests to add:**
- a candidate file round-trips through the parser with its provenance intact
- an unknown provenance value is rejected at write time, not silently stored
- the nudge fires at most once per session
- the nudge does not fire when a session record dated today exists
- candidates are counted by the ledger and never injected as knowledge

**Verify:** suite green. Then a real check: work normally for one session and confirm the nudge
appears once, at a moment where acting on it is still possible.

**STOP.**

---

### Stage 4 — Inventory, metadata, and the 1.4.0 fixes  ⬜ NOT STARTED

**Files:** `bin/chamnan-report`, `lib/memory.py`, `lib/milestones.py`, `hooks/session_start.py`,
`lib/ledger.py`, `tests/run_tests.py`

1. **`chamnan-report` knowledge inventory** — store / entries / last written, as a table, printing
   zeros, plus "N of your M lessons name no file in this repository". Reuses `lib/ledger.py`.
2. **`as-of` stamped automatically** on every memory entry at write time. `memory/` carries no date
   anywhere today. Costs the user nothing and is the prerequisite for 1.6.0's aging.
3. **`Provenance:`** on memory entries, same enum as candidates.
4. **`state_token_budget: 1700`** replacing `MAX_STATE_CHARS`, **with a visible truncation marker**
   (`_…9.9k more — read .chamnan/STATE.md_`). The marker matters more than the number.
5. **The four defects** from §2: `milestones._ENTRY` en-dash, `render_titles` 120-char cap,
   `describe()` first-sentence fallback.

**Tests to add:** one per fix, both directions — that the fix works and that it does not
over-apply. The en-dash test must include an em-dash and a hyphen entry that still parse.

**Verify:** suite green. Run `chamnan-report` against the live workspace and read the output.

**STOP.**

---

### Stage 5 — Release  ⬜ NOT STARTED

1. Version bump to `1.5.0` in `.claude-plugin/plugin.json`.
2. README: the new lines, the candidate flow, and **the honest ceiling** — chamnan still depends on
   someone choosing to record; what changed is that not recording is now visible.
3. Full suite green. `python3 tests/run_tests.py`.
4. **Local commit only.** GitHub — push, release, marketplace — waits for the owner's explicit word.
   No `Co-Authored-By` trailer.

**STOP.**

---

## 4. Standing constraints — do not violate these

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

## 5. Blocked on the owner

- **The installed plugin is 0.1.4**, not 1.4.0. Its pre-fix two-pass `find_root` resolves a nested
  checkout to the **outer** repository and overwrites its `MAP.md`. Everything in this plan is
  written against the 1.4.0 source and is safe to build, but **the upgrade must land and be
  verified before 1.5.0 is installed anywhere.**
- Whether `.chamnan/` is pushed to GitHub for customer projects — decides how much of §3 Stage 3's
  candidate content can be committed.
