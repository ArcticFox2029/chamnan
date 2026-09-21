---
description: Review a change with what this repository knows about it — who depends on the file, which tests cover it, what broke here before, and what the repo has written down. Use before approving a diff, opening a PR, or when asked to review.
---

# Review it against the repository, not just against the diff

A diff shows what changed. It cannot show what depends on it, what broke here last time, or what
this repository has already decided about it. Those are the four things worth saying, and three of
them are one command.

```
chamnan-impact <each changed file>
```

That answers **who imports it**, **which tests cover it**, and **which threads name it**. Run it per
changed file, not once for the change.

## The four signals, and what each one is for

**1 · Who breaks.** The import graph. Say the number and name the surprising ones — *"six call
sites, and two are in hooks that run on every tool call"* is a review comment. *"This file is
imported"* is not.

**2 · Which tests cover it.** From the same output. If a changed file has none, that is the finding
— say so plainly, once, without turning it into a lecture about coverage.

**3 · What broke here before.** Look for a `🐛` marker on or near the changed lines. This project
writes the defect record at the line it was fixed on, so a diff that touches one is touching a line
somebody already got wrong. **A change that reverts a `🐛` line is the single most valuable thing a
review can catch**, and no diff-only reviewer can see it.

**4 · What the repository has already decided.**

```
chamnan-recall <the subject of the change>
```

If a rule, a dead end or a recorded lesson covers this, the review's job is to point at it — not to
re-argue it.

## When the workspace is new

A fresh workspace has no `🐛` records and no recorded rules. **Report the signals you have and stop.**
Two of four is still two more than a diff gives, and inventing the other two is worse than missing
them.

## What not to say

**Do not restate the diff.** The reader has it. Every line of the review should be something they
could not have got by reading the change themselves — which is exactly the four signals above.

**Do not report a stale index as fact.** `chamnan-impact` says when the map is behind the code and
tells you to run `chamnan-map`. That warning is part of the answer; passing its conclusions on
without it turns "nothing references this" into a false all-clear.

**Do not manufacture severity.** If the four signals come back quiet, the change is quiet. Saying so
in one line is a complete review.
