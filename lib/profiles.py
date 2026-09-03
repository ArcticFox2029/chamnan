"""How much context the target model can usefully take — a number, never a code path.

The third axis, and the one most easily confused with the other two. `host.os_family()` decides
which FILE OPERATIONS are legal; `host.agents()` decides WHERE the context is delivered and in
what format. Neither of those changes because the model behind the harness changed. What a model
changes is how much material is worth sending, and that is a budget.

chamnan does not call a model and never will, so it cannot detect one. A profile is therefore
CHOSEN, in `.chamnan/config.json`, not sniffed. Everything here is inert until someone names it.

**Bigger is not automatically better, and the measurement that says so is not hypothetical.** In
the repository chamnan was generalised out of, injecting a whole 228,262-character knowledge file
into every prompt was replaced by retrieving ~2,000 tokens of it: the short prompt was faster AND
answered with real specifics where the long one produced filler. A million-token window is
permission to send more, not an instruction to. `large-window` below is therefore about three
times `standard` rather than a hundred times, and that ratio is a judgement stated openly rather
than a limit anyone has measured on this corpus.

**What is deliberately NOT here: `output_byte_ceiling`.** That is the host truncating a hook's
stdout at roughly 10,000 bytes — a property of the HARNESS, not of the model behind it. Putting it
in a model profile would mean choosing a Gemini profile silently raised a ceiling Claude Code's
host still enforces, and the block would be cut with no explanation. It stays on the agent adapter
where it belongs.
"""

# Each profile: the two budgets, and the model class the numbers were chosen for. Names are
# descriptive of the WINDOW, not of a vendor -- a vendor ships several sizes, and a profile named
# after one dates the moment that vendor releases another.
PROFILES = {
    "small-window": {
        "index_token_budget": 1200,
        "state_token_budget": 700,
        "window": (0, 64_000),
        "for": "anything with roughly 8K-64K of room -- a 7B on Ollama, and equally a hosted "
               "model on a small-context tier",
        "why": ("A small window spends itself on the answer, not the briefing, and is the most "
                "sensitive of the three to noise. The index is cut to a directory roll-up early "
                "rather than late."),
    },
    "standard": {
        "index_token_budget": 3000,
        "state_token_budget": 1700,
        "window": (64_000, 400_000),
        "for": "roughly 100K-400K of room; the default, and what every measurement in this "
               "repository was taken against",
        "why": ("Unchanged from what chamnan has always shipped. A profile that moved the default "
                "would silently reinterpret every number in the CHANGELOG."),
    },
    "large-window": {
        "index_token_budget": 8000,
        "state_token_budget": 4000,
        "window": (400_000, None),
        "for": "400K and up; monorepo-scale analysis",
        "why": ("Roughly 3x, not 100x. The window is large; attention across it is not uniform, "
                "and the one measurement this project has on the question found a shorter brief "
                "beat a longer one on both speed and specificity."),
    },
}

DEFAULT = "standard"


def names():
    """Profile names, in ascending order of how much they send."""
    return ["small-window", "standard", "large-window"]


_BUDGET_KEYS = ("index_token_budget", "state_token_budget")


def budgets(name):
    """The two budgets for `name`, or the default's when the name is unknown.

    Only the numbers. The prose beside them in PROFILES is for `explain()` -- returning it here
    once meant `resolve()` handed its caller a dict carrying `for` and `why` alongside two budgets,
    which is the shape of a config value nobody can safely pass on.

    Unknown falls back rather than raising: this is read from a config file a human edits, a typo
    in it must not cost the session its whole context block, and `explain()` is what says so.
    """
    spec = PROFILES.get(name, PROFILES[DEFAULT])
    return {k: spec[k] for k in _BUDGET_KEYS}


