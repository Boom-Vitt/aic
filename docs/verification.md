# Verification evidence and limits

This document distinguishes offline contracts from actual host behavior. It does not certify universal interoperability, AI quality, prompt-injection containment or an operational deployment.

## Reproducible offline entrypoint

Run `./scripts/verify.sh` with Python 3.11+. The script prefers the checkout's isolated `.venv/bin/python` when present, otherwise `python3`; `AIC_PYTHON` can explicitly select a supported interpreter. Core-only checks need no third-party packages. Install the declared optional `.[mcp]` dependencies into that isolated environment before claiming MCP verification; without them the protocol tests explicitly skip. Verification itself performs no network installation or model call and requires no provider key. See [integration development](../CONTRIBUTING.md#integration-development).

Tests use isolated targets beneath the checkout's ignored `.work/` directory. They exercise manifest-owned install/update/uninstall, all documented adapter path contracts, modified/unmanaged preservation, symlink/traversal refusal, bounded metadata inspection, strict recommendation schemas and parallel scope boundaries, scoped note approval/integrity/staleness, read-only handoff data, canonical launch approval and dry-run immutability. Controlled subprocess fixtures check protocol and uncertainty handling; they are not live Orca/model proof.

## Security remediation receipt (0.0.3) — November 8, 2026

These are bounded Mac mini observations of the current working-tree source, not a public deployment, native model-invocation trace or guarantee that every exploit is absent. Package/plugin/marketplace metadata uses **0.0.3**; recommendation/catalog schema remains **3**. The live scheduler and globally installed skills were not upgraded.

| Complete offline entrypoint with official MCP SDK 2.3.0 | Tests | Passed | Skipped | Runtime | Exit |
| --- | ---: | ---: | ---: | ---: | ---: |
| Python 3.11.15 | 324 | 323 | 1 | 18.103 s | 0 |
| Python 3.14.7 | 324 | 323 | 1 | 17.182 s | 0 |

The single skip is the existing distinct-case-sensitive-filesystem fixture on this Mac. All sixteen MCP protocol cases ran in both final environments. The initial core-only environment skipped those sixteen optional cases and was not accepted as MCP evidence; SDK-enabled verification used task-private environments without changing the existing/global Python environment.

Forty-six new security cases were added before production edits, plus two arXiv deadline-wait cases. Focused RED demonstrated foreign marker queue blocks, accepted excessive recommendation inputs, six oversized/count/aggregate note failures, and three stalled DNS/status/header deadline failures. After the fixes all forty-six passed. Owner ambiguity, missing owner assignment, uncertain-effect non-replay, physical hard-link/case isolation, immutable/idempotent note boundaries and reference-only authority controls still passed.

There was **one failed full verification run**: the initial Python 3.11 pass exposed a fixture that assumed a 1,024-byte relative path plus its project root fit Darwin's `PATH_MAX`. Python 3.11 correctly surfaced `ENAMETOOLONG`; newer pathlib suppresses more metadata errors. The fixture now asserts the lexical byte ceiling without claiming unsupported project-filesystem behavior. No production filesystem guard was weakened. Focused routing passed on both interpreters, then both final full entrypoints passed. An earlier YAML plain-scalar parsing error was also corrected before executing the security job; that was not a failed full suite.

Real official-SDK clients exercised the source launcher, an actually built/installed wheel and the exact documented host-started `uvx` argument array from outside the checkout. All reported **AIC 0.0.3**, negotiated **2025-11-25**, rejected all four excessive-input probes, preserved a valid plan before/after errors, recovered and left the synthetic project unchanged. All twelve packaged resource hashes matched across all three forms. These are SDK transport observations, not a claim that a host model invoked the skill.

Actual optional helpers from source and the installed wheel accepted exact **65,536-byte** and **4,096-node** recommendation boundaries and refused one-over inputs with controlled exit 2. Real memory promotion/read helpers retained reference-only output, refused a valid canonical/hash-matching note one byte over 1 MiB without deleting it, preserved a pre-existing promotion lock, and succeeded after the fixture owner explicitly released that lock. Local socketpair/resolver fixtures cut short the previously six-second stalls and verified transport work was cancelled/reaped; no real publisher endpoint or model/provider was attacked.

Claude Code **2.1.319** accepted explicit strict validation of both plugin and marketplace manifests, installed the reviewed local source into a task-private local scope, listed **`aic@aic-marketplace` 0.0.3**, then uninstalled it and removed its private marketplace. Directory validation selected the marketplace, so `plugin.json` was also validated explicitly. The optional directory-profile missing-icon advisory remains nonblocking; no official directory submission is claimed. A private Git project, HOME/config and disabled child auto-updater kept this separate from existing user settings. No native skill/model invocation was performed.

