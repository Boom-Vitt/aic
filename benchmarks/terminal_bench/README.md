# Terminal-Bench adapter

This adapter runs [Terminal-Bench](https://github.com/harbor-framework/terminal-bench) through [Harbor](https://github.com/harbor-framework/harbor) on two Claude Code configurations and writes one JSON receipt:

- **baseline:** plain Claude Code, with no AIC skill and no AIC plugin
- **aic:** Claude Code with the AIC plugin manifest and the portable AIC skill

AIC does not vendor either upstream tree. Harbor checks out the pinned Terminal-Bench commit when a live run starts. This file does not report a score. No credentialed run was executed to produce it.

Checked 2026-11-07. Both pinned `LICENSE` files are Apache-2.0. Their text is not copied here.

| Piece | Repository | Commit | License |
| --- | --- | --- | --- |
| Terminal-Bench tasks | https://github.com/harbor-framework/terminal-bench | `cfc7b6c66f2c731e4b70d92ee71ee5d6d3b55b64` | Apache-2.0 |
| Harbor harness | https://github.com/harbor-framework/harbor | `2bc1a23bd961de0bec8742940f35ac9070c67815` | Apache-2.0 |

At that Terminal-Bench commit, `tasks/` contains 66 directories whose `task.toml` is exactly one level down (`tasks/<task-id>/task.toml`). A task id is that directory name. `html-js-filter` is one id present at the pin. Pass `--task-id` for every task you intend to run. The adapter does not default to the full set.

## What each configuration launches

Both configurations call the same pinned Harbor command: agent `claude-code`, one attempt, the sandbox you name (`docker` by default), and `--include-task-name` for each requested id. The dataset argument is `harbor-framework/terminal-bench@cfc7b6c66f2c731e4b70d92ee71ee5d6d3b55b64` with `--path tasks`.

The baseline passes no `--skill`. The AIC configuration passes `--skill` pointing at a staging directory built from this checkout:

- `skills/aic/` is copied as the portable skill, including its `SKILL.md`
- `.claude-plugin/plugin.json` is copied beside that skill
- the same skill tree is copied again to `skills/aic/` inside the staged directory so the plugin's own skill root resolves

Harbor uploads that directory and the pinned Claude Code agent copies it into `$CLAUDE_CONFIG_DIR/skills`. Claude Code can then load it as a skills-directory plugin and as a skill. This is not an interactive `/plugin marketplace add` install, and it does not claim that every Claude Code build discovers that directory the same way. Symlinks inside the skill or manifest are refused and are not followed.

## Credential gate

`ANTHROPIC_API_KEY` must be set to a non-blank value before any Harbor process starts. When it is unset or blank, the adapter prints:

```text
ANTHROPIC_API_KEY is unset or blank. Terminal-Bench was not started and no receipt was written.
```

It then exits **3**. It does not create the jobs directory, the staging directory, or the receipt, and it does not modify an existing output path.

## Seeds and pass/fail

`--seed` is a paired repetition id. Each seed runs every requested task once on the baseline and once with AIC. Job names are `baseline-seed-<n>` and `aic-seed-<n>`. The same seeds are stored on both sides of the receipt.

The pinned Harbor `run` command has no Anthropic sampling-seed flag. A recorded seed identifies the paired repetition. It does not make model tokens reproducible.

A trial is **passed** only when Harbor's trial `result.json` has no `exception_info` and `verifier_result.rewards.reward` is a finite number greater than or equal to 1. Every other parsed trial is **failed**. The receipt copies that reward (or `null` when Harbor did not report one). It does not invent a reward. Task failures are still written into the receipt. If Harbor stops before every requested task has one trial, no receipt is written.

## Receipt

The receipt is JSON, schema `aic.terminal-bench.receipt`, version 1. It records:

- the Terminal-Bench, Harbor, and AIC commit pins, including each upstream license
- `pins.harbor.invocation`: `pinned-uvx` for the default launcher, or `override` when `AIC_TERMINAL_BENCH_HARBOR` selected another executable (an override does not prove that executable is the pinned Harbor commit)
- the AIC commit and whether the worktree was dirty, without listing paths
- the model id, sandbox, task ids, and seeds
- for each configuration, each task, and each seed: `passed`, `reward`, `error`, and the Harbor job name

`--validate-receipt PATH` checks that shape and does not start Harbor or read `ANTHROPIC_API_KEY`.

## Run once a key exists

The process needs Python 3.11 or newer, `uvx`, Docker, network access for the pinned Harbor and Terminal-Bench checkouts, and `ANTHROPIC_API_KEY` already in the environment. It calls the model and can spend provider quota. The model id below is the Claude Code example in the pinned Terminal-Bench README, not a model this adapter measured. Substitute the id your key is allowed to call. The default concurrency is 1.

```bash
python3 benchmarks/terminal_bench/adapter.py \
  --model anthropic/claude-fable-5 \
  --task-id html-js-filter \
  --seed 0 \
  --jobs-dir .work/terminal-bench/jobs \
  --output .work/terminal-bench/receipt.json
```

Repeat `--task-id` and `--seed` to add tasks and paired repetitions. The adapter refuses to overwrite an existing receipt, job directory, or staging directory. Exit 0 means a receipt was written, including when individual tasks failed. Exit 1 means Harbor stopped before a complete trial set and no receipt was written. Exit 2 is a local usage or preflight error. Exit 3 is the missing-credential gate above.

`AIC_TERMINAL_BENCH_HARBOR` can point at a local Harbor executable instead of `uvx`. Use that only when you have a separate reason to; the receipt then sets `invocation` to `override`.

## Offline tests

`./scripts/verify.sh` runs `tests/test_terminal_bench_adapter.py`. Those tests exercise the credential gate, receipt schema, reward pass/fail mapping, and the two Harbor command lines. They use a local stub executable. They do not contact a model, and their fixture rewards are not Terminal-Bench scores.

## Limits

- A receipt from a live run is evidence about that model, those task ids, those seeds, and this plugin/skill staging. It is not a leaderboard row and not a general claim that AIC improves terminal work.
- Installing or copying the skill does not prove the model read it.
- Docker, `uvx`, and the model credential are live-run requirements. Verification does not start them.
- Harbor's own job directories remain after a failed launch so the logs can be inspected. The AIC receipt is written only when every requested trial was parsed.
- Do not commit receipts, job logs, or API keys.
