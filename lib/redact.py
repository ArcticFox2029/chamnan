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

# 🐛 Two rules in this file match on ADJACENCY alone — a secret word sitting next to a value, with
# no `=` or `:` anywhere to say an assignment is happening. That is the weakest evidence any rule
# here has, and it is what destroyed ordinary prose inside committed MAP.md files. Measured by
# running the current redactor over four cloned repositories:
#
#   class HTTPBasicAuth — Attaches HTTP Basic <REDACTED> to the given Request object.
#   _basic_auth_str(username, password) — Returns a Basic Auth <REDACTED>
#   class DefaultCredentialsError — Used to indicate that acquiring default credentials <REDACTED>
#   google/oauth2/gdch_credentials.py — Experimental GDCH credentials <REDACTED>
#   class CustomAwsSupplier — Custom AWS Security Credentials <REDACTED>
#
# The published precision figure was 100%, and it stayed 100% because the decoy corpus tested
# identifiers and config lines — not SENTENCES. MAP.md summaries are prose harvested from
# docstrings, and MAP.md is the committed, shared surface, so this is where a false positive costs
# most: the marker tells a reviewer the line was handled, which is worse than a plain miss.
#
# The discriminator is the VALUE's shape. A credential is not an ordinary word: `dXNlcjpwYXNz` has
# capitals inside it, a JWT has dots, `hunter2secret` has a digit. `Authentication`, `Supplier.`,
# `failed.` and `string.` are words. Anything past 18 letters is treated as a value regardless,
# because a lowercase run that long is not prose in these positions.
#
# Deliberately NOT applied to the assignment rules. `api_key = correcthorse` is an explicit
# assignment and a plain word there is exactly the secret; the guard is only for the two rules that
# have nothing but adjacency to go on.
# The trailing class carries `…` on purpose: summaries are clipped before they reach the index, so
# the last word of a truncated docstring arrives as `functionality.…` and stopped looking like a
# word for the sake of one character.
_PLAIN_WORD = re.compile("^[A-Za-z][a-z]{1,17}[.,;:!?)\\]\u2026\"'`]*$")


def _is_a_plain_word(value):
    """True when the captured value reads as prose rather than as a credential.

    Two shapes, both measured on real output rather than imagined. One ordinary word, clipped or
    not — `Authentication`, `Supplier.`, `functionality.…`. And anything opening with a bracket,
    which in this position is a docstring's type annotation: `private_key (Union["rsa.key…` and
    `id_token (str):` were both being redacted inside an Args: block. A credential does not begin
    with `(`, and the assignment rules still cover `password = {...}` if one ever did.
    """
    value = value or ""
    return bool(_PLAIN_WORD.match(value)) or value[:1] in "([{"


def _is_a_type_annotation(match):
    """True when what follows `password:` is a TYPE in a parameter list, not a value.

    🐛 The first version of this asked whether the value looked like a type name — alphabetic,
    capitalised, no digits — and it was wrong in BOTH directions. `password: Correcthorsebatterystaple`
    is a perfectly ordinary passphrase and walked out unredacted, which is a hole this rule opened.
    And `password: string, page: Page` still came out mangled, because TypeScript and Go spell their
    types in lower case, so the original defect survived in the languages that write it most.

    The distinguishing fact is not how the word is spelled. It is WHERE it sits: a type annotation
    lives inside a parameter list and is followed by a separator. So both must hold — an unclosed
    `(` before it on the same line, and a `,` or `)` immediately after it. A value at the end of a
    line has neither, and a dict entry has `{` rather than `(` as its nearest opener.
    """
    value = match.group(2) or ""
    if not value.rstrip().endswith((",", ")")):
        return False
    line_start = match.string.rfind("\n", 0, match.start()) + 1
    before = match.string[line_start:match.start()]
    depth_paren = before.count("(") - before.count(")")
    depth_brace = before.count("{") - before.count("}")
    depth_brack = before.count("[") - before.count("]")
    return depth_paren > 0 and depth_brace <= 0 and depth_brack <= 0


