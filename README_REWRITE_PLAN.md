# README rewrite plan — 1.1/1.2 explanation → the 1.3 product story

A plan. `README.md` is untouched.

**Supersedes the earlier draft of this file.** That version opened by recording that five of the
six 1.3 features did not exist and recommending they be built first. They were. Everything below
now describes shipped behaviour, and the *Planned* / *Roadmap* sections that draft needed are gone.

---

## 0. What is actually shipped

Checked against the repository, because the whole plan depends on it:

| | |
|---|---|
| Modules | `sessions.py` · `memory.py` · `impact.py` · `workflows.py` · `milestones.py`, alongside the existing `mapper` · `schema` · `catalogs` · `deploy` · `assets` · `redact` · `rollup` · `tokens` · `peek` · `workspace` |
| Skills | **8** — `bootstrap` `capture` `promote` `remap` `report` **`resume`** **`remember`** **`milestone`** |
| Config | **15 keys**, up from 11 |
| Tests | **378**, up from 220 |
| 1.2 docs | `docs/architecture.md` · `docs/data-flow.md` · `docs/verification.md` |
| Measured injection, all six features populated | **507 tokens** |

Everything in this plan can be written as present tense.

---

## 1. Current README analysis

741 lines, 24 sections.

### Stays unchanged

| Section | Why |
|---|---|
| **Requirements** | Graded honestly — macOS tested, Linux expected-not-tested, Windows neither. Rewriting risks softening a distinction that was drawn carefully. |
| **Secrets** | Holds the "not a sandbox" statement. **`docs/data-flow.md` quotes it verbatim, so any edit here silently breaks that page.** |
| **The chaos test** | Measured, with provenance labels. Re-measure or leave alone; never reword. |
| **Evidence** | Same. |
| **Limitations** · **Troubleshooting** · **Update, disable, uninstall** | Trust assets. Every quoted string in Troubleshooting is verbatim from source; every command in Update was verified against `claude plugin --help`. |
| **Bootstrap does not rewrite your code** | The tool-list-versus-prompt distinction is precise and hard-won. |
| **What it deliberately does not do** | Directly serves the "no AI hype" constraint. |
| **Read this before installing** | The amortisation argument is *strengthened* by 1.3, not replaced. Keep the two-question test verbatim. |

### Outdated because 1.3 exists

| Section | What is now wrong |
|---|---|
| **What it does** | An 11-row feature table listing Index, Data model, API surface, Configuration, Deployment, Stored material, State, Procedures, Tools, Measurement, Routing. It has no Impact, Resume, Memory, Workflows or Milestones, and its flat shape cannot absorb five more rows without becoming a wall. **Reorganise into four capabilities** — §4. |
| **The problem it aims at** | Opens on a token-cost table and a comparison against an output-compression plugin. That framing is now the smaller half of what the tool does. **Reframe** — §2. |
| **Configuration** | Documents 11 keys. There are **15**. Four rows to add: `resume`, `session_retention_days`, `memory`, `milestones`. |
| **Commands** | Lists five slash commands. There are **eight**. |
| **Quick start → What it creates** | The `.chamnan/` tree shows six entries. It now also has `sessions/`, `memory/{decisions,lessons,rules}/` and `milestones.md`. |
| **Tests** | Says "220 checks". It is **378**. |
| **One file, only what applies, and a ceiling** | Still true about `MAP.md`, but the ceiling argument now covers more stores. Needs a sentence, not a rewrite. |
| **More documentation** | Four rows; unchanged unless new docs appear. |

### Concepts needing reframing

1. **The headline.** "Makes a repository know itself, so an agent stops rediscovering it" →
   *…and preserve the engineering context built while you work with it*. **`plugin.json`'s `description` carries the old wording
   too, and the marketplace listing reads from that, not the README.**
2. **Token savings as pitch → as consequence.** §2.
3. **Feature list → capability model.** §4.
4. **Amortisation, which the README already argues, becomes the spine.** §3.

---

## 2. New product positioning

| | |
|---|---|
| From | "chamnan saves tokens" |
| To | "chamnan reduces repeated discovery — and the token savings follow" |

The four things an agent should stop rediscovering, which is the section's actual content:

- where code lives
- why decisions were made
- how previous problems were solved
- what happened in the previous session

**Keep every measured number.** The 91.2% / 8.8% split and the comparison against an
output-compression plugin are the most credible content in the document. They move down one
section — behind the discovery argument — not into an appendix. Demoting them further would trade
the README's strongest asset for a better story.

There is a real argument for this beyond positioning: the current opening invites comparison
against token-compression tools, a category chamnan competes in badly and by accident.

---

## 3. Required new concepts

### 3.1 `## Agent continuity` — replaces `## The problem it aims at`, position 2

Four causes, each factual:

- a new session starts with nothing
- a long session compacts, and what was worked out is gone
- knowledge discovered *during* the work is never written down
- the repository itself does not explain its own accumulated experience

Then the mechanism, which is the whole product in one line: **chamnan externalises what the agent
discovers into repository artifacts, so the next session reads instead of rediscovering.**

Ends with the two-kinds-of-cost table (§3.3).

### 3.2 `## The compounding effect` — new, position 3

| | |
|---|---|
| Day 1 | `MAP.md` |
| Day 30 | `+ STATE.md`, procedures, tools, session records |
| Day 180 | `+ decisions`, `+ lessons`, `+ rules`, `+ milestones`, `+ workflows` |

