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

**What the 3x buys on Claude Code's own hook, measured rather than assumed.** (R10) reported
that the ceiling makes the delivered block "byte-for-byte identical regardless of profile" and
that `large-window` is therefore dead code on chamnan's flagship integration. Reproduced against
the real hook on four fixtures -- 120, 400 and 1,200 files, and 1,200 files with a five-times
larger STATE.md -- and it is NOT identical at any size:

    120 files    standard 6,781 bytes    large-window 8,957 bytes
    400 files    standard 7,127 bytes    large-window 8,960 bytes
    1,200 files  standard 7,142 bytes    large-window 8,836 bytes
    1,200 + 5x STATE.md   7,143 bytes                 8,931 bytes

So the profile does change what Claude Code receives, and the claim to be careful with is a
different one: a 2.4-2.7x increase in the two TOKEN budgets buys roughly 25% more delivered BYTES,
because `fit.CEILING` caps both profiles near the same number. That is the honest shape -- the
budgets are caps on two sections, the ceiling is a cap on the whole block, and a bigger cap on a
part cannot lift a smaller cap on the sum. `--explain` already says this in the reader's own
numbers ("the byte ceiling binds first"); it is written here so the next round does not re-open a
question that has been measured.
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

    A HAND-TUNED `index_token_budget` in the config WINS over the profile, and does so silently by
    design: someone who set a number themselves has measured something on their own repository, and
    a profile added later must not quietly undo it.

    🐛 [2026-09-06] "Explicit" used to mean `key in config`, and `load_config()` merges DEFAULT_CONFIG
    into every config it returns — so both budget keys are ALWAYS present and the profile could
    never move either of them. Choosing `large-window` in the file did nothing at all. The one path
    that worked, the environment variable, worked only because its caller popped the two keys first,
    which is the same fix spelled at one call site instead of here where the precedence lives
    (R8 agent 4, 2026-09-06).
    #
    A value still equal to its own default was not tuned by anybody, so it does not outrank a
    profile the user chose. A value they changed still does.
    """
    name = str(config.get("context_profile", DEFAULT))
    chosen = budgets(name)
    for key in ("index_token_budget", "state_token_budget"):
        if key in config and config[key] != _default_for(key):
            chosen[key] = config[key]
    return name, chosen


def _default_for(key):
    """The shipped default for `key`, or a sentinel that equals nothing when it cannot be read.

    Imported here rather than at module scope: `workspace` is the module everything else loads, and
    a cycle between the two would be paid at every import in the package. A missing default must
    read as "no default", so an unreadable one leaves the old behaviour rather than silently making
    every hand-tuned number stop counting.
    """
    try:
        import workspace as _ws
        return _ws.DEFAULT_CONFIG.get(key, _NO_DEFAULT)
    except Exception:                       # noqa: BLE001 — a config question must not raise
        return _NO_DEFAULT


class _NoDefault:
    """Equal to nothing, including itself, so `config[key] != _NO_DEFAULT` is always true."""

    def __eq__(self, other):
        return False

    def __ne__(self, other):
        return True

    __hash__ = None


_NO_DEFAULT = _NoDefault()


# ---------------------------------------------------------------------------------------------
# A convenience, and it is dated on purpose. `by_window()` above is the authority; this table only
# saves someone looking up a number they may not have to hand. Vendors ship several sizes under
# one family name and the numbers move, so a wrong entry here must be cheap: it selects a budget,
# never a code path, and `--window` overrides it.
#
# 🐛 [2026-09-03] "codestral" had carried its family's May-2024 launch number, 32K, through a
# January-2025 refresh that moved it to 256K -- eight months stale by the time anyone checked, and
# silently sending every codestral user's index to small-window's budget instead of standard's.
# Caught by re-deriving each entry from what is actually known about it rather than trusting the
# table was still current because nothing had touched the file. No network access was available to
# re-verify the rest of this table against live vendor docs from where this check was run; treat
# every entry below as no fresher than that limitation allows, and re-check before trusting one.
#
# AMBIGUOUS is the honest half of the table. Qwen is the case that forced it -- the same family
# name covers an 8K-class build people run on Ollama and a long-context hosted one, and the two
# want opposite profiles. Guessing between them silently is worse than saying which two.
MODEL_WINDOWS = {
    "claude": 1_000_000,
    # 🐛 This table is keyed by FAMILY, which quietly assumed a family's name is what people type.
    # Anthropic's current models are not called "Claude something" — they are Fable, Opus, Sonnet
    # and Haiku. Every one of those names fell through to `standard`, so a user on the newest
    # Claude model was told to size for a small window while running a million-token one. Found by
    # the R1 vendor check, which exists for exactly this: a table of other people's numbers goes
    # stale without anything failing.
    #
    # These four are from Anthropic's own documentation, checked 2026-09-06 (R2 agent 1, 2026-09-09). `mythos`
    # is deliberately NOT here: it is very probably 1M like its siblings, and probably is not a
    # number. It falls through to `standard` with the table's own "not in the model table, which is
    # a dated convenience rather than an authority" note, which is the honest answer.
    #
    # Haiku is the one that is NOT a million: 200K. Putting it here rather than leaving it to the
    # family entry is the difference between a right answer and a lucky one.
    "fable": 1_000_000,
    "opus": 1_000_000,
    "sonnet": 1_000_000,
    "haiku": 200_000,
    # 🐛 400,000 was GPT-4.1's number and outlived it. OpenAI's own model documentation, read
    # 2026-09-06, gives 1.05M for every current flagship — GPT-6 Astra and the three GPT-5.6
    # builds. A round earlier raised the possibility that 400,000 was deliberately matching Codex
    # CLI's practical cap rather than the API's window; that page states no Codex figure, and
    # nothing in this file ever claimed it, so the guess is not what the table was recording.
    #
    # It changes no profile today: both numbers are over the large-window boundary. Corrected
    # because a table of other people's numbers is either accurate or it is decoration, and the
    # next boundary this feeds may not sit where this one does (R3 agent 1).
    "gpt": 1_050_000,
    "openai": 1_050_000,
    "gemini": 1_000_000,
    # 🐛 [2026-09-06] Four entries checked against each vendor's OWN current documentation, not
    # against a listicle (R8 agent 1, 2026-09-06). Three were stale toward the small number and one toward the
    # large, which is what tells you they aged separately rather than all being copied from one
    # outdated source. The `kimi` direction is the one that matters: a window stated LARGER than the
    # model really has is the only error in this table that can make chamnan ship a block the model
    # cannot hold, and it was overstated by 2x.
    #
    #   kimi      2,000,000 -> 1,000,000   Moonshot's own pricing/chat docs: K3, the current
    #                                      flagship, is 1M. The 2M figure's origin was not chased
    #                                      and is not guessed at here.
    #   grok        256,000 ->   500,000   xAI's own model page: grok-4.6, the current flagship, is
    #                                      500K. 256K survives only on one narrow build.
    #   deepseek    128,000 -> 1,000,000   DeepSeek's own models table: all three current models
    #                                      share 1M, so this is not SKU ambiguity.
    #   glm         200,000 -> 1,000,000   200K was an exact match for GLM-4.6; the vendor has
    #                                      since shipped GLM-5.3 at 1M.
    #
    # `codestral` is below, and `mistral` moved out of this table on 2026-09-09 — see AMBIGUOUS.
    #
    # Two earlier rounds could not read a number out of Mistral's own page and said so rather than
    # copy a listicle, which was the right call and is why the entry sat at a stale 128,000 with a
    # comment explaining the refusal. What closes it is a different URL shape: the overview page is
    # client-rendered, the per-model cards at `docs.mistral.ai/models/model-cards/<slug>` are not.
    # Fetched 2026-09-09 from the vendor, not from this report: Mistral Medium 3.5's specifications
    # table reads "256k" (R2 agent 1, 2026-09-09).
    "kimi": 1_000_000,
    "grok": 500_000,
    "deepseek": 1_000_000,
    "glm": 1_000_000,
    # 32K was this family's window at its May-2024 launch. The January-2025 refresh moved it to
    # 256K, and the entry was never updated -- it was still 32K when this table's own comment
    # claimed a 2026-09-03 snapshot, silently sending every codestral user to small-window instead
    # of standard.
    "codestral": 256_000,
}

AMBIGUOUS = {
    # family: (what the small deployment looks like, what the large one looks like)
    "qwen": ("a 7B-14B build served locally, around 32K",
             "the hosted long-context build, around 256K"),
    # The same shape as Qwen, and for the same reason: "llama" alone no longer names one window.
    # A Llama 3.x build served locally is still the common case, at 8K-128K depending on which
    # 3.x -- and it now sits beside a Llama 4 whose headline number is 1M (Maverick) to 10M
    # (Scout). A single flat entry picked one of those silently; this says which two exist.
    "llama": ("a Llama 3.x build served locally, 8K-128K depending on version",
              "Llama 4 (Scout/Maverick), 1M and up"),
    # 🐛 [2026-09-09] Both of these were flat 128,000 entries, and both families had split since.
    # A flat number in a table whose whole value is that it was verified is a claim; when the
    # family covers two windows, the honest entry is the one that says which two.
    #
    # Gemma: checked 2026-09-06 at 128K and correct for Gemma 3, then Gemma 4 shipped. Fetched
    # 2026-09-09 from `ai.google.dev/gemma/docs/core`: "Small models feature a 128K context window,
    # while the medium models support 256K." Three days between a verified entry and a stale one is
    # the argument for this table saying when it was checked (R2 agent 1, 2026-09-09).
    "gemma": ("a small build, E2B or E4B, 128K",
              "a medium build — 12B, 26B A4B, 31B — 256K"),
    # Mistral: `docs.mistral.ai/models/model-cards/mistral-medium-3-5-26-04`, fetched 2026-09-09,
    # gives 256k for the current flagship. Older locally-served builds are still 128K, and "mistral"
    # alone does not say which, so it does not get a single number either.
    "mistral": ("an older or locally-served build, around 128K",
                "Mistral Medium 3.5 and current hosted builds, 256K"),
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
    # 🐛 [2026-09-10] The normaliser was taught `_`, `-`, whitespace and trailing version digits,
    # and never the two things every GATEWAY and every CLOUD PLATFORM puts in front of the family:
    # a slash-separated publisher, and a dotted region/publisher prefix. So the three standard ways
    # of addressing a hosted model all missed the table —
    #
    #   anthropic/claude-opus-5                    OpenRouter and most gateways
    #   us.anthropic.claude-opus-5-20260101-v1:0   Bedrock
    #   publishers/anthropic/models/claude-opus-5  Vertex
    #
    # — while the bare `claude-opus-5` matched. Every one of those families IS in the table, so the
    # user was handed `standard`'s 3,000-token index budget while running a model `large-window`'s
    # 8,000 was written for: 2.7× smaller, silently. And the note printed said the family "is not in
    # the model table", which is true of the string and false of the family, so the honest reading
    # of it is "my vendor is unsupported" rather than "I typed a prefix" (R4 agent 1, finding 9).
    #
    # Publisher first, then the family token, then the dotted prefix off what is left — in that
    # order, because `gpt-5.6` has a dot the version-digit strip is meant to see and the region
    # prefix is only ever ahead of the family, never behind it.
    key = text.rsplit("/", 1)[-1].split("-")[0].split()[0].rsplit(".", 1)[-1].rstrip("0123456789.")
    if key in AMBIGUOUS:
        small, large = AMBIGUOUS[key]
        return DEFAULT, (f"`{family}` ships in two sizes that want different profiles: {small} "
                         f"and {large}. Using `{DEFAULT}` — pass --window with the number your "
                         f"deployment actually has.")
    if key in MODEL_WINDOWS:
        return by_window(MODEL_WINDOWS[key]), ""
    return DEFAULT, (f"`{family}` is not in the model table, which is a dated convenience rather "
                     f"than an authority. Using `{DEFAULT}` — pass --window to be exact.")
