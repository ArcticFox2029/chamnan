# chamnan for VS Code

Installs and updates [chamnan](https://github.com/ArcticFox2029/chamnan) in the open repository,
from a command instead of three typed into a chat window.

**It is a channel, not a feature.** Everything it does is a `bin/chamnan-*` invocation — the same
commands the CLI has. Nothing works only when this extension is installed, by design: a capability
that existed here and not in the CLI would mean chamnan had become two products.

## Commands

| command | what it runs |
|---|---|
| `chamnan: what is installed on this machine` | `chamnan-setup` |
| `chamnan: install or update in this workspace` | `chamnan-setup --dry-run` |
| `chamnan: show the block this repository injects` | `chamnan-context` |

## What it never does

No network call of any kind — no telemetry, no update check, no marketplace fetch at runtime. There
is exactly one process-spawning call in the whole extension and a test asserts that, because the
claim is the product.

It never writes to `.chamnan/memory/`, `state/`, `skills/`, `sessions/`, `logs/` or `candidates/`.
Those are yours.

## Requirements

A `python3` on PATH, and a chamnan checkout. The extension uses the one it ships beside; set
`chamnan.checkoutPath` to point somewhere else.
