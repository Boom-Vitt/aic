# AIC with the Orca template

AIC is the skills-first workflow library. Orca (Boom Big Nose Workflow v0.4.0) is a separate Claude Code plugin. This repository templates how they fit together. The native AIC plugin stays skills-only: do not add hooks to `.claude-plugin`.

Grok Build, Claude Code, and Codex in Orca are roles inside Claude Code. A Codex CLI is not required.

## Commands

- Offline checks: `./scripts/verify.sh`
- Template dry-run: `./scripts/orca-headless.sh --plan templates/orca-claude/plan.example.json`
- New project: `./scripts/bootstrap-orca-project.sh /absolute/new/path`
- Mac mini setup, dry-run: `./scripts/macos-setup-orca.sh`

## Roles and evidence

- AIC selects the workflow, scope, owners, and acceptance. It does not launch the loop.
- grok-build writes `.orca/plan.json` and does not implement.
- claude-code implements one accepted stream in its worktree.
- The reviewer is a separate read-only session. It sees the spec, SHAs, diff, and command results.
- Bug streams need a baseline failure, a passing reproduction, and a clean existing suite. Import errors and missing dependencies are not reproductions.
- A gate or review for a different head or patch id does not count.
- Hooks read the active cwd. `CLAUDE_PROJECT_DIR` stays the original checkout after EnterWorktree.

## Limits

- Default headless budget: 1 agent and 1 worktree. Ceilings: 4 and 6.
- `./scripts/orca-headless.sh` does not call a model. `--apply` is the only path that runs `claude -p`, with `dontAsk`, a turn limit, and a wall-clock limit.
- Do not use `--bare` or a permission bypass for this workflow. Do not push, force-push, or delete worktrees from the unattended loop.
- Exit 2 from `.claude/hooks/guard.py` blocks a tool. CI remains the independent acceptance gate.