The actual dependency security workflow shell block passed with no known advisories. The actual secret-scan block passed against reachable history with a checksum-verified native Gitleaks 8.30.1; the equivalent Linux CI archive was independently downloaded and SHA-256 checked against official release metadata, but not executed on Darwin. Current tracked/nonignored public source was also scanned separately, including uncommitted changes. Both scans used bundled default rules, redaction and no repository suppression. Bandit parsed all production/helper files and retained fourteen reviewed diagnostics: eleven argv/subprocess advisories, two preguarded XML warnings and Git-format SHA1 verification. No warning suppression or fake clean-static-analysis claim was introduced.

The required CI shell gate was executed with successful, failed, cancelled, skipped and missing reusable-workflow results: only `success` returned zero. Hosted Ubuntu workflow orchestration and the new daily schedule await source publication; local shell execution is not a fabricated GitHub Actions run. Public pull-request code is not run on this private Mac as a self-hosted runner.

GitHub vulnerability alerts, automatic security updates and private vulnerability reporting were actually enabled and read back with the existing authentication. Visible open Dependabot alerts were empty at the subsequent query; newly enabled graph coverage is asynchronous. A separate read-back confirmed administrator enforcement, the three existing required contexts and every captured branch-protection field were unchanged. The new source ties reusable security results into `offline-contracts` rather than weakening repository protection.

Two independent read-only security reviews found no actionable defect within their assigned current-source scopes. They did not independently execute the checks or certify OS sandboxing, hostile concurrent-writer containment, authenticated human approval or absence of unknown flaws. Tool/license provenance is retained in both NOTICE copies. Private verification receipts remain outside the public package; the actual wheel inventory excludes `.work`, environments, caches, credentials and bytecode despite the build tool's conservative cache-location warning.

No source commit/push, release tag, PyPI publication, global installation refresh, live journal clearing, provider invocation or running-service change was part of this remediation. Source publication, installed-skill refresh and an immutable scheduler upgrade remain separate authorized operations.

## Skills-first plugin and MCP receipt (0.0.2) — November 7, 2026

These are functional observations from the standalone AIC checkout on the Mac mini, not a model benchmark, universal host certification or hosted-service deployment. The skill/plugin now use the host conversation as their user entry point; internal helpers are not a user prerequisite. Recommendation/catalog schema remains **3**.

- The complete entrypoint with isolated **Python 3.14.7**, official **MCP SDK 2.3.0** installed, ran **276 tests: 275 passed, one case-sensitive-filesystem fixture skipped; exit 0**, in 11.199 seconds. All **16** new MCP consumer cases ran, including strict noncoercing arguments, opaque JSON, fixed/independent roots, metadata privacy, evidence and parallel-scope checks, denied arbitrary resources, error recovery and real source stdio outside the checkout.
- The first full run failed with 16 new-fixture import errors: older tests prepend the legacy helper directory to `sys.path`, while the new fixture delayed its source import until setup. Moving that import beside its explicit source-path selection fixed the isolation issue without changing a production guard. The corrected cases passed with the entire suite discovered first, then the complete entrypoint passed. That is **one failed full run**, not a hidden zero-failure claim.
- Earlier real source startup exposed a separate package-shadowing bug that in-process tests missed: an implicit namespace could resolve the sibling legacy `aic.py` launcher and start its argument parser. The permanent stdio consumer regression failed before the ordinary package anchor was added and passed afterward. SDK client lifetime is kept in the same async test task; no validation/privacy/approval boundary was relaxed.
- Actual Claude Code native strict validation accepted both plugin and marketplace manifests with no manifest errors/warnings. Native local-scope install/list reported **`aic@aic-marketplace` version `0.0.2`, enabled**, in a task-private HOME/config/project; the client version command reported **2.1.319**. The plugin declares no hooks, settings or automatically started MCP. The native directory checker also reported a nonblocking missing-icon advisory; official directory submission is not claimed. Its plugin validator does not accept a bare skill directory without a plugin manifest, so that attempt is not skill-validation or discovery evidence.

The official SDK client launched three actual stdio subprocess forms from outside the source tree. Each negotiated **2026-07-28**, reported server **AIC 0.0.2**, exercised all four tools, fetched all twelve concrete resources, denied unsafe operations and recovered:

