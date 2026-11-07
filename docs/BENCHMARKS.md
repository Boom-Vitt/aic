# Benchmarks

No public benchmark score is claimed. The numbers below are not results.

This harness compares arms only when they share one model id, one budget (`max_turns`, `timeout_sec`, `max_usd`), one seed, and one pinned benchmark revision. The treatment is the workflow: plain Claude Code does not load AIC; the AIC arm loads the AIC skill. Everything else stays the same. A different seed, model, or revision is a different run, not a comparison.

## Suites

| Suite | What it is | License observed 2026-11-07 | Status |
| --- | --- | --- | --- |
| `smoke` | One local Python process that exits 0, recorded for two arm names | Original AIC fixture | Runnable. Not a benchmark score. |
| `swe-bench-lite` | [SWE-bench](https://github.com/SWE-bench/SWE-bench) software at `02e7a74ffd0b707aab73d203fe87bdc7c76afc8e` | MIT on that GitHub repository. Dataset rows are separate. | Not run. |
| `swe-bench-verified` | Filtered subset described by the [SWE-bench project](https://www.swebench.com/) | MIT above is not a grant for the Verified subset. Confirm the subset's own terms before use. | Not run. |
| `terminal-bench` | [laude-institute/terminal-bench](https://github.com/laude-institute/terminal-bench) at `d28711d0da2675d0bb1d56de45ae5df6082438a3` | Apache-2.0 on that repository. Task notices can be narrower. | Not run. |
| `aider-polyglot` | [Aider-AI/polyglot-benchmark](https://github.com/Aider-AI/polyglot-benchmark) at `7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f` | No SPDX license on the repo. README attributes the exercises to Exercism. [Aider](https://github.com/Aider-AI/aider) is Apache-2.0 at `5dc9490bb35f9729ef2c95d00a19ccd30c26339c`; that does not license the exercises. | Not run. Do not copy the exercises here. |
| `real-task` | Operator-owned repositories | The operator's own rights | Not run. None are included. |

`benchmarks/catalog.json` is the machine-readable copy of this table. Revisions above are the commits whose license metadata was read. A later run must pin the revision it actually checks out. License metadata can change.

## Commands

Plan the local recorder, or see why a public suite is blocked:

```sh
./scripts/benchmark-run.sh plan --suite smoke
./scripts/benchmark-run.sh plan --suite swe-bench-lite
```

Run only the local recorder:

```sh
./scripts/benchmark-run.sh run --suite smoke
```

The smoke receipt sets `public_benchmark_scores` to null, `invokes_model` to false, and `workflow_loaded` to false on every arm. Both arm names run the same local command so the recorder can show a shared model, budget, and seed. That does not load AIC and does not call Claude Code.

`plan` on a public suite exits 3 and writes no score. `run` on a public suite exits 3.

## What a scale run still needs

- A local checkout of the suite at one revision, after the license check above.
- The suite's own evaluator. SWE-bench and Terminal-Bench need their containers and credentials for private tests. This repository does not start those.
- The operator's Claude Code CLI, signed in by the operator. One model id for every arm.
- The same `max_turns`, wall-clock timeout, and spend cap for every arm. The spend cap is a stop rule, not a prediction of cost.
- One shared seed, passed the same way to every arm.
- The plain arm must not see the AIC skill. The AIC arm must see it. Do not use `--bare` on the AIC arm if the skill has to load. Do not use `--bare` on the plain arm either if that would change permissions or login relative to the AIC arm.
- A result file produced by the run. Exit codes, commands, revision, model, budget, and seed are the evidence. A missing file is not a score.

Comparable open-source workflow repositories can be extra arms later, under the same four conditions, and only when their licenses allow the run. None are wired or scored here.