# `Authorization: Bearer <jwt>` and `Basic <base64>` — but "Basic Authentication" is a phrase, and
# this rule matched it for years because twelve letters is twelve characters.
AUTH_SCHEME_SECRET = re.compile(
    r"(?<![A-Za-z0-9_-])(?:Bearer|Basic|Token)\s+([A-Za-z0-9._~+/=-]{12,})")

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
    AUTH_SCHEME_SECRET,
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
    #
    # `passphrase` and `cred` were added after a review found both missed: `GPG_PASSPHRASE = "..."`
    # and `db_creds = "admin:..."` came back unredacted. Both are ordinary in real repositories --
    # a GPG or SSH key passphrase, and `creds` as the everyday abbreviation. `ssh_key_passphrase`
    # was caught already, but only incidentally through the `key` component beside it, which is
    # the kind of accident that stops being one the moment somebody renames a variable.
    #
    # Bounded as components like the rest, so `passphraseless` and `credible` are untouched --
    # the whole reason these are components and not substrings.
    #
    # `storepass` and `keypass` are Java's keytool flags and are single words, so the component
    # boundary that protects everything else works against them: the `pass` in `storepass` is
    # preceded by a letter and the lookbehind refuses it. Named in full instead. Measured missed:
    # `keytool -storepass hunter2 -keypass hunter2` passed through whole — a real shape in any
    # repository that signs an Android build or a JAR.
    r"(?<![A-Za-z])(?:password|passwd|pwd|passphrase|secret|credential|cred|storepass|keypass)"
    r"s?(?![A-Za-z])"
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
_YAML_BLOCK_OPENER = re.compile(r":\s*[|>][-+]?[ \t]*\n")
YAML_BLOCK_SECRET = re.compile(
    r"((?:" + SECRET_WORDS + r")[\w-]*\s*:\s*[|>][-+]?[ \t]*\n)((?:[ \t]+\S.*\n?)+)", re.I)
# Space-separated forms with no `[:=]` at all: Dockerfile's legacy `ENV KEY VALUE`, `.netrc`, and
# `.pgpass`'s colon-delimited final field. `_netrc` — the Windows spelling — and `.pgpass` are in
# neither refusal list, so peek opens both.
SPACED_SECRET = re.compile(
    r"((?:^|[ \t])[\w-]*(?:" + SECRET_WORDS + r")[\w-]*[ \t]+)(\S{6,})$", re.I | re.M)
# A command-line FLAG and its value: `-storepass hunter2`, `--password hunter2`. SPACED_SECRET
# cannot reach these because it anchors the value at end-of-line, and that anchor is not negotiable
# — it is what stops the weakest rule in this file from eating prose, which it has done before.
#
# A leading dash is the discriminator, and it is a strong one: `-storepass hunter2` is not a
# sentence anybody writes, so this rule needs no plain-word guard the way the adjacency rules do.
# Bounded to a value with no whitespace, and the flag must be the whole token, so `--password-file
# creds.txt` (a PATH, not a secret) still has to be handled by the value shape rather than by luck.
FLAG_SECRET = re.compile(
    r"((?:^|[ \t])--?[\w-]*(?:" + SECRET_WORDS + r")[\w-]*[ \t]+)(?!-)([^\s]{4,})", re.I | re.M)
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
# 🐛 `.netrc` was here and its siblings were not, so the same class of file was refused or read
# depending on which platform's spelling it used. `_netrc` is the Windows name for exactly `.netrc`;
# `.pgpass` and `pgpass.conf` are libpq's password file in its two spellings, and every line in one
# ends with the password in clear. All four are credential stores whose whole content is the secret,
# which is the property this list is for — not "a file that might contain one".
BLOCKED_NAMES = ("id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", ".htpasswd", ".netrc", "_netrc",
                 ".pgpass", "pgpass.conf",
                 "credentials", "secrets.yml", "secrets.yaml")

