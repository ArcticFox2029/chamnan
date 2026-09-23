# `statistic/` — what using this repository actually looks like

Two pages, built from `.chamnan/logs/**` and nothing else.

    python3 statistic/build_statistic.py      # writes data/ and report/data.js
    open statistic/report/index.html          # no server, no build step, no network

**Page 1 — impact.** What is different with the plugin and without it, counted as events; the
period's activity; what kind of tokens the work is made of; what this repository puts in front of
every session; and the block the plugin injects.

**Page 2 — features.** Which features actually spoke and how many chances each had, how many
guards have proved they can fail, what the gate finds, and the model's own repeated mistakes.

**Page 3 — usage.** When the work happens, reading against writing, which file kinds and which
directories get touched, which files keep being edited, and what the local model read so a session
did not have to.

**English is the primary language and Thai is the second line**, smaller, under it.

## Day or month, and twelve months of it

The picker in the top right is a popover: choose `month` to scan, `day` to drill in. Every page
reads the same `?grain=&at=` from the URL, so a period stays chosen while you move between them.
**Twelve months is the ceiling** — a dashboard that grows without bound becomes the thing it was
measuring.

## The three rules it is held to

1. **No money, no model names, no vendor.** This plugin does not know which LLM anybody runs,
   whether it is local, or what any of it is charged at — so a page that implies one vendor's
   economics is wrong for every reader who uses another. The first version carried a `rate`
   column (0.1x, 5x); those are one vendor's ratios and they are gone. What is true everywhere is
   the SPLIT between kinds of token. A check in `.chamnan/tests/test_statistic_pages.py` fails if
   a price, a currency or a model name appears.
2. **Every number names the file it came from**, in the panel, in small type. A figure with no
   source is not drawn.
3. **A panel with no data is drawn greyed out with the reason** — never omitted. An empty panel
   that explains itself is how a missing recorder gets built; a missing panel is how it stays
   missing.

## What it deliberately does not claim

It does not say "chamnan saved X tokens". Nothing here knows what a session without chamnan would
have cost — the 2026-09-22 comparison recorded that there is no way to measure it on one machine
with one person's work. What is measurable is **what was sent out**, and that is what is drawn.
