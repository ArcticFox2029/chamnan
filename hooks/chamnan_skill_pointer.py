#!/usr/bin/env python3
"""PreToolUse hook — when a command starts a kind of work, name the procedure that covers it.

ENFORCES: memory/rules/check-for-a-skill-first-and-extend-it-not-fork-it.md
ENFORCES: memory/rules/how-a-blocked-decision-gets-made.md
# That rule's own text says its content lives in `working_a_research_round.md` and that the
# copy actually read was always the skill's — so routing to the skill IS the machine for it., and the session-start
block's own instruction to read the matching procedure before starting that kind of task.

🐛 [2026-09-18] (R26.5) The instruction has been in the block every session since the workspace existed, and
the procedures are good, and they are still not opened at the moment they apply. The reason is not
mystery: a procedure is named at session start, and the work begins hours and a hundred thousand
tokens later. R19 measured the tier this belongs to — NIOSH ranks administrative controls fourth of
five *because they rely on people following rules* — and found that the two remedies this project
reaches for, remembering and re-reading, are the two with evidence against them. What moves the
number is a control that acts at the moment of the command.

`chamnan_file_pointer.py` already does this for a FILE being opened. This is the same idea for a
COMMAND being run, and it holds itself to the same four rules: silent when it has nothing, at most
three times per procedure per session, never noisy, and never about chamnan's own reading of itself.

**The mapping lives in the skills, not here.** Each procedure declares `COVERS: <pattern> | <pattern>`
in its own header, so a new procedure arrives with its triggers and this file never changes. A table
in the hook would be the defect this repository records most often — a set maintained in one place
and forgotten in the other.

🐛 [2026-09-18] (R19 agent 4, 2026-09-18) "Once per procedure per session" assumed a session is short. Measured on this
repository's own session today, from `.chamnan/logs/commands.jsonl` and the old
`logs/skill_pointer_seen.json`: 387 tool commands over 8.0 hours (07:12 → 15:12), the pointer spoke
3 times — one procedure each — all before 08:30, then silence for roughly 360 commands. The
heaviest three hours of work, 271 of the 387 commands, got no pointer at all. This is the identical
defect already found and fixed in the sibling hook, `chamnan_scratch_watch.py` (its `NUDGE_AT` /
`NUDGE_AGAIN_AT` comment there, "one ask per session, at call 10, and then silence"): a budget keyed
to "session" instead of to elapsed work goes quiet exactly when a long session most needs it. Fixed
the same way here — a procedure may speak up to three times per session, mirroring the sibling's
own re-ask marks so the two numbers cannot drift apart.

READS: .chamnan/skills/*.md via COVERS: within 1500 except README.md
READS: .chamnan/skills/*.md via FIRST: within 1500 except README.md
READS: .chamnan/logs/skill_pointer_nudge/*.json via { at least 1
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import workspace as ws  # noqa: E402

# Mirrors chamnan_scratch_watch.NUDGE_AGAIN_AT (its resume nudge fires again at 150 and 400 calls).
# Kept as a literal rather than an import: that module's top-level pulls in `redact` and other
# PostToolUse-only weight this frequently-run PreToolUse hook should not pay for on every command
# (see the dated note further down about two PreToolUse hooks on Bash doubling the cost -- it is
# referenced, not repeated, because a bug marker in a cross-reference reads as a second defect
# record to anything that counts them). The two
# constants must move together by hand.
NUDGE_AGAIN_AT = (150, 400)

# One state file per session (own directory — this hook does not share chamnan_scratch_watch.py's
# `logs/nudge`, because its entries are keyed per PROCEDURE, not one counter for the whole session).
NUDGE_DIR = "logs/skill_pointer_nudge"
NUDGE_MAX_AGE = 2 * 24 * 3600     # a session older than this is over; its marker is dead weight


def _covers(wsdir):
    """Every procedure that declares what it covers, as (stem, [patterns])."""
    out = []
    base = wsdir / "skills"
    if not base.is_dir():
        return out
    for p in sorted(base.glob("*.md")):
        try:
            head = p.read_text(encoding="utf-8", errors="replace")[:1500]
        except OSError:
            continue
        for line in head.splitlines():
            if line.startswith("COVERS:"):
                pats = [x.strip() for x in line[len("COVERS:"):].split("|") if x.strip()]
                if pats:
                    out.append((p.stem, pats))
                break
    return out


def _first_steps(path):
    """What the procedure says to do first — declared by the procedure, never guessed.

    🐛 The first version picked the first few bullet lines it found, and on both skills tested it
    returned the gotchas rather than the steps: a reminder that quotes the wrong three lines is
    worse than one that quotes none, because it reads as the summary. A procedure knows its own
    opening moves; it declares them on a `FIRST:` line and this prints that or nothing.
    """
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:1500]
    except OSError:
        return []
    for line in head.splitlines():
        if line.startswith("FIRST:"):
            return [x.strip() for x in line[len("FIRST:"):].split("·") if x.strip()]
    return []


# 🐛 [2026-09-23] (self-measured) Caught live: `git commit` whose MESSAGE mentioned `2dspeak/` raised the Live2D
# procedure. A commit message, a heredoc body and a `-m` string are prose ABOUT work, not the work,
# and matching them is how a pointer earns its way into being ignored — the same "noise gets a
# guard switched off" reasoning the nudge budget below is built on.

def _the_work_itself(command):
    """`command` with the prose stripped out: what is being RUN, not what is being said about it."""
    try:
        import cmdtext
        return cmdtext.without_prose(command, drop_heredoc=True)
    except Exception:              # noqa: BLE001 — matching the raw command is the safe fallback
        return command

def _nudge_path(wsdir, session_id):
    """One state file per session, never one shared dict keyed by session id — the same reasoning
    as chamnan_scratch_watch.py's `_nudge_path`: a shared file is a read-modify-write with no lock,
    and two writers on one repository is normal rather than exotic. This hook does not reuse that
    module's file, because its entries are keyed per procedure rather than one counter."""
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in str(session_id))[:64] or "none"
    return wsdir / NUDGE_DIR / f"{safe}.json"