# The scanner's list above and this one answer different questions. The scanner should not open a
# database at all -- it indexes source, and a .sqlite is not source. peek is asked for one file by
# name, and a database's table and column names are exactly the useful answer, with no row ever
# printed. Refusing those too cost peek one of its better features for no gain. What stays refused
# is the set whose contents ARE the secret: keys, certificates, and credential files.
NEVER_OPENED_SUFFIXES = (".pem", ".key", ".pfx", ".p12", ".crt", ".cer", ".der",
                         ".jks", ".keystore", ".asc", ".gpg")


def _has_source_extension(name):
    """True when the extension names a language the index extracts symbols from.

    🐛 Used only to switch OFF the stem rule below, and nothing else. The stem rule exists so that
    `credentials.ini` is caught by a deny-list entry spelled `credentials` -- and it caught
    `credentials.py`, `credentials.ts`, `credentials.rb` and `credentials.go` with it, which is the
    commonest filename in any authentication library. google-auth-library-python lost FOUR files
    this way, including google/auth/credentials.py, the abstract base class every credential type
    in the package subclasses; 201 files indexed and the four most central absent, with no notice.
    chamnan-peek refused the same file with "its contents are credentials or a key", about 23.8KB
    of `class Credentials:` definitions.

    The discriminator is the extension, not the stem. An EXTENSIONLESS `credentials` -- which is
    what ~/.aws/credentials is, and the file the entry was written for -- or credentials.ini,
    .cfg, .json, .yaml is a credential store. `credentials.<source extension>` is a module.

    Asked of mapper rather than of a second list kept here, because a list would drift and the
    drift would be silent in the unsafe direction. Imported inside the function: mapper imports
    this module, so a top-level import would be a cycle. If it cannot be answered at all the answer
    is False, which leaves the old over-cautious behaviour exactly as it was.
    """
    if "." not in name:
        return False
    try:
        import mapper
        return ("." + name.rsplit(".", 1)[-1]) in mapper.EXT_LANG
    except Exception:
        return False


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
    return (name.endswith(BLOCKED_SUFFIXES) or name in BLOCKED_NAMES
            or (stem in BLOCKED_NAMES and not _has_source_extension(name)))


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
            or (stem in BLOCKED_NAMES and not _has_source_extension(name)))


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


# 🐛 A secret-named assignment whose value is CODE was having the code replaced. Reproduced with
# chamnan-peek on httpie:
#
#   285: default_auth_plugin = <REDACTED>       was: plugin_manager.get_auth_plugins()[0]
#   294: self.args.auth = <REDACTED>            was: AuthCredentials(
#   ws_tokens = <REDACTED> token.NEWLINE, …}    was: {token.DEDENT, token.NEWLINE, tokenize.NL}
#   soft_key_lines: <REDACTED> = set()          was: set[int]
#   print(json.dumps(x, sort_keys=<REDACTED>    was: True
#
# Those are the two lines that answer "how does httpie choose an auth plugin", which is why anyone
# ran that command. The third also shows the failure this module already calls worse than a plain
# miss: the value class is one unbroken run, so the rest of the set literal is printed beside the
# marker, telling a reviewer the line was handled.
#
# The aggressive behaviour is deliberate and documented — `AWS_SECRET = base64.b64decode("QUtJQ…")`
# must not survive, and what is inside a call is not knowable from here. So this does NOT relax it.
# When the value is an expression, the STRING LITERALS INSIDE IT are redacted instead of the whole
# thing: base64.b64decode(<REDACTED>) keeps the secret gone and the code readable, while an
# expression carrying no literal — a call, a set, a type annotation, True — has nothing to remove
# and is left alone. Strictly safer than before in both directions: nothing that used to be removed
# survives, and code that never held a secret stops being destroyed.
_CODE_EXPRESSION = re.compile(
    r"^(?:[A-Za-z_]\w*(?:\s*\.\s*\w+)*\s*[([{]|[([{]|(?:True|False|None|self)\b)")
_STRING_LITERAL = re.compile(r"""(['"])((?:\\.|(?!\1)[^\\])*)\1""")


