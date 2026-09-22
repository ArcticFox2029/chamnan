---
description: A decision procedure for any gate, check or judgement — name the questions before looking, answer each from counted evidence, set one threshold per action by what being wrong costs, and hand the uncertain ones to a person. Use when deciding whether something is safe, done, duplicated, stale, or worth doing.
---

# Decide from counted evidence, not from an impression

**Code calculates. A model reasons. This decides.** The pattern is borrowed openly from the
decision models now being built for agent systems, and one thing is deliberately different: the
confidence here does **not** come from a model. It comes from evidence you counted. Nothing in this
procedure calls out, and nothing about it needs a network.

That difference is the whole reason it can be trusted offline — and the reason step 3 is the one
that cannot be skipped.

---

## 1 · Name the decision, and what being wrong costs

Write both before looking at anything. The cost sets the threshold; there is no global one.

> *"Is this file safe to edit?" Being wrong means the edit is silently discarded.*
> *"Does this component already exist?" Being wrong means a wasted afternoon, recoverable.*
> *"Is this a credential?" Being wrong once is the whole product failing.*

**One threshold per action, scaled to that cost.** A single number for the whole system is how a
gate ends up too strict for cheap mistakes and too loose for expensive ones.

## 2 · Write the questions before you look

Each question gets a **type**, and the type is one of three:

| type | shape | example |
|---|---|---|
| **choice** | one value from a set you named | generated · hand-written · cannot tell |
| **count** | a number, with what it is out of | 26 of 28 planted credentials caught |
| **yes/no** | with the evidence that decides it | is a test command in this session's log? |

**Never a free-prose answer.** Prose cannot be thresholded, cannot be compared to last week's, and
cannot be checked by anybody else. If a question can only be answered in prose, it is not a
decision — it is a discussion, and it belongs with a person.

## 3 · Answer each from something you counted — and record the count

This is the step that makes the rest honest.

> **A number you did not count is an impression wearing a number's clothes.**

Where the counts come from, offline:

| question shape | what counts it |
|---|---|
| is this name used anywhere else | `chamnan-where <name>` — uses, not lines that mention it |
| what breaks if this changes | `chamnan-impact <file>` — importers, covering tests |
| has this been decided before | `chamnan-recall <subject>` |
| does the behaviour hold | the check, run — and **seen to fail** before it is believed |
| does it hold on somebody else's code | the corpus, with the count it returns |

**Record what you EXAMINED, not only what you found.** "No references" from a scan that skipped a
file is not the same answer as "no references", and the difference is invisible unless the skipped
count is on the line. Every report in this procedure carries both numbers.

## 4 · Three bands, and the middle one is not a failure

| band | what happens |
|---|---|
| the evidence is complete and agrees | **act** |
| the evidence is partial, or two signals disagree | **say so and continue** — name what is missing |
| the evidence cannot be counted, or being wrong is expensive | **hand it to a person** |

**The bottom band is an answer.** Routing a decision to a human is the procedure working, not the
procedure giving up — and pretending to a number you could not count is the only real failure here.

## 5 · Test the threshold before trusting it

A threshold nobody has tested is a guess with a number on it.

Find a case where the answer is already known and check the band lands right. Where there is no
such case, **build one**: a repository that has the defect, a file that names a path that has gone.
Then break it the other way and confirm the band moves.

**A credential-shaped fixture is the one case with a hard boundary, and it is not a style rule.**
Build it in a throwaway directory outside any repository, or in a corpus repository that exists for
the purpose — **never in a tracked file, and never anything that can be pushed.** GitHub's secret
scanning forwards a live-looking key to the provider within minutes of it reaching a remote, and the
account that owns it is marked. A test fixture is not worth that, and the damage is not yours to
undo. If a threshold can only be tested with a real-looking key, test it against a corpus somebody
built for testing rather than against the repository you are working in.

> A threshold that has never been seen to reject anything has not been tested, only run.

## 6 · Log the decision, then compare it with what actually happened

Write down the question, the count, the band and what was done. Later, check whether the decision
was right. **A threshold that is never compared with the outcome drifts silently**, and the drift is
only visible against a record.

---

## What this is not

**It is not a gate that blocks.** Every decision here ends in an action, a notice, or a person —
never in a refusal the reader cannot override. A tool that stops work on a number it could not
fully justify will be turned off, and then none of its decisions matter.

**It is not for choices with one obvious answer.** Running six steps on something a glance settles
is overhead dressed as rigour.

**It is not a confidence generator.** If step 3 has nothing to count, the honest output is the
bottom band. Inventing a number to get past it is the one thing this procedure exists to prevent.