| Actual consumer form | Read-only tools | Packaged resources | Unsafe tool calls refused | Arbitrary resource reads denied | Synthetic project unchanged |
| --- | --- | --- | --- | --- | --- |
| Source Python launcher | 4 | 12 | 9 | 2 | Yes |
| Installed wheel console entry point | 4 | 12 | 9 | 2 | Yes |
| Exact documented host-started `uvx` argument array | 4 | 12 | 9 | 2 | Yes |

All twelve resource hashes matched across the three forms. Calls covered catalog/guidance, metadata-only inspection, a valid schema-3 recommendation, boolean-limit refusal, root-switch refusal, serialized-plan refusal, traversal, old schema, false approval, execution/agent-launch refusal and successful use afterward. These are real SDK transport observations, **not** a Claude Code/other host's native MCP discovery or model invocation trace.

The actual wheel was built with pinned **Hatchling 1.29.0** and installed into separate task-owned full-SDK and core-only environments. The wheel contains the original skill tree, catalog/examples, guides, LICENSE.txt/NOTICE and distribution license files. With **no MCP SDK installed**, core validation, packaged resources and a lazy adapter import worked; attempting MCP startup failed cleanly with exit 2 and a missing-extra message, not a traceback. No PyPI publication is implied.

The SDK and protocol-types distribution license files were checked as **MIT, Copyright (c) 2024 Anthropic, PBC**; the build backend's installed MIT grant credits **Ofek Lev**. [Pinned provenance](../skills/aic/references/provenance.md) and both NOTICE copies retain dependency and existing research credits. Optional dependencies keep their own notices and are not vendored or relicensed by AIC.

No inference/model scenario, real Orca launch, public MCP listener, global skill/MCP/plugin configuration, scheduler upgrade or release tag was part of these checks. Existing historical host-consumption receipts below remain historical; installing/listing a plugin does not establish native skill invocation or AI quality. Final exact-head publication and independent-review receipts belong to the associated GitHub pull request.

## Development-version correction — November 7, 2026

The owner selected **`0.0.1`, `0.0.2`, `0.0.3`, and onward** for current/future development versions. Larger package labels in earlier receipts below are historical observations, not the current versioning policy; their actual past output is not rewritten. This correction does not reset any format/schema version or change the five-family workflow behavior.

- Actual current source and isolated installed CLIs reported **`AIC 0.0.1`**; the installed skill metadata also reported `0.0.1`.
- An intact owned installation of the actual previous source at commit `3f8f74646aa11938927f1b814e9294a8fc188d96` was updated through the real managed installer. It returned `upgraded`, then the installed CLI reported `0.0.1`; repeated installation returned `unchanged`. Managed uninstall completed and the synthetic fixture was removed. A numerically lower development label did not block the content-owned update.
- Actual installed `check-plan --project` preserved a valid schema-3 recommendation unchanged and refused schema-1/2 recommendations with exit 2. No legacy recommendation was silently accepted because the package was renumbered.
- No global skill/settings, Git tags/releases or running service were changed by the smoke. It launched no model or scenario. This is explicit installed-file consumption, not native discovery or a live runtime/service upgrade.

Publication checks belong to the actual candidate head and are recorded in its associated GitHub pull request. The dated receipts below retain their original evidence and limitations.


## Five-family local update receipt — November 7, 2026

This receipt records the local verification stage of **unreleased AIC 3.0.0 / recommendation schema 3** in the standalone AIC checkout on the Mac mini, captured before the owner's subsequent GitHub publication request. Older receipts below preserve their actual version-specific observations. Repository settings, global installed skills and the immutable maintainer service were not changed by this verification stage. Track later source publication through its GitHub pull request separately; a source merge does not imply a release tag, global installation or service upgrade.