def _nudge_read(wsdir, session_id):
    try:
        d = json.loads(_nudge_path(wsdir, session_id).read_text(encoding="utf-8-sig"))
    except (UnicodeDecodeError, OSError, json.JSONDecodeError, RecursionError):
        return {"calls": 0, "procs": {}}
    # Valid JSON of the wrong shape is not a missing file.
    return d if isinstance(d, dict) else {"calls": 0, "procs": {}}


def _nudge_write(wsdir, session_id, entry):
    if ws.read_only():
        return
    p = _nudge_path(wsdir, session_id)
    try:
        ws.atomic_write_text(p, json.dumps(entry))
        for old in p.parent.glob("*.json"):
            if old != p and time.time() - old.stat().st_mtime > NUDGE_MAX_AGE:
                old.unlink()
    except OSError:
        pass


# 🐛 [2026-09-18] (R19 agent 4, 2026-09-18) The division is the owner's, set 2026-09-16 and written in two skills and in the
# operating agent's own definition: this session picks the work, X-rays it and designs the A/B; the
# CUT is dispatched to `engineer-operate` on sonnet; this session judges the result. On 2026-09-18 I
# made every cut of the day myself on opus — two hooks, three checks, three tools, a redactor change
# — and none of them was dispatched. Not once. The rule was read at session start and the edits
# happened hours later, which is the placement problem R19 measured rather than a mystery.
#
# So the reminder moves to the moment of the edit. It does NOT block: a one-line change, a comment,
# or the operating agent's own work would be worse for a refusal, and a hook that blocks editing is
# a hook that gets switched off within a day.
_SURGERY = ("/Work-Mode/chamnan/lib/", "/Work-Mode/chamnan/bin/", "/Work-Mode/chamnan/hooks/")


