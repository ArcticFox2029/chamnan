"""What this system is deployed as — read from the manifests rather than from the code.

On a platform of any size the question "what actually runs, and where" is not answerable from the
source. It lives in Kubernetes manifests, Ansible roles, Compose files and CI pipelines, none of
which chamnan reads as code because none of them are code. Left out, an agent asked to change a
service's memory limit or find which CronJob writes a report has to go hunting through a deploy
tree that is often larger than the application.

So the manifests are read for their SHAPE only: kinds and names, roles and playbooks, image names,
compose services, pipeline files. Never their data — a Kubernetes Secret contributes its name and
nothing else, and the redactor still runs over everything written out.

YAML is matched with regexes rather than parsed. There is no YAML parser in the standard library,
and shipping one to read four fields would trade the plugin's only real deployment advantage — no
dependencies — for a marginal gain in precision.
"""
import mdblock
import pathlib
import re
from collections import defaultdict
import tokens
import tree

K8S_KIND = re.compile(r"^kind:\s*([A-Za-z]+)\s*$", re.M)
# `[\w.-]` deliberately does not match `{{ include "of-service.fullname" . }}` -- a
# templated name is not a name, and the fallback above says so in words instead.
K8S_NAME = re.compile(r"^\s{0,4}name:\s*([\w.-]+)\s*$", re.M)
IMAGE = re.compile(r"^\s*image:\s*[\"']?([\w./-]+(?::[\w.-]+)?)[\"']?\s*$", re.M)
# Any indent, not exactly two. Two spaces is the common style and was taken for the rule; a
# compose file written with four -- equally valid, and what several generators emit -- produced
# zero services, and an empty catalog looks identical to a repo that simply has no compose file.
# The depth is decided per file below, from the shallowest key actually present under `services:`.
COMPOSE_SERVICE = re.compile(r"^([ \t]+)([a-z][\w-]*):\s*$", re.M)
# Helm's `image:` is a mapping, not a string -- `repository:` and `tag:` on the lines under it --
# which is how most charts declare the thing IMAGE exists to find, and none of them were found.
HELM_IMAGE = re.compile(r"^(\s*)image:\s*$\n(?:\1\s+\w+:.*$\n)*?\1\s+repository:\s*"
                        r"[\"']?([\w./-]+)[\"']?\s*$(?:\n(?:\1\s+\w+:.*$)?)*", re.M)
HELM_TAG = re.compile(r"^\s+tag:\s*[\"']?([\w.-]+)[\"']?\s*$", re.M)
ANSIBLE_PLAY = re.compile(r"^-\s*(?:name|hosts):\s*(.+)$", re.M)
CI_JOB = re.compile(r"^\s{0,4}([a-z][\w-]*):\s*$", re.M)

MANIFEST_GLOBS = ("*.yaml", "*.yml")
# Matched as whole path COMPONENTS, never as substrings. "ci" inside a substring matches
# services/pricing, apps/ios/Sources/Specific and charts/civic -- and it did, which is how an
# Ansible inventory under inventories/ci/ came out labelled as a CI pipeline.
CI_DIRS = (".github", ".circleci", "ci", ".ci", ".buildkite", ".woodpecker")
CI_FILES = ("Jenkinsfile", ".gitlab-ci.yml", ".travis.yml", "azure-pipelines.yml",
            "bitbucket-pipelines.yml", "cloudbuild.yaml", "cloudbuild.yml")
# Ansible is more than roles: an inventory, its group_vars and host_vars, and the playbooks at the
# top of the tree are all part of how the system is deployed, and none of them sit under /roles/.
ANSIBLE_DIRS = ("roles", "inventories", "inventory", "group_vars", "host_vars", "playbooks")
ANSIBLE_FILES = ("site.yml", "site.yaml", "playbook.yml", "playbook.yaml", "ansible.cfg",
                 "requirements.yml", "hosts.yml", "hosts.yaml")
SKIP = {".git", "node_modules", "__pycache__", ".venv", "vendor", ".terraform"}
# 🐛 [2026-09-06] A count cap and `as_quoted`'s per-entry length cap bound quantity and size
# separately, and nothing bounded their PRODUCT. `catalogs.py` diagnosed exactly this for routes
# and configuration and replaced the count cap with a token budget; this module renders into the
# same index from the same two primitives and was never given the fix. Measured: eight kinds of
# twenty objects with 73-character names -- what a GitOps monorepo reaches once environment and
# region suffixes are on the name -- rendered 4,059 tokens, above the whole 3,000-token default
# `index_token_budget`, with MAX_PER_GROUP reporting nothing wrong. And it does not fail on its
# own: mapper concatenates this into the very text `tokens.fits(index, budget)` measures, so one
# oversized Deployment section forces the directory roll-up onto the entire repository's Quick
# Index (R10 acc3).
#
# The count cap stays as a floor against a wall of very short names; the token budget is now the
# primary limit. One eighth of the configured index budget: this is a supplement to the Quick
# Index, not a replacement for it, and routes already take two fifths.
MAX_PER_GROUP = 14
DEPLOY_BUDGET_SHARE = 0.125
# A Secret contributes its name so the reader knows one exists; never anything under it.
NEVER_EXPAND = {"Secret", "SealedSecret"}


