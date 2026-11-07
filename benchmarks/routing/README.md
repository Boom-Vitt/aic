# Routing scorer

Offline comparison of routing decisions with a routing pack. The default pack is the dev pack at `tests/fixtures/routing-scenarios.json`. The release pack is `benchmarks/routing/heldout-v2.json`. The scorer does not read request text to choose a workflow, and it does not call a model, a network API, or a cloud service. A number appears only after you point it at a decision file from a real run. This document has no results table.

Each pack's own `limits` text still applies: the expected fields and stage labels are evaluation data, not a production classifier, and they stay withheld from fresh host inputs.

## Pack roles

Tuning happens only on the dev pack, `tests/fixtures/routing-scenarios.json`. Its doc role is `dev`. Do not read it when editing `skills/aic`.

`benchmarks/routing/heldout-v2.json` is scored once per release. Do not tune the skill against it, and do not read it when editing `skills/aic`. `benchmarks/routing/heldout-v2-answers.json` holds one rationale for each label. The scorer does not read that file, and it is not model input.

`--scenarios` and `--pack` select the same kind of schema-3 pack. Pass only one. Omitting both uses the dev pack. A byte change to heldout-v2 or its answers requires a new `pack_version` and a new row in the lock below. Do not replace the digest of a version that has already been published.

## heldout-v2 lock

| pack_version | file | sha256 |
| --- | --- | --- |
| 1 | `benchmarks/routing/heldout-v2.json` | `e26c69eb2b81e4536dea8e4aab59d798b6a1381c9ba9fde3598ee275590f0479` |
| 1 | `benchmarks/routing/heldout-v2-answers.json` | `bbd33ad04bdee9ee25c1ca5280036553a8b84ca06d45aae5e45fc5739b03d9e6` |

## Commands

From the repository root:

```sh
python -m benchmarks.routing.score --decisions decisions.jsonl
python -m benchmarks.routing.score --decisions decisions.jsonl --output report.json
python -m benchmarks.routing.score --decisions decisions.jsonl --pack benchmarks/routing/heldout-v2.json
python -m benchmarks.routing.baseline --output prompts.jsonl
python -m benchmarks.routing.compare --model MODEL_ID --output comparison-dir
python -m benchmarks.routing.compare --model MODEL_ID --output comparison-dir --pack benchmarks/routing/heldout-v2.json
```

`--scenarios` or `--pack` replaces the default dev pack. The replacement must use schema version 3. `--output` creates a new file and refuses a path that already exists or is a symlink. Decision, scenario, catalog, and output paths are not followed when the final component is a symlink.

`--help` works with no model credential. Scoring does not read `ANTHROPIC_API_KEY`.

## Decision file

UTF-8 JSONL, one JSON object per line. Blank lines are ignored. Each object needs an `id` that matches a pack case, or that pack's project case id, exactly once. The dev pack's project id is `mixed-project-plan`. The release pack's project id is `h2-library-hold-plan`.

Flat cases supply `workflow`, `template`, and `topology`. Those three strings may sit on the object or one level down under `recommendation`, `decision`, `plan`, or `structured_output`. If more than one of those places sets the same field, the strings must be identical. JSON `null`, or a missing field, is an abstention. An abstention is not a predicted class.

```json
{"id": "example-only", "workflow": "answer", "template": "direct", "topology": "solo"}
```

That line is a format example. `example-only` is not a pack id, and the line is not a measured run.

The project case is not one triple. Its decision object uses:

- `stages`: objects with `id`, `workflow`, `template`, and `topology`. Stage ids must belong to the pack. Labels may use the same nesting as a flat case.
- `milestones`: the decision's milestone strings.
- `invariants`: the decision's invariant strings.

Comparison of milestones and invariants is set equality with the pack's `required_milestones` and `required_invariants`. Order does not matter. A missing key is an unanswered check. Duplicate strings in a supplied list are a file error.

Unknown ids, duplicate ids, conflicting labels, and malformed JSON stop the process with no report. A pack case that simply has no row is scored as unanswered.

## What is correct

A flat case is correct on a field when the predicted string equals the pack's `expected_workflow`, `expected_template`, or `expected_topology`. Exact correctness requires all three. Comparison is case-sensitive and does not trim an already-accepted string; surrounding space is a file error rather than a second spelling.

The project case is correct on a stage by the same field rules. Its milestone check and invariant check are separate booleans. Stage rows are not added to the flat-case denominator. Flat-case metrics do not include the project case, and project metrics do not include the flat cases.

The report lists every flat case in pack order, with the expected labels, the predicted labels, and the four booleans. It does not copy request text. The project section lists every stage the same way, plus the milestone and invariant differences.

## Precision, recall, and accuracy

Each population is single-label. A population is the flat cases, or the project stages, and a label is one field or the exact triple.

- Accuracy is the number of gold items predicted correctly, divided by the number of gold items. An abstention or a missing row is incorrect.
- Recall uses the same numerator and the same denominator. Every gold item is a recall trial.
- Precision uses the same numerator and divides by the number of items that made a prediction. An abstention is not a precision trial. If nothing was predicted, precision has no rate and no interval.

These are micro-averages. When every item has a prediction, the three proportions are the same count. The report still records them separately so a file with abstentions does not hide which denominator moved.