def by_window(tokens):
    """The profile name for a context window of `tokens`, which is the question users can answer.

    Vendor names date and mislead: Qwen ships an 8K local build and a long-context hosted one under
    the same name, and picking a profile from the word "Qwen" gets one of them wrong. Nobody has to
    know a vendor to know roughly how much room they have.
    """
    try:
        n = int(tokens)
    except (TypeError, ValueError):
        return DEFAULT
    for name in names():
        low, high = PROFILES[name]["window"]
        if n >= low and (high is None or n < high):
            return name
    return DEFAULT


def explain(name):
    """One line a caller can print: what was chosen, and whether the name was recognised."""
    if name in PROFILES:
        p = PROFILES[name]
        return (f"context profile `{name}` — {p['for']} "
                f"(index {p['index_token_budget']}, state {p['state_token_budget']} tokens)")
    return (f"context profile `{name}` is not one of {', '.join(names())} — "
            f"falling back to `{DEFAULT}`")


def resolve(config):
    """`(name, budgets)` from a loaded config dict.

    An explicit `index_token_budget` in the config WINS over the profile, and does so silently by
    design: someone who tuned a number by hand has measured something on their own repository, and
    a profile added later must not quietly undo it.
    """
    name = str(config.get("context_profile", DEFAULT))
    chosen = budgets(name)
    for key in ("index_token_budget", "state_token_budget"):
        if key in config:
            chosen[key] = config[key]
    return name, chosen


# ---------------------------------------------------------------------------------------------
# A convenience, and it is dated on purpose. `by_window()` above is the authority; this table only
# saves someone looking up a number they may not have to hand. Snapshot taken 2026-09-03 from each
# family's published context window. Vendors ship several sizes under one family name and the
# numbers move, so a wrong entry here must be cheap: it selects a budget, never a code path, and
# `--window` overrides it.
#
# AMBIGUOUS is the honest half of the table. Qwen is the case that forced it -- the same family
# name covers an 8K-class build people run on Ollama and a long-context hosted one, and the two
# want opposite profiles. Guessing between them silently is worse than saying which two.
MODEL_WINDOWS = {
    "claude": 1_000_000,
    "gpt": 400_000,
    "openai": 400_000,
    "gemini": 1_000_000,
    "kimi": 2_000_000,
    "grok": 256_000,
    "deepseek": 128_000,
    "glm": 200_000,
    "llama": 128_000,
    "gemma": 128_000,
    "mistral": 128_000,
    "codestral": 32_000,
}

AMBIGUOUS = {
    # family: (what the small deployment looks like, what the large one looks like)
    "qwen": ("a 7B-14B build served locally, around 32K",
             "the hosted long-context build, around 256K"),
}


def by_model(family):
    """`(profile_name, note)` for a model family name. The note is empty when it was unambiguous.

    Case- and separator-insensitive on the first word, so "Qwen3-Coder", "qwen 3" and "QWEN" all
    reach the same entry. Never raises: an unknown family returns the default and a note saying so,
    because this is a convenience and the number is what actually decides.
    """
    # 🐛 The first token alone was not the family: "Qwen3-Coder" normalised to `qwen3`, which is
    # in neither table, so the one family the AMBIGUOUS list exists for fell through to the
    # unknown branch. A version number is part of how people write these names -- gpt-5, llama-3,
    # gemma-3, kimi-k2 -- so the trailing digits come off after the first token is taken.
    text = str(family).strip().lower().replace("_", "-")
    if not text:
        return DEFAULT, (f"no model family given. Using `{DEFAULT}` — pass --window to be exact.")
    key = text.split("-")[0].split()[0].rstrip("0123456789.")
    if key in AMBIGUOUS:
        small, large = AMBIGUOUS[key]
        return DEFAULT, (f"`{family}` ships in two sizes that want different profiles: {small} "
                         f"and {large}. Using `{DEFAULT}` — pass --window with the number your "
                         f"deployment actually has.")
    if key in MODEL_WINDOWS:
        return by_window(MODEL_WINDOWS[key]), ""
    return DEFAULT, (f"`{family}` is not in the model table, which is a dated convenience rather "
                     f"than an authority. Using `{DEFAULT}` — pass --window to be exact.")
