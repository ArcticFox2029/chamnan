# Changelog

Release notes for every version. The newest release is also at the top of the
[README](README.md#whats-new-in-1221), and every one of these is on the
[releases page](https://github.com/ArcticFox2029/chamnan/releases).

Kept here rather than in the README because thirteen of them had grown to a third of that file, and
a version history is the one thing a first-time reader never needs.

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

### And the evidence trail, in this README — [Evidence](#evidence)

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
