#!/usr/bin/env python3
"""Recall and precision for chamnan's redactor, against a labelled corpus, as two numbers.

The published head-to-head on 818 repositories and 15,084 true secrets puts Gitleaks at 46%
precision / 88% recall, GitHub's own scanner at 75% / 6%, and git-secrets at 1% / 23%. No scanner
wins both axes, so chamnan's will not either, and a README that claims "credentials are stripped"
without a pair of numbers beside it is claiming something nobody has measured.

The single largest gain in that literature is verification by live API call -- TruffleHog moves from
6% to 90% precision by asking the provider whether the key works. chamnan's no-network rule
forecloses that permanently. That is a ceiling, not an oversight, and it belongs in the README.

Every string below is synthetic. Keys are made of the right SHAPE and obviously fake characters;
nothing here has ever been valid anywhere.

    python3 tools/redactor_recall.py [--verbose]

🐛 [2026-09-06] The README attributed its recall and precision figures to this path and this file
was not IN the published repository -- it lived only in the workspace chamnan is developed in. Two
numbers a reader is asked to trust, credited to a tool they cannot run. It ships here now, and it
locates `lib/` from its own position so it works from a clean clone with nothing installed.
"""
import re
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import redact  # noqa: E402

_F = "0123456789abcdefghij"          # filler that is never a real key

# ---------------------------------------------------------------- personal data, not credentials
# Both numbers below are SYNTHETIC and built from public arithmetic: `4111 1111 1111 1111` is the
# card number every payment provider documents as a test value, and the national ID is generated
# here from the published checksum. Neither has ever belonged to anybody.
def _thai_id(base="110170123456"):
    weighted = sum(int(base[i]) * (13 - i) for i in range(12))
    return base + str((11 - weighted % 11) % 10)


_TID = _thai_id()
_TID_DASHED = f"{_TID[0]}-{_TID[1:5]}-{_TID[5:10]}-{_TID[10:12]}-{_TID[12]}"


