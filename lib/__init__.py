"""Make `lib/` importable as a package without giving up the flat imports inside it.

Every module here imports its siblings by bare name — `import tree`, `from workspace import
workspace` — which works because `bin/` and `hooks/` each do `sys.path.insert(0, .../lib)` before
importing anything. It also means `import lib.ledger` from outside raises
`ModuleNotFoundError: No module named 'workspace'`: the package loads, then the first sibling
import inside it has nowhere to resolve from.

Anything wanting to read chamnan's own state — a test, a report, a tool in another repository — hit
that and had to know to reproduce the `sys.path` line. Putting this directory on the path here, at
package-import time, removes the trap without touching the 23 modules or the callers that already
work: a bare `import tree` and a package-qualified `import lib.tree` now both resolve, to the same
file.

They resolve to two *separate module objects*, though — `tree` and `lib.tree` — so anything that
compares types or keeps module-level state must not mix the two styles in one process. In practice
nothing does: `bin/` and `hooks/` use the flat form throughout, and an external reader uses the
package form throughout.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
