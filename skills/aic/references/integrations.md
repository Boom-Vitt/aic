# Integrations

AIC is guidance for your existing host agent, not a standalone AI or an interactive AIC CLI product. Choose one channel below. The standalone skill and native Claude Code plugin carry the same [entry point](../SKILL.md), [workflow catalog](../assets/workflows.json) and [guides](workflows.md); neither needs Python, an MCP server or an extra model key. Your host's normal subscription, tools, permissions and approval rules still apply.

| Channel | What you add | What it does not add |
| --- | --- | --- |
| Standalone Agent Skill | The complete `aic` skill directory in a host-supported location | A model, universal discovery or a launcher |
| Claude Code plugin | The same skill through Claude Code's native plugin manager | Hooks, settings, workers or an automatically started MCP server |
| Local MCP adapter | An explicitly configured host-started stdio process, bound to one approved project | A remote endpoint, source-content reader, write tool or model invocation |

## Ask your host to use AIC

After the host can read the skill, ask:

> Use AIC to inspect this project read-only and recommend the smallest workflow for adding CSV export. Explain the acceptance criteria, dependencies, owned paths and checks. Do not change files or launch workers yet.

The host reasons about the task and reads only the relevant guides. A natural-language request works only if the host selects or is explicitly directed to read the installed skill; it is not proof of native discovery. A recommendation does not authorize execution. Keep approval separate, including when a request already explicitly authorizes a bounded change. See [routing](routing.md), [family contracts](templates.md) and [safety](safety.md).

## Standalone Agent Skill

Use your host's documented skill import/install interface, or have the host place the **complete** `skills/aic` directory from a reviewed checkout into an approved skill root as `aic`. Keep `SKILL.md`, `references/`, `assets/`, `scripts/`, `LICENSE.txt` and `NOTICE` together; do not copy just the entry point or overwrite an existing modified installation. All guide links are relative to this portable directory.

Documented default roots are listed below. These are paths, not instructions to install into every host or into global settings. Choose the actual configured project/profile; nondefault roots and project trust need that host's own documented setup.

