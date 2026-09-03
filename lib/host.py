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
  HOME      a config directory under the user's home. Proves the agent is installed on this
            machine, which is the weakest of the three and the easiest to be stale.

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
        # NOT measured: Cursor was not installed on the machine this was written on, so no claim is
        # made about an environment variable it may or may not set. File markers only, which is the
        # honest limit of what is known -- `.cursor/rules/` is the current convention and
        # `.cursorrules` the legacy single-file one.
        "env": (),
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
    "mistral": {"env": (), "repo": (".vibe/",), "home": ()},
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
         "qwen", "iflow", "codebuddy", "mistral", "aider", "generic")


def _marker_present(base, marker):
    if not base:
        return False
    path = Path(base) / marker.rstrip("/")
    try:
        return path.is_dir() if marker.endswith("/") else path.exists()
    except OSError:
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
    home = Path.home() if home is None else Path(home)
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