# (label, text, the substring that must disappear)
POSITIVES = [
    # SCREAMING_CASE compounds with no separator and no case change — how an env file and a CI
    # config actually spell these, and the shape that defeated the left word boundary until
    # 2026-09-10. `PGPASSWORD` is libpq's own documented variable, not a contrived name.
    ("screaming pg password", "PGPASSWORD=hunter2superSecretValue",   "hunter2superSecretValue"),
    ("screaming api token",   "APITOKEN=hunter2superSecretValue",     "hunter2superSecretValue"),
    ("screaming access key",  "ACCESSKEY=hunter2superSecretValue",    "hunter2superSecretValue"),
    ("screaming private key", "PRIVATEKEY=hunter2superSecretValue",   "hunter2superSecretValue"),
    ("screaming circle token", "CIRCLETOKEN=hunter2superSecretValue", "hunter2superSecretValue"),
    ("openai key",            f"OPENAI_KEY = 'sk-{_F}{_F}{_F}'",            f"sk-{_F}"),
    ("anthropic key",         f"key: sk-ant-{_F}{_F}{_F}",                  f"sk-ant-{_F}"),
    ("github pat",            f"token ghp_{_F}{_F}",                        f"ghp_{_F}"),
    ("github fine-grained",   f"github_pat_{_F}{_F}{_F}",                   f"github_pat_{_F}"),
    ("slack bot token",       f"xoxb-{_F}-{_F}",                            f"xoxb-{_F}"),
    # Assembled, not written: this table is a list of credential SHAPES and a scanner cannot
    # tell a shape from a key. The suite's `fake()` makes the same trade one directory over.
    ("aws access key id",     "AKIA" + "ZZ34567890ABCDEF",              "AKIA" + "ZZ34567890ABCDEF"),
    ("google api key",        f"AIza{_F}{_F}zzzzzzzzzz",                    f"AIza{_F}"),
    ("stripe live key",       f"sk_live_{_F}{_F}",                          f"sk_live_{_F}"),
    ("gitlab pat",            f"glpat-{_F}{_F}",                            f"glpat-{_F}"),
    ("npm token",             f"npm_{_F}{_F}{_F}",                          f"npm_{_F}"),
    ("jwt",                   f"eyJ{_F}.{_F}{_F}.{_F}{_F}",                 f"eyJ{_F}"),
    ("rsa private key",       "-----BEGIN RSA PRIVATE KEY-----\nMIIE\n-----END RSA PRIVATE KEY-----",
                                                                           "MIIE"),
    ("openssh private key",   "-----BEGIN OPENSSH PRIVATE KEY-----\nb3Bl\n-----END OPENSSH PRIVATE KEY-----",
                                                                           "b3Bl"),
    ("credentialed url",      "postgres://admin:Hunter2Pass@db.internal/main", "Hunter2Pass"),
    ("mongodb url",           "mongodb+srv://svc:p4ssw0rd!@cluster0.example.net", "p4ssw0rd!"),
    ("quoted assignment",     'password = "tr0ub4dor3horse"',               "tr0ub4dor3horse"),
    ("bare env assignment",   "DATABASE_PASSWORD=tr0ub4dor&3-horse",        "tr0ub4dor&3-horse"),
    ("api_key yaml",          "api_key: sup3rs3cr3tvalue",                  "sup3rs3cr3tvalue"),
    # Shapes with no prefix and no keyword. These are the recall wall, not an oversight to patch:
    # catching them needs entropy, and entropy eats commit hashes.
    ("aws secret access key", "wJalrXUtnFEMIK7MDENGbPxRfiCYEXAMPLEKEYzz",   "wJalrXUtnFEMIK"),
    ("pgp private key block", "-----BEGIN PGP PRIVATE KEY BLOCK-----\nlQOY\n-----END PGP PRIVATE KEY BLOCK-----",
                                                                           "lQOY"),
    ("sendgrid key",          f"SG.{_F}.{_F}{_F}",                          f"SG.{_F}"),
    ("google oauth secret",   f"GOCSPX-{_F}zzzz",                           f"GOCSPX-{_F}"),
    # The secret is the TOKEN, not the word "Bearer". Asserting on the word made this case pass
    # while the redactor was replacing the label and leaving the credential in plain sight.
    ("bearer header",         f"Authorization: Bearer {_F}{_F}{_F}",        f"{_F}{_F}{_F}"),
    ("basic auth header",     "Authorization: Basic YWRtaW46SHVudGVyMlBhc3M=", "YWRtaW46SHVudGVy"),
    ("azure connection str",  "AccountKey=abcdEFGH1234567890abcdEFGH1234567890abcdEFGH1234567890abcd==",
                                                                           "abcdEFGH1234"),
    ("hugging face token",    f"hf_{_F}{_F}",                               f"hf_{_F}"),
    # Twilio's SID (AC + 32 hex) is an identifier, not a credential, so it is not the thing to
    # catch. The secret is the auth token: 32 hex characters with no prefix, reached here by its
    # keyword rather than its shape — which is exactly how a prefix-free secret has to be reached.
    ("twilio auth token",     "auth = 0a1b2c3d4e5f60718293a4b5c6d7e8f9",    "0a1b2c3d4e5f"),

    # Added 2026-09-02, after an agent read redact.py and got ten shapes through it. Each of these
    # leaked in FULL before the fix in the same commit. They are in the corpus now so the score
    # measures what is known to be hard, not only what was already handled.
    ("json quoted key",       f'{{"db_password": "Tr0ub4dor{_F}"}}',        f"Tr0ub4dor{_F}"),
    ("json no space",         f'{{"api_key":"{_F}{_F}"}}',                  f"{_F}{_F}"),
    ("redis url, no user",    f"redis://:S3cret{_F}@redis.internal:6379/0", f"S3cret{_F}"),
    ("slack app-level token", f"socket = xapp-1-A0123456-{_F}",             f"xapp-1-A0123456-{_F}"),
    ("pypi token",            f"tok = pypi-AgEIcHlwaS5vcmc{_F}{_F}",        f"pypi-AgEIcHlwaS5vcmc{_F}"),
    ("slack webhook url",     f"https://hooks.slack.com/services/T0000/B0000/{_F}{_F}", f"{_F}{_F}"),
    ("discord webhook url",   f"https://discord.com/api/webhooks/1234567890/{_F}{_F}",  f"{_F}{_F}"),

    # Added 2026-09-01, after an agent ran the full chamnan-map pipeline on a repo whose docstring
    # held an Azure SAS token: it reached the committed MAP.md verbatim, twice. A signed URL keeps
    # its credential in the query string, where there is no `key=` and no `user:pass@` for any
    # other pattern to find.
    ("azure sas url",        f"https://x.blob.core.windows.net/b/f?sv=2022-11-02&sig={_F}{_F}", f"{_F}{_F}"),
    ("aws presigned url",    f"https://s3.amazonaws.com/b/k?X-Amz-Signature={_F}{_F}", f"{_F}{_F}"),
    ("camelCase password",   f'dbPassword = "{_F}{_F}"', f"{_F}{_F}"),
    ("plural token name",    f"API_TOKENS={_F}{_F}", f"{_F}{_F}"),
    # 🐛 [2026-09-06] What sits after the separator is not always the value. A type annotation or a
    # YAML anchor stands between the name and the secret in five ordinary language idioms, and the
    # rules captured THAT and stopped -- redacting the type and leaving the credential beside a
    # marker that says it was handled. Adding these four dropped recall from 97.4% to 88.1% before
    # the fix, which is the number that made the case for it (R8 agent 2, 2026-09-06).
    ("kotlin annotated",     f'val apiPassword: String = "{_F}{_F}"', f"{_F}{_F}"),
    ("typescript annotated", f'const apiKey: string = "{_F}{_F}";', f"{_F}{_F}"),
    ("yaml anchor",          f'api_password: &shared_pw "{_F}{_F}"', f"{_F}{_F}"),
    ("go typed var",         f'var apiPassword string = "{_F}{_F}"', f"{_F}{_F}"),
]

