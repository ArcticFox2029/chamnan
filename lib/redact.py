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
    # GREEDY, and that is the whole point. A lazy body stops at the FIRST text shaped like an END
    # line -- and a README snippet, or a comment reading "keys end with -----END RSA PRIVATE
    # KEY-----", supplies one between the real BEGIN and the real END. The header and the decoy
    # were replaced while the entire base64 body of a real key went through untouched, on the
    # highest-value pattern in this file. Greedy runs to the LAST END marker instead: over-covering
    # a decoy costs a line of prose, under-covering one publishes a private key.
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY(?: BLOCK)?-----.*"
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
    # A signed URL carries its credential in the query string, where no `key=` and no `user:pass@`
    # exists for the other patterns to find. Reproduced end to end: an Azure SAS token in a
    # docstring reached the committed MAP.md verbatim, twice. The parameter names are anchored to a
    # `?` or `&` and the value to sixteen characters, so `sig` -- three letters -- cannot fire on
    # prose. The NAME is kept and only the value replaced, because "this talks to blob storage" is
    # exactly what the index should still say.
    re.compile(r"(?<=[?&])(?:sig|signature|x-amz-signature|awsaccesskeyid|x-goog-signature)"
               r"=([A-Za-z0-9%+/=_.~-]{16,})", re.I),
]

# The names that mean "a credential lives here". Written once and shared by the assignment
# patterns below, which had drifted -- one had gained spellings the other had not.
SECRET_WORDS = (
    # Each one a whole COMPONENT of the name, with a plural allowed. These were bare substrings
    # while `key` and `auth` beside them were carefully bounded -- the same bug, left in the words
    # nobody re-read. Measured: `self.tokenizer_config = AutoTokenizer.from_pretrained(model_name)`
    # came back as `self.tokenizer_config = <REDACTED>`, and so did `detokenize_output_text`,
    # `retokenized_batch`, `credentialing_deadline` and `secretariat_id`. Ordinary identifiers,
    # destroyed in the index the tool exists to write.
    r"(?<![A-Za-z])(?:password|passwd|pwd|secret|credential)s?(?![A-Za-z])"
    # `token` needs a component beside it, for the same reason `key` does: a bare `token` in source
    # is far more often a lexer token than a credential, and `tokens = tokenizer.encode(prompt)` is
    # the identifier family this module's own docstring says was already fixed once. The credential
    # spellings — access_token, auth_token, api_token, refresh_token — all carry one.
    r"|(?<![A-Za-z])[A-Za-z0-9]+[_-]tokens?(?![A-Za-z])"
    # ...and the same words in CamelCase, where there is no separator to anchor on: dbPassword,
    # apiToken. Case-sensitive under `(?-i:)` for the reason the `key` branch below gives.
    r"|(?-i:(?<=[a-z0-9])(?:Password|Passwd|Secret|Token|Credential)s?)(?![A-Za-z])"
    # `key` as a whole COMPONENT of the name, not the four compound spellings that were listed by
    # hand. ssh_key, signing_key, encryption_key, master_key and db_key all passed through
    # untouched, and "key" on its own is the commoner spelling. BOTH boundaries are load-bearing:
    # without the left one `monkey_patch` matches, without the right one `keyboard_layout` does,
    # and destroying ordinary configuration is the other half of this module's trade.
    # 🐛 ...but the leading component is now REQUIRED, not optional. `key` is the commonest
    # parameter name in Python, and measured against 257 real files it accounted for 70 of 129
    # destroyed lines on its own: `key=lambda p: p.stat().st_mtime` became `key=<REDACTED> p: …`,
    # `st.button("บันทึก", key="save_sn_key")` lost its widget id. `token`/`tokens` alone is the
    # same story — `tokens = tokenizer.encode(prompt)`. The credential spellings all carry another
    # component (api_key, ssh_key, AccountKey), so requiring one costs nothing on the secret side
    # and stops the single largest source of damage on the other. `password`, `secret` and
    # `credential` keep their bare form, because `password = "…"` really is one.
    r"|(?<![A-Za-z])[A-Za-z0-9]+[_-]keys?(?![A-Za-z])"
    # ...and the same component written in CamelCase, where there is no separator to anchor on:
    # AccountKey, ApiKey, PrivateKey. `(?-i:...)` turns the surrounding re.I off for this branch
    # only, because the distinction IS the case -- a capital K after a lowercase letter is a word
    # boundary, a lowercase one is the middle of `monkey`.
    r"|(?-i:(?<=[a-z0-9])Keys?)(?![A-Za-z])"
    # Word-anchored on the left, and `authentication` excluded on the right. Unanchored, `auth`
    # fires inside `oauth_flow` and `authentication_flow`, whose values are OAuth grant types.
    # `entic` covers authentication, authenticate, authenticates, authenticated, authenticator and
    # authenticity in one: only `authentication` was excluded, so a sentence saying what a gate
    # "authenticates" lost its last word. Prose is the other half of this module's trade.
    r"|(?<![A-Za-z])auth(?!ors?\b|entic|orit)"
)

