# Verification evidence and limits

This document distinguishes offline contracts from actual host behavior. It does not certify universal interoperability, AI quality, prompt-injection containment or an operational deployment.

## Reproducible offline entrypoint

Run `./scripts/verify.sh` with Python 3.11+. The script prefers the checkout's isolated `.venv/bin/python` when present, otherwise `python3`; `AIC_PYTHON` can explicitly select a supported interpreter. No pip packages, provider key, network installer or model call is required.

Tests use isolated targets beneath the checkout's ignored `.work/` directory. They exercise manifest-owned install/update/uninstall, all documented adapter path contracts, modified/unmanaged preservation, symlink/traversal refusal, bounded metadata inspection, strict recommendation schemas and parallel scope boundaries, scoped note approval/integrity/staleness, read-only handoff data, canonical launch approval and dry-run immutability. Controlled subprocess fixtures check protocol and uncertainty handling; they are not live Orca/model proof.

## Workflow-template update receipt — November 6, 2026

This receipt covers the version-2 template/schema update, not an unattended-maintenance deployment or a new cross-model benchmark.

- Focused RED/GREEN checks exercised the new template contract: six template tests passed after implementation; eighteen routing tests ran, with seventeen passed and the distinct case-sensitive-directory fixture skipped on macOS.
- The actual checkout and isolated installed CLI both reported `AIC 2.0.0` and accepted the schema-2 example. Managed fixture installation, source upgrade and unchanged repetition returned `installed`, `upgraded` and `unchanged`.
- A fresh native worker consumed the isolated installed version-2 skill, references and catalog. Expected fields were withheld for eight synthetic requests spanning all seven templates. All **8/8** workflow/template/topology selections matched; all eight actual recommendations then passed the installed `check-plan --project` CLI. A real CLI probe rejected an out-of-project traversal with exit 2.
- Its mixed project plan preserved independent discovery → single-owner shared contract → isolated formatter builds → single-owner integration → independent acceptance. Every hypothetical milestone/check remained not-started/not-run; no scenario implementation or agent launch occurred.
- Independent static review found no actionable patch-introduced defect in the assigned schema, path/approval, handoff, packaging and guide surface. That review ran no executable checks and did not independently repeat the upstream license audit.
- Actual `orca-plan` preserved the nested schema-2 template and emitted a digest-bound preview. The proposed new-project directory remained absent; no operational Orca registration or agent launch occurred.

The worker's required global skill read resolved to the older 1.0.0 installation before it explicitly consumed the fixture's 2.0.0 instructions. This is installed-file consumption, **not** proof of native discovery of version 2, another Claude Code/Codex CLI run, statistical quality or a universal runtime ranking. No existing global installation/settings were changed. Primary source inspection and rights checks support the ledger's recorded facts; the cited experiments were not independently reproduced.

## Research-maintenance implementation receipt — November 6, 2026

Before initial maintainer publication, the corrected complete Mac mini entrypoint ran **253 tests: 252 passed, one filesystem-specific skip; exit 0**, using isolated Python 3.14.7. Earlier integration fixture errors were corrected without relaxing the private-directory permission gate. No full verification run failed.

