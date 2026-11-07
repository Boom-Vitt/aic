# Agents

- AIC states the workflow, owners, dependencies, and acceptance. It does not launch the loop.
- The user accepts the plan and approves any push, pull request, or merge.
- The implementer and the reviewer are different sessions. The reviewer reads the spec, SHAs, diff, and command results.
- Codex is a role name inside Claude Code. Do not install a Codex CLI for this template.
- Headless apply may invoke the operator's own `claude` CLI. It must not embed keys or call another model API.
