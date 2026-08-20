# Chamnan 1.2.0 Community & Trust Release

Last updated: 2026-08-20

## Status

Current task: TASK-08
Last completed task: TASK-07
Overall status: IN_PROGRESS

Baseline confirmed at the start of this work:
- Released version: **1.1.0** (`.claude-plugin/plugin.json`)
- Published tag: **`chamnan--v1.1.0`** — the only tag in the repository
- Branch: **main**, working tree clean, HEAD `f0723d6 release: bump version to 1.1.0`
- GitHub Release for 1.1.0 is published and marked latest

**Commit policy for this release: one commit at the end, not one per task.** Tasks stage their
files and stop. TASK-08 reviews the whole staged set, then a single
`docs: prepare Chamnan 1.2.0 community release` commit, push, tag `chamnan--v1.2.0`, release.

## Checklist

- [x] TASK-01 Release planning check
- [x] TASK-02 Add CONTRIBUTING.md
- [x] TASK-03 Add Architecture Diagram
- [x] TASK-04 Add Data Flow Diagram
- [x] TASK-05 Improve Release Notes template
- [x] TASK-06 Add Verification artifact
- [x] TASK-07 README consistency review
- [ ] TASK-08 Final staging review

## TASK-01

Status: COMPLETE. Inspection only — no files were created, as instructed.

### Current documentation state

**All prose documentation lives in a single file.** `README.md` is 731 lines across 23 top-level
sections, and it is the only document in the repository. There is no `docs/` directory and no
second page of any kind.

The other `.md` files are **plugin content, not documentation**, and should not be treated as docs
when deciding where new pages go:

- `skills/{bootstrap,capture,promote,remap,report}/SKILL.md` — frontmatter-driven instructions
  Claude Code loads as slash commands
- `agents/{commenter,librarian}.md` — agent definitions with `tools:` and `model:` frontmatter

### Existing files

| | |
|---|---|
| `CONTRIBUTING.md` | **absent** |
| `CODE_OF_CONDUCT.md` | **absent** |
| `SECURITY.md` | **absent** |
| `SUPPORT.md` / `GOVERNANCE.md` / `CHANGELOG.md` | **absent** |
| `.github/` | **absent** — no issue templates, no PR template, no workflows |
| `docs/` | **absent** |
| `LICENSE` | present — **MIT** |
| Diagrams of any kind | **none anywhere** — no Mermaid, no SVG, no PNG |

Tracked top-level layout: `lib/` (10) · `bench/` (6) · `skills/` (5) · `hooks/` (5) · `bin/` (4) ·
`agents/` (2) · `.claude-plugin/` (2) · `tests/` (1) · `README.md` · `LICENSE` · `.gitignore`.

### Recommended locations

| Artifact | Recommended path | Why |
|---|---|---|
| Contributor guide | `CONTRIBUTING.md` (repo root) | GitHub links it automatically from the PR and issue UI only when it is at the root, in `.github/`, or in `docs/`. Root is the most discoverable of the three and matches the existing flat layout. |
| Architecture diagram | `docs/architecture.md` | Creates `docs/` as the home for prose that is not the README. Keeps a 731-line README from growing further, which would work against the plugin's own argument about context cost. |
| Data-flow / security diagram | `docs/data-flow.md` | Same directory, separate page — TASK-04's subject is security posture, which readers look for on its own rather than inside an architecture page. |
| Release notes template | `.github/release-template.md` | Exactly the path TASK-05 specifies. Creating `.github/` for this one file is fine; it is the conventional home and costs nothing. **Note:** GitHub does not auto-apply a release template — it is a copy-from reference, so the file should say so. |
| Verification artifact | `docs/verification.md` | Groups with the other `docs/` pages. TASK-06's path suggestion and this recommendation agree. |

### Findings that affect later tasks

- **No diagram convention exists**, so TASK-03 and TASK-04 are free to use Mermaid. GitHub renders
  it natively in Markdown, needs no build step and no committed image, and stays diffable — the
  right default here.
- **`.github/` does not exist yet.** TASK-05 creates it. Per its own brief, no workflows.
- **The test surface is one file**: `python3 tests/run_tests.py`, 220 checks, stdlib only, no
  pytest. TASK-02 and TASK-06 should both describe exactly that and nothing more.
- **`bench/` is tracked** (6 files: `run_bench.py`, `calibrate_tokens.py`, `questions.json`,
  `calibration.json`, `smoke_smallchat.json`, `_no_plugin_settings.json`). Its outputs
  (`bench.log`, `results.json`) are excluded locally. TASK-06 may reference the harness, but must
  not imply a reader can reproduce the chaos-test corpus — that corpus is not in this repository.
- **Licence is MIT**, which TASK-02 should state in the contribution terms.
- **`README_AUDIT.md` was in `.git/info/exclude`** from the 1.1.0 audit, when it was meant to stay
  local. This release intends to commit it, so the exclude entry was removed rather than working
  around it with `git add -f`. `note-readme.md`, `bench/bench.log` and `bench/results.json` remain
  excluded.

### Next task

**TASK-02 — Add CONTRIBUTING.md**

Files it should create: `CONTRIBUTING.md` at the repository root.
Facts it will need, already gathered here: MIT licence · `python3 tests/run_tests.py` (220 checks,
stdlib only) · language support lives in `lib/mapper.py` (`EXT_LANG` maps extension to language,
`REGEX_RULES` holds per-language extraction, Python uses `ast` instead) · every fix in this project
has historically shipped with a regression check in `tests/run_tests.py`.

## TASK-02

Status: COMPLETE. Created `CONTRIBUTING.md` at the repository root — 144 lines, 9 sections.

Covers the eight required topics: project overview, development setup, repository structure,
running tests, adding language support, documentation requirements, pull requests, bug reports,
plus the MIT licensing line.

Deliberately **not** claimed, because none of it exists:
- no CI, no PR template, no issue templates, no review rota — the PR section says so outright
  rather than describing a process a contributor would then look for and not find
- no build step, no virtualenv, no dependency install; setup is `git clone` then run the tests

Content grounded in the code rather than invented:
- language support documented as it actually works — `EXT_LANG` maps extension to language key,
  `REGEX_RULES` holds `(kind, pattern)` tuples per key, and `_extract_one` dispatches `"py"` to
  `extract_python` (which uses `ast`) and everything else to `extract_regex`
- the two failure modes a new pattern hits are written up from real ones: borrowing another
  language's rules (Kotlin on Java's rules gave 34 symbols where 254 were correct), and control
  flow matching a call shape (`NOT_A_FUNCTION`)
- `leading_comment` and `HASH_IS_DIRECTIVE` named for summary extraction
- `DEFAULT_CONFIG` named as the single source of truth for options
- the "assert both directions" rule for redaction tests, which the suite already follows

Validation: markdown well-formed (fences balanced, no heading-level jumps, table rows terminated);
every symbol it names verified present in `lib/mapper.py` or `lib/workspace.py`; every path it
cites verified to exist.

## TASK-03

Status: COMPLETE. Created `docs/architecture.md` — 107 lines. This also creates `docs/`, which
TASK-01 recommended as the home for prose that is not the README.

