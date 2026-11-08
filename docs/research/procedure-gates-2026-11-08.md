# Procedure gates for a short coding turn budget

Checked **2026-11-08**. This note records two sources that are not in the 2026-11-07 harness ledger, and the product change they support. It does not copy paper prose, tables, prompts, or implementation source. AIC has not rerun Terminal-Bench or SWE-bench. A source-declared rate is not an AIC score and is not a score-history row.

The shared comparison stop is unchanged: `max_turns` 30, `timeout_sec` 600, `max_usd` 0.35, one model id, one seed. The stop is from `benchmarks/baselines/registry.json`. Nothing here raises that cap or changes a pinned baseline's install.

## Sources and rights

| Source | What was read | Rights on 2026-11-08 |
| --- | --- | --- |
| Terminal-Bench | Merrill, Shaw, Carlini, Li, Raj, Bercovich, and coauthors, *Terminal-Bench: Benchmarking Agents on Hard, Realistic Tasks in Command Line Interfaces*, arXiv:2601.11868, [HTML](https://arxiv.org/html/2601.11868). The abstract page displayed a **CC BY 4.0** badge. The ICLR 2026 proceedings PDF was not used as the text source. That badge is not assumed to be the proceedings' license. | Reference-only. No paper text is included. |
| mini-swe-agent | [SWE-agent/mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) `LICENSE.md` on the default branch: **MIT**, Copyright (c) 2025 Kilian A. Lieret and Carlos E. Jimenez. The design summary is from the repository overview, not from a function body. No source is included. | MIT notice applies to copies of the software. None is included. The repository states a SWE-bench Verified figure. This note does not repeat it and did not reproduce it. |

Competitor procedure shapes at the registry commits are in the 2026-11-08 section of [competitors-claude-skills.md](competitors-claude-skills.md). Those five repositories are MIT. Their skill text was not copied.

## What the sources support

Terminal-Bench 2.0 is 89 tasks. The paper says frontier models and agents resolve less than 65 percent of them. Its trajectory review groups failures into execution, coherence, and verification. Two verification labels matter for a coding skill: stopping before the required check has been shown, and treating a weak or substituted check as if it covered the behavior. A separate command-failure sample (3,800 failures) puts a missing executable first, at 24.1 percent of that sample. Those figures are the paper's. AIC did not re-annotate the trajectories. The judge-agreement rates in the paper are about the paper's labels, not about AIC's helper.

mini-swe-agent's overview describes a linear loop whose only action is a shell command, with history appended rather than summarized by an extra scaffold. The useful limit, next to the Terminal-Bench labels, is that extra ceremony is turns. AIC's comparison allows 30 turns. A second agent, a three-file plan, or a multi-phase verification ritual spends turns before the check that decides the task.

The 2026-11-07 ledger already records the editing mechanisms AIC kept: a capped search, a bounded view, a reproduction check that is not a hidden suite, and an undo when an edit adds a diagnostic. This cycle makes that loop the first procedure in the skill the benchmark prompt actually names, and it refuses a `passed` record whose exit codes do not match.

## What shipped

Original AIC wording in `skills/aic/SKILL.md`, `references/editing.md`, `references/workflows.md`, `references/templates.md`, and the schema-3 catalog purposes:

- One already approved behavior in one workspace binds `direct` / `solo` and runs the loop. A second write scope, a required separate evaluator, or durable continuity still uses the existing family table.
- The loop shows the check before the edit, edits a small region, undoes a new diagnostic, and reruns the same check.
- If the check cannot be started, the outcome is `blocked`. The skill does not say to install a tool or to repeat the same failure and call that progress.
- `passed` needs the after observation and an empty skipped-check list. Failure and new behavior need a nonzero before exit and an after exit of 0 on the same command. A refactor needs both exits to be 0. A documentation change needs an after exit of 0 and forbids a before/after pair whose exit code changed.
- `check-surface` validates that record. It does not run the command, does not read the workspace, and does not judge whether the observation sentence is true. A command that names an `oracle` or `reference` path, uses `..`, or is absolute is rejected.

The native plugin is still skills-only. No hook, no egress change, no sandbox change, and no second skill. Bare mode names `/aic:aic`; a skill the prompt does not name would not be the treatment.

## What this does not claim

Offline skill-lint, the routing scorer, aicbench oracles, and the suite stub do not call a model. They cannot show a SWE-bench or Terminal-Bench pass rate. The routing scorer has no deterministic router in this repository. Without `ANTHROPIC_API_KEY` it cannot score the dev pack, because a score needs a decision file from a run. `benchmarks/routing/heldout-v2.json` stays sealed. This change is not a release, so it was not scored.

The routing comparison prompt is the skill entry plus the files that entry links. It was already large before this change. Growing it is a cost, reported below, not a win. The loop was added to the entry the model is told to read, instead of as another linked essay.

## Offline measurements

These are not benchmark scores. The dev pack was not opened while the skill was edited. `benchmarks/routing/heldout-v2.json` was not opened. Sample sizes are the whole small fixtures these commands grade.

Skill documents are what `benchmarks.routing.compare.skill_documents` would attach to the AIC routing arm. The count is files. The bytes are UTF-8.

| Instrument | Command | Before | After |
| --- | --- | --- | --- |
| Skill-lint | `python3 -m benchmarks.skill_lint . --format json --summary` | mean 95.00, 1 skill, 0 errors, 1 `nested-reference` warning, format pass, 39 lines, 1471 instruction units | mean 95.00, 1 skill, 0 errors, 1 `nested-reference` warning, format pass, 54 lines, 2131 instruction units |
| Routing scorer | `python3 -m benchmarks.routing.score --from-router` | exit 2. No decision file and no router. No accuracy. | exit 2. Same message. No accuracy. |
| Skill documents in the routing prompt | `skill_documents` on the repo root | 14 files, 202842 bytes | 14 files, 207850 bytes (+5008) |
| aicbench oracles | `python3 -m unittest tests.test_aicbench_oracles tests.test_aicbench_catalog -q` | 4 tests, OK | 4 tests, OK, inside the full suite |
| Baseline stub | `python3 -m benchmarks.aicbench --baseline-stub` | `ok` true, 7 arms passed, `official` false, `public_benchmark_scores` null, `invokes_model` false, sample size 1 | same, rechecked by the suite |
| Suite stub | `python3 -m benchmarks.suite_arms stub` | `ok` true, `fetched` false, `public_benchmark_scores` null, `harness_loaded_aic` false, `aic_treatment` true only for `aic` | same, rechecked by the suite |
| Full offline suite | `python3 -m unittest discover -s tests -q` | not a separate before run | 506 tests, OK, 30 skipped |

The skill-lint mean did not move. The nested-reference warning is the existing reference graph. Removing those links to raise the mean would hide the contracts the entry already points at. The routing scorer cannot show a gain or a loss until a model writes a decision file. The +5008 bytes are a larger AIC routing prompt. That can hurt a later routing run. It is recorded here so it is not mistaken for a pass-rate gain.
