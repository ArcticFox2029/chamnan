"""Which file you change next, learned by counting — no model call, no user command.

The gap this closes was measured rather than assumed. On a real work repository chamnan recorded
zero sessions, decisions, lessons, rules and threads across three days and 764 commands, while
Claude Code's own memory tool captured six substantive lessons from the same work in the same
window. chamnan's knowledge only accumulates when somebody runs a command, and on that repository
nobody ran one — chamnan's own commands were invoked zero times in the whole period.

So the question became: what can be learned from what the hooks ALREADY see, without asking the
user for anything and without a model?

Command signatures cannot answer it. `commands.jsonl` stores the first token, and on that
repository the top of the list is `ssh` 107 times, `sudo` 43, `curl` 23, `def`, `tr`, `puts` —
`workflows.repeated()` returns None on all 2,477 entries across both real logs. "You ran ssh 107
times" is not a lesson.

Edits can. Measured across 16 real sessions and 929 edited files, asking "of the times A was
edited, how often was B edited within the next five edits":

    pmg-evidence-print.html  ->  pmg-evidence.html        10/10   100%
    shop_sim.mjs             ->  bank_sim.mjs             10/10   100%
    chamnan-candidates       ->  run_tests.py              9/9    100%
    claude_session2.sh       ->  start_recheckapp.command  9/9    100%

45 pairs cleared a 40% bar. That is a real, deterministic signal about this repository, available
for the cost of counting, and it is the shape of thing the native memory tool wrote by hand.

Two things this deliberately is not. It is not a dependency graph — `lib/impact.py` reads imports
and answers "what breaks", which is a different and stronger question. This answers "what did you
touch next", which is habit, and habit includes the test file, the changelog and the config that no
import edge would ever show. And it is not stored as a derived artefact: the log is the record, the
correlation is computed on read, so there is nothing to regenerate, invalidate, or merge.
"""
import json
import time
from collections import Counter, defaultdict

LOG = "logs/edits.jsonl"
# How many later edits count as "next". Five was not tuned: it is the window the measurement above
# used, and widening it turns "I changed the test with the code" into "I was in the same session".
WINDOW = 5
# Below this, one coincidence looks like a rule. At 8 the pairs that survive on real data are the
# ones a person would also name.
MIN_EDITS = 8
MIN_CONFIDENCE = 0.4
MAX_PARTNERS = 2
# A log older than this describes a codebase that has moved. Kept in step with the rest of the
# workspace's retention rather than invented here.
MAX_AGE_DAYS = 30


def record(wsdir, path):
    """Append one edit. Called from the PostToolUse hook, which already fires on Write and Edit."""
    try:
        dest = wsdir / LOG
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": int(time.time()), "fp": str(path)}) + "\n")
    except OSError:
        pass          # a read-only checkout must still be able to edit files


def _sequence(wsdir):
    cutoff = time.time() - MAX_AGE_DAYS * 86400
    out = []
    try:
        with (wsdir / LOG).open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue          # a torn append is one lost edit, not a broken feature
                if isinstance(rec, dict) and rec.get("fp") and (rec.get("at") or 0) >= cutoff:
                    out.append(rec["fp"])
    except OSError:
        return []
    return out


def partners(wsdir, path, window=WINDOW):
    """[(other_path, times, confidence)] for files usually edited right after `path`.

    Confidence is P(B edited within the window | A edited), and B is counted at most once per edit
    of A — the obvious version counts every co-occurrence in the window and produces confidences
    above 100%, which is how the first measurement of this was wrong.
    """
    seq = _sequence(wsdir)
    if not seq:
        return []
    edits = Counter(seq)
    if edits.get(str(path), 0) < MIN_EDITS:
        return []
    follows = defaultdict(int)
    target = str(path)
    for i, a in enumerate(seq):
        if a != target:
            continue
        for b in set(seq[i + 1:i + 1 + window]):
            if b != target:
                follows[b] += 1
    n = edits[target]
    rows = [(b, c, c / n) for b, c in follows.items() if c / n >= MIN_CONFIDENCE and c >= 3]
    rows.sort(key=lambda r: (-r[2], -r[1], r[0]))
    return rows[:MAX_PARTNERS]


def line(wsdir, path, display=str):
    """One sentence for the file pointer, or "" when there is nothing worth saying."""
    rows = partners(wsdir, path)
    if not rows:
        return ""
    parts = ", ".join(f"`{display(b)}` ({p * 100:.0f}%)" for b, _, p in rows)
    return f"_You usually change {parts} right after this one._"