Format: **Mermaid**, in a fenced ```mermaid block. TASK-01 established there was no existing
diagram convention anywhere in the repository, so this sets one. GitHub renders it natively — no
build step, no committed image, and it stays diffable.

The diagram shows the required path — repository → scanner → `MAP.md` / `STATE.md` / procedures /
tools → Claude Code session — and distinguishes two kinds of arrow: solid for what chamnan does on
its own, dotted for what happens because the user or Claude asked. That distinction matters
because `STATE.md`, `skills/` and `tools/` are **not** written by the scanner, and a diagram that
implied otherwise would misdescribe the tool.

Three prose sections follow the diagram, as required: what runs locally, what is generated, what
Claude consumes. A fourth, "What chamnan does not do", states the boundaries.

Claims deliberately excluded, per the brief: no cloud processing, no vector database, no embedding
model, no index server, no external service. The words appear only in negative statements, which
the validation checked for specifically.

Accuracy points worth keeping:
- `session_start.py` injects the Quick Index, `STATE.md`, and the **names and descriptions only**
  of `skills/` and `tools/` — not their contents
- the Full Detail half of `MAP.md` is never injected
- `chamnan-peek` is on-demand and outside the session-start path
- the only write outside `.chamnan/` is the opt-in git hook

Validation: fences balanced; mermaid has a diagram type; 10 nodes declared and every edge
references a declared node; `subgraph`/`end` balanced; no unqualified forbidden claims.

**One deliberate forward reference:** `docs/architecture.md` links to `docs/data-flow.md`, which
TASK-04 creates. Harmless under this release's one-commit policy — the link is never broken in any
committed state — but it makes TASK-04 obligatory. **If TASK-04 changes that filename, this link
must change with it.**

## TASK-04

Status: COMPLETE. Created `docs/data-flow.md` — 103 lines, Mermaid.

The diagram shows the required path — source repository → local processing → `MAP.md` / metadata /
local state — with `lib/redact.py` drawn as the single choke point every output passes through, and
two **crossed** edges (`.-x`) to a Network node. Those two are the point of the picture: there is no
path from the scanner or from `.chamnan/` to anywhere off-disk.

Four sections follow, as the brief required: processing happens locally · what is generated · what
is not sent externally · chamnan is not a sandbox.

The most important thing this file gets right: **"nothing is sent externally" is scoped to
chamnan, not to Claude Code.** They are different programs. chamnan writes files to disk; what
Claude Code does with a repository when it reads a file is unchanged by whether this plugin is
installed. The page says so explicitly, because the obvious misreading — "installing chamnan stops
my code being sent anywhere" — would be a false security claim.

The related honest point is also made: an indexed session tends to read fewer whole files because
it knows where things are, but that is a consequence of better navigation, **not a control**, and
not a guarantee about any particular session.

No new security claims. The sandbox paragraph is quoted **verbatim** from the README rather than
paraphrased, and the two "further limits" are the README's own.

Validation: fences balanced; 8 mermaid nodes declared with every edge referencing a declared node;
`subgraph`/`end` balanced; scanned for wording stronger than the README (`100% secure`,
`cannot leak`, `fully prevents`, `guarantees`, `sandboxed`, …) — none present; the quoted sentence
confirmed present in README.md, so it cannot have drifted; the blocked-suffix list cross-checked
against `lib/redact.py`; all relative links resolve.

The forward reference recorded in TASK-03 is now discharged — `docs/architecture.md` →
`docs/data-flow.md` resolves.

## TASK-05

Status: COMPLETE. Created `.github/release-template.md` — 95 lines. This creates `.github/`, which
did not exist. **No workflows were created**, per the brief; the directory holds this one file.

All five required sections present: Install · What's new · Breaking changes · Security notes ·
Verification.

Two things this template does that a generic one would not:

- **It says GitHub does not apply it automatically.** There is no release-template mechanism in
  GitHub the way there is for issues and pull requests. Leaving that unsaid would have someone
  wondering why their release form came up empty. The header says to copy it, or pass it with
  `gh release create --notes-file`.
- **"What's new" is split into Functional changes and Documentation, with an instruction not to
  merge them.** That split is the lesson from the 1.1.0 notes, where documentation work sat beside
  real behavioural change and had to be separated by hand.

It also tells the author to delete empty sections rather than leave a heading with nothing under
it, and to keep security wording no stronger than the README's, pointing at `docs/data-flow.md`.

Validation: all five headings present; fences balanced; the three install/update commands checked
to appear verbatim in README.md; scanned for concrete values — **no version number, no commit sha
and no test count** anywhere, only the placeholders `{VERSION}`, `{FULL_SHA}`, `{N}`, `{CHANGE}`,
`{PLACEHOLDER}`; confirmed no `workflows/` directory exists.

**One deliberate forward reference:** the template links to `docs/verification.md`, which TASK-06
creates. Same reasoning as TASK-03's — harmless under the one-commit policy, but it makes TASK-06
obligatory at that exact path. **If TASK-06 chooses a different filename, this link must change
with it.**

## TASK-06

Status: COMPLETE. Created `docs/verification.md` — 147 lines, 4 sections.

Contains the three required things: the test command, the expected result format, and a release
verification checklist.

Grounded in observed output, not described from memory:
- success is `220/220 checks passed`, exit `0`
- failure prints `  FAIL  <name>` per failed check, then the total, and exits `1`
- both forms were captured by running the suite, and the doc notes that the count changes as
  checks are added — what matters is that the two numbers match

The checklist is eight steps, each a command whose output can be read rather than a judgement
call. Two steps earn their place beyond the obvious:
- **`claude plugin tag --dry-run` is a real gate, not a formality.** It was observed refusing to
  proceed on a dirty working tree, and it validates that `plugin.json` agrees with the marketplace
  entry — so a version bumped in one file and not the other is caught before publishing.
- **`gh release create --verify-tag`** fails rather than inventing a tag when the name is wrong,
  which is the behaviour you want given the tag name is the thing most likely to be mistyped. The
  `v1.1.0` → `chamnan--v1.1.0` correction during the last release is why this is called out.

A closing section states what the suite does **not** verify: it does not check that the README's
measured figures are still true, because those came from a synthetic corpus that is not in this
repository. `bench/` is tracked so the method is inspectable, not because the results regenerate
from a clone.

Validation: fences balanced; scanned for machine-specific paths (`/Users/...`, `/home/...`,
`Lumin-App`) and for anything token-shaped — **none present**; all required content confirmed
present; the quoted expected output matches a live run.

The forward reference from TASK-05 is now discharged — `.github/release-template.md` →
`docs/verification.md` resolves.

## TASK-07

Status: COMPLETE. `README.md` changed by **10 added lines and nothing removed**.

Reviewed for what this release actually introduced, and the honest finding first: **no statement in
the README was made false by the new files.** The README never claimed to be the only
documentation, so nothing needed correcting. The two existing hits for "architecture" refer to
"the architecture index" (`MAP.md`) and are unrelated to `docs/architecture.md`.

What there **was**, was a real gap: the release adds `CONTRIBUTING.md` and three pages under
`docs/`, and the README pointed at none of them. For a release whose stated purpose is community
and trust, shipping documentation that cannot be reached from the front door is a defect in the
release rather than a missing nicety.

Fix: a four-row `## More documentation` table inserted immediately before `## License`. That is the
whole change — no existing prose was touched, nothing was reordered, and no section was rewritten.

Validation: every relative link in the README resolves on disk; every internal anchor still
resolves; README is now 741 lines and 24 top-level sections; `git diff --stat` confirms
`10 insertions(+)` and zero deletions.

## Next task

**TASK-08 — Final staging review.**

Expected staged set at that point (7 files, all additions except README.md):
`CONTRIBUTING.md` · `README.md` · `README_AUDIT.md` · `.github/release-template.md` ·
`docs/architecture.md` · `docs/data-flow.md` · `docs/verification.md`

