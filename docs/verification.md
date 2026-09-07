# Verification

What to run before tagging a release, and what a good result looks like.

Everything here works from a clean clone. There is nothing to install and no credentials involved.

## The test suite

```bash
python3 tests/run_tests.py
```

Expected output:

```
N/N checks passed
```

Exit status `0`. The two numbers are what matters, not their value: the count grows every time a
check is added, and a figure written here would be stale within the week. It has been in the
thousands since well before 1.0 — this block used to print `220/220`, a snapshot from an early
release that survived the suite growing more than tenfold past it, and a reader who took it
literally would have concluded a correct run was broken.

A failure prints each failed check by name before the total, and exits `1`:

```
  FAIL  <name of the check>

N-1/N checks passed
```

There is no pytest, no fixtures directory and no configuration file. A check is a call to
`check(name, condition)` in `tests/run_tests.py`, and the suite uses only the standard library —
so if it runs on your Python, it runs.

## Smoke test on a real repository

The suite proves the parts work. This proves the plugin works end to end. Run it from inside any
repository you do not mind writing a `.chamnan/` directory into:

```bash
chamnan-map
```

A healthy run reports the file count, the token cost of each half of the index, comment coverage,
and whether the index fits `index_token_budget`. Then:

```bash
chamnan-map --preview
```

That prints exactly what a session in that repository would receive at start-up, followed by its
token count, and it writes nothing — including in a repository that has never run chamnan, where it
previously created the whole workspace before telling you what you would get.

Read the block itself for the answer: a repository with no index says so in it, in a line naming
`chamnan-map`. The older instruction here — look for `nothing to inject yet — run chamnan-map
first` — described a fallback that only fires when the hook produces no output at all, which it no
longer does; that string is still in the code and is no longer the signal to watch for.

## Release checklist

Work down it. Each step is a command whose output you can read, not a judgement call.

**1. The tree is clean and the tests pass.**

```bash
git status --short          # expect no output
python3 tests/run_tests.py  # expect N/N checks passed
```

**2. The version has been bumped, in the one place that matters.**

`.claude-plugin/plugin.json` is the only file carrying an authoritative version. `marketplace.json`
has no version field, and the README carries no version-specific text — if that changes, this list
has to change with it.

```bash
git diff HEAD~1 -- .claude-plugin/plugin.json
```

Choose the number by what actually changed, not by diff size:

| | |
|---|---|
| **Patch** | backward-compatible fixes only |
| **Minor** | backward-compatible capability added — a new language, a new section in the index |
| **Major** | a config key renamed or removed, a command or flag dropped, or a change to the shape of a generated file |

Documentation-only work is not a functional change and should not be described as one in the notes.

**3. The candidate goes to the private mirror first, and only a green one goes public.**

`ArcticFox2029/chamnan-test` is a private clone of this repository carrying the same
`.github/workflows/tests.yml`, so the same five jobs run there. It exists because a red column is
information, not something to publish: 1.23.1 spent an evening pushing candidates to the public
repository and collecting failed runs on it, each one visible forever beside the releases.

Verified 2026-09-08, and in both directions, because a mirror that cannot go red is a mirror that
proves nothing:

- A pull request opened on it dispatches all five jobs — ubuntu 3.8, ubuntu 3.13, macos 3.13,
  windows 3.8, windows 3.13 — exactly as the public one does. A push to a branch alone does not;
  the workflow fires on `pull_request` and on a push to `main`.
- The candidate that had just failed the public repository's Windows columns failed the mirror's
  in the same place and on the same checks: `EVERY ONE OF 400 CONCURRENT INCREMENTS IS RECORDED`
  at 31 and 207 of 400, against 41 and 187 on the public run. Different numbers, because the defect
  is a timing one; the same finding.

The mirror is slower — 6 to 9 minutes a job against 3 to 4 — which is the cost of it, and it is
paid while the local suite is running anyway.