- Consumer-visible regressions cover source identity/completeness and transport bounds, reference-only/public-prose limits, strict role/head/source binding, durable usage, changed packet/trace/receipt rejection, no uncertain-effect replay, exact record Git modes/bytes, stash/ref and owner-file preservation, interrupted main integration, rejected cleanup, and mixed-batch manual tasks.
- Actual throwaway Python processes exercised SIGTERM/SIGINT cleanup of the owned agent group and handler restoration. A separate real-signal fixture interrupts successful capture finalization so shutdown cannot continue into acceptance. These are local process checks, not proof of live launchd or provider behavior.
- Independent read-only security/correctness reviews found actionable defects, followed by regression fixes and re-review. The scoped follow-ups found no remaining actionable defect in the reviewed fixes. They did not execute the checks or certify deployed service compatibility.
- Actual bounded daily discovery retrieved complete evidence for [XStack: A Benchmark for ML Repo Migration, arXiv:2611.08472v1](https://arxiv.org/abs/2611.08472v1), published November 5, 2026, and first-party engineering sources. Other abstract-only/inaccessible bodies and a non-reviewed journal entry remained visible errors; the partial result exited 2 and started no model or publication.
- A live Content-Length transport failure was reproduced through a real socket/HTTP-response fixture and fixed; subsequent arXiv retrieval succeeded. Publisher redirect and byline/author handling also have isolated boundary coverage. Discovery is bounded, not a claim of exhaustive paper coverage or independent scientific reproduction.
- The actual installed CLI advertises the required isolation controls. Per-process fixtures verify protocol, credential-override exclusion and no-fallback handling; existing global settings and skill installations were not changed.

The first actual subscription-backed researcher completed through `openai-codex/gpt-6.1-sol`, but the adapter rejected duplicate receipts whose timing metadata differed. The stable-identity fix then parsed that **same original stream offline**, without another model call. Its unchanged seven findings and six limitations still exceeded the four-item policy, so the result was rejected and the consumed call/evidence retained. Both role prompts now disclose the same hard limits as their validators; no bound was widened and no output was trimmed or repaired.

A subsequent corrected researcher invocation passed the unchanged source, rights, originality and output-bound gates and produced one accepted private record. This was an explicitly labeled historical first-party engineering backfill, not a newly published or peer-reviewed paper. The owner approved a one-time ceiling of three total proof invocations, including the rejected attempt; two have run at this stage. Both ledgers/evidence are retained and the normal two-per-day policy is unchanged.

Fresh exact-head review, protected publication and installed-service lifecycle remain separate gates. Nothing was published or enabled by the rejected attempt or private researcher stage. The [maintenance guide](maintenance.md) requires initial manual publication before installing maintainer-only branch checks, then real end-to-end proof before scheduler activation.


## Initial delivery receipt — November 6, 2026

Actual full offline runs used the entrypoint above. Filesystem-specific cases are complementary: macOS skipped the distinct case-only-directory fixture; Linux skipped the case-insensitive-directory-alias fixture. The other scope, future-name and hard-link cases ran in each environment.

| Interpreter | Environment and selection | Observed result |
| --- | --- | --- |
| Python 3.14.7 | macOS arm64, isolated checkout `.venv` | 82 ran: 81 passed, 1 skipped; exit 0 |
| Python 3.11.15 | macOS arm64, explicit `AIC_PYTHON` | 82 ran: 81 passed, 1 skipped; exit 0 |
| Python 3.11.18 | Ubuntu 24.04.5, [initial PR CI run](https://github.com/Boom-Vitt/aic/actions/runs/42187083490) | 82 ran: 81 passed, 1 skipped; exit 0 |

A targeted path-safety regression run was initially RED because the helper did not yet exist; after implementation all four cases passed. The older system Python is not a supported-runtime claim.

The host-AI smoke used fresh isolated project installations, synthetic public-data files and the four requests in [routing-scenarios.json](../tests/fixtures/routing-scenarios.json). Agents received only request IDs/text, not expected labels. Each actual output was compared with the predeclared workflow/topology, then passed through the real `check-plan --project` CLI. All plans retained `next_action: recommend` and `approval_required: true`.

| Actual host | Observed model | Evidence level and limit | Expected routing cases |
| --- | --- | --- | --- |
| Claude Code 2.1.318 | `claude-opus-5-5` | Installed-file consumption. An additional verbose Read-only probe captured reads of the installed skill/references. AIC was not advertised in that restricted probe's native skill catalog, so native discovery is not claimed. | 4/4 matched and validated |
| Codex CLI 0.166.0 | `gpt-6.1-sol` | Installed-file consumption. The read-only trace captured the project-installed skill and synthetic source reads; native discovery metadata was not separately verified. | 4/4 matched and validated |
| omp 18.16.0 | `gpt-6.1-sol` via `openai-codex` | Native discovery verified: `read` resolved `skill://aic` and its references to the isolated `.omp/skills/aic` installation. Only the read tool was enabled. | 4/4 matched and validated |

These are functional smoke cases, not a statistical quality benchmark or a ranking. Safe isolation flags differ between hosts. Existing authenticated host sessions were used; AIC added no provider client, key or billing account. Raw traces and local paths are not distributed.

Actual CLI lifecycle checks installed, upgraded, repeated unchanged and uninstalled the consumed copies. A separate synthetic memory command refused promotion without approval, then an explicitly approved promotion read back as `reference-data-only` with a matching local source hash. A real `orca-plan` emitted a digest-bound preview; wrong-digest `orca-apply` refused, and the requested new-project directory remained absent. No Orca registration or operational agent launch was performed.

All ten documented adapter paths were exercised by isolated project/user CLI installation, installed helper invocation, idempotency and uninstall contracts. Pi, Hermes, OpenClaw, Cursor, Gemini CLI, OpenCode and Copilot CLI were not live-discovery/model-tested. Generic destination support is not an invented native integration. Official documentation supports the path contracts, not a universal permissions or interoperability guarantee.

### Reproduce a safe host smoke

1. Create a disposable project containing only synthetic evidence and install AIC with an explicit `--project`.
2. Give the host the scenario IDs and requests, withholding the `expected_*` fields. Ask for recommendations only, not execution of those requests.
3. Have it read its installed `SKILL.md`, relevant references and the synthetic source, then return one complete recommendation per case.
4. Save each actual plan in that disposable project and run `python3 scripts/aic.py check-plan PLAN.json --project PROJECT` from this checkout.
5. Compare workflow/template/topology against the fixture's expected fields, require all case IDs exactly once and preserve the recommendation/approval boundary. Evaluate the separate project case against its preserved acceptance, dependency and ownership invariants; do not mistake its milestone table for executable scheduling. Record failures as well as successes.
6. Record the host/version, actual model and trace-based discovery level. Do not turn file consumption into native-discovery proof or a small smoke into a benchmark. Uninstall only the intact owned test copy.

## Verification boundaries

- An isolated file installation is not proof an actual host discovered the skill.
- Explicit installed-file consumption is not automatic native discovery.
- A small routing smoke is not a statistical model/harness benchmark.
- Dry-run or subprocess contract tests are not a real Orca project/agent launch.
- Host subscription/provider usage is governed by the user's existing service; AIC installs no inference client or billing account.
- Inspection uses common exclusions, not arbitrary repository ignore rules or complete secret detection. Use trusted, access-controlled directories; path checks alone do not contain a concurrent hostile local writer.
- No personal skill collection, credentials, private transcripts or third-party product source is part of this distribution.
