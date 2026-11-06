# Compatibility

AIC follows the Agent Skills format; that standard does not define universal discovery directories, permissions, slash commands or cloud synchronization. Each registry entry records an official source. The installer supports the documented default paths below; custom profiles/state roots need `generic --destination` and the host's own configuration/trust process.

All paths are skill roots: installation creates `<root>/aic/SKILL.md`. User paths are relative to the explicitly selected home, or the invoking user's home. Project paths are relative to `--project`.

Managed file mutations require POSIX directory-descriptor/no-follow primitives on macOS/Linux. The installer refuses unsupported platforms, including Windows, rather than falling back to pathname-recursive deletion. A host's own supported manual skill installation is separate from AIC's managed installer; it is not verified by this adapter matrix.

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

## Important differences

- omp scans one level below its skills root. Default user root is `.omp/agent/skills`, not `.omp/skills`; named profiles and `PI_CODING_AGENT_DIR` can change it. Foreign user providers can require opt-in. Do not assume installing a Claude user skill makes it available in omp.
- Pi supports explicit skill-directory selection; its project resources may require trust. AIC does not change that trust.
- Hermes profile root can change through `HERMES_HOME`; project skill discovery requires project trust at the Git-root ancestor. External skill directories can be writable, not inherently read-only.
- OpenClaw's project path means its configured agent workspace, not every arbitrary nested checkout. Nondefault state paths need an explicit destination. Its skill containment rules are not identical to another host's symlink handling.
- OpenCode, Cursor and Gemini have additional compatibility roots; AIC chooses a documented native path instead of duplicating one skill into every fallback root.
- Copilot CLI is one product surface. Cloud agents, editor integrations and GitHub Actions may need separate setup and do not automatically receive personal skills.
- DeepSeek is a model/provider selected through a compatible host such as OpenCode, not a standalone adapter with an invented `~/.deepseek/skills` path. Other model families work only to the extent their host can load and follow the skill.
- Unknown tools are not silently mapped to a guessed directory. Add an official-source-backed registry entry, or use explicit generic destination without claiming native integration.

## Evidence levels

1. **Documented:** official sources describe the discovery interface/path.
2. **Installation contract-tested:** AIC copies the intact self-contained package into an isolated matching path; idempotency, preservation and uninstall are exercised.
3. **Installed-file consumption smoke:** an actual agent reads/uses an isolated installed copy for specified scenarios.
4. **Native discovery verified:** an actual installed host discovers the named skill through its own discovery path/invocation.
5. **Operational handoff verified:** an approved real project/agent launch is observed through the target runtime.

Do not promote a lower level to a higher one. Current delivery evidence and unexercised integrations are stated in [verification.md](verification.md). Initial OS checks cover only the actually recorded environments, not every platform.