```bash
git remote add staging https://github.com/ArcticFox2029/chamnan-test.git   # once per checkout
git push staging main:main release/{version}:release/{version}
gh pr create --repo ArcticFox2029/chamnan-test --base main --head release/{version} \
  --title "{version} release candidate — staging run" --fill
gh pr checks <n> --repo ArcticFox2029/chamnan-test --watch
```

**Push it to the mirror before the local suite finishes, not after.** The two measure different
things and neither waits on the other: the local run cannot see Windows at all, and CI cannot see
this machine. Running them in series turned a 12-minute wait into a 22-minute one, several times
in one evening.

Only once all five are green:

```bash
git push -u origin release/{version}
gh pr create --fill
gh pr checks --watch
gh pr merge --squash --delete-branch
git switch main && git pull
```

`main` is protected, and a direct `git push origin main` is rejected with
`GH006: Protected branch update failed` — that has been true since 1.18.0, so the pull request is
the normal path rather than an exception to it.

**Windows is the column that catches what a Mac cannot**, and it has caught a real regression here
more than once — a `#!/bin/sh` fixture that will not run, a path compared with the wrong separator,
a `/nonexistent-...` path that is writable there, a subprocess spawn added per session, and a lock
whose timeout was a ceiling on total waiting rather than on waiting without progress. A red Windows
job is a finding, not a flake; read it before re-running it.

**And before reaching for CI at all, ask whether the platform difference can be squeezed instead.**
Four of those five were findable from macOS, and the fifth — the lock — was reproduced here in
thirty seconds by shrinking `LOCK_TIMEOUT` to 0.05 s, which is the 40x that separates the two
platforms. `tests/test_concurrent_writers.py` runs that squeeze on every platform now. A CI round
trip is twenty minutes; a squeeze is thirty seconds and it runs on the machine you are already
sitting at.

Tag after the merge, not before, so the tag never points at a commit no one else can fetch.

**4. Dry-run the tag.**

```bash
claude plugin tag --dry-run
```

This is a real check, not a formality. It refuses to proceed on a dirty working tree, and it
validates that `plugin.json` agrees with the marketplace entry — so a version bumped in one place
and not the other is caught here rather than after publishing. Expect it to print the tag it would
create, in the form `chamnan--v{version}`.

**5. Create and push the tag with the same tool.**

```bash
claude plugin tag --push
```

`chamnan--v{version}` is the convention Claude Code uses for plugin releases. Do not hand-write a
differently shaped tag; a plain `v{version}` is not the same thing and has had to be corrected
before.

**6. Confirm the tag reached the remote and points where you think it does.**

```bash
git ls-remote --tags origin
```

An annotated tag appears twice — the tag object, and a `^{}` line dereferencing to the commit. The
second one is the commit the release actually ships.

**7. Tag the release, and publish from it.**

There are TWO tags per release and they are not interchangeable. `chamnan--v{version}` is the one
Claude Code reads to resolve a plugin version, and step 5 creates it. `v{version}` is the one the
releases page is built on, which every release from 1.14.0 onward has used. Both point at the same
commit.

```bash
git tag -a v{version} -m "chamnan {version}" && git push origin refs/tags/v{version}
gh release create v{version} --verify-tag --notes-file <your-notes> --latest
```

`--verify-tag` makes the command fail rather than invent a tag if the name is wrong — which is the
behaviour you want when the tag name is the thing most likely to be mistyped.

🐛 This step named `chamnan--v{version}` from 2026-08-20 until 1.20.0, while every release actually
published in that time used `v{version}`. Following the checklist as written would have put one
release on a tag no other release uses.

`.github/release-template.md` is a starting point for the notes.

### The demo page ships with the release, not after it

