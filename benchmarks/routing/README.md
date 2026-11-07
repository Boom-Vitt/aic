# Routing scorer

Offline comparison of routing decisions with the held-out pack at `tests/fixtures/routing-scenarios.json`. The scorer does not read request text to choose a workflow, and it does not call a model, a network API, or a cloud service. A number appears only after you point it at a decision file from a real run. This document has no results table.

The pack's own `limits` text still applies: the expected fields and stage labels are evaluation data, not a production classifier, and they stay withheld from fresh host inputs.

## Commands

From the repository root:

```sh
python -m benchmarks.routing.score --decisions decisions.jsonl
python -m benchmarks.routing.score --decisions decisions.jsonl --output report.json
python -m benchmarks.routing.baseline --output prompts.jsonl
```

`--scenarios` replaces the default pack. The replacement must use schema version 3. `--output` creates a new file and refuses a path that already exists or is a symlink. Decision, scenario, catalog, and output paths are not followed when the final component is a symlink.

`--help` works with no model credential. Scoring does not read `ANTHROPIC_API_KEY`.

## Decision file

UTF-8 JSONL, one JSON object per line. Blank lines are ignored. Each object needs an `id` that matches a pack case, or the project case id `mixed-project-plan`, exactly once.

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

## No-skill baseline template

`python -m benchmarks.routing.baseline` prepares the prompts a no-skill arm would see.

- Without `ANTHROPIC_API_KEY`, or when the value is empty or whitespace, the process exits 3. It prints the refusal on stderr, leaves stdout empty, and does not create or replace the output file.
- `--help` does not need the key and does not write a pack.
- With a non-blank key, the process writes a JSONL prompt pack and a JSON receipt. It still does not start Claude Code, open a provider connection, or copy the key into the pack, the receipt, or a child environment. `calls_api`, `invokes_model`, `executed`, and `skill_loaded` are false. The receipt is not a score.

Each prompt object has `id`, `instruction`, and `request`. The instruction is the same for every row and names the catalog ids from `skills/aic/assets/workflows.json`. It does not say which id belongs to which scenario. The request is the pack's request string. Expected fields, required milestone lists, required invariant lists, and stage objects are not copied. The project case is one prompt, containing its request and not its stage table.

The other adapters in this repository start a model only when the key is set. This file is the routing template those runs would consume. Producing decisions is an external step. Score the JSONL that step writes. Do not treat the prompt pack, or a run that exited 3, as a baseline result.

A no-skill harness should not load the AIC skill. The aicbench baseline arm is the local precedent: Claude Code without the AIC skill directory. Wiring that command, including any live credential, stays outside this template.

## Exit codes

| Code | Score | Baseline |
| --- | --- | --- |
| 0 | Report written. Accuracy can be anywhere in range. | Prompt pack written. No model was called. |
| 2 | Usage, malformed input, unknown id, or no deterministic router. | Usage, or the pack could not be read. |
| 3 | Symlink or overwrite refused. | `ANTHROPIC_API_KEY` missing or blank, or the output path was refused. |

A traceback is not part of these exits.

## Limits

The scorer checks string equality with the pack. It does not judge whether a recommendation was wise, whether the host actually withheld the labels, or whether two runs are comparable. Schema validation of a full AIC recommendation is the separate `check-plan` helper, not this report.

Catalog ids in the baseline instruction describe the closed label set. They are not predictions. Adding a keyword table, a model client, or a checked-in score file would cross the boundary this package is held to.
