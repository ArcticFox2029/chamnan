"""Which operating system, and which coding agent — detection ONLY, no behaviour.

This module answers two questions and does nothing with the answers. That separation is the
point: the moment detection also decides what to WRITE, one agent's quirk starts leaking into
another's path, and the bug is somewhere in a function that was supposed to be about neither.

**Several agents coexist on one machine, and that is the normal case rather than an edge one.**
The machine this was written on carries `~/.claude`, `~/.gemini` and `~/.kiro` side by side, with
Claude Code the one actually running. So `agents()` returns a LIST, ordered by how strong the
evidence is, and never collapses to a single winner — a caller that wants one asks for `primary()`
and gets told what that was based on.

Evidence comes in three strengths, and they are not interchangeable:

  RUNNING   an environment variable set by the agent's own process. Only this proves which agent
            is executing right now. Verified by measurement for Claude Code (`CLAUDECODE`,
            `CLAUDE_CODE_ENTRYPOINT`); NOT verified for any other agent, so nothing else claims it.
  REPO      a file or directory in the repository that the agent reads. Proves the repository is
            set up for that agent, not that it is running.
  HOME      a config directory under the user's home. Proves configuration was found for that
            agent at some point, not that it is installed or runnable now — a home directory
            outlives an uninstall. The weakest of the three and the easiest to be stale.

Anything unverified is recorded as the convention it is, not asserted as fact. Where a signal
could not be measured on a real installation, the comment beside it says so.
"""
import os
import platform
from pathlib import Path

RUNNING, REPO, HOME = "running", "repo", "home"

# Ranked, strongest first. Ties inside a strength keep this order.
_STRENGTH = (RUNNING, REPO, HOME)


def os_family():
    """"windows", "macos", "linux", or "unknown".

    `platform.system()` rather than `sys.platform`, because `sys.platform` reports "linux" for
    every Linux and "darwin" for macOS but says nothing useful for the BSDs, and a family name is
    what callers branch on. WSL reports "Linux" and is treated as Linux on purpose: a WSL checkout
    behaves like a Linux one for every path, permission and line-ending question chamnan asks.
    """
    name = platform.system().lower()
    if name == "darwin":
        return "macos"
    if name == "windows":
        return "windows"
    if name == "linux":
        return "linux"
    return "unknown"


def is_windows():
    """Windows needs a different answer often enough to be worth its own predicate."""
    return os_family() == "windows"


