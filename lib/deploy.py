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
import re
from collections import defaultdict

K8S_KIND = re.compile(r"^kind:\s*([A-Za-z]+)\s*$", re.M)
K8S_NAME = re.compile(r"^\s{0,4}name:\s*([\w.-]+)\s*$", re.M)
IMAGE = re.compile(r"^\s*image:\s*[\"']?([\w./-]+(?::[\w.-]+)?)[\"']?\s*$", re.M)
COMPOSE_SERVICE = re.compile(r"^  ([a-z][\w-]*):\s*$", re.M)
ANSIBLE_PLAY = re.compile(r"^-\s*(?:name|hosts):\s*(.+)$", re.M)
CI_JOB = re.compile(r"^\s{0,4}([a-z][\w-]*):\s*$", re.M)

MANIFEST_GLOBS = ("*.yaml", "*.yml")
CI_DIRS = (".github", ".gitlab-ci.yml", "ci", ".circleci")
SKIP = {".git", "node_modules", "__pycache__", ".venv", "vendor", ".terraform"}
MAX_PER_GROUP = 14
# A Secret contributes its name so the reader knows one exists; never anything under it.
NEVER_EXPAND = {"Secret", "SealedSecret"}


def _read(root):
    for pattern in MANIFEST_GLOBS:
        for path in sorted(root.rglob(pattern)):
            if any(p in SKIP for p in path.parts):
                continue
            try:
                yield path, path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue


def scan(root):
    found = {"k8s": defaultdict(set), "images": set(), "compose": set(),
             "ansible": set(), "ci": set(), "helm": set()}
    for path, text in _read(root):
        rel = str(path.relative_to(root))
        low = rel.lower()

        for kind in K8S_KIND.findall(text):
            names = K8S_NAME.findall(text)
            found["k8s"][kind].add(names[0] if names else path.stem)
        for img in IMAGE.findall(text):
            if "/" in img or ":" in img:
                found["images"].add(img)
        if path.name in ("docker-compose.yml", "docker-compose.yaml", "compose.yaml", "compose.yml"):
            body = text.split("services:", 1)[-1]
            found["compose"].update(COMPOSE_SERVICE.findall(body)[:40])
        if "/roles/" in low or path.name in ("site.yml", "site.yaml", "playbook.yml"):
            found["ansible"].add(rel)
        if any(c in low for c in CI_DIRS) or path.name in ("Jenkinsfile", ".gitlab-ci.yml"):
            found["ci"].add(rel)
        if path.name in ("Chart.yaml", "Chart.yml"):
            found["helm"].add(rel)

    for name in ("Dockerfile", "Dockerfile.*", "Jenkinsfile", "Makefile"):
        for path in root.rglob(name):
            if not any(p in SKIP for p in path.parts):
                found["ci"].add(str(path.relative_to(root)))
    return found


def render(found):
    lines = []
    k8s = found["k8s"]
    if k8s:
        total = sum(len(v) for v in k8s.values())
        lines.append(f"{total} Kubernetes object(s):")
        for kind in sorted(k8s, key=lambda k: (-len(k8s[k]), k)):
            names = sorted(k8s[kind])
            shown = ", ".join(f"`{n}`" for n in names[:MAX_PER_GROUP])
            more = f" _+{len(names)-MAX_PER_GROUP}_" if len(names) > MAX_PER_GROUP else ""
            note = "  _(names only — never their contents)_" if kind in NEVER_EXPAND else ""
            lines.append(f"- **{kind}** ({len(names)}) — {shown}{more}{note}")
    if found["compose"]:
        svc = sorted(found["compose"])
        lines.append(f"- **Compose services** ({len(svc)}) — "
                     + ", ".join(f"`{s}`" for s in svc[:MAX_PER_GROUP]))
    if found["images"]:
        img = sorted(found["images"])
        lines.append(f"- **Images** ({len(img)}) — "
                     + ", ".join(f"`{i}`" for i in img[:8])
                     + (f" _+{len(img)-8}_" if len(img) > 8 else ""))
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
