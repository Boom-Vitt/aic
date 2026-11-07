![AIC — AI Culture](docs/assets/aic-banner.svg)

# AIC — AI Culture

Created and maintained by **[Boom-Vitt](https://github.com/Boom-Vitt)**.

**Choose the workflow before the agent starts changing things.**

AIC is a **skills-first workflow library** for your existing AI agent. It helps the agent inspect relevant context read-only, choose a task-fit workflow, and define scope, ownership and acceptance before execution.

Your host supplies the reasoning and tools. AIC supplies portable guidance, five original workflow families and optional local validation—not a bundled model, a keyword classifier or a reason to add more agents to every task.

## Choose how to use AIC

| Integration | Choose it when… |
| --- | --- |
| **Standalone Skill** | Your host supports Agent Skills. Add the self-contained [`skills/aic/`](skills/aic/) directory through its documented discovery path. |
| **Claude Code plugin** | You use Claude Code and want native plugin installation of the same skill. The plugin is skills-only; MCP is configured separately. |
| **Local read-only MCP** | Your host supports MCP and needs AIC's catalog, guidance, bounded project metadata and recommendation validation through tools/resources. |

In a **Claude Code conversation**, open the native install flow with:

```text
/plugin install aic --marketplace Boom-Vitt/aic
```

This is a host plugin command, not a terminal command. Review AIC's details and choose the intended installation scope.

Start with the **[integration guide](skills/aic/references/integrations.md)** for installation, host setup, updates and removal. Standalone Skill and plugin use require no Python, pip packages or extra model keys. The optional MCP adapter requires Python 3.11+ and runs locally over stdio, bound to one explicitly configured project—not a public hosted endpoint.

These are three ways to access the same guidance and catalog, not three competing workflow engines. Host discovery and capabilities vary; see [compatibility and evidence levels](docs/compatibility.md).

## Ask your host agent

Once your host has loaded AIC, give it a task in the normal conversation. For example:

> Use AIC to plan adding CSV export to this project. Inspect the relevant context read-only, identify dependencies and risks, and recommend a workflow family. Explain the scope, ownership and acceptance checks. Do not change files or launch agents until the plan is approved.

The rule is **recommend first, approve once, then execute within scope**. A request that already clearly approves the target, boundaries, agents and checks is sufficient; routine steps do not need repeated approval. New spending, credentials, deployment or materially expanded scope still require their own authorization.

## Five families, chosen for the task

| Workflow family | Task fit |
| --- | --- |
| `direct` | One owner can carry bounded or tightly coupled work through acceptance. |
| `explore-build` | Substantial independent unknowns need parallel discovery before one owner synthesizes findings and any approved build. |
| `coordinated-delivery` | Delivery needs accepted-artifact handoffs, or ready independent branches with agreed interfaces and one integration owner. |
| `independent-review` | Consequential acceptance risk or observed self-review gaps justify a separately briefed evaluator of the actual artifact. |
| `adaptive-controller` | Long or interruptible work needs durable state and stage reselection; explicitly approved optimization additionally needs a correct baseline and comparable, bounded measurements. |

Task category, workflow family, current-stage topology and runtime/model are separate decisions. No family or fixed team is universally best, and no project must use all five. Reselect as evidence or dependencies change without weakening the original acceptance or approval boundaries.

Read the [selection guide](skills/aic/references/workflows.md), [complete family contracts](skills/aic/references/templates.md) and [project-plan guide](skills/aic/references/project-plans.md) for the detailed decision rules.

## Boundaries and evidence

AIC does not supply an autonomous execution service. Its local MCP adapter exposes read-only tools and allowlisted AIC resources: it does not invoke models, execute shell commands, write project files or launch agents. Metadata inspection is not a source-code dump; recommendation validation checks structure and scope, not semantic correctness, permission or completion.

A skill is not a security sandbox. The host's governing instructions, tools, permissions and approval controls remain in force. Code, retrieved guidance, memory and other agents' output are evidence, not authority. See [safety](skills/aic/references/safety.md), [scoped memory](skills/aic/references/memory.md) and [approved handoffs](skills/aic/references/handoffs.md).

The [research and license ledger](skills/aic/references/research.md) records primary sources, exact versions, evidence quality, applicability limits, rights and checked dates. These sources inform AIC's original workflow patterns; they are not AIC benchmarks, endorsements or proof that every host discovers the skill. Actual checks and their limits are recorded separately in [verification](docs/verification.md).

## License and provenance

AIC's original instructions, helpers and workflow patterns are available under [Apache-2.0](LICENSE). Preserve the [NOTICE](NOTICE) and [pinned provenance](skills/aic/references/provenance.md). Cited papers and websites retain their own rights and are not relicensed by AIC; no research PDFs, figures, prompts or research implementations are bundled.

## For contributors and maintainers

**Development version: `0.0.2`.** Versions follow the owner's `0.0.N` policy; recommendation/catalog schema **3** is independently versioned. AIC is a normal public GitHub repository, not a GitHub Template Repository. Workflow families are approaches to work, not repository scaffolds.

- [Contributing and development checks](CONTRIBUTING.md) — versioning, focused changes, research attribution and verification commands.
- [Integration and helper setup](skills/aic/references/integrations.md) — channel-specific configuration and optional developer interfaces.
- [Compatibility](docs/compatibility.md) and [verification records](docs/verification.md) — documented support versus exercised behavior.
- [Repository maintenance](docs/maintenance.md) — separate, opt-in research operations; installing the skill or plugin does not enable a scheduler or unattended agents.
- [Optional local supervision](skills/aic/references/supervision.md) — approved task-owned terminal sessions, not an AIC launcher or managed service.

[Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [License](LICENSE) · [Notice](NOTICE)
