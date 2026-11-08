# Roadmap

No public benchmark score exists. This file is the backlog and the score history. A row appears in the history only after a real run, with the raw results linked. The stub proof in `docs/BENCHMARKS.md` is not a row. Promotion waits on that history, not on a plan.

Issue [#4](https://github.com/Boom-Vitt/aic/issues/4) is a manual adoption note. It authorizes no implementation and is not a backlog item here.

## Done

Landed on `main` through [#31](https://github.com/Boom-Vitt/aic/pull/31) (`7909370`). The benchmark-relevant pieces:

| Change | PR |
| --- | --- |
| Competitor notes for Claude Code skill and workflow repositories | [#13](https://github.com/Boom-Vitt/aic/pull/13) |
| Third-party license audit and NOTICE corrections | [#14](https://github.com/Boom-Vitt/aic/pull/14) |
| Pinned Terminal-Bench adapter | [#16](https://github.com/Boom-Vitt/aic/pull/16) |
| SWE-bench Lite runner for plain Claude Code and AIC | [#17](https://github.com/Boom-Vitt/aic/pull/17) |
| aicbench, a graded suite of original tasks, plus its oracle | [#20](https://github.com/Boom-Vitt/aic/pull/20) |
| Offline skill-lint benchmark | [#22](https://github.com/Boom-Vitt/aic/pull/22) |
| Container pipeline smoke for the aicbench stub | [#25](https://github.com/Boom-Vitt/aic/pull/25) |
| Offline routing scorer | [#26](https://github.com/Boom-Vitt/aic/pull/26) |
| MCP input schema bounds | [#27](https://github.com/Boom-Vitt/aic/pull/27) |
| Sealed heldout-v2 routing pack | [#28](https://github.com/Boom-Vitt/aic/pull/28) |
| Install UX and install-smoke CI | [#29](https://github.com/Boom-Vitt/aic/pull/29) |
| `scripts/run-benchmarks.sh` and manual `benchmarks.yml` | [#30](https://github.com/Boom-Vitt/aic/pull/30) |
| Vulnerability stewardship | [#31](https://github.com/Boom-Vitt/aic/pull/31) |

`docs/BENCHMARKS.md` still lists SWE-bench Lite, SWE-bench Verified, Terminal-Bench, and Aider polyglot as not run. Routing label matches inside a results bundle are not copied into the table below.

## Blocked

- No `ANTHROPIC_API_KEY` repository secret, and no signed-in Claude Code in CI or in this cloud environment. A missing key exits 3. Nothing in that path is a score.
- SWE-bench Lite and Verified, Terminal-Bench, and Aider polyglot have not been run. Aider's exercises are not licensed for copying into this tree. See `docs/BENCHMARKS.md`.
- The Terminal-Bench and SWE-bench flags on `./scripts/run-benchmarks.sh` still record `aic_treatment` false. They do not load AIC or the other registered plugins inside those harnesses.
- Registered comparable repositories are pinned and wired. They have not been fetched or scored in a model run.
- Official aicbench numbers still require `--sandbox container`. The baseline stub proof uses sandbox `none` on purpose, so the stub can read the reference solution. That report stays unofficial.

## Next

1. Add `ANTHROPIC_API_KEY` as a repository secret. Run `./scripts/run-benchmarks.sh --baselines` (or dispatch `.github/workflows/benchmarks.yml` with `baselines` true). Append one score-history row per arm from that bundle only. Link the raw `results/` tree. Leave the row out if the model did not run.
2. Set one shared `max_usd` in `benchmarks/baselines/registry.json` before any wider task list. The current budget sends no dollar cap. `max_turns` is 30 and `timeout_sec` is 600 for every arm.
3. Load the same arms inside the pinned Terminal-Bench and SWE-bench Lite adapters, under the same model, budget, and seed. Until that lands, those receipts stay `aic_treatment: false`.
4. Leave Aider polyglot unwired until each Exercism track's terms are reviewed. Do not copy the exercises.
5. Keep `benchmarks/routing/heldout-v2.json` sealed. Score it once per release. Do not tune on it.
6. Do not promote AIC on a benchmark claim before a real run is in the score history.

## Baselines

Machine-readable pin: `benchmarks/baselines/registry.json`. Checked 2026-11-08 from each root license file. Details and the maintainer command are in `docs/BENCHMARKS.md`.

| Arm | Commit | License |
| --- | --- | --- |
| `plain-claude-code` | None | No extra workflow |
| `aic` | Working tree | Apache-2.0 |
| `superpowers` (`obra/superpowers`) | `22f0b463e7a5e579904dd6211a520321035526f7` | MIT, Copyright (c) 2025 Jesse Vincent |
| `ecc` (`affaan-m/ECC`) | `d2ef2680594f9a17526a6e1a2e18b3d242c5d17b` | MIT, Copyright (c) 2026 Affaan Mustafa |
| `agent-skills` (`addyosmani/agent-skills`) | `301b02b12bff98e4688e6984af6556802322bbde` | MIT, Copyright (c) 2025 Addy Osmani |
| `planning-with-files` (`OthmanAdi/planning-with-files`) | `2362ca385ad74f061aa0e7b73f56543a4b7e6df2` | MIT, Copyright (c) 2026 Ahmad Adi |
| `gstack` (`garrytan/gstack`) | `23f9d07ce9e802ac148a8a353228f201655fc5b8` | MIT, Copyright (c) 2026 Garry Tan |

Not registered: repositories with no root license, CC BY-NC-ND 4.0, plugin marketplaces that are not one workflow, and the claude-mem service. The list is in `docs/BENCHMARKS.md`.

## Score history

Rows: none. A later real run appends one row per arm. Rows that share a date, suite, sample size, model, budget, and seed are one comparison. Pass rate, cost, and time come from that run's raw results. Do not estimate them.

| Date | Suite | Sample size | Model | Budget | Seed | Arm | Pass rate | Cost | Time | Raw results |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