# 🎯 [R26, 2026-09-18] The Fogg Behavior Model in one line: a behaviour needs motivation, ability AND
# a prompt at the same moment — "no prompt, no behavior", however high the first two are. Measured
# here that day: `chamnan-recall` answers "does this exist already" in under a second, it was called
# TWICE, and the session wrote three tools that duplicated things the store would have named.
# Capra & Pérez-Quiñones is the same result from the user's side: people browse rather than search
# even when search is faster, because browsing costs no query formulation. Sourcegraph Cody's answer
# is the shape adopted here — automatic retrieval is the DEFAULT and asking by hand is the override,
# not the other way round.
#
# So this does not remind anyone to search. It searches, and puts the answer in front of the write.
def _what_this_repo_already_has(payload):
    """Run the store query FOR a new tool file, and show what it names. "" when nothing matches."""
    raw = (payload.get("tool_input") or {}).get("file_path") or ""
    rel = raw.replace("\\", "/")
    if "/.chamnan/tools/" not in rel or not rel.endswith((".py", ".sh")):
        return ""
    if Path(raw).exists():          # editing something that exists is not the case this is for
        return ""
    stem = Path(raw).stem
    words = [w for w in re.split(r"[-_]", stem) if len(w) > 2][:4]
    if not words:
        return ""
    root = ws.hook_root(payload)
    # 🐛 [2026-09-22] (self-measured) This built the path from the repository directory plus two
    # hard-coded segments naming the author's own checkout layout, rather than from where the
    # plugin is installed. Anywhere else that path does not exist, the guard
    # below returned "" every time, and the whole feature was dead for every user who is not the
    # author — silently, because returning "" is also what "nothing matched" looks like.
    # The plugin knows where it lives: this file is in `hooks/`, so `bin/` is its sibling.
    recall = Path(__file__).resolve().parents[1] / "bin" / "chamnan-recall"
    if not recall.is_file():
        return ""
    try:
        # The argv is one list literal with `*words` spread into it, not `[...] + words`: a
        # concatenation is a BinOp, and the sweep that asserts every subprocess call runs git or
        # this interpreter cannot read the head of a BinOp, so it reports the site as executing
        # something unknown. And `text=True` alone decodes with the platform's preferred encoding,
        # which is not UTF-8 everywhere this ships.
        out = subprocess.run([sys.executable, str(recall), *words], cwd=str(root),
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=20).stdout
    except Exception:
        return ""
    lines = [ln for ln in out.splitlines() if ln.strip()]
    if not lines or "0 of" in lines[0]:
        return ""
    head = ["chamnan: before writing `%s` — the store was asked for you:" % Path(raw).name]
    head += ["  " + ln.strip()[:130] for ln in lines[:7]]
    head.append("  (this ran automatically; `chamnan-recall <words>` is the manual form)")
    return "\n".join(head)


UI_SUFFIXES = (".tsx", ".jsx", ".vue", ".svelte")
# A stem this short is a word, not a component name, and matching on it would fire on anything.
MIN_STEM = 3


