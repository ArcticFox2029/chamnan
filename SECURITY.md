# Security

## Reporting a vulnerability

**Use [private vulnerability reporting](https://github.com/ArcticFox2029/chamnan/security/advisories/new).**
It is enabled on this repository. Please do not open a public issue for anything that could expose
someone's credentials before there is a fix.

You will get a first response within a week. If the report is confirmed, the fix ships in the next
release with the finding described in the release notes — this project publishes what went wrong,
including its own mistakes, rather than quietly patching them.

## Supported versions

**The latest release only.** Releases are frequent and each one is a superset of the last; there are
no long-term support branches and no backports. Upgrade with `claude plugin update chamnan`.

## What chamnan can actually do to you

Worth stating plainly, because "an installed plugin" is a large permission and most of the surface
people worry about is not present here.

| | |
|---|---|
| **Network** | None. chamnan makes no network call at runtime, holds no API key, and has no telemetry. There is nothing for it to send anything to. |
| **Third-party code** | None. Python standard library only, enforced by the test suite. There is no dependency tree to compromise. |
| **Background execution** | None. No daemon, no server, no scheduled job. It runs only when a hook fires or you type a command. |
| **Writes** | Everything it writes goes inside `.chamnan/`, as plain markdown and JSON you can read and delete. The single exception is an optional Git pre-commit hook, installed only if you say yes. |
| **Your source** | Read, never rewritten. The index copies comments you already wrote rather than generating them. |
| **Reads outside the repository** | `chamnan-report` reads Claude Code's own transcript directory to count tokens. Nothing else leaves the repository, and nothing outside it is written. |

The chain that would have to complete for a repository's secrets to reach someone else — read,
stage, exfiltrate — is described in the README under
[what an installed plugin can do to you](README.md#9-what-an-installed-plugin-can-do-to-you-and-what-this-one-cannot),
along with the link chamnan breaks.

## The redactor, and the ceiling it does not reach

Everything chamnan is about to write or inject passes a credential filter first. Measured against a
labelled corpus of 38 secret shapes and 22 ordinary strings that must survive:

**97.4% recall (37 of 38) · 100% precision.**

That is not 100% recall, and the missed shape is named in the README rather than hidden. Two limits
follow from it, and both are worth knowing before you point this at a private repository:

- **A secret written as prose is not caught.** The filter strips assignments and known token
  shapes. A comment that reads *"the console password is Tr0ub4dor-2026"* is a sentence, and it
  will reach `MAP.md` — which the optional pre-commit hook then commits. If your repository keeps
  credentials in prose, review `.chamnan/MAP.md` before its first commit.
- **A shape nobody has seen is not in the table.** New vendors invent new token formats. If you
  find one that gets through, that is exactly the report this file is asking for.

`.chamnan/` is committed beside your code on purpose, which means anything that does get through is
visible in a diff rather than hidden in a database. That is the trade this design makes.

## What is not a vulnerability here

- **chamnan reporting a file, a table, or an environment variable name.** Names are the product;
  values are never recorded. If you find a *value* in anything chamnan wrote, that is a
  vulnerability and this file is asking for it.
- **A prompt-injection payload appearing inside the injected block.** chamnan fences repository
  text and attributes it rather than claiming to neutralise it — the reasoning, and the measured
  ceiling for delimiting as a defence, are in the README under
  [prompt injection](README.md#9b-prompt-injection). A payload that escapes the fence, or that the
  fence fails to attribute, is a vulnerability.
- **A finding that requires an attacker who can already write to your repository and run your
  Claude Code session.** At that point chamnan is not the weakest link.
