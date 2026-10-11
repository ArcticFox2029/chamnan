"""Which tool call would read a credential file into the session, so the hook can refuse it.

🎯 [2026-10-07] (owner's direction, 2026-10-07: "การเพิ่มความระมัดระวังในการเรียกใช้ข้อมูลสำคัญ แบบไม่ให้ llm
ได้ไป") chamnan refused credential files in its OWN commands -- `chamnan-peek` declines a real
`.env`, a kubeconfig, a private key -- while the agent's own Read tool, a `cat .env`, or a Grep aimed
at the file still put the values straight into the model's context. The redactor cannot help there:
hooks can refuse a call but cannot rewrite what a tool returns. So the refusal moves to the moment
before the call, through a PreToolUse `deny`. Verified before relying on it: in a scratch project a
`deny` stopped a planted `.env` from reaching the reply in `bypassPermissions` and `acceptEdits`, and
the documentation says it holds in every permission mode.

One list decides what counts: `redact.is_never_opened`, the same one peek uses, so the two can never
disagree about a file. A template (`.env.example`) is read as before. A command that only MOVES a
file (`cp`, `mv`, `source`, `git add`) is not a read and is not refused -- the value never reaches
the screen that way. Check 461.
"""
import re
import shlex
from pathlib import Path

import redact

# Commands that print a file they are given. A pipeline segment starting with one of these, or any
# segment with `<` reading from the file, is a read.
READERS = frozenset({
    "cat", "head", "tail", "less", "more", "bat", "batcat", "nl", "tac", "grep", "egrep", "fgrep",
    "rg", "ag", "sed", "awk", "gawk", "cut", "sort", "uniq", "strings", "xxd", "od", "hexdump",
    "base64", "diff", "jq", "yq", "type", "get-content", "gc", "view", "vim", "vi", "nano", "emacs",
    "column", "paste", "fold", "fmt", "pr", "iconv", "openssl", "keytool", "sqlite3",
})
# `git` prints file contents only through these.
GIT_READERS = frozenset({"diff", "show", "log", "blame", "grep", "cat-file"})


# 🐛 [2026-10-07] (owner, 2026-10-07: "ก็มันทำงานได้ไหมหละ ถ้าต้องเรียกใช้ข้อมูลในการทำงาน เช่น ssh")
# Measured on 19 real working commands: `cat ~/.ssh/id_rsa.pub` (a PUBLIC key, pasted onto servers)
# and `openssl x509 -in server.crt -noout -enddate` (a certificate's expiry) were refused, because
# peek's refusal list also covers public material. A public key and a certificate are published by
# design, so the guard lets them through; private keys and env files stay refused. Check 461.
PUBLIC_SUFFIXES = (".pub", ".crt", ".cer")
# `openssl` commands that only inspect public material or a connection.
OPENSSL_PUBLIC = frozenset({"x509", "s_client", "verify", "crl", "version", "ciphers", "dgst"})


# 🐛 [2026-10-07] (R52 acc4, 2026-10-07) Package-registry configs hold a token beside settings the
# work needs -- the registry URL, a scope, a proxy, a mirror. Measured: `cat ~/.npmrc`, `.pypirc`,
# `pip.conf`, `.yarnrc.yml`, `.docker/config.json` and `.m2/settings.xml` all reached the session
# with the token in clear, while `chamnan-peek` shows each with the token replaced. So such a file
# is refused only when it really carries a value the scrubber would remove, and the refusal points
# at peek: the settings stay readable, the token does not travel. A token-free `.npmrc` (just a
# `registry=` line) is read as before. Check 463.
REGISTRY_CONFIGS = frozenset({".npmrc", ".pypirc", "pip.conf", "pip.ini", ".yarnrc", ".yarnrc.yml"})
# The same idea for files whose name only means a registry config inside one directory.
REGISTRY_CONFIGS_IN = frozenset({(".docker", "config.json"), (".m2", "settings.xml"),
                                 ("pypoetry", "auth.toml"), (".bundle", "config"),
                                 (".cursor", "mcp.json"), (".vscode", "mcp.json"), (".gemini", "settings.json"),
                                 ("Claude", "claude_desktop_config.json")})