# Each agent: the env vars that prove it is RUNNING, the repository markers, the home markers.
# A marker ending in "/" must be a directory; anything else must exist as a file or directory.
_AGENTS = {
    "claude": {
        # Measured on a live Claude Code session: both are set. `CLAUDECODE` is the one that has
        # been stable across versions; the entrypoint variable is kept as a second signal.
        "env": ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT"),
        "repo": ("CLAUDE.md", ".claude/"),
        "home": (".claude/",),
    },
    "cursor": {
        # 🎯 [2026-09-08] The comment here used to say no claim was made about an environment
        # variable "it may or may not set", because Cursor was not installed on the machine this
        # was written on. Cursor's own terminal documentation names one: `CURSOR_AGENT`, offered
        # for exactly this purpose -- "use the CURSOR_AGENT environment variable in your shell
        # config to detect when Cursor is running". Fetched from the vendor's page rather than
        # taken from a search summary, which this project has already been caught doing once.
        #
        # It is RUNNING-tier evidence, which is the strongest kind here and the kind only two of
        # twenty-three agents had: a file marker says somebody once used this agent in this
        # repository, an env var says it is the process asking right now (R2 acc3, 2026-09-08 adapters).
        # `.cursor/rules/` is the current file convention and `.cursorrules` the legacy one.
        "env": ("CURSOR_AGENT",),
        "repo": (".cursor/", ".cursorrules"),
        "home": (".cursor/",),
    },
    "gemini": {
        "env": (),
        "repo": ("GEMINI.md", ".gemini/"),
        "home": (".gemini/",),
    },
    "kiro": {
        # `~/.kiro/steering/` was observed on a real installation; the repository-level convention
        # is `.kiro/steering/*.md`, which is what the adapter writes.
        "env": (),
        "repo": (".kiro/",),
        "home": (".kiro/",),
    },
    # 🐛 Five agents were detected while twenty-three had adapters, so `--detect` reported "nothing
    # found" on a repository plainly set up for Roo, Windsurf or Copilot. The entries below are
    # REPO markers only — a directory the agent itself created, which is evidence rather than a
    # guess — and deliberately no HOME markers: this module's own docstring calls HOME the weakest
    # and stalest signal, and a machine carrying six agents' config directories would then report
    # six agents for every repository.
    #
    # Detection still writes nothing. Its only consumers are `--detect` and a printed suggestion.
    # Hermes reads project instructions from the repository, so `.hermes.md` and `HERMES.md` are
    # the signals. `~/.hermes/` is deliberately NOT one: this file's own rule is that HOME is the
    # weakest and stalest marker there is, and somebody who installed Hermes once would otherwise
    # have every repository on the machine reported as a Hermes repository forever.
    "hermes": {"env": ("HERMES_HOME",), "repo": (".hermes.md", "HERMES.md"), "home": ()},
    "windsurf": {"env": (), "repo": (".windsurf/",), "home": ()},
    "roo": {"env": (), "repo": (".roo/",), "home": ()},
    "cline": {"env": (), "repo": (".clinerules",), "home": ()},
    "continue": {"env": (), "repo": (".continue/",), "home": ()},
    "copilot": {"env": (), "repo": (".github/copilot-instructions.md",
                                    ".github/instructions/"), "home": ()},
    "amazonq": {"env": (), "repo": (".amazonq/",), "home": ()},
    "augment": {"env": (), "repo": (".augment/", ".augment-guidelines"), "home": ()},
    "trae": {"env": (), "repo": (".trae/",), "home": ()},
    "junie": {"env": (), "repo": (".junie/",), "home": ()},
    "goose": {"env": (), "repo": (".goosehints",), "home": ()},
    "grok": {"env": (), "repo": (".grok/",), "home": ()},
    "antigravity": {"env": (), "repo": (".agents/",), "home": ()},
    "zed": {"env": (), "repo": (".rules",), "home": ()},
    "replit": {"env": (), "repo": ("replit.md",), "home": ()},
    "qwen": {"env": (), "repo": ("QWEN.md",), "home": ()},
    "iflow": {"env": (), "repo": ("IFLOW.md",), "home": ()},
    "codebuddy": {"env": (), "repo": ("CODEBUDDY.md",), "home": ()},
    # No `mistral` row, and its old one was wrong twice over: `.vibe/` is Vibe's HOME directory
    # (`_DEFAULT_VIBE_HOME = Path.home()/".vibe"` in the vendor's source), so a `.vibe/` inside a
    # repository marks nothing -- and Vibe reads the root AGENTS.md, which makes `mistral` an alias
    # of `generic` and detected the way every other AGENTS.md reader is: by that file.
    "aider": {"env": (), "repo": (".aider.conf.yml", "CONVENTIONS.md"), "home": ()},
    "generic": {
        # `AGENTS.md` is the cross-tool convention several agents now read, and it is what an agent
        # with no adapter of its own gets. Never detected from home: it is a repository convention,
        # and there is no installation to find.
        "env": (),
        "repo": ("AGENTS.md",),
        "home": (),
    },
}

# The order a tie is broken in, and the order `agents()` lists equal-strength matches in.
# Most specific first, with `generic` last: `AGENTS.md` is read by eleven agents, so finding it
# says less than finding a directory only one of them creates. A tie inside a strength is broken
# by this order.
ORDER = ("claude", "cursor", "gemini", "kiro", "windsurf", "roo", "cline", "continue", "copilot",
         "amazonq", "augment", "trae", "junie", "goose", "grok", "antigravity", "zed", "replit",
         "qwen", "iflow", "codebuddy", "aider", "hermes", "generic")


def _marker_present(base, marker):
    """Is this agent's marker here, whatever case the repository wrote it in?

    🐛 [2026-09-09] This asked `Path.exists()` for the exact string, and on a case-sensitive
    filesystem `AGENTS.md` and `agents.md` are two different files. `lib/adapters/generic.py`
    already carries a tested guard for precisely that — `_warn_about_a_differently_cased_sibling`,
    added by an earlier round — and the function whose whole job is "read markers off disk and
    report what is there" did not. Reproduced on a case-sensitive APFS volume: a repository whose
    file is `agents.md` reported no agent at all, so `--detect` and `primary()` both answered as
    though nothing was set up. One of a pair guarded and the identical one beside it left
    (R1 agent 1).

    The directory scan runs only when the exact name misses, so the ordinary case still costs one
    stat, and a directory that cannot be listed falls back to the answer this always gave.
    """
    if not base:
        return False
    name = marker.rstrip("/")
    path = Path(base) / name
    try:
        if path.is_dir() if marker.endswith("/") else path.exists():
            return True
    except OSError:
        return False
    try:
        import mdblock
        # `mdblock.filesystem_key`, not `.lower()`: the fold a filesystem actually applies is NFC
        # then casefold, and `.lower()` is neither. The suite refuses a bare `.lower()` name
        # comparison by name, and it is right to — `memory.case_collisions` and `adapters.generic`
        # once disagreed about the same pair for exactly this reason, five files apart.
        parent = path.parent
        want = mdblock.filesystem_key(name.rsplit("/", 1)[-1])
        for entry in parent.iterdir():
            if mdblock.filesystem_key(entry.name) != want:
                continue
            return entry.is_dir() if marker.endswith("/") else True
    except (OSError, ImportError):
        pass
    return False


