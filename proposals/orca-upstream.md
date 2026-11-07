# Proposal for the Orca plugin owner

This file is issue text. It was not opened on `Boom-Vitt/claude-mods-boombignose`. The plugin source stays in that repository.

## Title

Worktree cwd, headless limits, and disk preflight for Orca v0.4.0

## Body

Orca v0.4.0 already has schema-checked plans, an acceptance checkpoint, per-stream ownership, worktree isolation, `maxTurns`, gate timeouts, patch-sensitive review, dry-run merge, a local ledger, and `git merge-tree` conflict prediction. This proposal does not claim those as new.

Three follow-ups match current Claude Code docs and the research notes in AIC's `RESEARCH.md`:

1. Document that hooks and gates must use the active cwd. `CLAUDE_PROJECT_DIR` does not follow `EnterWorktree`. A gate that trusts the original checkout can test the wrong tree.
2. Do not recommend `claude --bare` for a subscription session that needs this plugin, `CLAUDE.md`, or hooks. Bare mode skips those and does not use subscription OAuth.
3. Add a disk and timeout preflight before fan-out. On a machine with little free disk, start at one stream. Keep four agents and six worktrees as ceilings. Do not require a Codex CLI: in v0.4.0 that name is a role inside Claude Code.

The later `bbnw` line is a different design (herdr teammates, and Codex as a CLI). Please do not treat a patch for v0.4.0 as a request to merge that line back.

AIC's template only wraps the v0.4.0 contract. It does not vendor the plugin.
