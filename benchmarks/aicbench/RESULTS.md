# aicbench results methodology

This file says which runs may be published. It does not contain a measured pass rate, token count, cost, or wall time. Those fields come only from a report the runner writes after a real Claude Code process.

## What counts

A published aicbench result is a report with all of the following:

- `"sandbox": "container"`
- `"official": true`
- `"publication_warning": null`

That report is produced only by a completed run with `--sandbox container`. Bubblewrap starts the agent and does not mount this repository, so the process is not given `reference/` or `oracle/`. The grader still checks the SHA-256 manifest after the process exits.

The runner sets `official` from the sandbox mode. There is no switch that marks a non-container report official. `require_official` rejects a report whose sandbox is not `container`, whose `official` field is not true, or which still carries `publication_warning`. `--require-official REPORT.json` uses that check and does not start a model. Editing the JSON to flip `official` does not make the report publishable.

## What does not count

A run without `--sandbox container` is debugging output. The report is written with `"official": false` and a `publication_warning`, and the runner prints that warning. The agent can read `reference/` through the operating system. `--official` without `--sandbox container` exits 2 and does not start Claude Code.

A missing or blank `ANTHROPIC_API_KEY` exits 3 and writes no report. An invalid trial, a failed task, or a client-side `total_cost_usd` estimate is not a pass rate by itself. Do not fill a missing cost or token field with a computed price or a guessed count.

## How a published run is started

Install bubblewrap first. CI runs on Ubuntu and does not install it, because `./scripts/verify.sh` does not call the model. The verify workflow records the setup command. On that image:

```bash
sudo apt-get update && sudo apt-get install -y bubblewrap
bwrap --version
```

The package is `bubblewrap`. The executable is `bwrap`. User namespaces must work. Then:

```bash
python3 benchmarks/aicbench/runner.py --sandbox container --official --output report.json
python3 benchmarks/aicbench/runner.py --require-official report.json
```

`--require-official` exits 0 only for a container report. It exits 2 for every other file.

## Fields

pass@1 is the unbiased per-task estimator averaged across tasks. Tokens are taken from Claude Code's `usage` object when `input_tokens` and `output_tokens` are present. Cost is the sum of reported `total_cost_usd` values, or null if any sample omits the field. Wall time is the runner's clock around each agent process. See [README.md](README.md) for the task list and the grading rules.
