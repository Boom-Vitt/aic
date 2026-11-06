# Verification evidence and limits

This document distinguishes offline contracts from actual host behavior. It does not certify universal interoperability, AI quality, prompt-injection containment or an operational deployment.

## Reproducible offline entrypoint

Run `./scripts/verify.sh` with Python 3.11+. The script prefers the checkout's isolated `.venv/bin/python` when present, otherwise `python3`; `AIC_PYTHON` can explicitly select a supported interpreter. No pip packages, provider key, network installer or model call is required.

Tests use isolated targets beneath the checkout's ignored `.work/` directory. They exercise manifest-owned install/update/uninstall, all documented adapter path contracts, modified/unmanaged preservation, symlink/traversal refusal, bounded metadata inspection, strict recommendation schemas and parallel scope boundaries, scoped note approval/integrity/staleness, read-only handoff data, canonical launch approval and dry-run immutability. Controlled subprocess fixtures check protocol and uncertainty handling; they are not live Orca/model proof.

## Initial delivery receipt — November 6, 2026

Actual full offline runs used the entrypoint above. The one skipped case requires two distinct existing directory names differing only by case, which this filesystem cannot create; the other alias, future-name and hard-link scope cases ran.

| Interpreter | Environment and selection | Observed result |
| --- | --- | --- |
| Python 3.14.7 | macOS arm64, isolated checkout `.venv` | 82 ran: 81 passed, 1 skipped; exit 0 |
| Python 3.11.15 | macOS arm64, explicit `AIC_PYTHON` | 82 ran: 81 passed, 1 skipped; exit 0 |

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
5. Compare workflow/topology against the fixture's expected fields, require all case IDs exactly once and preserve the recommendation/approval boundary. Record failures as well as successes.
6. Record the host/version, actual model and trace-based discovery level. Do not turn file consumption into native-discovery proof or a small smoke into a benchmark. Uninstall only the intact owned test copy.

## Verification boundaries

- An isolated file installation is not proof an actual host discovered the skill.
- Explicit installed-file consumption is not automatic native discovery.
- A small routing smoke is not a statistical model/harness benchmark.
- Dry-run or subprocess contract tests are not a real Orca project/agent launch.
- Host subscription/provider usage is governed by the user's existing service; AIC installs no inference client or billing account.
- Inspection uses common exclusions, not arbitrary repository ignore rules or complete secret detection. Use trusted, access-controlled directories; path checks alone do not contain a concurrent hostile local writer.
- No personal skill collection, credentials, private transcripts or third-party product source is part of this distribution.
