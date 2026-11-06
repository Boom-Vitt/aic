![AIC — AI Culture](docs/assets/aic-banner.svg)

# AIC — AI Culture

Created and maintained by **[Boom-Vitt](https://github.com/Boom-Vitt)**.

**Choose the workflow before the agent starts changing things.**

AIC helps your AI agent turn a task or project plan into the right workflow: inspect relevant context read-only, identify dependencies and risks, select a reusable template, and define ownership and acceptance before execution.

Your existing host supplies the reasoning. AIC provides portable instructions and deterministic local helpers—not a bundled model, an automatic intent classifier, or a reason to add more agents to every task.

## Install

Requirements: Git for obtaining the repository; Python **3.11+** for helpers; a compatible host agent. Managed installation/uninstallation requires POSIX directory-descriptor support (macOS/Linux); Windows mutations fail closed instead of using an unsafe fallback. No pip packages or model keys are required by AIC.

Clone the repository, then install into your host's **documented skill directory**:

```sh
git clone https://github.com/Boom-Vitt/aic.git
cd aic
python3 scripts/aic.py install --agent generic --destination /absolute/path/to/skills
```

The destination is the directory that contains skills, not the AIC directory itself. Review a pinned revision before executing local code when reproducibility matters; do not pipe a remote installer into a shell.

Named adapters, project/user scopes and host-specific discovery details are documented in the [compatibility guide](docs/compatibility.md). A successful file installation is not proof of native discovery.

No settings are edited and no agent is launched by installation. Intact identical installs are unchanged; unmanaged or user-modified content is refused rather than overwritten.

Updates are explicit: fetch and review the desired revision, then rerun the same managed installation command. Repository research updates do not silently synchronize installed copies or overwrite local edits.

## Use

Restart/reload skill discovery as your host requires, then ask:

> Use AIC to inspect this project read-only and recommend how to approach this task or project plan. Select a workflow template from the evidence, explain the topology, scope, ownership, risks and acceptance checks, and obtain any required approval before changing files or launching agents.

```mermaid
flowchart LR
    Inspect[Inspect read-only] --> Recommend[Recommend a workflow]
    Recommend --> Scope{Within approved scope?}
    Scope -->|Yes| Verify[Execute and verify]
    Scope -->|No| Clarify[Resolve scope first]
```

## What gets selected?

Task category, workflow template, topology and runtime/model are separate decisions. The host AI makes them using the actual goal, dependencies, risks and available tools.

| Template | Select when |
| --- | --- |
| `direct` | Work is small/coupled and one owner can implement and verify it |
| `explore-build` | Substantial independent discovery is the bottleneck before implementation |
| `ordered-handoff` | Delegated units depend on confirmed upstream artifacts or share mutation boundaries |
| `isolated-build` | Substantial implementation units have agreed interfaces and independent acceptance |
| `independent-review` | Consequential acceptance gaps justify a separately briefed evaluator |
| `durable-controller` | Long-running work needs compact state, artifact dependencies and explicit recovery ownership |
| `adaptive-optimization` | A measured optimization task has a diagnosed plateau and approved experiment limits |

Read the [selection guide](skills/aic/references/workflows.md), [complete templates](skills/aic/references/templates.md), and [project-plan guide](skills/aic/references/project-plans.md). Choose per milestone; do not force every project through all seven templates or confuse template choice with model choice.

## Evidence and rights

The [evidence ledger](skills/aic/references/research.md) records exact source versions, evidence quality, applicability limits, license status and checked dates. Summaries and workflow templates are original AIC material; cited publications are reference-only. No paper PDFs, figures, prompts or research implementations are bundled. Detailed source attribution and required notices remain in the reference files and [NOTICE](NOTICE).

## Local helpers

```sh
python3 scripts/aic.py agents
python3 scripts/aic.py inspect /path/to/project
python3 scripts/aic.py check-plan recommendation.json --project /path/to/project
python3 scripts/aic.py memory-read --project /path/to/project
```

`inspect` returns a bounded metadata inventory, not a source-code dump. `check-plan` validates recommendation structure and scope, not semantic truth or consent. Learn more about [routing](skills/aic/references/routing.md), [scoped memory](skills/aic/references/memory.md), and [approved handoffs](skills/aic/references/handoffs.md).

Recommendation schema 2 requires an explicit `template` and checks compatibility with the selected topology, including ordered `sequential` work. Version-1 recommendations are rejected rather than silently assigned a workflow. Regenerate older recommendations from their real task, dependencies and current authorization; see the [migration and full contract](skills/aic/references/routing.md). Validation cannot prove semantic task selection, interface independence or human consent.

Inspection has finite entry and directory budgets, including excluded entries. Returned selected items are sorted, but a truncated subset follows filesystem enumeration order rather than claiming a globally sorted scan of an arbitrarily wide directory.

The rule is **recommend first, approve once, then execute within scope**. Existing explicit task approval is sufficient; do not ask again for every routine step. New spending, credentials, deployment or materially expanded scope still require their own authorization. A skill and a digest flag are not a security sandbox or proof of human identity.

## Research maintenance

The optional [repository maintainer](docs/maintenance.md) checks primary sources daily, creates assigned research/adoption tasks, and proposes original evidence records for independent review. Automatic merges are limited to new research records after local and repository checks pass.

Workflow instructions, code, CI, credentials and permission changes remain manual. The maintainer is separate from the installed skill, uses at most two unattended agent runs per day, and requires explicit setup; installing AIC does not enable it.

## Uninstall

Use the same destination selectors as installation:

```sh
python3 scripts/aic.py uninstall --agent generic --destination /absolute/path/to/skills
```

Only an intact manifest-owned AIC directory is removed. Modified files, extra content and unrelated parent/sibling data are preserved. Keep your edits and inspect a refusal; there is no force-delete option.

## Verify

```sh
./scripts/verify.sh
```

Verification is offline and uses isolated fixtures. It exercises installation boundaries, recommendation schemas, path/privacy protections, memory authority, maintenance safety gates and launch dry runs. Actual host consumption and operational maintenance have separate evidence; see [verification results and limits](docs/verification.md). The offline command does not launch models, publish changes or provision resources.

## Project layout

- `skills/aic/`: self-contained skill, references, catalog, adapter registry and Python helpers.
- `scripts/`: checkout CLI and offline verification entrypoint.
- `maintenance/`: opt-in primary-source discovery, bounded agent jobs and guarded repository maintenance.
- `tests/`: consumer-visible regressions and scenario fixtures.
- `docs/`: compatibility, evidence, provenance and verification.

[Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [License](LICENSE) · [Notice](NOTICE)