TASK-08 must confirm nothing else crept in, run `python3 tests/run_tests.py` expecting
`220/220 checks passed`, and recommend a commit message. It must **not** commit or push — the
single commit for this release is taken after that review, per the policy at the top of this file.

Note for whoever runs it: no source file has been touched in this release. The suite is expected to
pass unchanged, and a change in the count would mean something unintended was staged.

---

# Chamnan README Audit (1.1.0) — COMPLETE, retained as history


Last updated: 2026-08-20

## Status

Current task: none — audit finished
Last completed task: TASK-14
Overall status: COMPLETE

## Checklist

- [x] TASK-01 Repository documentation inventory
- [x] TASK-02 README vs implementation mismatch audit
- [x] TASK-03 Requirements and compatibility
- [x] TASK-04 Quick Start and bootstrap lifecycle
- [x] TASK-05 Bootstrap side effects
- [x] TASK-06 Configuration reference
- [x] TASK-07 CLI commands and debugging
- [x] TASK-08 Troubleshooting
- [x] TASK-09 Update, disable and uninstall
- [x] TASK-10 Chaos Test verification
- [x] TASK-11 Security documentation verification
- [x] TASK-12 README structure cleanup
- [x] TASK-13 Full documentation consistency check
- [x] TASK-14 Tests and final validation

## Repository facts

- Repo root: `Work-Mode/chamnan/` inside the Lumin-App working tree, but it is its **own git
  repository** with remote `https://github.com/ArcticFox2029/chamnan.git`.
- Plugin version at audit start: **1.0.0** (`.claude-plugin/plugin.json`).
- Test suite: `python3 tests/run_tests.py` → 220 checks, stdlib only, no pytest.
- `lib/__pycache__/` is gitignored, not tracked.

## Authoritative file per feature

| Feature | Authoritative file(s) | Notes |
|---|---|---|
| Plugin metadata | `.claude-plugin/plugin.json` | name, version, description, keywords |
| Marketplace entry | `.claude-plugin/marketplace.json` | |
| Hook wiring | `hooks/hooks.json` | 4 events; commands use `${CLAUDE_PLUGIN_ROOT}` |
| Session-start injection | `hooks/session_start.py` | injects index + state + tools + skills + optional reply style |
| Session-end | `hooks/session_end.py` | |
| Scratch-script watcher | `hooks/scratch_watch.py` | `PostToolUse`, matcher `Bash\|Write\|Edit` |
| Bulk-read notice | `hooks/bulk_read_notice.py` | `PreToolUse`, matcher `Read` |
| Workspace paths + config | `lib/workspace.py` | `WORKSPACE_DIRNAME = ".chamnan"`; `find_root`, `workspace`, `ensure`, `load_config`, `enabled` |
| Config defaults | `lib/workspace.py` → `DEFAULT_CONFIG` | **single source of truth for TASK-06** |
| Index generation | `lib/mapper.py` (601 lines) | scan, symbol extraction, summaries, render |
| Index roll-up to budget | `lib/rollup.py` | shared by hook and reporter |
| Token estimation | `lib/tokens.py` | script-aware; drives budget enforcement |
| Schema / data model | `lib/schema.py` | SQL, Prisma, Django, SQLAlchemy, Rails, TypeORM, Room/JPA |
| Routes + env catalogue | `lib/catalogs.py` | HTTP decorators, OpenAPI, gRPC from `.proto`, env names |
| Deployment inventory | `lib/deploy.py` | K8s, Ansible, Helm, Compose, CI |
| Stored-material inventory | `lib/assets.py` | non-source trees, `MIN_FILES` threshold |
| Redaction / deny-list | `lib/redact.py` | `PATTERNS`, `scrub()`, `is_blocked()`, `is_never_opened()` |
| Attachment peeking | `lib/peek.py` + `bin/chamnan-peek` | |
| CLI: index | `bin/chamnan-map` | |
| CLI: peek | `bin/chamnan-peek` | flags `--find`, `--budget`, `--help` |
| CLI: promote | `bin/chamnan-promote` | flags `--list`, `--desc` |
| CLI: report | `bin/chamnan-report` | no flags registered |
| Slash commands | `skills/{bootstrap,capture,promote,remap,report}/SKILL.md` | |
| Agents | `agents/commenter.md`, `agents/librarian.md` | |
| Git integration | `bin/chamnan-map` (`--install-git-hook`) | marker text not yet verified — TASK-09 |
| Chaos Test numbers | `README.md` only | corpus lives OUTSIDE this repo at `~/Documents/test-chamnan/_megasystem` — **not reproducible from a clone**; relevant to TASK-10 |
| Benchmark harness | `bench/run_bench.py`, `bench/calibrate_tokens.py` | **untracked**; `bench/results.json` and `bench/bench.log` also untracked |

## CLI flag reality (recorded for TASK-02 / TASK-07)

`bin/chamnan-map` registers **no argparse arguments**. It substring-matches `argv`:

- `--install-git-hook` → `bin/chamnan-map:91`
- `--preview` → `bin/chamnan-map:93`

`--measure` is **not** accepted by `bin/chamnan-map`. It exists only in `lib/mapper.py`'s own
`main()` (`lib/mapper.py:566-569`: positional `repo`, `--out`, `--measure`), i.e. a
library/dev entry point invoked as `python3 lib/mapper.py <repo> --measure`.

`lib/mapper.py:21` docstring still names an old script, `map_project.py`.

## Completed Tasks

### TASK-01 — Repository documentation inventory

Status: COMPLETE

Files inspected:
- `.claude-plugin/plugin.json`, `hooks/hooks.json`
- `lib/workspace.py` (lines 13-45, 65-136)
- `bin/chamnan-map`, `bin/chamnan-peek`, `bin/chamnan-promote`, `bin/chamnan-report` (flag grep only)
- `lib/mapper.py` (argparse block only)
- repository file listing

Files changed:
- `README_AUDIT.md` (created)
- README.md: not modified

Findings:
- Feature-to-file inventory captured in the table above; `lib/workspace.py:DEFAULT_CONFIG` is the
  only place config defaults are defined.
- Two entry-point layers exist and differ: the plugin command `bin/chamnan-map` and the library
  `main()` in `lib/mapper.py`. Their accepted flags are not the same.
- `README.md` documents `chamnan-map --measure`, which the plugin command does not accept.
- The Chaos Test corpus is not part of this repository, so most of its numbers cannot be
  re-derived by anyone who clones it. TASK-10 must decide how to label them.
- Benchmark scripts under `bench/` are untracked, so README must not point readers at them until
  that is resolved.

Validation:
- `git status --short` before and after: only pre-existing untracked files
  (`bench/bench.log`, `bench/results.json`, `note-readme.md`). Nothing discarded.
- No source or README changes made, so no test run was required for this task.

Remaining concerns:
- `--measure` mismatch must be fixed in TASK-02 or TASK-07, not here.
- Git hook marker string still unverified (TASK-09).

### TASK-02 — README vs implementation mismatch audit

Status: COMPLETE

Files inspected:
- `README.md` (targeted line ranges only: 60-70, 176-200, 240-260, 265-305, 425-436)
- `lib/workspace.py` DEFAULT_CONFIG via import
- `hooks/session_start.py` REPLY_STYLES via regex
- `bin/chamnan-map` flag parsing (already recorded in TASK-01)

Files changed:
- `README.md` — one correction, `chamnan-map --measure` to `chamnan-map`
- `README_AUDIT.md`

#### Mismatches found

**M1 — unsupported CLI flag (FIXED in this task)**
- README says: `chamnan-map --measure`
- Implementation says: `bin/chamnan-map` registers no argparse args and substring-matches only
  `--install-git-hook` and `--preview`. `--measure` exists only in `lib/mapper.py` main().
  The bare `chamnan-map` already prints the token report the sentence is asking for.
