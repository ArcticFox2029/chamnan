# Verification

What to run before tagging a release, and what a good result looks like.

Everything here works from a clean clone. There is nothing to install and no credentials involved.

## The test suite

```bash
python3 tests/run_tests.py
```

Expected output:

```
220/220 checks passed
```

Exit status `0`. The count changes as checks are added — what matters is that both numbers match.

A failure prints each failed check by name before the total, and exits `1`:

```
  FAIL  <name of the check>

219/220 checks passed
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

**3. The commit is in, and pushed.**

Tag after the push, not before, so the tag never points at a commit no one else can fetch.

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

**7. Publish the release from the tag that already exists.**

```bash
gh release create chamnan--v{version} --verify-tag --notes-file <your-notes> --latest
```

`--verify-tag` makes the command fail rather than invent a tag if the name is wrong — which is the
behaviour you want when the tag name is the thing most likely to be mistyped.

`.github/release-template.md` is a starting point for the notes.

**8. Verify what was published.**

```bash
gh release view chamnan--v{version} --json tagName,isDraft,isPrerelease,publishedAt,url
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