Per-class precision and recall are also in the report, for each gold label in that population. A predicted string that is not a gold label does not gain its own class row. It still counts in the micro denominator as a prediction that was not a true positive. A class with no predictions has no precision interval. This scorer does not publish a macro average, because that average is not one binomial proportion and this tool will not invent an interval for it.

The exact triple is one label. If any of the three fields is missing, there is no exact prediction.

## Wilson interval

For `k` successes in `n` trials, with `n > 0` and sample proportion `p = k / n`:

```text
z = statistics.NormalDist().inv_cdf(0.975)
center = p + z^2 / (2n)
margin = z * sqrt(p(1-p)/n + z^2 / (4n^2))
bound = (center ± margin) / (1 + z^2 / n)
```

`z` is the 0.975 quantile of the standard normal, not a rounded substitute. Bounds are clipped to `[0, 1]`. When `k` is 0 the lower bound is reported as 0, and when `k` is `n` the upper bound is reported as 1, so binary noise at those edges is not a second interval. `n = 0` yields a null rate and a null interval. The method is the Wilson score interval (Wilson, 1927). No continuity correction is added.

The report's `rate` is `k / n` as an IEEE float. `k` and `n` are the integers to cite. A saved report describes the file you scored. It is not, by itself, a published model comparison: the same model, budget, seed, and pack revision still have to be recorded with the run that wrote the JSONL.

## Deterministic router

`python -m benchmarks.routing.score --from-router` looks for `route_scenario` in `benchmarks.routing.router`. This repository does not include that module. The command exits 2 and does not guess labels from the request. If a later change adds the function, it is called with only `id` and `request` for each flat case and for the project case. Gold fields are not passed in. There is no keyword router in this package.

## Prompt pack

`python -m benchmarks.routing.baseline` writes the prompt pack. It does not read `ANTHROPIC_API_KEY`, does not call a model, and does not exit 3. `--help` and a normal write both work with no key. Overwrite and symlink refusal exit 2.

Each prompt object has `id`, `instruction`, and `request`. The instruction is the same for every row and names the catalog ids from `skills/aic/assets/workflows.json`. It does not say which id belongs to which scenario. The request is the pack's request string. Expected fields, required milestone lists, required invariant lists, and stage objects are not copied. The receipt has `invokes_model` false. A prompt pack is not a comparison result.

## Paired comparison

`python -m benchmarks.routing.compare` runs two arms on one pack:

- `no-skill` receives the request and the closed catalog.
- `aic` receives the same request, the same catalog, and the same output schema, plus `skills/aic/SKILL.md` and the relative files that page links. Linked web URLs are not fetched. Gold fields are not added to either arm.

Both arms send the same `model`, `temperature`, and `max_tokens` to `https://api.anthropic.com/v1/messages` over HTTPS. The client does not follow redirects. The API key is the `x-api-key` header only. `--timeout` is the per-call limit, shared by both arms.

The Messages API has no seed parameter. `--seed` is recorded on the receipt and is not sent. `--model` is required; this command does not pick a model for you.

Without `ANTHROPIC_API_KEY`, or when the value is empty or whitespace, the process exits 3, writes nothing, and does not open a connection. `--help` does not need the key.

A finished run creates a new directory with `no-skill.jsonl`, `aic.jsonl`, and `report.json`. Each JSONL file is scored with the scorer above. The receipt's top-level `invokes_model` is true and `transport` is `anthropic-https`. Nested score objects still say `invokes_model` false: those objects only describe the decision files. `date` is the UTC calendar date of the run. `temperature`, `max_tokens`, `seed`, and `model` are the settings that were used.

The paired block uses flat cases only. For a field, or for exact match:

- `k_delta` is the AIC arm's correct count minus the no-skill arm's correct count.
- `rate_delta` is `k_delta / n`. It is null when `n` is 0.
- `baseline_only_correct` is the count correct only on the no-skill arm. `aic_only_correct` is the count correct only on the AIC arm.

The exact McNemar test is the two-sided exact binomial test on those discordant pairs. With `n = b + c` and `b` the no-skill-only count, the probability is the sum of `Binomial(n, 0.5)` masses whose likelihood is at most the likelihood of `b`, as a reduced rational `p_numerator / p_denominator`. When `b + c` is 0 the probability is null. There is no significance cutoff in the receipt.

Unparseable model text is an abstention for that case, not a fabricated label. An HTTP or transport failure exits 1 and writes no directory.

## Exit codes

| Code | Score | Prompt pack | Compare |
| --- | --- | --- | --- |
| 0 | Report written. Accuracy can be anywhere in range. | Prompt pack written. No model was called. | Both arms finished and the receipt was written. |
| 1 | Unused. | Unused. | The API call failed. No receipt was written. |
| 2 | Usage, malformed input, unknown id, or no deterministic router. | Usage, unreadable pack, or refused output path. | Usage, unreadable pack, or refused output path. |
| 3 | Symlink or overwrite refused. | Unused. | `ANTHROPIC_API_KEY` missing or blank. |

A traceback is not part of these exits.

## Limits

The scorer checks string equality with the pack. It does not judge whether a recommendation was wise. Two arms are comparable here only when they share the model id, temperature, max_tokens, timeout, pack, and output schema recorded in the receipt. A different seed value is a different recorded run even though the API does not receive it.

Catalog ids describe the closed label set. They are not predictions. Stage ids in the project prompt are alignment keys for the output schema, not gold labels. This document has no results table. Do not check a score file into the repository from a local run unless that run's receipt is the artifact under review.
