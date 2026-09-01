# Evidence

Every number this project quotes, where it came from, and — for the ones that changed the code —
what changed and what did not.

Two kinds of claim appear here and they are kept apart deliberately:

- **Published** — measured by someone else, cited, and used to decide something. chamnan did not
  measure it and does not claim to have.
- **Measured here** — measured on this repository or the plugin's own corpus, with the command that
  produces it, so it can be re-run and disagreed with.

**Findings that argue against this project are in the same tables as the ones that support it.**
That is the point of the page. A tool that only cites what flatters it is advertising.

---

## 1. What a context file actually buys

| | |
|---|---|
| human-written context files | **+4%** task success |
| LLM-generated context files | **−2%** |
| any context file | **+20%** cost |
| 288-attempt study, July 2026 | **no measurable correctness gain**; **−29%** median runtime, **−17%** output tokens |

**So the claim on the front page is efficiency, not correctness**, and it is stated that way.

**The finding that argues against the flagship feature.** Architectural overviews were measured
*increasing inference cost and encouraging broader file traversal without improving task success*.
Restating a README hurts. Longer context files hurt, because an agent follows some instructions and
ignores others and the inconsistency is worse than no file. What measurably helps is narrower: tool
choices that diverge from defaults, non-obvious test configuration, and constraints not apparent
from reading the code.

**What follows from it, and both were already true.** The index is budgeted, rolled up, and is the
**first section dropped** when the byte ceiling binds — while `memory/rules/`, the session handoff
and recorded procedures are the last. And `rules/`, `skills/` and `decisions/` are precisely the
"constraints not apparent from the code" category.

