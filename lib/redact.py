"""Strip credentials out of any text chamnan is about to write into MAP.md.

This is not defence in depth for the whole session — a hook cannot rewrite what the Read tool
returns, so chamnan cannot filter what Claude reads. It defends the one thing chamnan actually
controls: its own output.

That output is the part that matters most, because MAP.md is a file this plugin encourages
committing, and its summaries are copied verbatim out of source comments. Verified before this
module existed: a comment reading `// Prod DB is postgres://admin:Hunter2Pass@db.internal/main`
was copied straight into MAP.md, turning an indexing tool into the thing that published a password.

Patterns are deliberately narrow — known token shapes, key blocks, credentialed URLs, and explicit
secret assignments. Redacting anything that merely looks high-entropy would eat commit hashes,
UUIDs and version strings, and an index full of <REDACTED> is not an index. A missed secret is
recoverable; an unusable map means the tool gets uninstalled and nothing is protected at all.
"""
import re

PLACEHOLDER = "<REDACTED>"

PATTERNS = [
    # Provider tokens with unambiguous prefixes — no false positives worth worrying about.
    re.compile(r"(?<![A-Za-z0-9_-])sk-(?:proj-|ant-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?<![A-Za-z0-9_-])(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{16,}"),
    re.compile(r"(?<![A-Za-z0-9_-])xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"(?<![A-Za-z0-9_-])AKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?<![A-Za-z0-9_-])AIza[0-9A-Za-z_-]{30,}"),
    re.compile(r"(?<![A-Za-z0-9_-])(?:sk|rk|pk)_(?:live|test)_[A-Za-z0-9]{16,}"),
    re.compile(r"(?<![A-Za-z0-9_-])glpat-[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?<![A-Za-z0-9_-])npm_[A-Za-z0-9]{30,}"),
    re.compile(r"(?<![A-Za-z0-9_-])SG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?<![A-Za-z0-9_-])GOCSPX-[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?<![A-Za-z0-9_-])hf_[A-Za-z0-9]{30,}"),
    # An Authorization header names its scheme and then hands over the credential. Matching this
    # explicitly is not a nicety: the bare-assignment rule below sees "Authorization:" as a secret
    # assignment, captures the word "Bearer" as the value, and replaces THAT -- leaving the token
    # itself in plain sight under a line that looks redacted. A miss is recoverable; a miss dressed
    # as a hit is not.
    re.compile(r"(?<![A-Za-z0-9_-])(?:Bearer|Basic|Token)\s+([A-Za-z0-9._~+/=-]{12,})"),
    # A JWT is three base64 segments; the header almost always starts eyJ.
    re.compile(r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
    # Private key and certificate blocks.
    # "BLOCK" is not decoration: a PGP secret key is delimited "PRIVATE KEY BLOCK-----", so a
    # pattern anchored on "PRIVATE KEY-----" matched every other format and missed that one.
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY(?: BLOCK)?-----.*?"
               r"-----END [A-Z ]*PRIVATE KEY(?: BLOCK)?-----", re.S),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY(?: BLOCK)?-----"),
]
# scheme://user:password@host — the password is replaced, the rest is left readable because
# "this talks to postgres on db.internal" is exactly the kind of thing the index should say.
# Prefixes added after the original list was written, and two shapes where the secret is not a
# value at all but a path segment — no `key=` and no `user:pass@` for the other patterns to find.
LATE_PREFIXES = [
    re.compile(r"(?<![A-Za-z0-9_-])xapp-[A-Za-z0-9-]{10,}"),                      # Slack app-level, not xox[baprs]-
    re.compile(r"(?<![A-Za-z0-9_-])pypi-[A-Za-z0-9_-]{20,}"),
    re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/]{20,}"),
    re.compile(r"https://discord(?:app)?\.com/api/webhooks/\d+/[A-Za-z0-9_-]{20,}"),
]

CREDENTIALED_URL = re.compile(
    # `*`, not `+`: redis://:password@host and amqp://:pass@host carry no username at
    # all, which is the normal form for both, and a one-or-more group never matched them.
    r"(?<![A-Za-z0-9_-])([a-zA-Z][a-zA-Z0-9+.-]*://[^\s:/@]*):([^\s@/]{3,})@")
# password = "...", api_key: '...', SECRET_TOKEN="..." — the value goes, the name stays.
ASSIGNED_SECRET = re.compile(
    r"((?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|"
    r"account[_-]?key|auth(?!ors?\b)|credential)[\w-]*\s*['\"]?\s*[:=]\s*)(['\"])([^'\"]{6,})\2", re.I)
# The same assignment without quotes, which is how every .env and .ini file on earth is written.
# Requiring quotes meant DATABASE_PASSWORD=tr0ub4dor&3-horse passed through untouched. Bounded to a
# single unbroken run of characters so a prose comment ("password: ask the platform team") is not
# eaten, and to six characters so token_ttl=3600 is not either.
ASSIGNED_SECRET_BARE = re.compile(
    r"((?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|"
    r"account[_-]?key|auth(?!ors?\b)|credential)[\w-]*\s*['\"]?\s*[:=]\s*)"
    r"(?!<REDACTED>)([^\s'\"#;,)\]}]{6,})", re.I)

