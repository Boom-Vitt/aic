# aicbench

Offline-checked coding tasks for the kind of work AIC is asked to plan: a bug that crosses files, a feature that needs tests, a refactor with the same behavior, or documentation written from the code. Each task is original Apache-2.0 material. See [NOTICE](NOTICE).

The hidden oracle grades a workspace with the Python standard library. It does not call a model. The reference solution is how CI proves the task is solvable and that the oracle accepts a correct result and rejects the starting tree.

## Tasks

| Id | Category | What the agent is asked to do |
| --- | --- | --- |
| `bugfix-ledger-signs` | bugfix | Fix signed amounts in the parser and the totals |
| `bugfix-interval-merge` | bugfix | Fix half-open overlap and a merge that drops meetings |
| `bugfix-retry-budget` | bugfix | Count the first attempt and skip non-retryable errors |
| `bugfix-config-layers` | bugfix | Deep-merge layers so the user value wins |
| `bugfix-path-allowlist` | bugfix | Keep a joined path inside the allowlisted root |
| `bugfix-csv-roundtrip` | bugfix | Quote and decode inventory fields that contain commas |
| `bugfix-session-expiry` | bugfix | Expire on the exact instant and refuse a revoked refresh |
| `feature-slug` | feature | Add `slugify` and unit tests |
| `feature-ring-buffer` | feature | Add a ring buffer that drops the oldest item, with tests |
| `feature-duration` | feature | Parse `1h30m` style durations, with tests |
| `feature-cursor-page` | feature | Add cursor pagination, with tests |
| `feature-redact` | feature | Redact secrets, longest match first, with tests |
| `feature-semver` | feature | Compare strict three-part versions, with tests |
| `refactor-billing-package` | refactor | Split one billing module into a package |
| `refactor-shared-email` | refactor | Share one email normalizer between two callers |
| `refactor-discount-registry` | refactor | Replace a discount chain with a registry |
| `refactor-typed-errors` | refactor | Raise missing-key and bad-type errors |
| `docs-rate-limiter` | docs | Document the token bucket without changing it |
| `docs-state-machine` | docs | List every legal transition from the table |
| `docs-cli-reference` | docs | Document argparse help strings |
| `docs-api-inventory` | docs | Write a signature line for each public function |

Public files for a task live in `workspace/` plus `instruction.md`. `oracle/` and `reference/` are grader inputs. A live agent is given a copy of `workspace/` only.

## Offline proof

`./scripts/verify.sh` discovers `tests/test_aicbench_*.py`. Those tests grade every starting workspace and every reference solution. They do not need an API key. A starting workspace must fail. The reference must pass. A one-line break of a solved ledger must fail again.

## Comparison runner

The runner compares two arms on the same tasks:

- `baseline`: Claude Code, with project skills and user customizations skipped
- `claude_code_plus_aic`: the same invocation, plus AIC installed for Claude Code and passed with `--add-dir`

Checked against Claude Code's headless interface on 2026-11-07. The process is `claude --bare -p ... --output-format json`. Bare mode does not inject the skill list, so the AIC arm's prompt tells the model to read the installed `SKILL.md`. Both arms receive the same task text and the same approval to edit that workspace. This is one harness, not a claim that every host behaves this way.

```bash
python3 benchmarks/aicbench/runner.py --output report.json
```

Without `ANTHROPIC_API_KEY`, or when the key is blank, the process exits **3** and does not start Claude Code. A usage error exits 2. A finished comparison exits 0 even when some tasks fail; the report holds the failures.

The report records, per arm and per task:

- **pass@1** — for each task, the unbiased estimator over that task's samples (default one sample). The arm value is the mean across tasks. A timed-out or harness-broken sample counts as not passed.
- **tokens** — `input_tokens` and `output_tokens` from Claude Code's top-level `usage` object when both are present. Cache fields are included only when Claude Code reports them. A missing usage object stays null. Token counts are never estimated from text length.
- **cost** — the sum of Claude Code's `total_cost_usd` values, as a decimal string. AIC does not multiply tokens by a price. If any sample omits the field, the aggregate cost is null.
- **wall time** — `time.perf_counter` around each Claude Code process, in seconds, summed for the arm.

`total_cost_usd` is Claude Code's own client-side estimate. It can differ from an invoice. This repository does not ship a measured pass rate: publishing a number requires an actual run with a key.

Useful limits: `--tasks id,id`, `--samples` from 1 to 10, `--max-turns`, `--agent-timeout`, `--model`, `--arm`, and `--sandbox`.

## Isolation

Before any agent starts, the runner stores a SHA-256 manifest of that task's `oracle/` file and `reference/` tree. The agent cwd is a copy of `workspace/` in a temp directory outside this repository. `reference/` and `oracle/` are not copied there and are not passed as `--add-dir`. The child environment does not include `PYTHONPATH` or the repository path. After the agent exits, the manifest is checked again. A mismatch marks that trial `invalid`, does not count as a pass, and does not execute the altered oracle. Grading copies the verified oracle bytes into a new temp directory and runs them with `python -I`. The workspace is not placed on `sys.path`. A top-level module whose name matches the standard library or `unittest` is not used; the real standard-library module is.

`--sandbox container` runs the agent under bubblewrap (`bwrap`) with the workspace and the installed skill mounted, plus the usual system library directories. It does not mount this repository. If `bwrap` is missing, the runner exits 2 and does not start Claude Code. This mode needs working user namespaces. It is not run by `./scripts/verify.sh`.

Without that sandbox, a shell can still read any path the operating system allows, including this checkout if the process discovers it. The manifest detects writes to the oracle and the reference. It does not detect a read. That residual exposure is why the container option exists.

## Limits

The oracle process has no API key. A workspace file named `unittest.py` cannot satisfy the grader's import. A result from this runner is a measurement of those two arms on these tasks, not a general ranking of AIC, Claude Code, or a model.