- Decision: corrected to `chamnan-map`. Safe, unambiguous, allowed by TASK-02 scope.

**M2 — `--preview` implemented but undocumented**
- README says: nothing (0 occurrences)
- Implementation says: `bin/chamnan-map:93` handles `--preview`
- Decision: defer to TASK-07 (CLI commands). Needs its actual output described, not guessed.

**M3 — `reply_style` implemented but undocumented**
- README says: nothing (0 occurrences of `reply_style`, `concise` or `terse`)
- Implementation says: `DEFAULT_CONFIG["reply_style"] = "off"`; allowed values are
  `off` / `concise` / `terse` (`hooks/session_start.py:28`, and an unknown value injects nothing)
- Decision: defer to TASK-06 (configuration reference).

**M4 — `log_retention_days` implemented but undocumented**
- README says: only `logs/  bounded, expires` in the layout tree (line 273)
- Implementation says: `DEFAULT_CONFIG["log_retention_days"] = 7`, applied by `prune_logs()`
  which every `bin/` command calls
- Decision: defer to TASK-06.

**M5 — attachment numbers contradict the Chaos Test section in the same README**
- README says (lines ~293-299): "A 3.5 MB CSV is about a million tokens ... are 108 ...
  9,455x smaller"; "A SQLite file gives up its tables and row counts in 39"; "the matching rows
  of a 60,000-row file ... in 240"
- Implementation/measurement says: largest corpus CSV is 1.0 MB → 204 tokens against 418,607
  (2,050x); SQLite schema → 148 tokens; the Chaos Test section states these figures. The 9,455x
  shape derives from dividing a binary's size on disk by a constant, which `lib/peek.py`
  deliberately no longer does for binaries.
- Decision: do NOT edit here — numbers are TASK-10's scope, and the two sections must be
  reconciled together. Flagged as the highest-priority TASK-10 item.

**M6 — `lib/mapper.py:21` docstring names a script that does not exist**
- Implementation says: `python3 map_project.py <repo> [--out PATH] [--measure]`
- Reality: the file is `lib/mapper.py`; no `map_project.py` in the repo
- Decision: source comment, not README. Out of audit scope; noted for the owner.

#### Verified as consistent (no action)

- `--install-git-hook` — documented (line 255), implemented (`bin/chamnan-map:91`).
  Hook marker text still unverified; TASK-09.
- `index_token_budget` — documented as 3,000 default (line 196), matches DEFAULT_CONFIG.
- `warn_on_bulk_reads` — documented as settable to `false` (line 246), matches DEFAULT_CONFIG.
- `language` — documented with `{ "language": "th" }` example, matches DEFAULT_CONFIG default `en`.
- `MAP.md` / `STATE.md` / `config.json` — all referenced under `.chamnan/`, matching
  `lib/workspace.py:WORKSPACE_DIRNAME`.
- Five slash commands documented match the five `skills/*/SKILL.md` directories exactly.
- `map` / `state` / `capture` / `promote` / `report` / `agents` all present in DEFAULT_CONFIG and
  the README's claim that each part can be switched off independently (line 66) holds.
- `chamnan-peek` flags `--find` and `--budget` documented and implemented.

Validation:
- `python3 tests/run_tests.py` → 220/220 passed after the edit.
- `grep -n -- "--measure" README.md` → no matches.
- `git diff --stat -- README.md` → 1 file, 1 insertion, 1 deletion.
- `git status --short` → the three pre-existing untracked files still present, nothing discarded.

Remaining concerns:
- M5 is a factual contradiction visible to any reader of the README; it should not survive to
  release. TASK-10 must fix it.
- M2/M3/M4 mean three shipped features are invisible to users.

### TASK-03 — Requirements and compatibility

Status: COMPLETE

Files inspected:
- `hooks/*.py` and `bin/*` — shebang lines and executable bits (all 8 files)
- `hooks/hooks.json` — how hooks are launched
- `bin/chamnan-map:30-31, 64-90` — `HOOK_MARKER`, `HOOK_BODY`, `install_git_hook`
- `bin/chamnan-map:51-52` — the only `subprocess` call in the plugin
- import and syntax survey across `lib/*.py`, `bin/*`, `hooks/*.py`
- `README.md` — confirmed no Requirements section existed

Files changed:
- `README.md` — new `## Requirements` section with a `### Platforms` subsection, inserted
  immediately before `## Install`
- `README_AUDIT.md`

Evidence behind each claim:
- **Python floor 3.8** — assignment expression `:=` appears 6 times; grepped for and found NONE of
  `match/case`, `removeprefix`, `removesuffix`, `zoneinfo`, `graphlib`, `functools.cache`,
  `BooleanOptionalAction`, `ExceptionGroup`, `tomllib`, `pairwise`, `ast.unparse`, `strict=True`.
  So 3.8 is the honest floor, not a guess.
- **Tested on** Python 3.12.10, Darwin 25.2.0 arm64.
- **stdlib only** — full import survey yields only stdlib modules plus local `lib/` modules.
  No third-party names at all.
- **`python3` must be on PATH** — `hooks.json` uses `"type": "command"` with a bare path such as
  `"${CLAUDE_PLUGIN_ROOT}/hooks/session_start.py"`. All four hook scripts are `chmod +x` and carry
  `#!/usr/bin/env python3`. There is no explicit interpreter in the command string.
- **Git binary never invoked by the plugin** — the only `subprocess` call in the entire codebase is
  `bin/chamnan-map:52`, `subprocess.run([sys.executable, str(hook)], ...)`, which is `--preview`
  running the session-start hook. `install_git_hook` writes `.git/hooks/pre-commit` through
  `pathlib` alone.
- **Windows** — no code is platform-gated, but the launch path depends on shebang + exec bit, and
  the generated git hook starts `#!/bin/sh`. Recorded as "Not tested, and not expected to work
  as-is", with WSL pointed at the Linux row. No support claimed.

Wording used, as instructed: macOS "Supported and tested"; Linux "Expected to work, not tested";
Windows "Not tested, and not expected to work as-is".

Deliberately NOT claimed:
- No minimum Claude Code version. `plugin.json` declares none, so inventing one would be a guess.
  The section names the four hook events instead, which is checkable.

Validation:
- `python3 tests/run_tests.py` → 220/220 passed.
- `grep -n "^## " README.md` → `## Requirements` at line 69, immediately before `## Install` at 87.
- `git status --short` → `M README.md` plus the four pre-existing untracked files. Nothing
  discarded, nothing committed.

Remaining concerns:
- Linux is genuinely untested. If the owner has a Linux box, one `python3 tests/run_tests.py` plus
  one `chamnan-map` run there would upgrade that row from "Expected to work" to "Tested".
- `HOOK_MARKER` is `# >>> chamnan` — recorded here so TASK-09 does not have to rediscover it.

### TASK-04 — Quick Start and bootstrap lifecycle

Status: COMPLETE

Files inspected:
- `lib/workspace.py:118-139` — `ensure()`
- `skills/bootstrap/SKILL.md` — frontmatter and all six step headings, steps 3 and 4 read in full
- `README.md` — the old `## Install` section, and `## Layout` at line 323
- grep for every `STATE.md` reference across `bin`, `hooks`, `lib`, `skills`, `agents`

Empirical check (the decisive evidence, not inference):
Created a throwaway two-file repo in the scratchpad, ran `chamnan-map .`, and listed the result.
Created exactly:

```
.chamnan/  .chamnan/MAP.md  .chamnan/config.json  .chamnan/logs/  .chamnan/skills/  .chamnan/tools/
```

**`.chamnan/STATE.md` was NOT created.** It is written by Claude during bootstrap step 4, not by
any script — `hooks/session_start.py:77` only reads it if it happens to exist. The task brief said
not to assume these files exist, and that assumption would have been wrong for STATE.md.

Verified lifecycle:
install plugin → open Claude Code in the repo → `/chamnan:bootstrap` → (1) index built by
`chamnan-map` (2) coverage measured, comments *offered* if under 70% (3) baseline via
`chamnan-report` (4) Claude writes the first `STATE.md` (5) optional git hook offered
(6) honest report → every later session receives index + state from `hooks/session_start.py`.

Files changed:
- `README.md` — `## Install` replaced by `## Quick start`, with a five-row table of what bootstrap
  actually does, a new `### What it creates` subsection stating which files appear when and who
  writes them, and `### Trying it without installing`
- `README_AUDIT.md`

Findings:
- `ensure()` creates the workspace, three empty subdirectories, and `config.json`. On an upgrade it
  MERGES config rather than replacing it, keeping user keys and dropping keys no longer in
  `DEFAULT_CONFIG` — worth documenting in TASK-06 and TASK-09.
- Bootstrap is a skill, i.e. instructions Claude follows, not a script. That is why STATE.md exists
  only after step 4 and why step 2 can ask permission.
- The old Install section's `claude --plugin-dir ./chamnan` was correct but unexplained; it now
  shows the clone that makes that relative path true.

Deliberately NOT done:
- Did not create the link to a "bootstrap does not rewrite your code" section, because that section
  is TASK-05's to write and a dangling anchor would have failed TASK-13. Replaced with plain
  wording: "It never edits source code on its own."

Validation:
- `python3 tests/run_tests.py` → 220/220 passed.
- Empirical `find .chamnan` listing above.
- `grep -n "^## " README.md` → `## Quick start` at 87, `### What it creates` at 114.
- `git status --short` → `M README.md` plus the four pre-existing untracked files. Nothing
  discarded, nothing committed.

Remaining concerns:
- **I introduced a duplication.** `## Layout` (line ~323) now shows the same `.chamnan/` tree as the
  new `### What it creates`, which is a strict superset of it. TASK-12 should delete `## Layout`
  and keep `### What it creates`. Recorded here because I created the problem, not because I found
  it.

### TASK-05 — Bootstrap side effects

Status: COMPLETE

Files inspected:
- `skills/bootstrap/SKILL.md:17-40` — step 2 in full
- `agents/commenter.md` — frontmatter and its prohibition lines
- `bin/chamnan-map:177-191` — the low-coverage branch
- `lib/workspace.py` — `ensure()`, `enabled()` (already recorded in TASK-04)

Files changed:
- `README.md` — new `## Bootstrap does not rewrite your code` section with four subsections
  (Read-only / Written automatically / Optional after you say yes / The one write outside
  `.chamnan/`), inserted before `## Evidence`; the Quick start step-2 row now links to it
- `README_AUDIT.md`

Answers to the questions the task asked:

- **What bootstrap reads**: source files, for their opening comment and top-level symbols. Reads
  only; no source file is ever opened for writing by the scanner.
- **What chamnan creates internally**: `.chamnan/` plus `skills/`, `tools/`, `logs/`;
  `config.json` (merged on upgrade); `MAP.md` rewritten each index run; logs pruned per
  `log_retention_days`. All inside `.chamnan/`.
- **Does it evaluate coverage**: yes — `bin/chamnan-map` computes it and branches at `pct < 70`.
- **Does it offer to add comments**: yes, and only offers. `chamnan-map` prints a suggestion and a
  sample of missing files; it performs no edit. When `agents` is `false` it changes the wording
  instead of pointing at a disabled agent (`bin/chamnan-map:186-189`).
- **Is approval required before modifying source**: yes, and the skill says it twice — "**with the
  user's go-ahead**" and "Never edit files for this without asking first. It touches every
  undocumented file in the repo."

The README claim written in TASK-04 — "It never edits source code on its own" — is therefore
accurate. It has been replaced by a link to the new section rather than left as a bare assertion.

Findings worth keeping:
- The `commenter` agent's real boundary is its `tools: Read, Edit, Glob` frontmatter, which is
  enforced outside the agent: no shell, no `Write`, no create or delete. That is a hard limit.
- Its behavioural rules ("one line", "never touch a file that already has a comment", "never change
  code") are prompt instructions to a `haiku` model, NOT code-enforced. The README now says this
  plainly and tells the reader to review the diff. Overstating it as a guarantee would have been
  the easy and wrong thing to write.
- The optional git hook is the only write outside `.chamnan/`. It appends a block marked
  `# >>> chamnan` and never clobbers an existing hook (`bin/chamnan-map:72-84`).

Validation:
- `python3 tests/run_tests.py` → 220/220 passed.
- Internal-anchor check across the whole README: 1 link, 0 broken. The link added in this task
  resolves to the section added in this task.
- `grep -n "^## " README.md` → new section at 147, before `## Evidence` at 202.
- `git status --short` → `M README.md` plus the four pre-existing untracked files. Nothing
  discarded, nothing committed.

Remaining concerns:
- None specific to this task. The TASK-12 debt from TASK-04 (redundant `## Layout`) still stands.

### TASK-06 — Configuration reference

Status: COMPLETE

Files inspected:
- `lib/workspace.py:18-64` (DEFAULT_CONFIG with its authoring comments), `prune_logs():98-107`
- `hooks/session_start.py` — the `capture` gate at :99, `REPLY_STYLES` at :28
- grep for every config key across `lib`, `bin`, `hooks`, `skills`, `agents` to find its consumer

Files changed:
- `README.md` — new `## Configuration` section with an 11-row table and an `### On upgrade`
  subsection, inserted before `## Commands`
- `README_AUDIT.md`

Verified defaults, straight from `lib/workspace.py` (all eleven, nothing inferred):
`map` true · `state` true · `capture` true · `promote` true · `report` true · `agents` true ·
`log_retention_days` 7 · `language` "en" · `index_token_budget` 3000 · `warn_on_bulk_reads` true ·
`reply_style` "off"

`reply_style` valid values confirmed as exactly `off` / `concise` / `terse`. `off` is the default
and injects nothing; the two named styles come from `REPLY_STYLES` in `hooks/session_start.py:28`;
an unrecognised value injects nothing rather than erroring.

Consumer of each key, recorded so a future task does not re-derive it:
- `map` → `bin/chamnan-map`, `hooks/session_start.py`
- `state`, `capture`, `reply_style` → `hooks/session_start.py`
- `promote` → `bin/chamnan-promote`, `hooks/scratch_watch.py`, `hooks/session_end.py`,
  `hooks/session_start.py`
- `report` → `bin/chamnan-report`
- `agents` → `bin/chamnan-map`
- `language` → `bin/chamnan-map`, `bin/chamnan-report`
- `index_token_budget` → `bin/chamnan-map`, `hooks/session_start.py`
- `warn_on_bulk_reads` → `hooks/bulk_read_notice.py`
- `log_retention_days` → `lib/workspace.py:prune_logs()` only (the initial key-consumer grep
  excluded `workspace.py` and so appeared to find no consumer — it does have one)

Fixes the two gaps TASK-02 recorded:
- M3 `reply_style` — now documented, with its exact enum.
- M4 `log_retention_days` — now documented, including that pruning is best-effort and silent.

Validation:
- **Machine-checked the table against the source**: parsed the 11 rows back out of README.md and
  compared to `workspace.DEFAULT_CONFIG` → keys documented 11 of 11, none missing, none present in
  the table that is absent from the code, and zero default-value mismatches.
- `python3 tests/run_tests.py` → 220/220 passed.
- `git status --short` → `M README.md` plus the four pre-existing untracked files. Nothing
  discarded, nothing committed.

Remaining concerns:
- Three existing prose sections now overlap the table: `## Language` (the `language` rationale),
  `## One file, only what applies, and a ceiling` (`index_token_budget`), and `## Bulk reads`
  (`warn_on_bulk_reads`). They were deliberately kept — they carry the WHY, the table carries the
  WHAT — but TASK-12 should confirm none has become purely redundant.

### TASK-07 — CLI commands and debugging

Status: COMPLETE

Files inspected:
- `bin/chamnan-map:45-63` — the `preview()` function
- `bin/chamnan-promote:10-11, 55-65` — usage lines and flag handling
- `bin/chamnan-peek` — via its own `--help` output
- `bin/chamnan-report` — via running it

Empirical checks (ran the commands rather than reading them):
- `chamnan-map --preview` in a throwaway repo → prints the session-start injection verbatim
  (`## chamnan` / `### Architecture index` / the Quick Index) then a footer giving the token count
  and the sentence "This is what every session in this repo receives automatically". Writes nothing.
- `chamnan-peek --help` → confirms `--find PATTERN` and `--budget 800`, and states the default
  ceiling is **400 tokens**.
- `chamnan-report` in a repo with no history → "no Claude Code transcripts found … (nothing to
  measure until this repo has been worked on in Claude Code)". It degrades honestly, so the README
  says so.