def _redact_literals_in(expr):
    """`expr` with every quoted literal of six or more characters emptied, or None when there is
    nothing to empty — in which case the caller must leave the expression alone rather than
    replace it wholesale."""
    if not _CODE_EXPRESSION.match(expr):
        return None
    out, hit = [], False
    last = 0
    for m in _STRING_LITERAL.finditer(expr):
        if len(m.group(2)) < 6:
            continue
        hit = True
        out.append(expr[last:m.start()])
        out.append(f"{m.group(1)}{PLACEHOLDER}{m.group(1)}")
        last = m.end()
    if not hit:
        return expr                      # a valid expression holding no literal: nothing to remove
    out.append(expr[last:])
    return "".join(out)


def _looks_like_a_credential_name(key, value=None):
    """False when the name's own tail says it is something other than a credential.

    Complements `_names_a_mechanism` below, which reads a curated suffix list. This one reads the
    LAST component: a name ending `_RE`, `_PATTERN`, `_HEADER` or `_ORDER` describes a regex, a
    header or an ordering, and no value it holds is a secret.
    """
    bare = re.sub(r"['\"\s:=]+$", "", (key or "").strip())
    if not _NOT_A_CREDENTIAL_NAME.search(bare):
        return True
    # 🐛 The tail decided alone, so ~50 ordinary endings — `id`, `type`, `name`, `field` — exempted
    # the value whatever it was. Reproduced end to end through `bin/chamnan-peek --find`:
    # `api_secret_id = "AKIAIOSFODNN7EXAMPLE1234"` and `db_password_type = "tr0ub4dor3horsebattery"`
    # printed in full (R12 agent 2). The exemption is still needed — `secret_name` and
    # `api_key_path` genuinely name things, and redacting those is the noise that gets a redactor
    # switched off — so the name still decides unless the VALUE settles it.
    return _value_overrides_the_name(value)


# A value that no name should be trusted against: nothing whose tail says "this holds a path" or
# "this holds a type" ever holds THIS. Long, mixed, and not a word or a path — the same evidence
# the adjacency rules use, applied in the other direction.
_CREDENTIAL_SHAPED = re.compile(r"^[A-Za-z0-9+/=_\-.]{16,}$")


def _value_overrides_the_name(value):
    """Whether the VALUE is credential-shaped enough to ignore a reassuring key name."""
    v = (value or "").strip().strip("\"'").strip(",;)]}\"' ")
    if not _CREDENTIAL_SHAPED.match(v) or "/" in v or v.startswith("."):
        return False
    # A path, a hyphenated phrase and a dotted module name are all long and mixed; a credential is
    # the one that carries both letters and digits with no separator doing the work.
    if _is_a_plain_word(v) or v.count("-") >= 2 or v.count(".") >= 2:
        return False
    return any(c.isdigit() for c in v) and any(c.isalpha() for c in v)


def _names_a_mechanism(key, value=None):
    """True when the key is describing HOW a credential is handled, not holding one.

    🐛 It read the key and nothing else, so ~50 ordinary tails — `name`, `id`, `type`, `field`,
    `path` — exempted the value whatever it was. Reproduced end to end through
    `bin/chamnan-peek --find`: `api_secret_id = "AKIAIOSFODNN7EXAMPLE1234"` and
    `db_password_type = "tr0ub4dor3horsebattery"` printed in full (R12 agent 2).
    
    The exemption is still right and still needed — `secret_name = "the-name-of-my-secret"` and
    `api_key_path = "/etc/keys/prod.pem"` genuinely name things, and redacting those is the noise
    that gets a redactor switched off. So the name still decides, unless the VALUE settles it.
    """
    tail = key.rstrip(": =\t").lower().rsplit("_", 1)[-1].rsplit("-", 1)[-1]
    if tail not in NAMING_SUFFIXES:
        return False
    return not _value_overrides_the_name(value)


