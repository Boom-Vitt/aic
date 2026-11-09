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
| `aider-polyglot` | Exercism tracks named by [Aider-AI/polyglot-benchmark](https://github.com/Aider-AI/polyglot-benchmark) at `7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`. That mirror has no root license and is not fetched. | MIT on six Exercism tracks, checked 2026-11-09. See the pin below. | Not run. The adapter can fetch those tracks. No score is claimed. |
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

`tests/fixtures/routing-scenarios.json` has doc role `dev`. Tune only on that pack. Do not read it when editing `skills/aic`. A skill written from those requests or labels measures the fixture instead of the skill.

`benchmarks/routing/heldout-v2.json` is the release pack. Score it once per release. Do not tune the skill against it, and do not read it when editing `skills/aic`. Its answers file is not model input.

`./scripts/run-benchmarks.sh --routing-pack heldout-v2` passes that file to `benchmarks.routing.compare --pack`. The default remains the dev pack. A run records the selected pack name and the SHA-256 digest of the pack file in `provenance.json`.

## What a scale run still needs

- A local checkout of the suite at one revision, after the license check above.
- The suite's own evaluator. SWE-bench and Terminal-Bench need their containers and credentials for private tests. The default command below does not start those. The optional flags do, only for a checkout at the pinned revision, and they still publish no score.
- The operator's Claude Code CLI, signed in by the operator. One model id for every arm.
- The same `max_turns`, wall-clock timeout, and spend cap for every arm. The spend cap is a stop rule, not a prediction of cost.
- One shared seed, passed the same way to every arm.
- The plain arm must not see the AIC skill. The AIC arm must see it. Do not use `--bare` on the AIC arm if the skill has to load. Do not use `--bare` on the plain arm either if that would change permissions or login relative to the AIC arm.
- A result file produced by the run. Exit codes, commands, revision, model, budget, and seed are the evidence. A missing file is not a score.

Comparable workflow repositories are registered in `benchmarks/baselines/registry.json`. A live run fetches each one at its pinned commit, checks the root license file, and discards the checkout with the run. None of those trees are vendored here. No public score includes them yet.

## Pinned AIC-versus-baseline command

`./scripts/run-benchmarks.sh` is the comparison to run once `ANTHROPIC_API_KEY` is set in the environment. If that variable is missing, empty, or contains whitespace, the command exits 3 and does not call a model. The key is not an argument and it is not written into the bundle.

The default command runs two pinned pieces, using `benchmarks/pinned.json`. `--baselines` adds a third piece: every arm in the baseline registry, on the one local aicbench task `bugfix-ledger-signs`, with that same model and seed and the shared budget in the registry. The third piece still leaves `public_benchmark_scores` null. It is not a SWE-bench, Terminal-Bench, or Aider result.

The two default pieces are:

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

Terminal-Bench, SWE-bench Lite, and Aider polyglot stay out unless you pass a flag.

```sh
./scripts/run-benchmarks.sh --dry-run
./scripts/run-benchmarks.sh
./scripts/run-benchmarks.sh --routing-pack heldout-v2
./scripts/run-benchmarks.sh --terminal-bench --terminal-bench-checkout /absolute/pinned/terminal-bench
./scripts/run-benchmarks.sh --swe-bench-lite --swe-bench-lite-checkout /absolute/pinned/SWE-bench --swe-bench-lite-predictions /absolute/predictions.jsonl
./scripts/run-benchmarks.sh --aider-polyglot
```

`--terminal-bench` runs one task of `terminal-bench-core==0.1.1` through the checkout's `terminal_bench` CLI at revision `d28711d0da2675d0bb1d56de45ae5df6082438a3`, once per official arm. The agent phase runs on the host behind the egress proxy. The task container does not receive the API key, `agent-env.sh`, or a copy of an installed third-party arm. Before that phase forwards a command, the container is disconnected from every network, including Docker-internal networks. The run accepts only an empty Networks map or the `none` network and refuses if any other attachment remains. A task that still needs a route does not run in official mode. `--swe-bench-lite` runs the six official arms (`plain-claude-code`, `aic`, `ecc`, `agent-skills`, `planning-with-files`, and `gstack`) through the same agent-phase proxy under the shared `max_usd` stop, then runs the pinned SWE-bench harness at revision `02e7a74ffd0b707aab73d203fe87bdc7c76afc8e` on a JSONL predictions file of at most 5 rows. `superpowers` stays out. The install phase has no API key and allows only the GitHub, npm, and Bun hosts. The agent phase allows only `api.anthropic.com:443`. Official runs refuse to start when bubblewrap or the proxy is missing. Both CLIs still have no token budget, so the estimate lists them as unpriced instead of inventing a suite cost. The shared `max_usd` stop is sent anyway. It is not a price for those suites. `public_benchmark_scores` stays null. `aic_treatment` is true only for the `aic` arm when a process read that shipped plugin. It stays false for `plain-claude-code` and for every other plugin. `harness_loaded_aic` stays false until the Terminal-Bench run writes `arm-load.json`. The SWE-bench evaluation command scores predictions and does not load a plugin, so `evaluation_aic_treatment` stays false. A missing checkout, the wrong revision, a missing predictions file, or a missing key exits 3 before any routing call.

GitHub Actions starts this only from a manual `workflow_dispatch` on `.github/workflows/benchmarks.yml`. Pull requests and pushes do not start it. The workflow installs the `bubblewrap` package, passes `secrets.ANTHROPIC_API_KEY` only into the run step, checks out with `persist-credentials: false`, and uploads `results/` as an artifact. Action revisions are pinned SHAs. The workflow token has `contents: read`, which is enough for upload-artifact v7. The dispatch input `routing_pack` defaults to `dev`. The dispatch input `baselines` defaults to false, so a manual run does not fetch the registered repositories until that input is set.

## Workflow baselines

No public benchmark score is claimed for these arms. The registry is the pin. Licenses below were read from the root license file at that commit on 2026-11-08. A later live run refuses the arm when the file's SHA-256 differs. A root MIT grant is not a separate review of every nested file. Nested notices stay in the fetched tree and are not copied here.

| Arm | Repository | Commit | License | Root license SHA-256 |
| --- | --- | --- | --- | --- |
| `plain-claude-code` | None. Claude Code with no plugin. | | | |
| `aic` | This repository's `.claude-plugin` | Working tree | Apache-2.0 | |
| `superpowers` | [obra/superpowers](https://github.com/obra/superpowers) | `22f0b463e7a5e579904dd6211a520321035526f7` | MIT. Copyright (c) 2025 Jesse Vincent | `a37e0e9697144819e1d965176ac4ae5bc3fa02d11e7812036bbcadf6dafe2400` |
| `ecc` | [affaan-m/ECC](https://github.com/affaan-m/ECC) | `d2ef2680594f9a17526a6e1a2e18b3d242c5d17b` | MIT. Copyright (c) 2026 Affaan Mustafa | `326146379f01bb137c0a5d3c54770c1aa31076705c8b88a7f6b26a460f6221b2` |
| `agent-skills` | [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | `301b02b12bff98e4688e6984af6556802322bbde` | MIT. Copyright (c) 2025 Addy Osmani | `6f202f8bd568cd730dbb2b0d1f8e243bc74c2fa1f64dbce9b2c7ea08bd5c9fd7` |
| `planning-with-files` | [OthmanAdi/planning-with-files](https://github.com/OthmanAdi/planning-with-files) | `2362ca385ad74f061aa0e7b73f56543a4b7e6df2` | MIT. Copyright (c) 2026 Ahmad Adi | `4f2e5ecfaa4e0833621cfe54c0bdc2f60f086c0925540d7bdc713517eafb3c84` |
| `gstack` | [garrytan/gstack](https://github.com/garrytan/gstack) | `23f9d07ce9e802ac148a8a353228f201655fc5b8` | MIT. Copyright (c) 2026 Garry Tan | `e56fbb5b3d95756f3fa1cfefa24732ec79f18ece1ad08a4e79e00df57e8b198c` |

Every official arm runs inside the same bubblewrap container `benchmarks/aicbench/sandbox.py` uses for `aicbench --sandbox container`. Fetch, install, and the agent are inside that container. Each arm gets a fresh `HOME` and a fresh Claude config directory. The repository, the invoking user's home, task `oracle/` directories, task `reference/` directories, `benchmarks/routing/heldout-v2.json`, and `benchmarks/routing/heldout-v2-answers.json` are not mounted. Receipts record `"sandbox": "container"`. A live run with sandbox `none` is refused, including an official result. The key-free stub stays on sandbox `none` and stays unofficial.

Each live arm has two phases inside `bwrap --unshare-net`. A host HTTP CONNECT proxy listens on a Unix socket that the container bind-mounts. An in-container forwarder accepts `127.0.0.1:3128` and splices it to that socket, and the phase sets `HTTPS_PROXY` to that loopback URL. Direct connections have no route. Official results refuse to run without this egress proxy.

The install phase is git fetch, `npx`, and gstack `./setup`. Its environment has no `ANTHROPIC_API_KEY` and no other secret. Its allow-list is `github.com:443`, `codeload.github.com:443`, `registry.npmjs.org:443`, `bun.sh:443`, `objects.githubusercontent.com:443`, `release-assets.githubusercontent.com:443`, and `github-releases.githubusercontent.com:443`. The agent phase has the API key. Its allow-list is `api.anthropic.com:443` only. Receipts record both policies. The read-only system binds are `/usr`, `/lib`, `/lib64`, `/bin`, `/sbin`, the certificate directories, and `/etc/resolv.conf` when those paths exist outside the repository. Writable binds are the per-arm workspace, that arm's fresh `HOME`, and that arm's fresh config directory, plus a tmpfs at `/tmp`. The Claude executable file is also read-only mounted when it lives outside those system prefixes. The API key is not a command argument.

`plain-claude-code` installs nothing. `aic` is a staged directory of the wheel packages `skills/aic` and `src/aic_quickstart`, plus `LICENSE`, `NOTICE`, `README.md`, and the `.claude-plugin` manifests. `claude --plugin-dir` points at that directory, not at the repository root. `agent-skills` and `planning-with-files` use the `--plugin-dir` their pinned docs describe, on the fetched commit. `ecc` runs `npx ecc-universal@2.2.3 setup` with the pinned help flags for Global user, Standard hooks, and confirm. `gstack` is fetched into `~/.claude/skills/gstack` in the fresh home and `./setup` is run with Bash; Bun 1.4.2 or newer must be on `PATH`. `superpowers` is `unverified-install`: the pinned README's Claude Code section documents only marketplace slash commands, those commands do not select this commit, and the README does not sanction `--plugin-dir`. That arm is excluded from official comparisons. Every compared arm gets the same model id, the same seed, the same budget (`max_turns` 30, `timeout_sec` 600, `max_usd` 0.35), and the same allowed tools, `Read,Edit,Write,Bash,AskUserQuestion`. `max_usd` is the shared stop from `benchmarks/budget.py`. Input allowance is `max_turns` times `timeout_sec` tokens (one token per second of the wall clock, on every turn). Output allowance is `max_turns` times the pinned `max_tokens` (1024). Both use the pinned Claude Sonnet 5.5 base rates, 2 USD per million input tokens and 10 USD per million output tokens. The exact product is 0.3432 USD (343200 millionths). The sent cap rounds up to the next cent, 0.35. Official comparisons refuse a null cap. The figure is a stop, not a predicted cost and not an invoice. The seed is recorded and is not sent to the provider. The prompt text is the same; the install is the treatment. Install commands are stored on the arm and copied onto the receipt.

These repositories were not registered, after the license file at the default-branch head was checked on the same day: `anthropics/skills` and `multica-ai/andrej-karpathy-skills` have no root license file; `hesreallyhim/awesome-claude-code` is CC BY-NC-ND 4.0; `anthropics/claude-plugins-official` is Apache-2.0 and is a plugin directory rather than one workflow; `wshobson/agents` is MIT and is a multi-plugin marketplace without one `plugin.json`; `thedotmack/claude-mem` is Apache-2.0 and is a memory service, not a workflow skill pack.

### Maintainer command once a key exists

Add `ANTHROPIC_API_KEY` as a repository secret. Do not put the key in the repository, in an argument, or in the results bundle. Then either of these runs the pinned comparison, including every registered arm:

```sh
./scripts/run-benchmarks.sh --baselines
```

On GitHub Actions, dispatch `.github/workflows/benchmarks.yml` with `baselines` set to true. The workflow already passes `secrets.ANTHROPIC_API_KEY` only into that run step. If the variable is missing, empty, or contains whitespace, the command exits 3 and does not fetch a repository or call a model.

That command writes `results/<UTC date>-<full git SHA>/receipts/baselines.json` beside the routing and aicbench receipts. `public_benchmark_scores` in that file stays null. Do not copy a pass or a cost from it into the score history in `docs/ROADMAP.md` until the run used a real model and the raw bundle is the linked evidence. A missing Claude Code executable fails the live arm. It does not invent a pass rate.

### Key-free plumbing proof

CI runs this without a key and without fetching:

```sh
python3 -m benchmarks.aicbench --baseline-stub
```

The same proof is `python3 -m benchmarks.baselines stub`. It runs `benchmarks/aicbench/stub/agent.py` once per arm, then the aicbench oracle for `bugfix-ledger-signs`. Each receipt records the arm, model, budget, seed, the stub's reported cost, wall time, and pass or fail. `public_benchmark_scores` is null, `invokes_model` is false, and `fetched` is false. The stub applies the task's reference solution so the oracle can pass. That pass proves the mount and the grader. It is not a model score and it is not a row in the score history. The sandbox is `none`, so the stub can read the reference. That is why the report stays unofficial. Official baseline results refuse sandbox `none`.

The suite wiring proof is separate and also key-free:

```sh
python3 -m benchmarks.suite_arms stub
```

It stages the shipped AIC plugin and local stand-ins for the other official arms, then runs the same stub agent. `aic_treatment` is true only for `aic`, because that process read plugin name `aic`. It stays false for `plain-claude-code`, `ecc`, `agent-skills`, `planning-with-files`, and `gstack`. `superpowers` is excluded. `harness_loaded_aic` is false: Terminal-Bench and SWE-bench are not started. `public_benchmark_scores` is null. Nothing is fetched. The shared budget on that report is `max_turns` 30, `timeout_sec` 600, and `max_usd` 0.35.

## Aider polyglot

Checked 2026-11-09 from each root license file. The machine-readable pin is `benchmarks/polyglot/pins.json`. A root MIT grant is not a separate review of every nested file. Exercise bytes are not stored in this repository.

Aider's benchmark README at `5dc9490bb35f9729ef2c95d00a19ccd30c26339c` says to clone `Aider-AI/polyglot-benchmark`. That commit of the mirror, `7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f` (2024-12-22), has no root license file. No root license file was added later; the default branch still points at that commit. The GitHub license API returns null. The README attributes the exercises to Exercism and does not itself grant a license. The adapter does not fetch that tree. Aider's own `LICENSE.txt` is Apache-2.0, sha256 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`. That grant covers the harness, not the exercises. `benchmark/clone-exercism.sh` in that same commit clones the six Exercism tracks named below.

The exercise index is the 225 practice-directory names listed in the unlicensed mirror. Those names are not the exercise text. The default live subset is one exercise, `cpp` / `all-your-base`, the first name in that index. It is not the full 225-case run. `public_benchmark_scores` stays null until a real model run is linked from `docs/ROADMAP.md`.

| Track | Commit | Commit date | Root license | SHA-256 |
| --- | --- | --- | --- | --- |
| [exercism/cpp](https://github.com/exercism/cpp) | `9d47dff5f64f9244699b82cfcdf68ed72edd289f` | 2026-11-08 | MIT. Copyright (c) 2021 Exercism | `e52f804e74f0fbd34e8927962319df346166b8194094309a0aee318693df44df` |
| [exercism/go](https://github.com/exercism/go) | `54da18da1bf36b9c03cdad48d592fb28101ac08f` | 2026-11-08 | MIT. Copyright (c) 2021 Exercism | `e52f804e74f0fbd34e8927962319df346166b8194094309a0aee318693df44df` |
| [exercism/java](https://github.com/exercism/java) | `be2d006c30c50e0154231dd987d5a3b5526c0427` | 2026-11-08 | MIT. Copyright (c) 2021 Exercism | `e52f804e74f0fbd34e8927962319df346166b8194094309a0aee318693df44df` |
| [exercism/javascript](https://github.com/exercism/javascript) | `43dd0939ec1e1bdb3a69852b0512928b9c4ef996` | 2026-11-08 | MIT. Copyright (c) 2021 Exercism | `e52f804e74f0fbd34e8927962319df346166b8194094309a0aee318693df44df` |
| [exercism/python](https://github.com/exercism/python) | `479f11b44b02337b0413e805b948491c2179615a` | 2026-11-07 | MIT. Copyright (c) 2021 Exercism. The track README says this repository uses the MIT License. Its PSF paragraph is about Python itself. | `e52f804e74f0fbd34e8927962319df346166b8194094309a0aee318693df44df` |
| [exercism/rust](https://github.com/exercism/rust) | `523fff27328e9b85085cd7eb7bd6ac36af730433` | 2026-11-08 | MIT. Copyright (c) 2021 Exercism. The track README says this repository uses the MIT License. | `e52f804e74f0fbd34e8927962319df346166b8194094309a0aee318693df44df` |

No reviewed track was excluded. MIT permits a runtime copy when the copyright and permission notice stay with that copy. The fetched checkout keeps the root `LICENSE`. The agent workspace omits `.meta`, where Exercism keeps exemplar solutions. The live command fetches only the selected exercise directory plus that license file, inside the install-phase egress proxy. That phase has no API key. The agent phase is the only phase that receives the key, and its allow-list is `api.anthropic.com:443`. The score command runs in bubblewrap with `--unshare-net` and without the key. Official runs refuse to start when bubblewrap or the proxy is missing. The same six arms, model, seed, and budget apply: `max_turns` 30, `timeout_sec` 600, `max_usd` 0.35. `superpowers` stays out. A missing compiler or test runner is a failed case, not a pass.

```sh
python3 -m benchmarks.polyglot stub
python3 -m benchmarks.polyglot live
```

The stub builds an original local git fixture, fetches it through the same sparse checkout, and scores it with unittest. `upstream_fetched` is false. `sandbox` is `none`, `official` is false, and `invokes_model` is false. The same process builds the install, agent, and score bubblewrap commands. It does not start bubblewrap and it does not call a model. The fixture is deleted when the process exits.