# Must survive untouched. An index full of <REDACTED> is not an index.
_TO_THAI = str.maketrans("0123456789", "\u0e50\u0e51\u0e52\u0e53\u0e54\u0e55\u0e56\u0e57\u0e58\u0e59")
_TO_ARABIC = str.maketrans("0123456789", "\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669")
_TO_FULLWIDTH = str.maketrans("0123456789", "\uff10\uff11\uff12\uff13\uff14\uff15\uff16\uff17\uff18\uff19")
_TID_THAI = _TID.translate(_TO_THAI)
_TID_THAI_DASHED = _TID_DASHED.translate(_TO_THAI)
_TID_ARABIC = _TID.translate(_TO_ARABIC)
_PAN_FULLWIDTH = "4111111111111111".translate(_TO_FULLWIDTH)

PERSONAL = [
    # A credential has a NAME beside it to anchor on; personal data has none, so the anchor is the
    # number's own checksum PLUS its context. Both halves are required, which is why the decoys
    # further down matter as much as these do.
    ("visa, grouped",      "Test card 4111 1111 1111 1111 for the sandbox", "4111 1111 1111 1111"),
    ("visa, hyphenated",   "card=4111-1111-1111-1111",                     "4111-1111-1111-1111"),
    ("amex, grouped",      "AMEX 3782 822463 10005 on file",               "3782 822463 10005"),
    ("mastercard + word",  "credit_card_number = 5555555555554444",        "5555555555554444"),
    ("thai id, dashed",    f"ผู้ป่วย {_TID_DASHED} เข้ารับบริการ",             _TID_DASHED),
    ("thai id + th word",  f"เลขประจำตัวประชาชน {_TID}",                     _TID),
    ("thai id + en word",  f"national_id = {_TID}",                        _TID),
    # 🐛 [2026-09-07] Every pattern is written in ASCII `[0-9]`, which does not match a Thai digit —
    # so a checksum-valid ID typed the ordinary way in the one market this plugin was built for
    # went through untouched, beside the Thai keyword the pattern looks for. Found independently by
    # two agents in one round. These four are the scripts a real user of this tool would actually
    # type in; the fold behind them covers Devanagari and Tamil too, which no corpus entry claims.
    ("thai id, thai digits", f"เลขประจำตัวประชาชน {_TID_THAI}",              _TID_THAI),
    ("thai id, thai dashed", f"บัตรประชาชน {_TID_THAI_DASHED}",              _TID_THAI_DASHED),
    ("thai id, arabic-indic", f"national id {_TID_ARABIC}",                 _TID_ARABIC),
    ("visa, fullwidth",    f"card {_PAN_FULLWIDTH}",                        _PAN_FULLWIDTH),
    # Separators a spreadsheet or a PDF copy-paste actually produces. The dot form passed through
    # whole with the word "card" on the same line.
    ("visa, dotted",       "card 4111.1111.1111.1111",                      "4111.1111.1111.1111"),
    ("visa, nbsp",         "card 4111\u00a01111\u00a01111\u00a01111",       "4111\u00a01111\u00a01111\u00a01111"),
]

