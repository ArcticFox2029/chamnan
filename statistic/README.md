# `statistic/` — what using this repository actually looks like

Two pages, built from `.chamnan/logs/**` and nothing else.

    python3 statistic/build_statistic.py      # writes data/ and report/data.js
    open statistic/report/index.html          # no server, no build step, no network

**Page 1 — the overview.** What kind of tokens the work is made of, what the context is made of,
when the work happens, which file kinds and which directories get touched, reading against
writing, and what the session block was built from.

**Page 2 — what fires and what breaks.** Which chamnan features actually spoke and how many
chances each had, how often the gate finds something, how many guards have proved they can fail,
the model's own repeated mistakes, which files keep being edited, and what the local model read so
a session did not have to.

## The three rules it is held to

1. **No money and no model names.** `Sum-Usage-Claude` is where spend lives; this page is about
   the work. A check in `.chamnan/tests/test_statistic_pages.py` fails if either appears.
2. **Every number names the file it came from**, in the panel, in small type. A figure with no
   source is not drawn.
3. **A panel with no data is drawn greyed out with the reason** — never omitted. An empty panel
   that explains itself is how a missing recorder gets built; a missing panel is how it stays
   missing.

## What it deliberately does not claim

It does not say "chamnan saved X tokens". Nothing here knows what a session without chamnan would
have cost — the 2026-09-22 comparison recorded that there is no way to measure it on one machine
with one person's work. What is measurable is **what was sent out**, and that is what is drawn.