# 🐛 [2026-10-08] (R59 acc1, 2026-10-08: 24,008 secrets in MCP config files on public GitHub) An MCP
# server config keeps the server's API key in its `env` block beside the command that starts it, the
# same mix as a registry config, and `cat .mcp.json` brought the key into the session. Check 477.
MCP_CONFIGS = frozenset({".mcp.json", "mcp.json", "mcp_config.json"})
# 🐛 [2026-10-08] (R59 acc1, 2026-10-08: the s1ngularity malware enumerated exactly these files; R53
# acc1, 2026-10-08: a pod's service-account token) Where agent CLIs and cloud tools keep the user's
# sign-in -- Claude Code's `.credentials.json`, Codex's `auth.json`, Gemini's `oauth_creds.json`, gh,
# Copilot, gcloud's application-default login -- and the token Kubernetes mounts into a pod. Each was
# read into the session whole. Refused when the file really holds a token, like a registry config;
# the tool that owns the file reads it itself. Check 477.
TOOL_LOGINS_IN = frozenset({(".claude", ".credentials.json"), (".codex", "auth.json"),
                            (".gemini", "oauth_creds.json"), ("gh", "hosts.yml"),
                            ("github-copilot", "apps.json"), ("github-copilot", "hosts.json"),
                            ("gcloud", "application_default_credentials.json"), ("serviceaccount", "token"),
                            # 🐛 [2026-10-09] (R119 claudeaccount1, 2026-10-09) A remote cloned with a
                            # token in its URL, or a CI checkout's `extraheader`, keeps the credential
                            # here; refused only when the file carries one. Check 489.
                            (".git", "config"),
                            # 🐛 [2026-10-10] (R55 acc4, 2026-10-10) sops keeps age identities here, and
                            # an `AGE-SECRET-KEY-1...` line is the whole private key. Check 498.
                            ("age", "keys.txt"),
                            # 🐛 [2026-10-11] (R47 acc4, 2026-10-11: Azure CLI's token cache is plain text
                            # off Windows; Terraform keeps its registry tokens in plain JSON) Both were
                            # read whole. Check 508.
                            (".azure", "accessTokens.json"), (".azure", "msal_token_cache.json"),
                            (".terraform.d", "credentials.tfrc.json")})
# 🐛 [2026-10-11] (R1 acc4, 2026-10-11: the SSO cache holds access and refresh tokens; R8 acc4,
# 2026-10-11: kubelogin and the GKE auth plugin cache tokens on disk) Some tools keep their sign-in in
# a cache directory under hash-named files, so no (directory, file) pair above can name them: the
# AWS CLI's SSO and assumed-role caches and kubelogin's OIDC cache were read whole while
# `~/.aws/credentials` beside them was refused. Matched by the trailing directories instead, and
# refused like the files above only when the file really holds a token. Check 508.
TOOL_LOGIN_CACHES = ((".aws", "sso", "cache"), (".aws", "cli", "cache"), (".kube", "cache", "oidc-login"))
TOOL_LOGIN_NAMES = frozenset({"gke_gcloud_auth_plugin_cache"})
# 🐛 [2026-10-11] (R11 acc4, 2026-10-11: HashiCorp says local state holds secrets even when they are
# marked sensitive; R7 acc4, 2026-10-11: an `.env*` glob misses direnv's `.envrc`) Settings files that
# carry a credential among ordinary values: Terraform state and variable files, and direnv's `.envrc`,
# which exports keys for the shell. All were read whole. Refused when the file holds a value the
# scrubber would remove, with peek offered for the rest; a state file past the read cap is refused
# unread, because state is where Terraform keeps every resource's secrets. Check 509.
SETTINGS_FILE_NAMES = frozenset({".envrc"})
SETTINGS_FILE_SUFFIXES = (".tfstate", ".tfstate.backup", ".tfvars", ".tfvars.json")
_STATE_SUFFIXES = (".tfstate", ".tfstate.backup")
_REGISTRY_READ_CAP = 256 * 1024
# Lower-cased once: the directory names above are written as the tools spell them (`Claude`).
_REGISTRY_PAIRS = frozenset((d.lower(), n.lower()) for d, n in REGISTRY_CONFIGS_IN)
_TOOL_LOGIN_PAIRS = frozenset((d.lower(), n.lower()) for d, n in TOOL_LOGINS_IN)


