"""Render the feature sections of every translated README from one shared table.

Why a generator rather than 32 hand-written pages: the sections below are the same table of the
same rows in every language, and the failure mode of writing them by hand is a row that exists in
some languages and not others -- which nobody would ever notice, because nobody reads all 32. The
prose at the top of each page stays hand-written; only these sections are rendered, and they are
spliced in ahead of the "read this before installing" heading that every page already has.

Run from anywhere: `python3 docs/i18n/build_sections.py`. It rewrites the pages in place and is
idempotent. A language missing from STRINGS is skipped and named, never half-rendered.

The no-numbers rule in MAINTAINING.md applies to everything here: not one digit, including the
Python version floor, which lives in the English README and is linked to instead.
"""
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent

# The row labels, in order, per group. Each language supplies the same keys.
GROUPS = [
    ("understand", ["index", "impact", "datamodel", "api", "config", "deploy", "stored"]),
    ("remember", ["state", "resume", "memory", "threads"]),
    ("reuse", ["procedures", "tools", "workflows"]),
    ("evolve", ["milestones", "candidates", "environments", "report"]),
]
COMMANDS = ["map", "report", "impact", "timeline", "peek", "promote", "candidates", "env", "age"]
BIN = {"map": "chamnan-map", "report": "chamnan-report", "impact": "chamnan-impact",
       "timeline": "chamnan-timeline", "peek": "chamnan-peek", "promote": "chamnan-promote",
       "candidates": "chamnan-candidates", "env": "chamnan-env", "age": "chamnan-age"}
WRITES = ["w_map", "w_state", "w_sessions", "w_memory", "w_threads", "w_skills", "w_milestones",
          "w_config"]
WRITE_KEY = {"w_map": "`MAP.md`", "w_state": "`STATE.md`", "w_sessions": "`sessions/`",
             "w_memory": "`memory/`", "w_threads": "`threads/`",
             "w_skills": "`skills/` · `tools/`", "w_milestones": "`milestones.md`",
             "w_config": "`config.json`"}
SAFETY = ["s_network", "s_source", "s_daemon", "s_secrets", "s_plugin"]

SKILLS = ("`/chamnan:bootstrap` `/chamnan:remap` `/chamnan:resume` `/chamnan:remember` "
          "`/chamnan:milestone` `/chamnan:capture` `/chamnan:promote` `/chamnan:report`")


def render(t):
    """One language's sections. `t` is that language's string table."""
    out = [f"## {t['h_features']}", "", t["features_intro"], ""]
    for group, keys in GROUPS:
        out += [f"### {t['h_' + group]}", "", "| | |", "|---|---|"]
        for k in keys:
            out.append(f"| **{t[k + '_n']}** | {t[k]} |")
        out.append("")
    out += [t["features_close"], "", f"## {t['h_commands']}", "", t["commands_intro"], "",
            "| | |", "|---|---|"]
    for c in COMMANDS:
        out.append(f"| `{BIN[c]}` | {t['c_' + c]} |")
    out += ["", f"{t['skills_intro']} {SKILLS}", "", f"## {t['h_writes']}", "",
            t["writes_intro"], "", "| | |", "|---|---|"]
    for w in WRITES:
        out.append(f"| {WRITE_KEY[w]} | {t[w]} |")
    out += ["", t["writes_hook"], "", t["writes_nolearn"], "", f"## {t['h_safety']}", "",
            "| | |", "|---|---|"]
    for s in SAFETY:
        out.append(f"| **{t[s + '_n']}** | {t[s]} |")
    # What it works with, and how to set it up for each. Added because the translated pages said
    # what chamnan IS and never said what it runs against -- a reader who does not read English had
    # no way to learn that it is not tied to one model, one operating system or one agent.
    out += ["", f"## {t['h_works']}", "", t["works_intro"], "", "| | |", "|---|---|"]
    for w in ("llm", "os", "agents", "hermes"):
        out.append(f"| **{t['works_' + w + '_n']}** | {t['works_' + w]} |")
    out += ["", f"## {t['h_setup2']}", "", t["setup_intro"], "", "| | |", "|---|---|"]
    for w in ("plugin", "file2"):
        out.append(f"| **{t['setup_' + w + '_n']}** | {t['setup_' + w]} |")
    out += ["", t["setup_more"], ""]
    out += ["", f"## {t['h_req']}", "", t["req"], "", t["req_note"], "",
            f"## {t['h_off']}", "", t["off"], ""]
    return "\n".join(out)


def splice(path, block):
    """Replace everything from the fourth `## ` heading's predecessor onwards -- that is, insert
    before it -- removing any block a previous run put there."""
    text = path.read_text(encoding="utf-8")
    heads = [m.start() for m in re.finditer(r"^## ", text, re.M)]
    if len(heads) < 4:
        return False
    # A previous run's block sits between heading 3 (install) and the "read before installing"
    # heading. Cut back to the install section, then splice fresh.
    marked = "<!-- generated: build_sections.py -->"
    if marked in text:
        start = text.index(marked)
        end = text.index("## ", text.index("<!-- /generated -->"))
        text = text[:start] + text[end:]
        heads = [m.start() for m in re.finditer(r"^## ", text, re.M)]
    at = heads[3]
    new = text[:at] + marked + "\n\n" + block + "\n<!-- /generated -->\n\n" + text[at:]
    path.write_text(new, encoding="utf-8")
    return True


def main():
    from i18n_strings import STRINGS
    done, skipped = [], []
    for path in sorted(HERE.glob("README.*.md")):
        code = path.name[len("README."):-len(".md")]
        t = STRINGS.get(code)
        if not t:
            skipped.append(code)
            continue
        if splice(path, render(t)):
            done.append(code)
    print(f"rendered {len(done)}: {', '.join(done)}")
    if skipped:
        print(f"no string table yet, left alone: {', '.join(skipped)}")
    # The rule the English README advertises, enforced rather than stated.
    bad = []
    for path in sorted(HERE.glob("README.*.md")):
        stray = [w for w in re.findall(r"\S*\d\S*", path.read_text(encoding="utf-8"))
                 if "ArcticFox2029" not in w]
        if stray:
            bad.append(f"{path.name}: {stray}")
    if bad:
        print("DIGITS LEAKED INTO A TRANSLATED PAGE:\n  " + "\n  ".join(bad))
        return 1
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    sys.exit(main())
