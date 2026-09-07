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
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import redact  # noqa: E402

_F = "0123456789abcdefghij"          # filler that is never a real key

# (label, text, the substring that must disappear)
POSITIVES = [
    ("openai key",            f"OPENAI_KEY = 'sk-{_F}{_F}{_F}'",            f"sk-{_F}"),
    ("anthropic key",         f"key: sk-ant-{_F}{_F}{_F}",                  f"sk-ant-{_F}"),
    ("github pat",            f"token ghp_{_F}{_F}",                        f"ghp_{_F}"),
    ("github fine-grained",   f"github_pat_{_F}{_F}{_F}",                   f"github_pat_{_F}"),
    ("slack bot token",       f"xoxb-{_F}-{_F}",                            f"xoxb-{_F}"),
    ("aws access key id",     "AKIAZZ34567890ABCDEF",                       "AKIAZZ34567890ABCDEF"),
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
    # the fix, which is the number that made the case for it (R8 agent 2).
    ("kotlin annotated",     f'val apiPassword: String = "{_F}{_F}"', f"{_F}{_F}"),
    ("typescript annotated", f'const apiKey: string = "{_F}{_F}";', f"{_F}{_F}"),
    ("yaml anchor",          f'api_password: &shared_pw "{_F}{_F}"', f"{_F}{_F}"),
    ("go typed var",         f'var apiPassword string = "{_F}{_F}"', f"{_F}{_F}"),
]

# Must survive untouched. An index full of <REDACTED> is not an index.
NEGATIVES = [
    # Ordinary identifiers that contain a secret word as a SUBSTRING. Every one of these was being
    # destroyed: `token`, `secret` and `credential` were bare substrings while `key` and `auth`
    # beside them were carefully bounded — the same bug, left in the words nobody re-read.
    ("tokenizer attr",   "self.tokenizer_config = AutoTokenizer.from_pretrained(model_name)"),
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


def main():
    verbose = "--verbose" in sys.argv
    caught, missed = [], []
    for label, text, secret in POSITIVES:
        (caught if secret not in redact.scrub(text) else missed).append(label)

    clean, eaten = [], []
    for label, text in NEGATIVES:
        (eaten if redact.PLACEHOLDER in redact.scrub(text) else clean).append(label)

    recall = len(caught) / len(POSITIVES) * 100
    # Precision here is over this corpus: of everything redacted, how much deserved it. A labelled
    # corpus cannot give the precision a repo-wide scan would; it can give the pair honestly.
    flagged = len(caught) + len(eaten)
    precision = len(caught) / flagged * 100 if flagged else 0.0

    print(f"recall     {recall:5.1f}%   ({len(caught)}/{len(POSITIVES)} secret shapes redacted)")
    print(f"precision  {precision:5.1f}%   ({len(caught)}/{flagged} redactions deserved)")
    print(f"           {len(eaten)}/{len(NEGATIVES)} ordinary strings damaged")

    if missed:
        print(f"\nnot caught ({len(missed)}) — no prefix and no keyword, so only entropy would "
              f"find them, and entropy eats commit hashes:")
        for m in missed:
            print(f"  {m}")
    if eaten:
        print(f"\nfalse positives ({len(eaten)}):")
        for e in eaten:
            print(f"  {e}")
    if verbose:
        print("\nredacted output for every case:")
        for label, text, _ in POSITIVES:
            print(f"  [{label}] {redact.scrub(text)[:96]}")
        for label, text in NEGATIVES:
            print(f"  [{label}] {redact.scrub(text)[:96]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
