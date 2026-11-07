# Compatibility

AIC has three distinct integration channels: a self-contained Agent Skill, a native **skills-only Claude Code plugin**, and an explicitly configured local read-only MCP adapter. Ask the existing host agent to use AIC; a manual AIC CLI, Python or extra model key is not a prerequisite for the skill/plugin. The portable [integration guide](../skills/aic/references/integrations.md) contains host prompts, native UI/in-session setup and the separate host-run MCP configuration.

AIC follows the Agent Skills format; that standard does not define universal discovery directories, permissions, slash commands or cloud synchronization. The paths below are documented standalone-skill destinations, not universal native plugin support. Each registry entry records an official source. The optional internal managed-copy installer supports these documented defaults; custom profiles/state roots need its explicit `generic --destination` interface and the host's own configuration/trust process.

All paths below are standalone skill roots: the complete skill lives at `<root>/aic/SKILL.md`, with its references, assets, scripts and rights notices intact. Use the host's documented skill import/copy interface; the internal installer is optional agent/operator tooling. For that helper, user paths are relative to the explicitly selected home or invoking user's home, and project paths are relative to `--project`.

The optional managed-copy helper requires Python 3.11 or newer and POSIX directory-descriptor/no-follow primitives on macOS/Linux. It refuses unsupported platforms, including Windows, rather than falling back to pathname-recursive deletion. A host's own supported skill installation is separate and is not verified by the managed-copy adapter matrix.