# 🐛 A path's components are tested RELATIVE to the repository root, never absolute. Testing the
# absolute path means one directory ABOVE the checkout named `vendor`, `node_modules`, `build`,
# `dist` or `.venv` skips every file in the repository -- and each of these renderers returns "" on
# an empty result, so whole sections simply vanish with no hedge. `assets.scan` already tested
# `rel.parts`, which is what made the asymmetry findable. Two harms beyond the missing sections:
# `mapper.scan` is unaffected, so the index and the catalogues then disagree about the same
# repository; and the unignored-`.env` warning goes silent, which is the false-calm direction.
def _rel_parts(path, root):
    """`path`'s components below `root`, or its own components when it is not below root."""
    try:
        return pathlib.Path(path).relative_to(root).parts
    except (ValueError, TypeError):
        return pathlib.Path(path).parts


def _read(root):
    # Nested checkouts are excluded here for the same reason as in mapper and catalogs: a checkout
    # inside a checkout is somebody else's code. This module is the one that made the consequence
    # visible -- a Streamlit app's architecture map listed a Namespace, an Ingress and 31 container
    # images belonging to a logistics test corpus that happened to be checked out under it.
    from mapper import _nested_repo_dirs
    nested = _nested_repo_dirs(root)
    for pattern in MANIFEST_GLOBS:
        for path in tree.matching(root, pattern):
            if any(p in SKIP for p in _rel_parts(path, root)):
                continue
            if nested and any(parent.resolve() in nested for parent in path.parents):
                continue
            try:
                yield path, path.read_text(encoding="utf-8-sig", errors="replace")
            except OSError:
                continue


# A List is a wrapper `kubectl get -o yaml` produces, not an object anyone deployed. Its own kind
# used to be indexed -- with the filename as its name, since a List carries none -- while every
# real object inside it stayed invisible.
K8S_WRAPPERS = {"List"}
K8S_NESTED_KIND = re.compile(r"^\s*-?\s*kind:\s*([A-Za-z]+)\s*$", re.M)
K8S_NESTED_NAME = re.compile(r"^\s*name:\s*([\w.-]+)\s*$", re.M)
DOC_SPLIT = re.compile(r"^---\s*$", re.M)


_BLOCK_KEY = re.compile(r"^([ \t]*)(?:-[ \t]+)?([A-Za-z_][\w-]*):[ \t]*$", re.M)


def _metadata_spans(doc):
    """Character ranges covered by a `metadata:` block, so a name can be required to live in one.

    🐛 A Kubernetes object's name is `metadata.name` and nothing else, but the name pattern was
    matched against the WHOLE document and the first hit after `kind:` was taken. Two orderings,
    both legal YAML and both real, therefore put a Secret's own value where the index prints a name:

        kind: Secret          kind: Secret
        stringData:           metadata:
          name: AKIA…           generateName: db-cred-
        metadata:             stringData:
          name: db-creds        name: sk-proj-…

    The first because `stringData` simply came first; the second because `generateName` is a real
    field and leaves no `metadata.name` to find at all. Both reproduced end to end into MAP.md,
    under the caption "names only — never their contents" and the line "a Secret contributes its
    name and nothing under it". A caption that is false is worse than no caption: it is the reason
    a reader does not check.

    A block's extent without a YAML parser: `metadata:` at indent N owns every following line
    indented deeper than N, and ends at the first non-blank line that is not. That is enough for
    both the top-level and the inside-a-List case, and a manifest with no `metadata:` now yields no
    name and falls back to the filename -- which is the safe direction.

    It also fixes a quieter wrong answer: `spec.template.spec.containers[].name` was eligible too,
    so a Deployment could be indexed under a container's name rather than its own.
    """
    spans, lines, pos = [], doc.splitlines(keepends=True), 0
    starts = []
    for line in lines:
        m = _BLOCK_KEY.match(line)
        if m and m.group(2) == "metadata":
            starts.append((len(m.group(1)), pos))
        elif starts and line.strip():
            indent = len(line) - len(line.lstrip(" \t"))
            while starts and indent <= starts[-1][0]:
                spans.append((starts.pop()[1], pos))
        pos += len(line)
    spans.extend((start, len(doc)) for _, start in starts)
    return spans