- The new seven-test template contract was RED against the prior validator: schema 3 was rejected and schema 2 was still accepted. After implementation all seven passed. Focused routing ran 19 cases (18 passed, one case-sensitive-filesystem skip); all ten Orca contract cases passed.
- The required complete entrypoint, with the isolated Python 3.14.7 explicitly selected, ran **260 tests: 259 passed, one filesystem-specific skip; exit 0**, in 11.583 seconds. No full verification run failed.
- Actual checkout and explicitly installed generic-fixture CLIs reported `AIC 3.0.0`. Installation returned `installed`, repetition `unchanged`, bounded metadata inspection worked, the portable copy included the original tmux profile, and final managed removal returned `uninstalled`. The installed copy and generated synthetic project were removed; private input/output and execution receipts remain outside the distributed package.
- A fresh native worker explicitly consumed the installed version-3 skill and 27 anonymous synthetic requests with expected selectors withheld. The parent ran **all 27 actual recommendations** through the installed `check-plan --project`; all were accepted unchanged, with recommendation-only actions and approval still required. Family/topology matched all 27 reference annotations; the complete category/family/topology triple matched **26/27**. The preserved disagreement labels a bounded code-change explanation `answer` rather than the fixture's `implementation`; both select `direct`/`solo`, and the consumer explicitly forbids implementation/experiments. Neither output nor reference annotation was rewritten to manufacture a match.
- The returned mixed project used the six expected stage arrangements: independent discovery, direct shared contract, sequential dependent delivery, parallel ready formatters, independent acceptance and solo durable continuation. Original acceptance, producer readiness, ownership and permission gates remained explicit. Every hypothetical milestone/check remained **not-started/not-run**; no scenario implementation or benchmark was executed.
- Ten real installed-CLI probes refused old schema 1/2, the four retired IDs, an incompatible topology, out-of-project writes, an execution action and a false approval requirement, all with exit 2. An actual `orca-plan` preserved outer handoff schema 1 and nested recommendation schema 3; wrong-digest apply refused, and the proposed project remained absent. No operational Orca registration/agent launch was performed.
- Official stable-release metadata and the installed version both identified **tmux 3.8**. Real private-socket tmux servers loaded the trusted per-run copied profile. PTY interaction observed role/title borders, RUNNING-to-retained-DEAD transitions for exit 0 and 7, window-tree output, zoom state 1 then 0, bounded retained scrollback, detach and same-session reattach without losing panes. DEAD/exit information never became task PASS. All owned smoke sessions/servers were removed; no model was launched by this exercise and no existing/default server or global config was targeted.
- Two smoke-harness assertions were corrected without changing the profile: a local-only option query omitted inherited global defaults, and a visible-viewport capture omitted scrollback after resizing. Subsequent actual global-option and bounded `capture-pane -S -1000` observations established the intended state/output. These were smoke-driver corrections, not failed full-suite runs or suppressed product errors.
- Independent read-only review reported no actionable defect within the assigned code, contract, guide and supervision surface. It cross-checked relevant primary tmux and pinned OMP documentation, but did not execute checks or independently reproduce the cited research experiments. OMP Agent Hub controls here are documented capability, not a new live UI-interaction receipt.

This is explicit installed-file consumption, **not native discovery of version 3**, another Claude Code/Codex CLI evaluation, a statistical quality benchmark, proof that any family is universally optimal, or a real multi-model team running under tmux. Counts and source-informed procedures do not establish task-independent effectiveness. AIC is a normal public GitHub repository, not a GitHub template repository. The changes were local and unpublished when these observations were recorded; subsequent publication does not retroactively expand their evidence or authorization.


## Live maintenance and lifecycle proof — November 7, 2026

These are dated Mac mini observations, not a continuous-health or scientific-quality guarantee.