def _is_registry_config(path):
    # Judged on the real file too when the leaf is a link or a directory-qualified name, so a
    # symlinked `.docker` directory is still `.docker` (check 466).
    for p in redact._with_resolved(path, *{n for _d, n in REGISTRY_CONFIGS_IN}):
        if (p.name.lower() in REGISTRY_CONFIGS or p.name.lower() in MCP_CONFIGS
                or (p.parent.name.lower(), p.name.lower()) in _REGISTRY_PAIRS):
            return True
    return False


def _is_tool_login(path):
    """True for a file where an agent CLI, a cloud tool or Kubernetes keeps a sign-in token."""
    for p in redact._with_resolved(path, *{n for _d, n in TOOL_LOGINS_IN}):
        if (p.parent.name.lower(), p.name.lower()) in _TOOL_LOGIN_PAIRS or p.name.lower() in TOOL_LOGIN_NAMES:
            return True
        if any(tuple(x.lower() for x in p.parent.parts[-len(t):]) == t for t in TOOL_LOGIN_CACHES):
            return True
    return False


def _is_settings_file(path):
    """True for a settings file that keeps a credential among ordinary values (see the list above)."""
    name = path.name.lower()
    return name in SETTINGS_FILE_NAMES or name.endswith(SETTINGS_FILE_SUFFIXES)


def _settings_carry_a_value(path):
    try:
        if (path.name.lower().endswith(_STATE_SUFFIXES) and path.is_file()
                and path.stat().st_size > _REGISTRY_READ_CAP):
            return True
    except OSError:
        return False
    return _registry_carries_a_secret(path)


# 🐛 [2026-10-10] (R186 acc4, 2026-10-09: shells and REPLs persist pasted inline credentials) A history
# file keeps every `export TOKEN=...` and `-H 'Authorization: ...'` typed or pasted; this workspace's
# owner's own `.zsh_history` held 5 lines the redactor changes. Refused when it carries one, like a
# registry config. A history past the read cap is refused unread: it is long enough to hold anything.
SHELL_HISTORIES = frozenset({".bash_history", ".zsh_history", ".sh_history", ".history", "fish_history",
                             "consolehost_history.txt", ".python_history", ".psql_history",
                             ".mysql_history", ".node_repl_history", ".sqlite_history", ".rediscli_history",
                             ".irb_history", ".lesshst"})
_HISTORY_READ_CAP = 1024 * 1024


def _history_carries_a_secret(path):
    try:
        if not path.is_file():
            return False
        if path.stat().st_size > _HISTORY_READ_CAP:
            return True
        text = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return False
    return redact.scrub(text) != text


# 🐛 [2026-10-10] (R39 acc4, 2026-10-10: whole-home scans find service-account JSON in ~/Downloads) A
# cloud key downloads as `<project>-<hash>.json`, so a name list cannot know it; the file says what it
# is in its first few hundred bytes. Only the head is read, and only for a .json the guard is asked
# about. Check 497.
_SA_HEAD = 8192


def _is_service_account_key(path):
    if path.suffix.lower() != ".json":
        return False
    try:
        with open(path, "rb") as fh:
            head = fh.read(_SA_HEAD)
    except (OSError, ValueError):
        return False
    return (b'"service_account"' in head and b'"private_key"' in head
            and b"PRIVATE KEY-----" in head)


