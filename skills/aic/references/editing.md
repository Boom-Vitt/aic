# Editing and checking a change

Host guidance for an approved edit or a reported failure. It applies inside `direct` and to the owner's own edits in any other family. It does not add a family, a shell, a second agent, an embedding index or a keyword router. The cited papers are not relicensed, and AIC has not rerun their benchmarks. A published comparison is not an AIC measurement and is not permission to launch extra model calls.

Read [workflow selection](workflows.md) for the family, and the ledger entries [swe-agent-2024](research.md#swe-agent-2024), [agentless-2024](research.md#agentless-2024) and [autocoderover-2024](research.md#autocoderover-2024) for credit and rights. Those entries paraphrase mechanisms. They do not include upstream source, prompts or tables.

## Search, then open a window

Use the host's existing search and editor.

- Ask for a capped summary of matches. Do not dump every hit, and do not page through matches one at a time. A one-match walk was the worse search shape in the SWE-agent comparison this procedure follows.
- When the file is long, open the relevant region rather than the entire file. Edit against the lines in that view. After the edit, show the updated region.
- Keep the latest observation. Do not paste the whole scrollback into the next step.
- Do not add an AIC shell or a file-viewer program to obtain this. The host's read and edit tools are enough.

## Narrow the location before writing

When the task does not already name the edit:

1. Name candidate files from the repository layout and from the issue text. Prefer a search by class, method and caller when the host already has that navigation.
2. Read a skeleton of the relevant file: headers, signatures and the comments that state a contract. Do not paste every suspicious file in full.
3. Name the spans to change.

If several plausible locations remain, inspect or repair them separately. Do not merge competing locations into one large context. The Agentless comparison this procedure follows found that merging locations raised coverage of the developer edit and lowered the number of fixes, which that paper explains as a context-size effect. Coverage of a developer location is not itself a fix.

Skip the staging when the request already names the file and the behavior. Do not add a vector index. If the host already ranks symbols, the owner may use that ranking and must not claim a measured resolve-rate gain for it.

## Show the failure, then edit

For a reported failure, keep the report as ground truth.

- Before editing, show the failure with a check that runs on the unmodified code inside the approved workspace.
- Drop a patch that fails that check. If every candidate fails it, say so and fall back to the checks that already passed before the change. Say that the reproduction check rejected the pool.
- Pre-existing passing tests may guard behavior the owner has said a correct fix must keep. They are not permission to change that behavior silently.
- Do not open or copy an acceptance suite outside the approved workspace. Using one as a localization signal or as a voter invalidates the comparison.
- A generated check can prefer a wrong patch. Treat it as a filter with that limit, not as the user's acceptance suite.
- One careful edit is the default. Sampling more than one patch is allowed only when the user has already authorized the extra model calls, a baseline and a stop count.

## Undo an edit that adds a diagnostic

After an edit in a language the host can lint, compare diagnostics with the file from before the edit. If the edit introduces a new syntax or lint error, undo it and return the diagnostic. A lint failure shows a bad edit. It does not show that the issue is fixed.

The same owner applies the undo. Do not add a second agent whose only job is to format the edit. If a formatted edit fails, restate the change and then apply it. That split is a response to a format failure, not a default team.

## Record the changed surface

For the behavior that was supposed to change, record:

- the command or route that was exercised
- the input
- the observed result
- the empty or error case, when the surface has one
- the checks that were not run

A screenshot, a worker report or a claim that the code looks right does not fill this record. When the task is documentation, record that the text matches the code and that code bytes stayed unchanged if the task forbids code edits. When the task asks for tests, run those tests. When the task is a refactor, show that the stated behavior is unchanged.

Passed, partial and blocked keep the meanings in [workflow selection](workflows.md#outcomes-and-stop-rules). An unrun required check blocks a passed claim.

### Machine-checked record

The optional `check-surface` helper accepts one JSON object and does not run the command. A valid record is not approval, and it does not prove the observation text is true. `passed` needs an empty `not_run` list and the same command recorded both before the edit and after it, each with an exit code. Any other outcome may omit checks.

Fields are exactly `schema_version` (the integer 1), `kind` (`aic-changed-surface`), `task`, `outcome` (`passed`, `partial`, `blocked` or `failed`), `checks` and `not_run`. Each check has exactly `command`, `phase` (`before` or `after`), `observed` and `exit_code`. A command that uses `..` or is absolute is rejected. At most 8 checks and 12 not-run strings.

## Findings, when evaluation is separate

Use this only when the selected family is `independent-review`, or when the user asked for a separate check. The evaluator receives the issue or criteria, the artifact version and the check outcomes. The evaluator does not receive the generator's argument for its own patch.

Each finding names the artifact version, the criterion, a location, the observation and the impact on acceptance. A review with no findings names the surfaces that were examined and the surfaces that were not. Do not report a pass that omits both.

## What this procedure does not adopt

- No new code-execution tool. A host that can already run a check may bundle that check and the follow-up. File edits still use the guarded edit above. An unrestricted shell edit is the shape the SWE-agent comparison found weaker than a dedicated edit.
- No search tree and no extra selector model, unless the user has already authorized measured optimization with a correct baseline, a correctness check, comparable measurements and a call budget. Flexible stage order is not a default. The small gain from unconstrained transitions in the SWE-Search comparison is a reason to keep stage order unless search is there to stop a loop.
- No spectrum ranking on tests taken from a hidden suite. Hints from a failing test are eligible only when that test already exists in the project and was not written from the hidden acceptance suite. The issue text still has to agree before editing. Stop a validation retry when the authorized tests pass or a small bound is hit. The AutoCodeRover comparison bundled hints and a retry and measured them on a suite that included tests written with the fix. That bundle is not evidence for ranking with only the tests that passed before the issue. Do not import that project's runner. Its current repository license is source-available and is not a grant to copy the implementation.
- No embedding provider and no claim that a repository map, by itself, has a measured resolve-rate gain in the sources named above.

## Rights

This file is original AIC wording. It does not copy paper prose, tables, prompts or implementation source. License notes, paraphrased from the checks named in the ledger:

- The SWE-agent arXiv abstract page displayed a CC BY 4.0 badge. That badge is not a license for the NeurIPS proceedings PDF. The pinned implementation repository is MIT. No source is included.
- The Agentless arXiv abstract page displayed CC BY 4.0. The pinned implementation repository is MIT. No source is included.
- The AutoCodeRover arXiv abstract page displayed a CC BY 4.0 badge. That badge is not assumed to license the ACM proceedings PDF. The implementation repository checked for this ledger is under a source-available license. Only the paper's described mechanism is used, and no source is included.