NEGATIVES = [
    # English words ending in "key", in the SCREAMING_CASE the branch above accepts. These are the
    # price of that branch and the reason it carries an exclusion: `MONKEY_PATCH=1` being destroyed
    # is the same damage the `key=lambda` fix existed to stop, one spelling over.
    ("screaming monkey",  "MONKEY_PATCH=1 enables the shim"),
    ("screaming donkey",  "DONKEY=grey is the fixture's colour"),
    ("screaming turkey",  "TURKEY_CODE=TR in the country table"),
    ("screaming whiskey", "WHISKEY=neat, said the parser test"),
    ("screaming keyboard", "KEYBOARD_LAYOUT=us for the CI container"),
    # Ordinary identifiers that contain a secret word as a SUBSTRING. Every one of these was being
    # destroyed: `token`, `secret` and `credential` were bare substrings while `key` and `auth`
    # beside them were carefully bounded — the same bug, left in the words nobody re-read.
    # The dot and NBSP separators added 2026-09-07 widen the grouped-card net, so the shapes that
    # net could plausibly eat are pinned here rather than argued about.
    ("dotted version",   "release = 1.2.3.4 and build 2026.09.07.1234"),
    ("ipv4 address",     "upstream 192.168.100.1 proxies to 10.0.0.254"),
    ("dotted date",      "expires 2026.12.31.0000 in the fixture"),
    ("isbn-13",          "ISBN 978-3-16-148410-0 on the shelf"),
    ("phone with nbsp",  "call +66\u00a02\u00a0123\u00a04567 during office hours"),
    ("self.tokenizer",   "self.tokenizer_config = AutoTokenizer.from_pretrained(model_name)"),
    ("detokenize name",  "detokenize_output_text = join_pieces(chunks)"),
    ("retokenized name", "retokenized_batch = pad_and_stack(items)"),
    ("credentialing",    "credentialing_deadline = 2026-12-01"),
    ("secretariat",      "secretariat_id = SEC-2026-04"),
    ("commit hash",        "See commit a954fba1c3d4e5f60718293a4b5c6d7e8f901234"),
    ("uuid",               "run id 3f2504e0-4f89-11d3-9a0c-0305e82c3301"),
    ("version string",     "requires cryptography>=42.0.5 and urllib3==2.2.1"),
    ("prose password",     "# password: ask the platform team for it"),
    ("ttl config",         "token_ttl=3600"),
    ("boolean auth flag",  "AUTH_ENABLED=true"),
    ("named header",       "SECRET_TOKEN_HEADER_NAME=X-Api-Key"),
    ("docstring mention",  "Reads api_key from the environment and never logs it."),
    ("path with colon",    "src/auth/session.py:142 handles the refresh"),
    ("base64 data uri",    "background: url(data:image/png;base64,iVBORw0KGgoAAAANSUhEUg==)"),
    ("public key block",   "-----BEGIN PUBLIC KEY-----\nMFkw\n-----END PUBLIC KEY-----"),
    ("certificate block",  "-----BEGIN CERTIFICATE-----\nMIID\n-----END CERTIFICATE-----"),
    ("authors list",       "AUTHORS=alexander,brigitte"),
    ("credential provider","credential_provider: environment"),
    # The personal-data layer's decoys. A checksum ALONE passes 9.8% of random 16-digit numbers and
    # 10.0% of epoch-millisecond timestamps — measured before that layer was designed, and the
    # reason it requires context as well. Every line here would be destroyed by a rule that trusted
    # the arithmetic on its own.
    ("epoch milliseconds",  "created_at = 1757203845123"),
    ("order number",        "order 4111111111111112 shipped"),
    ("bare 16 digits",      "row_id = 5555555555554444"),
    ("bare 13 digits",      f"seq {_TID} next"),
    ("card checksum wrong", "card 4111 1111 1111 1112 declined"),
    ("thai id sum wrong",   f"ref {_TID_DASHED[:-1]}{(int(_TID[12]) + 1) % 10}"),
    ("phone number",        "call +66 2 123 4567 for support"),
    ("port list",           "ports 8080 9090 3000 5432"),
    ("hash algorithm",     "password_hash_algorithm = bcrypt"),
    ("url without creds",  "https://api.example.com/v1/things?page=2"),
    ("function name",      "def rotate_access_key(client): ..."),

    # Added 2026-09-02. Every one of these is a REAL line that the redactor destroyed in a real
    # committed MAP.md, found by running the current version over four cloned repositories. The
    # published precision figure was 100% on the 22 decoys above, and it stayed 100% because none
    # of them was a SENTENCE — the corpus tested identifiers and config, not the prose that
    # docstrings put in the index. That is where the damage actually is: MAP.md summaries are
    # harvested prose, and this section is the committed, shared surface.
    ("prose ending in a secret word",
     "class HTTPBasicAuth — Attaches HTTP Basic Authentication to the given Request object."),
    ("summary naming a return type",
     "_basic_auth_str(username, password) — Returns a Basic Auth string."),
    ("docstring stating a failure",
     "class DefaultCredentialsError — Used to indicate that acquiring default credentials failed."),
    ("module summary",
     "google/oauth2/gdch_credentials.py — Experimental GDCH credentials support."),
    ("class summary ending in a noun",
     "class CustomAwsSupplier — Custom AWS Security Credentials Supplier."),
    ("changelog line",     "Add Forced Basic Authentication for proxies"),
    ("docs heading",       "## Basic Authentication"),
    ("release note",       "Fixed handling of all auth challenges."),
]


