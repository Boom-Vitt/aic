# Contributing to AIC

Use English for authored documentation, skill instructions, examples and helper messages. Keep the portable skill self-contained and its deterministic core standard-library-only. The optional MCP adapter uses the declared official SDK; it must not become a prerequisite for standalone skill/plugin use.

## Development versioning

Use **`0.0.1`, `0.0.2`, `0.0.3`, and onward** for AIC development versions. Increment the final component for subsequent versions; stay in `0.0.N` until the owner explicitly changes this policy. Keep `pyproject.toml`, `skills/aic/scripts/aiclib/__init__.py`, `skills/aic/SKILL.md` metadata and the native plugin manifest synchronized.

Package versions do not derive from workflow counts, features or schema numbers. Recommendation/catalog, installer, memory, handoff and maintenance formats retain their independent versions and compatibility rules. Renumbering the package must not reset schemas, accept retired contracts or imply a compatibility migration.

Earlier provisional labels in dated verification receipts and existing Git history remain historical evidence, not the current versioning policy. Do not rewrite old results, move/delete existing tags or releases, refresh global installations or activate services merely to renumber the source. Publishing a GitHub source change is separate from creating a release tag.


## Propose a focused change

Explain the user-visible behavior, boundaries, expected evidence and compatibility impact. Do not add a permanent team, paid provider, memory database or app-specific plugin without a demonstrated requirement. Use an issue or pull request; never include real credentials, private prompts or customer code.

## Add a harness adapter

1. Find current official skill discovery documentation; record its URL, checked date and a pinned revision when available.
2. Add only supported default user/project paths to `skills/aic/assets/harnesses.json`. A missing scope is `null`, not a guessed fallback. Custom profile/state locations use explicit generic destination.
3. Add behavior tests for discovery-directory placement, idempotency and refusal boundaries. These are installation contracts, not proof the actual host discovered the skill.
4. Update `docs/compatibility.md` and report any actual live checks separately. Model/provider names alone are not harness adapters.

## Add research or a workflow template

Use original wording and reliable primary sources: prefer the current peer-reviewed journal/conference version; label controlled preprints, first-party engineering cases and capability documentation separately. Record author/team, exact version/date, claim, applicability limits, checked date and the actual source-content license with an evidence URL in `skills/aic/references/research.md`. A repository's implementation license is not automatically the paper/website license. Unknown or restrictive content stays reference-only; do not vendor upstream text, figures, PDFs or code without separately reviewed rights and required notices.

Update template guidance, the machine catalog, strict recommendation contract and consumer examples together. State selection/avoid triggers, ownership/dependencies, effective authority, context/control transfer, observable acceptance and partial/blocked exits. Do not add a keyword router, a universal runtime winner, compulsory swarm, unbounded review loop or model-confidence completion rule. Keep NOTICE copies consistent and preserve upstream attribution. Schema changes need an explicit migration, not a silent compatibility guess.

## Maintain dated research records

The optional repository maintainer may propose original factual records and assigned adoption tasks; it must not adopt its own instructions, code or permissions. Follow [maintenance](docs/maintenance.md), including source-content rights, complete-method evidence, exact-head independent review, real local/CI checks and durable daily usage. Never reset reservations or replay an uncertain paid/external operation to obtain a green result.

Keep dated records data-only and self-contained under `skills/aic/references/research-updates/`. Changes to the collector, model capabilities, GitHub authority, schemas or scheduler are manual security-sensitive changes with runnable boundary checks and independent review. Do not execute an untrusted PR on a private host.


## Integration development

The public product is the [portable skill, native skills plugin and optional MCP](skills/aic/references/integrations.md), not a standalone AIC CLI. Existing `scripts/aic.py` installer, recommendation, memory and handoff helpers remain optional developer/operator interfaces; scheduled-maintainer commands remain scoped operations, not customer onboarding.

Use Python 3.11 or newer in an isolated environment. Install `.[mcp]` into that environment to exercise protocol tests; without the extra those tests explicitly skip, which is not MCP verification. The wheel keeps the existing skill tree as the `aic` package, including guides, examples, catalog, LICENSE.txt and NOTICE. Its root package anchor prevents the source launcher's sibling `aic.py` from shadowing it. `aic-mcp` is a host-invoked stdio transport entry point, not an interactive workflow runner.

For plugin changes, run the actual Claude Code native validator and install/list/remove in a task-private HOME/config; never use real user plugin settings or infer discovery/model invocation from a manifest check. For MCP changes, exercise the official client over real stdio from both source and an installed wheel, including malformed inputs, project boundaries and recovery. Read-only annotations supplement enforcement; they are not a sandbox or permission grant.

## Orca and Claude Code template

The repository template under `templates/orca-claude/`, `.claude/`, and `scripts/orca-headless.sh` is project harness guidance for Boom Big Nose Workflow v0.4.0. It does not add a workflow family, a plugin hook, or a model client. Keep the native plugin skills-only. Shell changes need a consumer-visible test and `shellcheck` in CI. Do not put secrets, `--bare`, or permission bypasses into the harness. Cite new research in `RESEARCH.md` with primary URLs and the limits in the skill research ledger; do not vendor paper text.

Do not publish a benchmark score without a receipt from `scripts/benchmark-run.sh`. Public suites stay blocked until a pinned checkout, its license, and a real run exist. The smoke suite is a recorder check, not a result.

Tune routing guidance only on the dev pack `tests/fixtures/routing-scenarios.json`. Score `benchmarks/routing/heldout-v2.json` once per release. Do not read either pack while editing `skills/aic`.

## Implement and verify

Write regressions for plausible consumer failures: traversal, unauthorized effects, modified/unmanaged preservation, evidence freshness, semantic interface overlap and uncertain launch replay. Do not pin prose, incidental implementation or mocked success as live behavior.

Run `./scripts/verify.sh` before requesting review. It is offline, uses task-owned fixtures and does not require model keys. A live agent smoke must have an explicitly safe scope and available authorization; never spend money, expose private data or change real user settings to make a test green. Review concrete acceptance findings, not model confidence or speculative feature requests.

Keep notices/license provenance intact. Security-sensitive changes need independent review and clear limitations. A skill does not override its host's governing instructions, sandbox, tools, billing or approval controls.