def agents(root=None, env=None, home=None):
    """Every agent this repository or machine shows evidence of, strongest evidence first.

    Returns a list of `(name, strength)`. Empty when nothing is found, which is a real answer:
    a repository nobody has set up for any agent should get the generic treatment by choice, not
    by a detector guessing.

    `env`, `root` and `home` are injectable so a test can describe a machine it is not running on
    -- a Windows layout, a Cursor install -- without needing that machine.
    """
    env = os.environ if env is None else env
    # 🐛 Unguarded, and reachable from every `chamnan-context` run. `Path.home()` raises when
    # neither $HOME nor a passwd entry resolves — a container, a daemon, a stripped environment —
    # and detection is a convenience that must never be the reason a command fails (R20 agent 1).
    if home is None:
        try:
            home = Path.home()
        except (RuntimeError, OSError):
            home = None
    else:
        home = Path(home)
    root = None if root is None else Path(root)

    found = {}
    for name in ORDER:
        spec = _AGENTS[name]
        if any(env.get(v) for v in spec["env"]):
            found[name] = RUNNING
        elif any(_marker_present(root, m) for m in spec["repo"]):
            found[name] = REPO
        elif any(_marker_present(home, m) for m in spec["home"]):
            found[name] = HOME
    return sorted(found.items(),
                  key=lambda kv: (_STRENGTH.index(kv[1]), ORDER.index(kv[0])))


def primary(root=None, env=None, home=None):
    """The one agent to act as, and the strength that decision rests on: `(name, strength)`.

    `("generic", "")` when nothing was found -- a repository with no agent set up is not an error,
    and the generic adapter is a correct answer for it.
    """
    ranked = agents(root=root, env=env, home=home)
    return ranked[0] if ranked else ("generic", "")


# The context files that sit BESIDE chamnan's block and are loaded whole on every session.
#
# 🎯 [2026-09-07] chamnan budgets itself to the byte -- `output_byte_ceiling` is 9,000 and
# `fit.shrink` enforces it section by section -- and said nothing at all about the file next to it.
# Measured on this repository the day this was written: chamnan's block 8,925 bytes against its own
# ceiling, `CLAUDE.md` 17,116 bytes with no budget of any kind. Nearly twice the size, same context,
# never mentioned. A tool whose whole argument is context economy should not have a blind spot
# shaped exactly like its own subject (R5 acc3, 2026-09-07 new_ideas #2).
#
# Derived from `_AGENTS` rather than listing `CLAUDE.md`, because the same blind spot exists for
# every other vendor's file and a hardcoded name would cover one of twenty-four.
# Directories that hold payload or somebody else's code rather than this repository's own source.
# A context file inside one of these is not loaded for a session working on this repository, and
# counting it would inflate the very figure this exists to state honestly.
_NOT_SOURCE = frozenset({
    ".git", ".chamnan", "node_modules", "vendor", "venv", ".venv", "dist", "build",
    "target", "__pycache__", ".tox", "site-packages", "third_party", "fixtures",
})


def context_files(root):
    """Every agent context FILE present in `root`, as [(path, bytes)], largest first.

    Directory markers are skipped: `.claude/` is a directory of configuration, not a file loaded
    into the prompt, and counting it would answer a different question.
    """
    root = Path(root)
    seen, out = set(), []
    for spec in _AGENTS.values():
        for marker in spec.get("repo", ()):
            if marker.endswith("/") or marker in seen:
                continue
            seen.add(marker)
            f = root / marker
            try:
                if f.is_file():
                    out.append((marker, f.stat().st_size))
            except OSError:
                continue
    # 🐛 [2026-09-09] Only `root / marker` was checked, so a context file one directory down was
    # invisible. Claude Code loads a nested `CLAUDE.md` the moment a session opens any file under
    # its directory, and the repository this was written in has one: the report showed 17,116 bytes
    # of un-budgeted context beside the block while the real floor for a session working in the
    # application directory is 28,168. The caller's own comment calls this class of gap "a blind
    # spot shaped like its own subject" — and had it one directory down (R5 agent3, 2026-09-09).
    #
    # Bounded on purpose. Two levels, and only into directories that hold source rather than
    # payload: a full walk of a large repository to add a line to a report is a cost the report
    # does not justify, and the deep case is a monorepo package, not a build directory.
    for marker in sorted(seen):
        if "/" in marker:
            continue          # already a path; walking it again would double-count
        for f in sorted(root.glob(f"*/{marker}")) + sorted(root.glob(f"*/*/{marker}")):
            try:
                if not f.is_file():
                    continue
                rel = f.relative_to(root).as_posix()
                if any(part in _NOT_SOURCE for part in f.relative_to(root).parts[:-1]):
                    continue
                out.append((rel, f.stat().st_size))
            except (OSError, ValueError):
                continue
    return sorted(out, key=lambda r: -r[1])