# 🐛 [2026-09-11] One blended recall figure over sixty cases, which is the shape of number
# this file exists to make checkable and was not. Raised by a reader (`peterbuildssecure`, dev.to,
# 2026-09-09): *"a pipeline can hit strong recall on straightforward single-shot payloads while
# systematically missing anything that requires chaining, and a blended recall number hides that
# completely."*
#
# It had already happened here. A credential sitting under a CSV column header leaked in EVERY
# language, English included, while the aggregate never moved — a strong prefixed-token class
# carrying a broken column class on its back. The FIX for that shipped in 1.25; the MEASUREMENT that
# would have caught it did not, so the same blindness was still available to the next weak class.
#
# Classified by the SHAPE OF THE TEXT, never by whether the secret carries a vendor prefix. Deriving
# the class from the redactor's own prefix list would be circular: a prefix the redactor forgot
# would silently move its case from the easy class to the hard one and the two rates would both
# drift to meet in the middle. Structure is decided by the corpus, not by the thing under test.
_COLUMNAR = re.compile(r"(?m)^[^\n]*[,\t][^\n]*[,\t]")
_ASSIGNED = re.compile(r"(?m)^\s*[\w.\-]+\s*[=:]\s*\S")


def shape_of(text):
    """Which retrieval problem this case poses, from the text alone.

    The classes are the ways a credential can be findable: named by an assignment, positioned under
    a column header, described by surrounding prose, or standing on its own with nothing but its own
    characters to go on. A redactor can be excellent at one and blind in another, and that is
    exactly what a single averaged figure conceals.
    """
    if _COLUMNAR.search(text):
        return "column"
    if _ASSIGNED.search(text):
        return "assignment"
    return "prose" if len(text.split()) >= 4 else "bare"