def _registry_carries_a_secret(path):
    try:
        if not path.is_file() or path.stat().st_size > _REGISTRY_READ_CAP:
            return False
        text = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return False
    return redact.scrub(text) != text


# 🐛 [2026-10-07] (R60 benchmark, 2026-10-07) `grep -c '^API_TOKEN=' .env` -- asking whether a
# variable is SET -- was refused, measured in a scratch run: a count, a file name or an exit status is
# all those flags print, never a line of the file. Only the searchers get this; `cat -c` is not a thing.
_SEARCHERS = frozenset({"grep", "egrep", "fgrep", "rg", "ag"})
_NO_CONTENT_FLAGS = frozenset({"--count", "--files-with-matches", "--files-without-match", "--quiet",
                               "--silent"})


def _is_credential(token, root):
    token = token.strip().strip("'\"")
    if not token or token.startswith("-") or "=" in token and not token.startswith((".", "/")):
        return None
    if token.lower().endswith(PUBLIC_SUFFIXES):
        return None
    token = str(Path(token).expanduser()) if token.startswith("~") else token
    path = Path(token)
    if not path.is_absolute() and root is not None:
        path = Path(root) / path
    try:
        if redact.is_never_opened(path):
            return token
        if (_is_registry_config(path) or _is_tool_login(path)) and _registry_carries_a_secret(path):
            return token
        if path.name.lower() in SHELL_HISTORIES and _history_carries_a_secret(path):
            return token
        if _is_settings_file(path) and _settings_carry_a_value(path):
            return token
        if _is_service_account_key(path):
            return token
    except (OSError, ValueError):
        return None
    return None


def _words(segment, posix=True):
    # `posix=False` for PowerShell: POSIX splitting reads `\` as an escape and turns
    # `C:\Users\me\.netrc` into `C:Usersme.netrc`, a path nobody has.
    try:
        return shlex.split(segment, posix=posix)
    except ValueError:
        return segment.split()


# 🐛 [2026-10-07] (R86 acc4, 2026-10-07: measure a rule set on a foreign population) Run over every
# Bash, Read and Grep call in this project's transcripts -- 18,354 real calls -- the guard refused 10,
# and 9 were false: `grep -n "\.env" lib/tree.py` had its PATTERN read as a file, and a line inside
# a `python3 - <<'EOF'` body was judged as a command. These verbs take a program or pattern before
# their files, and a heredoc body is data. Check 465.
_PROGRAM_FIRST = frozenset({"grep", "egrep", "fgrep", "rg", "ag", "sed", "awk", "gawk", "jq", "yq"})
# Options whose next word is a value, not a file. `-e`/`-f` and their long forms also mean the
# program was given that way, so every positional after them is a file.
_TAKES_VALUE = frozenset({"-e", "-f", "-m", "-A", "-B", "-C", "-d", "-D", "-g", "-t", "-T", "-M", "-j",
                          "-v", "-F", "--regexp", "--file", "--glob", "--type", "--max-count",
                          "--context", "--after-context", "--before-context", "--expression"})
_PROGRAM_GIVEN = frozenset({"-e", "-f", "--regexp", "--file", "--expression"})
_HEREDOC = re.compile(r"<<-?[ \t]*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1[^\n]*\n(.*?)(?:\n[ \t]*\2[ \t]*(?=\n|$)|\Z)",
                      re.S)


def _segments(text):
    """The command split at `|`, `||`, `&&`, `;`, `&` and newlines that are NOT inside quotes.

    A grep pattern such as `"a\\|b"` used to be cut at its `|`, and the half after it judged as a
    command of its own (check 465)."""
    out, cur, quote, i = [], [], None, 0
    while i < len(text):
        ch = text[i]
        if quote:
            cur.append(ch)
            if ch == "\\" and quote == '"' and i + 1 < len(text):
                cur.append(text[i + 1])
                i += 1
            elif ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
            cur.append(ch)
        elif ch == "\\" and i + 1 < len(text):
            cur.append(ch + text[i + 1])
            i += 1
        elif ch in "|;&\n":
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    out.append("".join(cur))
    return out


