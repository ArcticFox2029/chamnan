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
    re.compile(r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"\b(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{16,}"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}"),
    re.compile(r"\b(?:sk|rk|pk)_(?:live|test)_[A-Za-z0-9]{16,}"),
    re.compile(r"\bglpat-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bnpm_[A-Za-z0-9]{30,}"),
    # A JWT is three base64 segments; the header almost always starts eyJ.
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
    # Private key and certificate blocks.
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]
# scheme://user:password@host — the password is replaced, the rest is left readable because
# "this talks to postgres on db.internal" is exactly the kind of thing the index should say.
CREDENTIALED_URL = re.compile(r"\b([a-zA-Z][a-zA-Z0-9+.-]*://[^\s:/@]+):([^\s@/]{3,})@")
# password = "...", api_key: '...', SECRET_TOKEN="..." — the value goes, the name stays.
ASSIGNED_SECRET = re.compile(
    r"((?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|"
    r"auth|credential)[\w-]*\s*[:=]\s*)(['\"])([^'\"]{6,})\2", re.I)
# The same assignment without quotes, which is how every .env and .ini file on earth is written.
# Requiring quotes meant DATABASE_PASSWORD=tr0ub4dor&3-horse passed through untouched. Bounded to a
# single unbroken run of characters so a prose comment ("password: ask the platform team") is not
# eaten, and to six characters so token_ttl=3600 is not either.
ASSIGNED_SECRET_BARE = re.compile(
    r"((?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|"
    r"auth|credential)[\w-]*\s*[:=]\s*)([^\s'\"#;,)\]}]{6,})", re.I)

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
    if name.startswith("id_rsa") or name.startswith("id_ed25519"):
        return True
    # Compare the stem too: the deny-list carries "credentials", and the file everyone actually
    # has is credentials.ini, which an exact match on the full name lets straight through.
    stem = name.rsplit(".", 1)[0] if "." in name else name
    return name.endswith(BLOCKED_SUFFIXES) or name in BLOCKED_NAMES or stem in BLOCKED_NAMES


def is_never_opened(path):
    """Files peek refuses outright, because a summary of them is a summary of a secret."""
    name = path.name.lower()
    if name.startswith(("id_rsa", "id_dsa", "id_ecdsa", "id_ed25519")):
        return True
    stem = name.rsplit(".", 1)[0] if "." in name else name
    return (name.endswith(NEVER_OPENED_SUFFIXES) or name in BLOCKED_NAMES
            or stem in BLOCKED_NAMES)


def scrub(text):
    """Every string that leaves chamnan for a written file goes through this."""
    if not text:
        return text
    for pattern in PATTERNS:
        text = pattern.sub(PLACEHOLDER, text)
    text = CREDENTIALED_URL.sub(rf"\1:{PLACEHOLDER}@", text)
    text = ASSIGNED_SECRET.sub(rf"\1\2{PLACEHOLDER}\2", text)
    text = ASSIGNED_SECRET_BARE.sub(rf"\1{PLACEHOLDER}", text)
    return text