def _ui_component_already_here(payload):
    """A new UI component whose name the index already knows, else "".

    The most-reported complaint about coding agents is that they "create duplicate code or write
    custom code for pre-existing functions instead of integrating". In UI work that is the same
    `Button`, `Modal` or `Card` written a fourth time, and chamnan is the only thing installed that
    already holds every symbol in the repository.

    **Exact stem, case-insensitive, and nothing cleverer.** `Btn` against `Button` is a similarity
    judgement, and a similarity judgement without a model is a false-positive machine -- which is
    the detector shape this project has recorded fifteen times. A name that matches exactly is
    evidence; a name that looks a bit like another is not.

    Only on a file that does NOT exist yet. Editing a component is not the case this is for.
    """
    raw = (payload.get("tool_input") or {}).get("file_path") or ""
    if not raw or not raw.lower().endswith(UI_SUFFIXES):
        return ""
    if Path(raw).exists():
        return ""
    stem = Path(raw).stem
    if len(stem) < MIN_STEM or not stem[:1].isalpha():
        return ""
    root = ws.hook_root(payload)
    wsdir = ws.workspace(root)
    mp = wsdir / "MAP.md"
    try:
        if not mp.is_file() or mp.stat().st_size > 4_000_000:
            return ""
        text = mp.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""
    low = stem.lower()
    hits = []
    for m in re.finditer(r"(?m)^## `([^`]+)`$", text):
        other = m.group(1)
        if Path(other).stem.lower() == low and Path(other).name != Path(raw).name:
            hits.append(other)
        elif Path(other).stem.lower() == low:
            hits.append(other)
    if not hits:
        # Not a file of that name -- a SYMBOL of that name, which is how a component defined
        # inside a shared file is found.
        for m in re.finditer(r"(?m)^- `([A-Za-z_][A-Za-z0-9_]*)\(", text):
            if m.group(1).lower() == low:
                sec = text.rfind("\n## `", 0, m.start())
                owner = text[sec:sec + 200].split("`")[1] if sec >= 0 else ""
                if owner:
                    hits.append("%s (as `%s`)" % (owner, m.group(1)))
                break
    if not hits:
        return ""
    named = ", ".join("`%s`" % h for h in hits[:3])
    more = "" if len(hits) <= 3 else " and %d more" % (len(hits) - 3)
    return ("chamnan: this repository already has `%s` — %s%s. Reuse or extend it rather than "
            "writing a second one, or pick a name that says how this one differs."
            % (stem, named, more))


# 🐛 [2026-09-19] (self-measured), from the full gate run of this date. This hook emitted four `additionalContext` payloads and ran none of them through
# the redactor — the one hook in the family that did not, while every sibling has since
# 2026-09-06. Scrub is the credential half; `for_a_terminal` is the control-character half, and it
# has to reach the TEXT: `json.dumps` escapes every non-ASCII code point to `\uXXXX`, which no
# character filter matches and which Claude Code decodes straight back on the other side.
#
# `redact` is imported HERE rather than at module scope, and that is the whole reason this was put
# off. Measured on this machine, five runs, after `workspace` is already imported (which this hook
# pays for anyway): **20.5 ms marginal**, tight across runs. This is a PreToolUse hook on every Bash
# command, so at module scope that is 20.5 ms every command, forever, including the large majority
# of commands where the hook says nothing at all. Inside the one function that writes, it is paid
# only when there is something to write. The cost argument was real; it was an argument about
# WHERE, not about whether.
# The payload for THIS process, so the six `_emit` sites below can reach the turn claim without
# threading it through six signatures. One hook process handles exactly one tool call, so a module
# global is the whole lifetime of the value -- and `_emit` is called from paths that run before
# `wsdir` is computed, which a parameter would have to skip.
_CALL = {}


def _emit(text):
    """The one place this hook writes to stdout. Scrubbed, then control-stripped, then serialised.

    Gated on `turn.claim`: three PreToolUse hooks run for one tool call, each its own process, and
    before this gate whichever reached stdout first won by accident of code order. The claim fails
    OPEN -- see `lib/turn.py` -- so the worst outcome is the behaviour this replaced.
    """
    import redact
    if _CALL:
        try:
            import turn
            if not turn.claim(_CALL, ws.workspace(ws.hook_root(_CALL))):
                return
        except Exception:
            pass          # never let the coordinator's own failure silence a notice
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": redact.for_a_terminal(redact.scrub(text))}}))