# 🐛 [2026-09-04, R14 agent 2 finding 02, verified before acting] A value that continued past a
# space was redacted only up to that space, and the remainder was printed beside the placeholder:
# `aws_secret_key: AKIA1234 EXTRA5678` came back as `aws_secret_key: <REDACTED> EXTRA5678`. That is
# worse than a plain miss, and the module says so about the identical shape a few rules up — the
# marker tells a reviewer the line was handled while half the credential is still on it.
#
# Extending the value across spaces is what the history already tried and reverted, because it ate
# `password: ask the platform team for it`. So neither: the placeholder swallows FOLLOWING runs only
# while they are credential-SHAPED, and stops at the first word-shaped one.
#
# Measured before landing, on 496 real lines in this repository that carry a secret word and an
# assignment: zero would have anything additional consumed. The prose corpus the history was
# protecting ("ask the platform team for it", "not set in this environment", "String, page Page")
# is untouched, because none of those tokens carry a digit or the length that mixed case needs.
_CREDENTIAL_SHAPED = re.compile(r"^[A-Za-z0-9+/=_\-]{8,}$")


def _looks_like_more_credential(token):
    """Is this whitespace-separated run more of the secret, or the start of a sentence?"""
    if not _CREDENTIAL_SHAPED.match(token):
        return False
    has_digit = any(c.isdigit() for c in token)
    has_upper = any(c.isupper() for c in token)
    has_lower = any(c.islower() for c in token)
    # A digit beside letters is the common credential alphabet. Mixed case with no digit needs
    # length as well, or ordinary CamelCase identifiers in prose would qualify.
    return (has_digit and (has_upper or has_lower)) or (has_upper and has_lower and len(token) >= 12)


def _swallow_trailing_credential_runs(text, start):
    """How many characters after `start` are more of the same credential. 0 when the next run is
    prose, which is the common case and the one the space boundary exists to protect."""
    end = start
    while True:
        gap = re.match(r"[ \t]+", text[end:])
        if not gap:
            return end - start
        run = re.match(r"[^\s]+", text[end + gap.end():])
        if not run or not _looks_like_more_credential(run.group(0)):
            return end - start
        end += gap.end() + run.end()


def _value_is_the_key_itself(key_part, value):
    """Whether the value is just the key's own name — a label, never a credential.

    🐛 `"s_secrets": "Secrets"` in this repository's own committed translation table was redacted:
    an explicit assignment whose key carries a secret word, which is the strongest evidence the
    assignment rules have and normally right (`api_key = correcthorse` IS the secret). It is wrong
    for exactly one shape, and the shape is narrow enough to name: a value that is the key spelled
    as a word. A translation table, an enum, a form label and a column heading all look like this,
    and nobody has ever set a password to the name of the field holding it.

    Deliberately not a general softening of the assignment rules — a plain-word value there is
    still redacted, because that is where a weak password actually lives.
    """
    # Stripped of quotes AND of the punctuation a value carries in real source: `"Secrets",` is
    # what the bare rule captures, trailing comma included, and an earlier version of this checked
    # `isalpha()` on that and answered False — the guard was written, wired into both rules, and
    # still did nothing. Its own test caught it.
    word = value.strip().strip("\"'").strip(",;:)]}\"' ").lower()
    if not word or not word.isalpha():
        return False
    return word in re.sub(r"[^a-z]+", " ", key_part.lower()).split()


