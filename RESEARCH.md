# Research notes for the Orca and Claude Code template

Checked **2026-11-07**. These notes explain why the template is shaped the way it is. They are not a benchmark of this repository, not a promise of the same gains on current models, and not permission to copy paper text, prompts, or code. AIC's license does not relicense the sources below.

The Orca plugin this template targets is Boom Big Nose Workflow **v0.4.0**, commit `ad1a6032465546883d57299fda5677d6b2a7750d` in [Boom-Vitt/claude-mods-boombignose](https://github.com/Boom-Vitt/claude-mods-boombignose/tree/ad1a6032465546883d57299fda5677d6b2a7750d/boom-big-nose-workflow). Its README states that Grok Build, Claude Code, and Codex are roles inside Claude Code, not logins to external products. A Codex CLI is not required. Upstream later renamed the plugin to `bbnw` and changed the team model; this template does not follow that later line.

## What the template takes from the evidence

1. **Small checkable contracts.** Each stream has a slug, a role, owned paths, dependencies, and at least one acceptance check. The plan validator rejects cycles, unknown roles, and overlapping paths that have no `dependsOn`. Simple work stays one stream.
2. **Reproduce, then regress.** A bug stream is not done because an implementer says so. The bug example asks for a baseline failure, a passing rerun, and a clean existing suite. An import error or a missing dependency is not a reproduction.
3. **Separate review and a deterministic gate.** The reviewer is another session with read-only tools. A recorded approval matches one head and one patch id. CI in this repository is the acceptance gate for the template itself. A hook is not that gate.
4. **Worktree-aware, budgeted parallelism.** The default budget is one agent and one worktree. Four agents and six worktrees are ceilings from Orca's config, not an optimum from a paper. Hooks use the active cwd. `CLAUDE_PROJECT_DIR` stays the original checkout after EnterWorktree.
5. **Bounded headless runs.** `--apply` is opt-in. The command uses `dontAsk`, a turn limit, a wall-clock limit, and JSON output. Success requires a structured result, an empty denial list, and no plugin-load error. `--bare` is not used, because it skips plugins, `CLAUDE.md`, and hooks, and it does not use subscription login.

## Sources

### SWE-agent

- **Credit:** John Yang, Carlos E. Jimenez, Alexander Wettig, Kilian Lieret, Shunyu Yao, Karthik Narasimhan, and Ofir Press.
- **Version:** NeurIPS 2024 conference paper. [arXiv:2405.15793](https://arxiv.org/abs/2405.15793). [Proceedings abstract](https://proceedings.neurips.cc/paper_files/paper/2024/hash/5a7c947568c1b1328ccc5230172e1e7c-Abstract-Conference.html).
- **Use here:** agent-computer interfaces and concise feedback change outcomes, which supports short contracts and explicit commands.
- **Limit:** this does not measure the template. Publication reuse rights for the proceedings paper were not re-audited; the paper stays reference-only.
- **Checked:** 2026-11-07.

### Agentless

- **Credit:** Chunqiu Steven Xia, Yinlin Deng, Soren Dunn, and Lingming Zhang.
- **Version:** *Proceedings of the ACM on Software Engineering*, 2025. [arXiv:2407.01489](https://arxiv.org/abs/2407.01489). [ACM record](https://dl.acm.org/doi/10.1145/3715754).
- **Use here:** the paper's reported SWE-bench Lite ablation moved from 77 tasks with majority voting, to 81 after regression filtering, to 96 of 300 after reproduction filtering. It also reports that only 94 of 213 selected reproduction tests recognized the developer fix. The template therefore asks for a baseline failure, a passing reproduction, and the existing suite.
- **Limit:** those figures are historical results for that system. They are not a prediction for Claude or for Boom's repositories.
- **Checked:** 2026-11-07.

### CodeR

- **Credit:** Dong Chen and coauthors.
- **Version:** preprint, not used here as a confirmed main-conference paper. [arXiv:2406.01304](https://arxiv.org/abs/2406.01304).
- **Use here:** executable task graphs with separate reproduce, localize, edit, and verify stages. The Orca plan's dependencies and acceptance checks are the local form of that idea.
- **Limit:** no optimal team size is taken from this preprint.
- **Checked:** 2026-11-07.

### MASAI

- **Credit:** Daman Arora and coauthors.
- **Version:** NeurIPS 2024 workshop poster, not a main-conference paper. [Workshop entry](https://neurips.cc/virtual/2024/100955). [arXiv:2406.11638](https://arxiv.org/abs/2406.11638).
- **Use here:** modular stages are a useful design sketch. The poster is not treated as stronger evidence than the peer-reviewed papers above.
- **Checked:** 2026-11-07.

### Claude Code product documentation

Checked **2026-11-07**. These pages describe the current product. They are not an experiment.

- [Best practices](https://code.claude.com/docs/en/best-practices), including a fresh reviewer that did not watch the implementation.
- [Hooks](https://code.claude.com/docs/en/hooks). Exit 2 blocks a tool. Hook failures otherwise tend to fail open unless `onFailure: block` applies. The field needs a current Claude Code. Stop hooks are not a security boundary. CI still decides acceptance.
- [Worktrees](https://code.claude.com/docs/en/worktrees). After EnterWorktree, `CLAUDE_PROJECT_DIR` stays at the original root. Hook input `cwd` follows the active worktree. A worktree isolates edits, not credentials or the network.
- [Headless](https://code.claude.com/docs/en/headless) and the [CLI reference](https://code.claude.com/docs/en/cli-reference). Use explicit permissions, turn limits, and structured JSON. Check `structured_output` and `permission_denials`. Current docs recommend `--bare` for generic scripts. This template does not use it: bare mode skips plugins, project instructions, and hooks, and it does not use subscription OAuth.
- [Permissions](https://code.claude.com/docs/en/permissions/). `dontAsk` denies prompts that nobody can answer. The template does not use a permission bypass.
- [Setup](https://code.claude.com/docs/en/setup). Native install is the current path. `npm install` of Claude Code is deprecated. The Mac mini script uses the documented Homebrew cask `claude-code` and does not pipe the remote install script into a shell.

## What this repository did not verify

No Claude Code process was started while preparing these notes. Plugin load, interactive sign-in, and a doctor run on the Mac mini are operator steps. The tests here are offline: invalid plans, ownership, permissions, stale reviews, worktree cwd, budgets, timeouts, bootstrap refusal, and the absence of push or delete in the default command.