# 🐛 [2026-09-19] (self-measured) A `git checkout -- <directory>` was run to undo ONE file a tool had mangled, and
# it discarded every uncommitted change under that directory — four files of work that had no
# commit behind them yet. The class was already recorded in four places: two gotchas in
# `working_fixing_a_finding.md` and two "X-ray the blast radius" references in the skills. It
# happened anyway, which is this repository's own measured finding about rules: the ones that break
# are the ones with no machine.
#
# So the control moves to the moment of the command, which is the only place it can act — the
# operation is irreversible the instant it runs, and there is nothing to inspect afterwards. It
# does not block: it says how many files with uncommitted work sit inside the path, and lets the
# caller decide. A count is what was missing, not permission.
_DESTRUCTIVE = (
    ("git checkout --", "checkout -- discards every uncommitted change under the path"),
    ("git restore", "restore overwrites the working tree from the index or a commit"),
    ("git reset --hard", "reset --hard throws away every uncommitted change in the tree"),
    ("git clean", "clean deletes untracked files outright"),
    ("git stash drop", "stash drop cannot be undone once the ref is gone"),
    ("git stash clear", "stash clear deletes every stash"),
)


def _about_to_discard(command, root):
    """A line naming what an irreversible git command is about to take, or ''.

    Counts only what is actually AT RISK — files git reports as modified, staged or untracked —
    because a path holding a hundred clean files and one dirty one is a one-file decision.
    """
    # 🐛 [2026-09-19] (self-measured) This matched the whole command line, so the WORDS of a
    # destructive command sitting inside a heredoc body tripped it — it fired while this session was
    # writing a note ABOUT such a command, with nothing destructive being run. It is advisory, so it
    # blocked nothing; the cost is that a warning built to stop the reader skimming taught them to
    # skim it. Everything from the first heredoc operator on is the document being written, not the
    # command being run, so only the part before it is examined.
    _cmd = re.split(r"<<-?\s*['\"]?\w", command, maxsplit=1)[0]
    _hit = next((why for frag, why in _DESTRUCTIVE if frag in _cmd), "")
    if not _hit:
        return ""
    # `git -C <dir>` makes git read that directory's config, and a directory chamnan does not own
    # is a directory that can choose what git runs. Asked before the call, never after.
    try:
        if not ws.git_can_speak_for(root):
            return ""
    except Exception:            # noqa: BLE001 — a guard must never be why a command fails
        return ""
    try:
        out = subprocess.run(["git", "-C", str(root), "status", "--porcelain"],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=10)
    except Exception:            # noqa: BLE001 — a guard must never be why a command fails
        return ""
    if out.returncode != 0:
        return ""
    dirty = [ln[3:] for ln in out.stdout.splitlines() if ln.strip()]
    if not dirty:
        return ""
    return ("chamnan: %s. %d file(s) in this repository currently carry uncommitted work.\n"
            "  Name the exact paths instead of a directory, or commit first — this is not "
            "recoverable afterwards.\n  %s" % (_hit, len(dirty), ", ".join(dirty[:6])))


def _surgery_belongs_to_the_operator(payload):
    """Editing the package's own source is step 4, and step 4 has an owner."""
    raw = (payload.get("tool_input") or {}).get("file_path") or ""
    if not raw or not any(part in raw.replace("\\", "/") for part in _SURGERY):
        return 0
    # The operating agent edits these files too; it must not be told to dispatch itself.
    if os.environ.get("CLAUDE_AGENT_NAME") or os.environ.get("CLAUDE_SUBAGENT"):
        return 0
    _emit("chamnan: this is the CUT, and the cut is step 4 — `engineer-operate` (sonnet) makes it, "
          "this session X-rays and judges. `.chamnan/skills/working_choosing_and_proving_a_change.md`. "
          "Hand it the sites the x-ray named and the A/B; never ask it whether to cut.")
    return 0


