# Contributing to AIC

Use English for authored documentation, skill instructions, examples and CLI messages. Keep the package self-contained, standard-library-only and compatible with the declared Python versions.

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


## Implement and verify

Write regressions for plausible consumer failures: traversal, unauthorized effects, modified/unmanaged preservation, evidence freshness, semantic interface overlap and uncertain launch replay. Do not pin prose, incidental implementation or mocked success as live behavior.

Run `./scripts/verify.sh` before requesting review. It is offline, uses task-owned fixtures and does not require model keys. A live agent smoke must have an explicitly safe scope and available authorization; never spend money, expose private data or change real user settings to make a test green. Review concrete acceptance findings, not model confidence or speculative feature requests.

Keep notices/license provenance intact. Security-sensitive changes need independent review and clear limitations. A skill does not override its host's governing instructions, sandbox, tools, billing or approval controls.
