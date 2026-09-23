# The outcome pilot's scoring, written before the first task runs

🎯 [1.31 queue item 4, agreed with a second reader 2026-09-23] **This pilot does not measure
whether chamnan wins. It measures whether the METHOD of measuring is reliable.** If the scoring
turns out to be ambiguous, or a replay is not comparable, that is the result — found for the price
of ten tasks instead of a hundred.

The rubric is fixed here, before any task has been executed, because a rubric written after seeing
the outputs scores the outputs it has already seen.

## The only questions asked

Never *"which answer is better"*. Only questions with a forced answer:

| question | answers |
|---|---|
| Changed the correct file? | yes · no · **unknown** |
| Satisfied the required behaviour? | yes · no · **unknown** |
| Introduced a regression? | yes · no · **unknown** |
| Repeated a recorded rejected decision? | yes · no · **unknown** |
| Needed human correction? | 0 · 1 · 2+ · **unknown** |

`unknown` is not a middle grade. It means the evidence does not decide, and **any `unknown` makes
the whole task INVALID** — which is the rule that keeps a scorer from quietly inventing a verdict.

## The four outcomes

```
PASS     matches ground truth · violates no constraint · regression command passes
PARTIAL  direction correct · a STATED requirement missing
FAIL     wrong result · wrong file changed · regression introduced · a rejected decision repeated
INVALID  replay not comparable · environment drift · the scorer cannot decide
```

Resolution order, so two people reading the same evidence reach the same verdict:

1. any `unknown` → **INVALID**
2. environment drift recorded → **INVALID**
3. regression introduced, or wrong file changed, or a rejected decision repeated → **FAIL**
4. required behaviour not satisfied → **PARTIAL**
5. otherwise → **PASS**

A disagreement between two scorers is **INVALID**, never a forced winner. An INVALID task is not a
failure of the arm being measured; it is a failure of the measurement, and it is reported as such.

## What a task must carry to be scoreable at all

Every task declares ground truth that a machine can check:

- `must_change` — the file(s) a correct fix touches
- `must_not_change` — files a correct fix leaves alone
- `behaviour` — a command and the exit code a correct fix produces
- `regression` — a command that passed BEFORE and must still pass
- `rejected` — approaches this repository has already refused, in its own words

A task missing any of these is not run. **A benchmark that scores a task it cannot check is the
thing this rubric exists to prevent** — the same reason the question bench counts its unscored
questions separately instead of treating them as passes.