**Every artifact named here exists.** The wording is *accumulates repository-specific knowledge* —
never "learns", never "gets smarter".

The honest counterweight already in the README stays attached: on a four-file repository this costs
more than it saves. Compounding cuts both ways and saying so is what makes the rest believable.

### 3.3 Two kinds of cost — a table inside §3.1

| | what it is | what answers it |
|---|---|---|
| **Discovery cost** | finding where things live and how they connect | `MAP.md`, **Impact** |
| **Re-solving cost** | working out again what was already worked out | procedures, tools, **memory**, **decisions**, **session records** |

Token reduction is stated as the *result* of both, not as a third row.

---

## 4. Feature mapping — replaces `## What it does`

| | today | new in 1.3 |
|---|---|---|
| **Understand** | `MAP.md` · data model · API surface · configuration · deployment · stored material | **Impact** — who depends on this file, which tests cover it |
| **Remember** | `STATE.md` | **Resume** (session records) · **Memory** (decisions, lessons, rules) |
| **Reuse** | procedures · tools · capture · promote | **Workflows** — the same commands in the same order, weeks apart |
| **Evolve** | — | **Milestones** — the handful of changes that reshaped the repository |

Each capability gets a paragraph and a table; every row is shipped, so no status labels are needed.

**Evolve needs its boundary stated in the same breath as its name:** repeated engineering work
becoming reusable repository knowledge — *not* model training, not automation of the developer.
It is a mechanism for preserving work, and the section should say so where the word "Evolve" first
appears rather than in a disclaimer further down.

---

## 5. Preserve

Listed in §1 and repeated because it is the constraint most likely to be lost in a rewrite:
**Security, Chaos Test, Evidence, Limitations, Requirements, Troubleshooting stay.** No reduction
in technical depth. Length is not the problem this rewrite solves.

---

## 6. Avoid

Never: *model training* · *learns like a human* · *permanently remembers everything* ·
*memory outside the repository* · *security sandbox* · *guarantees no leaks*.

Use: *accumulates repository-specific knowledge* · *stores repository-local artifacts* ·
*preserves useful engineering context* · *reduces repeated discovery*.

A `grep` for the banned phrases is part of §8, exactly as the 1.1.0 audit scanned for
"100% secure" and "cannot leak".

Two specific traps this release creates:

- **"Memory"** invites the reading that something persists outside the repository. Every mention
  should sit near the words *repository-local* or *committed*.
- **"Continuity"** invites the reading that the agent is continuous. It is not — the *artifacts*
  are. The section should say the session still starts from nothing and reads what was left.

---

## 7. Proposed structure

24 → 26 sections. Moves are marked; everything else keeps its position.

| # | Section | |
|---|---|---|
| 1 | Read this before installing | keep |
| 2 | **Agent continuity** | **replaces** *The problem it aims at* |
| 3 | **The compounding effect** | **new** |
| 4 | **What it does — Understand · Remember · Reuse · Evolve** | **reorganised** |
| 5 | Who this is for | keep, +1 line (§7.1) |
| 6 | Who this is not for | keep |
| 7 | Requirements | keep |
| 8 | Quick start | update `### What it creates` |
| 9 | Bootstrap does not rewrite your code | keep |
| 10 | **What's new in 1.3** | **new**, after Quick start |
| 11–14 | Language · One file… · Keeping the index fresh · Bulk reads | keep, grouped under **How it works** |
| 15 | Configuration | 11 → 15 rows |
| 16 | Commands | 5 → 8 slash commands |
| 17 | Secrets | **keep unchanged** |
| 18 | Evidence | keep |
| 19 | The chaos test | keep |
| 20 | Troubleshooting | keep |
| 21 | Update, disable, uninstall | keep |
| 22 | What it deliberately does not do | keep |
| 23 | Limitations | keep |
| 24 | Tests | 220 → 378 |
| 25 | More documentation | keep |
| 26 | License | keep |

### 7.1 Audience addition

One line to *Who this is for*: developers who stay on the same repository for weeks or months,
repeatedly extend the same system, and want an agent that accumulates context about it.

Consistent with the existing framing rather than a change of it — the README already says chamnan
is for "one main folder you work in over and over".

---

## 8. Validation the rewrite must pass

Reusing the 1.1.0 audit's checks, plus three for this release:

1. Every documented command exists in `bin/` or `skills/` — now **8** slash commands.
2. Config table matches `lib/workspace.py:DEFAULT_CONFIG` — now **15** keys.
3. No banned phrases (§6).
4. No absolute security claims.
5. All internal anchors and relative links resolve.
6. Test count matches a live run — **378**.
7. **New:** every capability named under Understand/Remember/Reuse/Evolve has a module behind it.
8. **New:** the Secrets section still matches `docs/data-flow.md` character for character.
9. **New:** every `.chamnan/` path named is one `ensure()` creates.

---

## 9. Sequence

1. Execute this plan as a single README pass.
2. Update `plugin.json`'s `description` to match the new headline (§1).
3. Consider whether `docs/architecture.md` needs its diagram extended — it shows MAP/STATE/
   procedures/tools and now omits four stores. **Its own task, not part of the README pass.**
4. Run the §8 checks.
5. Version 1.3.0, tag, release.

---

**Status: plan only. `README.md` has not been modified.**
