---
description: Rebuild the architecture index after files were added, removed, renamed, or restructured. Cheap to run; run it whenever the shape of the repo changed rather than waiting to be asked.
---

# Refresh the index

```
chamnan-map
```

Run this after any change to the repo's *shape* — new module, deleted file, renamed directory, a
function moved somewhere else. Not after every edit; the index describes structure, and editing the
body of a function does not change structure.

A stale index is worse than none. It is confidently wrong, and the next session will believe it and
open the file that no longer holds what it says.

If the described-coverage percentage fell, new files arrived without an opening comment. Say which
ones, and offer the `commenter` agent.
