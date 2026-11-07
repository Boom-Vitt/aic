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

## Routing packs

`tests/fixtures/routing-scenarios.json` is the dev pack. Tune prompts and the skill on that pack only.

`benchmarks/routing/heldout-v2.json` is the release pack. Score it once per release. Do not tune on it. This checkout does not contain that file until the heldout-v2 change is present. `./scripts/run-benchmarks.sh --routing-pack heldout-v2` exits 2 before any model call when the file is missing, and it names that path.

A run records the selected pack name and the SHA-256 digest of the pack file in `provenance.json`.

## What a scale run still needs

- A local checkout of the suite at one revision, after the license check above.
- The suite's own evaluator. SWE-bench and Terminal-Bench need their containers and credentials for private tests. The default command below does not start those. The optional flags do, only for a checkout at the pinned revision, and they still publish no score.
- The operator's Claude Code CLI, signed in by the operator. One model id for every arm.
- The same `max_turns`, wall-clock timeout, and spend cap for every arm. The spend cap is a stop rule, not a prediction of cost.
- One shared seed, passed the same way to every arm.
- The plain arm must not see the AIC skill. The AIC arm must see it. Do not use `--bare` on the AIC arm if the skill has to load. Do not use `--bare` on the plain arm either if that would change permissions or login relative to the AIC arm.
- A result file produced by the run. Exit codes, commands, revision, model, budget, and seed are the evidence. A missing file is not a score.

Comparable open-source workflow repositories can be extra arms later, under the same four conditions, and only when their licenses allow the run. None are wired or scored here.

## Pinned AIC-versus-baseline command

`./scripts/run-benchmarks.sh` is the comparison to run once `ANTHROPIC_API_KEY` is set in the environment. If that variable is missing, empty, or contains whitespace, the command exits 3 and does not call a model. The key is not an argument and it is not written into the bundle.

The command runs two pinned pieces, using `benchmarks/pinned.json`:

1. `python3 -m benchmarks.routing.compare --pack <pack file>` compares the no-skill arm with the AIC arm. `--routing-pack dev` is the default and selects the dev pack. `--routing-pack heldout-v2` selects the release pack. Expected labels stay out of the prompt. Both arms use the pinned model id, temperature 0, and the same output-token cap. The recorded seed is not sent to the Messages API.
2. `python3 -m benchmarks.aicbench --sandbox container --official` runs the container sandbox. Only that sandbox can mark an aicbench report official. The command does not invent a token price for it. The aicbench report records Claude Code's own cost field when a run finishes.

`--dry-run` prints the budget cost ceiling and exits. It does not call a model, does not start bubblewrap, and does not create `results/`.

The ceiling uses the pinned Claude Sonnet 5.5 base prices checked 2026-11-07: 2 USD per million input tokens and 10 USD per million output tokens. The pricing page is the `url` in `benchmarks/pinned.json`. Input is not counted with Anthropic's tokenizer. The ceiling uses one token per UTF-8 byte of the system text and the user text that would be sent. Output uses the pinned `max_tokens` cap on every routing call. Cache discounts are not applied. The printed figure is a ceiling, not an invoice. The model id sent to the provider is `claude-sonnet-5-5`. The pinned seed is recorded and is not sent, because this command does not claim the Messages API accepts a seed.

A real run writes `results/<UTC date>-<full git SHA>/`:

| File | What it records |
| --- | --- |
| `provenance.json` | Git SHA, whether the worktree was dirty, model id, date, pinned settings, routing pack name, pack path, and the pack's SHA-256 digest |
| `estimate.json` | The ceiling printed before any model call |
| `receipts/` | Routing, the bubblewrap probe, and any optional suite that ran |
| `raw/` | Model text and harness stdout/stderr |

The command refuses to overwrite an existing bundle. `public_benchmark_scores` stays null. A routing receipt may count label matches for that bundle. This document does not publish those counts. Raw text is redacted if it contains the API key.

Terminal-Bench and SWE-bench Lite stay out unless you pass a flag.

```sh
./scripts/run-benchmarks.sh --dry-run
./scripts/run-benchmarks.sh
./scripts/run-benchmarks.sh --routing-pack heldout-v2
./scripts/run-benchmarks.sh --terminal-bench --terminal-bench-checkout /absolute/pinned/terminal-bench
./scripts/run-benchmarks.sh --swe-bench-lite --swe-bench-lite-checkout /absolute/pinned/SWE-bench --swe-bench-lite-predictions /absolute/predictions.jsonl
```

`--terminal-bench` runs one task of `terminal-bench-core==0.1.1` through the checkout's `terminal_bench` CLI at revision `d28711d0da2675d0bb1d56de45ae5df6082438a3`. `--swe-bench-lite` runs the pinned SWE-bench harness at revision `02e7a74ffd0b707aab73d203fe87bdc7c76afc8e` on a JSONL predictions file of at most 5 rows. Both CLIs have no token budget, so the estimate lists them as unpriced instead of inventing a dollar amount. Their receipts keep `public_benchmark_scores` null and `aic_treatment` false: this command does not claim the skill was loaded inside those harnesses. A missing checkout, the wrong revision, or a missing predictions file exits 3 before any routing call.

GitHub Actions starts this only from a manual `workflow_dispatch` on `.github/workflows/benchmarks.yml`. Pull requests and pushes do not start it. The workflow installs the `bubblewrap` package, passes `secrets.ANTHROPIC_API_KEY` only into the run step, checks out with `persist-credentials: false`, and uploads `results/` as an artifact. Action revisions are pinned SHAs. The workflow token has `contents: read`, which is enough for upload-artifact v7. The dispatch input `routing_pack` defaults to `dev`.