def scrub(text):
    """Every string that leaves chamnan for a written file goes through this."""
    if not text:
        return text
    for pattern in PATTERNS + LATE_PREFIXES:
        # A pattern with one group keeps everything outside it: "Bearer <REDACTED>" stays readable
        # as an Authorization header while the credential goes. Groupless patterns replace whole.
        if pattern.groups == 1:
            # Same position in the order, one extra question asked. See _is_a_plain_word.
            if pattern is AUTH_SCHEME_SECRET:
                text = pattern.sub(
                    lambda m: m.group(0) if _is_a_plain_word(m.group(1))
                    else m.group(0).replace(m.group(1), PLACEHOLDER), text)
            else:
                text = pattern.sub(lambda m: m.group(0).replace(m.group(1), PLACEHOLDER), text)
        else:
            text = pattern.sub(PLACEHOLDER, text)
    text = CREDENTIALED_URL.sub(rf"\1:{PLACEHOLDER}@", text)
    # Before the assignment rules: these forms carry no `[:=]` the assignment rules can anchor on,
    # and running them first means a value they take is not left for a looser rule to half-capture.
    text = XML_SECRET.sub(
        lambda m: m.group(0) if _names_a_mechanism(m.group(1), m.group(2))
        else f"{m.group(1)}{PLACEHOLDER}{m.group(3)}", text)
    # `=>` is not optional in ROCKET_SECRET — it is the operator the rule exists to read, and the
    # pattern cannot match a document that does not contain those two characters. The word list in
    # front of it is large, so the engine walks the whole document looking for a hit that is
    # impossible. `scrub` runs once over the entire map — 273 KB on a four-project tree — so the
    # literal test is one scan against many.
    #
    # This is a pre-filter, never a narrowing: the guard is implied by the pattern itself, so no
    # input that used to be redacted stops being redacted. Verified against the recall corpus
    # (38 secrets, 30 decoys) before and after — identical results, not merely a similar score.
    if "=>" in text:
        text = ROCKET_SECRET.sub(
            lambda m: m.group(0) if _names_a_mechanism(m.group(1), m.group(2))
            else f"{m.group(1)}{m.group(2)}{PLACEHOLDER}{m.group(2)}", text)
    # 🐛 The first version of this gate tested `"|" in text or ">" in text`, which is TRUE on any
    # markdown document — a table uses `|` and a blockquote uses `>` — so it skipped nothing and the
    # commit that introduced it claimed a saving it did not deliver: 67 ms still spent per render on
    # the real map. A gate has to test the STRUCTURE the pattern needs, not one character out of it.
    #
    # What YAML_BLOCK_SECRET actually requires is a colon, then a block scalar indicator, then a
    # newline. That cannot be faked by a table row.
    if _YAML_BLOCK_OPENER.search(text):
        text = YAML_BLOCK_SECRET.sub(
            lambda m: m.group(0) if _names_a_mechanism(m.group(1), m.group(2))
            else f"{m.group(1)}  {PLACEHOLDER}\n", text)
    text = SPACED_SECRET.sub(
        lambda m: m.group(0)
        # 🐛 The next FLAG is not this flag's value: `tool --password --verbose` means no password
        # was given on the command line at all, and redacting `--verbose` is pure noise in exactly
        # the output a reader is scanning for real findings. Pre-existing; found while adding the
        # CLI-flag rule beside this one.
        if m.group(2).startswith("-") else m.group(0)
        if _names_a_mechanism(m.group(1), m.group(2)) or not _looks_like_a_credential_name(m.group(1), m.group(2))
        or PLACEHOLDER in m.group(2) or _is_a_plain_word(m.group(2))
        else f"{m.group(1)}{PLACEHOLDER}", text)
    text = FLAG_SECRET.sub(
        lambda m: m.group(0) if PLACEHOLDER in m.group(2)
        # The next FLAG is not this flag's value. `tool --password --verbose` means the password
        # was not given on the command line at all; redacting `--verbose` would be pure noise.
        # A lookahead in the pattern was tried first and let this through, so it is asserted here.
        or m.group(2).startswith("-")
        # A flag naming a FILE that holds the secret is not the secret. `--password-file creds.txt`
        # and `-storepass:file x.txt` name a path the reader may need; redacting it hides which
        # file to go and protect.
        or m.group(1).rstrip().endswith("-file") or "/" in m.group(2) or m.group(2).endswith(".txt")
        else f"{m.group(1)}{PLACEHOLDER}", text)
    text = PGPASS_LINE.sub(rf"\1{PLACEHOLDER}", text)
    text = ASSIGNED_SECRET.sub(
        lambda m: m.group(0)
        if _names_a_mechanism(m.group(1), m.group(3)) or not _looks_like_a_credential_name(m.group(1), m.group(3))
        or _value_is_the_key_itself(m.group(1), m.group(3))
        else f"{m.group(1)}{m.group(2)}{PLACEHOLDER}{m.group(2)}", text)
    # Before the bare rule, which would otherwise capture the callee and leave the argument.
    text = ASSIGNED_SECRET_CALL.sub(
        lambda m: m.group(0)
        if _names_a_mechanism(m.group(1), m.group(2)) or not _looks_like_a_credential_name(m.group(1), m.group(2))
        else f"{m.group(1)}{_redact_literals_in(m.group(2)) or PLACEHOLDER}", text)
    text = ASSIGNED_SECRET_BARE.sub(
        lambda m: m.group(0)
        if _names_a_mechanism(m.group(1), m.group(2)) or not _looks_like_a_credential_name(m.group(1), m.group(2))
        # An earlier, more specific rule already replaced this value. Re-matching it swallowed the
        # `<REDACTED>` and everything after: `'password' => '<REDACTED>',` collapsed to
        # `'password' =<REDACTED>`, which loses the syntax a reader needs to see what was there.
        or PLACEHOLDER in m.group(2)
        or m.group(2).lower() in SCHEME_WORDS
        or (m.group(1).rstrip().endswith(":") and _is_a_type_annotation(m))
        or _value_is_the_key_itself(m.group(1), m.group(2))
        else f"{m.group(1)}{_redact_literals_in(m.group(2)) or PLACEHOLDER}"
        + " " * 0, text)
    # Applied after the substitution above rather than inside it, because the amount to swallow is
    # decided from the text FOLLOWING the match and a `sub` callback cannot consume beyond its own
    # span. Walks the result, and at each placeholder removes any credential-shaped runs that
    # follow it — see _swallow_trailing_credential_runs.
    out, pos = [], 0
    while True:
        at = text.find(PLACEHOLDER, pos)
        if at < 0:
            out.append(text[pos:])
            break
        stop = at + len(PLACEHOLDER)
        out.append(text[pos:stop])
        pos = stop + _swallow_trailing_credential_runs(text, stop)
    return "".join(out)


