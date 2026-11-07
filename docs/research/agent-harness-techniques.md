# Techniques from coding-agent harnesses

Original AIC note, checked **2026-11-07**. It records techniques from SWE-agent, OpenHands, Aider, Agentless, Moatless Tools, and AutoCodeRover that come with a published score comparison, then maps each one onto AIC's existing workflow families. It does not change the skill catalog, templates, recommendation schema, or either NOTICE file.

No upstream source, prompt, figure, table image, or paper paragraph is included. Bibliographic facts and AIC's own wording are not a relicense of the cited papers, websites, or repositories. Adoption below is a proposal for a later approved task. A paper result is not permission to launch agents, spend inference budget, or treat a generated test as the user's acceptance suite.

## How a delta is counted

A technique is listed only when a primary source reports two outcomes that differ by that technique or by a stated bundle of techniques. The comparison, model, benchmark, and sample size are kept together. A later leaderboard cell is not treated as the effect of an earlier design choice.

Absolute change is in percentage points on the same metric. Where a paper also prints a relative figure that does not equal `(new − baseline) / baseline`, both the printed figure and the two rates are given, and the arithmetic is not silently replaced.

These are source-declared results. AIC has not rerun SWE-bench, HumanEvalFix, M³ToolEval, or Aider's Exercism benchmark.

## Sources, licenses, and what was read

Repository licenses were read from the listed commits before any implementation file was opened. Papers were read as the HTML or PDF named below. AutoCodeRover's current tree is not under a permissive license, so its behavior below is taken from the paper, and its source was not copied or paraphrased from implementation text.

