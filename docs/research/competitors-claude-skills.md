# Competitor research: Claude Code skills, plugins, and agent workflows

Snapshot date: **2026-11-07** (UTC). Counts are GitHub REST `GET /repos/{owner}/{repo}` fields `stargazers_count` and `forks_count` from that day. They are popularity signals, not quality, security, or license clearance, and they move. This note does not copy upstream code, prompts, skill text, or README prose. Architecture statements come from repository trees, plugin manifests, license headers, and heading lists read that day. No competitor test suite was executed.

AIC's product boundary stays in force for every recommendation below: skills-first guidance, a skills-only Claude Code plugin (no hooks, permission overrides, or automatic server startup), and an optional local read-only MCP adapter. This review does not propose promotion, a second agent runtime, or a public component registry.

## How AIC was compared

AIC 0.0.3 already ships one portable skill, five original workflow families, schema-3 recommendation validation, scoped memory and handoffs, a research and rights ledger, documented harness discovery paths with evidence levels, a one-plugin marketplace, and four read-only MCP tools bound to one approved project. The host reasons and executes. AIC does not launch agents, infer a workflow with a keyword classifier, or read project source through MCP.

A feature counts as missing only when that consumer-visible surface is absent. A large catalog of role prompts is not, by itself, a missing AIC feature.

## Inclusion rule

Profiled repositories are public projects whose main artifact is a skill library, a Claude Code plugin, a workflow or planning system, a curated catalog of those, or the Agent Skills specification. The search queries were `claude-code`, `claude code skills`, `claude code plugins`, `awesome claude code`, and `claude-code-templates`, then the named projects in the task. Confirmed with the repos API.

Left out of the profiles, even when search ranked them highly: the Claude Code product repository itself, leaked system-prompt collections, token-compression proxies, model gateways, desktop switchers, job-search agents, and vertical marketing or social-post skills. `anthropics/claude-code` had **154,898** stars and **25,599** forks on the snapshot day and no SPDX license. It is the host product, not an open skill source.

License reading: the root `LICENSE` (or its absence) was fetched for every profiled repository. Where the root file was missing, sampled skill licenses or a README license section are reported separately. A root MIT or Apache-2.0 grant was not treated as clearance for every file, dependency, or embedded skill.

## Snapshot