def emit(*args, **kwargs):
    """`print`, with every string argument scrubbed first. Meant to SHADOW the builtin.

    🐛 Three commands — `chamnan-env`, `chamnan-timeline`, `chamnan-impact` — printed the bodies of
    committed files straight to stdout with no redaction, while the SessionStart hook scrubbed the
    same stores. That is the shape that has produced five findings running: one store, several
    readers, and only some of them guarded. An agent runs these commands, so their stdout lands in
    a session's context exactly like the injected block does.

    Scrubbing at each `print` call was the obvious fix and is the wrong one: it is a rule every
    future print has to remember, and the misses are silent. A module-level `print = redact.emit`
    makes the guarded path the DEFAULT one, so a print added next year is safe without its author
    knowing this note exists.

    Non-string arguments are left alone — a caller printing an int or a Path means it, and coercing
    everything to str here would change what those commands output.
    """
    return _print(*(scrub(a) if isinstance(a, str) else a for a in args), **kwargs)


# Captured before any module shadows the name, so `emit` still reaches the real builtin.
_print = print


def _speak_utf8():
    """Make this process write UTF-8 on stdout and stderr, whatever the machine's code page says.

    🐛 Every chamnan command writes em dashes, and this repository's own corpus is largely Thai.
    Python encodes text output with `locale.getpreferredencoding()`, which is UTF-8 on macOS and
    Linux and the machine's ANSI code page on Windows -- so on a Windows console or pipe an em
    dash became `?` and Thai became a row of them. Measured in CI: `chamnan-report`'s usage table
    lost every ` — ` separator, and the checks that count them failed there and nowhere else.

    Done once, here, because `redact.emit` is already the single print every command routes
    through -- putting it in each command is the shape of fix this project has had to un-forget
    eight times. `errors="replace"` rather than strict: a command that cannot render one character
    must still deliver the rest of its output.

    Silent when the streams cannot be reconfigured (Python 3.6 and earlier, or a replaced stream
    object): the fallback is the old behaviour, which is what happens today.
    """
    import sys
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


_speak_utf8()