`site/` is published separately at
[arcticfox2029.github.io/chamnan-measure](https://arcticfox2029.github.io/chamnan-measure/), from
the `ArcticFox2029/chamnan-measure` repository. It runs chamnan's REAL modules through Pyodide, and
its whole claim to be worth looking at is that the numbers on it are this tool's own. That stops
being true the moment a release goes out without it, and nothing about the page says so — it will
keep reporting an old build's behaviour, confidently, in five languages.

So it is part of the release, in this order:

**a. Rebuild the bundle.** `python3 site/build.py` copies the import closure out of `lib/` and
writes the version into `site/lib/manifest.json`, which is what the page displays. Run it AFTER the
version bump, or the page announces the previous release. The suite has a check for the copy having
drifted; it cannot check that you rebuilt after bumping rather than before.

**b. Re-measure the sample table.** The rows in `PRE` are real measurements with a date beside
them, and those repositories are worked on daily — the figures move. A table that never changes is
a table nobody is measuring, and this one is the page's evidence that it measures anything at all.

```bash
python3 site/remeasure.py chalk/chalk facebook/react …      # one JSON line per repository
```

`site/remeasure.py` reproduces the browser without one: it asks jsDelivr for the same listing the
page asks for, falls back to the same GitHub tree API on the same 403, applies the same extension
filter, size gate and 400-file cap, and runs the same modules. Verified against three published
rows to the byte.

**The listing's order is the whole reason it has to ask.** Where the cap binds, a different order is
a different 400 files: reading the same repository from a clone's own tree order reported
facebook/react at 4,792 KB against the page's 257 KB, and the clone was not the one that was wrong
— it was answering a different question. A re-measurement that does not take the page's listing is
not a re-measurement of the page.

**c. Test the PUBLISHED page, not the local one.** A browser tab left open all afternoon holds the
script it loaded, so a local check can pass against code the deployed copy does not have. Load the
live URL with a cache-busting query and measure at least one repository through it. GitHub Pages
also caches HTML for about ten minutes, so a visitor arriving in that window sees the previous
build; that resolves itself, but do not conclude from it that the deploy failed.

**d. Push it.** The demo repository takes the same identity rules as this one.

### What every release note must contain

Not style. Each of these exists because a release went out without it and the omission cost
something.

**1. The number of checks that passed, and the platforms.** `N/N checks passed`, verbatim from the
run that gated this release. 1.22.0 shipped without it and 1.22.1 existed largely to correct that:
a page whose front matter says *"verifiable claims, not adjectives"* had dropped the one line in its
notes that is a claim rather than an adjective. Write the number the suite actually printed — not
one carried over from the previous release, which is how the README came to say "Over 1,800 checks"
long after there were 3,600.

**2. What changed, in terms of what it cost the user.** "Fixed a bug in `rulecheck`" is not a note.
"One committed rule file ended the injected block at the rules section — milestones, the session
handoff and the tools index stopped being injected, every session" is, because a reader can tell
whether it affected them.

**3. A measurement for anything described as faster, smaller or cheaper**, with the method. This
project has been wrong about its own performance more than once by reading a profiler instead of a
clock, and a number with no method behind it is the kind that survives into three more releases.

**4. Nothing described as a functional change that is documentation only.** Already stated in the
version table above; repeated here because notes are written last, when the temptation is highest.

### What a note should NOT carry

A correction is worth recording when it fixes something a PREVIOUS RELEASE shipped: the reader saw
the old behaviour, and the note explains why it changed. A mistake made and fixed inside one
unreleased working session is not that — nobody saw the wrong version, so writing "this was first
measured at X, which was wrong" reads as the author changing their mind twice and makes the work
look unstable rather than careful. Publish the correct answer and the measurement behind it. The
same rule applies to `🐛` comments in the code (owner, 2026-09-07).


**8. Verify what was published.**

```bash
gh release view v{version} --json tagName,isDraft,isPrerelease,publishedAt,url
```

Expect `isDraft: false` and `isPrerelease: false`, and a `tagName` matching step 5.

## What this does not verify

Worth being straight about, so nobody reads a green suite as more than it is.

The test suite checks the plugin's own behaviour against fixtures it builds at runtime. It does not
check that the README's measured figures are still true — those came from running the tool against
a large synthetic corpus that **is not part of this repository**, so a reader cannot reproduce them
from a clone. If a change alters what the index contains, re-measure before quoting a number.

`bench/` holds the harnesses used for that measurement. They are tracked so the method is
inspectable, not because their results can be regenerated here.