def _repeat_notice(payload):
    """"this failed here before" — or "" almost every time, which is the point.

    Never blocks and never rewrites the command: `chamnan_agent_result.py` states the rule for
    every hook in this package, and a notice that changes what runs is a decision belonging to the
    person typing it.
    """
    try:
        import gotcha
        root = ws.hook_root(payload)
        wsdir = ws.workspace(root) if root else None
        if wsdir is None or not wsdir.is_dir():
            return ""
        tool = payload.get("tool_name") or ""
        inp = payload.get("tool_input") or {}
        subj = (inp.get("command") or inp.get("file_path") or inp.get("path") or "") \
            if isinstance(inp, dict) else ""
        if not gotcha.might_repeat(wsdir, tool, subj):
            return ""
        import mdblock
        import redact
        hit = gotcha.about_to_repeat(wsdir, tool, redact.scrub(str(subj))[:300])
        if not hit:
            return ""
        count, err, when = hit
        return (f"chamnan: this exact command has failed here {count} times, most recently "
                f"{str(when)[:10]} — `{mdblock.as_quoted(err, 120)}`. Same command, same error; "
                f"nothing is blocked.")
    except Exception:              # noqa: BLE001 — a notice is never worth a failed tool call
        return ""


def _outside_the_checkout(payload):
    """🔴 The highest-severity rule in the store, with a machine behind it at last.

    `lib/boundary.py` carries the reasoning and the incident. First of every notice here because it
    is the only one where being wrong is not a revert — and a return, because nothing this hook has
    to say afterwards matters more than "that is not ours to write".
    """
    try:
        import boundary
        return boundary.advice(payload.get("tool_name") or "",
                               payload.get("tool_input") or {}, ws.hook_root(payload))
    except Exception:              # noqa: BLE001 — a notice is never worth a failed tool call
        return ""

def _running_right_now(payload):
    """"that file is executing" — the edit that lands in the middle of a running program.

    `lib/inuse.py` carries the two incidents. Said before the lesson notice, because a lesson about
    the code matters less than the fact that the code is being read from disk as it runs.
    """
    try:
        import inuse
        return inuse.advice(payload.get("tool_name") or "",
                            payload.get("tool_input") or {}, ws.hook_root(payload))
    except Exception:              # noqa: BLE001 — a notice is never worth a failed tool call
        return ""

def _the_lesson_recorded_here(payload):
    """"this place already records a lesson" — the 4,144 nobody could reach.

    `lib/bugnotes.py` carries the measurement. Said on Edit, where the lesson can still change the
    cut, and on a full Write, where it is about to be destroyed.
    """
    try:
        import bugnotes
        return bugnotes.advice(payload.get("tool_name") or "",
                               payload.get("tool_input") or {}, ws.hook_root(payload))
    except Exception:              # noqa: BLE001 — a notice is never worth a failed tool call
        return ""

def _the_others_in_the_set(payload):
    """"this text is also in N files beside it" — the most-recorded failure here, with a search.

    `lib/siblings.py` carries the reasoning and the bounds. It names them and stops: whether the
    others need the same cut is a judgement, and this package does not make judgements.
    """
    try:
        import siblings
        return siblings.advice(payload.get("tool_name") or "",
                               payload.get("tool_input") or {}, ws.hook_root(payload))
    except Exception:              # noqa: BLE001 — a notice is never worth a failed tool call
        return ""

def _wrong_shape(payload):
    """"you are running this script without the flag it says it needs" — or "".

    The complement to `_repeat_notice`: that one reads what FAILED, this one reads what the script
    about to run declares about itself. Today's three lost hours were all exit-0 commands that did
    less than intended, which a failure log cannot see by construction. `lib/canonical.py` carries
    the reasoning; nothing is blocked and nothing is rewritten.
    """
    try:
        import canonical
        root = ws.hook_root(payload)
        command = (payload.get("tool_input") or {}).get("command") or ""
        return canonical.advice(command, root)
    except Exception:              # noqa: BLE001 — a notice is never worth a failed tool call
        return ""

def _long_read_notice(payload):
    """The bulk-read notice, from the module that owns it. "" when it has nothing to say."""
    import io as _io
    import contextlib as _ctx
    try:
        import importlib.util as _ilu
        spec = _ilu.spec_from_file_location(
            "chamnan_bulk_read_notice",
            str(Path(__file__).resolve().parent / "chamnan_bulk_read_notice.py"))
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception:
        return ""
    buf = _io.StringIO()
    try:
        # It reads stdin and prints; give it the payload and take what it printed.
        import json as _json
        _stdin, sys.stdin = sys.stdin, _io.StringIO(_json.dumps(payload))
        try:
            with _ctx.redirect_stdout(buf):
                mod.main()
        finally:
            sys.stdin = _stdin
    except Exception:
        return ""
    out = buf.getvalue().strip()
    if not out:
        return ""
    try:
        return _json.loads(out)["hookSpecificOutput"]["additionalContext"]
    except Exception:
        return ""