def _without_heredoc_bodies(text):
    return _HEREDOC.sub(lambda m: m.group(0)[:m.start(3) - m.start(0)], text)


def _file_args(verb, args):
    """The arguments a command takes as FILES: for a pattern/program verb, not its first positional."""
    if verb not in _PROGRAM_FIRST:
        return args
    files, program_seen, skip = [], False, False
    for a in args:
        if skip:
            skip = False
            continue
        if a in _TAKES_VALUE:
            program_seen = program_seen or a in _PROGRAM_GIVEN
            skip = True
            continue
        if a.startswith("-"):
            program_seen = program_seen or a.split("=", 1)[0] in _PROGRAM_GIVEN
            continue
        if not program_seen:
            program_seen = True
            continue
        files.append(a)
    return files


# 🎯 [2026-10-09] (R82 acc4, 2026-10-08; R11 acc4, 2026-10-09; decided by the research skill's procedure,
# acc4 consulted: option c) Commands that print every exported key or a stored password, rather than a
# file holding one. Only the bulk forms: a named variable (`printenv PATH`) and a command run under an
# environment (`env FOO=1 cmd`) stay allowed, because blocking those would need a policy over intent.
# A short list of high-confidence hazards, not output redaction. Check 494.
ENV_DUMP = "the whole environment"
# 🐛 [2026-10-11] (R31 acc4, 2026-10-11: Docker says `compose config` output must never be stored raw)
# The same kind of bulk dump through another door: `docker compose config` prints the merged Compose
# file with every `${VAR}` filled in from `.env` and the shell, so a refused `.env` came back through it.
# `--no-interpolate` and the listing flags print no value and stay allowed. Check 511.
COMPOSE_RESOLVED = "the Compose file with its variables filled in"
_COMPOSE_SAFE_FLAGS = frozenset({"--no-interpolate", "--services", "--volumes", "--profiles", "--images",
                                 "--networks", "--hash", "-q", "--quiet", "--variables"})
# Flags that take the next word as their value, so `-f a.yml` is not read as a subcommand.
_COMPOSE_VALUE_FLAGS = frozenset({"-f", "--file", "-p", "--project-name", "--env-file", "--profile",
                                  "--project-directory", "--format", "-o", "--output", "--context", "-c"})
STORED_GIT_LOGIN = "git's stored credential"
_ENV_FILE = re.compile(r"^/proc/[^/\s]+/environ$")
_PS_LISTERS = frozenset({"get-childitem", "gci", "dir", "ls"})