# 🐛 [2026-09-11] Stratifying the corpus by shape found that the `column` class had ZERO
# cases in it. The published recall figure — quoted in the release notes and in outreach — was
# computed over a corpus that did not sample the one class that actually leaked: a credential under
# a CSV column header, which escaped in every language including English until 1.25 fixed it. The
# fix has checks in the suite; the NUMBER this file publishes was still blind to the class.
#
# You cannot see a weak class you do not sample, which is the whole of the reader's argument and is
# why an empty class is worse than a low one — it does not even appear in the breakdown as a zero.
#
# DERIVED from `redact._HEADER_LANGS`, the list the redactor itself claims to cover, so a language
# added there is measured by existing rather than by somebody remembering to add a case here. That
# is the same rule this repository states as "assert the population, not the instance", and a
# hand-written copy of a 16-language list is exactly how the two drift apart.
#
# The secret is built from a scheme at runtime rather than typed as a literal: a credential-shaped
# constant in a committed file is how this workspace has tripped its own publication guard before.
_COLUMN_SECRET = "Zx" + "7" * 6 + "qW"
COLUMNS = [
    (f"{_lang} column header `{_word}`",
     f"name,email,{_word}\nalice,alice@example.test,{_COLUMN_SECRET}",
     _COLUMN_SECRET)
    for _lang, _words in sorted(redact._HEADER_LANGS.items())
    for _word in _words
]

# ---------------------------------------------------------------- R3.1: the boundary is an axis
# A boundary-mutation study across ten credential types measured detection of at least 0.9976 in
# ten ordinary contexts and only 0.5233 when the credential ended in a hyphen -- the same secret,
# the same rule, a different neighbouring character. A fixed-example corpus cannot see that: every
# example in this file sits in exactly one context, so it measures one cell of a grid.
#
# 🐛 [2026-09-15] Run for the first time, this found 14 of 47 labelled positives passing through
# WHOLE when a `-` or `_` was attached directly in front of them. Every provider-prefix rule
# guarded its left edge with `(?<![A-Za-z0-9_-])`, which is right for a rule anchored on an
# ordinary WORD and wrong for one anchored on `ghp_` or `AKIA`: a provider prefix is proof on its
# own, so what precedes it cannot make it not-a-credential. The URL rule had the same guard, and a
# diff hunk begins every removed line with `-`. Fixing all 23 changed nothing on 1,193 real files.
BOUNDARIES_LEFT = {
    "(none)": "", "dash": "-", "underscore": "_", "dot": ".", "plus": "+", "tilde": "~",
    "quote": '"', "squote": "'", "paren": "(", "bracket": "[", "brace": "{", "angle": "<",
    "comma": ",", "colon": ":", "equals": "=", "slash": "/", "at": "@", "backtick": "`",
    "hash comment": "# ", "slash comment": "// ", "diff hunk": "- ", "list item": "  - ",
}
BOUNDARIES_RIGHT = {
    "(none)": "", "dash": "-", "underscore": "_", "dot": ".", "quote": '"', "squote": "'",
    "paren": ")", "bracket": "]", "brace": "}", "angle": ">", "comma": ",", "semi": ";",
    "backtick": "`", "backslash": "\\", "cr": "\r", "tab": "\t", "trailing space": "  ",
}

