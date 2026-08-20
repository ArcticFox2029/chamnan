# Architecture

How chamnan is put together, and what actually moves between the parts.

```mermaid
flowchart TD
    REPO["Your repository<br/><i>source files, schemas, manifests</i>"]

    SCAN["chamnan scanner<br/><code>bin/chamnan-map</code> → <code>lib/mapper.py</code>"]

    subgraph WS[".chamnan/ — written into your repository"]
        MAP["<b>MAP.md</b><br/>architecture index"]
        STATE["<b>STATE.md</b><br/>work in flight"]
        PROC["<b>skills/</b><br/>procedures you kept"]
        TOOLS["<b>tools/</b><br/>scripts you promoted"]
    end

    HOOK["session-start hook<br/><code>hooks/session_start.py</code>"]
    CLAUDE["Claude Code session"]

    REPO -- "read only" --> SCAN
    SCAN -- "writes" --> MAP

    CLAUDE -. "writes at milestones" .-> STATE
    CLAUDE -. "/chamnan:capture" .-> PROC
    CLAUDE -. "chamnan-promote" .-> TOOLS

    MAP --> HOOK
    STATE --> HOOK
    PROC --> HOOK
    TOOLS --> HOOK

    HOOK -- "injected at session start" --> CLAUDE

    PEEK["chamnan-peek<br/><i>on demand, one file</i>"]
    REPO -- "read only" --> PEEK
    PEEK -. "printed into the session" .-> CLAUDE
```

Solid arrows are what chamnan does. Dotted arrows are things that happen because you or Claude
asked for them.

## What runs locally

All of it. chamnan is Python scripts on your machine, run by Claude Code as hooks and by you as
shell commands. There is no service to sign up for, no daemon, and no account.

It uses the Python standard library and nothing else — no third-party packages at install time or
run time. It makes no network calls of its own, and it never invokes `git`. The one exception to
"nothing outside `.chamnan/`" is opt-in: `chamnan-map --install-git-hook` writes a `pre-commit`
hook, and only when you ask for it.

There is no vector database, no embedding model, and no index server. The map is a Markdown file,
and finding something in it is `grep`.

## What is generated

Everything chamnan produces lives in one directory at the root of the repository it is pointed at:

| | written by | when |
|---|---|---|
| `.chamnan/MAP.md` | `chamnan-map` | every index run — rewritten in full |
| `.chamnan/config.json` | `lib/workspace.py` | first run; merged, not replaced, on upgrade |
| `.chamnan/STATE.md` | **Claude, not a script** | at milestones, when there is something worth carrying forward |
| `.chamnan/skills/` | `/chamnan:capture` | when you decide a procedure is worth keeping |
| `.chamnan/tools/` | `chamnan-promote` | when a scratch script has earned a permanent place |
| `.chamnan/logs/` | the commands themselves | pruned on every run, per `log_retention_days` |

`MAP.md` has two halves and the split is the point. Above `## Full Detail` is the Quick Index —
one line per file, plus a section each for the data model, API surface, configuration, deployment
and stored files, and only for the ones the repository actually has. Below it is the per-file
detail, which is meant to be grepped for a single heading and never read whole.

Whatever the scanner is about to write passes through `lib/redact.py` first. That is one choke
point on the finished document rather than one per section, so a section added later cannot slip
past it.

## What Claude consumes

At the start of every session in that repository, `hooks/session_start.py` assembles one block and
hands it over:

- the **Quick Index** from `MAP.md` — capped by `index_token_budget`, and folded down by directory
  rather than truncated when it does not fit, so no part of the repository disappears silently
- **`STATE.md`**, if it exists
- the **names and descriptions** of anything in `skills/` and `tools/` — not their contents, so the
  agent knows what is available and loads one only when it needs it
- a reply-style instruction, only if `reply_style` is set to something other than `off`

Each of those four parts can be switched off independently in `.chamnan/config.json`.

The Full Detail half of `MAP.md` is **never** injected. Neither is the source. `chamnan-peek` is
separate from all of this: it reads one file's shape when a task genuinely needs it, and only when
it is invoked.

## What chamnan does not do

Worth stating plainly, because an indexing tool sitting between a repository and a model invites
assumptions:

- It does not send your code anywhere. It has no network path of its own.
- It does not filter what Claude reads. A plugin hook cannot rewrite what the `Read` tool returns,
  so if you ask Claude to open a file, it opens it — chamnan is not in that path and is not a
  sandbox. See [data-flow.md](data-flow.md) for where that boundary actually falls.
- It does not modify your source. The scanner opens files read-only. The one thing that can edit
  source is the `commenter` agent, which runs only after you say yes to it during
  `/chamnan:bootstrap`.