Sources: DAIR.AI's AGENTS.md evaluation; Generative Labs' analysis; [arXiv:2603.22744](https://arxiv.org/pdf/2603.22744).

---

## 2. The gap a bigger model does not close

| | |
|---|---|
| hallucinated package names, 576,000 samples / 16 models | **5.2%** Python, **21.7%** JavaScript |
| **hallucinated project-specific APIs** | **85.25%** |

Third-party libraries are all over the training data; your repository's names are not in it at all.
A larger model cannot know a name it has never seen.

**Measured here:** `MAP.md` answers **51.1%** of the identifiers this repository's sessions actually
searched for, and its claims about the tree check out at **2,329 of 2,329**.

**Bounded honestly:** the 85.25% is someone else's measurement of the gap, not a measurement of
chamnan closing it. No before/after invented-identifier rate has been measured here.

Sources: [arXiv:2505.05057](https://arxiv.org/pdf/2505.05057), [arXiv:2601.19106](https://arxiv.org/html/2601.19106v1), [arXiv:2502.18468](https://arxiv.org/pdf/2502.18468).

---

## 3. The host truncates a hook at 10,000 bytes

| | |
|---|---|
| **published** | Claude Code replaces a `SessionStart` hook's stdout above **10,000 bytes** with its first **2,048** plus a file path, from **v2.1.88** |
| **measured here** | **47 of 120** recorded injections truncated, each losing **77–86%** |

**The bracket came before the citation.** The largest delivery that arrived whole was **9,690
bytes**; the smallest that did not was **10,293**. That was derived from local transcripts, and only
then confirmed against [#70460](https://github.com/anthropics/claude-code/issues/70460) and
[#44086](https://github.com/anthropics/claude-code/issues/44086).

**Why the token budgets could not see it.** `index_token_budget` (3,000) plus `state_token_budget`
(1,700) is **11,501 bytes** on real index text — over the cap on their own, before any other
section. They are measured in a different unit from the cut.

**What changed.** `output_byte_ceiling`, default 9,000, enforced where the block is printed.
Resolution is spent before sections are; a section too large to fit is trimmed rather than dropped;
each drop is named with the file to read it in. Related: [#23948](https://github.com/anthropics/claude-code/issues/23948).

---

## 4. Position inside the block

| | |
|---|---|
| mid-prompt rules | lose **30–50%** of their compliance |
| content at the beginning | used correctly in about **73%** of positionally-sensitive cases |
| instruction adherence, multi-turn | **39%** worse, **112%** less reliable than single-turn; o1-preview **88% → 71%** by turn three |
| periodic re-injection of a whole block | **does not** restore adherence — *"late textual access alone is insufficient"* |
| a short, single-purpose message at the decision point | does |

chamnan emitted the architecture index — pure data — in the primacy slot and the repository's own
rules in the middle: the worst available arrangement of those two.

**What changed.** `fit.reorder()` moves rules and reply style to the front and the session handoff to
the back. It moves **blocks**, so a section's footnotes travel with it. **Cost: 0 bytes** — the block
measured 8,912 before and after. **No timer was added, and none will be**: the negative result above
is why.

Sources: [arXiv:2510.10276](https://arxiv.org/pdf/2510.10276), [arXiv:2502.13729](https://arxiv.org/pdf/2502.13729), [arXiv:2605.12922](https://arxiv.org/pdf/2605.12922), [arXiv:2505.06120](https://arxiv.org/pdf/2505.06120), Laban et al. 2025, Multi-IF.

---

## 5. Where an index belongs in the search order

| | |
|---|---|
| ripgrep, average | **< 0.02s** |
| indexed baselines | **3–7s**, over **50s** on a 754k-line repository |
| LSP vs grep, reference-finding | **1.00** vs **0.76** precision |
| LSP on **localization** | costs **more** tokens, not fewer |

Working order is lexical → structural → repo map, the map only when the query is conceptual.
**chamnan is the third layer and does not try to be the first two** — hence no vector store, no
embedding model, no index server, and a `MAP.md` that tells the reader to grep it rather than read
it.

**Measured here:** across this repository's transcripts, the `Grep` tool was called **0** times and
`Bash` **23,847** — all searching goes through `grep`/`rg` in a shell. Of the identifiers those
searches named, the **injected block** answers **3.2%** and **`MAP.md` answers 51.1%**. The map earns
its keep on disk, not in the injection.

Sources: [arXiv:2601.23254](https://arxiv.org/html/2601.23254v2), [arXiv:2608.13568](https://arxiv.org/html/2608.13568), [arXiv:2605.15184](https://arxiv.org/html/2605.15184v1).

---

## 6. What a compaction destroys, and what an index must not

| | |
|---|---|
| fact recovery through a summarization pass | about **63%** |
| what goes first | **identifiers** — `src/auth.ts:52` returns as "the auth middleware file" |
| dead documentation references, top-1000 GitHub projects | **28.9%**, average **4.7 years** stale |
| a *wrong* map versus no map | agent regressions **9.94%** vs **6.08%** |

**Measured here:** `STATE.md` carried **189** numbers and dates against **13** quoted paths and **0**
symbols — dense in what cannot be navigated with, thin in what can. `skills/resume` and
`skills/remember` now say to write the path, the symbol, the command, the commit.

**And the staleness question was answered rather than assumed.** Replaying the last 50 commits: the
index a session was handed named **74.6%** of the files those commits touched, but **0 of 264 paths
it named had disappeared.** A chamnan map is regenerated wholesale rather than patched, so it cannot
drift into being *wrong*; it can only fall behind. It is not confidently wrong, it is blind — and
blind where the work is. The warning now gives a count and names files instead of an age.

---

## 7. Validation, and what it is worth

| | |
|---|---|
| unvalidated LLM-written repository context | **−3%** success, **+20%** cost |
| guidance validated by probing | **25.5% → 33.0%** resolve on SWE-bench Verified, p<0.001; evaluable patches **41.7% → 56.2%** |

**Measured here:** `tools/map_claim_check.py` verifies the index's assertions against the tree —
paths, line counts, functions, classes, symbols. **2,329 of 2,329 true.** Two defects were found by
writing it: every line count was over by exactly one (`count("\n") + 1` counts the empty string after
a trailing newline, 276 of 277 entries affected), and `index_is_behind` filtered differently from
`mapper`, so a nested checkout made the staleness warning permanently on — which is the same as
absent on the day it is true.

Source: [arXiv:2606.20512](https://arxiv.org/abs/2606.20512) (Probe-and-Refine); ETH Zurich counterpoint.

---

## 8. Secrets

| | |
|---|---|
| chamnan's redactor, **before** | **66.7%** recall / **81.8%** precision |
| chamnan's redactor, **after** | **96.3%** recall / **100%** precision |
| corpus | 27 secret shapes, 17 ordinary strings that must survive |
| **the ceiling it cannot reach** | verification by live API call: TruffleHog **6% → 90%** precision |

**The worst bug was not a miss.** `Authorization: Bearer <token>` matched the bare-assignment rule,
which captured the word `Bearer` as the value and replaced *that* — a line that read as redacted with
the credential intact beneath it. A miss is recoverable because a reviewer can still see the secret;
a miss dressed as a hit is not. Also: a PGP secret key block ends `PRIVATE KEY BLOCK-----` and the
pattern was anchored on `PRIVATE KEY-----`.

**The ceiling is permanent.** Verification means a network call, and chamnan makes none at runtime.

---

## 9. Prompt injection

| variant | attack success rate |
|---|---|
| **delimiting** — what chamnan's `[repo:nonce]` fence is | about a **halving** |
| datamarking | ~50% → **under 3%** |
| encoding | **≈0%** |
| any of them, against an adaptive attacker | **>95%** ASR |

The two stronger variants work by making the untrusted text unreadable as prose. chamnan's untrusted
text is a code map whose purpose is to be read, so neither is available.

**The claim is therefore narrow and is stated that way: the fence answers *who said this*.** It is
not a defence. A poisoned comment arrives labelled as a poisoned comment.

Sources: [arXiv:2403.14720](https://arxiv.org/abs/2403.14720), [arXiv:2510.09023](https://arxiv.org/pdf/2510.09023).

---

## 10. Things measured and then deliberately **not** built

The list matters as much as the changes. Each of these was a plausible feature with a number
attached that said no.

| idea | what the measurement said |
|---|---|
| **Mark unreferenced files as dead** | Of 277 indexed files, **229 (83%)** are imported by nothing — 107 tests, 43 browser/node scripts, 42 shell entry points, 16 CLI tools. **Precision ceiling 6.1%**, i.e. at best **93.9% false positives** — worse than the static-analysis tools measured at 76–90% FP that destroy developer trust. |
| **Mine commit messages for rationale** | This repository is **95%** with a body, **81%** carrying rationale, median **1,323** characters — against a world where **44%** lack sufficient detail and **14%** are blank. A miner built on this would be tuned on the best input it will ever see. |
| **Periodic re-injection of the rules block** | Measured **not** to restore adherence. Only the decision-point form works, which chamnan already has. |
| **`llms.txt` for discovery** | **10.13%** adoption; **408 of 500M+** AI bot visits in 90 days targeted it; **no** significant correlation with citations, and removing it *improved* a prediction model. |
| **JSON-LD in the README** | GitHub strips `<script>` from rendered markdown. It would be invisible. |
| **Put symbol names into the injected roll-up** | `MAP.md` already answers **51.1%** of searched identifiers for **zero injected bytes**. |
| **Incremental index rebuilds** | The published 8.7×/25.4× speedups are dominated by **embedding API cost**. chamnan has no embeddings; a full rebuild is **11.9 seconds** and free — and rebuilding wholesale is what makes the map unable to drift into being wrong. |
| **Rank the injected tools list** | This repository has no `tools/index.json`, so the section never fires. Ranking an empty list is how a zero becomes a fake finding. |

---

## 11. Two cautions about reading any of this

**A zero is a bound, not a rate.** Ten quiet days with no observed use bounds the rate at
`1 − 0.05^(1/n)` = **0.259/day** — as much as 7.8 uses a month. It rules out daily use and nothing
below it. A design argument in an earlier release note leaned on such a zero; it no longer does.

**And the strongest caution is about the author.** A randomised controlled trial with **16
experienced open-source developers on 246 real tasks** found them **19% slower** with AI available
while estimating they had been **20% faster** — a **39-point gap** between measured and perceived
outcome. Erroneous automated advice is followed at a **26% higher** rate, and surface polish disarms
scepticism. A tidy generated index is surface polish.

That gap is why the headline A/B is still listed as **not run** rather than replaced by a judgement
that this feels better. It needs roughly eight more working sessions before it has the power to
detect the effect size the literature reports, and until it runs, chamnan's effect on this
repository is unmeasured.

Sources: [arXiv:2605.23130](https://arxiv.org/pdf/2605.23130); METR-style RCT; 2012 automation-bias systematic review.

---

## How to disagree with this page

Everything under "measured here" is reproducible:

```bash
python3 tests/run_tests.py          # the suite these numbers are pinned by
chamnan-map --explain               # index size, coverage, budget arithmetic
```

The per-topic working notes, including the searches that returned nothing, live in the development
repository under `.chamnan/state/` — kept so that a later round skips ground already covered rather
than re-walking it.