def _edit_will_not_survive(payload):
    """One sentence when an edit to this path is going to be thrown away, else "".

    Ranked above everything else this hook says, and above everything the other two PreToolUse
    hooks say, because it is the only notice where the whole edit is wasted rather than merely
    duplicated or under-informed. `hooks.json` puts this hook first for that reason.

    Once per (session, path). A file being edited repeatedly is the normal shape of work, and a
    notice on every edit of it is the one people learn to scroll past -- the lesson
    `_environment_notice` already records about `kubectl --context prod`.

    Deliberately NOT a gate. chamnan does not block; see `chamnan_scratch_watch._environment_notice`
    on why `permissionDecision` is not trusted here. Somebody editing a generated file on purpose,
    to test what the generator will overwrite, is doing something legitimate.
    """
    raw = (payload.get("tool_input") or {}).get("file_path") or ""
    if not raw:
        return ""
    root = ws.hook_root(payload)
    wsdir = ws.workspace(root)
    if not wsdir.is_dir():
        return ""
    session = str(payload.get("session_id") or "")
    entry = _nudge_read(wsdir, session)
    seen = entry.setdefault("doomed", [])
    key = str(raw).replace("\\", "/")
    if key in seen:
        return ""
    # 🐛 [2026-09-22] (self-measured) The path is recorded whatever the verdict, not only when it
    # is bad. Recording only the bad ones left the COMMON case -- an ordinary file, edited
    # repeatedly, which is the normal shape of work -- paying a `git check-ignore` subprocess on
    # every single Edit: median 33.5 ms against 0.5 ms for a file answered by its own header. The
    # expensive path was the one taken most often, which is backwards.
    #
    # The trade, stated rather than hidden: a file that BECOMES ignored mid-session is not
    # re-judged. That needs somebody to edit `.gitignore` and then keep editing the same file, and
    # the case that actually matters -- a new file created under an ignored directory -- is a new
    # path and is judged normally.
    try:
        import survives
        why = survives.verdict(root, key)
    except Exception:
        return ""
    seen.append(key)
    del seen[:-400]
    _nudge_write(wsdir, session, entry)
    return ("chamnan: " + why) if why else ""


