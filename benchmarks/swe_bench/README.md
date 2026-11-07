# SWE-bench Lite: Claude Code and Claude Code plus AIC

This directory runs one comparison. It asks Claude Code to repair [SWE-bench Lite](https://huggingface.co/datasets/SWE-bench/SWE-bench_Lite) instances, once as a baseline and once with the AIC plugin loaded, then scores both prediction files with the official SWE-bench harness at a pinned commit.

It does not ship a resolve rate. A completed run's only score is the harness `results.json` written under the output directory. The 10-instance smoke subset is a cheap check, not a leaderboard result and not a stratified sample.

`./scripts/verify.sh` does not run this benchmark. It does not download the dataset, start Claude Code, start Docker, or call Anthropic.

## Dataset terms checked on Hugging Face

Checked **November 7, 2026**.

| Item | Finding |
| --- | --- |
| Dataset | [`SWE-bench/SWE-bench_Lite`](https://huggingface.co/datasets/SWE-bench/SWE-bench_Lite) |
| Card API | [`huggingface.co/api/datasets/SWE-bench/SWE-bench_Lite`](https://huggingface.co/api/datasets/SWE-bench/SWE-bench_Lite) |
| Card revision | `b0dde1093fe417d83b7184254edf8199c1f0dff5` |
| Card `lastModified` | `2026-08-16T04:19:26.000Z` |
| Visibility | Public. API fields `private: false`, `gated: false`, `disabled: false`. No access request is published on the card. |
| License field | **None.** `cardData` contains `dataset_info` and `configs` only. There is no `license` key. |
| License tag | **None.** The tag list has no `license:` tag. |
| License file | **None.** The dataset repo files are `.gitattributes`, `README.md`, `eval.yaml`, and the `data/*.parquet` splits. |
| README license section | **None.** The card describes the task, the 300-example `test` split, the 23-example `dev` split, and points at the SWE-bench leaderboard and arXiv:2310.06770. |
| What AIC does with it | Downloads the pinned `test` split at runtime through the harness environment. Does not vendor the parquet, issues, patches, or tests into this repository. |

The card does not grant a dataset license and does not relicense the upstream repository contents inside each instance (issue text, gold patches, and tests). Those repositories keep their own terms. AIC does not copy them into the package. The benchmark uses the public ungated card for its stated task, at the pinned revision, and leaves redistribution to that card's terms. If a later card adds a license or a gate, this pin is no longer a description of the new card.

The older mirror [`princeton-nlp/SWE-bench_Lite`](https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite) (card sha `6ec7bb89b9342f664a54a6e0a6ea6501d3437cc2`, also checked November 7, 2026) is public and ungated and also has no license field. Its published columns do not include the container fields (`image`, `eval_script`, `log_parser`, `eval_type`) that the pinned harness grades. This runner uses `SWE-bench/SWE-bench_Lite`.

## Harness license

Checked **November 7, 2026**.

The official harness is [SWE-bench/SWE-bench](https://github.com/SWE-bench/SWE-bench) at commit `02e7a74ffd0b707aab73d203fe87bdc7c76afc8e` (committed September 2, 2026). Its [`LICENSE`](https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/LICENSE) is the MIT License, copyright (c) 2023 Carlos E Jimenez, John Yang, Alexander Wettig, Shunyu Yao, Kexin Pei, Ofir Press, Karthik R Narasimhan. `pyproject.toml` at that commit classifies the project as OSI-approved MIT.

AIC does not copy harness source into this repository. The runner installs that exact commit into a virtualenv under the run cache when a benchmark starts. The MIT notice stays with that installation. MIT permits that separate use; AIC's Apache-2.0 grant does not relicense the harness. The root `NOTICE` is unchanged because no harness code is vendored here.

Scoring calls `python -m swebench.harness.run_evaluation` from that environment. It does not reimplement the grader.

## What each arm runs

Both arms use Claude Code print mode (`claude --bare -p`) with the same issue text, the same checkout of `base_commit`, and the same tool list. The issue text is passed as data. The prompt tells the agent not to edit tests to force a pass and not to fetch the upstream solution. Web and pull-request clients are not in the tool list, and `curl`, `wget`, `gh`, `ssh`, and `scp` are denied. A shell command can still reach the network another way; that limit is not a claim of isolation from the gold patch.

| Arm | Difference |
| --- | --- |
| `baseline` | `--bare` and no plugin directory. The prompt does not name AIC. |
| `aic` | `--bare` plus `--plugin-dir` set to this repository, and the prompt invokes `/aic:aic` before editing. Bare mode does not advertise discovered skills, so the skill is named explicitly. The prompt approves a fix in the working tree after the recommendation. This is explicit plugin use, not a claim of unaided native discovery. |

The prediction patch is `git diff` of the working tree after the process exits, including a timeout. It is not parsed out of the model's prose, and the gold patch is not given to the model. The dataset export keeps `instance_id`, `repo`, `base_commit`, and `problem_statement` only.

`model_name_or_path` is the arm label `claude-code-baseline` or `claude-code-aic`. It is not a resolve rate and it is not a substituted model id.

## Smoke subset

`--smoke` keeps the lexicographic first **10** `instance_id` values of the pinned test split after checking that the download contains **300** test instances. Fewer than 300 rows is a failed download and is not scored. The 10 instances are whatever sorts first at that revision (often one repository). Do not report that run as SWE-bench Lite.

## Run

Requirements: Python 3.11 or newer, `git`, Docker running locally, the `claude` executable on `PATH`, network access, and `ANTHROPIC_API_KEY`. The key is passed only to the Claude Code process. Git, pip, Docker, and the harness do not receive it.

From the repository root:

```bash
python -m benchmarks.swe_bench --output .work/swe-bench-lite --smoke
```

Omit `--smoke` to run the 300-instance test split. That is 600 Claude Code sessions when both arms run, plus the harness containers. Set a spend cap when you want one:

```bash
python -m benchmarks.swe_bench --output .work/swe-bench-lite --smoke --max-budget-usd 2.00
```

`--max-budget-usd` is forwarded to Claude Code. It is a client-side cap from Claude Code's own documentation, not a measured bill.

Useful flags:

| Flag | Behavior |
| --- | --- |
| `--condition baseline` or `--condition aic` | Run one arm. The default is `both`. |
| `--cache DIR` | Reuse the harness virtualenv and the downloaded public fields. The default is `OUTPUT/cache`. |
| `--max-workers N` | Harness workers. The default is 1. |
| `--max-turns N` | Claude Code turn cap. The default is 30. |
| `--model ID` | Forwarded as Claude Code `--model`. Omit it to use the CLI default. |
| `--score-only` | Score `baseline/predictions.jsonl` and/or `aic/predictions.jsonl` already in `--output`. Do not combine it with `--smoke`. |

Output and cache paths inside this repository are refused unless they are under `.work/<name>`, so a run cannot vendor the dataset into the package. Existing output directories are refused. Symlinks are refused.

Without `ANTHROPIC_API_KEY`, or when the variable is empty or whitespace, the process prints a refusal and exits **3**. It does not create the output directory, download the dataset, or write a score. `--help` still works without the key and does not write a result.

| Exit | Meaning |
| --- | --- |
| 0 | Every Claude Code process and every harness process exited 0. This is completion, not a resolve rate. |
| 1 | A generation or harness process failed. An official report may still be present. |
| 2 | The run was refused or a setup step failed. |
| 3 | No API key. Nothing was recorded. |

After a scored run, read:

```text
<output>/scores/<condition>/logs/evaluation/<condition>/results.json
```

The runner prints `resolved_instances` and `total_instances` only when that official file contains those integers. It does not compute a percentage.
