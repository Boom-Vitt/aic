# Changelog

## 0.0.3 — 2026-11-08 (unreleased)
- Review Aider polyglot licenses and add a runtime Exercism fetch. `Aider-AI/polyglot-benchmark` has no root license file and is not fetched. The six named Exercism tracks have a root MIT license at the commits in `benchmarks/polyglot/pins.json`. That grant does not cover nested Catch BSL-1.0 or the Java Gradle Wrapper Apache-2.0. The agent workspace omits `.meta`, `.approaches`, and `.articles`. `python3 -m benchmarks.polyglot stub` proves fetch, sandbox wiring, and scoring with a local fixture and no model call. No public score is included.
- Add vulnerability-stewardship guidance to the skill. For a milestone that touches a trust boundary, the agent maps the boundary and uses the project's existing scanners when the run is approved. It confirms each finding with evidence (a reachable source line, a reproduced failing test or a version-matched advisory), fixes it test-first within the approved scope without weakening checks, and reports each item with its status. Findings never grant credential, permission or deployment authority.
- Add `scripts/run-benchmarks.sh` for one pinned AIC-versus-baseline run. It exits 3 without `ANTHROPIC_API_KEY`, prints a token-budget cost ceiling, and `--dry-run` does not call a model. `--routing-pack dev` is the default tuning pack. `heldout-v2` is the release pack and is scored once per release. A manual workflow uploads the provenance bundle. No public score is included.
- Document checkout and wheel installs for pip, pipx 1.8.0, and uv 0.9.26. The distribution name is `aiculture-skills`. The PyPI project named `aic` is unrelated, and this package is not published on PyPI. The wheel installs an `aic` console script whose `hello-world` command prints the install check. A pull-request workflow installs that wheel in a fresh venv and a fresh pipx home on Ubuntu and macOS, then makes one stdio `tools/list` call.
- Publish MCP input bounds that match server checks: `max_files` is 1..10000, `max_depth` is 0..32, and `section` is the declared guidance name with that longest name as `maxLength`. Every object in a tool input schema sets `additionalProperties` to false. Out-of-range values still fail with the existing fixed tool errors and those errors do not echo the rejected input. The recommendation `plan` value stays opaque JSON; its resource limits remain the validator's checks.
- Headless git reads reject command substitutions, here-strings, process substitutions, `git -c` / `--config-env`, gate scripts owned by the accepted plan, and slashless `git add` pathspecs that resolve outside the worktree.
- Add a benchmark harness skeleton that records a local smoke command and refuses to score SWE-bench, Terminal-Bench, Aider polyglot, or real-task suites. No public score is included.
- Add an aicbench container pipeline smoke. CI installs bubblewrap and runs the offline stub under `--sandbox container`. The stub is not a model result and is not a results-table row. A report is official only for that container run.
- Add an Orca v0.4.0 plus Claude Code project template: plan checks, a dry-run headless loop, a non-clobbering project bootstrap, a Mac mini setup script, safe project permissions, and CI lint/tests. The native plugin stays skills-only. The setup script does not handle secrets or call a model.
- Filter public issue/comment markers by approved-author provenance before uniqueness and reconciliation; retain owner ambiguity, assignment checks and uncertain-effect non-replay.
- Bound recommendation JSON, aggregate paths, path geometry and overlap work before project I/O across MCP, internal validation and approved handoff consumers. Preserve schema 3, detached unchanged values and physical isolation.
- Enforce end-to-end source deadlines with cancellable/reaped spawn-isolated transport, bounded non-executable IPC and parent-owned arXiv spacing.
- Bound reference-note size, entry count and aggregate bytes for both reading and promotion, preserving immutable/idempotent notes at capacity and controlled parser failures.
- Add reusable hosted dependency/secret security checks, a daily schedule and conservative Dependabot proposals. Make the existing required contract job explicitly depend on successful security checks without weakening branch protection.
- Retain security-tool provenance and license credits, private reporting guidance and measured verification limits. No release tag, PyPI publication, global installation or immutable-service upgrade is implied.

## 0.0.2 — 2026-11-07 (unreleased)
- Make the portable Agent Skill the default user experience: ask the existing host agent to use AIC, without a manual AIC CLI or Python prerequisite. Retain deterministic helper and maintainer commands as explicitly optional developer/operator interfaces.
- Add a native skills-only Claude Code plugin and single-plugin marketplace. Installation adds the same skill, not hooks, permission overrides, models or an automatically started server.
- Add an optional local stdio MCP adapter using the pinned official Python SDK. Four read-only tools expose the existing catalog/guidance, bounded metadata inspection and strict recommendation validation for one explicitly configured absolute project; no project rebinding, arbitrary file reads, writes, execution or model calls.
- Package the same portable tree and rights notices in an installable Python wheel, with the MCP SDK as an optional extra. Anchor the Python package so source startup cannot resolve the legacy helper script instead of the MCP adapter.
- Professionalize the public README around Skill/plugin/MCP choices and a host-agent example. Preserve the owner's original banner/byline and keep research, specification and dependency attribution in dedicated rights records.
- Keep recommendation/catalog schema 3, all five workflow families and the existing scoped maintenance authority unchanged. Add real protocol-boundary regressions and record actual native installation, source/wheel/host-started stdio and dependency-free-core checks in [verification](docs/verification.md).
- Source publication does not create a release tag, publish to PyPI or an official plugin directory, update global host installations, activate MCP globally or upgrade the immutable maintainer service.

