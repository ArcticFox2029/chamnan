# Changelog

Release notes for every version. The newest release is also at the top of the
[README](README.md#whats-new-in-1312), and every one of these is on the
[releases page](https://github.com/ArcticFox2029/chamnan/releases).

Kept here rather than in the README because thirteen of them had grown to a third of that file, and
a version history is the one thing a first-time reader never needs.

**Every fix gets its entry on the day it lands**, under an **Unreleased** heading, so that whenever
a release happens its notes are assembled rather than excavated from six weeks of commit messages.
A note written from a commit log weeks later is a worse note: the reason a thing was done is in the
head of whoever did it, that day, and nowhere else. When the release goes out, that heading takes
the version number and a new empty one starts.

Nothing under **Unreleased** carries a version number, on purpose. Numbering it would put a version
in this file that no tag matches — and on the machine chamnan is developed on, the installed plugin
already reports the last released number while running newer code.

---

## Unreleased

- **`chamnan-where` is about 16% faster on a large repository.** It no longer walks the parts of a
  file whose lines never mention the name. Measured on a 1,194-file repository: 3.74 s to 3.13 s
  (median of five runs each side). The answers are unchanged: the old and new code gave identical
  results on all 15,772 symbol-and-file pairs tried.
- **Secrets written with a full-width `：` or `＝` are now redacted.** Japanese and Chinese input
  methods type these, and a secret assigned with `：` had been passing through while the same line
  with `:` was caught. No other output changed on 1,391 real files, and the corpus benchmark is unchanged.
- **Every Bash call starts about 90 ms sooner.** Before a command runs, a hook checks whether it has
  already failed here twice. It used to redact the command first on every call, which cost 166 ms of
  regex compilation. It now skips that when nothing recorded could match: 246 ms to 153 ms median.
  Its answers are unchanged: old and new agreed on all 1,378 real commands tried.
- **`chamnan-recall` indexes only chamnan's own stores.** It also looked for two named files that are
  not part of the workspace layout chamnan creates; that lookup, and the section splitting it
  needed, are gone.
- **Two commands no longer follow a link out of the repository.** `chamnan-peek` refused a linked
  file that pointed outside, but read a file reached through a linked directory. `chamnan-where`
  opened a linked file wherever it pointed. Both now apply the rule the map already used. A link
  that stays inside the repository is read as before.
- **Commands chamnan suggests now work on paths with spaces.** A notice that said to run
  `chamnan-peek <path>` printed the path unquoted, so `my dir/long notes.md` named the wrong
  files. Paths and search terms in suggested commands are now quoted.
- **The dashboard no longer drops the record a running session is still writing.** It reads each
  transcript from where the last build stopped, and that point could fall inside a half-written
  line, which was then never counted. It now stops at the last complete line.
- **The redactor no longer slows down sharply on long dotted text.** A long run like `a.b.c…`
  with no `://` in it made one URL pattern re-scan from every dot: 50,000 characters took 99
  seconds, and they now take 0.23. Output is unchanged on every tracked file and on the corpus.

---

## What's new in 1.31.2

_A patch on 1.31.1: the dashboard counts honestly, and outside research earned four fixes._

### Fixed and improved

- **The session block holds still between firings, so it does not cost a cache write.** "Last edited" counted minutes when the last change was under an hour old, so the block changed every minute and a second firing of the same session re-wrote the whole cached block. Under an hour it now says `<1h`.
- **A config value of the wrong type is kept, and named — no longer replaced by the default.** Writing `"log_retention_days": "30"` (a quoted number) used to be overwritten with 7 on the next session, silently, which began deleting logs the user meant to keep. The file is now left as written, the session says which setting is being ignored and what it wants, and a config that does not parse says the line and column.
- **The dashboard's notes are held to a readable line length.** On a wide panel a note ran to about 130 characters; measured comprehension peaks near 55 and long lines read slower. Notes stop at 78 characters and source lines at 90, as the headline's sentences already did.
- **`/chamnan:review` checks the size of a change first.** Above about 400 changed lines it says so and reviews in parts: measured defect detection falls from 87% on 1-100 lines to 28% above 1,000, and a review of a large change finds less while reading as complete. A change that mixes a rename or move with a behaviour change is named too, and the behaviour reviewed on its own.
- **An ordinary line of code after a line ending in `..._key:` is no longer redacted.** A Python `if … != last_user_key:` made the redactor treat the NEXT line's assignment as that key's value, so `state["gap_ping_anchor"] = last_user_key` reached the index as `<REDACTED>` — and a second pass then redacted the dict key too. Found by a property test: scrubbing twice must equal scrubbing once. Recall and precision on the corpus benchmark are unchanged (98/99, 100%, 0/48 damaged).
- **A new session is told what moved while it was away.** When `chamnan-open` starts fresh, the handoff now names the files committed after the old conversation's last response — by another session or by hand — so the new one does not work from a picture of the repository that is already out of date. Nothing is added when nothing was committed.
- **A closed thread is no longer named when you open a file it lists.** The pointer treated a finished thread like live knowledge: on the repository it was built on, the most-named entry in 24 days was a thread closed weeks earlier, and in 35 of its 56 appearances it was the only thing named. Threads whose status is closed are skipped; on that repository's 136 plugin files the only change is that thread disappearing.
- **The dashboard counts the sessions you worked, and shows what filled them.** Its totals now come from one account's interactive sessions — including sessions started in a subdirectory, which it used to miss — and leave out sessions a script started with `claude -p`, which on the repository it was built on were a third of September. A new panel ranks the top five things that went into the context in the chosen period: the model's own output, each tool's results, hook and reminder context, the host's prompt, and what you typed.
- **The dashboard counts each response once.** Claude Code writes one transcript record per content block — a thinking block, a text block and each tool call of one response are separate lines, each repeating the response's usage — and the dashboard counted every line. On the repository it was built on that was 35,356 requests counted against 17,569 real ones, so every token total was about double. A record repeating the previous response's request id is now skipped, including across an incremental read, and the scan cache is re-read once under a new key. `chamnan-report` already kept one record per request and was not affected.

- **The plugin carries no key-shaped test data.** The checks that need a credential's shape, and the recall benchmark with its tables, moved to chamnan-corpus; the checks kept here use plain values.

### Verification

**6104/6104** checks on the release gate (macOS, with the live workspace), and CI green on all five legs — macOS · Linux · Windows on Python 3.8 and 3.13 — on the same commit. The check branch found seven things on the way, all fixed before this: a session-expiry test that passed only before noon UTC, a bare `next()`, the dashboard missing every Windows path and any path with a dot or a space, a byte offset shifted by Windows line endings, a concurrency harness decoding as cp1252 with a 30-second timeout, and the session block's "Last edited" line changing every minute — the last one a real cache cost for users.

---

## What's new in 1.31.1

_1.31.0 was never published: this is its first release, with what was found on the way out._

**This release is about the difference between a tool that works and a tool that can show you it
worked.** Four pages of your own numbers, a doctor that says whether the install is actually wired
up, and a corpus of a hundred ways a context tool can cost the person who installed it — which is
how five of the six fixes below were found; the sixth was reported by somebody using it.

### Found and fixed on the way out

- **A new conversation starts where the old one stopped.** When `chamnan-open` starts fresh while
  an earlier conversation exists — a new date and a night's gap, or `--fresh` — it writes
  `.chamnan/logs/handoff.md` from the earlier transcript's last typed messages (redacted, harness
  turns left out) and opens the new session with one instruction: read that and `STATE.md`, then
  carry on. The old transcript is kept and named, so it can still be resumed.
- **`chamnan-open --fresh` now does what it says.** The flag was parsed and never read, so it
  resumed the old conversation whenever the rule said to.
- **A filter a repository names in its own config no longer runs.** `.gitattributes` can name a
  clean/process filter whose program sits in the repository's `.git/config`; `git status` ran it
  whenever a file's stat info changed, which is every session start in a repository somebody is
  working in. Drivers set in a repository scope are stood down; your own global ones (git-lfs) are
  left alone.
- **The dashboard is yours, and stays in your repository.** It is built at session end into
  `.chamnan/statistic/` of the repository you are working in, which the workspace gitignores. It
  used to be written into the plugin's own directory, shared by every repository on the machine,
  and it looked for your repository in the wrong place on any install but the developer's.
- **`chamnan-doctor` no longer runs scripts from the repository it is pointed at.** It ran two
  workspace tools that do not ship with chamnan from whatever checkout it was asked about.
- **Two guards were silent on Windows.** The warning about writing outside the repository skipped
  every `~/…` path there (`expanduser` ran before the shape test), and the notice about reading one
  file slice by slice never counted a Windows path (POSIX `shlex` ate the backslashes). Both found
  by the Windows CI legs on the way to this release.
- **The index no longer describes your dashboard as source.** With the dashboard built into
  `.chamnan/statistic/`, the next `chamnan-map` indexed its pages; that directory is now skipped by
  path, and only under `.chamnan/`.
- **The plugin carries no fake credentials.** Its redaction test cases moved to
  [chamnan-corpus](https://github.com/ArcticFox2029/chamnan-corpus) 1.1.1 (`redaction/`), where
  key-shaped test data belongs; the suite no longer depends on another repository.

### You can now see what it cost, on your own numbers

Four pages are built out of your workspace's own logs, into your repository's own gitignored `.chamnan/statistic/` at the end of every session: what the plugin
changed about a period's token weight, which features fire and how often, what the redactor caught
and what no pattern can, and an editor for the weights. **A fresh clone opens to greyed panels
that name the file each one reads** — nothing is sampled, nothing is estimated, and no sample
dataset ships to make the pages look populated.

The top line shows its working, because it is the one worth arguing with: the bars start at the
common floor rather than at zero and say so, the saving is weighted the way a cache write is
weighted, and the 25% that turns "characters a local model read" into "tokens saved" is **named as
a judgement, not a measurement**, with the page that replaces it. No money and no model names
appear anywhere, because the plugin does not know which model you run.

### `chamnan-doctor` — is this install actually doing anything

Four copies of chamnan at four versions were found on one laptop, `.version` reading whichever
wrote last, and nothing downstream could tell. The doctor asks whether the hook is registered,
whether the recorders are writing, and whether the index describes the tree. **It found a dead
feature on its first run**: the failure recorder had been registered on an event that fires when a
TOOL CALL fails, which is not what a command exiting 1 is, so `logs/failures.jsonl` had never been
written at all.

### The questions a workspace could not answer before

`chamnan-explain-context` answers "why did the session not know that" from the shape of the block
rather than from a guess — which sections arrived as names only, how much of each was kept, and
how often that has happened lately. It reads the shape log and nothing else: **no prompt and no
file content is stored anywhere by this package**, which is what makes the audit safe to keep.
`chamnan-where`, `chamnan-vs` and `chamnan-setup` answer three more.

### The README is now an index of what this does

Seven groups, by what you are trying to do rather than by the order things were written, every row
linking to its detail. Neither list is typed: `bin/` and `skills/` are the population and a check
asserts both directions, because a command that ships and is missing cannot be found by anybody
reading the page, and a row for something that was removed is worse — it reads as real.

---

## Under the hood

**Three recorders that were writing nothing, and the lessons already in the code became readable.**

- **The failure recorder now listens where failures arrive.** `chamnan_tool_failed.py` had been
  taught to read a non-zero exit code and stayed registered on `PostToolUseFailure` alone — an
  event that fires when a TOOL CALL fails, not when a command exits 1. A shell command that exits
  non-zero is a tool call that succeeded and reported a failure, so it arrives on `PostToolUse`,
  and the branch written for it could never run. `logs/failures.jsonl` did not exist at all, and
  everything built on top of it had no input.
- **`secrets.toml` is refused by name.** `secrets.yml` and `secrets.yaml` were listed and the
  third spelling was not — the one Streamlit puts live API keys in. The entry is the stem now,
  so every config spelling is covered while `secrets.py` stays an ordinary module.
- **A `statistic/` site**, four pages built from the workspace's own logs: what the plugin
  changed about a period's token weight, which features fire and how often, what the redactor
  catches and what no pattern can, and an editor for the weights. No money and no model names on
  any page, because the plugin does not know which model a reader runs. Nothing is generated into
  the repository — a fresh clone opens to panels that name the file they read and say it is
  missing, which is the honest first view.
- **`tools/gotcha_index.py`** reads every recorded lesson in the tree instead of counting them.
  3,118 of them across 533 files, with the file, the line, the date and what went wrong.
- **`bin/chamnan-doctor`** is pinned to LF, so a Windows checkout under `core.autocrlf=true` does
  not receive a shebang no shell recognises.

**Six defects found by running chamnan against a corpus nobody on this project wrote.**
`chamnan-corpus` gained a hundred cases asked from the other side — somebody installed this in a
codebase they care about, and the repository was already in one of these states. Sixty-seven are
planted, twelve were already there, and the twenty-one no corpus can hold are listed with the
reason rather than dropped.

- **A credential the source split in half no longer reaches `MAP.md`.** A deploy key written the
  way a formatter leaves it — `("ghp_"` on one line, the rest on the next — was copied into the
  index complete, because every prefix rule needs the prefix and the body contiguous and the
  language rejoins them where a pattern cannot. `MAP.md` is the file this plugin tells people to
  commit. Adjacent string literals are now joined before matching, and the joined form is kept
  only when it actually redacts more, so ordinary text is returned untouched.
- **Session records are named before they are deleted.** `prune_sessions` removes a handoff
  somebody wrote on the retention window at every session start; in a committed workspace that is
  a `D` in a teammate's `git status` nobody asked for, and a failed `git diff --exit-code` in CI.
  The sweep over `logs/` had named its files first since the release before; sessions had not.
- **Four warnings were being deleted on their way out of the block.** Standalone notices are moved
  to the end of the block for the prompt cache, and the fitter treats a bare line after a section
  as that section's footnote — so a session-wide warning that merely sat behind the last section
  was dropped with it, while `dropped` reported nothing at all. Measured on the corpus: log
  expiry, session expiry, "source has changed since this index was built" and "25 of 576 file(s)
  this index names no longer exist", gone in one firing from a block that looked complete.
- **Three state files left everybody's diff.** `drift.json` is a function of HEAD, `.temps-swept`
  is this machine's last sweep, and `notices.json` counts how often one person has been shown a
  notice — so committing it let the first teammate who saw one silence it for the whole team. The
  rule that already excluded two derived files stopped one short of the identical cases beside
  them; the population is now declared and derived from the source instead of enumerated.
- **`chamnan-explain-context` reads both shapes of its own log.** The writer began recording
  `{whole, rank}` where it had written a plain size, and the reader was never taught; any
  workspace with two shortened sections crashed it, which is every recent firing here.

### Verification

```
6138/6138 checks passed, 3 block(s) skipped on this platform
```

Quoted from the run on the tagged code, not remembered. The public CI matrix — Ubuntu, macOS and
Windows on Python 3.8 and 3.13 — is green: `5768/5768` on Ubuntu 3.13, `5766/5766` on macOS,
`5674/5674` on Windows 3.13. Before the gate, every commit this release pushes was scanned the way
GitHub push protection scans (added lines, as written and base64-decoded), and chamnan was run over
[chamnan-corpus](https://github.com/ArcticFox2029/chamnan-corpus) 1.1.1: 595 source files, 97.1%
described, seven writing systems, no planted credential in the index, all twenty redaction cases
loaded.


## What's new in 1.30.0

**Five new questions you can ask the repository, and the answers arrive faster than the last release
could give them.**

| | 1.29.0 | 1.30.0 |
|---|---|---|
| Naming an edit that will not survive | 33.5 ms per Edit | **0.5 ms** |
| Cache hit ratio behind the similarity path | 23.5% | **90.3%** |
| Languages a reference scan can read | 1 | **21** |
| Noise in a cross-language reference scan | a plain grep's | **98% of it removed** |
| Instruction files checked for claims that stopped being true | none | **every one in the tree** |

Together those say one thing: **the cost of asking fell far enough that asking became worth doing.**
A question that takes a third of a second gets asked; the same question at thirty milliseconds a
file does not.

- **You can ask where a name is actually used**, not where it is mentioned. `chamnan-where` reads
  21 languages and excludes comments, strings and docstrings before it answers.
- **You can ask what this repository costs a model, measured on this repository.** `chamnan-vs`
  prints three numbers from your own tree rather than quoting ours.
- **You can ask whether the problem is the machine or the code**, before an hour goes into the wrong
  one. `/chamnan:why`.
- **You can have a change reviewed against what the repository already knows** — its rules, its
  recorded decisions, the sibling that solved this before. `/chamnan:review`.
- **You can have a decision counted rather than argued.** `/chamnan:decide` puts the evidence on
  each side and shows the count, with no model in the loop.
- **Resuming a session stops paying twice.** The hook recognises its own block in the transcript and
  sends one line instead of the whole thing.

### What you should notice

Most of this is deliberately invisible on the happy path. What you will see: a resumed session that
does not re-send what it already told you, a repository whose stale index asks once instead of every
time, and one notice per tool call instead of one per hook that fired.

What you will not see, and that is the point, is the `chamnan-where` that used to take long enough
that you would have run `grep` instead.

### Under the hood

**Asking the repository a question**

Five commands, and the common thread is that each answers a question somebody was already asking
badly. `chamnan-where` answers "where is this name used" — a comment, a string and a docstring all
*mention* a name and none of them *uses* it, and that distinction is the whole difference between a
list you can act on and a list you have to filter by hand. Python is answered by its own parser;
twenty other languages are answered lexically, and labelled as lexical so nobody mistakes one for
the other. Comments and string literals are blanked before the identifier is matched: against the
AST's verdict on six real symbols in this package — 92 true uses against 178 raw grep hits, 86 of
them noise — that removes 98% of the noise, reporting 94 against the AST's 92.

`chamnan-vs` prints three numbers measured on the tree it is run in: every indexed file
concatenated, the block chamnan injects, and the largest file read whole against the same file
peeked. It names no other tool, deliberately — a reader gains nothing from a competitor's name and
loses the ability to check the figure against their own code. A repository with no recorded sessions
gets the block's byte *ceiling* rather than a token figure that would have to be invented from a
chars-per-token ratio this package refuses to use.

`/chamnan:why` separates "the machine is wrong" from "the code is wrong" before either is debugged.
`/chamnan:review` reviews a change against the repository's own rules and recorded decisions.
`/chamnan:decide` counts evidence on each side of a question and shows the count.

**Performance**

Naming an edit that will not survive went from **33.5 ms to 0.5 ms** per Edit. The old path paid a
git subprocess on every edit of every file, and 32 ms of that is process spawn alone and cannot be
optimised away — it had to stop being spawned.

One similarity threshold existed in two copies that could disagree. Consolidating it and moving it
from 0.99 to 0.75 took the cache hit ratio behind it from **23.5% to 90.3%**, because a threshold
that strict meant almost nothing was ever recognised as the thing it had just seen.

The reference scan no longer walks a function's whole subtree once per enclosing function. On a
module where every function shadows the searched name, the old shape visited 1,852 AST nodes against
520 now — and produced the identical answer on all 5,016 (file, symbol) pairs it was checked against.

**Reliability**

A repository whose index has fallen behind now asks once and stops. Measured over 400 real sessions,
the index was behind on **78 of them (19.5%)**, median 42 minutes, p90 3.6 hours, and a maximum of
16.6 hours — so the notice was firing constantly and being ignored constantly, which is the worst
state for a notice to be in.

Instruction files are now checked for claims that stopped being true. On this machine that check
reported 11 of 24, 8 of 12 and 19 of 47 statements no longer matching the tree they describe —
between 50% and 80% of each file. The check reports and never rewrites: an instruction file is the
owner's, and a tool that edits one is a tool nobody can trust with anything else.

A tool call produces one notice now, across hooks that cannot see each other and each believed
itself the only speaker.

**Security**

Homoglyph detection closes the half of Trojan Source this package never answered. The bidirectional
and zero-width halves were already scrubbed; a Cyrillic character standing in for a Latin one was
not, and a path mixing two scripts is exactly how a reviewer is shown one thing while the machine
reads another. It detects and names the segment — it never rewrites a path, because a rewrite is a
decision about somebody else's filename.

Per-segment, not per-path, and that is load-bearing: this repository's own tree contains Thai
directory names, and a per-path test would flag every one of them.

**Cross-platform**

The long-document notice told every reader to run a script that exists only on the machine that
wrote it. Windows paths that git C-quotes are decoded before they are compared, rather than compared
as quoted bytes against unquoted ones.

### Interesting findings

**A check can assert the opposite of its own name and pass for its entire life.** A guard was found
beside the feature it was written for, having never once run — its population was empty, so it
reported success over nothing every time. The fix was not to the guard: the new check derives its
population from the source rather than trusting a list, because a list is what let the population go
empty unnoticed.

**A warning that fires on healthy files teaches people to ignore it.** Two warnings were measured
firing on files with nothing wrong with them, and both were found by the feature that had just been
built to warn about things — it warned about itself. Both were removed rather than tuned; a
threshold that needs tuning to stop crying wolf is usually answering the wrong question.

**Three claims the index made about the tree were false.** An absent reference, a swallowed commit,
and a rebuild that reported success without running. All three now check rather than assert, which
is the whole difference between a document and a claim.

**The right answer to "which language is this" was already written down.** A declaration scanner was
about to get its own rules for naming things, one file away from `mapper.py`, which had answered the
same question for twenty languages already. Terraform scored 0 of 19 under the new rules and 19 of
19 under mapper's — nine resources of type `aws_kms_key` are not nine things named `aws_kms_key`.

### Dogfood and real-world discovery

Every number in the performance section came from running this package on real repositories rather
than on a fixture. The 400-session index-staleness figure is this machine's own session history. The
33.5 ms edit cost was noticed as a session that felt slow before it was ever measured, and was turned
into a reproducible case before any code moved.

The five new commands each exist because the same question was asked badly three times in a row in
real work, and the third time it was written down instead of answered again.

### Research-driven improvements

Two techniques that a repository index is expected to adopt were measured against this one and are
deliberately not in it.

**Incremental rebuild.** Rebuilding only what changed is the standard answer for an index, and three
separate literatures — incremental recomputation, content-addressed identity, differential dataflow —
arrive at it. Measured here, a full index rebuild is 11.5 seconds across 660 files. Against that
base, the published conditions on those techniques bite: the first incremental build is slower, each
configuration needs its own cache, and a coarse task erases the benefit entirely. The staleness
class it would introduce costs more than the seconds it would return, so the index still rebuilds
whole and stays simple enough to reason about.

**Late-interaction retrieval.** Token-level matching with a reranker is the current answer to
retrieval quality, and every published variant requires a neural encoder, a multi-vector index and
accelerator-backed inference. This package is standard library, with no model and no index service,
which is what lets it install into any repository and run the same way. Retrieval here stays lexical
and exact rather than trading that away.

Both decisions, their sources and the conditions that would reopen them are in the research index
attached to this release.

### Research & evidence

- `INDEX_CITED_IN_CODE.md` — attached to this release. Every defect record in the source that names
  the research round or the measurement that found it, resolved back to the line it was fixed on.
- `tests/run_tests.py` — the whole suite, runnable after a clone.
- `tools/redactor_recall.py` — recomputes the redactor's recall and precision on the shipped corpus.
- `tools/map_claim_check.py` — re-derives whether the index's claims about the tree still hold.
- `tools/verify_release.py` — checks the package itself.
- `bin/chamnan-vs` — the three numbers, on your repository rather than on ours.

### Verification

```
5847/5847 checks passed, 4 block(s) skipped on this platform
```

Quoted from the run on the tagged code, not remembered. The public CI matrix — Ubuntu, macOS and
Windows on Python 3.8 and 3.13 — is green on the same commit (`5485/5485` on its Ubuntu 3.13 leg),
and the suite was also run from a checkout with no development workspace above it (`5484/5484`),
which is what anybody cloning the repository gets. The three differ only in how many blocks each
one can reach: a bare checkout skips 81 that read a workspace, and CI skips the same 81.

The suite covers known regressions, malformed and hostile input, platform-specific behaviour,
research-derived edge cases and adversarial security fixtures. It is not a claim that this package
has no defects — it is a claim that the behaviours it defines still do what it said they would.

**The megaproject gate**, run before anything else and against a corpus nobody on this project
wrote: **532 source files, 517 of them described (97.2%), 69 distinct extensions, and 7 writing
systems in the index** — Arabic, CJK, Cyrillic, Devanagari, Hangul, Hiragana and Thai. **Planted
credentials reaching the index: 0**, which is asserted absolutely and never as a floor, because one
is the whole product failing.

The 15 files it does not describe are recorded rather than rounded off: three Perl files have no
reader at all, two Python-2 files cannot be parsed, and the rest carry no comment to read. 97.2% is
the ceiling currently available without writing a Perl reader.

**Catastrophic backtracking**, asked in the engine that actually runs the patterns: every quantified
regular expression this package ships was fired at with inputs shaped to force exponential
backtracking, inside a watchdog that kills the attempt rather than waiting for it. **None hung.**
That probe now runs as part of the suite, so a pattern added later is asked the same question.

### Measured and rejected

**A published figure was withdrawn rather than defended.** "Aggressive context compression raises
cost by 1.8% over 358 runs" was cited in this project's own notes. Re-measured, the smallest effect
this repository can detect at all is 52.7% of the mean — thirty times larger than that figure — so
the number was never separable from noise. It is withdrawn, and no compression change was made on
the strength of it.

**A fail-closed redaction mode was designed and rejected.** Refusing to store anything containing a
detected secret is safer in the narrow sense and stops the work in the broad one: real sessions
handle credentials legitimately, and a model that cannot see the sentence around a credential cannot
tell you to rotate it. This package filters and lets the work continue. That is a different product
from a blocking one, not a weaker version of it.

### Known limitations

- Windows behaviour is tested on CI, not on a Windows machine anybody here owns.
- `chamnan-where` still parses every source file in the tree rather than reading the index, so on a
  large repository it is seconds rather than milliseconds. The nested-walk half of that cost was
  fixed here; the parse-everything half was not.
- The reference scan is exact for Python and lexical for the other twenty languages. Lexical results
  are labelled as lexical and should be read that way.
- The redactor cannot catch a secret with no shape, no known prefix and no credential-named
  position, and the shipped corpus does not cover every secret format in existence.
- Homoglyph detection reports a mixed-script segment; deciding whether it is an attack or a
  legitimately multilingual path is left to the reader.

### Upgrade

```
/plugin update chamnan
```

Nothing else to do. The new commands appear on the next session start; existing workspaces are not
migrated or rewritten.

### In closing

This release is about the moment somebody turns to the repository with a question. Five of those
questions now have a command, the answers arrive fast enough to be worth asking for, and the
measurements behind every claim above ship with the package so you can take them apart.

## What's new in 1.29.0

**A cut through Thai deleted the tone mark it landed after.** `whole_graphemes` is the guard every
other cutter in the package goes through, and it removed the last character whenever that character
was a combining mark, a variation selector or a skin-tone modifier. All three follow their base, so
a cut can never orphan one — whatever the cut removed came after them. It was deleting complete
clusters: `ไม่` came back as `ไม`, a different word, and 👍🏽 came back without its skin tone.
Measured over the Thai lines of this workspace's own memory and skills, at the eleven limits the
code actually cuts at: 318 of 5,290 cuts lost a complete mark, 6.0%. Zero now. The two rules that
were right are untouched — half a flag is still half a flag, and a dangling ZWJ still goes.

**A log line nested past the interpreter's recursion limit threw away every line before it.** The
session-start hook reads `block_shape.jsonl` to recognise a block it has already sent. One torn
line was meant to cost one line, and `except ValueError` does not catch the `RecursionError` that
deep nesting raises — so it fell to the function's outer handler, which returns nothing at all.
Named where it happens now.

**A resume stops paying for a block the session already has.** Resuming a conversation re-sent the
whole workspace block even though every word of it was already in the transcript. The hook now
recognises its own block by the fence it wrote, and a resume that finds one sends a single line
instead. Measured on this machine's transcripts: 13 of 17 resumes shortened.

**Thai content past the first 4,000 characters of an entry could not be found at all.** Thai has no
word boundaries, so substring matching is the only path Thai has into `chamnan-recall` — and the
substring text was truncated at 4,000 characters per entry. Everything after that was invisible.
Found in use, not in a test: three of five Thai queries about entries that exist returned nothing.
The cap is gone. It was protecting the rule that the index must be smaller than the corpus it
indexes, and that rule had room: measured by building the real index both ways over the same
corpus, 57.8% with the cap against 67.7% without. Nothing about the session block changes — the
index is never read into it, and an A/B of the block with and without the cap is identical to the
byte in all four workspaces here.

**Two credential shapes walked past the redactor.** `api_key = os.environ["X"]` and `os.getenv("X")`
name where a secret lives rather than the secret, and were being redacted as though they were one;
and a base64 value inside a URL carries a `/`, which was ending the match early and leaving the tail
in plain text. Both were found by generating carriers rather than writing cases by hand — one
template per word cannot reach them.

**A multi-line command signed only its first line.** The shell splitter did not treat a newline as a
separator, so a script written across several lines was recorded as one step and everything after
line one vanished from the command ledger that `chamnan-candidates` and the repeat hint are built
on. `cd /tmp` then `git status` then `git commit` recorded as nothing at all. Found by reading the
ledgers of two real repositories, where Python and Ruby source had been signed as shell commands.

**A section cut down to its names now leaves a trace.** The block's headline number said how much
was sent and never that something arrived as a name only, so a reader could not tell a short block
from a trimmed one.

**The README advertised a repository that no longer exists**, beside its own table saying otherwise —
chamnan connects to those hosts itself now, and there is no separate repository to clone.

**For anyone reading the logs:** every field `block_shape.jsonl` can carry is now documented beside
the code that writes it, including which one is *not* the staleness pass. A wrong reading of that
file produced a wrong conclusion about a real repository here, and the retraction cost more than
the comment.

---

## What's new in 1.28.1

**A fix for something 1.28.0 shipped: `chamnan-setup` reported files it does not own, and offered
a command that cannot run.**

`chamnan-setup` lists generated files a version bump can invalidate. It was finding them by
globbing `.claude/agents/*.md` — which are Claude Code **subagent definitions**, your own
hand-written files. chamnan neither writes nor stamps those. Two different things share the word
"agent": chamnan's *agent context files* are the adapter instruction files (`AGENTS.md`,
`.cursor/rules/…`), written by `chamnan-context --write <adapter>`.

So in any repository with subagents, chamnan announced that your files were stale, and the fix it
printed for each — `chamnan-context --write <that file's name>` — exits with `invalid choice`,
because `--write` only accepts an adapter from a fixed list. Measured on the repository chamnan is
developed in: **8 files reported, 8 unrunnable commands, and the one genuinely stale file not
among them.**

| | before | after |
|---|---|---|
| Files reported stale here | 8 | **1** |
| Of those, actually written by chamnan | 0 | **1** |
| Remediation commands that run | 0 of 8 | **1 of 1** |

It now asks `adapters.artefact_drift()` — the function its own docstring already named, which
derives its population from the adapter registry rather than from a glob, and which the
SessionStart hook has been using all along. A file written by a *newer* chamnan is still reported
and still offered no fix, because rewriting it down would lose what the newer one put there.

### What you should notice

If you have subagents in `.claude/agents/`, `chamnan-setup` stops telling you they are out of date.
Nothing else changes, and nothing needs to be re-run.

### Interesting findings

**The check written to catch this passed against the broken code.** It read the report's JSON for a
key named `stale`, the key is `stale_artefacts`, the lookup returned nothing, and the loop ran over
an empty list — so it reported success while examining nothing. It was caught by reverting the fix
and seeing the check stay green, which is the only way that class of failure announces itself. A
missing key is now a failure in its own right rather than an empty population, because those two
look identical from the outside and only one of them is a result.

**A printed command is part of the product.** A tool that detects a problem and hands over a remedy
is trusted twice, and only the first half had ever been checked here. The new check takes every
remediation `chamnan-setup` emits and asks whether the argument is one the named command accepts,
reading that command's own declared choices rather than keeping a second list.

### Verification

```
5554/5554 checks passed, 3 block(s) skipped on this platform
```

Quoted from the run on the tagged code. The public CI matrix is green on the same commit.

### Upgrade

```
/plugin update chamnan
```

Nothing to do afterwards.

---

## What's new in 1.28.0

**A firmer boundary between chamnan and the repository it reads, and hooks that answer even when
the workspace is broken.** The repository you point this at is now treated as untrusted input
throughout — its config, its comments, its filenames — and the parts that run on every session were
made to fail visibly instead of quietly.

### Highlights

| | before | after |
|---|---|---|
| Session start on a workspace it cannot read | >45 s, 0 bytes | **0.5 s, with the reason** |
| `chamnan-map` on a crafted 8,000-space comment | 2,374 ms | **0.0 ms** |
| Windows installs where a byte-order mark hid the install | 21 of 21 | **0 of 21** |
| Repository-controlled git keys that can make git run something | 0 refused | **11 refused** |
| Secret detection on the published corpus | — | **99.0% recall · 100.0% precision** |

**A repository can no longer choose what git runs.** Eleven config keys — `core.hooksPath`,
`core.pager`, `core.editor`, `core.sshCommand`, `core.askPass`, `diff.external`,
`credential.helper`, `uploadpack.packObjectsHook`, `sequence.editor`, `gpg.program`,
`core.fsmonitor` — are forced inert for every git command chamnan issues. Cloning a repository and
opening a session in it used to be enough to have its chosen commands run.

- **Warnings at the moment of the command, not in a document.** Before `git checkout --`,
  `git restore`, `git reset --hard`, `git clean` or `git stash drop`, chamnan says how many files
  in that repository carry uncommitted work — the actual number, from `git status`, not a caution
  that something might.
- **A hidden instruction in a source comment no longer reaches the architecture index.** Stripping
  covered what hooks printed; the index is written from repository text and was not covered.
- **Every hook survives a workspace it cannot read**, and says so, instead of returning nothing
  that looks exactly like having nothing to say.
- **`chamnan-report` answers by who is reading it** — tables at a terminal, a summary when piped.
- **5,550 / 5,550 verification checks passed**, on all three platforms.

No migration required.

### What you should notice

Most of this is deliberately invisible on the happy path, and the honest summary is that a short
session in a healthy repository feels exactly as it did in 1.27. What changes is the unusual case:
a workspace with the wrong permissions, a repository that is not yours, a file with a byte-order
mark, a comment written to be hostile. Those used to produce silence, a hang, or an empty result
that reads like an answer.

The one thing you will see directly is the warning before an irreversible git command.

### Under the hood

#### Security — the repository is untrusted input

- **Git configuration.** Eleven keys forced inert for every git command chamnan runs. The list is
  the set of keys that turn a read into an execution; `git -C <dir>` makes git read that
  directory's config, so every such call now also asks git whether it can speak for the directory
  at all before running.
- **Hostile comments.** `mapper.py` compiled thirty-three patterns with no ReDoS check — the audit
  had been scoped to the redactor. One was quadratic: a leading comment of `import`, then spaces,
  then one rejecting character. `2,000 → 153 ms · 4,000 → 560 ms · 8,000 → 2,374 ms`, 4.2x per
  doubling where linear is 2; roughly 37 seconds at 32,000. Bounded rather than restructured, and
  behaviour-identical across all fifteen cases tested. **After: 0.0 ms at 8,000 spaces, 0.9x per
  doubling.**
- **Secret protection.** A decoy in the value position no longer keeps the real secret out of
  reach; one invisible character inside the word `password` no longer carries the credential out
  whole; a passphrase named in a sentence is treated as a credential; chat-template control tokens
  are stripped from the injected block, as ANSI escapes already were. Measured on the published
  corpus: **recall 99.0%, precision 100.0%**, with every category represented.
- **The index, not just the output.** A hidden instruction planted in a repository file reached
  `MAP.md`, because only the hook's own output was being stripped.

#### Reliability — the parts that run every time

- **A workspace that cannot be read.** The lock helper treated a permission error as a lock on its
  way out and retried it for the full timeout. On Windows that is right — a deleted lock lingers in
  `DELETE-PENDING` and every open fails with access-denied for a moment. Everywhere else it means
  what it says and will not change by waiting. Session start on an unreadable `.chamnan` therefore
  spun for **more than 45 seconds and answered with 0 bytes** — a hang, as far as anyone watching
  could tell. **Now 0.5 s, and it records why it gave up.**
- **A lock naming a process id that has been recycled** can now be broken.
- **Byte-order marks.** PowerShell's `Set-Content` writes UTF-8 with a BOM by default, so a file
  written on Windows could hide an install from the very code looking for it: **21 of 21 read sites
  affected, now 0 of 21**, with the check deriving its population from the source rather than a
  list, so the next site is caught without being enumerated.
- **Hooks under a broken workspace.** Every hook now survives one, including the one deliberately
  left unwrapped, and the deliberate exclusion is documented where it is made.

#### Measurement — numbers that stop being true

- **The block's token cost is measured where the text is**, not inferred from its byte count. The
  old arithmetic understated a Thai-and-English workspace's own block by 6% — 3,942 against 4,184.
- **`chamnan-report` now says how much of the context it reports is its own block.**
- **Published figures re-derive themselves.** Every re-derivable number in the README carries a
  marker naming the tool that produces it, and one command rewrites them all. Three had quietly
  stopped being true and were found by a reader, not by the project.

### Interesting findings

**A guard that fires on its own documentation.** The new warning before a destructive git command
matched the words of that command anywhere in the command line — including inside a heredoc, where
they are the document being written rather than the command being run. It fired while this session
was writing a note *about* such a command. It blocks nothing, so it cost no work; what it cost is
worse. A warning built to stop a reader skimming had started teaching them to skim.

**A rule that broke because the tool obeyed.** A recorded rule asserted a heading was present in a
generated document. The heading was changed on purpose, the generator produced the new one, and the
rule reported itself violated — a guard failing because the thing it guards did exactly what it was
asked to do. The rule now names a fixed marker in the *generator*, which is bounded source, rather
than a line in its output, which is not.

**A file too large to read was counted as a file that broke the rule.** The rule checker skips any
file over its scan cap, and a skipped file fell through into the "did not match" count. A `present`
check over one oversized document therefore reported the tree in violation when nothing had been
read at all. The other direction is worse and was silent: an `absent` guard over an unread file
reported that it held. A verdict now stands only when a file nobody read could not have changed it.

**The audit that was scoped to one module.** The ReDoS work had been done on the redactor and
reasoned about carefully there. Thirty-three patterns in the mapper had never been asked the same
question, and one of them was quadratic — the same failure family, in a different file, found only
because a round asked what breaks above the sizes anybody had run.

### Dogfood and real-world discovery

The permission-error hang was not found by a fixture. A session on this machine watched its own
session-start hook take more than forty-five seconds and produce nothing, which reads as slowness
rather than as failure; the workspace was simply unreadable. It was turned into a provoked,
reproducible case before any code moved, and that case now asserts both platforms' behaviour rather
than whichever one the suite happens to be running on.

### Research-driven improvements

Rounds run against outside literature during this cycle changed the code in three places: the
prompt-injection stripping was widened to the index after a round on what reaches a model's context
without passing a filter; the mapper ReDoS sweep exists because a round asked what breaks above the
sizes anybody has run; and the rule-conflict detector's categories were replaced after a round on
how real systems detect contradictions in a rule base — it had been using the firewall anomaly
classes, which assume ordered rules matching a packet space, on prose rules that have neither.

The full index of which research changed which line is attached to this release as
`INDEX_CITED_IN_CODE.md`. It is generated from the citations in this project's own source rather
than written by hand — every entry points at the commit that carries it, so a claim here can be
followed to a diff without cloning anything. The generator lives in the development workspace and
is not part of the package; what ships is the document.

### Research & evidence

- `INDEX_CITED_IN_CODE.md`, attached to this release — every cited fix, with the round that found
  it and the commit that carries it
- [chamnan-corpus](https://github.com/ArcticFox2029/chamnan-corpus) — 804 files, 72 extensions,
  23 programming languages, comments in eight writing systems. The secret-detection and coverage
  figures above are measured against it and are reproducible without cloning this repository.

### Verification

```
5550/5550 checks passed, 3 block(s) skipped on this platform
```

Quoted from the run on the tagged code, not remembered. The public CI matrix — Ubuntu, macOS and
Windows on Python 3.8 and 3.13 — is green on the same commit, and the suite was also run from a
checkout with no development workspace above it (`5469/5469`), which is what anybody cloning the
repository gets.

`5,550 / 5,550` is not "chamnan has no bugs". It is "5,550 behaviours we have defined still do what we said" —
known regressions, malformed input, platform-specific behaviour, research-derived edge cases and
adversarial security fixtures.

A tool anyone can run to reproduce it on their own machine:

```bash
python3 tools/verify_release.py
```

### Negative results

- **A grammar constraint on the local model was measured and rejected.** It blocked zero foreign-
  script leaks over fifty messages while pushing fourteen of them into the output cap, where the
  reply is discarded. It derails the model rather than guarding it, and it ships switched off.
- **Aggressive prompt compression was not adopted.** A pre-registered trial over 358 real runs
  found moderate compression cut cost 27.9% while aggressive compression *raised* it 1.8% through
  output expansion. The work stopped there rather than continuing toward a worse number.
- **One proof could not be automated and is stated as such.** The quadratic-pattern fix needs two
  bounded groups reverted at once, and the mutation harness takes a single substring, so it
  correctly reported "nothing failed". It was proved by hand instead: both groups reverted gives
  142 ms → 539 ms at 3.8x, and the check fires; restored, it does not.

### Known limitations

- Windows behaviour is exercised only on CI. Nothing on the development machine substitutes for it,
  and this cycle is the clearest evidence of that: the one defect no local instrument could reach
  was found by the Windows column of the release matrix.
- The corpus is synthetic. It is 804 real-shaped files across 72 extensions, not a sample of
  anybody's production code, and it does not cover every secret format that exists.
- The secret-detection figures are measured on that corpus. 99.0% recall is a number about those
  fixtures, not a guarantee about your repository.
- Nothing here is validated at very large scale. The block-fitting work was tested at 2x, 5x, 20x
  and 100x present store sizes; the repositories it has actually run on are smaller than that.

### Upgrade

```
/plugin update chamnan
```

Nothing to do afterwards. No configuration changed, no file format moved, and an existing
`.chamnan/` directory is read exactly as before.

### Closing

This release spends almost all of its effort on the boundary: what a repository can make chamnan
do, and what chamnan does when the thing it is reading is broken or hostile. Very little new
surface, and the parts you already use should feel the same — which is the point.

---

## What's new in 1.27.0

**More context, less waste, stronger safeguards.** Mostly about making the capabilities you already use more dependable under real workloads. Very
little new surface; the work went into what was quietly going wrong underneath it.

### Highlights

| | before | after |
|---|---|---|
| Sections of your workspace delivered to the session | 5 of 9 | **9 of 9** |
| Rules delivered | 13 of 16 | **16 of 16** |
| Tokens it costs | 4,189 | **4,161** |
| Prompt-cacheable prefix, in the measured case | 4.4% | **100%** |

**More context, for fewer tokens.** Those are the same measurement: the block was dropping the
tools list and the procedures list on 96.8% of firings and recorded decisions on 78.5%, and fixing
it cost nothing because a section that will not fit now leaves its *names* — the part that cannot be
guessed — instead of its title.

And it holds as your workspace grows: tested at 2×, 5×, 20× and 100× the present store sizes, every
store still has a representation in the block.

- **Stronger secret protection across real-world text** — natural-language mentions, Unicode
  look-alikes, multilingual credential vocabulary, YAML, JSON and CRLF files. Nine shapes that used
  to pass through untouched.
- **Safer command execution on Windows** — a cloned repository can no longer run its own `git.exe`.
- **`chamnan-guard` now reviews where a dependency comes from and what it runs**, and can scan the
  commits you already have rather than only the ones about to go in.
- **Tools that could not read something say so**, instead of an empty result that looks exactly like
  nothing being there.
- **5,448 / 5,448 verification checks passed.**

No migration required.

### What you should notice

Most of this is deliberately invisible on the happy path. Its purpose is to make unusual and
long-running work fail less often, and the honest summary is that a short session in a small
repository will feel much as it did in 1.26.

Where you may notice something:

- Fewer occasions where a resumed session seems to have forgotten part of the project — the block
  carrying it is no longer being cut off by the host.
- Recorded decisions, procedures and the tool list now arrive; three of those were delivered zero
  times in 400 recorded firings.
- A warning when chamnan cannot verify something, in place of a confident empty answer.

### What's new

**`chamnan-guard` reads what a change does to your dependencies.** A dependency can arrive from
somewhere other than the registry it appears to come from, under a name written to be read as a
different one, carrying code that runs because it was installed rather than because anything
imported it. Offline, with no list of known-bad names, it reports a redirected registry, a
look-alike name, a new install-time script and what that script does, a lock file with no digest,
and a dependency no registry hosts. Measured before shipping: **0 of 2,917 real commits across three
repositories would have raised a line.**

**`chamnan-guard --history`** answers the question a staged diff cannot: what is already in the
commits you have. It reports by file, worst first, and says rotate before rewrite — in that order,
because a rewrite leaves the blob in every fork and clone.

### Under the hood

#### Secret protection across real-world text

Nine shapes that used to pass through untouched — a sentence that merely names a credential, a
Unicode look-alike, Thai's own vocabulary for it, YAML's explicit-indentation scalars, CRLF
files, and the brace that closed the object a value sat in.

This is the largest cluster in the release, and they are all the same defect wearing different
clothes: **a rule was applied to one member of a set and forgotten in the identical ones beside
it.** Nine of the fixes below are that shape.

#### A credential a sentence names, with a clause between the word and the value

Every rule in the module keyed on an assignment — `password=`, `password:`, `password is`. That is
what configuration looks like. It is not what a person writing a note looks like, and the shape
came from real damage rather than from reading our own code: a break-glass password reached git in
four tracked files of a work repository and sat there fifteen days, on a documentation line.

    The break-glass password, which ops rotate quarterly, is `<value>`.
    Set the passphrase to '<value>' before running it.
    password for the jump host, rotated monthly: `<value>`

The window between the secret word and the quoted value is now forty characters of ordinary
sentence text instead of four spaces, and the precision moved onto the value itself, where it
belongs: a value that reads like a call, a dotted name, a path, a product name or a code fragment
carrying an inner `=` is not a credential. Trailing `=` is kept — that is base64 padding, and a
base64 secret is the thing this is here to catch.

Every one of those guards was bought with a real false positive out of chamnan's own tree, found by
the gate rather than imagined: `casefold()`, `time.time()`, `core.ignorecase`, `Qwen3-Coder`,
`per_dir=0`. Measured over all 229 tracked files against the self-scan baseline — five of five leak
shapes caught, zero new hits.

#### A credential's neighbours were deciding whether it counted as one

Twenty-three provider patterns guarded themselves with `(?<![A-Za-z0-9_-])`, which reads as "not
preceded by a word character" and actually means "…and not preceded by a hyphen or an underscore
either". A credential assigned to an upper-case name was redacted and the same credential one
hyphen further along was not — the same secret, one punctuation mark apart, and a diff hunk starts
every removed line with a hyphen. All twenty-three are now `(?<![A-Za-z0-9])`.

The AWS key-ID rule had the mirror image of it on the trailing edge: `[0-9A-Z]{16}\b` stops at a
word boundary, so a key followed by another capital letter did not match.

#### Thai had a wider credential vocabulary than English

The Thai list was `รหัสผ่าน|รหัส`, and `รหัส` alone means "code" — it fired on order numbers and
product codes while missing `รหัสลับ` and `รหัสเข้า`, which are what people actually write. Thai
also has no spaces, so every false positive in it takes its neighbours with it.

#### `password: |2` is a YAML block scalar too

`[|>][-+]?` matched `|`, `|-` and `|+` and not `|2`, `|-2` or `|2-` — the explicit-indentation
forms, which are in the YAML spec and in real configuration files. The header pattern and the
secret pattern both had it, and both were fixed; fixing one would have left the other.

#### The redactor was eating the brace that closed the object it stood in

A secret at the end of a JSON object took the closing `}` with it, so the document the block
carried no longer parsed. The same class of over-reach was fixed in six other places.

#### It leaked on every CRLF line

A file checked out on Windows ends its lines with `\r\n`, and `$`-anchored rules stopped at the
`\r`. Every rule in the module was affected; the scan that proved it is 48% of the module's test
surface.

#### Two quadratics, neither visible one pattern at a time

Two patterns backtracked quadratically on inputs that occur in ordinary files. Neither shows up
when you test a pattern by itself, which is why they survived every review.

#### And it now compiles when something needs it, not at import

61 patterns were compiled on every hook firing whether or not any of them would be used.

---

#### A failure in one prune was cancelling two unrelated jobs

Three retention sweeps ran under one `try`. When the first raised, the second and third never ran,
and nothing said so. Each has its own guard now.

#### A worktree that eats what it learns

A workspace inside a linked git worktree writes its state where the next session will not look for
it. chamnan now says so once, rather than losing the work quietly.

---

#### Windows — a cloned repository could have run its own `git.exe`

On Windows, `CreateProcess` searches the **current directory before PATH**, and the current
directory is the repository you just opened. This package runs `["git", …]` twenty-six times across
ten files, the first of them from the SessionStart hook. So cloning a repository that carries a
`git.exe` at its root was enough to execute it — arbitrary code from cloning, which is the class
chamnan exists to warn people about.

It is closed at the operating system rather than at the twenty-six call sites:
`NoDefaultCurrentDirectoryInExePath` is set on Windows at import of a module every path already
loads, children inherit it, and on every other platform it is an unread variable.

**And a second layer, because the first one can be silently absent.** That switch is not honoured
before Windows 10 1809, and nothing inside the process can observe whether it took effect — so on
those versions the hole is exactly as open as before and no error says so. The case it is *for* is
now detected directly: `chamnan-guard` finds a file named like the program in the directory
`CreateProcess` would search first, and **refuses** rather than routing around it. Nobody puts a
`git.exe` in a repository root by accident, and a tool that quietly picked the right binary would
leave the next tool on that machine to find the wrong one.

**Also Windows, and the same shape one layer up:** `chamnan-map` stripped the repository root from
a path with `path.replace(str(root) + "/", "")` in two places. On Windows the separator is a
backslash, so that never matches, the absolute path survives, and the rollup and asset groupings —
which both split on the first path component — see one component where a directory should be. Ten
other sites in the same file already used `relative_to(root).as_posix()`; these two were the
outliers.

#### The architecture map

- **A file git stores re-encoded is text, and the map called it binary.** A repository that
  declares `*.py text eol=lf` was having its own source classified as unreadable.
- **The glob tier was gated to one store**, so trailers in every other store were never matched —
  and no trailer has ever lived in the store it was gated to.
- **A record's trailer is parsed once**, not once per file opened.

---

#### New: `chamnan-guard` now reads what a change does to your dependencies

A dependency can arrive from somewhere other than the registry it appears to come from, under a
name written to be read as a different one, carrying code that runs because it was installed rather
than because anything imported it. `chamnan-guard` already reviewed a staged commit for leaked
secrets and for new MCP capability; it now reads the same diff for those three things.

What it looks at, in the files that can actually decide where a dependency comes from — `.npmrc`,
`pip.conf`, `Gemfile`, `package.json`, `Cargo.toml`, `composer.json`, `go.mod`, the lock files
beside them:

- **the registry was redirected** — a `registry=`, `index-url`, `replace-with` or `source` line
  pointing somewhere other than the twelve official hosts across npm, PyPI, RubyGems, crates.io,
  Go and Packagist;
- **the name is not the name it reads as** — `requеsts` with a Cyrillic `е`, `lοdash` with a Greek
  `ο`. Folded against the look-alike alphabet, which needs no list of real package names and works
  for every ecosystem at once;
- **something now runs on install** — `preinstall`, `postinstall`, `prepare`, composer's
  `post-install-cmd`, a `cmdclass` in `setup.py`;
- **and what that script does** — a line that fetches and pipes to a shell, decodes a blob and
  runs it, or spawns one. `"build": "tsc -b"` is not that, and stays silent;
- **nothing can verify what arrives** — a lock file that added resolved URLs and not one digest;
- **it comes from no registry at all** — a `git+`, `file:` or path dependency.

**It warns; it does not block.** Somebody adding a private registry on purpose is doing their job,
and is told once, at the commit that adds it. `chamnan-guard --strict` is where a project says the
commit should fail instead. This reduces a mistake by the person or the model driving the tool —
it is not a scanner and it does not decide what may run.

**The half it is judged on is the silent half.** Nine of the twenty-nine cases in the suite exist
only to pin that correct configuration says nothing: an official registry, a project's own build
script, a binary target path, a pinned requirement, an ordinary build step. Every one of them was
a false positive at some point while it was being written. Measured over real history before it
shipped: **0 of 2,917 commits across three repositories would have raised a line.**

#### New: `chamnan-guard --history` — the question a staged diff can never answer

Everything `chamnan-guard` did answered *is this about to go in*. Somebody adopting chamnan on a
repository that already has a past asks a different question first, and none of the thirteen
commands could answer it — nothing read `git log`.

The scanner is not duplicated: `git log -p` produces a unified diff and the redactor already takes
one, so this is the same rules over a different input.

**It reports by file, worst first, and that is the finding.** The first version listed every
(commit, path) pair and produced 431 lines across 79 commits on this package's own history, almost
all of it the redactor's own specimen credentials. A first run that hands somebody 431 alarms has
told them nothing. Grouped by file it is 22 rows: the fixture files are recognisable at the top and
dismissible in one line, and the file you do not recognise is not buried under them.

It says **rotate before rewrite**, in that order, because the order is the point — a rewrite leaves
the blob in every fork, clone and cache, so somebody who rewrites and stops believes they are
finished.

#### The session block — every store now arrives, and the order follows the work

This is the part that has been re-opened the most times, and the reason is worth stating plainly:
**every previous attempt was a NUMBER.** Raise the output ceiling. Lower the rules budget. Re-rank
the drop order. Each worked on the store sizes of the day it was measured and failed the next time
a store grew.

Measured over all 400 recorded firings on the development repository before this release:

| section | dropped on |
|---|---|
| This repo's own tools | **96.8%** |
| Recorded procedures (skills) | **96.8%** |
| Recorded decisions and lessons | 78.5% |
| Where the last session stopped | 58.8% |
| Recent milestones | 37.0% |

Blocks truncated by the host in those 400 firings: **0 of 392.** The ceiling was never the
constraint. The material is three to four times the ceiling at 9,000 and at 9,500 alike, so a
larger budget only moved where the same cut landed — and a fixed global drop order meant a
workspace whose skills are the point never received its skills, on any session, ever.

#### What changed

**A dropped section leaves its names, not its title.** A section that will not fit registers a
*brief* — the names in the store, one line. Names are what cannot be guessed; the prose around
them is what does not fit. A brief too big for the room is cut at a name boundary and says how
many it left out, never mid-name and never through its fence.

**The room is reserved before anything is packed, not offered afterwards.** Briefs used to get
whatever nothing else wanted, which on a workspace of any size is nothing. A share is now held
back first — and derived, not chosen: it is what the waiting stores ask for, one floor each, so it
scales with how many stores exist and never with how much is in them. A workspace that fits
reserves nothing and is bit-for-bit unaffected.

**What the reserve does not use goes back.** Leftover room upgrades a brief to the full section
where it fits, and lengthens the name list where it does not.

**The drop order follows what the workspace opens.** `pointer.note_opened` had been recording which
store each session reached for since it was written, and nothing had ever read a record.
Measured the first time anything did, on the development repository: `skills` and `memory` are what
get opened, `tools` is counted from its own register at 179 entries — and `skills` sits near the
cheap end of the hand-written order, so the store this repository actually uses was the first thing
it was told to lose. Usage now permutes those stores among their own slots. Every section the log
cannot speak for keeps its rank exactly, and a fresh install, where every count is zero, behaves
exactly as before.

**Result on the development repository: 5 of 9 sections delivered, then 9 of 9, and 13 of 16 rules
then 16 of 16 — at 4,161 tokens against 4,189 before.** More arrives, for less.

Two defects turned up in finishing it, both introduced by the fix itself and both the same shape as
what it was fixing. The line saying what the budget cost was appended **after** the body had been
measured, and took the block to 10,264 bytes — straight past the host's own cut, which is the single
thing this module exists to prevent. And once every section had a brief, nothing was dropped whole
any more, so that line stopped being written at all: somebody who had pinned more than the block can
carry was told nothing, and the block simply looked thinner for no stated reason. A message about
what the budget cost has to be inside the budget, or it only prints when nobody needed it. Tools and skills arrive together for the first time in 400 recorded firings.
Held under growth: with the stores at 2×, 5×, 20× and 100× their present size, every store still
delivers names and the block stays inside its ceiling.

#### Rules: primary loads, secondary loads enough to be called on

Three arithmetic faults meant the rules section did neither, and all three were invisible because
the section honestly reported what was missing:

- the weighted shares were never required to **add up** to the budget — sixteen rules at a
  120-character floor plus double for two pinned ones comes to 2,124 against a 2,000 cap, and the
  whole-budget cut took the overflow out of the last three rules;
- each trimmed rule appended its `…the rest is in <file>` pointer **after** its share, putting
  sixteen tails of about fifty characters outside the budget the shares were sized against;
- the joins between rules were never subtracted either, so a 1,998-of-2,000 allocation still
  landed over.

And when none of it fit, every rule received one equal slice — so a pinned rule and an ordinary one
were indistinguishable in the one place the distinction exists to show.

Allocation now fits **by construction**: every rule is given its own floor first (its heading and
the path to the rest, which is the smallest thing that can still be recognised and followed), a
pinned rule is then asked for in full, and only what is left is shared out. Verified on a fixture
of fourteen rules against a 2,000-character budget: **14 of 14 arrive, both pinned rules arrive
whole, the twelve others arrive as a heading and a pointer, and the section uses 1,702 of 2,000.**

---

#### A section written as one paragraph keeps what fits

A budget cut was backed to the last complete line, so a section with no line break in it had no
boundary and arrived **empty** — 0 of 235 phrases, where the same content line-broken kept 28 of
120. A word boundary is the honest fallback and is safe exactly there: a fence marker occupies its
own line, so text with no newline cannot have opened one.

#### The resume nudge asked the calendar, not the session

It gated on whether *any* session record carried today's date. One record written at 09:00 by a
different session, about different work, silenced every other session for the rest of the day —
while the nudge's own text said "nothing is recorded for today yet". It now remembers how many
records existed when the session first fired and stays quiet only once that count has grown.

### Interesting findings

Four worth reading, out of the set.

#### A warning that made the thing it was warning about worse

The injected block has a byte ceiling, and the packer was respecting it exactly: 9,447 bytes against
a limit of 9,500. Then a delivery-failure warning was prepended to the finished body, +119 bytes,
with nothing re-checking. 9,566 went out and the host truncated it.

The loop closed on itself. Over the ceiling means truncation; truncation is what the warning detects;
detecting it re-arms the warning next session, which adds the bytes that push it over again. 27 of
the last 84 firings were in that state. The log is read before packing now: +1 byte afterwards,
9,445 emitted, warning still present.

#### "Nothing here" and "I could not look" were the same answer

`os.walk` defaults to ignoring directories it cannot read. Silently. A `chmod 000` on a subtree
holding five of six source files produced "1 source file(s)" and a green 100% coverage bar — and a
root-owned directory from a Docker bind mount or a CI checkout is how that happens to a real person.
Four walks had this. They report what they could not read now.

#### A single letter nobody could see

`раssword` with a Cyrillic `а` is not `password` to any regex in the module, and on screen the two
are identical. chamnan now unmasks confusable characters, scrubs both spellings and keeps whichever
redacts more, so the disguised form cannot carry a value past a reader who sees nothing wrong.

#### 95.4% of the bytes were the same and only 4.4% could be cached

The prompt cache is prefix-based, so what matters is not how much of the block changed but how
early. Two firings of one session with a file written between them shared 95.4% of their bytes and
cached 4.4% of them, because the staleness notice that file write produced was inserted at
character ~60 and everything behind it was reprocessed at full price. After: 100%.

The rule needs no tuning as the workspace grows — everything chamnan says about the *moment* goes
after everything it reads from *files*.

### Where these came from

Several began as small inconsistencies noticed while using chamnan on this repository and on real
work, not as failures. They produced no crash and no error message, which is why each was turned
into a reproducible case before any code moved: the ceiling defect was found by reading what
`chamnan-context --preview` actually prints, and the silent walks by deleting eight files, hiding
eight more, and comparing what was reported.

The research behind the rest is attached as `INDEX_CITED_IN_CODE.md` — every finding linked to the
commit that acted on it, so any claim here can be followed to a diff without cloning anything.
Regenerate it with `python3 .chamnan/tools/research_citations.py --write`.

### What was measured and rejected

The Windows fix shipped is not the one first written. Resolving `git` to an absolute path at all
twenty-six call sites also closes the hole — and it broke three other things, and it violates a rule
added the same day forbidding use of `shutil.which`'s *result* as a path, because Python 3.12
changed what that selects on Windows. It was reverted in full for a single line that sets the
operating system's own switch.

### Verification

**5,448 of 5,448 checks passed** on macOS 26.6 / Python 3.9.6, concurrency 34 of 34, with 3 blocks
skipped for want of another platform — each says so by name in its own line. The same tree with no
`.chamnan` workspace above it, which is what a fresh clone and CI see, is **5,385 of 5,385**; the
difference is entirely checks that measure the development workspace and skip without it.

The suite covers known regressions, malformed input, platform-specific behaviour, research-derived
edge cases and adversarial security fixtures. It is not a claim that chamnan has no defects — it is
5,448 behaviours that are defined, and still do what they were defined to do.

```bash
python3 tests/run_tests.py                   # the full gate
python3 tools/verify_release.py              # the gate plus the index claim, on your machine
```

### Known limitations

`chamnan-report`'s ceiling comparison used to quote the value the package ships with rather than the
one your workspace runs at; it uses the recorded ceiling now, but a measurement taken before this
release still carries the old comparison. The redaction recall figure is measured over a corpus of
credentials, so it describes what is found among secrets it is shown, not a rate over everything
that passes through.

### Upgrade

```
/plugin update chamnan
```

No migration is required.

---

This release adds little that is new. Almost all of it went into making behaviour that already
existed harder to break, easier to verify, and more predictable on machines and repositories that
are not the one it was written on.

## What's new in 1.26.0

### New: `chamnan-schedule` — finish this work later, when the limit has reset

You are most of the way through something and the usage limit is about to stop you. Name the time
and chamnan comes back to it.

```bash
chamnan-schedule set 2h31m                 # resume this session's work in 2h31m
chamnan-schedule set 11:10pm               # or at a wall-clock time
chamnan-schedule set --reset-json resp.json  # or read the reset out of a rate-limit response
chamnan-schedule list                      # what is pending
chamnan-schedule cancel <id>               # or --all
```

**It carries the work, not a command line.** "Finish what you were doing" is not something a command
line can say, and retyping the job at the moment the session is ending is the thing this exists to
avoid. The record points at where the work is already written down — `.chamnan/STATE.md` by default,
`--resume-from` for anywhere else — and the resumed session is told to carry on from there. A
schedule is worth exactly what that record is worth.

**A schedule, never an auto-renew.** Nothing notices that a limit was hit, nothing decides on its own
that work should resume, and nothing repeats unless you ask. There is no way to know whether someone
else's session wants to wake itself up, so a person names the time and chamnan keeps the appointment.

**It writes nothing outside your repository.** No LaunchAgent, no crontab, no registry task. What
runs is a detached child of your own shell that exits as soon as it has fired. `--caffeinate` will
hold a Mac awake until then, and it is opt-in, because keeping a laptop awake for hours is your call.

`--runner` is the extension point: give it any command and that runs instead of the default CLI, so
a harness, a router, or a model with no CLI of its own can be the thing that resumes.

Knowing what to fire *at* is the hard half, and it cannot be answered after the fact — somebody
running several pools or a router in front of many models leaves no trace of which one a session
used. So it is recorded at `set` time: the agent, the config directory in force right then, the
transport, and the process, identified by when it was born rather than by elapsed time. A birth time
needs no tolerance, and this machine sleeps after a minute idle, which is exactly what distorts an
elapsed figure.

**Four commands were telling you things that were not true.** All four are fixed, and each one now
has a test that fails if the wrong answer ever comes back.

### A file five modules import, reported as safe to change

`chamnan-impact <file>` answers "what breaks if I touch this". For a file belonging to a repository
nested inside your own — a vendored checkout, a submodule, a plugin you are developing in place —
it said:

```
a file nothing imports and nothing has happened to is the cheap case — change it freely
```

The index deliberately does not cover a nested repository, and the command was reading that absence
as "nothing depends on it". Those are different answers, and only one of them is honest. It now
says the file belongs to a repository the index does not cover, and to ask from inside that
repository instead.

The same branch already refused the all-clear for a stale index and for a path not on disk. This
was the third case with the identical shape and no guard.

### A stale-knowledge warning that could never be satisfied

`chamnan-age` reports stored knowledge naming a version no environment declares any more. It
reported `python 3.9` as undeclared on a machine whose environment declares `3.9.6`.

`3.9` is the name of a release series, not a vague patch number. A note saying a test "runs under
the 3.9 interpreter" is precise about what its author meant, and the only way to satisfy the
warning was to rewrite it as `3.9.6` — more specific than the author intended. A warning that never
clears teaches you to skip the one in ten that is real.

A claim whose dotted components are a prefix of the declared version is now covered, in either
direction. `3.9` against a declared `3.10` still reports, because that is a genuinely stale claim.

### "Installed" said about an agent that cannot run

chamnan detects which coding agents are present by three strengths of evidence. The weakest is a
configuration directory under your home. The legend treated that directory as proof the agent was
installed on the machine.

It does not. A home directory outlives an uninstall — measured on a machine with two such
directories and no runnable binary for either. It now says configuration was found at some point,
and not that anything is installed or runnable now.

The detector itself was already honest and is unchanged; it reports evidence `home`. Only the
sentence describing it overclaimed.

### "I updated chamnan, and the hooks are still the old ones"

Two different faults produce that one sentence, and this release closes the second of them. If you
have hit it, check both.

**One: the copy that answered was not the copy you updated.** A host keeps a separate install per
scope, and the narrowest one wins. `claude plugin update chamnan@chamnan` updates `user`, prints
that it succeeded, and leaves a `project` install untouched — and it is the `project` one that runs.
Its hooks, its `bin/` commands, its agents and its skills all stay a release behind while the update
reports success. That was fixed in 1.25.1, which added a session-start notice naming the install
that actually answers and the `-s` flag that updates it.

**Two: the version string did not move, so nothing refreshed.** That is the rest of this section.

#### An update that was invisible because the version string had not moved

`chamnan-report` and the session banner tell you when a newer copy is waiting on disk. They
compared version strings only, so a marketplace whose **files** changed while its version stayed
the same reported nothing, and you were told you were current.

This is the case that most needs the notice: `claude plugin update` will not refresh a path install
while the version string is unchanged, so this line is the only signal you would get.

It now compares the content of the shipped code — `lib/`, `bin/`, `hooks/`, `adapters/` — but only
when the two versions are equal, so a real version bump costs nothing extra. Bounded, and it
reports nothing rather than guessing on a tree it could not measure.

Nothing on local disk can tell "the marketplace moved" apart from "you edited your own copy", so
the notice says only what was measured and names both readings.

### A candidate file removed mid-command

`chamnan-candidates confirm 3` resolves a candidate by position, then reads it. If the file was
removed in between — by the background hook's own dedup, or by a second command racing it — you got
a raw `[Errno 2]`, or an uncaught traceback. Three readers lacked the guard that ten of their
siblings in the same module already had.

### A password in your language was not a password

The redactor stops a credential reaching the model. It stopped an English one.

Measured against a corpus of 800 files in eight writing systems: a credential introduced by a
**translated keyword** passed through untouched. The English spelling was caught; the Thai, Chinese,
Japanese, Korean, Arabic, Hindi, Spanish, French and German spellings of the same word were not.
Three of thirty cases caught. It is now thirty of thirty.

The vocabulary was already in the file. It had been added for reading CSV header rows and was never
connected to the patterns that read an assignment — same words, one path covered, the identical
path beside it missed.

The fix groups the vocabulary by **script**, not by language, because they are not the same thing:
German, Italian, Dutch and Indonesian are not English and are plain ASCII. Each script then gets the
rule that fits it. Thai, Chinese, Japanese and Korean do not put spaces between words, so a keyword
joined to the next word is ordinary writing there and is now caught — `รหัสผ่านใหม่` used to pass.
Latin, Cyrillic, Arabic and Devanagari keep word boundaries, so `passwordless` and ordinary prose
are still left alone.

A Kubernetes Secret's base64 `data:` value under a key name with no credential word in it also
passed. That is closed.

### A variable named after the secret it holds

A variable called `secret`, assigned the word *secret*, printed its value. So did `credential`,
`apikey`, `passphrase`, `auth`, `cred`, `keypass`, `storepass`, `passwd` and `secretkey`. Only
`password` was caught.

The rule that decides these reads the letter case of the key. An ALL-CAPS `CREDENTIAL` assigned its
own lowercase name is the enum idiom and is left alone; a lowercase `credential` assigned the same
word is a variable holding a value somebody did not choose. That rule was unreachable. An exemption added earlier — for the
`accessToken = "access_token"` shape, where a key and value are one name spelled by two conventions
— answered "this is a label" for every key whose value repeats it, and it runs first. `password`
escaped only because it is on the list of default credentials that the exemption steps around.

When the two spellings are identical there is no convention gap to explain, so that exemption now
defers to the case rule instead of answering. Both `accessToken` shapes still work and are pinned.

A bare `key` or `token` is still left alone deliberately: in source it is far more often a map key
or a lexer token than a credential, and the credential spellings all carry a second component —
`api_key`, `access_token`. The check states that, so a change there has to be deliberate.

The check that caught the first of these asserted one example. Its replacement derives the whole
credential vocabulary from the module and asserts every word in it, so a word added later is
covered on the day it is added.

### And six places it was destroying text that was not a secret

Found in the same corpus run. A GraphQL type annotation could be mangled file-wide; Swift and Dart
`Codable` raw values, a SQL `COMMENT ON ... IS`, a Lua cache key and a Protobuf field name were all
being rewritten. One of them is worth naming: the guard meant to protect non-ASCII prose was itself
ASCII-only, so it failed on `contraseña`.

All six are fixed, and the check that pins them also asserts that six near-neighbour real secrets
are still redacted — because the easy way to stop over-redacting is to start under-redacting.

The published recall figure moved with the work, from 95 of 96 to **98 of 99**. It is measured by a
tool you can run yourself.

### chamnan-recall now searches what the project already refused

`chamnan-recall <question>` answers "what do we already say about this". It searched rules,
decisions, lessons, skills, threads and sessions — and not the two files written specifically to
stop work being repeated: the refused-topics list and the research backlog.

So the tool built to prevent repeated work could not see the record of what had already been
decided. Both are now indexed by section rather than as whole files, so a match names the heading
that answers you rather than the file it sits in. A refusal ranks just under a standing rule,
because a refusal carries the measurement that produced it.

### Also

- A session reading one of chamnan's own skills is now recorded. It never was, which meant chamnan
  could not see the event its own discovery numbers describe.
- `chamnan-guard` names newly staged MCP server configuration, so a commit that grants a tool
  execution or network capability is visible at review time. Advisory by default; `--strict` fails.
- A staleness scan and a corpus sweep both skipped, in silence, any knowledge store named by file
  rather than by folder — so two of the places chamnan looks were never actually looked at. Both
  now cover them.

### Verify it yourself

```bash
git clone https://github.com/ArcticFox2029/chamnan && cd chamnan
python3 tools/verify_release.py
```

**5,081 / 5,081 passed. 0 failed.**

That is a fresh clone of this tag. Your own total will land near it rather than on it: some checks
need a developer setup a clone does not have, so they report themselves skipped instead of running,
and how many depends on your operating system. The half that should be identical everywhere is the
second one.

**98 of 99 secret and personal-data shapes are redacted.** The one that is not caught is named in
the tool's own output, with the reason: it carries no prefix and no keyword, so only entropy would
find it, and entropy eats commit hashes.

### The research behind it

**21 findings reached the code in this release. 722 in total.**

Each is a place in the shipped source where a defect a research round found was fixed, linked to the
commit that fixed it, so a claim can be followed to a diff. `INDEX_CITED_IN_CODE.md` is attached to
this release and carries all of them.

## What's new in 1.25.1

**A plugin can be installed more than once on the same machine, and the copy that answers is not
always the copy you updated.**

1.25.0 was deployed to three accounts. Each one was verified file by file against the release and
reported complete. One of them went on serving 1.24.0.

A host keeps one install per **scope** — `user`, `project`, `local`, `managed` — and the narrowest
one wins. `claude plugin update chamnan@chamnan` updates `user` and prints `✔ updated to 1.25.0`,
which is true and is not the whole truth: a `project` install pinned at the home directory stayed a
release behind, and because every session runs somewhere under the home directory, that was the copy
answering. Its hooks, its `bin/` commands, its agents and its skills were all a release old.

Every version string anyone thought to check said 1.25.0, including the script written to check it —
which read the first record in the registry and stopped.

**chamnan now says so at session start.** It reads the host's own install registry, which is a file
sitting beside the cache it is running out of, and names any other version registered on the
machine — with the **scope**, because that is the part the fix needs:

    claude plugin update chamnan@chamnan -s project

Without `-s` the obvious command updates `user`, reports success, and changes nothing.

**Why the existing check could not catch it.** `reconcile_version` reports a *downgrade* — an older
build running in a workspace a newer one has already touched. That fires after the wrong version has
run, and only where a newer one has been. It cannot see an install sitting unused that will win the
next time a session opens in a different directory. The new check looks at the installation rather
than at the workspace, which is the only place the answer exists before the damage.

No network and no host API: the registry is a file the host already maintains.

**The gate that was supposed to catch this could not see the file.** `lib/installs.py` was written,
the suite passed 4,878 of 4,878, the file was committed, and CI then refused it on all five
platforms for a literal the local run had never read: the redactor self-scan listed files with
`git ls-files`, which names only what git ALREADY TRACKS. A file added by the same change the gate
is gating had never been scanned by it — and a new file is the likeliest place for a credential to
arrive. The sweep now includes what is untracked and not ignored, which is exactly the set about to
be committed.

### Re-run it yourself

**check 4879 / 4879**, and 1,475 of 1,475 index claims true, on the code this tag carries.

    python3 tools/verify_release.py

---

## What's new in 1.25.0

**A guard you never point at anything reports nothing, for ever.** chamnan's redactor has always
watched what leaves for the model. It had never been pointed at the direction a secret actually
leaves a machine, which is `git commit` — and the pre-commit hook chamnan installs only rebuilt the
index. Several things in this release are that shape: a check wired to one store of two, a version
stamp nothing carried, a column header in a language the matcher did not read.

The rest is **228 defect records** across 90 files, in a handful of shapes. They came from **57
research rounds**, each named on the row of the attached index that carries the fix.

### A password column in a language the redactor did not read

**A blended recall number hid a whole class of leak.** The redactor scored well on prefixed vendor
tokens — `ghp_`, `xoxb-`, `sk-ant-` — and the aggregate never moved while shape-only credentials
stayed open. The one that mattered: a table whose COLUMN HEADER says what the values are.

`chamnan-peek` built its summary from parsed rows. Column names went out comma-separated on one
line and the sample rows pipe-separated a dozen lines below, so the two never formed a table, the
column-marking rule had no header row to work from, and the choke point at the end scrubbed a
document in which nothing looked like a credential. `redact.scrub()` on the same file's raw text had
been redacting it correctly the whole time. The rule was there; the shape it needed was not.

**And the header list was English.** A CSV column called `contraseña`, `senha`, `mot_de_passe`,
`密码` or `รหัสผ่าน` printed its values. `_HEADER_LANGS` now claims **16 languages and 36 terms**,
and the suite asserts every one of them is actually matched — so the next gap is a failing check
rather than a silent miss.

### The redactor now guards the direction a secret leaves

`chamnan-guard` reads the staged diff and names files that look like they carry a credential.

**It warns; it does not block.** Published recall is 99.0% on a synthetic corpus, and 93.8% in its
weakest class, and it verifies
nothing against a live service, so a false positive that stops every commit is worse than the leak
it guards — the person turns it off, and then nothing is watching. `chamnan-guard --strict` exits 1
for anyone who wants the gate.

**It never prints what it found.** A finding is a path and line numbers; the matched text never
leaves the scan. Reading it out would copy the secret into a terminal, a CI log and an agent's
transcript — three more places it now exists.

It reads ADDED lines only. A removed line is a secret leaving; a context line is already committed.
The pre-commit hook runs it, deliberately outside the added/deleted/renamed branch that guards the
index rebuild — because a credential arrives by editing a file that already exists.

### Nothing chamnan wrote could say which chamnan wrote it

A file written by 1.12 was structurally identical to one written by 1.24. No tool, no session and no
reader could tell them apart, and the staleness machinery watched `MAP.md` and nothing else. The
case that surfaced it was an installed git hook nineteen days and about nine releases behind the
workspace's own version file sitting beside it, reported by nothing in all that time.

Every artefact now carries the version that wrote it, and chamnan reports drift without being asked
— in the session block and in `chamnan-map`, which is what the installed hook runs. Three states,
because they need different answers: **no version** cannot be assumed current; **older** is a
distance; **newer than the running build** is never quietly rewritten down.

The order mattered more than the stamp. The marker FINDER was widened to accept both shapes before
any writer emitted the new one — the other way round appends a second block to every `AGENTS.md` in
the world, exactly once.

### Checks that reported a pass they had not performed

**A failure path asserted by its symptoms passes when the code crashes.** A check for "this refuses
cleanly on a read-only file" tested exit 1, no success message, and the file unchanged. An uncaught
`PermissionError` satisfies all three. Failure paths are now asserted by the artefact of HANDLING
them — the sentence the code chose to print, and no traceback.

**A check that greps for its own subject matches the comment describing it.** One asserted a hook
"calls `chamnan-guard`" by substring, and passed on the comment naming the command while the
invocation was gone.

**A predicate can be too loose and report honest code as a defect.** One matched any function using
`.relative_to`, `.parts` and an `except` — four unrelated functions — instead of the body shape it
meant.

### A rule applied to some members of a set

The defect this codebase produces more than any other, and this release closes eight instances of it.

- The vendors warned about duplicate delivery were **4 of 8 that qualify**; the set is now derived
  from a declaration each adapter carries, so one added later joins by existing.
- That warning also fired in **one ordering only** — writing `AGENTS.md` second created the same
  duplicate in silence.
- **Three copies** of "is this registered tool really there", and the round that found it reported
  the one reader that was MISSING the check rather than that the check existed three times.
- The `**Check:**` grammar was wired to `memory/rules/` and nowhere else, so four skills' trailers
  had **never been evaluated once** — and six of the eight named a directory where the grammar
  wants a file glob, so they could never have passed.
- **Six byte-identical copies** of the wrapper whose entire job is that a hook cannot take a session
  down; the sixth was added by copying the fifth.
- Two derivations of the fence marker, and only one carried the reasoning for why it is safe.
- Three modules that group files by location each decided the out-of-root case alone.
- Every write in the package goes through the atomic writer — a rule applied one writer at a time
  until three were still bare, two of them sitting beside the comment explaining why they should not
  be.

### Writes that were not atomic, and a runner outlived by its own child

`Path.write_text` truncates on open. `.version` is written by every session that starts, and its
own unreadable-file branch prints a ⚠ banner in chamnan's voice — so the failure mode of the unsafe
write was a warning about the corruption the write itself caused.

The check runner ran the script it generates with no timeout and no stdin. One sat for **5 hours 59
minutes** at 1.3% CPU holding a machine down, with a frozen terminal and a `^C` that did nothing as
the only symptom. Both fixed at the runner: a child cannot outlive the command that started it, and
a child that reads stdin inherits a terminal nobody is typing at.

### A fast path that only ever ran on a young repository

Reading `HEAD` off the filesystem instead of spawning `git rev-parse` shipped in 1.24. It read a
loose ref — `.git/refs/heads/<branch>` — and handed every other shape back to the subprocess.

`git gc` moves branch tips out of that file and into `.git/packed-refs`, and that is what happens to
every repository that lives long enough. On a packed repository the fast path therefore did nothing
at all — and the roll-up that calls it runs several times per session start, so it was four calls
and four subprocesses on exactly the mature repositories the optimisation was written for. It had
been verified against a freshly `git init`ed fixture: the one shape that never has packed refs.

Packed refs are read now, consulted only when the loose file is absent, which is git's own
precedence. The value is a cache key, so every uncertainty still returns nothing and asks git —
a stale ranking served as current is worse than a slow answer.

The test beside it was reading one repository shape and stopping. It builds six — loose, packed,
detached, worktree, unborn and not-a-repository — and now asserts across all of them that no shape
answers from disk with something git would contradict.

### A command in the release notes that nobody could run

1.24's notes invited the reader to regenerate the citation index with a tool that has never shipped
in this repository. Pasting the line produced `No such file or directory`.

Every `python3 …` command printed in a code block anywhere in this repository's documentation is
now held against what actually ships — paths under `.gitignore` included, because a path that
exists in a development checkout and in no clone reads as runnable and is not.

### Reports that named the wrong thing

- `chamnan-report` printed a hand-deleted tool as a real one at 0 runs — indistinguishable from one
  worth demoting.
- `--written-agents` named the root `AGENTS.md` as `amp`, a product the user of Codex, Devin, Kimi
  or Warp has never mentioned. An alias is a spelling of an adapter; the answer is the adapter.
- The model-family table missed **every namespaced ID** — `anthropic/claude-opus-5`, Bedrock's
  `us.anthropic.…`, Vertex's `publishers/anthropic/models/…` — handing those users a 2.7× smaller
  index budget while the note said their family was "not in the model table", which was true of the
  string and false of the family.
- A declared `CEILING` is a promise about the FILE, and the file is the block plus the wrapper plus
  the marker plus the snapshot line. Three of the four were counted.

### `chamnan-report` answers two more questions

**Which recorded skills are pulling their weight** — from the pointer log and the store on disk,
with each never-named skill's AGE beside it, because one written yesterday has had no chance.

**What raising `rules_char_budget` would actually cost**, as a constraint and never a
recommendation: on a store like this one, fitting a third of the rules costs more than half of
everything chamnan may say at session start. Whether more rules SHOULD arrive in full is a
judgement, and it stays with the person reading it.

### The test suite failed for everyone except the machine that wrote it

**If you cloned chamnan and ran its own test suite, fifteen checks failed.** Not because anything
was broken — because those checks read the development workspace, two directories above the
checkout, which exists on one machine in the world.

Nothing distinguished them from real failures. The suite ships with the package, and a suite that
cries fifteen times is one nobody runs twice.

The checks that genuinely test the development environment now say so and skip, naming what they
skipped and why. They run for anyone who has that workspace and stay quiet for everyone else — and
a silent `is_file()` guard was not accepted as the fix, because a check that quietly does nothing
looks exactly like coverage.

### A published number measured over a corpus missing the case it was about

**The redactor's recall figure was one blended number, and one blended number can hide an entire
class.** Splitting it by the retrieval problem each case poses — a credential named by an
assignment, sitting under a column header, described in prose, or standing bare — showed the
column-header class held **no cases at all**.

That is the class that leaked. A password under a CSV header escaped in every language including
English until this release fixed it, and the number published beside that fix had never tested it.

The corpus now derives its column cases from the redactor's own list of claimed languages, so a
language it claims is a language it is measured on. Sixteen languages, thirty-six cases.

**And the fix moved the headline the wrong way, which is worth saying plainly.** Those thirty-six
cases pass, so the blended figure ROSE from 98.3% to 99.0% — a number improved by testing more of
what already worked. A headline that flatters is the same defect as a headline that hides. So the
documents publish the pair: **99.0% overall, 93.8% in the weakest class**, and a check fails if
either number goes missing.

### Two more numbers that could be confidently wrong

**A file chamnan cannot read is not a file nobody described.** Both landed in the coverage figure as
the same miss, and only one is fixable by writing a docstring. The coverage line now says which is
which, and still counts them — removing them raises the percentage, which would mean a repository
scoring better because chamnan could read less of it.

**The list of accepted findings could grow without anyone noticing.** When the redactor's self-scan
finds something new, the cheapest way to make the check pass is to add it to the accepted list,
which silences a real finding exactly as well as fixing one. The list has a ceiling now, and raising
it has to appear in a diff.

### Where each fix came from — attached to this release

**`INDEX_CITED_IN_CODE.md` is attached as a file**, so any claim above can be followed to a diff
without cloning anything.

This release carries **188 research findings**; the index now holds **686** in total. Read the
attached file for which finding became which line. Every row is derived from the shipped source and
from `git blame`, never written by hand, which is why it can be checked: each row names a file, a
line and the commit that fixed it, and a row nobody can follow to a diff is not in it.

### Re-run it yourself

**check 4869 / 4869**, and 1,466 of 1,466 index claims true, on the code this tag carries.

    python3 tools/verify_release.py

It runs the suite and the index claim check on your machine and prints what happened. It refuses to
report a result when the suite's totals line is missing, because a run that dies mid-way prints no
failure lines at all.

### Credit

**Peter (`peterbuildssecure`) on dev.to** — a DevSecOps builder whose stated audience is solo
founders and small teams shipping with AI.

He raised the redaction gap on chamnan's own write-up twice and was right both times. His argument
that a blended recall figure hides a weak class is what turned "the redactor scores well" into the
per-language header work in this release: a password sitting under a CSV column header escaped in
**every language, English included**, while the aggregate number never moved. `_HEADER_LANGS` exists
because of that discussion.

Four of his arguments are built into this release, and the one above was not the only thing they
found. Measuring recall per class — his point, applied — showed that the corpus behind the published
figure contained **no column-header case at all**. The vulnerability had been fixed; the measurement
that should have caught it never sampled it.

His other three: report a rate with its denominator, keep a third bucket for cases the tool cannot
decide rather than counting them as misses, and hold the list of accepted findings to the same
review as the thing it governs. Each one names a way a number can be confidently wrong, which is
this project's own recurring failure.

---

## What's new in 1.24.0

**A context tool fails quietly.** The block fits, nothing errors, every number on screen looks
healthy — and a third of what you wrote is not reaching the session.

This one was found in ordinary use rather than by reading code: a workspace that kept forgetting,
where work done in the morning was gone by the afternoon and answers came back confident and
unsourced. Measuring it turned up several things chamnan already knew and had never told anyone.

The rest is **219 defect records**, and they fall into a handful of shapes. They were found by the
reports of **37 research rounds**, each named on the row of the attached index that carries the
fix — which is also where the running totals live, so they are not repeated here.

### What this workspace is not delivering

`chamnan-report` has a new section. It is silent when there is nothing to say. On the workspace
where the forgetting was reported, it said this:

```
What this workspace is not delivering
  STATE.md is 13,474 bytes and 3,812 of them reach a session (28%). The rest is named at the
  end of that section and nothing fetches it.
  No session records at all, so "where the last session stopped" is empty every time and
  yesterday's work reaches today only if somebody typed it into STATE.md.
  5 of 9 rule(s) reach a session as a title only (24,293 characters against a 1,500 budget).
```

Its block was 7,997 bytes against a 9,000-byte ceiling with no section dropped: every number a
person would think to check said it was fine. Nobody can be asked to count bytes against a budget
they have never seen, so the tool counts them.

`rules_char_budget` is the new setting behind the third line. **Every rule is always NAMED in the
block**; this decides how many arrive with their body rather than their title. It was hardcoded at
1,500 characters on a day when the repository it was written in had one rule; by nine rules, five
were arriving as names and nothing anywhere said so. A rule about a KIND of work belongs in
`.chamnan/skills/`, read when that work starts — which is what the report now suggests, naming the
candidates.

### Things chamnan measured and never read back

**`blocklog` has recorded the shape of every session block since Stage 10, and nothing read it.**
Its own docstring names three defects that each went unnoticed for hours — a block cut rather than
shortened, ~257 bytes and a section lost to a tools-index bug, a banner that jumped to 34,728 bytes
— and says "all three are obvious in a column of numbers". `chamnan-report` now checks that column
for exactly those three: `early` straight through, a byte collapse against the trailing median
rather than a fixed number, and a section carried in at least half the window and not in the last
block. Replayed over 36 real records it is silent; each defect recreated by substituting one field
fires exactly one line.

**`interrupted` and `stderr_seen` have been maintained on every tool call since Stage 10** and
printed nowhere. One tool here had written to stderr on all ten of its recorded runs while the
report said "10 runs". Both are reported now — stderr only at three runs or more with every one
noisy, because it is a weak signal; `interrupted` with no threshold at all, because a command
somebody stopped is an unambiguous fact.

**`tools/index.json` tracked 3 of the 43 scripts in `tools/`.** The other forty had been placed
there by hand, which the README documents as normal, and were invisible to every mechanism chamnan
has for asking whether a tool still earns its place — including the pre-commit gate and the
regression suite themselves. They are named now, most recently changed first.

**`chamnan-context --write <agent>` printed the path and nothing else.** The file it creates is
18,805 bytes / 7,959 tokens on this repository, against the hook's 8,942 / 3,799 for the same
information, and that difference is deliberate: `output_byte_ceiling` is the host truncating a
hook's stdout, and a file on disk has no such cut. What was wrong is that the person typing the
command was never told the number, at the one moment they have both the figure and the choice.

**The benchmark folded away the one result it produces that is not about tokens.** On the
credential-audit question the bare arm refused outright and the chamnan arm produced a 45-entry
table; both are defensible on a corpus its own README calls fictional, and reporting neither is
not. `run_bench.py` now prints the refusal-versus-compliance delta separately from cost and from
scoring.

### The commit hook, and what it did to repositories that were not ours

**It could put work into commits you did not stage.** The hook ended in `git add -u`, which stages
every modification to every tracked file. Reproduced end to end: stage one file, leave another edit
deliberately unstaged, commit with a message naming the first — and the commit contains both, with
no error and nothing shown. It now stages only the paths it wrote, taken from each command's own
output rather than from a second list that can disagree with it.

**Appending to an existing hook could disable that hook.** A POSIX hook exits with its LAST
command's status, and chamnan appended always-succeeding shell after it. lefthook's installed hook
ends in a plain call; a hand-written `! git diff --cached | grep -q TODO` ends in a test. Both kept
PRINTING their failure and stopped BLOCKING the commit, with nothing on disk to say the gate had
stopped gating. The original status is captured and handed back through `( exit $status )` — a
subshell rather than a bare `exit`, so a line the user appends after chamnan still runs.

**Two neighbouring installs reported success and did nothing at all.** `pre-commit install`'s hook
is an if/elif/else whose every branch ends in `exec`, which replaces the process — so the append
landed after a line nothing reaches, the install said it was installed, and the index never
refreshed once. husky v9 points `core.hooksPath` at `.husky/_`, a directory it generates and
gitignores: the file chamnan wrote was untracked and would be overwritten by the next
`npm install`. Both are refused now, each naming the one line to add by hand and where.

**And `--uninstall-git-hook` exists.** Every tool chamnan appends beside — husky, lefthook,
pre-commit — ships one. It removes chamnan's block and its status-preserving preamble and nothing
else, and deletes the file only when it held nothing but chamnan's block.

### A cap that chose what you see by the first letter of a filename

**Twenty skills in this repository, eight of them never injected** — including one written the day
before to stop a repeated mistake, cut from every session because its name began with a w. The
same shape was found in memory titles, in the lessons a session is shown, in the tools index and
in the rules section, each fixed alone before anybody asked the question of the family. All of
them rank by recency now, with the filename as the tie-break, because after a clone every mtime is
the checkout time and the order should fall back to exactly the previous behaviour rather than to
noise.

A derived check now fails if a new capped list of workspace files is added without a ranking key.

### Checks that reported a pass they had not performed

**`chamnan-age` printed "every version named in stored knowledge is still declared" over a check
that had skipped files.** An entry it could not open was dropped from the loop in silence — one
`chmod 000` was the entire difference between a correctly detected finding and a clean pass, in the
module whose own docstring spends four paragraphs on a false all-clear being worse than no check at
all. Unreadable entries are counted and named. `deploy_drift()` had the same shape one function
down: `except Exception: return []` made a broken scanner indistinguishable from a repository with
no manifests.

**`map_claim_check.py` verified 1,313 claims and said nothing about chamnan's own command
surface.** It checked function and class counts only where `path.suffix == ".py"` — sound
reasoning, wrong discriminator, because every `bin/chamnan-*` command is Python with no extension
and is indexed as Python through its shebang. Eleven files, now checked like any other.

**The suite's totals line said only what RAN.** One commit reported 3,846 checks on ubuntu-latest,
3,844 on macOS and 3,783 on windows — 63 fewer — and all three went green with nothing saying they
had measured different things. Every skipped block already printed its reason; the count now
reaches the line a reader takes the number from.

**Malformed-payload safety was tested for two of the six hooks.** All six carry a wrapper written
for exactly one purpose — garbage from the host must never take a session down — and four of them
had never been fed any. The property held in all six when it was finally measured, which is the
point: it held by nobody's design.

### Reads and writes that were not bounded, and locks that were not held

**Three stores did read-modify-write with no lock at all** while their siblings held one, so a
second writer's work was lost. **`peek_pdf` had no size bound and a quadratic extraction regex** —
a 1.5 MB crafted PDF held the real CLI for 16 seconds. **Several reads took a repository file
whole** while `mapper` refused anything over the same limit, and the limit itself was written out
by hand in three places.

### Credentials that were reaching the model

Three families the redactor could not see, and one place it marked where nothing was.

**A credential name with no separator in it.** `PGPASSWORD` — Postgres's own environment variable —
along with `APISECRET`, `CLIENTSECRET`, `APITOKEN`, `ACCESSKEY` and `PRIVATEKEY` leaked in full,
because every rule needed a separator or a capital to find the second word. **Bare `pass` was
missing from the word list entirely**, which is Ansible's own `ansible_ssh_pass` and
`ansible_become_pass`. **The personal-data gate read the current line only**, so a value followed
by its label — the ordinary shape of a chat transcript or a support ticket — leaked a
checksum-valid national ID.

**A list of secrets under one key kept everything after the first.** Every assignment rule answers
"name, separator, ONE value" and stops, which is right for an assignment and wrong for a JSON array
or a YAML block sequence. **A value containing its own `=`** — base64 padding, or an ODBC
connection string packing several `KEY=VALUE` pairs — lost the redaction almost entirely while a
`<REDACTED>` marker sat beside the plaintext saying otherwise.

Also: Slack's rotation-era `xoxe-` prefixes, a JWT whose third segment is shorter than eight
characters, a CPF written with spaces, an IBAN compared against the unfolded line where its six
sibling rules used the folded one, and `<password>` as an XML tag where the credential word was not
first.

And the other direction: **`api_key_env = "MY_SECRET1"` holds the NAME of an environment variable,
not a secret**, and was being redacted.

### Unicode, in the places it had been fixed once already

**A C function whose return type is not ASCII was absent from the index** — not mis-named, absent.
The same fix had been made for Ruby weeks earlier and recorded as checked for C, which was true of
the function's NAME and false of its return type, which is the position the anchor actually guards.

**`[]…]` and `[^]…]` — the standard way to put a literal `]` in a character class — were rewritten
into a different regex that still compiles.** Nothing shipped uses the idiom, so this was dormant
rather than live; it is fixed because a wrong answer with nothing to signal it is the failure this
codebase warns about most, and the next person to write a language rule would have had no way to
see it.

**A thread name was reduced to lowercase ASCII to make its slug**, so two Thai names became one
file. Case-collision detection reached some stores and not others; it now reaches threads,
sessions, candidates and the skills listing.

### Lists that were cut short without saying so

Seven of them, in one file and the two beside it. A repository with seven unreadable extensions was
told about three. A 30-column SQLite table was reported as a 12-column one. A compose file with
sixty services reported forty — because the cap was applied at extraction, where the renderer that
prints `+N more` could not see it.

### Windows was running a different program

Four defects that were only ever wrong on Windows, and one that was only ever wrong on the Pythons
most people run. None of them errored anywhere. Each was a rule that held on the platform it was
written on.

**A symlink pointing out of the repository was read into the transcript.** `chamnan-peek` refuses a
link that a repository chose whose target sits outside it — that guard compared a resolved path
against an unresolved one. On macOS and Linux the two spellings always agree, because `getcwd()`
returns a canonical path with no links in it. Windows returns whatever string the process was
started with, short `PROGRA~1`-style components included, so the two sides could not match and the
guard was simply absent. It resolves the containing directory now, which normalises the name
without following the link being judged.

**The commit hook has never refreshed an agent file on Windows.** It rebuilds the index and stages
it, then reads back which agent files chamnan wrote and refreshes each. Under git's bundled shell
Python ends every line with CR LF, `read -r` keeps the CR, and an agent name carrying one is not a
name chamnan accepts — so the loop wrote and staged nothing, on every commit, since the loop was
written. The index looked healthy throughout, because the line above it parses no output.

**The one instruction a new Windows user is given did nothing when pasted.** A first run that
cannot find these commands on your PATH prints the line to add. It printed `export PATH="…:$PATH"`
to every operating system — three things Windows does not have. It prints the PowerShell form
there, and the suite now asks for the shell it is actually running under rather than for the text
it expected.

**A `.cmd` shim ran a different interpreter than the job that tested it.** Every shim resolves
`py -3`, which is right for a real user — it is what the python.org installer puts on PATH — and on
a runner it means the image's newest Python. Read from a real run: the "python 3.8" job and the
"python 3.13" job both resolved to 3.14.7, so the version axis never reached the shim path at all.
The shims keep `py -3`; a new step reaches the same entry points with the interpreter that was
pinned.

**And on every Python before 3.13, a file the index could not read vanished without a word.** A
symlink loop makes `Path.resolve()` raise, and the walk caught that and dropped the entry in
silence — the one exit from that function that recorded nothing, while every other exit reports
what it refused. 3.13 rewrote `resolve()` to return a path instead of raising, so the same tree was
reported honestly there and silently truncated on 3.8 through 3.12, under a coverage bar reading
100% over a smaller set than the one it walked.

`_redact_secret_lists` also split its input with `splitlines()`, which breaks on eight characters
besides `\n`.

A failing check now prints what it saw, not only what it expected. Three of the findings above were
diagnosed from that line.

### Vendor facts, re-fetched from each vendor's own page

Amazon Q Developer is in its sunset window and AWS names Kiro as the successor — the adapter stays,
since existing subscribers are real users until 2027, and now says so. `roo.py` claimed Kilo Code
"gets its own module rather than an alias", which was false in the commit that wrote it. `trae.py`
contradicted itself across two paragraphs because a correction had landed beside the claim it was
correcting rather than over it. GitHub Copilot combines `AGENTS.md` with `.instructions.md` rather
than choosing, so a repository that ran both `--write generic` and `--write copilot` pays twice —
warned at the moment the second file is created. `.windsurf/rules/` is the vendor's documented
legacy path and `.devin/rules/` the preferred one; the target is deliberately unchanged, because
"legacy, still read" is not "removed".

### Also

- **A repository chamnan cannot index is no longer a dead end.** It got exit 1 and no workspace
  while every other command answered "run `chamnan-map` first". The index still cannot be built;
  the half of chamnan that needs no index now works there.
- **`--undocumented` said "every file already has an opening comment" over a repository it had read
  nothing of**, on a real CPAN distribution, following chamnan's own suggested next step.
- **"8/8 files (100%)" on a repository holding sixteen** now says where the other eight went and
  which sections were read from them.
- **A first run says why these commands are not on your PATH**, once, naming the directory — and
  says nothing to anyone who has already done it, or to any session inside Claude Code, where they
  resolve regardless.
- **`chamnan-map --help` printed two flags in its table and then named them both as undocumented
  three lines below.** Two hand-kept lists of the same flags. Four commands also accepted
  `--list`/`-l` without naming it; a check now walks every command's accepted flags against its own
  help.
- **The knowledge inventory printed "last write" over a date a person had stamped.** A file written
  today came back as written 39 days ago. Each row says which clock answered.
- **`chamnan-impact` answers with what this repository already decided** about the file you are
  about to change.
- The suite left 779 directories in the system temp folder, ran one block twice, and defined one
  helper twice, a hundred lines apart.

### Verify it yourself

One command re-runs every check this note quotes and prints what actually happened on your machine:

```bash
git clone https://github.com/ArcticFox2029/chamnan && cd chamnan
python3 tools/verify_release.py
```

```
chamnan 1.24.0 — verifying this release's own claims

  running the regression suite — about fifteen minutes, no output until it ends
  ✓ 4,418/4,418 checks passed in 12.4 minutes, 0 failing, 0 traceback(s)
  ✓ 1,340 of 1,340 index claims true (100.0%)
  · 7 function bodies written in more than one file — advisory, not a gate

VERIFIED — 4,418 of 4,418 checks pass and 1,340 of 1,340 index claims are true, on this
machine, from this checkout.
```

No network, no dependencies, no API key: the plugin is standard library only and so is the
verifier. It exits non-zero if anything it checked disagrees with this note, and says which.

**The suite's totals line is the proof, not the absence of failures.** A run that dies mid-way
prints a traceback and no failure lines at all, so a `grep` for them reads zero over a run that
stopped early. `verify_release.py` refuses to report a result when that line is missing, which is
the one thing a person re-running this by hand is most likely to miss.

### Where each fix came from — attached to this release

**`INDEX_CITED_IN_CODE.md` is attached to this release as a file**, so it can be read without
cloning anything and without trusting this page.

It links every defect recorded in chamnan's own source to the commit that fixed it, and — where the
research report that found it survives — to that report. Its own counts move every time a round is
archived, which is why they are not quoted here: read the file rather than this page for them. Every claim in the notes above can be
followed to a diff. It is generated rather than written, from the shipped source and from
`git blame` — each row names a file, a line and the commit that fixed it.

The index is deliberately narrower than the research archive it is built from: the archive holds
every round including the ones that measured a dead end, and the index holds only what reached the
code. A report nobody implemented is not evidence for anything.


---

## What's new in 1.23.1

**Measure this on your own repository before installing anything:
[arcticfox2029.github.io/chamnan-measure](https://arcticfox2029.github.io/chamnan-measure/)**

Paste a public GitHub repository. The page runs chamnan's real modules through Pyodide — not a
re-implementation — and reports what would be injected per session, what the redactor would alter,
and a 50-turn simulation over that repository's own files. No server, nothing uploaded, no API key
asked for, and the source it downloads is deleted the moment the numbers exist. Five languages.

The rest of this release is one defect, found in fourteen places, plus two things the tool could
not previously say about itself.

### A rule applied to some members of a set, and forgotten in the identical ones beside it

Every item below is that shape. They were found by separate research rounds, in code written
months apart, which is why they are worth naming together rather than listed as unrelated fixes.

**A rule file's glob could end a session's context, permanently.** `Path.glob` raises
`NotImplementedError` — not `ValueError`, not `OSError` — for any pattern beginning with `/`, and
`rulecheck` caught the other two. One committed line reading ``**Check:** absent `X` in every
`/etc/*` `` left `run()`, hit the session-start hook's blanket `except Exception`, and ended the
injected block where it stood: milestones, the last session's handoff, the tools index, open
threads and the reply style stopped being injected, every session, under a message that never named
the rule. A rule file arrives with a clone, so this needed no local access.

**A committed tools index did the same through a different field.** `sort(key=lambda t: -(t.get(
"runs") or 0))` on `"runs": "12"` is `-"12"`, a `TypeError`. The name in that file was validated,
because a name becomes a path; the other fields were trusted, and a sort key is exactly where an
untrusted field turns into arithmetic.

**All three context-injecting hooks failed to strip zero-width characters, each differently.**
Two bypassed the `print` shadow with a raw write; the third called it faithfully on the finished
JSON, by which point `json.dumps` has escaped every smuggled code point to `\uXXXX` text that no
character filter matches and Claude Code decodes straight back. Reproduced end to end: 44 Unicode
Tag characters in, an instruction back out.

**Eleven places wrapped a repository-derived name in backticks and folded it with `one_line`
instead of making it inert with `as_quoted`.** A filename carrying a backtick closes its own code
span, and everything after it stops being the repository's data and becomes chamnan's formatting.
A report named two of them; the sweep found nine more across five modules and a hook.

**`rulecheck` could name a file outside the repository even though it could not read one** — the
offenders list came from a second, uncontained glob, and that line prints outside the
`[repo:nonce]` fence in chamnan's own voice.

**The forged-milestone detector was wrong in both directions, and its sibling had none at all.**
`rstrip("\n")` removes the blank line it is trying to detect, so two legitimate field-less entries
were flagged while one invisible trailing space hid a real forgery. `timeline` had no detector,
although the comment above its entry regex already said it was "the same shape as milestones'".
A planted `## 2099-12-31` takes the top slot of the Open-threads section and pushes real threads
down.

**`--version` answered a refusal instead of the version** in exactly the two cases its own comment
says it must survive. Six of nine commands put the check first; three put it below the
no-workspace exit and the feature-disabled exit, and the existing sweep passed because it ran every
command inside a healthy workspace — the one state nobody is in when they ask.

**The downgrade banner had no bound and `fit.shrink` cannot drop it.** A committed `.version` of
`999.0.0` plus 500 unknown config keys took the hook's stdout to 34,728 bytes against a 9,000-byte
ceiling, truncated mid-key-name at the host's 2,048.

**The `MIN_FILES` cliff was explained by a count the gate does not use.** `assets.scan()` applies
the floor per top-level directory; the explanation summed globally, so twelve unindexable files
split six-and-six across two directories got the silent exit 1 with no explanation.

**A heredoc body was scanned as shell.** Every `;` `&&` `||` `|` inside one split the command and
each fragment's first word became a fabricated step. Five of the eight candidates in this
repository's own queue carried the token `s` as a result — the `s` of `sed -i '' 's/…/…/'` written
inside a `python3 - <<'PY'` block, read as a command name.

### Where processes cannot be spawned, and where git cannot answer

Fourteen handlers around a git call named "git is not installed" and "git said something odd".
None named `NotImplementedError`, which is how an environment with no process layer fails —
Pyodide and WASM, and some restricted sandboxes and CI containers. chamnan did not fall back to its
no-git behaviour, which it has and is tested for; it raised out of `mapper.scan()` and took the
whole index with it. There is now one `git_cannot_answer()` with fourteen callers and a check that
finds every handler wrapping a subprocess call and requires it to use that definition — which
caught a fifteenth site the first fix had missed.

Two more thresholds in the same family: `git_is_installed()` answered "a file called git exists",
which is true of a git too old for `-C` (added in 1.8.5, 2013 — RHEL 7 and CentOS 7 shipped
1.8.3.1 for years), so the diagnostic added for a missing git never fired and every git-derived
section went silent. And `git_owns()` used `--absolute-git-dir`, which arrived in git 2.13 (2017),
so a bare repository was unrecognised by the git Ubuntu 14.04 and 16.04 shipped. Both fixed, and
the message now names the real cause: telling somebody who has git that git is missing sends them
to install what is already there.

### Two things chamnan could not previously say about itself

**The file beside the block is finally counted.** `chamnan-report` now reports the agent context
files loaded into the same window as chamnan's own block. Measured on this repository: the block is
8,925 bytes against its own 9,000-byte ceiling, and `CLAUDE.md` is 17,116 against no budget at all.
Derived from the vendor table, so it covers all twenty-four agents rather than Claude alone, and
stated as a measurement rather than as advice — a long context file is frequently the correct one.

**Every session now records the SHAPE of the block it was handed**, in `logs/block_shape.jsonl`:
byte totals, per-section sizes, and whether the block stopped early. Not the text — the block is
reassembled from files already in git, so a copy buys nothing that re-running the hook does not.
What cannot be regenerated is what yesterday's block looked like, and all three truncation defects
above are obvious in a column of numbers. 188 bytes a session against the block's ~9,000, bounded
by record count so it cannot grow without limit, and it honours `CHAMNAN_READ_ONLY` so
`chamnan-map --preview` still writes nothing.

### Also

`dead_entries` claimed to be bounded by the index budget and was not: it stated every name in the
on-disk `MAP.md`, 250 ms at fifty thousand. It now walks the tree once above a threshold and stats
below it, because which is cheaper is a ratio and not a rule — 68 ms for the same exact answer, and
the measured crossover is written beside the constant so the next reader does not re-derive it.

### Card numbers and national IDs, in the scripts people actually type them in

The redactor already refused to let a credit-card number or a Thai national ID reach a model, and
this release found the hole in how: **every pattern was written in ASCII `[0-9]`, and Python's `re`
does not match a Thai digit with it.** A checksum-valid national ID typed as ๑๒๓๔๕๖๗๘๙๐๑๒๓ — the
ordinary way to write one in the one market this plugin was built for — went through untouched,
sitting next to the Thai keyword the rule looks for. The same was true of Arabic-Indic, Persian,
Devanagari, Tamil and fullwidth digits. Two separate research agents found it in one round, which
is how a gap that wide survives: nobody had typed a number in anything but ASCII.

It is one fold table now, applied before matching rather than added to every character class,
because a rule spelled into six places is the defect this repository pays for most often. The fold
is codepoint-for-codepoint, so the span found in the folded text is the span replaced in the
original.

What the layer covers, and why each rule is shaped the way it is:

| | |
|---|---|
| **Credit cards** | Luhn **and** an issuer prefix that is actually issued — Visa, Mastercard including the 2-series, American Express, Discover, JCB, UnionPay. Grouped 4-4-4-4 and Amex's 4-6-5, separated by space, dash, dot, NBSP or the narrow spaces a spreadsheet or PDF copy-paste produces. `4111.1111.1111.1111` used to pass through whole, with the word "card" on the same line. |
| **Thai national ID** | Checksum and a word naming it on the same line. |
| **IBAN** | mod-97 over the 77-country length table. |
| **CPF** (Brazil) | mod-11, dotted form. |
| **Aadhaar** (India) | Verhoeff, keyword-gated. |

**Each of those earned its shape from a measurement taken before the rule was written**, because
the answer decided the design. A Luhn check passes **9.8% of random 16-digit numbers**, and the
Thai national-ID checksum passes **10.0% of epoch-millisecond timestamps** — the commonest 13-digit
run in any log or JSON file. A checksum alone would therefore destroy one timestamp in ten. So
every rule here is checksum **and** context: the conventional grouped form, which nothing else is
written in, or a word on the same line naming what the number is. A bare undelimited run with no
word near it is left alone on purpose. IBAN mod-97 passes 1.02% of random alphanumerics and CPF
1.03%, so shape alone is enough for those two; Aadhaar's Verhoeff passes 9.99%, so it is gated like
the Thai ID and for the same reason.

One false positive is accepted and the reasoning is in the code beside it: `device_id =
4737-0000-0000-0002` is redacted, because it is card-shaped in every way this module can test. That
costs a model one opaque `<REDACTED>` in a file regenerated from source. The other way round puts a
live card number in the block that goes to the provider on every session, and those are not
comparable.

The invisible-character filter gained the code points Unicode itself deprecates and the invisible
math operators, and deliberately did NOT gain the other sixty-two format characters that survive
it — ZWJ holds a family emoji together, ZWNJ separates a Persian verb prefix, and the bidi marks,
Arabic number signs and Hangul fillers are ordinary letters in languages this tool indexes.

`chamnan-map`'s unindexed tally no longer swallows files a person placed in `.chamnan/tools/`
alongside their own scripts; the CI workflow says out loud that `"3.8"` resolves to different
interpreters per OS; and the release checklist in `docs/verification.md` now states what every
release note must carry, starting with the number of checks that passed.

### The file lock kept its promise on Linux and macOS and broke it on Windows

Every session's bookkeeping goes through one mutex, and under real contention on Windows it was
handing the same file to two writers. Eight processes making four hundred increments recorded
forty-one of them. Nothing raised, nothing corrupted a file; the running total was simply wrong
afterwards, permanently, because nothing recomputes it.

The mechanism was in the waiter rather than in any timeout. Checking who holds a lock means reading
the lock, the poll did that every ten milliseconds, and **Windows refuses to delete a file another
process holds open** — Python's `open()` there does not grant delete sharing. So the holder's own
release failed silently and the lock outlived its owner, and nothing could break it afterwards:
the age rule spares a lock whose PID is still alive, and that PID belonged to a process that was
alive and had simply moved on. Every other writer then waited out its ceiling and wrote unguarded.

The poll uses `os.stat` now, which does not pin the file, and opens the lock only once it is older
than a quarter-second — a critical section here is a few milliseconds, so in a healthy workspace no
waiter ever opens it, while a lock left by a crashed process still gets read and broken. The
release retries its delete twelve times over a quarter-second, and a waiter's deadline now resets
whenever the lock changes hands, because a queue that is moving is one worth staying in.

This is one defect and it produced five different numbers — 31, 41, 83, 187 and 207 of 400 — which
is what a collision rate looks like when it is reported as a count.

Two checks were added so the next one is found on a laptop rather than in CI: the concurrency suite
re-runs its storm under a ceiling scaled to what one lock cycle costs **on the machine running it**,
and a session start is now measured for the number of processes it spawns, because a correct probe
added to that path once took the Windows job from 4m16s to 9m25s and nothing was counting.

---

**3,846 of 3,846 checks passed** on macOS 15 / Python 3.14.7, concurrency 34 of 34, and the CI
matrix runs the same suite on ubuntu-latest, macos-latest and windows-latest at Python 3.8 and 3.13
— all five green. The demo page's sample table was re-measured on 2026-09-08 by `site/remeasure.py`,
which reproduces the browser without one: ten of thirteen rows came back identical to the byte, and
`psf/requests`, `rust-lang/mdBook` and `torvalds/linux` moved and carry their new figures.

---

## What's new in 1.22.1

1.22.0's notes never said how many checks it passed. Every release before it closed with that
number and the platforms it was green on, and a page whose front matter says "verifiable claims,
not adjectives" is the wrong place to drop the one line that is a claim rather than an adjective.
That is what this release exists to correct, and the number is below.

The README's own suite paragraph had drifted the same way: it still read "Over 1,800 checks",
written when there were 1,800. It says "Over 3,600" now.

Six fixes landed alongside it, all of them findings that had been reported and never acted on — a
triage pass found that the backlog rolls up rounds R1-R8 and nothing after, leaving 35 reports
never summarised and 14 findings with no trace in code or archive.

### The tools index destroyed its own history on a merge conflict

`load()` returns `[]` for a file it cannot parse, and `[]` is exactly what it returns for a registry
that never existed — indistinguishable to every caller. The next `chamnan-promote` wrote its one new
entry over the top and every previously registered tool, with its run counters, was gone. Silently
and permanently. An unresolved `<<<<<<< HEAD` is the ordinary way there: `index.json` is committed,
and two branches registering different tools collide in it. Reported independently by two rounds and
unfixed both times, while the guard sat one file away.

### Four more that were reported and forgotten

A badly-resolved merge in MAP.md injected both sides as settled fact — the sibling of a bug whose
STATE.md half was fixed the same day, in the store most likely to conflict rather than least, since
two branches editing unrelated files still collide in an alphabetical index.

A Jupyter notebook was bucketed as payload rather than as source this indexer cannot parse, so a
fifteen-notebook repository reported "described 2/2 files (100%)" while all of its real content was
invisible.

The carry-forward cap counted characters, which mis-prices any script that is not mostly Latin —
measured at 1.99x for Thai at the same character count.

And on Windows: a Python App Execution Alias stub reported "too old" instead of "not installed",
sending a new user toward the wrong diagnosis; and a missing `git` made "Where the last session
stopped" vanish with no diagnostic at all, which is a different failure from having nothing to say.

### On Windows an exited process read as alive

`OpenProcess` succeeding is not liveness there: the process object outlives the process while
anything holds a handle to it, so a lock left by a process that CRASHED was never reclaimed and
every later write was silently unguarded. `GetExitCodeProcess` answers it, paired with a
zero-timeout wait for the one process whose real exit code is 259.

3,662 checks, green on macOS, Ubuntu and Windows at Python 3.8 and 3.13.

---

## What's new in 1.22.0

Sixty commits, and almost all of them close something that was quietly wrong rather than adding
anything. The themes below are the ones that recurred.

### A rule file could hang every session in the repository

`**Check:**` trailers are regular expressions that arrive with a clone and run at every session
start. Five more catastrophic-backtracking families were found and closed, on top of the four
already guarded: ambiguous alternations repeated by *concatenation* rather than by a quantifier;
the same shapes hidden behind `(?:`, `(?P<name>` or `(?i:`, whose group modifier was being read as
part of the first branch; a bounded count over an atom made nullable by `?`; the same made nullable
by an *empty* alternation branch; and an ambiguous alternation wrapped in one redundant group,
which neither alternation pattern could see because a regex cannot look inside nested parentheses.
Every one of them was under thirty characters, and the last of them hung the real session-start
hook past ninety seconds from a single committed file.

The ninth was not found by anyone noticing a shape. It was found by generating them — every
combination of group opener, inner body and quantifier, flat, nested and concatenated, compiled,
filtered to the ones the guards allow, and timed. **That generator is now part of the test suite**,
so the tenth family is reported by name on any run rather than waiting for somebody to spot it.

The guard beside them was refusing `(\d+)` and `(\d{4})` — the most ordinary patterns there are —
because `"" in "+*{"` is true in Python and the check asked about the character after a group,
which is the empty string at the end of a pattern. Every rule written that way had silently never
run. And nothing bounded the *number* of checks a session pays for: fifty ordinary trailers cost
4.5 seconds. Twenty-five now run and the rest are reported as unrun rather than quietly skipped.

### A clock that jumped forward could delete your work

Three separate mechanisms computed a deadline from the wall clock and nothing else. With the clock
400 days ahead — an NTP correction, a dead RTC battery — retention deleted files written seconds
earlier, the orphaned-staging-file sweep deleted the temporary file of a write that was still in
progress (losing the new content while the destination kept the old), and the mutex let a second
process take a lock a live process was holding.

There is no way to tell a jumped clock from real age using the clock that jumped, so each of them
now has a second bound the clock cannot move: process liveness for the two that had a PID available,
and "a retention pass never empties a store" for the rest.

### Writes that reported success and had not happened

`chamnan-timeline new` on a directory it could not write printed "declared", named the file, printed
the follow-up command, and exited 0 — with nothing on disk. Of two dozen call sites for the atomic
writer, two ever checked whether it worked. Every write a person asked for by name now fails loudly,
and says *why*: a read-only file, a read-only directory and a full disk used to produce one identical
sentence and need three different fixes.

### Files that were destroyed, forked, or written wrong

The classifier that decides whether an adapter file is chamnan's own output destroyed a hand-written
one for the fourth time — an italic first line is how a person writes a warning, and that was the
test. It recognises chamnan's own voice now: the framing sentence every generated block has opened
with since 1.8.0, plus a matched fence whose nonce is generated per run.

A UTF-8 BOM — what PowerShell and Notepad write by default — made a thread's title unreadable, so
`chamnan-timeline` forked one thread's history into a second file. Fixed at the read, so every file
chamnan opens is now immune rather than the three parsers somebody remembered.

`chamnan-timeline add --files` wrote absolute paths verbatim into a tracked file, committing one
developer's machine layout. Claude Code requires absolute paths for Read and Edit, so an agent
recording what it touched typed exactly the shape that broke.

### Things chamnan knew and never told anyone

Whether the pre-commit hook that keeps the index fresh is even installed — the detection lived
inside the command that installs it, so a repository whose index was quietly going stale looked
exactly like one whose hook was working. Whether any stored knowledge names a version no environment
declares. Whether a rule's mechanical check *could not run*, which looked identical to a rule that
never had one. Whether every candidate in the queue was machine-detected and unreviewed. And
`environments.md`, which the inventory had never counted at all.

`chamnan-map --undocumented` lists every file with no opening comment, because the two skills told
the session to fix "the files that lack one" and only eight were ever shown — on a repository with
forty, that left 80% untouched and unmentioned. `chamnan-map --verify` checks every mechanical claim
the index makes against the tree and **exits non-zero** when one is false; the checker existed, its
own comment recorded that its parser had been broken for three days "because nothing runs this
file", and it returned 0 whatever it found.

### What a session pays

A resumed session was sent the entire block a second time. It is not resent when the transcript
*proves* the first one is still in context — no compaction boundary after this session's own fence —
and on every doubt the whole block is emitted exactly as before, because the cost of being wrong is
a session with no index at all. Measured 837 tokens to 54.

One optional section could cost more than the whole index budget: eight kinds of twenty Kubernetes
objects with realistic names rendered 4,059 tokens against a 3,000-token budget, and forced the
directory roll-up onto the entire repository's index as collateral. 808 now, with every kind still
named. And chamnan counted *its own workspace* as your uncommitted work, so a clean tree was told
"1 uncommitted file, and nobody recorded what for".

### Leaks

Control characters — ESC, BEL, the bidi overrides — reached the injected block from a session
record's title, and reached the model through the JSON hook payloads where `json.dumps` escaped them
past every check that scanned raw output. `chamnan-map --verify` printed index rows with no
redaction at all, because it shells out to a tool that lives outside `bin/` and was therefore outside
the sweep that requires the guard. That sweep is now derived from what the commands *invoke*.

3,646 checks, green on macOS, Ubuntu and Windows at Python 3.8 and 3.13 — and four of those platform jobs are the reason this release took five CI runs rather than one. Every defect they caught is in the notes above.

---

## What's new in 1.21.0

### Credentials that were reaching the index

A connection string whose password contains `@` leaked. The rule's password class excluded `@`, so
it stopped at the first one: `amqp://svc:a@b@rabbit/vhost` and `mongodb://root:x@y%40z@cluster/admin`
passed through whole, and `postgres://admin:Hunter2@Pass@db/main` came out as
`<REDACTED>@Pass@db/main` — half the password beside the marker that says it was handled. `@` is
ordinary in a generated password and real connection strings do not percent-encode it. No
`jdbc:postgresql://` URL had ever matched either, because the scheme admitted only one layer.

A symlink with an innocent name walked past the "never open this file" refusal. Both refusals judged
the name they were handed rather than the file that gets opened, and opening follows a link — so
`safe_data.bin` pointing at `release.jks` was opened and its readable strings printed, alias and
password-shaped fragment included.

### Files that were silently lost

Five functions turn free text into a filename and three never passed it through the guard that
exists for this: a record titled `CON` or `nul` becomes `con.md` or `nul.md`, which on Windows are
the console and the bit-bucket. The write does not fail, it goes to the device, the record is gone,
and the index says it was written.

The memory stamper read a file, decided, and wrote it back with nothing holding it in between,
while firing on every Write and Edit — so a second write landing in that gap was overwritten by the
stamped copy of the older text.

Three generated shell scripts were written with the platform's line endings, so on Windows the
installed git hook and both generated tool scripts began `#!/bin/sh\r`, which no shell recognises.

### Files that were never described

A destructured JavaScript import spanning several lines ate the comment below it, so the file went
into the index with no description at all. Brackets were counted; braces were not.

### Sizing, and honesty about it

`--model fable`, `opus`, `sonnet` and `haiku` now size correctly. Anthropic's current models are not
called "Claude *n*", so every one of those names fell through to the default profile — a user on a
million-token model told to size for a small window. The four numbers come from Anthropic's own
documentation; `mythos` is deliberately absent, because "probably a million" is not a number, and it
falls through with the table's own note that it is a dated convenience rather than an authority.

`CHAMNAN_READ_ONLY` reached five call sites and no others, so every store kept writing with it
set — including the one a background hook fires on ordinary Bash calls. And the commands were not
told: `chamnan-timeline new` reported "declared — .chamnan/threads/a-thread.md" with nothing on
disk. The first-session banner had the same fault against a repository that is simply not writable,
announcing a workspace it had failed to create.

A `tools/index.json` holding `{}` — a hand-edit, a bad merge — took `chamnan-report` down with a
TypeError rather than reading as empty.

### The suite

Its version-drift check had never run on CI, on any platform: the checkout fetches no tags, `git
describe` finds nothing, and the whole block vanished inside an `if` with no `else`. A check that
skips itself in silence is worse than an absent one, because the green total counts it as passed.

3,215 checks, green on macOS, Ubuntu and Windows at Python 3.8 and 3.13.

---

## What's new in 1.20.1

**A secret whose `=` is on the next line was left in the clear.** 1.20.0 made `redact.scrub()`
faster by running five rules only inside windows around each secret word, and the regex that
decides how far such a window must reach was written as `[^\S\n]*` — whitespace *except* a
newline. `ASSIGNED_SECRET`'s own separator is `[\w-]*\s*['"]?\s*[:=]\s*`, which crosses lines
and permits a quote around the key. So three ordinary shapes —

```
api_password
  = "<40 lines of base64>"

api_password =
  "<40 lines>"

api_password
: "<40 lines>"
```

— found no opening quote, took an un-extended window, and left **39 of 40 lines of the secret
unredacted**, while the same document scanned whole was redacted completely. Found by an
adversarial review the morning after the release.

The direction of that error is the lesson, and it is now written beside the regex: this pattern
decides how far a window *reaches*, so matching too much makes a window larger — slower, never
wrong — and matching too little leaks. It is deliberately more permissive than any rule it
protects.

The differential fuzz that was supposed to catch this generated 400 documents and put every key
and its operator on one line, so it agreed with itself. It now generates line-crossing separators,
and the five shapes above are pinned individually.

Upgrade if you are on 1.20.0.

---

## What's new in 1.20.0

**There is no 1.19.** The releases jump 1.18.1 to 1.20.0 on purpose. 1.19.0 and 1.19.1 were version
bumps made during this work and never published — no tag, no release, no announcement. They exist
because Claude Code installs a plugin from a local directory BY VERSION STRING, so raising the
number is the only way to make an unchanged path marketplace copy itself again, and two were spent
doing that in one evening. Everything they contained is in 1.20.0 below.


Thirty-nine commits, and most of them are the same shape: a rule applied to some members of a set
and not the identical ones beside them. That is this repository's own recurring defect, so these
were found by walking each set programmatically rather than by reading code, and each is held by a
test that asserts the whole set.

### The redactor got faster without getting looser

Five of its rules cannot match text with no secret word in it, so one cheap scan now tells the
other five where not to look. `scrub()` on the 293 KB index goes 277ms to 216ms, byte-identical on
that file, on the test corpus, and on 400 randomised adversarial documents.

Two earlier attempts at this are now regression tests rather than history. The first used a raw
±8192-character window that merged into 77.7% of the real document and was slower than not
windowing at all. The second snapped every boundary to a line ending and argued that made it safe,
because no value class in those rules permits a newline — true of four of the five. `ASSIGNED_SECRET`
delimits its value with quotes, not with the line, so `api_password = "<40 lines of base64>"` — a
PEM key pasted into a config — was left entirely in the clear: the window held the opening quote
without the closing one, so the rule did not match short, it did not match at all.

`scrub(text, windowed=False)` runs every rule over everything, and the suite holds the two against
each other. An optimisation that cannot be checked against the thing it optimises is a claim.

### Output is guarded against what it says, not only what it contains

Every command already prints through the redactor, which removed credentials. A committed file
holding `\x1b[2K\x1b[G` still erased the line the reader had just seen and wrote its own, and
U+202E still reversed what followed — enough to make one command's output read as another's.
`chamnan-timeline show` prints a whole thread body and `chamnan-candidates` prints a title lifted
from a file's first heading, so that text is the repository's, not chamnan's.

### `--preview` writes nothing, which is what it always said it did

In a repository that had never run chamnan it created the entire workspace — fourteen entries,
`.gitignore` and `.gitattributes` included — before telling you what you would get, because what it
runs to answer the question is the hook that sets the workspace up. `CHAMNAN_READ_ONLY` is how it
now asks that hook to look without touching, and the test counts what is on disk afterwards rather
than reading the code.

### It stopped telling other agents to type Claude Code commands

`/chamnan:remember` and its three siblings are Claude Code slash commands, and the line naming them
went into AGENTS.md, `.cursorrules` and the twenty-one other adapter files, because nothing asked
who the reader was. That line exists precisely to tell an agent it is allowed to write, so it
failed worst for the reader it was aimed at. The same went for the first error a terminal user
hits — no workspace here — which sent them to `/chamnan:bootstrap`.

Both now name `chamnan-map`, which works everywhere. And the README says how to get `bin/` onto
`PATH`, without which every example in it is "command not found" — the line it documents picks the
newest installed version rather than naming one, so it does not rot on the next release.

### Smaller things

- A Mercurial or Subversion checkout nested inside a repository is somebody else's code, as a Git
  one always was; its internal store is no longer walked as source. An `.svn/pristine` tree is
  every file in the working copy a second time.
- `chamnan-report` was the one of nine commands that reported on a directory with no workspace in
  it, printing "0 entries, last write never" — which is what a real but empty workspace prints too.
- The update notice can see a plugin installed from a local path, the convention this project is
  developed under, and one `claude plugin update` does not refresh while the version is unchanged.
  Three installs on the machine that writes chamnan sat 25 commits behind while the check that
  exists to say so read a stale copy of a different directory.
- The SubagentStart firing log records every gate with the reason it stopped, so an empty log can
  finally distinguish "never fires" from "fires and finds nothing" — the question it was added to
  answer. It no longer creates a workspace in whatever directory a subagent happened to start in.

---

## What's new in 1.18.1

### The translated pages name the models too

1.18.0 gave all thirty-two translations a row saying chamnan works with any model from any vendor,
and stopped there. The English page listed every family `--model` recognises; the translated pages
did not, so a reader who does not read English got "any model" in answer to the question they
actually had, which is *will it work with mine*.

The omission came from applying the translation set's own rule too widely. That rule is that no
translated page carries a **number**, because figures change every release and a translation does
not. Model family names are not figures — they are proper nouns that change when the table changes,
which is rarely, and they are the single most useful thing that row can say.

Every translated page now names all eleven families, the two left out on purpose and why, and the
exact escape hatch for a model that is not listed. No digit entered the translation set to do it,
and a test now fails if a family is added to the code and any page falls behind — it names the
language and the family that went missing.

Found by the owner reading the rendered Thai page, which is the only way it could have been found:
every check that existed passed.

---

## What's new in 1.18.0

### It now says what it works with, in every language it speaks

1.17.0 shipped twenty-three adapters and a README that still opened with "a Claude Code plugin".
Someone who searched *does chamnan work with Cursor* would have read that sentence and concluded no.

The English page gained four sections written as instructions rather than claims — **installing it
per tool** (three routes in, and which one you get depends only on whether the tool has a session
hook), **using it with Hermes Agent**, **using it with more than one model**, and **running it on
each operating system**. The front page now names every model family `--model` recognises, says
plainly that an unrecognised one still works, and answers the four questions people actually type:
does it work with Cursor, does it work on Windows, does it work with GPT or a local model, does it
work with Hermes.

All thirty-two translated pages gained the same ground — seventeen new keys each, rendered from the
string table rather than hand-edited, and not a digit in any of them. That rule is the translation
set's own: every number lives in the English README, the only page rewritten each release, because a
translated page carrying a release-specific figure is wrong within one cycle and still reads as
current.

### `llms.txt`

The convention for handing a model a short structured description instead of making it parse a
rendering meant for people. This README is over a hundred and forty thousand characters; an
assistant reads the first few thousand and answers from those, so an absent summary is not the
neutral outcome — it answers anyway, from whatever it happened to see.

Generated from the code, never hand-written: the adapters and their targets, the model families, the
commands and the translated pages are all read from the tree. A test fails when the generated and
committed forms disagree, when an adapter is missing from it, or when an anchor it points at is not
a real heading.

### Hermes Agent

Hermes is a self-hosted agent that also acts as a control plane for other coding agents — its own
documentation names Codex, Claude Code, Gemini CLI and OpenCode as things it drives, so a repository
set up for it usually means several tools reading one index.

Its precedence, taken from the official docs rather than a search summary: `.hermes.md` / `HERMES.md`
first and walking to the git root, then `AGENTS.md`, then `CLAUDE.md` and `.cursorrules`. chamnan
already wrote three of those, so Hermes has been reading it since the adapter set shipped. What was
missing is the file above them, and that is what the new adapter writes — sized to the cap Hermes
documents, and refusing to overwrite one it did not write.

### Two more things the index was wrong about

**A bundle with no header saying it is one.** GENERATED_MARKER finds files that announce themselves;
Webpack, Vite and esbuild emit hash-named output that announces nothing. A single-line minified
`.js` was indexed as hand-written source, counted in the coverage denominator and offered to the
commenter agent. Both new rules are GitHub Linguist's own, quoted from its source, and kept as
narrow as Linguist keeps them — a long-lined Python file is a style, not a build artefact, and the
test pins that direction because over-skipping is the more expensive mistake.

**`chamnan-map <dir>` replaced the map in silence.** Replacing is the documented, useful behaviour;
doing it without a word is not. Reproduced on a real map: three hundred and twenty files became a
hundred and fifty-three, every other directory gone, exit zero, nothing printed. It now says how
many described files are about to stop being described, and how to get them back.

### Measured, 1.17.0 against 1.18.0

| | 1.17.0 | 1.18.0 | |
|---|---|---|---|
| agent names it can write for | thirty-four | **thirty-five** | Hermes |
| a repo with a hash-named minified bundle | indexed as hand-written source | **flagged as build output** | |
| `llms.txt` for AI search | absent | **present, generated** | |
| README mentions Hermes | no | **yes** | |
| translated pages covering models, systems, agents and Hermes | none | **all thirty-two** | |
| strings per translated page | eighty-three | **one hundred** | |
| regression checks | two thousand seven hundred and ninety-one | **two thousand eight hundred and thirteen** | |

---

## What's new in 1.17.0

### chamnan is no longer a Claude Code plugin that happens to write files

**1.16.0 shipped zero adapters. This release has twenty-three.** `cursor`, `windsurf`, `copilot`,
`kiro`, `zed`, `continue`, `roo`, `cline`, `aider`, `goose`, `junie`, `amazonq`, `gemini`, `qwen`,
`grok`, `mistral`, `trae`, `replit`, `augment`, `iflow`, `codebuddy`, `antigravity`, and a `generic`
AGENTS.md fallback. Each writes the block at the path that tool actually reads, in the format it
actually parses, under the size limit that tool actually publishes.

That last clause is not decoration. `antigravity` declared no ceiling and emitted 21,388 bytes
against Google's documented 12,000-character cap — 1.78× over, silently, with nothing shrinking and
nothing warning. It emits 11,931 now. `windsurf` had carried the identical fix for two days; the
sibling added the same day did not get it. The ceilings that have been checked against a vendor's own
documentation are now a table in the test suite rather than a constant per file, so an adapter for a
vendor already in that table cannot quietly declare `None`.

### Subagents get context now

`SubagentStart` accepts `additionalContext`. This programme had recorded the opposite as settled —
"subagents and the context they never receive", closed as unfixable — on the strength of a
documentation page that was being truncated before the table that answers it. Three separate
attempts read the event list and never reached the decision-control table; one came back hedged as
"likely". `curl` on the `.md` URL returns all 317,647 bytes at once.

What a subagent gets is a **pointer, not the block**: 958 bytes naming the index, saying to grep it
rather than read it, listing the rules in force, and — the part that took a second pass — naming the
nested checkouts the index deliberately excludes. 96.6% of this repository's own subagent dispatches
start at the outer root while the work is in an inner project, where the outer index mentions the
file they need zero times and the inner one is 85,000 characters about it. An index that looks empty
reads as "this repository is undocumented" rather than "you are looking at the wrong one".

Forks get nothing: they inherit the parent's whole conversation already. Measured over 22 historical
fork dispatches, none ever opened the map.

### Repository text cannot rewrite what you read

A repository chamnan indexes is not a trusted input. Its filenames, docstrings, table names and
directory names are written into Markdown that a model then reads as instructions, and four
consecutive research rounds each found an instance of the same defect and fixed only that instance.

Walked as a set instead: **31 sites in 14 files**, against the 8 that had been found one at a time.
The one that mattered was invisible to every audit of call sites — `mapper._clip()` is the second
whitespace fold in the codebase and never had the control-character table, and its callers assemble
the Markdown afterwards, so no f-string anywhere shows an unsanitised field. Reproduced on a fixture
repository: a docstring carrying `\x1b[31m` and a bidi override reached MAP.md verbatim.

Two guards, because neither shape catches the other: a structural one that walks `lib/` and `hooks/`
and names any unsanitised field, and a behavioural one that runs the real renderer over a repository
built to attack it.

### Windows was never actually working, and now CI says so out loud

The Windows CI jobs were added in this release and had **never been green**. Three real defects were
behind that, and none of them could be found from a Mac — so a lab was built out of the CI runner
itself: six isolated questions run on `windows-latest` with an `ubuntu-latest` column beside them in
the same job.

The first hypothesis was wrong, which is why it was measured. `LOCK_TIMEOUT` was never being
reached: 240 of 240 acquisitions succeeded on both platforms. What was actually happening:

| | windows | ubuntu |
|---|---|---|
| concurrent `open("a")`, 6 × 200 short lines | **1,034 / 1,200** | 1,200 / 1,200 |
| `os.replace` onto a file a reader has open | **PermissionError** | allowed |
| 8 × 50 increments through `record_call`'s shape | **399 / 400** | 400 / 400 |

- **Appends are not atomic on Windows.** The code carried a comment saying "the append path is safe
  on its own — O_APPEND writes of short lines do not interleave". True, and true only on POSIX. 166
  of 1,200 lines vanished with no error anywhere. The append now takes the lock on Windows and keeps
  the lock-free path on POSIX, where it is correct and runs on every Bash call.
- **`os.replace` can be refused.** A write could fail purely because somebody was reading the file
  at that instant. It now retries twelve times over about a quarter of a second and re-raises if it
  still cannot land — a caller that cannot write must hear about it.
- **A lock in DELETE-PENDING state raises the wrong exception.** A lock file another process has
  just unlinked stays visible on Windows: the name resolves, opens fail with `ERROR_ACCESS_DENIED`,
  and Python raises `PermissionError` rather than `FileExistsError`. That fell into a catch-all that
  read "somebody has this, retry in 10ms" as "this lock cannot be taken". One in four hundred, on a
  running total nothing recomputes, so it stayed wrong forever.

Two of the failures were the tests rather than the code — a doubling ratio computed from a 0.000 s
measurement on a 15.6 ms clock, and a path compared in its 8.3 short form against its long one — and
both are fixed. All five jobs are green.

### Measured, 1.16.0 against 1.17.0

Both on the same machine, alternating, the 1.16.0 column being the released plugin as installed.

| | 1.16.0 | 1.17.0 | |
|---|---|---|---|
| tools chamnan can write for | 1 | **23** | Claude Code was the only one |
| a repo with `Pods/`, `Carthage/`, `third_party/`, `bower_components/` | 5 files indexed | **1** | the other four were somebody else's library |
| Antigravity rules file, large-window profile | — | **11,931 bytes** | under the documented 12,000 |
| regression checks | 2,168/2,169 | **2,795/2,795** | the released build has one failing |
| CI platforms green | 3 of 3 | **5 of 5** | Windows jobs added here, and made to pass |
| hooks | 5 | **6** | `SubagentStart` |
| `map_claim_check` on a correct map | 83.6% | **100.0%** | it had been wrong since 2026-09-02 |
| SessionStart hook, this repository | 0.55–0.62 s | 0.48–0.63 s | **no measurable difference — ranges overlap** |
| injected block | 8,618 bytes | 8,647 bytes | +29 |

**Eighty-two commits, 90 files, +9,270 −822.** The theme, again, is chamnan being wrong about
something and finding out: a checker that reported 83.6% about a map independently measured at 100%
and had been doing so for three days because nothing ran it; a `README` that told Windows users to
use WSL on one line and that Windows is tested in CI on another; `atomic_write_text` writing CRLF on
Windows because `write_text` asks the platform; a second drifted copy of the skip list; and
`carry_forward` reading one session record where two people had written two.

---

## What's new in 1.16.0

### 1.15.0 against 1.16.0, measured

Both builds run on the same machine at the same moment, alternating, so a busy laptop cannot favour
one of them. The 1.15.0 column is the released plugin as installed, not a reconstruction.

| | 1.15.0 | 1.16.0 | |
|---|---|---|---|
| SessionStart hook, this repository | 3.23 s | **0.79 s** | 4.1× faster, six interleaved pairs |
| SessionStart hook, 6,000-file repository | 16–39 s | **1.2–2.7 s** | it did not scale before |
| `chamnan-map`, same 33-file corpus | 1.35 s | **0.79 s** | identical output, 537,606 tokens both |
| `chamnan-report` | 7.14 s | **5.20 s** | byte-identical report |
| file opens in one `chamnan-map` | 2,259 | **568** | four scanners re-read what the first had read |
| files indexed in chamnan's own repo | 42 | **51** | its own `bin/` was invisible |
| `lib/redact.py` consumers published | 7 | **16** | the nine missing were the CLI tools |
| files indexed in sveltejs/svelte | 3,480 | **8,060** | 4,540 `.svelte` files were dropped silently |
| regression checks | 1,815 | **2,172** | |

And four numbers that did not get *better* — they got **true**:

| | 1.15.0 said | actually |
|---|---|---|
| "repeat work" headline | 20% → 7% | **28% → 20%** (it counted other repositories' files) |
| coverage on gin | 44% | **~31%** (`//go:build` counted as a description) |
| coverage on svelte | 13% | **4.3%** (a JSDoc `@import` counted as one) |
| `--explain`'s remainder | −3,396 | **positive, and it reconciles** |

**Seventy-nine commits, and the theme is uncomfortable: most of them are chamnan being wrong about
chamnan.** Eight separate claims the tool made about itself turned out not to survive being checked
— a headline metric counting other repositories' files, a docstring promising 0.04s for something
taking 39s, a coverage bar counting compiler directives as descriptions, and an index that could not
see the plugin's own commands. Every one was reproduced before it was believed and pinned by a test
afterwards. The suite is at 2,172 checks.

### It could not see its own `bin/`

Nine command-line entry points — every command chamnan has — are extensionless shebang scripts, and
the indexer decided language from the suffix alone. So `lib/redact.py` was published as used by 7
modules when it is used by 16, and all nine missing consumers were the CLI tools that print output
for a living. Present since the first commit, with the index reporting full coverage the whole time.
A shebang names the interpreter as reliably as a suffix names a language; 42 indexed files became 51.

### Numbers that were wrong

- The **"repeat work" headline** counted file paths from other repositories, because a session
  rooted here dispatches subagents elsewhere and their paths land in this repository's transcript.
  902 of 7,801 counted touches were outside the root. Scoped: 20%→7% becomes 28%→20%.
- **`--explain` billed sections it had already dropped** and printed its own remainder as −3,396 —
  the parts adding to more than the total they were subtracted from.
- **The coverage bar counted directives as descriptions.** `//go:build linux && !windows` was the
  summary of 12 of gin's described files; a JSDoc `@import` of 289 of svelte's 440. Real coverage
  was ~31% against 44%, and 4.3% against 13%.
- **The index warning said "281 file(s) are not in it"** on a repository where all 281 are in it,
  having compared bare filenames against root-relative paths.

### Faster, measured interleaved

    SessionStart hook, 6,000-file repo    16-39 s  ->  1.2-2.7 s
    chamnan-report                          7.14 s ->  5.20 s
    chamnan-map                        3.45-5.15 s ->  3.29 s
    file opens in one map                    2,259 ->  568

The staleness check was reading 8 KB of every file in the tree to answer a question about mtimes.
The symlink guard resolved every path when the short-circuit meant to stop it sat one line below.
`chamnan-report` read 746 MB of transcripts, then read the same 746 MB again.

### Security

A **route path could open a heading in the index it was written into** — reproduced in ordinary,
valid JavaScript, putting an attacker's prose into the region injected into every session. Four
catalogue modules published repository substrings without the markdown neutralisation the codebase
already had. Also: both automatic hooks were the two that never redacted, a committed symlink could
read `~/.ssh/id_rsa` into the block, every `bin/` command now scrubs what it prints rather than
each deciding for itself, and `chamnan-candidates demote` could rename a file anywhere on disk.

### It now reads what it could not

`.svelte`, `.vue` and `.astro` — Svelte's own repository indexed 3,480 files with 4,540 invisible.
The script block is extracted first, because feeding the whole file to a JavaScript reader is wrong
in both directions: it never reaches the doc comment, and an HTML comment in the template becomes a
*wrong* description. Go and Rust environment variables are found now too, added only after measuring
58 and 12 true positives with zero false ones on real clones.

### Honesty about limits

A catalogue's count cap and its per-entry size cap did not compose, so a section could sit inside
both and still cost more than the whole index budget. Sections have a token budget now, proportional
to the one configured. A section that keeps its heading and loses most of its body says so. An
extension chamnan cannot read is named. And when the version string has not moved past the last tag,
the test suite says so, because that string is the only thing that makes an installed copy refresh.

---

## What's new in 1.14.0

**A crash that made the hook print nothing behind a symlink, a command whose own advice erased the
record, and thirty-two translated pages that finally say what this does.** Twenty-five commits.
Every defect was reproduced before it was believed and pinned by a test afterwards; the suite is at
1,495 checks and now runs in CI on Linux and macOS, at the Python version this project calls its
floor and at the newest release.

### CI, and the two defects it found before its first merge

There was none until this release. The front page asserted that Linux was "expected to work, not
tested" and that Python 3.8 was the floor, on a page whose own headline is "verifiable claims, not
adjectives" — a support matrix nobody runs is an adjective. There is no dependency step, on
purpose: chamnan is standard library only, and a workflow that ever needs a `pip install` is the
change to reject rather than the workflow to fix.

It earned its keep immediately.

**`find_root()` resolved its path and `hook_root()` did not.** When the host hands over a path that
goes through a symlink — `/tmp` and `/var` are symlinks on macOS, and keeping a project behind one
is ordinary — one returned `/var/x` while the workspace lookup returned `/private/var/x/.chamnan`,
and the first `relative_to` raised `ValueError`. Uncaught. The hook died with a traceback: zero
bytes of output, exit 1, no message. That is precisely the silent-nothing failure `hook_root` was
written to prevent, reintroduced by disagreeing with `find_root` about one path. Measured on a
symlinked project: **0 bytes before, 4,622 after.** Both layers are closed, because either alone
would let it recur — `hook_root` resolves now, and every path the block prints falls back to the
bare filename rather than raising. A label is never worth an exception.

**`sys.stdlib_module_names` arrived in Python 3.10**, and the fallback below it left the set empty.
So on 3.8 and 3.9 — the two versions this project declares as its floor — every `import re` in the
codebase was reported as a third-party dependency. Standard-library-only is one of three things
chamnan actually promises, and the check for it had inverted into a false alarm on the interpreter
least likely to be the one you ran it on.

Two test blocks were also found to be asserting the author's own folder layout: they resolved a
fixture path two directories above the checkout, which happens to be another chamnan workspace on
that machine and an empty directory everywhere else. On any other machine they tested nothing.

### The command `chamnan-env check` tells you to run was the one that erased the entry

It ends with "re-confirm with `chamnan-env set <name> --checked <date>`". Running exactly that
replaced the whole record — the platform, the versions and every constraint went with it. Anything
not named on the command line is now carried forward from what is already recorded, and
`--platform ""` still clears a field, so there is a way to say it really is empty.

`chamnan-candidates demote` deleted the tool file. A promoted tool ships as a skeleton whose steps
are placeholders — the command's own help says it is not runnable until you fill in the commands —
so demoting destroyed exactly the part a person wrote, in exchange for a candidate that the code
itself calls not a reconstruction. It is archived now, and the path is printed.

### The block told you to read a section it had already thrown away

Caught in a live session: "Full detail lives in `.chamnan/MAP.md`" printed a few lines above a list
naming the architecture index as one of the sections left out to stay under the byte ceiling.
Dropping a section now takes its footnotes with it, and restoring one pays for them out of the same
room. Separately, "Environment constraints" had been emitted since 1.11.0 without ever being
ranked, so it fell to the unranked default and was dropped ahead of everything but the index — the
one section whose job is to stop a wrong action being proposed at all.

### What the index says about real repositories

Found by running the build over tokio and Homebrew rather than over fixtures.

- **A crate root described by an aside about a build flag.** tokio's `src/lib.rs` carries 431 lines
  of `//!` saying what the crate is; the index said "loom is an internal implementation detail. Do
  not show…". A multi-line `#![allow(…)]` matched only on its first line, and once that was fixed
  the first ordinary `//` won, because nothing preferred the marker the language itself uses for
  file-level documentation.
- **A Homebrew tap with nothing said about any of it**: a formula states its summary in
  `desc "..."`, which is not a comment. **0 of 36 described, now 33.** Anchored on the Formula
  declaration, so Rake's per-task `desc` is not mistaken for a description of the file.
- **`(root)` swallowing real directories.** One dominant directory pushing the roll-up to depth two
  sent every single-segment path into one bucket, so production code and integration tests shared a
  group of 175 under a name true of neither.
- Full Detail called a TypeScript interface a class — the half the index tells a reader to grep
  when they want symbol-level truth.

### chamnan-report was reading another project's numbers

Its fallback for a working directory whose exact encoding is missing accepted any transcript
directory ending with this repository's basename and returned the first in sort order. A second
checkout, or an unrelated repo sharing a basename, was silently reported as this one. It ranks
candidates by how much of the path agrees now, and returns nothing at all when two agree equally,
because there is no honest answer there.

Same command: `input_tokens` was unpacked from every usage record and then never added to anything.
That is the input the model read which was *not* served from cache — the whole prompt on every
session's first call, and on every call after the cache expires. Those calls reported a context of
zero and pulled the per-call average down by exactly the calls that cost the most.

And the ledger dated memory entries by file mtime, under a comment saying they carry no date of
their own "until Stage 4 adds `as-of`". Stage 4 shipped three releases ago. On a fresh clone every
decision ever recorded read as written today.

### The front page, rebuilt for how it is actually read

People paste the link into an AI and ask for a summary. It now opens with a self-contained digest
and a contents list, so a summariser that reads only the top of a 1,900-line page still gets the
tool right. The hero image says what chamnan is rather than what its biggest number is; the
token-ratio figure moved down to sit directly under the two rows that produce it, with its
qualification travelling alongside.

### Thirty-two translated pages that finally say what it does

They carried what chamnan is and how to install it, and not one word about the features. Someone
who cannot read English had no way to learn from their own language's page that there is an impact
query, or a secret filter, or that nothing is ever promoted without a person saying yes. Each page
now covers all four capability groups, every command and skill, what is written and where, the
safety guarantees and how to remove it — and still carries no digits, which is the rule that keeps
them from needing an edit every release.

They are generated from one shared table rather than written out thirty-two times, because the
failure mode of the latter is a row missing from some languages that nobody would ever catch. The
suite asserts every language carries every row, none carries a row the others do not, and no page
has acquired a number.

### Quieter ones

`timeline.for_path` follows renames, so a thread entry written before a `git mv` still answers a
question asked about the new name. `chamnan-peek` says when it stopped counting rows and how many
columns it left out, instead of printing a cap as if it were a fact. The Configuration list is
ranked by how many places each variable is referenced rather than cut alphabetically, and says so.
Retention runs from the SessionStart hook instead of only from the two commands in `bin/` that
happened to call it. `entries_naming_no_file` stopped counting `path:line` — the citation format
chamnan's own guidance asks for — as naming no file. The injected tools list is ranked by use, so a
thirteenth promoted tool can actually appear.


## What's new in 1.13.0

**Two credential leaks, a rule that could read outside the repository, and one bug that was thirty
bugs.** Five research rounds, every finding required to come with a reproduction before it was
believed. Twenty-eight defects fixed; these are the ones worth your time.

### A comment mentioning an END marker was enough to publish the key it sat above

The private-key pattern matched lazily, so it stopped at the *first* text shaped like an END line.
A README snippet, or a comment reading "keys are terminated with `-----END RSA PRIVATE KEY-----`",
supplies one — and everything between it and the real END went through untouched. The header and
the decoy were replaced; the entire base64 body of a real key was published. It is greedy now:
over-covering a decoy costs a line of prose.

Three more in the same file. Only four compound spellings of "key" were listed by hand, so
`ssh_key`, `signing_key`, `encryption_key`, `master_key` and `db_key` — the commonest form there
is — were never trigger words at all; `AccountKey` and `apiKey` were missed for the separate reason
that CamelCase has no separator to anchor on. A value that was a call had the callee captured *as*
the secret: `AWS_SECRET = base64.b64decode("QUtJQ…")` redacted `base64.b64decode` and left the
payload beside a line it had just broken. And `auth` was unanchored, so it fired inside
`oauth_flow`, whose value is a grant type — the over-redaction side of the same trade.

### A rule shipped in a clone could read `/etc/hosts` and report the match count

A `**Check:**` trailer is a path written in repository text, and `rulecheck` is the one place such a
path becomes an `open()`. `root.glob()` follows `..`, so a rule reading ``present `localhost` in
`../../../../../../etc/hosts` `` read the real file and reported its match count into the session —
a working oracle for anything the process can open, arriving with a clone. It went around the
never-open list too. Every resolved path must now sit under the repository root.

The ReDoS guard beside it was blind to the other classic shape. It refused a quantified group that
is itself quantified; ambiguous *alternation* has no inner quantifier at all, and `(a|a)*$` measured
0.25s against 20 identical characters, 4.2s against 24, and had not finished at 28 — through a
guard whose entire reason for existing is that hang, on a pattern that runs at every session start.

### One formula for every language produced the same bug once per language

`#` was read as a comment everywhere except three languages someone had noticed. So Rust's
`#[cfg(not(windows))]` became a file's **description** in **149 of tokio's 555 files**, and the index
said a networking module was "[cfg(not(windows))]". Fix Rust and Ruby brings it back; fix Ruby and
TypeScript does. The defect was the shape, not the entries.

Each language now states its own facts and the universal rule is derived from them, so a language
nobody has written facts for is visibly missing rather than silently wrong. Re-measured on tokio:
**149 attribute-descriptions to 0**. Reported coverage falls from 67% to 41% — and that is the
point, the 149 were being counted as described.

Three languages the generic rule could not know. **Ruby**: a method name may end in `?`, `!` or `=`,
so `def boot!` was recorded as `boot` and `def owner=` collided with its own getter; a method name
may be an *operator* with no word character at all, so `def ==`, `def <=>` and `def []` were
invisible; and `module` — Ruby's actual namespacing keyword — had no rule. **Terraform**: a `data`
block carries two names and the second is its identity, so nine distinct `data "aws_iam_policy"`
blocks in a real production module deduped into one row. **TypeScript**: a real 4,133-line `.d.ts`
with 91 exported interfaces reported "100% described" and zero symbols.

### A quoted example could close an open thread and drop it from the next session's handoff

Four modules found their structure by scanning for lines starting with `#`, and none could tell a
heading from a line inside a fenced code block. A thread quoting `**Status:** closed` inside a fence
read as closed, and the next session was never told that work was open. A session record quoting
`## Remaining` split there, and the handoff delivered the fabricated section while dropping the real
one after it. A milestone title carrying a newline wrote a second, well-formed milestone that won
the most-recent slot.

### Thirty-two languages, and the rule that keeps them honest

The README now opens with a flag row. Each translated page is short — what this is, the problem it
solves, how to install it, what to know first — and **none of them contains a number**.

That is not laziness. Measured across large open-source repositories: once a translation is merged,
the English source takes a median of **8.5 more commits in six months while the translation takes a
median of 0**, with a maximum observed gap of 166. chamnan releases often, and a wrong translation
is worse than an absent one because it still reads as current. So the measurements stay in English
and every translated page links to them. The ordinary release touches one document.

### The strongest evidence against this tool is now on its front page

A leak-audited causal ablation of an index *richer* than this one beat a grep-only agent by +5.1pp
on resolve rate at **p = 0.087 — not significant**, with the gain concentrated in cross-file changes.
Cursor's own before-and-after sits beside it: **+12.5%** on their internal benchmark, **+0.3%** in
live production traffic. Both are in the README, at the top, not buried.

One code change follows from reading them. `## Impact` — what is connected to what — has been built
and committed all along, and the injected block never told a session it existed. Eighty bytes now
name it.

### Quieter ones

Five PostToolUse notices had used `print()` since 0.1.0, and PostToolUse is not one of the four
events whose plain stdout reaches the model — every one of them was written to a channel nobody
reads. The token estimator claimed for a year that it errs toward over-counting; measured against
the API on chamnan's own `MAP.md` it came back **under** by 8.2%, and 18.1% on the symbol-dense
section — wrong in the direction that overruns a budget, on the one file it exists to budget. A
`.gitattributes` line was being appended to the repository root on first session, contradicting the
README's promise that `pre-commit` is the only file written outside `.chamnan/`. A tool name that
was a path escaped the workspace and left a registry entry pointing at a file nothing could find.
`chamnan-map /etc` walked `/etc` before dying on it. A symlink loop raised `RuntimeError` past an
`OSError` guard and killed the entire scan. `chamnan-peek` described source code — the most common
file in every repository chamnan targets — as an unrecognised binary blob. Seventy printed
suggestions named commands that do not exist.

**Verified on an 804-file, 28-language corpus rather than on this repository**: 8.1 seconds, 29 MB,
byte-identical across runs, and 2,329 claimed symbols with not one absent from its own source file.
1,334 checks pass.

---

## What's new in 1.12.0

**Eight defects, every one reproduced before it was fixed.** Three research rounds went looking for
evidence about people and found a great deal of it; this release came from pointing the same method
at the code instead — filesystem paths, markdown parsing, git states, concurrent writes, text
decoding — and asking for documented failure modes with a reproduction rather than survey figures.

### A symlink out of the repository was being read and committed

`followlinks=False` stops recursion into symlinked **directories**. It does nothing about a symlink
to a **file**: that is still yielded by the walk, `read_text()` follows it transparently, its leading
comment is copied verbatim into `MAP.md` — and the pre-commit hook then `git add`s `MAP.md`.

Reproduced: a link named `leaked.py` pointing at a file outside the root holding a database DSN was
walked, read, and its docstring copied into the index. **The redactor does not catch this** — it
gates on the link's own name and suffix, so an innocuous `.py` passes, and it strips
`key = "value"` assignments rather than prose. Links that stay inside the repository are still
indexed, because that is an ordinary way to arrange a tree; only escapes are dropped, and a broken
link is dropped rather than raised.

### The hook was being installed where git would never look

`core.hooksPath` relocates hooks entirely, and **pre-commit, Husky and lefthook all set it**. A file
written to `.git/hooks/pre-commit` in such a repository is a dead file: git runs the other directory,
the commit succeeds, and nothing reports that the hook installed a moment ago will never fire. And in
a **worktree**, `.git` is a file rather than a directory, so an `is_dir()` test called a perfectly
good repository *"not a git repository"* and refused to install at all.

`git rev-parse --git-path hooks` resolves both. Verified across four states: plain repository,
`core.hooksPath` set, inside a worktree, and not a repository at all.

### The fence bug came back in the function next door

`state.py`'s `_age_units` called `_HEADING.finditer` directly instead of `md.headings` — the same
fence-blindness fixed in 1.10.0, still live in the sibling function the fix was never ported to. A
`#` comment inside a bash fence became a unit boundary, splitting a pinned section's ageing span so
the half after the fence aged out on its own. **Found in the module whose entire docstring is about
not letting that happen again.**

### `## Pinned 📌 ##` was not pinned

A closing ATX sequence is syntax, not content — CommonMark examples 71 and 73 — and every markdown
viewer renders it away. chamnan captured it as heading text, so `endswith(PIN)` was `False`. The
author sees a pin, the tool does not, and nothing says so.

### The pointer's "once per file per session" rule kept nothing under concurrency

`pointer_seen.json` was a single shared file holding `{"session": id, "paths": [...]}`, read, modified
and written with no lock. Measured on the real function: **four concurrent writers recorded 48 of 160
paths — 70% lost** — and two sessions alternating **wiped each other down to a single entry**, so
`already_pointed` returned `False` for a file that had just been pointed at. Two sessions in one
repository is normal, not exotic.

That is the lost-update anomaly, and an atomic write does not prevent it — only a lock spanning the
read *and* the write does, or not sharing the file at all. Each session now has its own store, named
after it, swept when it is two days stale. No lock has to be reasoned about, which matters given that
`flock` is not reentrant across two descriptors in one process and `fcntl` drops every lock a process
holds the moment **any** descriptor to the file is closed.

### Churn was splitting a renamed file's history in half

`git log --name-only` without `-M` gives a renamed file two literal names: the old one collects the
commits before the move, the new one only those after. Measured on a file with six touches across one
`git mv` — **old: 4, new: 2, and the true six appears nowhere.** The file that actually exists was
ranked on a third of its churn and dropped off roll-up lines it had earned a place on. Now
`--name-status -M`, following a chain of renames to the name that survives.

### Three quieter ones

**A UTF-8 BOM is not whitespace**, so the comment regex missed the first line entirely and the file
got no summary at all — silently lowering the coverage figure the whole index leans on. Now
`utf-8-sig`.

**Clipping by character count is not clipping by what a reader sees.** `"👍🏽 …"[:1]` is a thumbs-up
with the skin tone silently removed; `"🇯🇵"[:1]` is a lone regional indicator most terminals draw as a
boxed letter. The word-boundary back-off cannot help — from Python's side each half is already a
valid string. Trailing combining marks, joiners, variation selectors, skin tones and odd regional
indicators are now trimmed before the ellipsis.

**And a comment that claimed more than it had shown.** The line-count fix said it was "verified
against `wc -l` on 276 files." True, and narrower than it sounds: `splitlines()` breaks on eleven
boundaries and `wc -l` on one. They agreed because none of those files contains a form feed, a lone
carriage return or a Unicode line separator — not because they are equivalent. The comment now says
so.

---

---

## What's new in 1.11.0

**Six defects, three of them in code shipped a day earlier, and all six found by using the thing
rather than reading it.** 1.10.0 introduced a byte ceiling to stop the host truncating the injected
block. It worked, and then three separate bugs inside it quietly threw away most of what it had just
saved.

- **The restore loop returned the cheapest dropped section, not the best.** Sections are dropped
  cheapest-first, so the most valuable one sits at the *end* of that list, and the loop walked it
  forwards. On the development repository the block came out at **4,039 of 9,000 bytes — 45%, with
  the session handoff dropped and 55% of the room unused.** Its test had passed by accident: the
  fixture's index section was unfenced and therefore untrimmable, so the loop fell through to the
  right answer for the wrong reason.
- **The trim then undid what a pin protected.** `state.render` correctly produced both pinned
  headings; `_trim` took the head of that and dropped the tail, and *"do not audit, do not report as
  pending"* happened to sit last. **That is the host's positional cut reproduced inside the module
  written to replace it** — the third appearance of the same shape. Pinned blocks are now reserved
  before anything else is fitted, line by line rather than block by block, because filling by block
  makes a section with no headings one indivisible atom that either fits or vanishes.
- **chamnan's own note about trimming was sitting inside the repository fence**, whose framing line
  says everything between the markers is text read from a file. The fence makes one claim and the
  trim was quietly making it untrue.

**Constraints now come first, and it costs nothing.** Mid-prompt rules are measured losing **30–50%**
of their compliance, while content at the beginning is used correctly in about **73%** of
positionally-sensitive cases. chamnan emitted the architecture index — pure data — in the primacy
slot and the repository's own rules in the middle: the worst available arrangement of those two.
`fit.reorder()` moves rules and reply style to the front, the session handoff to the back, and
everything else stays where it was. Blocks move with their own footnotes. **The block measured 8,912
bytes before and after.** A second argument lands on the same order — with `output_byte_ceiling: 0`
the host's positional cut takes over, so whatever is emitted first is what survives the degraded case.

**Every line count in the index was over by exactly one.** `source.count("\n") + 1` counts the empty
string after a trailing newline: **276 of 277 entries**, verified against `wc -l`. And
`index_is_behind` filtered the tree differently from `mapper`, so a nested checkout — chamnan's own
source, 28 files the index will never contain — reported the host repository's index as stale on
every edit. **On the repository chamnan is developed in, that warning was permanently on, which is
the same as absent on the day it is true.** One filter written twice had drifted; there is now one
definition, `mapper.indexable()`, and 39 phantom missing files became 0.

**The staleness warning also said the wrong thing.** Replaying the last 50 commits against the index
a session was actually handed: it named **74.6%** of the files those commits touched and fully
covered 18% of them, and the misses clustered in a directory of active work. But **0 of 264 paths it
named had disappeared.** A chamnan map is regenerated wholesale rather than patched, so it cannot
drift into being *wrong* — only behind. It is not confidently wrong, it is blind, and blind where the
work is happening. The warning gives a count and names the newest missing files instead of an age.

**A rule the repository can check for itself.** Adherence to a session-start instruction decays with
turn count — models measure **39% worse and 112% less reliable** multi-turn, and o1-preview falls from
**88% to 71%** by the third turn. Injecting a rule harder does not fix that. A rule may now carry:

```
**Check:** present `PATTERN` in `GLOB`
**Check:** absent  `PATTERN` in `GLOB`
```

and the repository is asked directly instead of the model being asked to remember. **Silent while
every rule holds** — a line that always says "all good" stops being read before the day it says
something else — and *unverifiable* is kept distinct from *BROKEN*, because a check that could not run
and a rule that is violated are different facts. The same glob then does double duty: `pointer.py`
uses it to surface a rule when a file it governs is opened, which is the decision point. **There is
no timer, and there will not be one** — periodic re-injection of a whole block is measured *not* to
restore adherence, while a short message at the decision point does.

**The redactor was replacing the label and leaving the token.** `Authorization: Bearer <token>`
matched the bare-assignment rule, which captured the word `Bearer` as the value and replaced *that* —
emitting a line that reads as redacted with the credential intact beneath it. A miss is recoverable;
a reviewer can still see the secret. A miss dressed as a hit is not. Also: a PGP secret key block ends
`PRIVATE KEY BLOCK-----` and the pattern was anchored on `PRIVATE KEY-----`. Against a labelled corpus
of 27 secret shapes and 17 ordinary strings that must survive: **66.7% recall / 81.8% precision →
96.3% / 100%**.

**CJK text is written with CJK punctuation, and it was priced as Latin.** The ideographic comma and
full stop and the fullwidth comma were in none of the estimator's CJK ranges — 18 of 306 characters
in the Chinese calibration sample, each costing 0.42 tokens where it costs about 1. Chinese **−7.7%
→ +0.4%**.

**`MAP.md` now tells git it is generated.** chamnan recommends committing it, and it is 285KB on the
development repository; a large regenerated file is the purest form of the noisy diff that slows
review down. `.gitattributes` gets `linguist-generated=true`, appended once, never rewriting a file
that already exists, skipped outside a git repository. What makes collapsing it honest rather than
negligent is that `chamnan-map` is **byte-identical across consecutive runs**.

### And the evidence trail, in this README — [Evidence](README.md#evidence)

Every number this project quotes, where it came from, and what it changed. Published results are kept
in separate columns from what was measured here. **Findings that argue against chamnan are in the same
tables as the ones for it**: architectural overviews measured *increasing* inference cost without
improving task success; context files buying **no correctness gain** at all; the `[repo:nonce]` fence
being *delimiting*, the weakest of three known variants, worth about a halving of attack success rate
where datamarking reaches under 3%.

It also carries **eight features that were measured and then deliberately not built** — marking
unreferenced files as dead would have been **93.9% false positives** here; `llms.txt` receives **408
of 500M+** AI crawler visits with no significant correlation to citations; JSON-LD in a README is
stripped by GitHub.

**Three of chamnan's own claims were corrected rather than defended.** *"Across a hundred sessions it
is close to free"* is gone — the published mean is **12.6 sessions per repository**, this machine
measures **1.2**, and the index build costs 12 seconds and zero tokens, so there was little to
amortise in the first place. A zero is a bound, not a rate: ten quiet days still permit 0.259 uses a
day. And the fence answers *who said this*; it is not a defence.

---

**Earlier releases:** [CHANGELOG.md](CHANGELOG.md) — every version back to 1.0, or the [releases page](https://github.com/ArcticFox2029/chamnan/releases).

---

## What's new in 1.10.0

**Everything chamnan injected was being cut in half, and nothing said so.** Claude Code truncates a
`SessionStart` hook's stdout above **10,000 bytes**, replacing the block with its first 2,048 bytes
and a path to a file — [#70460](https://github.com/anthropics/claude-code/issues/70460),
[#44086](https://github.com/anthropics/claude-code/issues/44086), from v2.1.88 onward. The cut is
positional. Measured across 120 recorded injections on the development repository, **47 were
truncated and each lost 77–86%**.

Because the architecture index is printed first, what survived was the tail of a directory listing.
What went was everything behind it: the repository's rules, its recorded decisions, its open
threads, the session handoff, and every pinned heading — including the ones that exist to stop a
session redoing settled work. `split_pinned()` had protected all of them correctly. The host
discarded them anyway, and the preview ends mid-sentence and reads like a whole block.

**Token budgets could not have caught this**, because they are not measured in the unit the cut is
made in. `index_token_budget` (3,000) and `state_token_budget` (1,700) come to **11,501 bytes** on
real index text — the two defaults exceed the cap by 15% before a single other section is added.
That has been true of every installation since the budgets were set.

So there is a byte ceiling now, `output_byte_ceiling`, default 9,000, enforced where the block is
printed. Over it, chamnan spends resolution before it spends sections — the roll-up steps down
`8 → 4 → 2 → 0` names per directory — and only then drops whole sections, cheapest first, each named
with the file to read it in. A section too large to fit at all is **trimmed with its fence rebuilt**
rather than dropped, because half a session handoff beats none of one. `--explain` now prints the
byte total, the ceiling, what was left out, and the token-to-byte arithmetic.

**The roll-up stopped choosing its filenames alphabetically.** When the index is folded, each
directory line shows eight names, and those eight were `sorted(names)[:8]` — the alphabet, which
knows nothing about the repository. Measured against 12,332 re-read events across six working
sessions: the alphabetical eight named **22.7%** of them, **git-churn-ranked eight named 35.6%**,
and an oracle picking with hindsight reaches 57.0%. Same budget, one `git log`, a third of the
available headroom. A repo with no git, a shallow clone, or under 50 commits falls back to the
alphabet — commit history degrades localization on sparse histories, and names are always printed
sorted so a re-run never reshuffles the line.

**A fenced code block is not structure.** `split_pinned()` matched `#` headings inside fenced
blocks, so a bash comment in a procedure ended the pinned span — the protected payload fell into the
droppable pool and the fence was torn in half. A `description:` line anywhere in a document was read
as front matter and became its title; one entry was titled *"was written by the vendor and could not
be checked."* Both fixed in a new `lib/md.py` that knows what CommonMark actually considers a fence.

**The redactor was replacing the label and leaving the token.** `Authorization: Bearer <token>`
matched the bare-assignment rule, which captured the word `Bearer` as the value and replaced *that*
— emitting a line that read as redacted with the credential intact beneath it. A miss is
recoverable; a reviewer can still see the secret. A miss dressed as a hit is not. Also: a PGP secret
key ends `PRIVATE KEY BLOCK-----`, and the pattern was anchored on `PRIVATE KEY-----`. Against a
labelled corpus of 27 secret shapes and 17 ordinary strings that must survive, **66.7% recall /
81.8% precision → 96.3% / 100%**. The README now carries that pair, the published head-to-head it
should be read against, and the ceiling chamnan cannot reach.

**CJK text is written with CJK punctuation, and it was priced as Latin.** The ideographic comma and
full stop and the fullwidth comma were in none of the token estimator's CJK ranges, so each cost
0.42 tokens where it costs about 1 — 18 of 306 characters in the Chinese calibration sample.
Chinese **−7.7% → +0.4%**. The whole per-script error table is a test now, run offline against the
measurements already on disk.

---

---

## What's new in 1.9.0

**The knowledge arrives with the file, instead of waiting to be asked for.** Measured on the
repository this plugin is developed against, over ten days: `chamnan-impact` — which answers *what
breaks if I change this*, the question actually asked before an edit — was run **zero times**. So
were `chamnan-age`, `chamnan-candidates`, `chamnan-env`, `chamnan-peek` and `chamnan-promote`.
`chamnan-map` 3, `chamnan-report` 1, `chamnan-timeline` 1. By the person who wrote them, in the
repository they were written for.

**What that zero does and does not establish.** Ten days of no uses does not mean the rate is zero.
The one-sided 95% upper bound after `n` observations with no events is `1 - 0.05^(1/n)`, so ten days
bounds the true rate at **0.259 per day - as much as 7.8 uses a month** still fits the data. A
command consistent with weekly use can easily show ten quiet days. The honest statement is "not once
in ten days, which rules out daily use and rules out nothing below it", and 80% of features in a
615-subscription study are rarely used, so a long tail is the ordinary shape rather than a defect.

The reading taken was therefore not that the knowledge is unwanted, and not that the zero proved
anything on its own. It was that a CLI is the wrong surface for it. The caller is a model, and a
model does not pause before an edit and think *"I should run chamnan-impact first"* - remembering to
ask is the work this plugin exists to remove. That argument stands without the zero; the zero is
consistent with it, not evidence for it.

So opening a file now says what the repository already records about it:

```
[chamnan] what this repository already records about command/start_recheckapp.command:
  procedure skills/main_app_machine_migration.md — machine migration & environment repair
  lesson    memory/lessons/statusline-lives-in-two-places.md — the statusline that runs is ~/.claude/
  used by   status_bar_app.py, start_backup.py
  tested by test_recheckapp_installs_what_runs.py
```

Matching is a filename **with its extension**, or a path, appearing in an entry's body — the cheap
design chosen over a required `files:` front-matter field. The extension is the whole guard: a bare
stem would fire on every sentence containing the word "state". Ranking is how often an entry names
the file, which earned its place on the first live run — the skills index, naming a script once
among fifty files, outranked the procedure literally titled after that script, which named it seven
times.

Four rules, because a hook that fires many times per session is judged by its worst moment: silent
when it has nothing (never "no results found"), once per file per session, never about chamnan's own
files, and bounded in time — measured at 12.7–21.5 ms of work per call. Turn it off with
`"pointer": false`.

**A big file hands over its shape, not just a warning.** The same measurement produced the same
verdict twice: `chamnan-peek` — which reads a 40MB CSV's column list, row count and three sample
rows for about two hundred tokens — was also run zero times. The bulk-read notice already fired
before a large read and said *"this is 1.4M tokens, go and grep"*, which leaves the work exactly
where it was. It now includes the shape:

```
chamnan: `orders.csv` is very large (~1,407,846 tokens), and every later turn in this session
carries it. A grep or a line range costs a fraction of that.

chamnan read its shape instead, so you can decide from this rather than from the size alone:

# orders.csv
4.8MB · .csv
6 columns, 120,000 data rows
columns: `order_id`, `customer`, `sku`, `qty`, `unit_price`, `shipped_at`
first rows:
  0 | cust0 | SKU-0 | 1 | 199.03 | 2026-08-01
_[115 tokens instead of about 2,111,769 for the whole file — 18,297× smaller]_
```

Only for formats peek has a real handler for — CSV, JSON, spreadsheets, archives, SQLite, PDF,
images. A 674KB JavaScript file falls through to the binary fallback, whose honest output is a crc32
and five string fragments, measured at 135 tokens of nothing; there the size warning alone is still
the better answer.

Making this possible meant fixing peek itself. Its cost note read the **whole file** to print one
comparison ratio: measured on a 4.8MB CSV, the actual work took 0.14s and the whole call took 7.5s,
all of it tokenizing five megabytes for a decorative number. It is now measured on a 16KB sample and
labelled "about" — **7.48s → 0.164s, a 46× speedup**, with the estimate 2.4% off on ASCII and 0.06%
off on Thai. The Thai figure is why the sample converts bytes to characters rather than assuming
they are the same: scaling a per-character token rate by a byte count would have reported every Thai
file at three times its real cost.

**STATE.md sections age out.** `STATE.md` was trimmed by a token budget, which is a size rule, not a
relevance one — so *"fixed and committed tonight (do not redo)"* was correct for one night and
charged to every session after it. Measured here: 2,367 tokens, 37.8% of the whole injection, 667
over its own budget.

A section now stops being injected once its text has been unchanged for `state_stale_days` (14 by
default, `0` turns it off). Per section, and the clock resets on any real edit — being worked on is
the evidence, so nothing in flight ages. This is the one place chamnan treats age as evidence, and
it is not a contradiction of [knowledge aging](#knowledge-aging--never-against-a-clock-and-it-refuses-rather-than-reassures):
a decision does not rot with time, but *"work in flight"* is a claim about the present.

Three rules keep it from losing anything: a pinned (📌) heading is exempt at any depth, the file
itself is never modified, and what was held back is named in one line saying how to keep it. On
upgrade, nothing is held back for the first 14 days — every section's clock starts the first time it
is seen.

---

## What's new in 1.8.0

**Repository text is fenced.** chamnan's whole job is to take markdown the repository controls and
put it in front of an agent — so a poisoned file in a repository you cloned is a path to
instructing that agent, and until now content from disk sat inline with chamnan's own words with
nothing to tell them apart.

Every section built from a file is now wrapped in a boundary carrying a nonce generated fresh each
session, with one line at the top saying what the boundary means. A fixed marker would simply be
written into a file to close the block early and let what follows read as chamnan speaking; a
per-session nonce cannot be written in advance, and a literal closing mark inside a body is escaped
before the body is wrapped.

It costs 178 tokens on this repository — 3.2% of the injection — and `chamnan-map --explain` prints
that figure rather than leaving you to wonder. It is a mitigation, not a proof: it gives a reliable
answer to *who said this*, which was unanswerable before. It does not make hostile text safe to act
on, and nothing is censored — an attempt is delivered inside the fence where it can be seen.

**How much a fence is worth, measured by people who measured it.** In the spotlighting taxonomy
([arXiv:2403.14720](https://arxiv.org/abs/2403.14720)) this is *delimiting*, the weakest of three
variants, and the paper puts its effect at roughly a **halving** of attack success rate. The two
stronger variants reach far further — *datamarking* takes ASR from ~50% to **under 3%**, *encoding*
to **≈0%** — and neither is available here: both work by making the untrusted text unreadable as
prose, and this untrusted text is a code map whose entire purpose is to be read. And all three are
beaten by an attacker who adapts: against static attacks spotlighting held ASR near 1%, while
adaptive search-based attacks reached **>95%**
([arXiv:2510.09023](https://arxiv.org/abs/2510.09023)).

So the honest claim is narrow, and it is the one made above: the fence answers *who said this*. It
is not a defence against a determined attacker, it was never going to be, and a plugin that told
you otherwise would be selling you something. What it buys is that a poisoned comment arrives
labelled as a poisoned comment.

---

## What's new in 1.7.3

**A restated filename took its separator with it.** A header that opens `# cve.sh — checks the CVE
list` has the filename dropped, because the index row already shows it — but the dash that joined it
to the sentence was left behind, so the row rendered as `path (137L, 2fn) — — checks the CVE list`:
two dashes with nothing between them. Found by rebuilding a real repository's map and reading the
diff rather than by a test, which is why there is now a test.

---

## What's new in 1.7.2

**An update is offered, never taken.** When a newer version is already sitting in the marketplace
Claude Code installed from, the session says so and stops there — nothing is changed until you say
yes. A tool that upgrades itself because you opened a session is doing something you did not ask
for, and doing it quietly is worse than not doing it at all. Once one repository is on the new
version, every other repository brings its own workspace up to date by itself the next time it is
opened.

No network is involved, and there will not be one: repository-local with no calls out is what this
is. The marketplace copy is already on disk, so "is there a newer one" is a local question.
`claude plugin marketplace update` is what refreshes that copy.

**An older build running against a newer workspace is caught.** A plugin's `bin/` goes on `PATH`
pinned at session start, so upgrading mid-session leaves the old executables live — and one machine
can carry several installs, one per config directory. The workspace records the newest version that
has set it up, and says so if something older turns up later. An upgrade is silent; only going
backwards is worth interrupting for.

**A stale index is reported.** If source has changed since `MAP.md` was built, the session says how
far behind it is and names the command that fixes it. Reported rather than rebuilt: rebuilding
unasked at session start spends real time on work nobody requested, and the gap is stated honestly
in minutes or hours rather than rounded up to a day.

---

## What's new in 1.7.1

**An upgrade now reaches the repository, not only the plugin.** 1.7.0 created the workspace when
`.chamnan/` was absent, which left every workspace made by an older version exactly as it was. Two
repositories that had been using chamnan for weeks still had no `memory/`, `sessions/` or
`threads/` directory at all, and a `config.json` holding 10 of the 19 keys — so memory, session
records, threads, timeline, environments, milestones and the ledger had never once worked there,
silently, because the directories those features write into did not exist.

The scaffold is now reconciled on every session: missing directories are created, and the config
gains keys added since it was written while keeping the values you chose. Nothing is overwritten,
and the "workspace created" line still appears only the first time.

---

## What's new in 1.7.0

Three changes, all of them about the system being ready and honest rather than about new places to
store things.

**A new repository is set up on its first session.** The workspace used to be created only as a
side effect of running `chamnan-map`, `chamnan-promote` or `chamnan-candidates` — so someone who
installed the plugin and opened a project got no directories, no `config.json`, and no indication
the plugin existed. Every write skill had nowhere to write. The scaffold is now laid down up front,
in a version-controlled repository only, and the session that creates it says what was created.

**`chamnan-map --explain` prices the injection.** Every section, what it cost, and the file or
store it came from — so "why is this in my context?" has a number rather than an argument. The
accounting is a side effect of building the text, so there is no second model of the context to
drift out of step with the real one.

**One tree walk instead of nine.** Building the map ran nine separate full-tree traversals, each
filtering its skip list only *after* descending, so every one paid the full cost of `.venv`,
`node_modules` and `.git` before discarding the results. On a 224-file repository that took
`chamnan-map` from ~92 seconds to ~10.6, with `MAP.md` byte-for-byte identical.

---

## What's new in 1.6.0

1.5.x made knowledge capture visible and reviewable. 1.6.0 is about context in **time** and
**place**: what has already happened to this file, and what the environment it runs in will not let
you do.

### Threads — one line of work across the sessions it took

    $ chamnan-timeline for src/auth.py
    2 entries naming src/auth.py

      2026-08-14 — second attempt held
               on Auth migration
      2026-08-01 — rolled back — sessions did not survive a node restart
               on Auth migration

"We have tried to fix this three times" is knowledge nobody can reconstruct from a git log: the
three attempts are three unrelated commits weeks apart, and the thing tying them together was only
ever in somebody's head.

**Threading is a pick from a declared list, never a string match** — the one design decision this
feature rests on. Guessing which thread an entry belongs to by matching its words fails on the
first synonym: one session writes "auth", the next writes "login", the third writes "the SSO work",
and a matcher scatters one thread across three. So `chamnan-timeline new` is the only thing that
creates a thread, and `add` refuses a name that was never declared, printing the declared list
instead of quietly starting a fourth.

### `chamnan-impact` — and the join that makes it worth asking

The dependency analysis already existed and already fed `MAP.md`; it simply had no way to be
*asked*. Now it does, and the answer carries the thread history for the same file:

    $ chamnan-impact src/auth.py

      used by   src/api.py
      tested by nothing the index can see — a change here is unguarded
      (from `.chamnan/MAP.md`, built today)

      2 thread entries name this file:
        2026-08-01 — rolled back — sessions did not survive a node restart

An import graph can say what breaks. It cannot say "last time this changed, it needed a rollback",
and that is the half that changes what somebody does next.

It reads `MAP.md` rather than rescanning — a full scan of the repository this plugin is developed
against measured **64 seconds**, which is not a thing to do on an interactive question. The cost is
that the answer is only as fresh as the last `chamnan-map`, so the index's age is printed with
every answer instead of left to be assumed.

### `environments.md` — the constraints nobody writes down

    ## production
    **Platform:** Kubernetes 1.28 on RKE2
    **Versions:** postgres 16, redis 7.2
    **Constraints:**
    - RWO storage only — no ReadWriteMany PVCs
    - no outbound internet from worker nodes
    **Checked:** 2026-08-27

"RWO storage only", "no TPM in UAT", "DR runs different hardware" — each one is discovered the same
way: somebody writes the obvious solution, it fails in one environment and not another, and an
afternoon goes into finding out why. The fact is one line long, and it is in neither the code (the
code is what got written *because* of it) nor the git history (the commit explains the workaround,
not the constraint).

The constraints are injected at session start, and named again the moment a session is
demonstrably working against that environment. **Nothing here contacts an environment** — every
line was typed by somebody who knew it, which is exactly why `Checked:` matters.

### Knowledge aging — never against a clock, and it refuses rather than reassures

A note written two years ago about a version still in production is current. One written last month
about a version replaced last week is already wrong. **Age carries no information about either**,
so `chamnan-age` compares what an entry *claims* against what `environments.md` *declares*.

That makes the check exactly as trustworthy as that file — which is the risk it is built around:

    $ chamnan-age
    chamnan: not checked — every declared environment has gone cold (uat, production) —
    nothing here is checked, because an unconfirmed entry is evidence nobody looked, not
    evidence nothing changed.

An environment nobody has confirmed in six months is not an authority. Reporting "your knowledge is
current" on the strength of it is a **false all-clear**, which is worse than no check at all,
because it is the answer that stops somebody looking. So when every environment has gone cold this
reports nothing and says why. There is a third outcome too — a claim matched only by a cold
environment is reported as *unverifiable*, not as a finding, because nobody knows.

Equality only, never ordering: `3.9` versus `3.11` is exactly the comparison a version comparator
gets wrong, and it is the one Python repositories hit most.

---

## What's new in 1.5.2

1.5.1 closed the loop from evidence to a kept tool. 1.5.2 asks what happens after — does a promoted
tool actually keep working, and is any of this actually being used.

### Tool health, without an exit code

A Bash `tool_response` carries `stdout`, `stderr` and `interrupted` — never a numeric status, so a
promoted tool exiting non-zero cannot be observed directly. What CAN be observed: whether the call
was interrupted, and whether it wrote to stderr. Neither means "it failed" on its own — plenty of
correct commands write warnings to stderr — so neither is ever reported as one. Three occurrences of
either flags the tool once, quietly:

    chamnan: `.chamnan/tools/deploy-check.sh` has been interrupted or written to stderr 3 times in
    its last 11 run(s) — worth a look. `chamnan candidates demote deploy-check.sh` sends it back for
    review if it no longer does what you expect.

Silent before the third occurrence, silent after — the same restraint every other notice in this
plugin already uses. `chamnan-candidates demote <tool-name>` undoes a promotion: removes it from
`tools/index.json`, deletes the file, and writes a fresh candidate from its own description, so the
routine goes back through review instead of just disappearing.

**Skills are out of scope, on purpose.** A tool is a script a hook can watch run; a skill is a
markdown file Claude reads on its own judgement, and nothing here can see that the read happened at
all, let alone whether following it went well. There is no smaller version of skill feedback that
stays honest about what a hook can actually see — so none is attempted.

### Usage counts, never a savings figure

`chamnan-report` now opens with a Usage section, right after the knowledge inventory:

    Usage
      chamnan-candidates     3 times
      chamnan-map            14 times
      chamnan-peek            0 times
      chamnan-promote         2 times
      chamnan-report           6 times
      (from the calls currently logged, 2026-08-01 to 2026-08-27 — commands.jsonl holds the
      most recent 400, not a calendar window)

    Promoted tools
      deploy-check.sh        12 runs

Both halves were already being written before this had a reader: the command counts come from
`commands.jsonl`, the same bounded log the workflow detector keeps; the tool counts come from the
`runs` field `chamnan-candidates demote`'s neighbour above has been incrementing since 1.5.2's tool
health tracking shipped. This reports **counts, never a savings figure** — a number of tokens or
hours saved would be invented, and this project already retired an "Engineer Scoreboard" for
measuring what is easy instead of what matters.

---

## What's new in 1.5.1

1.5 made a detected sequence survive as a **candidate** instead of a notice that scrolls away.
1.5.1 is what to do with one — a review CLI, and a promotion path honest about what it cannot know.

### `chamnan-candidates` — the review CLI

    $ chamnan-candidates
    2 candidate(s) waiting

    [1] docker compose · alembic · pytest
        observed 4 time(s) · last seen 2026-08-26 · ai-inferred
    [2] git add · git commit · git push
        observed 3 time(s) · last seen 2026-08-27 · ai-inferred

`confirm <id>`, `reject <id>`, `edit <id>` — `<id>` is either the number shown above (computed
fresh each call, never cached) or the candidate's own slug. `confirm` only moves `Provenance` from
`ai-inferred` to `ai-confirmed`; it never writes into `skills/` or `tools/` on its own.

### `chamnan-candidates promote` — and the honest ceiling on it

Refuses a candidate that has not been confirmed — the pipeline is *evidence → candidate → human
confirm → memory*, and this enforces the order rather than assuming it.

With no destination, it only suggests, and writes nothing:

    Suggested: tool — this is a sequence of shell commands, which is what a tool is.
    Choose skill instead if the real value is explaining WHY, or a judgement call at
    one of the steps — chamnan cannot tell that from the sequence alone; you can.

That is the whole classifier, stated as a default with its reasoning printed next to it, not a
computed score. A candidate stores what ran — `git commit`, never the literal command with its
real arguments, and never why the routine mattered. There is no signal in that to choose
confidently from, and a project that has already retired a Health Score and a Confidence Score for
being judgements no evidence backs was not going to invent a third one here.

**`promote <id> tool <name>`** writes an executable *skeleton* — one labelled placeholder per step
— and it fails loudly if you run it before filling those in, rather than silently doing nothing
while looking like it worked:

    echo "TODO step 1: docker compose" >&2; exit 1  # replace this line

Registered through the same `tools/index.json` machinery `chamnan-promote` already uses — the two
now share one implementation (`lib/tools_index.py`) rather than two that could drift apart. Once
installed, the candidate is removed; its finding now lives in the tool file, not duplicated in both.

**`promote <id> skill`** writes nothing at all. A skill's value is the prose explaining *why*,
which cannot be honestly generated from a signature list — this prints the sequence as a starting
point and names `/chamnan:capture`, and leaves the candidate exactly where it was, because nothing
has actually been captured yet.

---

## What's new in 1.5

Measured on a real workspace: `.chamnan/sessions/` and every `.chamnan/memory/` category held
**zero entries** after five weeks of daily use, while the hook-written activity logs held **700**
records. The stores 1.3 added were built correctly; nothing was making writing to them happen. 1.5
is entirely about that gap — no new store, one new record type, and four small mechanisms that
turn absence into something visible instead of something silent.

### Two lines that name what already exists

Every session now opens with two short lines, **~112 tokens together on an empty workspace, ~128
once something has actually been written** — this plugin's entire always-on price for the release:

    _Write with `/chamnan:resume` (session record), `/chamnan:remember` (decision, lesson, or
    rule), `/chamnan:milestone`, or `/chamnan:capture` (a procedure worth keeping). Nothing writes
    here unless you ask._
    _chamnan · 0 records · 0 memory entries · nothing written yet_

The first line exists because `chamnan_session_start.py` had never once named the plugin's own write
skills — it injected the *workspace's* recorded procedures and stopped there, so an agent had no
way to discover `/chamnan:remember` short of reading the plugin's source. The second is the
ledger: a count for every store, always printed, always showing **movement** rather than a static
number — `3 records (+2 this week) · last write 2 days ago`, once there is something to compare
against. A number that never changes is what gets tuned out; the word "zero" printed plainly is not.

### `STATE.md` stops losing what you pinned

The injection cap changed from a flat 4,000 characters with no notice when something was cut, to a
**token budget** (`state_token_budget`, default `1700`) with a visible marker — `_…9.1k more —
read .chamnan/STATE.md_` — so a truncated file says so instead of quietly dropping 69% of itself.

A heading can also be **pinned**, by ending it with 📌. A pinned section is injected in full,
first, regardless of where in the file it falls — so a standing instruction like `### SETTLED — do
not raise these again 📌` cannot lose a race for the top of the file as the file grows.

### The repeated-workflow detector actually detects something

1.3's sequence detector (`git diff → git status → git commit`, recurring across separate days) had
a bug that made it find nothing on a real, active workspace: shell keywords — `do`, `for`, `done`,
`then`, `break` — were being recorded as if they were program names, because a chained command
splits on `;` and the detector only ever looked at a fragment's first word. On one measured log,
**26% of it was shell syntax**, not workflow steps. Keywords are now excluded as their own
category, distinct from ordinary commands too common to mean anything.

### A finding that survives past the moment it was noticed

When a sequence crosses the threshold, it no longer just prints once and disappears — it is kept
as a **candidate**, one file under `.chamnan/candidates/`, keyed on the sequence itself so the same
routine detected again updates the one file instead of creating another:

    # docker compose · alembic · pytest
    **Sequence:** docker compose, alembic, pytest
    **Observed:** 3
    **Last seen:** 2026-08-27
    **Provenance:** ai-inferred

A candidate is evidence, never itself knowledge — nothing injects one into a session; only its
**count** reaches the ledger (`4 awaiting review`), and only `/chamnan:capture`, run by you,
promotes one into something a session actually reads. A companion **resume nudge** fires at most
once per Claude Code session — tracked by `session_id`, not by calendar day, so two sessions on
the same day each get their own chance — when real work has happened and nothing is recorded for
today yet.

### Knowledge inventory, and two questions nobody was asking

`chamnan-report` now opens with what actually exists, store by store, zeros printed plainly:

    Knowledge inventory
      sessions/             0 entries    last write never
      memory/decisions/     0 entries    last write never
      ...
      1 of 5 decisions have no `Rejected:` — a trade-off nobody wrote down

Decisions gain a named `**Rejected:**` field — a heading you fill in rather than a sentence that
was easy to skip while writing quickly — and every memory entry is automatically stamped with
`**As-of:**` (today's date) and `**Provenance:**` (`ai-drafted` by default) the moment it is
written, by a hook rather than by asking the `remember` skill to remember to include them. An
existing `Provenance` is never overwritten, so a value you set by hand stays exactly what you set.

### Three defects closed along the way

- An en-dash (`–`, which editors autocorrect `--` into) in a milestone heading was silently
  absorbed into the *previous* entry's body rather than becoming its own entry — the character
  class only recognised em-dash and hyphen. Fixed, and covered for all three.
- A decision or lesson title had no length limit on its way into the session-start listing —
  capped at 120 characters, with a visible `…` rather than a silent cut.
- A skill's registry line fell back to `no description — add one` whenever the file had no YAML
  frontmatter, which was true of every skill on the workspace this was measured against. It now
  falls back to the first real line of body text instead of staying empty.

**The honest ceiling, unchanged by any of this:** writing still depends on choosing to write.
Nothing here can see a session's conversation and decide something is worth keeping. What changed
is that not writing anything is now a fact printed in front of you every session, instead of a
silent absence nobody had reason to notice.

---

## What's new in 1.3

Six additions, all repository-local markdown, all bounded at the injection rather than in the
store. Measured with every one of them populated: **507 tokens** reach a session.

### Better Resume Work

One record per session under `.chamnan/sessions/`, written by `/chamnan:resume`. Only
**`Remaining` and `Blockers`** reach the next session — `Done` is history and the file list is
recoverable from git. A session that finished cleanly injects nothing at all, because an empty
record is worse than none.

It does not replace `STATE.md`. `STATE.md` is one overwritten file about the present; a session
record is one of many about a particular stretch of work.

### Smart Session Memory

`.chamnan/memory/` with three categories, used three different ways:

| | | reaches a session as |
|---|---|---|
| `rules/` | a standing constraint | **the full text**, capped |
| `decisions/` | a choice, and why | its title |
| `lessons/` | something that cost time once | its title |

Titles cost a line each and buy the ability to load the right file; injecting the bodies would cost
everything and buy nothing extra. **Not pruned by age** — a session record stops mattering, a
decision does not, and a timer would delete the oldest entries, which are the ones nobody can
reconstruct.

### Impact Map

Who depends on a file, and which tests cover it — in `MAP.md`, **below the Full Detail marker**, so
it is grepped when you are about to change one path and never injected into sessions that will not
touch it.

    - **`payment/service.py`** — used by `checkout/api.py`; **tested by** `tests/test_payment.py`

One hop, capped. No transitive closure, no cycle analysis, no database. Imports are collected while
the scanner already has each file open, so it adds no second read: measured at **0.673 s across 529
files**, 9.5% of scan time.

### Better Capture

The existing hint noticed the same *script* written a third time. This notices the same **commands,
in the same order, on a third separate day** — the deployment check or debugging routine that
leaves no file behind at all.

Four guards keep it quiet: arguments and paths are discarded so the same routine matches across
branches; 33 commands too common to mean anything are ignored; three distinct steps minimum; three
distinct days, so repeating something three times in one sitting counts once. It speaks once, and
never in the same turn as the script hint.

### Project Milestones

`.chamnan/milestones.md` — the handful of changes that reshaped the repository, with **why** it was
worth doing and **which areas moved together**. A git log rarely says the first and never says the
second.

Not project management: no status, no owner, no due date. Only the two most recent titles are
injected, so forty milestones cost the same per session as two.

### Better Language Support

Prioritised by measuring symbols per thousand lines across a 529-file polyglot corpus, then
inspecting each low number before touching anything:

| | before | after | |
|---|---|---|---|
| PHP | 82 symbols | **163** | the rule matched only a bare `function`, so 66 of 139 declarations were invisible |
| Rust | 66 | **150** | only an optional `pub` was allowed, missing every `async fn` |
| TypeScript / JS | 173 | **191** | class methods are indented; every rule was anchored at `^` |
| shell | 14 | **14** | **left alone** — its scripts are commands, not functions, so the low number is honest |

`MIN_YIELD` now asserts a minimum symbol count for twelve languages against ordinary-code fixtures,
so *a language partially understood beats one falsely claiming full support* is a test rather than
a slogan.
