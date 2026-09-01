# Keeping these pages honest

Thirty-two translated pages, and a rule that decides when each one has to be touched.

## The one thing that makes this maintainable

**No translated page contains a number.** Not a token count, not a percentage, not a benchmark
result. Every measurement lives in the English `README.md`, and every translated page links to it.

That is not tidiness, it is the whole design. Measured across large open-source repositories: once
a documentation translation is merged, the English source goes on to receive a median of **8.5
more commits in six months while the translation receives a median of 0**, with a maximum observed
gap of 166 commits ([arXiv:2508.02497](https://arxiv.org/abs/2508.02497), ICSE-NIER 2026). In small
repositories, 6 of 17 merged translations were already behind the source at the moment they were
measured.

chamnan releases often. A translation set carrying release-specific numbers would be wrong within
one cycle, and a wrong translation is worse than an absent one because it still reads as current.
So the translated pages carry only what does not change: what this is, the problem it solves, how
to install it, what to know before installing, and where the details live.

## What that means per release

| what changed | what to update |
|---|---|
| a measurement, a benchmark, a version number, a new finding | **`README.md` only.** No translated page mentions any of these. |
| the install command | `README.md`, and the fenced block in every translated page — it is the one literal shared with them |
| what chamnan *is*, or a new limitation a reader should know before installing | `README.md`, then `docs/i18n/README.th.md`, then the rest |
| a new language added | `docs/i18n/*.md` — every page carries the full navigation row |

**In the ordinary case a release touches one document.** That is the point of the rule above. If a
translated page starts needing an edit every release, something numeric has leaked into it — take
it back out rather than accepting the maintenance.

## Thai is the second primary language

English and Thai are the two the author writes directly; the other thirty are translations of the
same short page. Thai still carries no numbers, for the same reason as the rest — it does not need
a per-release edit, and it should not acquire one.

## Checking

A page is correct if it still describes chamnan truthfully. It does not go stale from a release,
by construction. If you are unsure whether a change belongs in the translations, ask whether the
sentence would have to be rewritten after the next `chamnan-map` run — if yes, it belongs in
`README.md` instead.