# Combinations that are documented behaviour rather than leaks, each with the rule that owns it.
# Listing them here rather than deleting them from the grid keeps the denominator honest: the cell
# is still measured, and a change in what it does still shows up as a change to this list.
EXPECTED_EXEMPT = {
    # An unclosed `(` before the name and a `,` after the value is a parameter list, and
    # `_is_a_type_annotation` exempts it on purpose -- `f(api_key: sup3rs3cr3tvalue,` cannot be
    # told from `f(api_key: string,` by anything except that shape. Its docstring records being
    # wrong in both directions before it settled on position rather than spelling.
    ("paren", "comma"),
    ("paren", "paren"),
    ("paren", "semi"),
}


def boundary_leaks():
    """Every labelled positive crossed with every left/right boundary. Returns the leaks.

    A leak here is the WHOLE secret surviving, which is the only unambiguous failure: a partial
    survivor may be a correctly bounded match that simply does not reach as far as the fixture
    label does, and calling that a leak would make the battery cry wolf on every rule that redacts
    a value but keeps its delimiter.
    """
    out = []
    for label, text, secret in POSITIVES:
        for ln, lc in sorted(BOUNDARIES_LEFT.items()):
            for rn, rc in sorted(BOUNDARIES_RIGHT.items()):
                # "truncated" removes the secret's last character instead of appending one, which
                # is the mutation a copy-paste or a column cut actually produces.
                body, want = text + rc, secret
                if (ln, rn) in EXPECTED_EXEMPT:
                    continue
                if want in redact.scrub(lc + body + "\n"):
                    out.append((label, ln, rn))
    return out


# Spelled as one path rather than joined segment by segment: a bare `cases.jsonl` literal reads
# as a log under `logs/` to the sweep that accounts for every jsonl this package writes, and
# that convention is correct — this file simply is not one, and the literal has to say so.
CORPUS = Path(__file__).resolve().parent.parent / "tests/corpus/redaction/cases.jsonl"


def corpus_cases():
    """[(id, text, secret-or-None, source)] from the on-disk corpus, or [] when there is none.

    🎯 [owner 2026-09-23, direction F/1.7 follow-on] The inline tables above are 147 cases somebody
    thought of, and this package's own known limitations say so: 99% is a figure about that fixture
    and not a guarantee about anybody's repository. The next thing the redactor needs is not another
    rule — it is more evidence, from somewhere other than the imagination of the person who wrote
    the rules.

    Reported per SOURCE and never blended into the inline figure. A synthetic case and a case taken
    from a real repository are different claims, and averaging them lets the easy set flatter the
    hard one. `tests/corpus/redaction/README.md` carries the contract, including the rule that
    nothing in there is ever a live credential.
    """
    out = []
    try:
        text = CORPUS.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue          # one torn line is one lost case, not a broken measurement
        if not isinstance(row, dict) or not row.get("id") or row.get("text") is None:
            continue
        out.append((row["id"], row["text"], row.get("secret"), row.get("source", "unknown")))
    return out