| Adapter | Project root | User root | Primary evidence |
| --- | --- | --- | --- |
| `claude-code` | `.claude/skills` | `~/.claude/skills` | [Claude Code](https://code.claude.com/docs/en/skills) |
| `codex` | `.agents/skills` | `~/.agents/skills` | [OpenAI](https://developers.openai.com/codex/skills) |
| `omp` | `.omp/skills` | `~/.omp/agent/skills` | [Pinned upstream](https://github.com/can1357/oh-my-pi/blob/75e7801e247d4e3263439d4cc08ccad60dc64bdd/docs/skills.md) |
| `pi` | `.pi/skills` | `~/.pi/agent/skills` | [Pi](https://pi.dev/docs/latest/skills) |
| `hermes` | `.hermes/skills` | `~/.hermes/skills` | [Hermes](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills) |
| `openclaw` | `skills` in the configured workspace | `~/.openclaw/skills` | [OpenClaw](https://docs.openclaw.ai/tools/skills) |
| `cursor` | `.cursor/skills` | `~/.cursor/skills` | [Cursor](https://cursor.com/docs/skills.md) |
| `gemini-cli` | `.gemini/skills` | `~/.gemini/skills` | [Gemini CLI](https://geminicli.com/docs/cli/skills.md) |
| `opencode` | `.opencode/skills` | `~/.config/opencode/skills` | [OpenCode](https://opencode.ai/docs/skills/) |
| `copilot-cli` | `.github/skills` | `~/.copilot/skills` | [Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills) |
| `generic` | Explicit `--destination` only | Explicit `--destination` only | Your host's documented Agent Skills interface |

Sources checked November 6, 2026. Rolling docs and installed versions may differ; the registry does not certify live discovery.

## Native plugin and local MCP are separate

| Channel | Native surface | Setup and boundaries |
| --- | --- | --- |
| Claude Code plugin | `aic@aic-marketplace`, skill `/aic:aic` | Register the reviewed checkout's marketplace in the host, open AIC's details and deliberately choose local/project/user scope. The plugin carries the same `skills/aic` directory through default discovery and declares no hooks, settings, duplicate scan paths or automatic MCP process. |
| Local MCP | Host-started stdio process `aic-mcp` | Configure `uvx --from /absolute/path/to/reviewed/aic --with mcp==2.3.0 aic-mcp --project /absolute/approved/project` as executable plus arguments. Requires the reviewed checkout, Python 3.11+, existing `uvx` and pinned official SDK. `--project` is an existing absolute directory with no symlink components. No PyPI publication or remote service is claimed. |

The Python distribution name is `aiculture-skills` (current version `0.0.3`). It is not published on PyPI. The PyPI project named `aic` (0.2) is unrelated. A fresh virtual environment installs a checkout with `python -m pip install ".[mcp]"`. The [README quickstart](../README.md#quickstart) also records the wheel install checked with pipx 1.8.0 and uv 0.9.26. Console scripts are `aic` and `aic-mcp`. `aic hello-world` prints the install check. `aic-mcp` needs the `mcp` extra.

The plugin/marketplace manifests target current official Claude Code [manifest](https://code.claude.com/docs/en/plugins-reference), [marketplace](https://code.claude.com/docs/en/plugins/marketplace-reference.md) and [installation](https://code.claude.com/docs/en/plugins/install.md) interfaces, checked November 7, 2026. The marketplace points to its root with `source: "./"`; the plugin version is declared only in `plugin.json`, independently of the marketplace manifest version. Neither a JSON/schema check nor plugin listing establishes actual skill consumption.

MCP exposes exactly `aic_get_workflow_catalog`, `aic_get_guidance`, `aic_inspect_project` and `aic_validate_recommendation`, plus fixed packaged resources. It binds one existing absolute approved project; no source-content reads, root-rebinding tools, shell execution, file writes, memory promotion, agent launches or HTTP listener are supplied. See the portable guide for exact argument arrays, guidance sections, resource URIs and client-specific configuration cautions. The host still reasons, obtains approval and enforces its own permissions.

Claude Code plugin support is not a claim about claude.ai chat, Cowork, browser/cloud sessions or every editor's plugin system. Other hosts use their documented standalone-skill path or an explicitly configured MCP client. There is no official-directory listing, universal plugin discovery or automatic cross-host synchronization claim.

## Important differences

- omp scans one level below its skills root. Default user root is `.omp/agent/skills`, not `.omp/skills`; named profiles and `PI_CODING_AGENT_DIR` can change it. Foreign user providers can require opt-in. Do not assume installing a Claude user skill makes it available in omp.
- Pi supports explicit skill-directory selection; its project resources may require trust. AIC does not change that trust.
- Hermes profile root can change through `HERMES_HOME`; project skill discovery requires project trust at the Git-root ancestor. External skill directories can be writable, not inherently read-only.
- OpenClaw's project path means its configured agent workspace, not every arbitrary nested checkout. Nondefault state paths need an explicit destination. Its skill containment rules are not identical to another host's symlink handling.
- OpenCode, Cursor and Gemini have additional compatibility roots; AIC chooses a documented native path instead of duplicating one skill into every fallback root.
- Copilot CLI is one product surface. Cloud agents, editor integrations and GitHub Actions may need separate setup and do not automatically receive personal skills.
- DeepSeek model/provider selection is separate from the official DeepSeek Harness and its [documented workflow capability](../skills/aic/references/research.md#deepseek-harness-2026). AIC has no verified native discovery adapter for that harness and does not invent a `~/.deepseek/skills` path. Other models remain usable only through a host that can load/follow the skill; use explicit generic installation when appropriate without claiming native discovery.
- Unknown tools are not silently mapped to a guessed directory. Add an official-source-backed registry entry, or use explicit generic destination without claiming native integration.

## Evidence levels

1. **Documented:** official sources describe the discovery interface/path.
2. **Installation contract-tested:** AIC copies the intact self-contained package into an isolated matching path; idempotency, preservation and uninstall are exercised.
3. **Installed-file consumption smoke:** an actual agent reads/uses an isolated installed copy for specified scenarios.
4. **Native discovery verified:** an actual installed host discovers the named skill through its own discovery path/invocation.
5. **Operational handoff verified:** an approved real project/agent launch is observed through the target runtime.

Do not promote a lower level to a higher one. Current delivery evidence and unexercised integrations are stated in [verification.md](verification.md). Initial OS checks cover only the actually recorded environments, not every platform.

### Current 0.0.3 security revision

The current source keeps the same integration channels and schema 3, while bounding recommendation and reference-note resource consumption and correcting repository-maintenance provenance/deadlines. See the [security policy](../SECURITY.md) for enforced boundaries and this revision's [verification receipt](verification.md) for actually exercised runtimes. Older native installation/model-consumption evidence remains historical; no global installation, live scheduler upgrade or universal host certification is implied.

### Historical 0.0.2 functional observations

The [dated receipt](verification.md) records actual native strict manifest validation and task-private local-scope installation/listing of `aic@aic-marketplace` 0.0.2. It does **not** claim current native skill invocation or an official directory listing.

Actual official-SDK stdio clients exercised the source launcher, installed wheel and exact documented host-run `uvx` configuration. Each exposed four read-only tools and twelve concrete resources, refused unsafe inputs and recovered without changing the synthetic project. The core-only installed wheel also worked without the SDK; missing-extra MCP startup failed cleanly. The complete Mac mini entrypoint ran 276 tests: 275 passed, one filesystem-specific skip. These observations do not certify every MCP host, protocol version, OS or model.

### Recorded integration coverage

The following summarizes dated records in [verification.md](verification.md), not new `0.0.3` execution receipts:

| Surface | Actual recorded coverage | Untested or not established |
| --- | --- | --- |
| All ten named standalone path adapters | Isolated project/user install, preservation, idempotency, installed-helper and uninstall contracts | Live discovery/model use in every host; Windows managed-copy behavior |
| Claude Code 2.1.318, `claude-opus-5-5` | Four synthetic installed-file-consumption recommendations matched and validated; restricted trace read installed files | Native discovery in that probe; current native plugin invocation |
| Codex CLI 0.166.0, `gpt-6.1-sol` | Four synthetic installed-file-consumption recommendations matched and validated | Separately verified native discovery |
| omp 18.16.0, `gpt-6.1-sol` | Four synthetic cases with native isolated skill reads; later five-family installed-file consumption separately recorded | Native discovery of every later revision; universal quality or performance |
| Pi, Hermes, OpenClaw, Cursor, Gemini CLI, OpenCode, Copilot CLI | Official path documentation and isolated managed-copy contracts | Live discovery or model-consumption smoke |
| Skills-only Claude Code plugin/marketplace; local SDK-backed MCP | Current setup/interfaces documented in the [integration guide](../skills/aic/references/integrations.md) | Historical skill tests do not establish native plugin validation/install/invocation, SDK stdio transport or installed-wheel behavior; candidate checks are recorded separately |
| Optional Orca/omp handoff | Preview, approval and isolated subprocess contract checks | A real project/agent launch from this setup, task completion or a general cross-runtime backend |

Small routing smokes are functional observations, not statistical benchmarks. Keep recorded host/model versions and historical package labels intact. Source review is not an operational receipt; consult this candidate's actual verification record before claiming a current channel passed.

## Workflow and recommendation compatibility

AIC 0.0.3 uses recommendation/catalog schema 3 and exactly five workflow families: `direct` (`solo`), `explore-build` (`parallel`), `coordinated-delivery` (`sequential` or `parallel`), `independent-review` (`generator-evaluator`) and `adaptive-controller` (any supported current-stage topology). Schema-1/2 recommendations and retired template IDs are rejected without aliases or silent migration. Reassess real task properties and authorization before regenerating; installer, memory, maintenance and outer handoff formats keep their independent versions.

The `0.0.N` development-package sequence is not a schema sequence or a rollback. Renumbering does not make old recommendations valid or change current format versions; see [development versioning](../CONTRIBUTING.md#development-versioning).

The host supplies semantic selection using goal, acceptance, dependencies, available capabilities and effective authority. The catalog validates combinations; it does not schedule milestones, benchmark agents or make every host equally capable. Choose per stage using the [selection guide](../skills/aic/references/workflows.md) and [family contracts](../skills/aic/references/templates.md). Mixed projects retain their original acceptance while a stage's category, family, topology or authorized runtime may change. AIC makes no universal Orca/OMP/Claude/Codex quality ranking and adds no general cross-CLI execution backend.

The Orca v0.4.0 project template in this checkout is a separate harness. Its offline plan, permission, bootstrap, and headless-result checks are contract tests. They do not show that Claude Code loaded the plugin, that a model ran, or that a Mac mini doctor was executed.

## Optional local supervision

The original [tmux profile](../skills/aic/assets/tmux.conf) and [supervision guide](../skills/aic/references/supervision.md) target stable tmux 3.8; see the [official-source evidence](../skills/aic/references/research.md#tmux-2026). This optional procedure is separate from skill discovery and the existing Orca-to-omp adapter. It requires explicit approval for task-local launch/cleanup, an explicit task-owned socket, trusted per-run config and exact session/pane IDs. It neither installs/upgrades tmux nor modifies existing servers, `~/.tmux.conf`, global settings or managed services.

For native OMP children, prefer available Agent Hub (`Alt+A`, tree `t`) instead of unnecessary panes. Panes are useful for approved independent terminal processes; the task/owner/dependency/blocker/evidence/next-action board remains in existing task artifacts. Process-running/dead/exit status is not task acceptance. Worktrees/tmux do not sandbox credentials or network access; detach/reattach is not recovery from host shutdown or consent for unattended model work. Unknown usage/cost stays unknown. A profile's documented behavior is not evidence that any particular host integration or model launch was exercised.
