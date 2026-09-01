<!--
  Reference template for a chamnan GitHub Release.

  GitHub does not apply this automatically — there is no such mechanism for releases. Copy it,
  fill it in, and pass it with `gh release create ... --notes-file`, or paste it into the release
  form.

  Delete any section that has nothing to say. An empty "Breaking changes" heading reads as an
  oversight; its absence reads as "there were none", which is what you mean.

  Replace every {PLACEHOLDER}. Nothing below is a real value.
-->

## Install

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

Already installed:

```bash
claude plugin update chamnan@chamnan
```

Claude Code applies an update on restart, not in the running session.

<!--
  BEFORE PUBLISHING: the translated pages under docs/i18n/ carry no numbers, deliberately, so a
  release does not make them stale (arXiv:2508.02497 — a merged translation gets a median of 0
  follow-up commits while the English source gets 8.5). So the ordinary release touches README.md
  and nothing else. Update docs/i18n/ ONLY when the install command changes, when what chamnan IS
  changes, or when a reader needs to know a new limitation BEFORE installing. Thai first, then the
  rest. See docs/i18n/MAINTAINING.md.
-->

## What's new

<!--
  Two lists, kept apart on purpose. Documentation work is not a runtime change, and describing it
  as one is the fastest way to lose a reader's trust in the rest of the notes.
-->

### Functional changes

- **{CHANGE}.** {What behaved one way and now behaves another. Where it was wrong before, say so
  concretely — "31 files produced 34 symbols where 254 were correct" tells a reader more than
  "improved extraction".}

State plainly whether configuration or command syntax changed. If neither did, say that:
`No configuration option and no command syntax changed.`

### Documentation

- {What a reader can now find that they could not before, or what was corrected.}

Do not list documentation under functional changes.

## Breaking changes

<!-- Delete this whole section if there are none. -->

- **{WHAT BREAKS}.** {Who is affected, what they will see, and the exact step to take.}

Anything that changes a config key's name or meaning, removes a command or flag, or alters the
shape of a generated file belongs here.

## Security notes

<!--
  Only real changes to what chamnan reads, writes, redacts or refuses to open.

  Keep the wording no stronger than the README's. chamnan defends its own output; it is not a
  sandbox and cannot filter what the Read tool returns. See docs/data-flow.md.
-->

- **{CHANGE}.** {What is now redacted, refused or reported that was not before — or the reverse.}

If nothing changed here, delete the section rather than writing "no security changes", which
invites the question of whether anyone looked.

## Verification

```
{N}/{N} checks passed
```

```bash
git clone https://github.com/ArcticFox2029/chamnan
cd chamnan
python3 tests/run_tests.py
```

- Tag: `chamnan--v{VERSION}` — the convention `claude plugin tag` produces
- Commit: `{FULL_SHA}`
- `.claude-plugin/plugin.json` reports `{VERSION}`

See [docs/verification.md](../docs/verification.md) for the full pre-release checklist.

<!--
  Figures quoted anywhere in these notes should be measured, and labelled as measured, observed or
  estimated. An estimate presented as a benchmark is worse than no number at all.
-->