Files changed:
- `README.md` — `## Commands` rewritten: slash commands split from shell commands, every flag
  documented, and a new `### When something looks wrong` subsection
- `README_AUDIT.md`

Findings:
- `--preview` (mismatch M2 from TASK-02) is now documented, and it is the natural debugging entry
  point: it answers "is anything being injected, and how much" without guesswork. Its description
  comes from running it, not from reading the code.
- `bin/chamnan-map` matches flags by membership in `argv` rather than parsing them, so a misspelt
  flag is ignored silently. Documented in the debugging subsection, because it is exactly the kind
  of thing that wastes an afternoon.
- `chamnan-promote`'s real usage is `<file> <name> [--desc "..."]` — the README previously implied
  only that a shell equivalent existed, without the argument shape.

Validation:
- **Cross-checked documented flags against implemented flags.** Documented: `--budget`, `--desc`,
  `--find`, `--install-git-hook`, `--list`, `--preview`. Implemented across `bin/`: the same six
  plus `--help`. So every documented flag exists, and the only undocumented one is `--help`, left
  out deliberately as self-documenting.
- `grep -c -- "--measure" README.md` → 0. The M1 correction has not regressed.
- `python3 tests/run_tests.py` → 220/220 passed.
- `git status --short` → `M README.md` plus the four pre-existing untracked files. Nothing
  discarded, nothing committed.

Remaining concerns:
- `### Reading an attachment without reading it` sits directly under `## Commands` and still holds
  the wrong figures (M5). Left untouched on purpose; it is TASK-10's.

### TASK-08 — Troubleshooting

Status: COMPLETE

Files inspected:
- grep across `lib/*.py` and `bin/*` for the exact user-visible failure strings
- `README.md` — `## Commands` and the `### When something looks wrong` subsection added in TASK-07

Files changed:
- `README.md` — new `## Troubleshooting` section (12-row symptom table) placed before
  `## Limitations`; the TASK-07 `### When something looks wrong` subsection was FOLDED INTO it and
  removed from under `## Commands`, so there is only one troubleshooting home
- `README_AUDIT.md`

Every quoted message was verified verbatim in the source, not paraphrased:
- `no recognised source files under {root}` — `lib/mapper.py`, and `bin/chamnan-map` for `{target}`
- `chamnan: nothing to inject yet — run chamnan-map first` — `bin/chamnan-map`
- `chamnan: not a git repository — nothing to install into` — `bin/chamnan-map`
- `chamnan: no Claude Code transcripts found for {root}` — `bin/chamnan-report`

All seven required symptoms are covered, plus five more that came out of the earlier tasks:
bootstrap unavailable · nothing injected · `python3` missing · hooks not firing on POSIX ·
hooks on Windows · unrecognised source files · index mostly filenames · index stale ·
over token budget · not a git repository · a flag silently ignored · rebuilding a workspace file.

Remedies use only verified commands and settings: `claude plugin list`, `python3 -V`, `chamnan-map`,
`chamnan-map --preview`, `chamnan-map <dir> [<dir> …]`, `chamnan-map --install-git-hook`,
`/chamnan:remap`, and the `index_token_budget` / `agents` config keys. Nothing invented.

Validation:
- Internal-anchor check across the whole README: 2 links, 0 broken (the new `[Commands](#commands)`
  reference resolves).
- Regex check for orphaned whitespace after lifting the subsection: 0 runs of 4+ newlines, and the
  one leftover double blank line was collapsed.
- `python3 tests/run_tests.py` → 220/220 passed.
- `git status --short` → `M README.md` plus the four pre-existing untracked files. Nothing
  discarded, nothing committed.

Remaining concerns:
- The Windows row says "Use WSL". That follows from TASK-03's finding but has not been executed on
  WSL by anyone. It is phrased as the supported route rather than as a tested one.

### TASK-09 — Update, disable and uninstall

Status: COMPLETE

Files inspected:
- `bin/chamnan-map:30` and `:41` — the two hook markers, read directly rather than trusted from
  the previous handoff
- `claude plugin --help` and `claude plugin marketplace --help` — the real subcommand list

Files changed:
- `README.md` — new `## Update, disable, uninstall` section with six subsections, placed after
  `## Troubleshooting` and before `## Limitations`
- `README_AUDIT.md`

Plugin-manager commands: VERIFIED, not guessed. `claude plugin --help` lists `update`, `disable`,
`enable`, `uninstall|remove`, `list`, `install`, `marketplace`; `claude plugin marketplace --help`
lists `add`, `remove|rm`, `list`, `update`. So the section documents real commands. It still opens
by saying these belong to Claude Code and that `claude plugin --help` is the authority if a build
differs — the brief's instruction not to guess is satisfied by checking, and the caveat covers other
versions.

`claude plugin update`'s own help states "restart required to apply", and the README repeats that
rather than implying the running session picks it up.

Empirical checks (run, not reasoned):
- Wrote `.chamnan/config.json` containing only `{"reply_style": "terse", "index_token_budget":
  9000}`, then ran `chamnan-map`. Result: both custom values intact, file grown to all 11 keys.
  This is the merge behaviour, demonstrated.
- `rm -rf .chamnan` then `chamnan-map` → recreated `.chamnan/`, `MAP.md`, `config.json`, `logs/`,
  `skills/`, `tools/`, with `reply_style` back to `"off"`. **`STATE.md` was NOT recreated**, which
  matches TASK-04 and is called out in the README as the one thing to copy before deleting.

Git hook removal: markers confirmed as `# >>> chamnan` (`bin/chamnan-map:30`) opening and
`# <<< chamnan` (`:41`) closing. Documented as "delete those lines and everything between them",
with the note that deleting the whole file is equivalent when chamnan created it.

Validation:
- Internal-anchor check across the whole README: 3 links, 0 broken (the new
  `[Configuration](#configuration)` reference resolves).