def _pair_in(doc, kind_re, name_re, fallback):
    """Give every `kind:` the name that belongs to IT, by position within its own document.

    Each kind used to be handed `names[0]` -- the first name anywhere in the whole file. A
    three-document manifest holding a ConfigMap, a Deployment and a Service therefore indexed all
    three under whichever name came first, and the index said so with no hedge. An invented entry
    is worse here than a missing one: a reader can act on it.

    And the name has to come from a `metadata:` block -- see `_metadata_spans` for the secret a
    document-wide match printed into the index.
    """
    kinds = [(m.start(), m.group(1)) for m in kind_re.finditer(doc)]
    meta = _metadata_spans(doc)
    names = [(m.start(), m.group(1)) for m in name_re.finditer(doc)
             if any(a <= m.start() < b for a, b in meta)]
    out = []
    for i, (pos, kind) in enumerate(kinds):
        nxt = kinds[i + 1][0] if i + 1 < len(kinds) else len(doc)
        after = [n for p, n in names if pos < p < nxt]
        if after:
            out.append((kind, after[0]))
            continue
        # `metadata:` above `kind:` is unusual but perfectly legal YAML, so a kind with nothing
        # after it looks backwards for a name belonging to the same object before giving up.
        prev = kinds[i - 1][0] if i else 0
        before = [n for p, n in names if prev <= p < pos]
        out.append((kind, before[-1] if before else fallback))
    return out


def _k8s_pairs(text, fallback):
    out = []
    for doc in DOC_SPLIT.split(text):
        pairs = _pair_in(doc, K8S_KIND, K8S_NAME, fallback)
        if len(pairs) == 1 and pairs[0][0] in K8S_WRAPPERS:
            # Only inside a wrapper is an indented `kind:` read. Elsewhere it would index the
            # `subjects:` of every RoleBinding as objects of their own.
            out.extend(p for p in _pair_in(doc, K8S_NESTED_KIND, K8S_NESTED_NAME, fallback)
                       if p[0] not in K8S_WRAPPERS)
            continue
        out.extend(p for p in pairs if p[0] not in K8S_WRAPPERS)
    return out


def _compose_services(body):
    """Service keys at the shallowest indent present, whatever that indent is."""
    hits = COMPOSE_SERVICE.findall(body)
    if not hits:
        return []
    depth = min(len(indent.expandtabs(2)) for indent, _ in hits)
    return [name for indent, name in hits
            if len(indent.expandtabs(2)) == depth][:40]


def _helm_images(text):
    """`image:` as a mapping — Helm's convention — assembled back into repository:tag.

    A templated value (`image: "{{ .Values.image.repository }}"`) is deliberately still skipped.
    It is not an image name, and recording it would put a string nothing can pull into the index.
    """
    out = set()
    for m in HELM_IMAGE.finditer(text):
        repo = m.group(2)
        if "/" not in repo and "." not in repo:
            continue
        tag = HELM_TAG.search(m.group(0))
        out.add(f"{repo}:{tag.group(1)}" if tag else repo)
    return out


def scan(root):
    found = {"k8s": defaultdict(set), "images": set(), "compose": set(),
             "ansible": set(), "ci": set(), "helm": set(),
             # Every path this section speaks for. The assets inventory subtracts it, because a
             # deployment manifest is not payload and telling a reader "do not read these to
             # understand the system" about the Ansible tree is the opposite of true.
             "claimed": set()}
    for path, text in _read(root):
        rel = str(path.relative_to(root).as_posix())
        low = rel.lower()
        claimed_before = _claim_count(found)

        # A Helm template's name comes from values at render time, so there is no name in the
        # file to read. Falling back to the FILENAME invented one: templates/deployment.yaml gave
        # `Deployment: deployment`, hpa.yaml gave `PodDisruptionBudget: hpa`, and both sat in the
        # index looking exactly like the fourteen real object names beside them.
        fallback = "(name from chart values)" if "{{" in text else path.stem
        for kind, name in _k8s_pairs(text, fallback):
            found["k8s"][kind].add(name)
        for img in IMAGE.findall(text):
            if "/" in img or ":" in img:
                found["images"].add(img)
        found["images"].update(_helm_images(text))
        if path.name in ("docker-compose.yml", "docker-compose.yaml", "compose.yaml", "compose.yml"):
            body = text.split("services:", 1)[-1]
            found["compose"].update(_compose_services(body))
        parts = {q.lower() for q in path.relative_to(root).parts[:-1]}
        if parts & set(ANSIBLE_DIRS) or path.name.lower() in ANSIBLE_FILES:
            found["ansible"].add(rel)
        elif parts & set(CI_DIRS) or path.name in CI_FILES:
            found["ci"].add(rel)
        if path.name in ("Chart.yaml", "Chart.yml"):
            found["helm"].add(rel)
        if _claim_count(found) > claimed_before:
            found["claimed"].add(rel)

    # Read by name rather than by glob: none of these are YAML, so the manifest sweep above never
    # sees them, and ansible.cfg is the file that says where the whole inventory lives.
    for name, group in (("Dockerfile", "ci"), ("Dockerfile.*", "ci"), ("Jenkinsfile", "ci"),
                        ("Makefile", "ci"), ("ansible.cfg", "ansible")):
        for path in tree.matching(root, name):
            if not any(p in SKIP for p in _rel_parts(path, root)):
                rel = str(path.relative_to(root).as_posix())
                found[group].add(rel)
                found["claimed"].add(rel)
    return found


