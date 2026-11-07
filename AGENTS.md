# AIC contributor instructions

AIC (AI Culture) is a skills-first workflow library, distributed as a portable Agent Skill, a native Claude Code skills plugin and an optional local read-only MCP adapter. All authored content and helper output must be English.

## Boundaries
- Work only in this repository and task-owned temporary fixtures inside it. Never modify unrelated projects, existing agent/global settings, credentials or running services.
- No private skill collections, customer data, personal transcripts, secrets or machine-specific private files enter the public package.
- Recommendation-first: inspect read-only and use the host agent's AI; do not disguise keyword heuristics or a mock as AI inference. No extra inference API key/service is required.
- Workflows are harness/model-neutral. Separate a documented adapter, an isolated contract test and a live-tested integration; do not claim universal compatibility.
- New projects, agent launches and file changes require explicit scope approval. Approval is not permission for new charges, credential changes, deployment or unrelated work.
- Users work through their host agent, not an interactive AIC CLI. Existing helper/installer and maintainer commands are optional internal interfaces, not the product's default entry point.
- The native plugin is skills-only: no hooks, permission overrides or automatic server startup. MCP requires a separately approved existing absolute project root; expose no arbitrary file reads, root switching, mutations, model calls or agent launches.

## Engineering and verification
- Prefer the Python standard library for the portable skill and deterministic core. Only the optional MCP adapter uses its declared official SDK; keep build dependencies separate. Declare supported Python versions in pyproject.toml.
- AIC development versions follow `0.0.1`, `0.0.2`, `0.0.3`, and onward until the owner changes the policy. Follow CONTRIBUTING.md; schema/format versions are independent.
- Keep SKILL.md entry points concise; use relative references for detailed contracts, workflows and scripts. Preserve template/license provenance.
- The integration owner runs ./scripts/verify.sh after implementation. The initial delivery has a hard cap of three failed full verification runs; record each outcome and stop on the third failure. Workers must not run builds, linters, tests or formatters mid-flight.
- Tests must exercise consumer-visible behavior: non-destructive installs/uninstalls, approval boundaries, actual routing contracts, privacy filtering, memory scope and non-mutating dry runs. No source-text/wiring tautologies or false live-support claims.
- Use explicit subprocess argument arrays, never a shell for user-provided input. Do not follow untrusted symlinks or overwrite unmanaged/modified files.
- Only the integration owner commits/pushes. Preserve unrelated work; no force pushes. Verification itself is offline after declared dependencies are installed; never install models or activate managed services to verify.
- Before final delivery, exercise the changed skill/plugin/MCP consumer surface (or internal helper when changed), review security-sensitive behavior and record actual evidence and limitations.