- `python3 tests/run_tests.py` → 220/220 passed.
- `git status --short` → `M README.md` plus the four pre-existing untracked files. Nothing
  discarded, nothing committed.

Remaining concerns:
- The plugin name is written as `chamnan@chamnan` throughout, matching what `claude plugin list`
  reported in this environment. If a user added the marketplace under another name, their id
  differs; the section points at `claude plugin list` for that.

### TASK-10 — Chaos Test verification

Status: COMPLETE

Re-measured the corpus at `~/Documents/test-chamnan/_megasystem` rather than trusting the README.
Chaos test was NOT removed, as the brief requires.

Files changed:
- `README.md` — mismatch M5 resolved; nine drifted figures corrected; a provenance paragraph added
  labelling which numbers are observed, which are estimates, and that all of it is a
  synthetic-corpus result
- `README_AUDIT.md`

**M5 RESOLVED.** `### Reading an attachment without reading it` claimed "a 3.5 MB CSV ... 108 tokens
... 9,455x smaller", "a SQLite file ... in 39", "a 60,000-row file ... in 240". None of those are
reproducible, and the 9,455x shape came from dividing a binary's size on disk by a constant, which
`lib/peek.py` no longer does. Replaced with the measured figures the chaos test already carried:
CSV 418,607 → 204, SQLite schema in 148, spreadsheet `--find` in 214. The two sections now agree.

Figures corrected (README value → measured value):
- total files 2,367 → **2,365**
- file types 30 → **31** (`.kts` became indexable when Kotlin got its own rules)
- symbols 3,177 → **3,266** (the Kotlin/Ruby/C-header extractor work raised it)
- non-source files 1,687 → **1,672**
- whole source 11,721,535 → **11,560,484**
- index 51,922 → **51,937**
- whole-index ratio 265x → **223x**
- "index is 0.02% of the source" → **0.4%** (51,937 / 11,560,484; the old figure was wrong by 20x)
- "five apparent credential hits" → **six**, the new one being `buildProperty`, verified as a Kotlin
  function in `apps/android/build.gradle.kts`

Verified unchanged, no edit needed:
size 34 MB · 8 writing systems · 529 source files · 517/529 = 98% coverage · 94 tables/models ·
116 routes (104 HTTP + 12 gRPC) · 74 Kubernetes objects across 27 kinds · 43 Ansible · 24 Compose ·
31 images · 21 pipelines · 64 environment variables · ~2,998 tokens injected per session ·
per-section ratios schema 174x, deployment 108x, config 110x, API 58x ·
92 planted credentials across 13 categories, none reaching MAP.md as a value

Labelling added, as the brief requires:
- **Observed** — counts of files, languages, tables, routes, Kubernetes objects, credentials.
  Reproducible by anyone holding the corpus.
- **Estimated** — every token figure. They come from `lib/tokens.py`, a script-aware estimator
  calibrated against measured API usage, not from an exact API count. The README now says a figure
  like 11,560,484 "is an estimate of a size, not a receipt".
- **Synthetic-corpus result** — the whole section. Stated as evidence the tool holds up under load,
  explicitly not a benchmark of the reader's codebase.

Validation:
- Programmatic sweep for stale figures — `2,367`, `11,721,535`, `51,922`, `3,177`, `1,687`, `9,455`,
  `265×` — all absent from README.md.
- Internal-anchor check: 3 links, 0 broken.
- `python3 tests/run_tests.py` → 220/220 passed.
- `git status --short` → `M README.md` plus the four pre-existing untracked files. Nothing
  discarded, nothing committed.

Remaining concerns:
- The corpus still is not in this repository, so "reproducible by anyone holding it" means the
  author. That is disclosed rather than solved.
- `bench/` remains untracked; the README does not point at it, which is correct for now.

### TASK-11 — Security documentation verification

Status: COMPLETE

Files inspected:
- `lib/redact.py` — `BLOCKED_SUFFIXES`, `BLOCKED_NAMES`, `NEVER_OPENED_SUFFIXES`, `is_blocked()`,
  `is_never_opened()`, `scrub()`, and the module docstring
- `lib/catalogs.py` `scan_env()` and the `ENV_FILE_KEY` / `ENV_IN_CODE` patterns
- `tests/run_tests.py` — the seeded credential cases
- `README.md` `## Secrets`, and `### What it protects` in the chaos test

Files changed:
- `README.md` — `## Secrets` bullets rewritten against the code; new `### What this is not`
  subsection replacing the single closing paragraph
- `README_AUDIT.md`

Claims checked, and how they came out:
- "Some files are never opened" — TRUE for the scanner. Expanded the list to match
  `BLOCKED_SUFFIXES` exactly (`.p12`, `.cer`, `.jks`, `.dump` were missing from the README).
- **Gap found and closed: `chamnan-peek` was not mentioned at all.** It has a NARROWER refusal list
  (`is_never_opened`) than the scanner's (`is_blocked`), and the difference is deliberate: the
  scanner will not open a `.sqlite`, while peek shows a database's schema and never a row. A reader
  of the old text would have concluded peek refuses databases too. Now documented as the distinct
  behaviour it is.
- "Everything written passes a redactor" — was understated. `scrub()` also runs on peek's printed
  output, not only on `MAP.md`. Corrected to "everything chamnan emits".
- "Environment variables recorded as names only ... values are discarded at parse time" — TRUE, and
  weaker than reality. `ENV_FILE_KEY` matches the name and stops at the `=`; the value is not in any
  capture group. Restated as "never captured in the first place", which is both stronger and
  verifiable.
- The `PostToolUse` limitation paragraph was already correct and is kept, promoted into a
  `### What this is not` heading so it is findable rather than buried at the end.
- `### What it protects` in the chaos test — checked, consistent, left unchanged. Its bold "None of
  them reached MAP.md" is scoped to the corpus by the provenance paragraph added in TASK-10, and the
  new Secrets section says explicitly that this is "good evidence, and still not a proof about your
  repository".

Honest limitations ADDED rather than removed:
- chamnan is stated not to be a sandbox, in those words, with the concrete example that asking
  Claude to open `.env` opens `.env` and chamnan is not in that path.
- The patterns are narrow by design, and narrow means some things get through — an unfamiliar
  credential shape, or a bare high-entropy string with no assignment around it, will not match.
  Framed as a chosen trade, since widening it would eat commit hashes and UUIDs.
- Readers are told to review `MAP.md` before its first commit.

Validation:
- Programmatic scan for forbidden absolute claims — "100% secure", "cannot leak", "fully prevents",
  "completely safe", "guarantees" — none present anywhere in README.md.
- `python3 tests/run_tests.py` → 220/220 passed.
- `git status --short` → `M README.md` plus the four pre-existing untracked files. Nothing
  discarded, nothing committed.

Remaining concerns:
- None for this task. chamnan is described as defending its own output and nothing more.

### TASK-12 — README structure cleanup

Status: COMPLETE

Files changed:
- `README.md` — 24 top-level sections reordered to 23; `## Layout` deleted; duplicated Git-hook
  mechanics trimmed out of `## Keeping the index fresh`
- `README_AUDIT.md`

Method: split the file on `^## ` headings, reassembled in an explicit target order, then asserted
that the set of headings before and after was identical, and that **every non-blank line of the
original still appears in the output** except those belonging to the one deleted section. Result:
0 lines lost. No prose was rewritten in the move.

New order:
intro · Read this before installing · The problem it aims at · What it does · Who this is for ·
Who this is not for · Requirements · Quick start · Bootstrap does not rewrite your code · Language ·
One file, only what applies, and a ceiling · Keeping the index fresh · Bulk reads · Configuration ·
Commands · Secrets · Evidence · The chaos test · Troubleshooting · Update, disable, uninstall ·
What it deliberately does not do · Limitations · Tests · License