# A compiled regular expression is not a credential, whatever it is called. `TOKEN_RE`,
# `TOKEN_LEAK_RE` and `SECRET_PATTERN` are the names a scanner gives its own patterns — including
# this module's — and they were being redacted out of the index of any repository that has one.
_NOT_A_CREDENTIAL_NAME = re.compile(
    r"(?:_|\b)(?:re|regex|rx|pattern|patterns|prefix|suffix|header|headers|field|fields|column|"
    r"columns|param|params|arg|args|label|labels|id|ids|name|names|type|types|kind|order|sort|"
    r"index|idx|map|maps|dict|list|set|count|len|size|fn|func|cls|class)$", re.I)

CREDENTIALED_URL = re.compile(
    # `*`, not `+`: redis://:password@host and amqp://:pass@host carry no username at
    # all, which is the normal form for both, and a one-or-more group never matched them.
    r"(?<![A-Za-z0-9_-])([a-zA-Z][a-zA-Z0-9+.-]*://[^\s:/@]*):([^\s@/]{3,})@")
# password = "...", api_key: '...', SECRET_TOKEN="..." — the value goes, the name stays.
ASSIGNED_SECRET = re.compile(
    r"((?:" + SECRET_WORDS + r")[\w-]*\s*['\"]?\s*[:=]\s*)(['\"])([^'\"]{6,})\2", re.I)
# The same assignment without quotes, which is how every .env and .ini file on earth is written.
# Requiring quotes meant DATABASE_PASSWORD=tr0ub4dor&3-horse passed through untouched. Bounded to a
# single unbroken run of characters so a prose comment ("password: ask the platform team") is not
# eaten, and to six characters so token_ttl=3600 is not either.
ASSIGNED_SECRET_BARE = re.compile(
    r"((?:" + SECRET_WORDS + r")[\w-]*\s*['\"]?\s*[:=]\s*)"
    # `(` is excluded from the value class. Without it, `AWS_SECRET = base64.b64decode("QUtJQ...")`
    # had `base64.b64decode(` captured AS the secret and replaced, leaving the real payload beside
    # a now-broken line -- a leak and a corruption from one missing character.
    # 🐛 The value class stopped at the first excluded character and the REMAINDER was printed
    # beside a `<REDACTED>` — `API_TOKEN=abcdef,Tr0ub4dorENV88` became
    # `API_TOKEN=<REDACTED>,Tr0ub4dorENV88`, which is worse than a plain miss because the marker
    # tells a reviewer the line was handled. And a value STARTING with an excluded character was
    # missed entirely: `DB_PASSWORD=#Tr0ub4dorENV99` passed through whole. The run may now begin
    # with any non-space and continue to the end of the line; `#` and `;` still terminate it only
    # when they follow whitespace, which is where a real trailing comment lives.
    # Still a single unbroken run — spanning spaces ate `password: ask the platform team for it`,
    # and prose is the other half of this module's trade — but the run may now START with an
    # excluded character and CONTAIN one. Before, the class stopped at the first `, # ; ( ) [ ] { }`
    # and the remainder was printed beside a `<REDACTED>`: `API_TOKEN=abcdef,Tr0ub4dorENV88` came
    # back as `API_TOKEN=<REDACTED>,Tr0ub4dorENV88`, which is worse than a plain miss because the
    # marker says the line was handled. And a value beginning with one was missed outright:
    # `DB_PASSWORD=#Tr0ub4dorENV99` passed through whole.
    r"(?!<REDACTED>)(\S{6,})", re.I)
# A secret-named assignment whose value is a CALL. What is inside is not knowable from here and the
# name says it is a credential, so the whole expression goes -- to the end of that line, no further.
# A credential written as XML/HTML element text. Maven `settings.xml`, Tomcat `server.xml`, .NET
# `web.config`, Spring XML and JBoss datasources all put it here, and every assignment rule above
# requires a literal `[:=]` that element syntax does not have. A whole ecosystem's config format,
# passing through untouched.
XML_SECRET = re.compile(
    r"(<\s*(?:\w+:)?(?:" + SECRET_WORDS + r")[\w.-]*\s*(?:\s[^>]*)?>)([^<>]{4,})(</)", re.I)
# The hash rocket. After `[:=]` matches the `=`, `\s*` cannot cross the `>` — so the quoted rule
# found no quote and the bare rule captured `>` alone and failed its six-character floor. This is
# how `config/database.php` is written in every Laravel app and every Rails `.rb` config.
ROCKET_SECRET = re.compile(
    r"((?:" + SECRET_WORDS + r")[\w-]*['\"]?\s*=>\s*)(['\"])([^'\"]{4,})\2", re.I)
# A YAML block scalar puts `|` or `>-` where the value would be and the value on the next line, so
# there was nothing on the key's own line to capture. Helm values.yaml is full of them.
YAML_BLOCK_SECRET = re.compile(
    r"((?:" + SECRET_WORDS + r")[\w-]*\s*:\s*[|>][-+]?[ \t]*\n)((?:[ \t]+\S.*\n?)+)", re.I)