| Source | Version checked | Rights evidence on 2026-11-07 |
| --- | --- | --- |
| SWE-agent paper | NeurIPS 2024 proceedings, Yang, Jimenez, Wettig, Lieret, Yao, Narasimhan, and Press, [proceedings PDF](https://proceedings.neurips.cc/paper_files/paper/2024/file/5a7c947568c1b1328ccc5230172e1e7c-Paper-Conference.pdf) | Proceedings copyright is the authors' grant to NeurIPS, not a general public Creative Commons license. The [arXiv:2405.15793](https://arxiv.org/abs/2405.15793) abstract page displayed a CC BY 4.0 badge. That badge is not treated as a license for the proceedings PDF. |
| SWE-agent code | [SWE-agent/SWE-agent](https://github.com/SWE-agent/SWE-agent) `3ea751c087f32b16e039a2233dd6eefecef325d5`, 2026-07-16 | [MIT](https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/LICENSE), Copyright (c) 2024 John Yang, Carlos E. Jimenez, Alexander Wettig, Shunyu Yao, Karthik Narasimhan, Ofir Press. The notice obligation applies to copies of the software. None is included here. |
| CodeAct paper | arXiv:2402.01030v4, updated 2024-06-07, Wang, Chen, Yuan, Zhang, Li, Peng, and Ji. The OpenHands paper cites this work as ICML 2024. The text read here is the [arXiv HTML](https://arxiv.org/html/2402.01030v4). | Abstract page displayed **CC BY 4.0**. The ICML proceedings PDF was not separately compared line by line. |
| OpenHands paper | arXiv:2407.16741v2, Wang, Li, Song, Xu, Tang, Zhuge, Pan, and coauthors, [HTML](https://arxiv.org/html/2407.16741v2) | Abstract page displayed **CC BY 4.0**. No conference version was verified for this text. |
| OpenHands code | Current [OpenHands/OpenHands](https://github.com/OpenHands/OpenHands) `c157abf3bdc1d795aadedb20c9862a2518e08806` is the Agent Canvas application and does not contain the CodeAct agent. The agent tools inspected are [OpenHands/software-agent-sdk](https://github.com/OpenHands/software-agent-sdk) `ff3a0b855d57eac804d66c4753843b36675ef677`, 2026-11-07, and [OpenHands/openhands-aci](https://github.com/OpenHands/openhands-aci) `a8d8d23ec635f9aaa94af17aec3c851656f10c8a`, 2026-03-24. | Both repositories are **MIT**. SDK copyright line: Copyright (c) 2026 OpenHands contributors. ACI copyright line: Copyright (c) 2025. No source is included. |
| Agentless paper | arXiv:2407.01489, Xia, Deng, Dunn, and Zhang, University of Illinois Urbana-Champaign, HTML updated on arXiv 2024-10-29, [HTML](https://arxiv.org/html/2407.01489) | Abstract page displayed **CC BY 4.0**. No peer-reviewed version of this text was verified. |
| Agentless code | [OpenAutoCoder/Agentless](https://github.com/OpenAutoCoder/Agentless) `5ce5888b9f149beaace393957a55ea8ee46c9f71`, 2024-12-22 | [MIT](https://github.com/OpenAutoCoder/Agentless/blob/5ce5888b9f149beaace393957a55ea8ee46c9f71/LICENSE), Copyright (c) 2024 OpenAutoCoder. |
| Aider benchmark post and data | Paul Gauthier, [Separating code reasoning and editing](https://aider.chat/2024/09/26/architect.html), 2024-09-26. Numeric rows were read from `aider/website/_data/architect.yml` in the repository below, not retyped from the chart. | The website's article license was **not** verified. The data file is in the Apache-2.0 repository. Article prose is not copied. |
| Aider code and benchmark definition | [Aider-AI/aider](https://github.com/Aider-AI/aider) `5dc9490bb35f9729ef2c95d00a19ccd30c26339c`, 2026-05-22. Benchmark description from the [benchmark notes](https://aider.chat/docs/benchmarks.html) as fetched the same day. | [Apache-2.0](https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/LICENSE.txt). `pyproject.toml` declares the OSI Apache classifier. The license appendix in that file was the standard Apache text. |
| Moatless Tools code | Albert Örwall, [aorwall/moatless-tools](https://github.com/aorwall/moatless-tools) `011ead57a5c81664e9c45e07e1f50b17e695cc63`, 2025-09-01 | [MIT](https://github.com/aorwall/moatless-tools/blob/011ead57a5c81664e9c45e07e1f50b17e695cc63/LICENSE), Copyright (c) 2024 Albert Örwall. |
| SWE-Search paper | Antoniades, Örwall, Zhang, Xie, Goyal, and Wang, *SWE-Search: Enhancing Software Agents with Monte Carlo Tree Search and Iterative Refinement*, **ICLR 2025**, [conference PDF](https://proceedings.iclr.cc/paper_files/paper/2025/file/a1e6783e4d739196cad3336f12d402bf-Paper-Conference.pdf). The author line in the PDF rendering splits the second author's name; the MIT license of Moatless Tools spells it Albert Örwall. | A public reuse grant for the **conference PDF** was not verified. [arXiv:2410.20285](https://arxiv.org/abs/2410.20285) displayed **CC BY-SA 4.0**. That badge does not license the conference PDF. Numbers below are from the conference PDF. |
| SWE-Search code | [aorwall/moatless-tree-search](https://github.com/aorwall/moatless-tree-search) `bc66ea64e3fe96cf3c90f197b4bab9aaa15e1eb9`, 2025-01-13 | **Apache-2.0**. The repository says it reproduces the paper. It was not copied. |
| AutoCodeRover paper | Zhang, Ruan, Fan, and Roychoudhury, *AutoCodeRover: Autonomous Program Improvement*, **ISSTA 2024**, DOI [10.1145/3650212.3680384](https://doi.org/10.1145/3650212.3680384). Text read: [arXiv HTML](https://arxiv.org/html/2404.05427), which carries the ISSTA proceedings header. | [arXiv:2404.05427](https://arxiv.org/abs/2404.05427) displayed **CC BY 4.0**. That is not assumed to be the ACM proceedings' license. |
| AutoCodeRover code | [AutoCodeRoverSG/auto-code-rover](https://github.com/AutoCodeRoverSG/auto-code-rover) `585d3e639aeda58ef0b6a151dd1cc2721a94d267` (GitHub redirects `nus-apr/auto-code-rover` here) | **Sonar Source-Available License v1.0**, last updated 2024-11-13, as the LICENSE file at that commit. This is not a permissive grant and is incompatible with copying the implementation into AIC. Only the license and the top-level directory names `app/search` and `app/analysis` were inspected. Mechanism details come from the paper. |
| SpecRover paper | Ruan, Zhang, and Roychoudhury, *SpecRover: Code Intent Extraction via LLMs*, arXiv:2408.02232v3, [HTML](https://arxiv.org/html/2408.02232v3) | Abstract page displayed **CC BY 4.0**. Included only to mark where a follow-up system score is not an isolated technique effect. |

Implementation files actually opened, all under the permissive commits above: SWE-agent `tools/windowed/config.yaml`, `tools/windowed/lib/flake8_utils.py`, and the `tools/windowed_edit_linting/` bundle; Agentless `agentless/fl/localize.py`, `agentless/fl/retrieve.py`, `agentless/repair/rerank.py`, and `agentless/test/generate_reproduction_tests.py`; Aider `aider/repomap.py`, `aider/coders/architect_coder.py`, and `benchmark/benchmark.py`; Moatless `moatless/index/code_index.py`; OpenHands SDK `openhands-tools/openhands/tools/preset/default.py` and the file-editor and terminal tool packages. Symbols and control flow were used to check the papers. No function body is reproduced.

## 1. Test-filtered majority vote over sampled patches

**What it is.** Agentless draws several candidate patches, runs tests the repository already passed, asks the model which of those tests would be invalidated by a correct fix, and keeps patches with the fewest remaining failures. It also samples a separate test file that must print a fixed reproduction message on the unmodified tree before it is allowed to vote. Patches that fail that selected test are dropped. If every patch fails it, selection falls back to the regression filter. The surviving normalized diffs are then majority-voted, with the earliest sample breaking ties. The implementation of that order is `majority_voting` in `agentless/repair/rerank.py` at the commit above: regression equality with the minimum failure count, then the reproduction flag, then the regression-only fallback, then the vote.

**Reported delta.** Agentless Table 4, SWE-bench Lite, 300 instances, GPT-4o (`gpt-4o-2024-05-13`), one submitted patch per instance:

| Selection | Resolved | Added cost in the table |
| --- | ---: | ---: |
| Majority voting only | 77 (25.67%) | $0.00 |
| Plus regression filter | 81 (27.00%) | $0.01 |
| Plus reproduction filter | 96 (32.00%) | $0.25 |

The reproduction stage is the largest single step in that table: 81 to 96, **+15 instances, +5.00 percentage points**. From majority voting alone to the full rule: 77 to 96, **+19 instances, +6.33 percentage points**. The paper's repair curve says one greedy sample on each of four location sets already resolves 80, and the submitted score plateaus near 40 samples. Counting a success if any sample would have passed, rather than the one submitted patch, reaches 126 (42.0%). That 42.0% figure is an upper bound on this candidate pool, not a pass@1 result.

**Limits.** Of 300 Lite instances, 213 generated tests printed the reproduction message on the original repository. Only 94 of those also printed the resolved message after the developer patch was applied, and that developer patch was used only for this quality check. The filter can therefore prefer a wrong patch. The paper's fallback when no candidate passes the generated test is part of the measured system. The $0.25 is their reported average extra inference cost for generating tests, not an AIC measurement. The same table does not separate a better test from a luckier vote.

**AIC adoption.** This fits `implementation` or `debug` when several concrete patches already exist, and `independent-review` when a separate owner selects among them. Give the selector the issue, the patches, and the test outcomes. Omit the generator's explanation. Keep the user's acceptance tests out of the ranking loop. Pre-existing passing tests may be used only after the owner marks which behaviors a correct fix is allowed to change. If the generated test rejects every candidate, fall back and say so. Sampling more than one patch is an `adaptive-controller` measured-optimization step only when the user has already authorized the extra model calls, a baseline, and a stop count. Forty samples is the paper's observed plateau for this pipeline, not an AIC default.

## 2. A small editing and search interface, with lint rejecting bad edits

**What it is.** SWE-agent replaces unrestricted shell editing with a file viewer that shows a window of at most 100 lines, commands that move that window, a search that returns a capped summary instead of every match, and one edit command whose line numbers refer to the open window. A Python edit is kept only when lint does not report a new error; otherwise the edit is undone and the diagnostic is shown. The proceedings describe this guard as catching syntax errors. At the 2026 commit, `tools/windowed_edit_linting/bin/edit` still runs flake8 before and after the replacement and calls the editor undo when the comparison reports new findings. History keeps the last five observations rather than every earlier dump. The same commit's `tools/windowed/` config still exposes `open`, `goto`, `scroll_up`, and `scroll_down`. The evaluated 100-line width is the proceedings' setting. The current config parameterizes the width as `{WINDOW}` and this note does not claim the default is still 100.

**Reported delta.** NeurIPS 2024 Table 1 and Table 3. Model: GPT-4 Turbo (`gpt-4-1106-preview`). Ablations are SWE-bench Lite, 300 instances, one run each. The full SWE-bench test set is 2,294 instances. Resolved means the submitted patch passes the benchmark tests. Average cost is over resolved instances, with a $4 per-instance cap.

| Comparison | Resolved | Absolute change |
| --- | ---: | ---: |
| Shell-only, Lite | 11.00% (cost $1.46) | baseline for the interface package |
| SWE-agent, Lite | 18.00% (54/300, cost $1.67) | **+7.00 percentage points**. The paper also states a 64% relative increase against this shell-only row. |
| Shell-only without the demonstration, Lite | 7.33% | The introduction's "10.7 percentage points" matches 18.00 − 7.33, not 18.00 − 11.00. |
| SWE-agent without the demonstration, Lite | 16.3% | −1.7 points versus 18.0 |
| Edit with linting | 18.0% | reference row of Table 3 |
| Edit action without linting | 15.0% | **−3.0 points** |
| No dedicated edit command | 10.3% | **−7.7 points** |
| Summarized search | 18.0% | reference row |
| No specialized search | 15.7% | −2.3 points |
| Iterative, one-match-at-a-time search | 12.0% | **−6.0 points**, and worse than having no specialized search |
| 100-line window | 18.0% | reference row |
| 30-line window | 14.3% | −3.7 points |
| Full file in view | 12.7% | −5.3 points |
| Last five observations | 18.0% | reference row |
| Full observation history | 15.0% | −3.0 points |

On the full test set, SWE-agent with GPT-4 Turbo resolves 12.47% (286/2,294) at $1.59 average cost on successes. The shell-only agent was not run on the full set. RAG with the same model resolves 1.31% full and 2.67% Lite. The Lite SWE-agent rate is 18.00 / 2.67 ≈ 6.7 times the RAG rate and, as the paper says, about 8–13 times the RAG cost. Claude 3 Opus under the same ACI resolves 10.46% full and 13.00% Lite, so the interface transferred, at a lower rate.

HumanEvalFix Table 2, pass@1, SWE-agent with GPT-4 Turbo: Python 87.7, JavaScript 89.7, Java 87.9. The results prose says 88.3% pass@1. Those are not the same figure. This note uses the three table cells. HumanEvalFix has no interface ablation in the tables above, so it is transfer evidence for the whole system, not a per-component delta.

**Limits.** Table 3 differences are single runs on 300 instances. The paper does not report a significance test for them. The hyperparameter sweep used a 37-instance development split. Per-instance outcomes move across repeats even when the average is stable, which the paper's pass@k plot shows. Removing the editor also removes the viewer feedback that the edit command uses, so the −7.7 point row is the editor-and-viewer bundle, not a one-line lint flag. Iterative search is a useful negative result: an interface copied from an editor's match list lowered the score.

**AIC adoption.** For a `direct` / `solo` edit, the host should search with a summarized, capped result; open a bounded window instead of an entire large file; apply a multi-line edit against visible line numbers; show the updated window; and discard an edit that introduces a syntax or lint error, returning the diagnostic. Keep the recent observation, not the whole scrollback. Do not add an AIC shell or a second agent to obtain this. The iterative-search result is a reason to avoid paging every hit. `independent-review` still checks the user's acceptance criteria after the edit. A linter failure is evidence of a bad edit, not evidence that the issue is fixed.

## 3. Executable code as the action, versus text or JSON tool calls

**What it is.** CodeAct has the model emit Python that may call tools, branch, and loop, then returns the interpreter's output, including errors, on the next turn. The comparison holds the model fixed and changes only the action format. OpenHands' 2024 agent is this CodeAct agent inside a general platform that also has a shell and a browser. The 2026 SDK's default preset registers a terminal tool, a file editor, a task tracker, and optionally a browser and a task-delegation tool. That preset is a later interface. It is not the system that produced the M³ToolEval numbers.

**Reported delta.** CodeAct Table 3, M³ToolEval, 82 human-curated tasks that need several tools over several turns, success by exact match to the reference answer, at most 10 turns.

The claude-2 row is intact in the HTML table:

| Format | Success | Average turns |
| --- | ---: | ---: |
| CodeAct | 54.9% | 7.2 |
| JSON | 39.0% | 8.3 |
| Text | 29.3% | 8.5 |

CodeAct minus JSON is **+15.9 percentage points**. CodeAct minus text is **+25.6 percentage points**. The abstract's phrase "up to a 20% absolute improvement" is smaller than this text comparison. The results prose separately states that `gpt-4-1106-preview` reaches 74.4% with CodeAct, **20.7 percentage points** above its next-best format (text), with **2.1 fewer turns** on average. The converted HTML did not preserve a clean JSON cell for that model, so no JSON number is stated for it. Twelve of seventeen models had a higher success rate with CodeAct, and twelve of seventeen used fewer turns. The best open model in that discussion reaches 13.4%, against 74.4% for this GPT-4 snapshot.

OpenHands Table 4, SWE-bench Lite, 300 instances, no hint text, CodeActAgent v1.8: Claude 3.5 Sonnet (`claude-3-5-sonnet@20240620`) 26.0% at $1.10 average cost; `gpt-4o-2024-05-13` 22.0% at $1.72; `gpt-4o-mini-2024-07-18` 7.0% at $0.01. There is no text-versus-code ablation on SWE-bench in that table. A later CodeAct 2.1 submission changed function calling, directory traversal, and the Claude snapshot together. Its higher SWE-bench rates are not an isolated format effect and are not used here.

**Limits.** M³ToolEval is tool composition with an exact answer, not a repository patch that must pass a hidden suite. The OpenHands Lite number shows that a CodeAct agent can be competitive on SWE-bench Lite under one 2024 model snapshot. It does not say the Python action format caused the difference from SWE-agent's 18.00%, because the model and the rest of the harness also differ. Interpreter actions are a broader capability than a lint-gated editor. SWE-agent's shell-only result is the warning against treating "just run code" as the whole interface.

**AIC adoption.** On `direct` work, a host that can run code may bundle a check, a parse of its output, and a follow-up into one action when the alternative is one rigid call per step. File modification still wants the guarded edit from the previous section, because the shell-only editor lost 7.7 points on Lite. Code execution stays inside the user's existing approval and command boundary. AIC does not gain a code-execution tool from this note. `independent-review` should see the command output, not a paraphrase of it, before accepting a fix.

## 4. Search over repair trajectories, with a separate selector

**What it is.** SWE-Search runs the Moatless agent as a tree. A node can expand into planning, searching, editing, or testing. A value model scores a node with both a number and a short critique. That critique is fed back when the node is expanded again. A discriminator then debates among up to five finished patches and picks one. The Moatless base agent, in `moatless/index/code_index.py`, searches a vector index of parsed code blocks, can require an exact string, ranks spans under a token budget, and can also look up a class or function by name. SWE-Search's own comparison does not remove that index. It compares search against the same adapted agent.

**Reported delta.** ICLR 2025 Table 1, SWE-bench Lite, 300 instances, resolve rate of the selected patch. Moatless-Adapted is moatless-tools v0.0.2 plus flexible transitions, a tree of states, and the ability to run tests. Fail-to-pass tests are not given to the agent. The paper caps expansions at three per node and iterations at 100.

| Model | Moatless v0.0.2 | Moatless-Adapted | SWE-Search | Printed ∆ % |
| --- | ---: | ---: | ---: | ---: |
| GPT-4o | 24.3 | 25.7 | 31.0 | +17 |
| GPT-4o-mini | — | 13.0 | 17.0 | +24 |
| Qwen-2.5-72B-Instruct | — | 18.0 | 24.7 | +27 |
| DeepSeek-V2.5 | — | 16.3 | 21.0 | +22 |
| Llama-3.1-70B-Instruct | — | 13.6 | 17.7 | +23 |

Every model improves. For GPT-4o the absolute change from Moatless-Adapted to SWE-Search is 31.0 − 25.7 = **+5.3 percentage points**. The printed ∆ column is the paper's column. It is not equal to `(SWE-Search − Moatless-Adapted) / Moatless-Adapted`. For GPT-4o that usual relative change would be 5.3 / 25.7 ≈ 21%, while the paper prints +17 and calls the five-model mean +23%. This note uses the resolve rates. Flexible transitions alone, v0.0.2 at 24.3 versus Adapted at 25.7, are **+1.4 percentage points** on GPT-4o. The paper describes that gap as modest and says unconstrained transitions can loop.

Pass@1 versus Pass@5 for the SWE-Search agent, same table block: GPT-4o 31.0 and 34.0; GPT-4o-mini 17.0 and 22.3; Qwen-2.5-72B-Instruct 24.7 and 25.7. Pass@5 means a correct patch appeared within five attempts. It is not the rate of the one patch the discriminator submitted. The value function picked the correct finished solution 73% of the time on average across the five models, and the discriminator 84%, in the cases where a correct solution was among the candidates. That is selection accuracy given a correct candidate, not an additional resolve-rate delta.

**Limits.** The search spends many more model calls than the linear agent. The paper does not claim a matched token budget. One hundred iterations was a feasibility cap, not an optimum. The 73% and 84% figures apply when a resolving patch is already in the pool. Agentless Table 1, a different snapshot, lists Moatless at 26.67% (80/300) with Claude 3.5 Sonnet and 24.67% (74/300) with GPT-4o. Those cells are not the v0.0.2 row above. No ablation that turns off Moatless' vector index was found in the paper or the inspected index module, so semantic search is a documented localization mechanism here, not a measured score change.

**AIC adoption.** Tree search belongs to `adaptive-controller` only for an explicitly scoped optimization: a correct baseline, an oracle that is not the hidden acceptance suite, comparable measurements, and a user-approved call budget. The +1.4 point flexibility result is a reason to keep stage order unless search is there to stop loops. The discriminator maps to `independent-review` if the reviewer receives the candidates, the issue, and the test outcomes, and does not receive each generator's argument for its own patch. A debate among copies of one model is still one model. Do not add a vector index or an embedding provider to AIC. If the host already has code search, the owner can use it inside `direct` or `explore-build` and record that the score effect of that index was not isolated.

## 5. Hierarchical localization, then separate repair contexts

**What it is.** Agentless localizes in three stages and only then samples patches. File candidates come from the repository tree plus an embedding retrieval over chunks that remain after the model names folders to ignore. The next stage sees a skeleton of headers, signatures, fields, and class or module comments, not the whole file. The last stage names edit spans. Four sampled span sets are repaired separately, ten patches each, instead of being merged into one large context. `localize.py` implements the file, related-element, and edit-location stages in that order. `retrieve.py` is the embedding retrieval.

**Reported delta.** Agentless Table 2, SWE-bench Lite, 300 instances, GPT-4o. "Contains GT" means the ground-truth edited locations are still inside the candidate set. It is not the resolve rate.

| Stage | Setting | Contains ground truth | Lines of code | Average cost |
| --- | --- | ---: | ---: | ---: |
| File | Prompting on the tree | 78.67% | 3,221 | $0.02 |
| File | Embedding, no folder filter | 67.67% | 3,388 | $0.05 |
| File | Embedding, folder filter | 70.33% | 3,622 | $0.04 |
| File | Prompting and embedding combined | 81.67% | 3,424 | $0.06 |
| Elements | Entire file contents | 53.67% | 778 | $0.15 |
| Elements | Skeleton | 58.33% | 698 | $0.02 |
| Edit spans | Greedy, after the element stage | 50.67% | 189 | $0.06 |
| Edit spans | Straight from files, skipping elements | 47.00% | 208 | $0.18 |
| Edit spans | Several samples merged | 56.33% | 342 | $0.07 |
| Edit spans | Several samples kept separate | 49.67% | 165 | $0.07 |

Combining prompting and embeddings raises file coverage from 78.67% to 81.67%, **+3.00 percentage points** of files, at $0.06 rather than $0.02. The skeleton raises element coverage from 53.67% to 58.33% and drops that stage's cost from $0.15 to $0.02. Skipping the element stage loses 3.67 points of span coverage and costs more.

Agentless Table 3 is the resolve-rate consequence of how those spans are repaired, again 300 instances:

| Repair input | Resolved | Repair cost |
| --- | ---: | ---: |
| One greedy location set, 40 patch samples | 88 (29.33%) | $0.22 |
| Merged multi-sample locations, 40 samples | 85 (28.33%) | $0.24 |
| Four location sets, 10 samples each | 96 (32.00%) | $0.29 |

Keeping the four location sets separate is **+8 instances, +2.67 percentage points** versus the greedy location set, and **+11 instances** versus merging the samples. Merging raised "contains ground truth" and lowered the number of fixes. The paper's explanation is that each set stays small enough for the repair prompt.

Submitted Agentless patches, Table 1, touch the developer line in 35.3% of instances, the developer function in 52.0%, and the developer file in 69.7%. Those are properties of the one submitted patch. They are lower than the localization-stage coverage numbers because a covered file is not yet a correct patch.

**Limits.** Coverage of the developer location is not required for a correct fix, and a covered location is not a fix. The embedding half uses `text-embedding-3-small` through LlamaIndex, chunk size 512, which is an extra model call AIC does not require. Prompting alone already holds 78.67% of ground-truth files. The +8 fix comparison spends $0.29 rather than $0.22 and uses the same downstream test filter, so part of the gain is interaction with section 1, not localization alone.

**AIC adoption.** `explore-build` can assign independent questions to separate files or symbols, then one owner narrows to skeletons and edit spans before any write. Do not paste every suspicious file into one context, and do not merge competing location hypotheses into one prompt when they can be repaired or inspected separately. The skeleton step is available with the host's existing read tools. An embedding index is optional host machinery, not a new AIC dependency. `direct` is enough when the issue already names the file. Localization coverage is an intermediate observation. Acceptance remains the user's tests and review.

## 6. Split proposing a change from formatting the edit

**What it is.** Aider's architect mode asks one model to describe the solution and a second coder, which may be the same model, to turn that description into file edits. In `architect_coder.py` the editor is a new coder with the editor model and editor format, an empty message history, and a repository-map budget of zero. The map itself, in `repomap.py`, extracts symbols with tree-sitter and ranks files with NetworkX PageRank on a definition and reference graph, with extra weight for files already in the chat and for names the conversation mentions, then fits the map to a token budget. No run that disables only the map was found in the benchmark data or the September 2024 post, so the map is not given a score delta.

**Reported delta.** Aider's code-editing benchmark is 133 Exercism Python exercises. `benchmark/benchmark.py` defines `pass_rate_1` as the fraction passing after the first try and `pass_rate_2` as the fraction passing after the second, and the default try count is 2. The architect post's pass-rate column matches `pass_rate_2` in `architect.yml`.

Least confounded same-model pair, both using the diff edit format:

| Run | Commit and date in the data file | After 1 try | After 2 tries |
| --- | --- | ---: | ---: |
| GPT-4o alone | `89aa385-dirty`, 2024-09-26, aider 0.57.2.dev | 55.6% | 71.4% |
| GPT-4o architect with GPT-4o editor | `9f3cd92`, 2024-09-25, aider 0.57.2.dev | 56.4% | 75.2% |

After two tries the split is **+3.8 percentage points**. After one try it is **+0.8 percentage points**. The commits are one day apart and are not the same revision.

The post's 85.0% row is o1-preview as architect with o1-mini as editor, whole-file format, `pass_rate_2` 85.0 and `pass_rate_1` 65.4, commit `53ca83b`, 2024-09-29. The o1-preview solo diff row in the same file is `pass_rate_2` 79.7 and `pass_rate_1` 57.9, commit `5493654-dirty`, 2024-09-21, with 93.2% well-formed edits. That comparison changes the editor model, the edit format, and the aider revision together. It is the published headline, and it is not a same-model format ablation.

Claude 3.5 Sonnet paired with itself scores `pass_rate_2` 80.5 on 2024-09-25 (aider 0.57.2.dev) against a solo diff baseline of 77.4 on 2024-07-04 (aider 0.42.1-dev). The version gap makes that pair weaker evidence than the GPT-4o pair.

**Limits.** These are short Python exercises with a stub and unit tests, not SWE-bench repositories. Two tries mean the second-try rate includes a repair attempt after a failure. Aider's SWE-bench Lite leaderboard figure of 26.33% (79/300) in the Agentless table uses GPT-4o and Claude together in a retry harness. It is a system score, not the effect of the architect split or of the repository map.

**AIC adoption.** When a model solves the task and then fails the edit format, a sequential `coordinated-delivery` step, or a second step by the same `direct` owner, can ask for a description first and a formatted edit second. The same-model first-try gain on this benchmark is under one point, so the split is a response to a format failure, not a default team. The editor should not also receive a second copy of the whole repository map. AIC does not vendor tree-sitter or PageRank. If the host already ranks symbols, the owner can request a token-budgeted map as selected context and should not claim a measured resolve-rate gain for it.

## 7. Structure search, and spectrum ranking only with tests that already exist

**What it is.** AutoCodeRover retrieves context by searching the abstract syntax tree for classes, methods, and snippets named in the issue, through a small set of search calls, then writes a patch. When a test suite exists, the ISSTA paper adds method-level spectrum-based fault localization: the top suspicious methods are shown to the retrieval agent as hints from an external analysis, and a failed validation run sends the agent back to write another patch, up to three times. The suspiciousness formulas named in the paper are Tarantula and Ochiai. The current AutoCodeRover repository was not used to recover those formulas or the API implementations.

**Reported delta.** ISSTA 2024 Table 2, SWE-bench Lite, 300 instances, pass@1 is the fraction resolved by one run. The paper repeated the base experiment three times.

| Setting | Resolved | Time | Tokens (reported cost) |
| --- | ---: | ---: | ---: |
| AutoCodeRover @1 | 19.00% (57) | 195 s | 37k ($0.43) |
| AutoCodeRover @3 | 26.00% (78) | 520 s | 112k ($1.30) |
| ACR with SBFL hints and test-suite retry | 22.00% (66) | 250 s | 40k ($0.47) |

@1 to the SBFL-plus-validation setting is 57 to 66, **+9 instances, +3.00 percentage points**. The paper's prose attributes the increase to the SBFL hints. The method section adds both the hints and the three-try validation loop in the same setting, and this note does not split them further because the paper does not. @3 is the fraction of instances solved by at least one of three independent runs. It is not the resolve rate of a single selected patch. On the full 2,294-instance set, @1 is 12.42% (285) and @3 is 17.96% (422).

The paper says ACR with this extra analysis still uniquely resolves 7 Lite instances that the other AutoCodeRover runs did not. Manual review of plausible Lite patches across the three base runs found 51 of 78 semantically equivalent to the developer patch, 65.4%. The other overfitting patches mostly edited the same methods as the developer patch.

**Limits.** The test suite in the SBFL setting is the developer-written suite shipped with each SWE-bench Lite instance. The paper says so. Those tests include tests written to accompany the fix. A +3 point gain measured with the benchmark's own fail-to-pass tests is not evidence that spectrum ranking helps when the only tests available are the ones that already passed before the issue. Using the hidden acceptance tests as a localization signal would invalidate the benchmark comparison and is outside AIC's acceptance rule. The base 19% versus SWE-agent's 18% compares GPT-4 with GPT-4 Turbo and two harnesses. It is not a technique effect.

**AIC adoption.** For `direct` or `debug` localization, prefer a search by class, method, and caller over reading the repository as flat files, using the host's existing code navigation. That part does not need the SBFL number. Spectrum ranking is eligible only when a failing test already exists in the project and was not written from the hidden acceptance suite. Show the owner the suspicious methods as hints, and still require the issue text to agree before editing. A validation retry is bounded, three in the paper, and stops when the authorized tests pass or the bound is hit. Do not import AutoCodeRover's retry, reset, or experiment runner. The source-available license blocks copying that implementation regardless.

## Scores that are not isolated technique effects

These numbers appear in the same papers and are easy to misread as ablation results.

- SpecRover reports 31.00% (93/300) on SWE-bench Lite and 19.31% (443/2,294) on full SWE-bench, using Claude 3.5 Sonnet and GPT-4o when the first API errors. AutoCodeRover's 19% Lite result used GPT-4. The model and the added reviewer, function summaries, and generated tests all change at once. The paper does not remove the reviewer or the function summary and rerun. On 119 Lite tasks where a reproduction test was produced, the reviewer's decision matched actual patch correctness on 64.7% (26 true positives and 51 true negatives in the paper's count), and precision among patches the reviewer called correct was 50.0%. That precision is not a resolve-rate delta.
- Agentless' 32.00% (96/300) and 38.80% (194/500) on SWE-bench Verified are system scores against other agents that often use different models. The within-system deltas are Tables 2–4, not the leaderboard gap.
- SWE-agent's 12.47% full-set result is the whole ACI with GPT-4 Turbo. The shell comparison was Lite-only.
- OpenHands CodeAct 2.1's later SWE-bench Verified announcement changes the model and several harness details together. It is not listed as a technique delta.
- Aider's repository map, Moatless' vector index, and OpenHands' 2026 file-editor-plus-terminal preset are implemented mechanisms whose isolated benchmark deltas were not in the sources read for this note.

## What would make an adoption real

A later change to a workflow family would name the family, the acceptance check, the budget, and a comparison on the user's task. The comparisons above use SWE-bench Lite or Verified, the full SWE-bench test set, HumanEvalFix, M³ToolEval, or 133 Exercism exercises, with the models named in each table. None of them is an AIC measurement, a ranking of current hosts, or a reason to add a team, an embedding service, a search tree, or a code executor by default.

The five comparisons with the strongest within-system evidence are the reproduction filter in Agentless Table 4 (+15 instances after regression filtering, +19 from majority voting alone), the SWE-agent editor ablation (−7.7 points without the dedicated editor, +7.0 points for the ACI against the shell on Lite), CodeAct's format comparison on M³ToolEval (claude-2 +15.9 points versus JSON and +25.6 versus text; GPT-4 Turbo +20.7 points versus text, on a benchmark that is not repository repair), SWE-Search's gain on all five models (GPT-4o +5.3 points, at much higher search depth), and Agentless' decision to repair four location sets separately (+8 instances versus one greedy location set). Aider's same-model architect split and AutoCodeRover's SBFL setting are real published comparisons and are weaker evidence for the reasons in sections 6 and 7.