# Never opened by the scanner at all, whatever else matches. .gitignore is not relied on: it is
# often absent, often wrong, and the cost of being wrong here is somebody's private key.
BLOCKED_SUFFIXES = (
    ".pem", ".key", ".pfx", ".p12", ".crt", ".cer", ".der", ".jks", ".keystore",
    ".db", ".sqlite", ".sqlite3", ".mdb", ".bak", ".dump",
)
BLOCKED_NAMES = ("id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", ".htpasswd", ".netrc",
                 "credentials", "secrets.yml", "secrets.yaml")

# The scanner's list above and this one answer different questions. The scanner should not open a
# database at all -- it indexes source, and a .sqlite is not source. peek is asked for one file by
# name, and a database's table and column names are exactly the useful answer, with no row ever
# printed. Refusing those too cost peek one of its better features for no gain. What stays refused
# is the set whose contents ARE the secret: keys, certificates, and credential files.
NEVER_OPENED_SUFFIXES = (".pem", ".key", ".pfx", ".p12", ".crt", ".cer", ".der",
                         ".jks", ".keystore", ".asc", ".gpg")


def is_blocked(path):
    name = path.name.lower()
    # The same four is_never_opened checks. These two lists had drifted apart, so a renamed
    # id_dsa_backup was refused by the read-one-file tool and scanned by the indexer.
    if name.startswith(("id_rsa", "id_dsa", "id_ecdsa", "id_ed25519")):
        return True
    # Compare the stem too: the deny-list carries "credentials", and the file everyone actually
    # has is credentials.ini, which an exact match on the full name lets straight through.
    stem = name.rsplit(".", 1)[0] if "." in name else name
    # ANY segment, not just the last. `server.key.old` and `prod.pem.txt` are the ordinary way a
    # key gets copied aside, and an endswith() check lets both through while catching the bare file.
    if any(f".{seg}" in BLOCKED_SUFFIXES for seg in name.split(".")[1:]):
        return True
    return name.endswith(BLOCKED_SUFFIXES) or name in BLOCKED_NAMES or stem in BLOCKED_NAMES


def is_never_opened(path):
    """Files peek refuses outright, because a summary of them is a summary of a secret."""
    name = path.name.lower()
    if name.startswith(("id_rsa", "id_dsa", "id_ecdsa", "id_ed25519")):
        return True
    stem = name.rsplit(".", 1)[0] if "." in name else name
    return (name.endswith(NEVER_OPENED_SUFFIXES) or name in BLOCKED_NAMES
            or stem in BLOCKED_NAMES)


# A key can carry a secret word and still be naming a mechanism rather than holding a credential:
# SECRET_TOKEN_HEADER_NAME is the name of a header, credential_provider is which provider to use,
# password_hash_algorithm is bcrypt. Redacting those costs the index real information and protects
# nothing. Kept short and each entry defensible -- this is the precision side of the trade in the
# module docstring, and a long list here is how a scanner starts missing things.
NAMING_SUFFIXES = ("name", "names", "path", "paths", "file", "files", "dir", "url",
                   "provider", "algorithm", "algo", "type", "method", "scheme",
                   "header", "enabled", "required", "ttl", "expiry", "field")


# The word after "Authorization:" is the scheme, never the credential — the credential is the token
# after it, which the Bearer/Basic pattern above has already taken. Without this the bare rule
# replaces the scheme too and an Authorization header reads "<REDACTED> <REDACTED>".
SCHEME_WORDS = frozenset({"bearer", "basic", "digest", "negotiate", "ntlm", "token", "apikey"})


def _names_a_mechanism(key):
    """True when the key is describing HOW a credential is handled, not holding one."""
    tail = key.rstrip(": =\t").lower().rsplit("_", 1)[-1].rsplit("-", 1)[-1]
    return tail in NAMING_SUFFIXES


def scrub(text):
    """Every string that leaves chamnan for a written file goes through this."""
    if not text:
        return text
    for pattern in PATTERNS + LATE_PREFIXES:
        # A pattern with one group keeps everything outside it: "Bearer <REDACTED>" stays readable
        # as an Authorization header while the credential goes. Groupless patterns replace whole.
        if pattern.groups == 1:
            text = pattern.sub(lambda m: m.group(0).replace(m.group(1), PLACEHOLDER), text)
        else:
            text = pattern.sub(PLACEHOLDER, text)
    text = CREDENTIALED_URL.sub(rf"\1:{PLACEHOLDER}@", text)
    text = ASSIGNED_SECRET.sub(
        lambda m: m.group(0) if _names_a_mechanism(m.group(1))
        else f"{m.group(1)}{m.group(2)}{PLACEHOLDER}{m.group(2)}", text)
    text = ASSIGNED_SECRET_BARE.sub(
        lambda m: m.group(0)
        if _names_a_mechanism(m.group(1)) or m.group(2).lower() in SCHEME_WORDS
        else f"{m.group(1)}{PLACEHOLDER}", text)
    return text