| Repository | Stars | Forks | License as read | Pushed | Role |
| --- | ---: | ---: | --- | --- | --- |
| [obra/superpowers](https://github.com/obra/superpowers) | 314,023 | 27,936 | MIT, Copyright (c) 2025 Jesse Vincent | 2026-11-03 | Methodology skill plugin |
| [affaan-m/ECC](https://github.com/affaan-m/ECC) | 299,062 | 44,183 | MIT, Copyright (c) 2026 Affaan Mustafa | 2026-11-06 | Multi-harness skill/hook bundle |
| [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) | 230,573 | 22,941 | No root license file | 2026-04-20 | One-file behavior guide |
| [anthropics/skills](https://github.com/anthropics/skills) | 188,606 | 22,239 | No root license file; sampled skills Apache-2.0 | 2026-11-06 | Official example skills |
| [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | 146,488 | 15,504 | MIT, Copyright (c) 2024 Next Level Builder | 2026-11-07 | One vertical design skill |
| [garrytan/gstack](https://github.com/garrytan/gstack) | 140,626 | 20,761 | MIT, Copyright (c) 2026 Garry Tan | 2026-11-07 | Opinionated sprint toolkit |
| [thedotmack/claude-mem](https://github.com/thedotmack/claude-mem) | 114,380 | 9,924 | Apache-2.0 license text | 2026-11-07 | Session-memory service |
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | 113,872 | 11,897 | MIT, Copyright (c) 2025 Addy Osmani | 2026-11-01 | Engineering skill set plus evals |
| [ruvnet/ruflo](https://github.com/ruvnet/ruflo) | 81,156 | 9,547 | MIT, Copyright (c) 2024-2026 ruvnet | 2026-11-07 | Swarm harness and plugin |
| [shareAI-lab/learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) | 80,018 | 12,799 | MIT, Copyright (c) 2024 shareAI Lab | 2026-10-27 | Layered harness tutorial |
| [ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills) | 78,987 | 9,599 | README claims Apache-2.0; no root `LICENSE` | 2026-09-18 | Skill catalog |
| [shanraisshan/claude-code-best-practice](https://github.com/shanraisshan/claude-code-best-practice) | 68,769 | 6,850 | MIT, Copyright (c) 2025-2026 Shayan Rais | 2026-11-07 | Workflow and practice notes |
| [gsd-build/get-shit-done](https://github.com/gsd-build/get-shit-done) | 64,157 | 5,444 | MIT, Copyright (c) 2025 Lex Christopherson; archived | 2026-05-31 | Spec-driven workflow system |
| [hesreallyhim/awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) | 57,463 | 4,925 | CC BY-NC-ND 4.0 | 2026-11-07 | Curated resource list |
| [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | 46,349 | 4,823 | Apache-2.0 license text | 2026-11-07 | Official plugin directory |
| [wshobson/agents](https://github.com/wshobson/agents) | 42,282 | 4,469 | MIT, Copyright (c) 2024 Seth Hobson | 2026-11-05 | Generated multi-harness plugins |
| [davila7/claude-code-templates](https://github.com/davila7/claude-code-templates) | 33,187 | 3,890 | MIT, Copyright (c) 2025 Daniel (San) Ávila | 2026-11-07 | Component registry and CLI |
| [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills) | 29,447 | 4,084 | MIT, Copyright (c) 2025 Alireza Rezvani | 2026-11-05 | Large multi-domain skill repo |
| [jarrodwatts/claude-hud](https://github.com/jarrodwatts/claude-hud) | 29,133 | 1,334 | MIT, Copyright (c) 2026 Jarrod Watts | 2026-11-03 | Status-line plugin |
| [OthmanAdi/planning-with-files](https://github.com/OthmanAdi/planning-with-files) | 27,940 | 2,314 | MIT, Copyright (c) 2026 Ahmad Adi | 2026-11-07 | File-based durable plans |
| [agentskills/agentskills](https://github.com/agentskills/agentskills) | 27,045 | 2,003 | Apache-2.0 code and spec; docs CC BY 4.0 | 2026-11-04 | Agent Skills specification |
| [VoltAgent/awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents) | 26,400 | 3,022 | MIT, Copyright (c) 2025 VoltAgent | 2026-11-02 | Subagent persona catalog |
| [travisvn/awesome-claude-skills](https://github.com/travisvn/awesome-claude-skills) | 15,736 | 2,125 | No license file | 2026-04-28 | Skill link list |
| [diet103/claude-code-infrastructure-showcase](https://github.com/diet103/claude-code-infrastructure-showcase) | 10,049 | 1,207 | MIT, Copyright (c) 2025 Claude Code Infrastructure Contributors | 2026-07-13 | Hooks-driven skill activation |
| [disler/claude-code-hooks-mastery](https://github.com/disler/claude-code-hooks-mastery) | 3,971 | 641 | No license file | 2026-03-04 | Hooks tutorial |

`affaan-m/everything-claude-code` resolved to `affaan-m/ECC` on the snapshot day. Fork counts are high enough on the leading rows that the star totals are not empty listings, which still does not measure whether the skills improve task success.

## Deep dives

### obra/superpowers

Plugin manifest on the default branch: `superpowers` **7.0.2**, MIT. The tree is a skills library plus harness adapters (`.claude-plugin`, `.codex-plugin`, `.cursor-plugin`, `.opencode`, `.pi`, `.hermes-plugin`, and others), `docs/porting-to-a-new-harness.md`, and per-harness tests (`tests/claude-code`, `tests/codex`, `tests/opencode`, `tests/pi`, `tests/hermes`, plus skill-layout and skill-size tests). `hooks/hooks.json` contains one `SessionStart` entry, and `hooks/session-start` is present.

Fifteen skill directories: `using-superpowers`, `brainstorming`, `writing-plans`, `executing-plans`, `test-driven-development`, `systematic-debugging`, `verification-before-completion`, `requesting-code-review`, `receiving-code-review`, `dispatching-parallel-agents`, `subagent-driven-development`, `using-git-worktrees`, `finishing-a-development-branch`, `writing-skills`, `diagnosing-superpowers`.

What the traction tracks: a small set of daily engineering procedures, install paths for many hosts, and a session hook so the library is in force without the user naming it. The procedures match work AIC only describes inside family contracts.

AIC lacks separately triggered procedure skills, a session-start mechanism (deliberately: the native plugin is skills-only), per-harness plugin packages with automated sync tests, and a skill-size test. The useful, compatible slice is the procedure split and the size test. The hook is a product conflict, not a gap to close inside the native plugin.

### affaan-m/ECC

MIT. The default-branch git tree contained **314** directories directly under `skills/`, **71** under `agents/`, and **98** under `commands/`. The root also has `hooks/`, `rules/`, `mcp-configs/`, `plugins/`, `schemas/`, many host folders (`.claude-plugin`, `.codex-plugin`, `.cursor`, `.gemini`, `.opencode`, `.pi`, and others), `install.sh` / `install.ps1`, and a low-context install path called out in the README headings. Sampled skill names include `agent-eval`, `agent-security-hardening`, `benchmark`, `benchmark-methodology`, and `browser-qa`. The README headings also describe TDD, rules, and shared context across harnesses. Those headings were not counted as an independent inventory.

Traction tracks coverage: one install that tries to be an agent operating environment, with a no-hooks option for people who do not want that much injection.

AIC lacks a security-review procedure, a benchmark-methodology procedure aimed at skill or workflow impact, and a browser-QA procedure. AIC should not absorb the hook bundle, the MCP config bundle, the agent roster, or the installer as the product entry point.

### multica-ai/andrej-karpathy-skills

**230,573** stars and no `LICENSE` file in the root listing. The only skill directory observed was `skills/karpathy-guidelines/`. The repository description says the guide is derived from Andrej Karpathy's observations. That description is not an authorship or endorsement check. Last push on the snapshot was **2026-04-20**, so the tree was stale relative to the star count.

Traction tracks a short, opinionated behavior file with a recognizable attribution, across Claude Code and Cursor paths.

AIC must not quote or copy that file. The product lesson that is safe to use is demand for a short trigger document. AIC's `SKILL.md` is already that entry point; the missing piece is additional short triggers for procedures, written originally.

### anthropics/skills

No root `LICENSE`. GitHub's license API returned none, matching that listing. The marketplace file is `anthropic-agent-skills`. Nineteen skill directories were listed, including `skill-creator`, `frontend-design`, `webapp-testing`, `mcp-builder`, `claude-api`, document skills (`docx`, `pdf`, `pptx`, `xlsx`), and creative skills (`algorithmic-art`, `canvas-design`, `theme-factory`, `slack-gif-creator`). `spec/agent-skills-spec.md` points at the external specification rather than vendoring it.

Apache-2.0 `LICENSE.txt` was present and read in `skills/skill-creator`, `skills/docx`, `skills/pdf`, `skills/frontend-design`, and `skills/webapp-testing`. The other fourteen skill directories were not opened. `skill-creator` also contains `eval-viewer/`, `agents/`, `scripts/`, and `references/`. `THIRD_PARTY_NOTICES.md` attributes components under BSD-2-Clause and GPL-3.0, including FFmpeg. A root-level Apache grant was not found, so the repository is not one license.

Traction tracks official examples: document skills, a skill authoring tool with an eval viewer, and a marketplace people can install.

AIC already credits skill-creator as a structural reference in `NOTICE` at a pinned revision and does not redistribute those skills. Still missing relative to this repo: an AIC skill-authoring check with fixtures, and a consumer-visible eval for whether a skill's contract holds. Copying the example skills or the eval viewer would require a file-by-file notice review and would also have to exclude the GPL-3.0 third-party components. That copy is not recommended.

### nextlevelbuilder/ui-ux-pro-max-skill

MIT. One design skill with a Claude marketplace plugin, a CLI, stack-specific guidance, and a persisted design-system layout described in the README headings. The repository description calls it design intelligence for professional UI. This review did not audit data files or the premium/basic split beyond those headings.

Traction shows that a single deep vertical skill can out-star a general methodology repo. AIC's job is workflow selection, so a design-system catalog is out of scope. The transferable product fact is specificity: one skill whose description matches a recognizable task.

### garrytan/gstack

MIT. The GitHub description says the repo is Garry Tan's setup of 23 tools covering roles such as CEO, design, engineering management, release, docs, and QA. This review did not independently count 23 packages; the root listing is large and includes `benchmark/`, `benchmark-models/`, `browse/`, `eval-plan/`, `agents/`, and per-host folders. `docs/skills.md` headings observed that day name workflows including office-hours, plan reviews, design review and design production, review, investigate, verify, QA, ship, land-and-deploy, and modernize. Further docs cover skill gates, review policy, ship policy, evals, and a browser.

Traction tracks an opinionated sprint: plan, review, QA in a browser, then ship, with benchmarks in-tree.

AIC lacks a review-finding artifact, a changed-surface verification procedure, and any in-repo evaluation of whether a workflow choice was the right one. AIC's families already warn against a fixed role roster, so the CEO/designer/QA agent team is not a feature to add. The sprint's evidence gates are the part that fits.

### thedotmack/claude-mem

Apache-2.0 license text at the root. Plugin manifest `claude-mem` **15.11.1** describes persistent memory so a later session continues the previous one, for Claude Code, Codex, Cursor, OpenCode, and others. The tree includes `src/`, `services/`, `plugin/`, host packages (`.claude-plugin`, `.codex-plugin`, `.cursor-plugin`, `.grok-plugin`, `openclaw`, `pi`, `omp`), `docker-compose.yml`, and docs such as `docs/architecture/observer-lifecycle.md`, `docs/native-memory-bridge.md`, and `docs/transcript-watch.example.json`. The plugin keywords include MCP, compression, transcript, and knowledge-graph. This is a running capture-and-recall service, not a guidance skill. The service internals were not executed.

Traction tracks the failure mode where compaction or a new session drops the plan. The implementation captures session activity and injects it later.

AIC already has scoped, source-backed memory promotion and a file-only handoff schema, and it treats unreviewed transcripts as unsafe to preload. The missing piece is a durable plan the host can re-read after compaction without a capture daemon. Importing claude-mem's observer would fight AIC's privacy and approval rules even though the license is compatible. Any future use of Apache-2.0 code from this repo would still need the license and notices retained; this review does not copy any.

### addyosmani/agent-skills

MIT. Twenty-five skill directories, four agent files (`code-reviewer`, `security-auditor`, `test-engineer`, `web-performance-auditor`), nine command files, `hooks/`, and `evals/` (`cases/`, `fixtures/`, `plugin/`, `skill-impact.md`). Skill names cover planning, spec-driven and constraint-driven development, TDD, debugging, code review, security, browser testing with devtools, context engineering, incremental implementation, and shipping.

Traction tracks production engineering procedures plus an eval directory, from an author with an existing engineering audience. The eval cases were not copied or scored.

AIC's catalog can express the same task shapes as family choices, and it does not ship these procedures or a scenario pack that checks the choice. That is the highest-signal gap in the set: comparable skills exist, and at least one peer stores eval fixtures beside them.

### ruvnet/ruflo

MIT. Root contains a Claude plugin, `plugins/`, `SKILL.md`, `skills.sh.json`, Rust crates, `v3/`, and `verification/`. The description presents multi-agent swarms, adaptive memory, and native host integrations. Internals were not reviewed beyond that tree.

Traction tracks people who want a harness that runs many agents. AIC's research ledger already treats fixed swarms as a non-default, and the product does not launch agents. No ruflo feature is recommended for import. Verification notes in a swarm repo are a reminder that AIC's own claims need receipts, which `docs/verification.md` already separates from documentation.

### shareAI-lab/learn-claude-code

MIT. Seventeen numbered lesson directories run from `s01_agent_loop` through tool use, permissions, hooks, todos, subagents, skill loading, context compaction, memory, a task system, background tasks, cron, agent teams, an MCP plugin, an integrated harness, a workflow runtime, and `s17_goal_loop`. Docs exist in English, Japanese, and Chinese.

Traction tracks a from-scratch teaching harness. It is useful as a map of host layers AIC assumes and does not reimplement. Vendoring the lessons, even with MIT attribution, would turn AIC into a second runtime. Not recommended.

### shanraisshan/claude-code-best-practice

MIT. Root directories include `best-practice`, `development-workflows`, `orchestration-workflow`, `agent-teams`, `tutorial`, `implementation`, and `reports`, with `.claude` and `.codex` trees. The description frames the repo as practice material from vibe coding toward agentic engineering. Individual articles were not read, so this note does not restate their advice.

AIC lacks a worked tutorial that shows one task moving through recommend, approve, and an evidence-backed outcome. The practice content itself stays upstream.

### gsd-build/get-shit-done

MIT. **Archived.** Description: a meta-prompting, context-engineering, and spec-driven system for Claude Code. The tree has `commands/`, `hooks/`, `agents/`, `sdk/`, `get-shit-done/`, and docs including `STATE-MD-LIFECYCLE.md`, `context-monitor.md`, and `issue-driven-orchestration.md`. Last push **2026-05-31**, with **64,157** stars still on the snapshot. Archive status means the star count is historical traction.

The idea that matches AIC is explicit state that survives a long run. GSD's hooks, command CLI, and archived maintenance do not. AIC's adaptive-controller family already requires durable state; it does not define the files a host should rewrite after compaction.

### Official and specification repos

`anthropics/claude-plugins-official` is Apache-2.0 at the root (standard license text; a separate copyright notice line was not in the header that was read). The `plugins/` listing had **41** directories and `external_plugins/` had **14**. Names relevant to workflow quality include `code-review`, `pr-review-toolkit`, `security-guidance`, `claude-security`, `feature-dev`, `skill-creator`, `plugin-dev`, `session-report`, `commit-commands`, `code-simplifier`, `hookify`, and `code-modernization`. Many others are language servers. README headings cover an internal versus external split and immutable plugin names.

This is the distribution channel AIC does not occupy. `docs/compatibility.md` already says AIC claims no official-directory listing. Joining that directory would be a distribution task, which this review does not propose. The capability gap is the existence of first-party review, security-guidance, and session-report plugins. Their text was not read and is not cleared for copying by this note; the root license is Apache-2.0, so a future copy would require the Apache notices. The recommendation is to write original procedures.

`agentskills/agentskills` is the specification AIC already follows. `GOVERNANCE.md` requires Apache-2.0 for code and specification contributions. `docs/LICENSE` is CC BY 4.0, so specification text and the surrounding docs are different grants. AIC's `NOTICE` already records that split at a pinned revision. No spec text is copied here.

### wshobson/agents

MIT. **92** plugin directories, plus `evals/` (including `static-score-snapshot.json`), `tools/`, and docs `architecture.md`, `authoring.md`, `harnesses.md`, `plugin-eval.md`, and `round-trip-results.md`. The repository description says plugins, agents, skills, and commands are written once in Markdown and adapted per tool by generators with validation and evals. Host folders include `.claude-plugin` and `.cursor-plugin`. The generator source was not reviewed line by line, and the score snapshot was not treated as an AIC result.

AIC documents several skill discovery paths and ships a Claude Code plugin only. It does not generate per-host plugin manifests, and it should not add those manifests until a host is actually exercised. The portable idea is the eval snapshot: a checked artifact that records what was measured, on which fixture, with an explicit limit. AIC's verification receipts are maintainer logs, not a skill-impact fixture.

### davila7/claude-code-templates

MIT. Description: an open-source registry and CLI for agents, commands, skills, hooks, MCPs, settings, and mods. The tree includes `cli-tool/`, `cli-rust/`, `dashboard/`, `cloudflare-workers/`, `docs/`, and `component-validation.json`. The live registry was not called.

A public registry would be a different product and a second entry point. AIC's contributing guide already keeps the host agent as the way users work. Not recommended. `component-validation.json` is another existence proof that peers validate component shape in CI. AIC already validates recommendations; it does not yet validate a held-out choice against a labeled scenario.

### alirezarezvani/claude-skills

MIT. The description claims 410 skills and 120+ agents across engineering, marketing, product, compliance, finance, and operations. This review did not count the skill files, so **410** and **120** stay the author's description, not an independent census. The root listing does show separate trees for engineering, marketing, finance, research, product, compliance, commands, and agents, plus `SKILL-AUTHORING-STANDARD.md` and `SKILL_PIPELINE.md`.

Breadth is the popularity mechanism and also the reason it is a weak template for AIC. A standards file for skill authors is the only adjacent gap, and AIC can enforce a thin `SKILL.md` with an original test instead of adopting that standard's text.

### jarrodwatts/claude-hud

MIT. Description: a plugin that shows context usage, active tools, running agents, and todo progress. The tree is a Node status-line project (`hud.mjs`, `src/`, `tests/`) with a small `skills/` directory. Status lines in Claude Code are a host UI hook, which AIC's plugin policy excludes.

Demand is real (**29,133** stars) and the feature stays outside the native plugin. A skill cannot honestly draw a live HUD. No import.

### OthmanAdi/planning-with-files

MIT. Skills: `planning-with-files` and `i18n`. Templates present: `task_plan.md`, `findings.md`, `progress.md`, `loop.md`, `analytics_task_plan.md`, `analytics_findings.md`. Hooks: `hooks.json`, `claude-hook.sh`, `codex-hooks.json`, `qoder-hooks.json`. Docs include per-host install notes, `docs/benchmark/`, `docs/evals.md`, and articles whose filenames describe recovery after `/clear` and compaction. The description says file-based plans survive crashes and context clears, with a deterministic completion gate, and that hooks re-inject the plan. Those behavior claims were not re-tested here.

This is the closest product to AIC's handoff and adaptive-controller guidance, and it is more concrete: named files, a completion gate, and published eval notes. AIC's MCP adapter cannot read those files (inspection returns names and sizes only), and the native plugin cannot install the hooks. The license-safe version is a host-written plan, validated when the host passes it to the existing validator, with instructions to re-read it after compaction. The upstream template text stays upstream. MIT would allow a derivative with the copyright notice; AIC's own policy is original wording.

### VoltAgent/awesome-claude-code-subagents

MIT. Ten category directories from core development through research, plus `install-agents.sh` and a plugin. The description says 100+ specialized subagents. The category directories were not enumerated file by file, so the 100+ figure remains the repository description.

AIC's worker model is a brief with a scope, not a persona library. A catalog of named agents would freeze a roster the workflow guide tells the host to avoid. The safe feature is a stricter brief, listed below.

### diet103/claude-code-infrastructure-showcase

MIT. `.claude/` contains `agents`, `commands`, `hooks`, `scripts`, `settings.json`, and `skills`. README headings describe hook-driven skill auto-activation, a `skill-rules.json` switch, and an optional external model key for classification. The same headings state catalog sizes of 4 skills, 9 hooks, 8 agents, and 4 slash commands. Those are the author's headings, not a recount.

Auto-activation by a hook or a second model conflicts with recommendation-first host reasoning and with "no extra inference API key." The compatible substitute is a skill description specific enough that the host's own skill trigger can select it.

## Catalogs

`hesreallyhim/awesome-claude-code` is the largest general Claude Code list in this search (**57,463** stars). The root `LICENSE` is Creative Commons Attribution-NonCommercial-NoDerivatives 4.0. The file says the maintainer chose that grant to limit modified reuse. AIC can cite the repository. AIC cannot adapt the list, copy the resource table, or build a derivative catalog from it. NonCommercial is also incompatible with folding the list into Apache-2.0 material. The list's scope, from its description and tree (`THE_RESOURCES_TABLE_NEW.csv`, `resources/`, a generator script), is skills, agents, status lines, hooks, and plugins. That scope explains demand. It is not a feature specification AIC can reuse.

`ComposioHQ/awesome-claude-skills` (**78,987** stars) has no root `LICENSE` file. The README license section states Apache-2.0 and says individual skills may differ. Several directories share names with Anthropic example skills (`skill-creator`, `mcp-builder`, document skills, `theme-factory`, `slack-gif-creator`). Until each folder's license is read, the bodies are not cleared. This note uses the repo only as evidence that skill catalogs attract stars.

`travisvn/awesome-claude-skills` (**15,736** stars) has no license file and a last push of **2026-04-28**. Link lists without a license are not sources for AIC text.

`disler/claude-code-hooks-mastery` (**3,971** stars) has no license file. It is a hooks tutorial, which is outside the plugin policy and uncleared to quote.

## What the popular set actually sells

The high-star repositories cluster into a few mechanisms:

1. **Named procedures for daily work.** Superpowers and Addy Osmani ship plan, TDD, debug, review, and verify as separate skills. AIC ships the decision among five families and leaves the procedure in long references.
2. **Something that survives compaction.** claude-mem captures sessions. planning-with-files and archived GSD put the plan in files and re-inject it. AIC can validate a handoff and promote a reviewed note; it does not give the host a plan file to reopen.
3. **Evaluation artifacts.** Addy Osmani, wshobson, gstack, and planning-with-files keep evals, benchmarks, or score snapshots in the repo. AIC's tests check safety and schema behavior. They do not check that a labeled task selects a labeled family.
4. **Many hosts.** Superpowers, ECC, and wshobson ship per-host packages. AIC copies one skill into documented discovery directories and only manifests a Claude Code plugin. Extra manifests without live discovery evidence would over-claim.
5. **Injection.** Session hooks, status lines, auto-activation classifiers, and memory daemons are common and popular. They conflict with the skills-only plugin, the read-only MCP adapter, and scoped memory.
6. **Breadth and personas.** ECC, wshobson, VoltAgent, Alireza Rezvani, and gstack's role roster win stars with surface area. AIC's research position is that a fixed team is not a default.

## Features AIC lacks

These are consumer-visible gaps, restricted to behavior that can exist inside AIC's boundaries:

- Triggerable procedure skills for planning, debugging, verification, and clean-input review.
- A held-out scenario pack that pairs a task with the family and topology the contract requires.
- A durable plan record the host re-reads after compaction, without a hook or a daemon.
- A review-finding record with a location, an observation, and room for a bounded no-findings result.
- A security-review procedure that never opens secrets and never runs attack tooling on its own.
- A changed-surface verification record for UI and non-UI work.
- Worker-brief fields beyond `goal`, `allowed_paths`, and `acceptance` (read scope, inherited context, return artifact, stop condition).
- A test that keeps `SKILL.md` a thin entry point.
- A consumer outcome card (`passed`, `partial`, `blocked`) separate from maintainer verification receipts.
- A CI check that compatibility claims point at real receipts.

## Do not import

- Superpowers' `SessionStart` hook, ECC's hooks and MCP bundle, diet103's classifier, claude-hud's status line, and planning-with-files' re-injection hooks. The native plugin stays skills-only.
- claude-mem's capture-all memory path. Scoped promotion stays the memory model. The Apache-2.0 license does not override that product rule.
- Fixed swarms and persona catalogs (ruflo, VoltAgent, gstack's role team, ECC's agent directory).
- Unlicensed text: Karpathy guidelines, travisvn's list, disler's hook guide.
- hesreallyhim's list or table (CC BY-NC-ND 4.0).
- Composio skill bodies until each folder's license is read. Shared names with Anthropic skills are a reason to be stricter, not looser.
- Anthropic example-skill implementations and the skill-creator eval viewer. Sampled skills are Apache-2.0; the repo has no root license, and `THIRD_PARTY_NOTICES.md` includes GPL-3.0 components. AIC already attributes skill-creator as a structural reference.
- Official plugin source, even under Apache-2.0, unless a later change retains the license and notices and reviews the file. This note recommends original procedures instead.
- The learn-claude-code lesson harness. MIT would allow a credited derivative; AIC is not a second agent loop.
- Marketing, SEO, job-search, and social-post skills. They are outside this product.
- Any star-count or benchmark figure printed by those READMEs. None of those performance numbers are repeated here because this review did not reproduce them.

## Ranked license-safe improvements

Ranking is a judgment of product-quality value for AIC from this review. It is not a measured bake-off. Effort is change size, not a schedule. Every item is original AIC writing and tests. None of them copy upstream skill text. If a later change does copy MIT or Apache-2.0 material, keep that upstream license notice and add the attribution to `NOTICE`.

1. **Held-out workflow-selection scenario pack.** Add task fixtures with the family, allowed topologies, and the reason a simpler family is insufficient. A deterministic test accepts only a schema-3 recommendation that matches the label. Live model scoring stays outside `./scripts/verify.sh` and, when someone runs it, records the host and model. This is the benchmark gap peers already file under `evals/`. **Effort: medium.** New fixtures, a checker, and a short note in the verification docs. No schema migration.

2. **Separately triggered procedure skills.** Add original skills for plan-before-edits, debug-from-the-reported-failure, verify-the-changed-surface, and clean-input review. Keep them in the skills-only plugin, with descriptions specific enough for host skill triggering, and with no `hooks.json`. Names and steps are AIC's; the existence of the split is what superpowers and `addyosmani/agent-skills` demonstrate. **Effort: large.** Several skill trees, package and install coverage, and trigger descriptions that do not bloat the current `SKILL.md`.

3. **Compaction-surviving plan record.** Define an original JSON plan, findings, and progress record that the host writes only after approval and re-reads after compaction or a new session. Validate it by passing it to the existing recommendation or handoff validator. Do not add a hook, a watcher, or an MCP tool that reads arbitrary project files. **Effort: medium.** Schema snippets, examples, and validator tests aligned with the current handoff fields. Upstream template filenames and prose stay unused.

4. **Clean-input review finding record.** A finding needs the artifact version, the criterion, a location, the observation, and the impact. A no-findings result needs the surfaces that were not examined. Reject a passing review that omits either. This is the artifact `independent-review` selects for and does not yet format. **Effort: small.** One reference, one example, one validator.

5. **Security-review procedure.** An original checklist: do not open secret files, separate a reported dependency risk from a demonstrated exploit, run audit commands only when the user approved that command, and do not generate attack payloads. The MCP surface stays unable to execute a shell. **Effort: medium.** One skill or reference plus fixtures. Inspired by the existence of `security-guidance` in the official plugin directory and `agent-security-hardening` in ECC, without their rule text.

6. **Changed-surface verification record.** For a behavior change, record the command or route, the input, the observed result, the empty or error case when the surface has one, and the checks that were not run. A screenshot or a worker report does not fill the record. **Effort: small.** One procedure and one example card. No bundled browser.

7. **Richer parallel-worker brief.** Extend the parallel branch contract with read scope, inherited-context disclosure, the artifact to return, and a stop condition. Keep exclusive write paths and the one-integrator rule. This needs an explicit schema migration, not a silent extra field. **Effort: medium.** Routing schema, catalog, tests, and the workflow reference together.

8. **Thin skill-entry test.** Fail CI if `SKILL.md` stops pointing at the workflow, template, routing, and safety references, or if it grows past a ceiling AIC chooses in that test. The ceiling is local policy. It is not copied from a peer's skill-size test. **Effort: small.** One test and a contributing sentence.

9. **Consumer outcome card.** A validated record with the family used, the checks actually run, the outcome (`passed`, `partial`, or `blocked`), the environment, and the unknowns. Store it only when the user approved the write. It is an evidence format, not a performance claim and not a substitute for `docs/verification.md`. **Effort: small.** One schema and a validator.

10. **Compatibility claims tied to receipts.** A test fails when `docs/compatibility.md` states an evidence level that does not cite a receipt already present in `docs/verification.md`. Do not add untested per-host plugin manifests to imitate superpowers or ECC. **Effort: medium.** A parser test and receipt links where a claim is currently prose-only.

Implementing the ten items is follow-on work. This file is the research record only.