def main():
    try:
        payload = json.load(sys.stdin)
        payload = payload if isinstance(payload, dict) else {}
    except Exception:
        return 0
    global _CALL
    _CALL = payload
    _tool = payload.get("tool_name") or ""
    _outside = _outside_the_checkout(payload)
    if _outside:
        _emit(_outside)
        return 0
    if _tool in ("Edit", "Write", "NotebookEdit"):
        _doomed = _edit_will_not_survive(payload)
        if _doomed:
            _emit(_doomed)
            return 0
    if _tool == "Write":
        _already = _what_this_repo_already_has(payload) or _ui_component_already_here(payload)
        if _already:
            _emit(_already)
            return 0
    # 🔴 The lesson comes FIRST of the edit notices: a sibling sweep tells you where else to cut,
    # but a recorded gotcha may tell you not to cut at all.
    if _tool in ("Edit", "Write", "NotebookEdit"):
        _live = _running_right_now(payload)
        if _live:
            _emit(_live)
    if _tool in ("Edit", "Write"):
        _lesson = _the_lesson_recorded_here(payload)
        if _lesson:
            _emit(_lesson)
    if _tool == "Edit":
        _set = _the_others_in_the_set(payload)
        if _set:
            _emit(_set)
            # Not a return: the operator notice below is about WHO cuts, this is about WHERE.
    if _tool in ("Edit", "Write"):
        return _surgery_belongs_to_the_operator(payload)
    if _tool != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not command:
        return 0
    root = ws.hook_root(payload)
    _risk = _about_to_discard(command, root)
    if _risk:
        _emit(_risk)
        return 0
    wsdir = ws.workspace(root)
    if not wsdir.is_dir():
        return 0

    # 🐛 [2026-09-18] (R18 agent 1, 2026-09-18) Two PreToolUse hooks on Bash cost 234 ms per command against 132 for one —
    # measured — and every shell command in a session pays it. R18's own finding says a change is
    # perceptible at about 20% of the base, and this was doubling it. So Bash has ONE hook and it
    # does both jobs by CALLING the other module rather than copying it: the long-read notice lives
    # in `chamnan_bulk_read_notice.py` and stays there, which is the difference between reusing a
    # guard and forking one.
    # 🎯 [owner 2026-09-23] "ไม่ทำผิดซ้ำๆ" — said BEFORE the command runs, which is the only moment
    # it can change anything. `chamnan_tool_failed.py` does the remembering; `lib/gotcha.py` decides
    # what counts as a repeat, and its key is at its tightest setting on purpose: the same tool, the
    # same command, the same error, twice. A first failure says nothing, because a first failure is
    # how anybody learns what the flags are.
    _shape = _wrong_shape(payload)
    if _shape:
        _emit(_shape)
        # Not a return, for the same reason as the repeat notice below it.

    _again = _repeat_notice(payload)
    if _again:
        _emit(_again)
        # Deliberately NOT a return: this is information about a command that is about to run, not
        # a reason to stop evaluating it. The pointer below may still have something to say, and
        # `_emit` already carries the one-notice-per-call coordination.

    _long = _long_read_notice(payload)
    if _long:
        _emit(_long)
        return 0

    # Every Bash command this hook evaluates counts toward the session's call total, whether or
    # not it matches a procedure — the same thing chamnan_scratch_watch.py's `entry["calls"]`
    # counts. Read before computing hits, so the total reflects the whole session, not just the
    # commands that happened to match.
    session = str(payload.get("session_id") or "")
    entry = _nudge_read(wsdir, session)
    entry["calls"] = entry.get("calls", 0) + 1
    calls = entry["calls"]

    _runnable = _the_work_itself(command)
    hits = [(stem, pats) for stem, pats in _covers(wsdir)
            if any(pat in _runnable for pat in pats)]
    if not hits:
        _nudge_write(wsdir, session, entry)
        return 0
    stem = hits[0][0]

    # At most three times PER PROCEDURE per session: immediately on the first match, then again
    # once the session has passed each of chamnan_scratch_watch.NUDGE_AGAIN_AT's own marks (150,
    # 400 calls) — mirrored above so the two budgets cannot drift apart. `0` stands for "no
    # minimum": unlike that hook's resume nudge, the first time IS the point of this one, so it
    # does not wait for a threshold the way NUDGE_AT does. A reminder on every command is noise,
    # and noise is what gets a hook switched off — which would be worse than the drift it exists
    # to stop, so the budget stops at three rather than firing on every later match too.
    procs = entry.setdefault("procs", {})
    proc = procs.setdefault(stem, {"nudges": 0})
    marks = (0,) + NUDGE_AGAIN_AT
    done = int(proc.get("nudges", 0))
    if done >= len(marks) or calls < marks[done]:
        _nudge_write(wsdir, session, entry)
        return 0
    proc["nudges"] = done + 1
    _nudge_write(wsdir, session, entry)

    steps = _first_steps(wsdir / "skills" / (stem + ".md"))
    lines = ["chamnan: this work has a recorded procedure — `.chamnan/skills/%s.md`" % stem]
    for s in steps:
        lines.append("  · " + s[:150])
    if steps:
        lines.append("  (read it before going further; said up to 3 times per session — now, "
                      "and again past %d and %d commands)" % NUDGE_AGAIN_AT)
    _emit("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(ws.never_fail(main))