def _claim_count(found):
    return (sum(len(v) for v in found["k8s"].values()) + len(found["images"])
            + len(found["compose"]) + len(found["ansible"]) + len(found["ci"])
            + len(found["helm"]))


def _within(names, cap, budget):
    """`names` truncated so the rendered list fits `budget` tokens as well as `cap` entries.

    Returns (rendered_names, kept). The per-name render is what `as_quoted` produces, so the cost
    counted here is the cost that lands in the index rather than the raw name's.
    """
    kept, _ = tokens.fill_by_budget(
        list(names), lambda n: f"`{mdblock.as_quoted(n, 80)}`", budget, cap)
    return kept, len(kept)


def render(found):
    lines = []
    k8s = found["k8s"]
    # One budget for the whole section, spent down kind by kind -- a per-kind budget would let
    # eight kinds cost eight times what the section is allowed, which is the same product the
    # count cap failed to bound.
    left = tokens.section_budget(DEPLOY_BUDGET_SHARE)
    if k8s:
        total = sum(len(v) for v in k8s.values())
        lines.append(f"{total} Kubernetes object(s):")
        for kind in sorted(k8s, key=lambda k: (-len(k8s[k]), k)):
            names = sorted(k8s[kind])
            # Kubernetes names, compose service names and image references are all read out
            # of repository YAML and written into MAP.md, which is committed and injected. Same
            # neutralisation the route, env and schema catalogues take: folded onto one line, with
            # the backticks that would close this span removed. See lib/mdblock.as_quoted.
            rendered, kept = _within(names, MAX_PER_GROUP, left)
            left -= sum(tokens.estimate(r) for r in rendered)
            shown = ", ".join(rendered)
            more = f" _+{len(names)-kept}_" if len(names) > kept else ""
            note = "  _(names only — never their contents)_" if kind in NEVER_EXPAND else ""
            lines.append(f"- **{kind}** ({len(names)}) — {shown}{more}{note}")
    if found["compose"]:
        svc = sorted(found["compose"])
        rendered, kept = _within(svc, MAX_PER_GROUP, max(left, 120))
        left -= sum(tokens.estimate(r) for r in rendered)
        lines.append(f"- **Compose services** ({len(svc)}) — " + ", ".join(rendered)
                     + (f" _+{len(svc)-kept}_" if len(svc) > kept else ""))
    if found["images"]:
        img = sorted(found["images"])
        lines.append(f"- **Images** ({len(img)}) — "
                     + ", ".join(f"`{mdblock.as_quoted(i, 80)}`" for i in img[:8])
                     + (f" _+{len(img)-8}_" if len(img) > 8 else ""))
    # The lists below are each ONE line with a flat cap of 8, and that is deliberate rather than the
    # same oversight: their product IS bounded -- 8 entries of at most 80 characters is about 200
    # tokens, four such lines under 800 in the worst case. What was unbounded above is the number of
    # KINDS, which a CRD can add to without limit, so eight kinds of fourteen names multiplied out
    # past the whole index budget while each individual cap looked reasonable.
    for key, label in (("ansible", "Ansible"), ("helm", "Helm charts"), ("ci", "Pipelines")):
        items = sorted(found[key])
        if items:
            lines.append(f"- **{label}** ({len(items)}) — "
                         + ", ".join(f"`{i}`" for i in items[:8])
                         + (f" _+{len(items)-8}_" if len(items) > 8 else ""))
    if not lines:
        return ""
    return "\n".join(["## Deployment", "",
                      "What runs, from the manifests rather than the code. Shape only — a Secret "
                      "contributes its name and nothing under it.", ""] + lines + [""])