def _dumps_secrets(verb, args):
    """ENV_DUMP or STORED_GIT_LOGIN when this command prints every secret at once, else None."""
    if verb == "printenv":
        return ENV_DUMP if not [a for a in args if not a.startswith("-")] else None
    if verb == "env":
        rest = [a for a in args if not a.startswith("-") and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", a)]
        return ENV_DUMP if not rest else None
    if verb in _PS_LISTERS and any(a.lower().rstrip("\\/") == "env:" for a in args):
        return ENV_DUMP
    _sub, _skip = [], False
    for a in args:
        if _skip:
            _skip = False
        elif a.startswith("-"):
            _skip = a in _COMPOSE_VALUE_FLAGS
        else:
            _sub.append(a)
    if ((verb in ("docker", "podman") and _sub[:2] == ["compose", "config"])
            or (verb in ("docker-compose", "podman-compose") and _sub[:1] == ["config"])):
        if not any(a.split("=", 1)[0] in _COMPOSE_SAFE_FLAGS for a in args):
            return COMPOSE_RESOLVED
    if verb == "git":
        positional = [a for a in args if not a.startswith("-")]
        if positional[:1] == ["credential"] and positional[1:2] in (["fill"], ["get"]):
            return STORED_GIT_LOGIN
        if positional[:1] and positional[0].startswith("credential-") and "get" in positional[1:]:
            return STORED_GIT_LOGIN
    return None


def bash_reads(command, root=None, posix=True):
    """The credential file a shell command would print, or None."""
    text = str(command or "")
    if not text.strip():
        return None
    for segment in _segments(_without_heredoc_bodies(text)):
        words = _words(segment, posix)
        if not words:
            continue
        if any(_ENV_FILE.match(w.lstrip("<")) for w in words):
            return ENV_DUMP
        # Before the wrapper loop below, which steps over a leading `env` as a prefix.
        _w0 = 0
        while _w0 < len(words) and words[_w0] in ("sudo", "command", "exec", "time"):
            _w0 += 1
        if _w0 < len(words):
            _dump = _dumps_secrets(words[_w0].rsplit("/", 1)[-1].lower(), words[_w0 + 1:])
            if _dump:
                return _dump
        # `< .env` and `<.env` feed the file to whatever runs; that is a read whatever the verb.
        for i, w in enumerate(words):
            if w == "<" and i + 1 < len(words):
                hit = _is_credential(words[i + 1], root)
                if hit:
                    return hit
            elif w.startswith("<") and len(w) > 1 and not w.startswith("<<"):
                hit = _is_credential(w[1:], root)
                if hit:
                    return hit
        start = 0
        while start < len(words) and (re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", words[start])
                                      or words[start] in ("sudo", "command", "exec", "env", "time")):
            start += 1
        if start >= len(words):
            continue
        verb = words[start].rsplit("/", 1)[-1].lower()
        args = words[start + 1:]
        if verb == "git":
            sub = next((a for a in args if not a.startswith("-")), "")
            if sub not in GIT_READERS:
                continue
            if sub == "grep":
                verb, args = "grep", args[args.index(sub) + 1:]
        elif verb == "openssl" and (args[:1] and args[0] in OPENSSL_PUBLIC):
            continue
        elif verb not in READERS:
            continue
        elif verb in _SEARCHERS and any(a in _NO_CONTENT_FLAGS or re.fullmatch(r"-[A-Za-z]*[clLq][A-Za-z]*", a)
                                        and not a.startswith("--") for a in args):
            continue
        for a in _file_args(verb, args):
            hit = _is_credential(a, root)
            if hit:
                return hit
    return None


def tool_reads(tool, tool_input, root=None):
    """The credential file this Read, Grep or Bash call would put into the session, or None."""
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    if tool == "Read":
        return _is_credential(str(tool_input.get("file_path") or ""), root)
    if tool == "Grep":
        return _is_credential(str(tool_input.get("path") or ""), root)
    if tool == "Bash":
        return bash_reads(tool_input.get("command"), root)
    # 🐛 [2026-10-09] (R124 claudeaccount1, 2026-10-09) READERS has carried `get-content`, `gc` and
    # `type` all along, and nothing ever routed the PowerShell tool here: `Get-Content` of a
    # credential file on native Windows reached the session whole. Check 488.
    if tool == "PowerShell":
        return bash_reads(tool_input.get("command"), root, posix=False)
    return None


def refusal(name):
    """The reason handed back to the model when a read is refused."""
    import mdblock
    if name == ENV_DUMP:
        return ("chamnan: this prints every exported variable, keys and tokens included, into the session, "
                "so it is not run. Ask for the one you need by name -- `printenv PATH`, `echo \"$HOME\"` -- "
                "which still works. This is a short list of bulk dumps, not a filter on what commands print.")
    if name == COMPOSE_RESOLVED:
        return ("chamnan: this prints the Compose file with every `${VAR}` filled in from `.env` and the "
                "shell, keys included, so it is not run. `docker compose config --no-interpolate` shows "
                "the same merged file with the variables as written, and `--services` lists the services.")
    if name == STORED_GIT_LOGIN:
        return ("chamnan: this prints the stored password or token in full, so it is not run. To USE the "
                "credential, run the git command that needs it (`git fetch`, `git push`); git asks its helper "
                "itself. If you need to know which helper is configured, `git config --get credential.helper`.")
    shown = mdblock.as_quoted(Path(name).name, 80)
    if _is_tool_login(Path(str(name).strip("'\""))):
        return (f"chamnan: `{shown}` is where a tool keeps its sign-in token, so it is not read into the "
                f"session. The tool that owns it reads it itself -- run that tool (claude, codex, gemini, "
                f"gh, gcloud, aws, kubectl) rather than opening the file. If you need to know what it holds, "
                f"ask the user.")
    if _is_settings_file(Path(str(name).strip("'\""))):
        return (f"chamnan: `{shown}` keeps a credential among its settings, so it is not read into the "
                f"session raw. `chamnan-peek {mdblock.as_quoted(str(name), 200)}` shows the same file with "
                f"the value replaced. To USE it, run the tool that reads this file (terraform, direnv); "
                f"it reads the file itself.")
    if _is_service_account_key(Path(str(name).strip("'\"")).expanduser()):
        return (f"chamnan: `{shown}` is a cloud service-account key, private key included, so it is not "
                f"read into the session. To USE it, point the client at the file and let it read it "
                f"(`GOOGLE_APPLICATION_CREDENTIALS={mdblock.as_quoted(str(name), 200)} <command>`); "
                f"to know which account it is, ask the user.")
    if Path(str(name).strip("'\"")).name.lower() in SHELL_HISTORIES:
        return (f"chamnan: `{shown}` is a command history and it holds a credential somebody typed or "
                f"pasted, so it is not read into the session. `grep -c <word> {mdblock.as_quoted(str(name), 200)}` "
                f"says whether a command is there without printing it; for the command itself, ask the user.")
    if _is_registry_config(Path(str(name).strip("'\""))):
        return (f"chamnan: `{shown}` carries a registry or server token, so it is not read into the session raw. "
                f"`chamnan-peek {mdblock.as_quoted(str(name), 200)}` shows the same file with the token "
                f"replaced -- registry URLs, scopes and settings stay readable. To USE the token, run the "
                f"tool that reads this file (npm, pip, twine, docker, mvn, an MCP host); it reads the file itself.")
    # 🎯 [2026-10-07] (R60 acc4, 2026-10-07: use a secret without seeing it) A refusal that only says
    # "ask the user" stops work that never needed the value in the session: a command needs the
    # value, the model does not. So the reason says how to hand the file to the program that uses
    # it -- the shell or the tool reads it, the command line carries `$NAME`, and nothing prints it.
    # 🐛 [2026-10-11] (R29 claudeaccount3, 2026-10-11: an accurate cause in an error raised agent
    # recovery from 59% to 82%) This sentence told the model that a refused `id_rsa`, `cookies.sqlite`
    # or `.git-credentials` had its "variable NAMES" listed in MAP.md, which is true only of a `.env`.
    # The variables sentence is kept for files that hold variables. Check 510.
    _leaf = Path(str(name).strip("'\"")).name.lower()
    if _leaf.startswith(".env") or _leaf.endswith(".env"):
        return (f"chamnan: `{shown}` holds credentials or a key, so it is not read into the session. "
                f"Its variable NAMES, never values, are listed under `## Configuration` in "
                f"`.chamnan/MAP.md`. To USE a value, let the program read the file itself and never print "
                f"it: `set -a; . ./.env; set +a; <command using $NAME>`, a tool's `--env-file`, or "
                f"`ssh -i <key>`. If you need to know a value itself, ask the user.")
    return (f"chamnan: `{shown}` holds credentials or a key, so it is not read into the session. To USE "
            f"it, hand the file to the program that needs it and never print it: `ssh -i <key>`, the "
            f"tool's own option for a key file, or the tool that owns the store. If you need to "
            f"know a value itself, ask the user.")