# Space-separated forms with no `[:=]` at all: Dockerfile's legacy `ENV KEY VALUE`, `.netrc`, and
# `.pgpass`'s colon-delimited final field. `_netrc` — the Windows spelling — and `.pgpass` are in
# neither refusal list, so peek opens both.
SPACED_SECRET = re.compile(
    r"((?:^|[ \t])[\w-]*(?:" + SECRET_WORDS + r")[\w-]*[ \t]+)(\S{6,})$", re.I | re.M)
PGPASS_LINE = re.compile(r"^([^:\s]+:\d+:[^:]*:[^:]+:)(\S+)$", re.M)

ASSIGNED_SECRET_CALL = re.compile(
    r"((?:" + SECRET_WORDS + r")[\w-]*\s*['\"]?\s*[:=]\s*)"
    r"(?!<REDACTED>)([A-Za-z_][\w.]*\s*\(.*)$", re.I | re.M)

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
    """Files peek refuses outright, because a summary of them is a summary of a secret.

    🐛 `is_blocked` above carries an ANY-SEGMENT extension check and the comment inside it claims
    both functions run "the same four checks". They did not: this one tested only the last segment,
    so `backup.pem.txt`, `server.key.old` and `deploy.key.bak` — the ordinary ways a key gets copied
    aside — were blocked from the indexer and opened by `chamnan-peek`. And peek prints only the
    first eight lines, so the `-----END PRIVATE KEY-----` never reached the scrubber, the greedy
    block pattern could not match, and the header-only fallback replaced the BEGIN line alone.
    Measured on a real 2048-bit RSA key: line 1 `<REDACTED>`, lines 2 onward live key material,
    under a header that tells a reviewer the file was handled. The lists drifted apart once before
    and the comment written to stop it happening again was attached to the function that was
    already right.
    """
    name = path.name.lower()
    if name.startswith(("id_rsa", "id_dsa", "id_ecdsa", "id_ed25519")):
        return True
    stem = name.rsplit(".", 1)[0] if "." in name else name
    if any(f".{seg}" in NEVER_OPENED_SUFFIXES for seg in name.split(".")[1:]):
        return True
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


def _looks_like_a_credential_name(key):
    """False when the name's own tail says it is something other than a credential.

    Complements `_names_a_mechanism` below, which reads a curated suffix list. This one reads the
    LAST component: a name ending `_RE`, `_PATTERN`, `_HEADER` or `_ORDER` describes a regex, a
    header or an ordering, and no value it holds is a secret.
    """
    bare = re.sub(r"['\"\s:=]+$", "", (key or "").strip())
    return not _NOT_A_CREDENTIAL_NAME.search(bare)


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
    # Before the assignment rules: these forms carry no `[:=]` the assignment rules can anchor on,
    # and running them first means a value they take is not left for a looser rule to half-capture.
    text = XML_SECRET.sub(
        lambda m: m.group(0) if _names_a_mechanism(m.group(1))
        else f"{m.group(1)}{PLACEHOLDER}{m.group(3)}", text)
    text = ROCKET_SECRET.sub(
        lambda m: m.group(0) if _names_a_mechanism(m.group(1))
        else f"{m.group(1)}{m.group(2)}{PLACEHOLDER}{m.group(2)}", text)
    text = YAML_BLOCK_SECRET.sub(
        lambda m: m.group(0) if _names_a_mechanism(m.group(1))
        else f"{m.group(1)}  {PLACEHOLDER}\n", text)
    text = SPACED_SECRET.sub(
        lambda m: m.group(0)
        if _names_a_mechanism(m.group(1)) or not _looks_like_a_credential_name(m.group(1))
        or PLACEHOLDER in m.group(2)
        else f"{m.group(1)}{PLACEHOLDER}", text)
    text = PGPASS_LINE.sub(rf"\1{PLACEHOLDER}", text)
    text = ASSIGNED_SECRET.sub(
        lambda m: m.group(0)
        if _names_a_mechanism(m.group(1)) or not _looks_like_a_credential_name(m.group(1))
        else f"{m.group(1)}{m.group(2)}{PLACEHOLDER}{m.group(2)}", text)
    # Before the bare rule, which would otherwise capture the callee and leave the argument.
    text = ASSIGNED_SECRET_CALL.sub(
        lambda m: m.group(0)
        if _names_a_mechanism(m.group(1)) or not _looks_like_a_credential_name(m.group(1))
        else f"{m.group(1)}{PLACEHOLDER}", text)
    text = ASSIGNED_SECRET_BARE.sub(
        lambda m: m.group(0)
        if _names_a_mechanism(m.group(1)) or not _looks_like_a_credential_name(m.group(1))
        # An earlier, more specific rule already replaced this value. Re-matching it swallowed the
        # `<REDACTED>` and everything after: `'password' => '<REDACTED>',` collapsed to
        # `'password' =<REDACTED>`, which loses the syntax a reader needs to see what was there.
        or PLACEHOLDER in m.group(2)
        or m.group(2).lower() in SCHEME_WORDS
        else f"{m.group(1)}{PLACEHOLDER}", text)
    return text