- The corrected 2.0.2 candidate ran the complete entrypoint with isolated Python 3.14.7: **256 tests, 255 passed, one case-sensitive-filesystem fixture skipped, exit 0**. All 26 service and 33 agent boundary cases passed separately. An earlier worktree invocation stopped at the unsupported system-Python preflight; explicitly selecting the project venv passed.
- [PR #2](https://github.com/Boom-Vitt/aic/pull/2) manually published the maintainer. [PR #3](https://github.com/Boom-Vitt/aic/pull/3) fixed the actual personal-repository protection rejection. Real read-back confirmed strict `offline-contracts`, `aic/macmini` and `aic/independent-review` requirements, administrator enforcement, PR integration, and disabled force-push/deletion.
- The real subscription-backed researcher and fresh isolated exact-head reviewer completed the record-only lane: [issue #4](https://github.com/Boom-Vitt/aic/issues/4) was assigned to `Boom-Vitt`, and [PR #5](https://github.com/Boom-Vitt/aic/pull/5) merged after actual local verification and genuine GitHub Actions CI. Its one new UTC-dated record is an explicitly labeled historical engineering backfill. The manual adoption issue remains open; publication did not change a workflow or authorize execution.
- That end-to-end proof used exactly three owner-approved invocations: the original rejected researcher, corrected researcher and fresh reviewer. The rejected result and both ledgers were preserved. The ordinary unattended policy remains two role runs per UTC day, one per role; the proof exception is not a recurring allowance.
- The new owned `ai.aic.research-maintainer` LaunchAgent was activated from published immutable commit `1e91caa6772b3c54908ad57f2afc456300045129`. Its actual first cycle reported the persisted daily discovery attempt and visible source exclusions, with no extra model invocation and empty stderr. This is a real cycle, not just a generated plist.
- Actual launchd output contains nested resource-coalition `state` fields. The original guard safely refused removal rather than guessing. After scoping lifecycle fields to the service level, the corrected helper removed only the owned label, retained durable state/logs, reactivated that verified published snapshot, and observed `loaded: true`. No serving release was edited; the regression also rejects a missing controller PID despite a nested PID and never substitutes a coalition PID for the controller.
- The first separately scheduled November 7 research startup reserved its ordinary daily slot but stalled in `preloadPluginRoots` and produced zero JSON model events. It was not retried. After confirming no accepted output or external effects, the operator paused only AIC's new label and rejected that job without deleting its packet, stderr or reservation; the sources remain unassessed, not scientifically rejected. This scheduled reservation is separate from the earlier three-invocation supervised proof.
- A real no-inference RPC startup smoke then completed in two seconds with a private home/project anchor and the existing CLI agent directory bound explicitly: `ready`, successful `get_state`, the expected Codex model/provider, zero messages, zero exposed tools, no streaming or `agent_start`, empty stderr, and zero role reservations. The ambient-startup-hook regression failed before the change and passed afterward. This proves startup/state observation, not another completed research assessment.
- A metadata-only live sweep found three complete candidates, including the November 5 XStack preprint, and retained four incomplete/non-reviewed-source exclusions as a partial result. It started zero model processes or GitHub mutations. Complete retrieval is not peer review, license permission or a positive adoption decision.
- An isolated explicit generic installation reported `AIC 2.0.2`, accepted the schema-2 `direct`/`solo` plan with approval still required, returned `unchanged` on repeated installation, and uninstalled cleanly. This used the documented script invocation; it does not claim native host discovery or update any existing global skill.
- The actual published GitHub README and original banner rendered on desktop and at a 390-pixel viewport. The narrow page had equal client/scroll widths, the banner loaded within its container, and the README retained only the owner's byline, without `agentskills.io` or an upstream byline. The verification browser workspace was closed.

Host power inspection reported AC `sleep 0`; no power settings were changed. Work still requires this Mac to stay powered, awake, online and logged into its user session. Source checks, installed-skill refreshes and immutable scheduler upgrades remain separate operations described in the [maintenance guide](maintenance.md). Cited experiments were not independently reproduced and no universally best runtime/model is asserted.


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

Skill text must never be derived from these held-out cases. Do not read `tests/fixtures/routing-scenarios.json` when editing `skills/aic`.

## Orca template checks — 2026-11-07

On this Linux checkout, `./scripts/verify.sh` with Python 3.12.3 ran **352** tests in **13.380s**, **17 skipped**, exit 0. The skips are the existing optional MCP cases because `.[mcp]` was not installed here. The new template tests passed: invalid and cyclic plans, unowned path overlap, permission denials, a missing gate, a stale review, a command confined to the named worktree, budget and timeout failure records, bootstrap refusal, and a headless apply whose argv did not push, delete, or pass `--bare`. `shellcheck` 0.9.0 passed on the new shell scripts. No Claude Code process, plugin install, model call, or Mac mini doctor was run. Hosted CI installs the MCP extra and shellcheck; that run is separate from this local receipt. A follow-up headless hardening check on the same interpreter ran **353** tests in **13.389s**, **17 skipped**, exit 0.

`./scripts/benchmark-run.sh run --suite smoke` on the same checkout recorded 2 runs, both exit 0, `invokes_model` false, and `public_benchmark_scores` null. That is the local recorder check. SWE-bench, Terminal-Bench, Aider polyglot, and real-task suites were not executed.

## Verification boundaries

- An isolated file installation is not proof an actual host discovered the skill.
- Explicit installed-file consumption is not automatic native discovery.
- A small routing smoke is not a statistical model/harness benchmark.
- Dry-run or subprocess contract tests are not a real Orca project/agent launch.
- Host subscription/provider usage is governed by the user's existing service; AIC installs no inference client or billing account.
- Inspection uses common exclusions, not arbitrary repository ignore rules or complete secret detection. Use trusted, access-controlled directories; path checks alone do not contain a concurrent hostile local writer.
- No personal skill collection, credentials, private transcripts or third-party product source is part of this distribution.