Against the brief's target flow: the audience sections moved from position 9-10 up to 5-6, before
Requirements as asked; Security (`## Secrets`) moved out of the middle of the how-it-works material
to sit after Commands; Measurements (`## Evidence`) now sits directly before the chaos test;
Troubleshooting and Update/uninstall are adjacent and late; Tests moved down beside License.

Debt 1 — **`## Layout` deleted.** It showed the same `.chamnan/` tree as `### What it creates`
(added in TASK-04), which additionally states who writes each file and when. A strict subset, so
removing it loses nothing.

Debt 2 — the three sections that overlap `## Configuration` were each examined:
- `## Language` — KEPT. Carries the rationale for the `en` default and the guarantee that reply
  language is unaffected. The table row states the value, not the reasoning.
- `## One file, only what applies, and a ceiling` — KEPT. Explains that everything is one `MAP.md`,
  that a section appears only when the repo has that thing, and that Full Detail is never injected.
  None of that is in the table.
- `## Bulk reads` — KEPT. Explains why it never blocks, and why comments are not stripped on the way
  in. The table row is one line about a boolean.
- `## Keeping the index fresh` — TRIMMED, not deleted. Its Git-hook mechanics had become the fourth
  copy (Commands, Update/uninstall, Troubleshooting). The mechanics now point at
  `[Update, disable, uninstall](#update-disable-uninstall)`, and the section keeps the argument that
  is only made here: "A stale index is worse than no index: it is confidently wrong, and the next
  session believes it."

Validation:
- Heading-set equality before/after, and a line-level content check: 0 non-blank lines lost.
- Internal anchors: 4 links, 0 broken (one added by this task).
- `# >>> chamnan` now appears twice rather than three times — once where the hook is described,
  once where its removal is documented.
- Regex check for stray whitespace at the new seams: 0 runs of 3+ blank lines.
- `python3 tests/run_tests.py` → 220/220 passed.
- `git status --short` → `M README.md` plus the four pre-existing untracked files. Nothing
  discarded, nothing committed.

Remaining concerns:
- Both debts recorded by earlier tasks are now discharged; nothing is carried forward.
- `## Tests` sits between `## Limitations` and `## License`. Defensible, but a reviewer might prefer
  it beside the chaos test. Left as is — it is a judgement call, not an error.

### TASK-13 — Full documentation consistency check

Status: COMPLETE

**Result: 0 inconsistencies. No changes made to README.md.**

Checked programmatically rather than by reading, so the result is repeatable. Ten checks:

1. Config table vs `lib/workspace.py:DEFAULT_CONFIG` — 11/11 keys present, no extras, no
   default-value mismatches.
2. Every `--flag` in the README vs the flags implemented in `bin/*` — one apparent miss,
   `--plugin-dir`, confirmed to be **Claude Code's own** flag (`claude --help` lists it), so a false
   positive of the checker, not a documentation error.
3. Every `/chamnan:<name>` vs `skills/<name>/` — all five resolve.
4. Stale references retired by earlier tasks — `2,367`, `11,721,535`, `51,922`, `3,177`, `1,687`,
   `9,455`, `265x`, `--measure`, `map_project.py`, `0.02% of the source` — all absent.
5. Absolute security claims — none present.
6. Internal anchors — 4 links, 0 broken.
7. `.chamnan/` paths named in the README vs the six the code creates — exact match.
8. "220 checks" claim vs a live run of the suite — matches.
9. Plugin version — README states none, so nothing can drift.
10. `reply_style` values — `off`, `concise`, `terse` all documented.

Also checked for references to things removed in earlier tasks (`## Layout`, the old
`### When something looks wrong`) and to files not in the repository (`bench/`, `run_bench`,
`calibrate_tokens`, `note-readme`) — zero occurrences of each. The only file path the README cites,
`lib/workspace.py`, exists.

External links: both return HTTP 200. The odd-looking `…cavemen-tosave-tokens` segment in the
JetBrains URL is the real URL, not a typo — verified rather than "corrected".

### TASK-14 — Tests and final validation

Status: COMPLETE

Every command example in the README was executed in a throwaway git repository, not merely read:

| command | result |
|---|---|
| `chamnan-map .` | OK |
| `chamnan-map --preview` | OK |
| `chamnan-peek data.csv` | OK |
| `chamnan-peek data.csv --find DEHAM` | OK |
| `chamnan-peek data.csv --budget 800` | OK |
| `chamnan-promote --list` | OK |
| `chamnan-report` | prints "no Claude Code transcripts found …" and exits non-zero — exactly the documented behaviour on a repo with no history |
| `chamnan-map --install-git-hook` | OK; re-running prints "already installed", so it is idempotent |

Git hook instructions validated by doing them: the hook lands at `.git/hooks/pre-commit`, mode
`-rwxr-xr-x`, opening `#!/bin/sh`, with exactly one `# >>> chamnan` and one `# <<< chamnan`.
Programmatically removing the marked block leaves `#!/bin/sh` and nothing else, so the README's
"delete those lines and everything between them, or delete the whole file" is literally true.

Required commands:
- `git diff --check` → clean, no whitespace errors
- `git status --short` → `M README.md` plus four pre-existing untracked files
- `git diff --stat` → `README.md | 565 ++++---`, 421 insertions, 144 deletions
- `python3 tests/run_tests.py` → **220/220 checks passed**

Nothing was committed, per the brief.

Remaining concerns for the owner:
- `chamnan-report` exits non-zero when a repo has no transcript history. Correct behaviour, and the
  message is clear, but a script wrapping it would see a failure. Not documented as an exit code;
  judged not worth a README line.
- The chaos-test corpus and `bench/` are outside the repository, so those figures are reproducible
  only by the author. Disclosed in the README's provenance paragraph rather than solved.
- `## Tests` sits between `## Limitations` and `## License`. A judgement call left as it is.
- `README_AUDIT.md`, `note-readme.md`, `bench/bench.log` and `bench/results.json` remain untracked.
  Decide whether `README_AUDIT.md` should be committed or added to `.gitignore`.

## Current Handoff

Previous task:
TASK-14

Next task:
none — the audit is COMPLETE

What changed overall:
- `README.md` only: 421 insertions, 144 deletions. Sections added — Requirements, Quick start
  (replacing Install), Bootstrap does not rewrite your code, Configuration, Troubleshooting,
  Update/disable/uninstall. Sections corrected — Commands, Secrets, The chaos test. Section deleted
  — Layout. Whole file reordered to the intended reading flow.
- `README_AUDIT.md` created as the audit record.
- No source file was changed by this audit. The 220-check suite passed at the end of every task.

Six mismatches were found and all are resolved:
- M1 `chamnan-map --measure` did not exist → corrected to `chamnan-map` (TASK-02)
- M2 `--preview` implemented but undocumented → documented from running it (TASK-07)
- M3 `reply_style` undocumented → documented with its enum (TASK-06)
- M4 `log_retention_days` undocumented → documented (TASK-06)
- M5 attachment figures contradicted the chaos test in the same file → replaced with measured
  values; the 9,455x claim described behaviour the code had already removed (TASK-10)
- M6 `lib/mapper.py:21` docstring names a non-existent `map_project.py` → SOURCE comment, outside
  audit scope, still unfixed. The only item left on the board.

Nothing is pending for a next session. If the owner wants one more pass, M6 is a one-line source
comment fix, and deciding the fate of `README_AUDIT.md` (commit or ignore) is the other open call.