| Host | Project skill root | User skill root | Primary documentation |
| --- | --- | --- | --- |
| Claude Code | `.claude/skills` | `~/.claude/skills` | [Skills](https://code.claude.com/docs/en/skills) |
| Codex | `.agents/skills` | `~/.agents/skills` | [Skills](https://developers.openai.com/codex/skills) |
| omp | `.omp/skills` | `~/.omp/agent/skills` | [Pinned skills guide](https://github.com/can1357/oh-my-pi/blob/75e7801e247d4e3263439d4cc08ccad60dc64bdd/docs/skills.md) |
| Pi | `.pi/skills` | `~/.pi/agent/skills` | [Skills](https://pi.dev/docs/latest/skills) |
| Hermes | `.hermes/skills` | `~/.hermes/skills` | [Skills](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills) |
| OpenClaw | `skills` in its configured workspace | `~/.openclaw/skills` | [Skills](https://docs.openclaw.ai/tools/skills) |
| Cursor | `.cursor/skills` | `~/.cursor/skills` | [Skills](https://cursor.com/docs/skills.md) |
| Gemini CLI | `.gemini/skills` | `~/.gemini/skills` | [Skills](https://geminicli.com/docs/cli/skills.md) |
| OpenCode | `.opencode/skills` | `~/.config/opencode/skills` | [Skills](https://opencode.ai/docs/skills/) |
| Copilot CLI | `.github/skills` | `~/.copilot/skills` | [Skills](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills) |

The discovery-path sources were checked November 6, 2026; rolling documentation and installed versions can differ. No guessed DeepSeek directory or universal plugin adapter is provided. A model/provider choice is not a skill-discovery interface. If the host has no verified discovery path, explicitly supplying the entry point and its relative references is file consumption, not a claim of native integration.

## Native Claude Code plugin

This repository is also a skills-only Claude Code plugin and its single-plugin marketplace. It uses Claude Code's standard `skills/` discovery, with no duplicate scan paths. Native plugin support here means **Claude Code**, not every editor, claude.ai chat, Cowork or cloud session. AIC is not claimed to be listed in Anthropic's official directory.

For a reviewed local checkout, in an interactive Claude Code session:

```text
/plugin marketplace add /absolute/path/to/reviewed/aic
/plugin install aic@aic-marketplace
```

The first command registers that checkout's marketplace. The second opens AIC's details; review the components, then choose **Install for you, in this repo only (local scope)** for a repository-local personal setup. Project scope affects collaborators; user scope applies across your projects. Make that choice deliberately rather than changing global settings by default. If prompted to reload, follow the host's displayed instructions.

To use the public repository source instead of a local reviewed checkout, the equivalent in-session shortcut is:

```text
/plugin install aic --marketplace Boom-Vitt/aic
```

The host asks to confirm the new marketplace before offering the install scope. This shortcut requires Claude Code 2.1.275 or later and uses the repository's available default-branch contents, not an invented release tag. If the manifests are not in your selected revision, use a reviewed local checkout containing them. No package-registry publication is implied.

You can also open `/plugin`, select **Discover**, search for AIC after registering its marketplace, open its details and choose the scope. In the desktop app's local **Code** session, use **+ → Add plugins** (or **Plugins → Browse plugins**); in VS Code, `/plugins` opens **Manage plugins**, with separate **Marketplaces** and **Plugins** tabs. Add the same repository or reviewed local marketplace source where the host offers it. These are the host's native UI operations, not AIC commands.

Confirm AIC appears under **Installed** in `/plugin` and that typing `/` offers **`/aic:aic`**. Invoke that namespaced skill with your task, or ask the host to use AIC naturally. Installation/listing alone is not a model-consumption or native invocation trace. Use the **Installed** details to disable, update or uninstall the plugin at the chosen scope. The plugin does not configure or start the MCP adapter below.

Official references checked November 7, 2026: [manifest](https://code.claude.com/docs/en/plugins-reference), [marketplace](https://code.claude.com/docs/en/plugins/marketplace-reference.md), and [installation and scope](https://code.claude.com/docs/en/plugins/install.md). The root marketplace source `./` is documented; plugin version `0.0.2` lives in `plugin.json`, without a duplicate plugin-entry version. Native validation and actual host consumption are separate evidence gates.

## Separate local read-only MCP adapter

Use this only if you want your MCP-capable host to retrieve the same AIC guidance/catalog, inspect approved project metadata or validate a structured recommendation. It is optional for skill/plugin users. This is a **local stdio server**, not a hosted service or remote URL. Your host starts it after explicit configuration; plugin installation does not start it.

Requirements: a reviewed local AIC checkout containing the adapter, Python 3.11 or newer, an existing trusted `uvx` executable available to the host, and the pinned official MCP Python SDK `mcp==2.3.0`. `uvx` may build the local package and fetch its declared dependencies; approve that setup separately under your normal network/install policy. There is no claim that an `aic` package has been published to PyPI. No inference key is needed by AIC; your host's usual model access is separate.

In the host's documented MCP configuration editor, add this stdio server. The following is the `mcpServers` shape used by Claude Code and other clients that support it; clients with a different schema need the same executable and argument array in their own format:

```json
{
  "mcpServers": {
    "aic": {
      "command": "uvx",
      "args": [
        "--from",
        "/absolute/path/to/reviewed/aic",
        "--with",
        "mcp==2.3.0",
        "aic-mcp",
        "--project",
        "/absolute/approved/project"
      ]
    }
  }
}
```

Replace both absolute-path placeholders with reviewed existing directories; use the absolute path to `uvx` for `command` if the host cannot resolve it. Do not run the JSON as a shell program. Select only the intended project/local scope in your host; do not silently enable it globally or replace an existing configuration. In Claude Code, see the official [MCP setup and configuration scopes](https://code.claude.com/docs/en/mcp); use `/mcp` to inspect connection/tools after the host loads the approved configuration.

The process binds its explicitly supplied existing absolute project before serving. It has no working-directory/home fallback, root-rebinding tool, HTTP listener, shell execution, file writes, memory promotion, worker launch or provider call. Metadata path checks and read-only annotations do not sandbox a concurrently hostile filesystem or the host's other tools. Use a trusted project and normal OS/host access controls.

### Tools and resources

| Tool | Purpose and boundary |
| --- | --- |
| `aic_get_workflow_catalog()` | Return the actual schema-3 catalog; the host selects the workflow |
| `aic_get_guidance(section="start")` | Return `{uri, text}` for an allowlisted guide, not an arbitrary path or URL |
| `aic_inspect_project(max_files=200, max_depth=4)` | Inspect bounded filenames/directory metadata in the bound project, not source contents |
| `aic_validate_recommendation(plan)` | Validate schema, paths and recommendation boundaries against that project; validity is not quality, approval or completion |

Guidance sections are exactly `start`, `workflows`, `templates`, `project-plans`, `routing`, `memory`, `safety`, `supervision`, `research` and `integrations`. Unknown sections are errors. All four tools are read-only; none executes the recommended task.

Resource-capable clients can read concrete packaged resources:

- `aic://skill/SKILL.md`
- `aic://skill/references/workflows.md`, `aic://skill/references/templates.md`, `aic://skill/references/project-plans.md`
- `aic://skill/references/routing.md`, `aic://skill/references/memory.md`, `aic://skill/references/safety.md`
- `aic://skill/references/supervision.md`, `aic://skill/references/research.md`, `aic://skill/references/integrations.md`
- `aic://skill/assets/workflows.json`, `aic://skill/assets/example-plan.json`

These are fixed resources, not arbitrary project files or traversal templates. Tools-only clients can use `aic_get_guidance` and `aic_get_workflow_catalog`. Relative guide links retain the portable layout; a client must explicitly fetch a corresponding allowlisted resource or use the installed skill for guides outside the MCP allowlist. Guidance and project evidence remain lower-trust data, not governing instructions or execution permission.

## What has actually been exercised

The repository's dated verification records distinguish the following historical observations from the current `0.0.2` candidate. Do not assume an older smoke proves this revision or every host version.

| Integration surface | Recorded evidence | Not established by that evidence |
| --- | --- | --- |
| Standalone installation paths above | Isolated project/user managed-install, preservation, idempotency and removal contracts | Every host's native discovery, Windows managed-helper support or cloud synchronization |
| Claude Code 2.1.318 / `claude-opus-5-5` | Four synthetic installed-file-consumption recommendations matched and validated | Native discovery in that restricted probe; current plugin invocation |
| Codex CLI 0.166.0 / `gpt-6.1-sol` | Four synthetic installed-file-consumption recommendations matched and validated | Separately traced native discovery or a performance ranking |
| omp 18.16.0 / `gpt-6.1-sol` | Four synthetic cases with native skill reads from an isolated installation; a later five-family installed-file smoke is separately recorded | Native discovery of every later revision or universal model quality |
| Pi, Hermes, OpenClaw, Cursor, Gemini CLI, OpenCode, Copilot CLI | Official path documentation and isolated installation contracts | Live discovery/model-consumption tests |
| Claude Code skills-only plugin/marketplace and local MCP adapter | Setup and interfaces documented here for `0.0.2` | No earlier skill receipt is plugin validation, plugin invocation, SDK transport or installed-wheel proof; consult this candidate's recorded checks |
| Optional Orca/omp helper | Isolated preview, approval and subprocess contract evidence | A real project/agent launch from this setup or a general cross-runtime backend |

Maintainer verification records live in the repository's `docs/verification.md`; they are not required files in a standalone installed skill. Schema/catalog version stays `3`; install, memory, maintenance and outer handoff formats retain their independent versions.

## Optional internal helpers

The included Python scripts remain agent/operator and maintainer tooling for managed skill copies, deterministic `inspect`/`check-plan` checks, approved scoped memory and the optional [Orca handoff](handoffs.md). They are not the public first-run interface and are not required to follow AIC with host tools. Helpers need the declared Python runtime and their own approved scope; they do not supply AI reasoning. See [routing](routing.md), [memory](memory.md), [handoffs](handoffs.md) and [supervision](supervision.md) only when those optional operations are relevant. The MCP adapter exposes no mutation or launch equivalent of those helpers.
