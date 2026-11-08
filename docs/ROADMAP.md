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

The shared dollar stop and the suite arm wiring are in the working tree that contains this file. They are not a score.

- `benchmarks/baselines/registry.json` sets `max_usd` to `0.35` for every arm. `max_turns` stays 30 and `timeout_sec` stays 600. The stop prices 30 × 600 input tokens and 30 × 1024 output tokens at the pinned Claude Sonnet 5.5 rates (2 USD and 10 USD per million). The exact product is 0.3432 USD. The sent cap rounds that up to the next cent. It is a stop rule, not a predicted cost. Official comparisons refuse a null cap.
- The pinned Terminal-Bench adapter (`d28711d0da2675d0bb1d56de45ae5df6082438a3`) and the official SWE-bench Lite path (`02e7a74ffd0b707aab73d203fe87bdc7c76afc8e`) load `plain-claude-code`, `aic`, `ecc`, `agent-skills`, `planning-with-files`, and `gstack` under that model, budget, and seed. `superpowers` stays `unverified-install` and out of the comparison. Both official paths use the two-phase egress proxy. The install phase has no API key. The agent phase is the only phase that receives the key, and its allow-list is `api.anthropic.com:443`. The Terminal-Bench task container does not receive the key or a copy of an installed third-party arm. It is disconnected from every network, including Docker-internal networks, before any forwarded command. The official run accepts only an empty Networks map or the `none` network and refuses any other attachment. Official runs also refuse to start when bubblewrap or the proxy is missing.
- `python3 -m benchmarks.suite_arms stub` is the key-free proof. It does not call a model and does not fetch third-party trees. No score-history row was added.

The key-free product cycle after that harness adds a short changed-surface loop to the shipped skill and a `check-surface` helper that rejects a `passed` record unless the recorded exit codes match the change kind. It does not run the command. Findings are in `docs/research/procedure-gates-2026-11-08.md` and the 2026-11-08 section of `docs/research/competitors-claude-skills.md`. Offline skill-lint, the routing scorer, aicbench oracles, the baseline stub, and the suite stub were rerun. Those results are not score-history rows. `benchmarks/routing/heldout-v2.json` was not opened: this change is not a release, so the once-per-release score was not taken.

`docs/BENCHMARKS.md` still lists SWE-bench Lite, SWE-bench Verified, Terminal-Bench, and Aider polyglot as not run. Routing label matches inside a results bundle are not copied into the table below.

## Blocked

- No `ANTHROPIC_API_KEY` repository secret, and no signed-in Claude Code in CI or in this cloud environment. A missing key exits 3. Nothing in that path is a score.
- SWE-bench Lite and Verified, Terminal-Bench, and Aider polyglot have not been run. Aider's exercises are not licensed for copying into this tree. See `docs/BENCHMARKS.md`.
- Terminal-Bench and SWE-bench Lite have not been scored. `./scripts/run-benchmarks.sh --terminal-bench` runs the official arms under one model, one budget, and one seed. The agent phase runs behind the egress proxy. `--swe-bench-lite` runs the same six arms through that proxy, then scores a predictions file. `aic_treatment` is true only when a process actually read the AIC plugin for the `aic` arm. It stays false for `plain-claude-code` and for the other plugins. `harness_loaded_aic` stays false until that run writes `arm-load.json`. The SWE-bench evaluation step scores a predictions file and does not load a plugin (`evaluation_aic_treatment` false). `public_benchmark_scores` stays null. The key-free stub is not a model run. A missing proxy, sandbox, or a task container that still has a route out refuses the official run before a model call.
- Registered comparable repositories are pinned and wired. They have not been fetched or scored in a model run. The suite stub uses local stand-ins for the git arms and does not fetch them.
- Official aicbench numbers still require `--sandbox container`. Official baseline results also refuse sandbox `none` and refuse to run without the egress proxy. The baseline stub proof uses sandbox `none` on purpose, so the stub can read the reference solution. That report stays unofficial. `superpowers` is an unverified install and is excluded from official comparisons.

## Next

1. Add `ANTHROPIC_API_KEY` as a repository secret. Run `./scripts/run-benchmarks.sh --baselines` (or dispatch `.github/workflows/benchmarks.yml` with `baselines` true). Append one score-history row per arm from that bundle only. Link the raw `results/` tree. Leave the row out if the model did not run.
2. Leave Aider polyglot unwired until each Exercism track's terms are reviewed. Do not copy the exercises.
3. Keep `benchmarks/routing/heldout-v2.json` sealed. Score it once per release. The procedure-gate change did not score it. Do not tune on it.
4. Do not promote AIC on a benchmark claim before a real run is in the score history.

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
