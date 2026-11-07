# Project contract

Use AIC before choosing a workflow. Use Orca v0.4.0 for accepted implementation. Grok Build writes the plan. Claude Code implements one stream in its worktree. Codex is the integration role inside Claude Code, not a separate CLI. The reviewer is a fresh read-only session.

## Commands

- Plan check: `scripts/orca-headless.sh`
- Accept, then apply, as two commands: `scripts/orca-headless.sh --accept` and `scripts/orca-headless.sh --apply`
- Gate: `./gate.sh` (exit 2 means no project check is configured)

Replace the gate with this project's lint, typecheck, and test commands. Record the command, commit, and exit code.

## Boundaries

- Bug work needs a baseline failure, a passing rerun, and a clean existing suite. Import errors and missing dependencies are not reproductions.
- Do not push, force-push, delete branches, or delete worktrees from an unattended session.
- Do not use `--bare` or a permission bypass. Hooks must use the active cwd. `CLAUDE_PROJECT_DIR` stays the original checkout.
- A review for an older head or patch id is stale.
- Default budget is one stream. Ceilings are 4 agents and 6 worktrees.
