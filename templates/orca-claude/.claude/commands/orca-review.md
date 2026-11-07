---
description: Start a fresh read-only review of the current Orca stream.
---

Use the reviewer agent in a new session. Give it the accepted plan, base SHA, head SHA, diff, and gate output. Do not include the implementer's narrative as proof.

A review recorded for an older head or patch id is stale. Do not merge, push, or delete a worktree from this command. Merging stays on the Orca plugin's dry-run-first merge script.