## 0.0.1 — 2026-11-07 (unreleased)
- Use the owner's development-version sequence `0.0.1`, `0.0.2`, `0.0.3`, and onward. Renumber the active package/CLI/skill metadata without changing independently versioned schemas, runtime behavior or historical verification results.
- Consolidate the active catalog into five original task-adaptive workflow families: `direct`, `explore-build`, `coordinated-delivery`, `independent-review` and `adaptive-controller`. Select and compose by evidence, dependencies, risk and cost, not a universal winner, permanent team or keyword classifier.
- Require recommendation/catalog schema 3. Reject schema-1/2 recommendations and retired IDs without aliases or silent migration; independently versioned installation, memory, handoff and maintenance formats remain unchanged.
- Combine accepted-artifact ordered handoffs and ready isolated branches under coordinated delivery. Keep controller durable delivery separate from explicitly authorized, correctness-gated measured optimization; ordinary continuity needs no benchmark.
- Extend task/project guidance and evaluation scenarios across all six task categories, with original acceptance, ownership, readiness, context, permission, resource and stop boundaries preserved.
- Update primary-source credit, publication versions, evidence limits and rights records, including final COLM CAID, ICLR BOAD, Nature Co-Scientist, first-party research/orchestration documentation and tmux. Cited content remains reference-only; no research code, prompts or figures are bundled.
- Add an original optional tmux 3.8 profile and supervision guide: private socket/config, role/title borders, retained exit/signal states, native navigation, scoped cleanup and verified OMP Agent Hub controls. Process visibility never establishes task acceptance or launch/spend authority.
- Clarify that AIC is a normal public GitHub repository, not a GitHub template repository. Keep the owner-focused README and separate required legal/source credits.
- Source publication does not automatically refresh installed skills or upgrade the immutable maintainer service. This change creates no release tag or service activation; actual checks and limits are recorded in [verification](docs/verification.md).

Earlier entries below retain historical provisional labels and existing publication facts; they are not the current development-version sequence.

## 2.0.2 — 2026-11-07
- Read only service-level launchd lifecycle fields. Nested resource-coalition states and PIDs no longer block owned removal or get mistaken for the controller; missing or ambiguous controller evidence still fails closed.
- Make the lifecycle fixture reflect the actual Mac mini response and retain explicit wrong-PID, unknown-running-state and ownership-preservation coverage.
- Isolate role startup from ambient home/project plugins while binding the existing CLI authentication directory without copying credentials. Hash the private runtime binding in version-2 receipts; preserve older evidence without automatic reuse.

## 2.0.1 — 2026-11-07
- Fix initial branch protection on personal GitHub repositories by omitting organization-only bypass structures. The read-back policy still requires strict checks, administrator enforcement and pull requests, and rejects every nonempty bypass allowance.
- Preserve the ordinary two-role-runs-per-UTC-day limit; a separately recorded owner-approved, three-invocation supervised proof does not increase recurring capacity.

## 2.0.0 — 2026-11-06
- Add seven original, task-conditioned workflow templates and a milestone-planning guide with ownership, dependency, context, permission and acceptance contracts.
- Separate task category, template, topology and runtime/model choice. The host AI reasons about selection; the local helpers do not infer intent, schedule teams or rank vendors.
- Require recommendation schema 2 with an explicit compatible `template`; add `sequential` topology and reject schema-1 recommendations rather than guessing a migration. Other AIC formats keep their independent versions.
- Credit primary research and engineering sources with exact versions, evidence limits, checked dates and content-specific license status. Preserve upstream notices; cited papers, figures, prompts and implementation code are not redistributed or relicensed.
- Expand portable routing scenarios to cover every template and mixed project milestones. Actual checks and consumption limits are recorded in [verification](docs/verification.md).
- Add opt-in primary-source discovery, owner-assigned research/adoption issues and independent exact-head review for a research-record-only automatic merge lane. Instruction, template, code, CI and security changes remain manual.
- Bound unattended work to two reserved role runs per UTC day using the existing subscription login, with no tools, provider fallback or new API credentials. Preserve durable evidence and reconcile uncertain external effects without automatic replay.
- Add an explicitly activated, immutable published-source macOS scheduler with owned installation/removal and private state/logs. Installing the portable skill does not start a service. See [maintenance](docs/maintenance.md) for policy and setup.
- Replace the README's upstream-facing presentation with owner-focused documentation and an original vector banner; retain legal notices and research credit in their dedicated files.

## 1.0.0 — 2026-11-06

- Publish the self-contained `aic` Agent Skill with English, evidence-backed task routing, workflow/topology selection, scoped memory and handoff guidance.
- Add standard-library Python 3.11+ helpers for bounded metadata inspection, strict recommendation validation, approval-gated reference notes and non-mutating Orca handoff previews with exact-digest opt-in execution.
- Add ten official-source-backed harness path adapters and an explicit generic destination, with owned-manifest installation, idempotency, preservation of modified/unmanaged files, and descriptor-anchored POSIX cleanup. Windows managed mutations are unsupported and fail closed.
- Preserve pinned Anthropic authoring-reference and Agent Skills specification provenance and Apache-2.0 notices.
- Add offline verification, read-only live routing smoke evidence, contribution/security guidance and pinned-action CI. See [verification](docs/verification.md) for observed results and limits, not a universal compatibility or model-performance claim.
