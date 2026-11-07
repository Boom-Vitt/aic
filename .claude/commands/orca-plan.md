---
description: Draft an Orca plan from an AIC recommendation. Do not implement or fan out.
---

Read the AIC skill and recommend the smallest workflow family, owners, dependencies, and acceptance checks. If planning is approved, write `.orca/plan.json` with Orca plan version 1: `status` stays `draft`, each stream has a slug, role `claude-code` or `codex`, repo-relative paths, dependencies, and at least one acceptance check. Overlapping paths need `dependsOn`. Keep the stream count at one unless the user raised the budget.

Do not create worktrees, commit, push, start the implementer, or set `status` to `accepted`. Ask the user to accept the plan before any fan-out.
