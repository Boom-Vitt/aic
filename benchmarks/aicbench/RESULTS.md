# aicbench results methodology

This file says which runs may be published. It does not contain a measured pass rate, token count, cost, or wall time. Those fields come only from a report the runner writes after a real Claude Code process.

## What counts

A published model result is a Claude Code report with all of the following:

- `"sandbox": "container"`
- `"official": true`
- `"publication_warning": null`
- `"measured": true`

`kind` must not be `pipeline-smoke`. Bubblewrap starts the agent and does not mount this repository, so the process is not given `reference/` or `oracle/`. The grader still checks the SHA-256 manifest after the process exits.

The runner sets `official` from the sandbox mode. There is no switch that marks a non-container report official. `require_official` rejects a report whose sandbox is not `container`, whose `official` field is not true, or which still carries `publication_warning`. A pipeline smoke report is official only as that sandbox attestation, and only while `model_result`, `measured`, and `invokes_model` stay false. `--require-official REPORT.json` uses that check and does not start a model. Editing the JSON to flip `official` does not make an unsandboxed report publishable.

## What does not count

A run without `--sandbox container` is debugging output. The report is written with `"official": false` and a `publication_warning`, and the runner prints that warning. The agent can read `reference/` through the operating system. `--official` without `--sandbox container` exits 2 and does not start Claude Code.

A missing or blank `ANTHROPIC_API_KEY` exits 3 and writes no report. An invalid trial, a failed task, or a client-side `total_cost_usd` estimate is not a pass rate by itself. Do not fill a missing cost or token field with a computed price or a guessed count.

## Pipeline smoke

`.github/workflows/aicbench-sandbox.yml` installs bubblewrap on `ubuntu-latest` and runs `python3 -m benchmarks.aicbench --pipeline-smoke --sandbox container` on every pull request. The agent is `stub/agent.py`, a deterministic pipeline smoke test. It is not a model result. It is not a row in a results table. This file does not record a pass rate, token count, cost, or wall time for that stub.

The container smoke report has `"sandbox": "container"`, `"official": true`, `"model_result": false`, `"measured": false`, and `"invokes_model": false`. The same smoke with `--sandbox none` has `"official": false` because the stub can read `reference/` and `oracle/`. `--require-official` accepts the container smoke report only as that sandbox attestation and says it is not a model result. It rejects the unsandboxed report. A hand-edited `official` field does not make the unsandboxed report official, and a smoke report with `measured` set to true is refused.

`./scripts/verify.sh` runs this smoke without a model key. The container probe runs when `bwrap` is on PATH. `.github/workflows/verify.yml` does not install bubblewrap and does not run the smoke.

## How a published model run is started

Install bubblewrap before a Claude Code comparison. `./scripts/verify.sh` does not call the model. The verify workflow records the setup command and does not install bubblewrap. On Ubuntu:

```bash
sudo apt-get update && sudo apt-get install -y bubblewrap
bwrap --version
```

The package is `bubblewrap`. The executable is `bwrap`. User namespaces must work. Then:

```bash
python3 benchmarks/aicbench/runner.py --sandbox container --official --output report.json
python3 benchmarks/aicbench/runner.py --require-official report.json
```

`--require-official` exits 0 for a container report that passes the check above. It exits 2 for every other file, including an unsandboxed pipeline smoke report.

## Fields

pass@1 is the unbiased per-task estimator averaged across tasks. Tokens are taken from Claude Code's `usage` object when `input_tokens` and `output_tokens` are present. Cost is the sum of reported `total_cost_usd` values, or null if any sample omits the field. Wall time is the runner's clock around each agent process. See [README.md](README.md) for the task list and the grading rules.