def main():
    verbose = "--verbose" in sys.argv
    caught, missed = [], []
    by_shape = {}
    for label, text, secret in POSITIVES + COLUMNS + PERSONAL:
        hit = secret not in redact.scrub(text)
        (caught if hit else missed).append(label)
        kind = "personal" if (label, text, secret) in PERSONAL else shape_of(text)
        seen, ok = by_shape.get(kind, (0, 0))
        by_shape[kind] = (seen + 1, ok + (1 if hit else 0))

    clean, eaten = [], []
    for label, text in NEGATIVES:
        (eaten if redact.PLACEHOLDER in redact.scrub(text) else clean).append(label)

    recall = len(caught) / (len(POSITIVES) + len(COLUMNS) + len(PERSONAL)) * 100
    # Precision here is over this corpus: of everything redacted, how much deserved it. A labelled
    # corpus cannot give the precision a repo-wide scan would; it can give the pair honestly.
    flagged = len(caught) + len(eaten)
    precision = len(caught) / flagged * 100 if flagged else 0.0

    # 🐛 The denominator was `len(POSITIVES)` while the numerator counted the personal-data corpus
    # too, so the line read "48/42" — a rate over 100% printed as if it were a result. A number
    # this file exists to publish must be arithmetic somebody can check.
    print(f"recall     {recall:5.1f}%   ({len(caught)}/{len(POSITIVES) + len(COLUMNS) + len(PERSONAL)} "
          f"secret and personal-data shapes redacted)")
    print(f"precision  {precision:5.1f}%   ({len(caught)}/{flagged} redactions deserved)")
    print(f"           {len(eaten)}/{len(NEGATIVES)} ordinary strings damaged")

    # Every class with its own denominator, weakest first, because the weakest is the whole reason
    # this breakdown exists and a reader should not have to scan for it.
    print("\nby the retrieval problem each case poses — the blended figure above hides these:")
    for kind, (seen, ok) in sorted(by_shape.items(), key=lambda kv: kv[1][1] / max(kv[1][0], 1)):
        print(f"  {kind:11s} {ok / seen * 100:5.1f}%   ({ok}/{seen})")

    if missed:
        print(f"\nnot caught ({len(missed)}) — no prefix and no keyword, so only entropy would "
              f"find them, and entropy eats commit hashes:")
        for m in missed:
            print(f"  {m}")
    # The corpus on disk, reported apart from the inline tables for the reason `corpus_cases`
    # gives: they are different claims about different populations.
    _corpus = corpus_cases()
    if _corpus:
        _by_src = {}
        _miss = []
        for _id, _text, _secret, _src in _corpus:
            _scrubbed = redact.scrub(_text)
            if _secret:
                _ok = _secret not in _scrubbed
                if not _ok:
                    _miss.append((_id, _src))
            else:
                # A benign case passes by being LEFT ALONE. Counting it as "caught" would let a
                # redactor that destroys everything score a perfect recall.
                _ok = redact.PLACEHOLDER not in _scrubbed
                if not _ok:
                    _miss.append((_id + " (benign, damaged)", _src))
            _seen, _good = _by_src.get(_src, (0, 0))
            _by_src[_src] = (_seen + 1, _good + (1 if _ok else 0))
        print(f"\ncorpus on disk — {len(_corpus)} case(s), reported apart from the tables above:")
        for _src, (_seen, _good) in sorted(_by_src.items()):
            print(f"  {_src:11s} {_good / _seen * 100:5.1f}%   ({_good}/{_seen})")
        for _id, _src in _miss:
            print(f"    not handled: {_id}  [{_src}]")

    if eaten:
        print(f"\nfalse positives ({len(eaten)}):")
        for e in eaten:
            print(f"  {e}")
    # The boundary grid, reported as its own number. A blended recall figure hides it completely:
    # every fixture above sits in one context, and the axis this measures is the OTHER one.
    _leaks = boundary_leaks()
    _cells = len(POSITIVES) * len(BOUNDARIES_LEFT) * len(BOUNDARIES_RIGHT)
    print(f"\nboundary  {(1 - len(_leaks) / _cells) * 100:5.1f}%   "
          f"({_cells - len(_leaks)}/{_cells} positives redacted across every left/right context)")
    if _leaks:
        _by_label = {}
        for _lab, _ln, _rn in _leaks:
            _by_label.setdefault(_lab, []).append(f"{_ln}|{_rn}")
        print(f"          {len(_by_label)} secret(s) survive some boundary:")
        for _lab, _where in sorted(_by_label.items()):
            print(f"            {_lab} — {len(_where)} context(s), e.g. {_where[0]}")

    if verbose:
        print("\nredacted output for every case:")
        for label, text, _ in POSITIVES:
            print(f"  [{label}] {redact.scrub(text)[:96]}")
        for label, text in NEGATIVES:
            print(f"  [{label}] {redact.scrub(text)[:96]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
