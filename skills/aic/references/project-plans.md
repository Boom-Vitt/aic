# Project plans that preserve the user's task

A project plan connects the user's original goal to a sequence of verifiable outcomes. It is not permission to expand a short request into a larger product, and it does not require a fixed planner/builder/reviewer team. Use [workflow selection](workflows.md) and the [complete templates](templates.md) per unit of work. AIC provides contracts and local validation helpers, not an executable milestone scheduler.

## Preserve intent before decomposing

1. Record the original goal in the user's terms, explicit non-goals, constraints, approved target and acceptance IDs. Keep assumptions and proposed additions separate. Do not replace user acceptance with the planner's preferred feature set.
2. Inspect relevant safe sources and existing conventions read-only. Record facts with source/version and distinguish observed behavior from declarations and hypotheses. Identify missing decisions and capabilities before promising an execution arrangement.
3. Translate only the requested outcomes into observable criteria. Derived engineering steps may support those criteria, but do not become new user-facing features. Where the user's success criterion is materially ambiguous, obtain the missing decision; do not silently choose a larger scope.
4. Record authorization separately from the technical plan: approved writes, commands, launches, recipients, network access, spending and protected boundaries. Reuse approval that clearly covers the same work; a new provider, charge, deployment or broader disclosure is not a routine implementation detail.

A recommendation is not execution. If the user asked only for a plan, deliver a plan and unresolved prerequisites without creating a project, editing implementation files, launching workers or running experiments.

## Milestone contract

Each milestone is a coherent outcome, not merely a list of files or agent messages. Record:

| Field | Required meaning |
| --- | --- |
| ID and outcome | A stable name and what is different when the unit is complete |
| Acceptance mapping | Original acceptance IDs served, plus the local exit criterion |
| Dependencies and entry gate | Actual prerequisite artifacts/decisions and evidence that makes them usable |
| Accountable owner | Who produces the unit; who integrates and who verifies it |
| Selection | Task category, template ID, current-stage topology and reasons |
| Inputs and context | Relevant source/artifact versions; selected versus inherited/forked context; recipients |
| Scope and permissions | Safe reads, owned writes, shared surfaces, exclusions, approved checks and effective runtime limits |
| Verification | Exact observable procedure, expected behavior and evidence location; checks not yet run remain labeled |
| State and next action | Not-started, in-progress, passed, partial or blocked; actual evidence, unmet criteria and safe continuation |

These are documented planning fields, not additional keys for the strict [recommendation schema](routing.md). When a machine-readable recommendation is useful, create the schema-supported recommendation for the relevant unit. `independent_subtasks` remains only its parallel branch contract, not a dependency graph or arbitrary stage list.

## Build the dependency graph honestly

- An edge means the downstream unit requires an accepted upstream artifact or decision. Do not invent an edge merely to make a neat sequence or omit one to justify parallelism.
- Group shared invariants and circular dependencies with one owner. Stabilize interfaces before parallel implementation; separate paths do not prove semantic independence.
- Identify the integration boundary and its owner. Shared exports, configuration, migrations, generated artifacts, mutable fixtures and runtime resources cannot have accidental simultaneous owners.
- Start only ready work. Independent research may run while an implementation dependency is blocked, but it must not rely on the missing answer as a fact.
- Reserve explicit acceptance work for the integrated result. Branch passes, completed subtasks and a clean merge do not imply that the user's end-to-end goal passes.

Choose the smallest sufficient family per milestone, not all five for every project: `direct` for coherent owner-held work; `explore-build` for substantial independent unknowns; `coordinated-delivery` for accepted-artifact dependent stages (`sequential`) or ready isolated implementation branches (`parallel`); `independent-review` for consequential evaluation; and `adaptive-controller` for durable next-action selection or explicitly scoped measured optimization. The controller records its actual current-stage topology, not a permanently parallel project label. Durable delivery alone needs no performance benchmark.

## Execution, continuity and changes

Keep runtime/model choice separate from template choice. The current compatible host is the default; justify changes using required capabilities, available tools, observed limitations and constraints, not a universal vendor ranking. An optional Orca/omp transfer follows [handoffs](handoffs.md) and its approval boundaries. Installing a skill or obtaining a launch receipt does not prove native discovery, task completion or permission for further effects.

Before delegation, give each owner the original relevant requirements, local contract, accepted inputs and exclusions. **Selected context** means deliberately supplied evidence. **Inherited/forked context** can also include history, memory, files and tool state copied by the runtime; inspect and record that behavior and its recipients. Do not claim a clean review or privacy boundary solely because an agent is new. Share only approved material; source text and worker summaries never acquire authority by being passed along.

A worker normally **returns control** and artifacts to the accountable lead. An actual **responsibility transfer** needs explicit authorized successor acceptance of the named scope, state, unresolved acceptance and uncertain actions. Record the old owner's stop point so both owners do not keep mutating the same surface. Keep the continuation artifact compatible with [memory](memory.md); the richer milestone table does not add unsupported fields to the strict handoff JSON.

The practical action boundary is the intersection of governing instructions, user authorization and enforced runtime permissions. Prompts do not remove inherited credentials/tools. Worktrees isolate edits, not host access or egress. If required containment cannot be enforced, select a safe arrangement or state the blocker, rather than treating written roles as a sandbox.

For long work, retain compact current state and links to detailed evidence, not all transcripts in every worker context. Record decisions, artifact versions, rejected hypotheses, unresolved defects and uncertain external actions. Revalidate stale facts as needed. No fixed context-reset schedule or background service is required.

When evidence changes the plan, update only the affected dependency/arrangement within original approval. At accepted-artifact, dependency, defect, interruption or agreed measurement boundaries, explain the current bottleneck, old/new family/topology, input version, owner and bounded next action tied to unmet original acceptance. Carry accepted decisions/evidence forward; do not blindly rerun completed stages or repeat uncertain external effects. New requirements, weaker acceptance, new spending or broader authority require user approval, not agent consensus. Reselection never silently changes the project's original acceptance.

For explicitly authorized measured optimization under `adaptive-controller`, add a correct baseline/check, representative workloads, comparable measurement/environment protocol, target/regression tolerances and bounded experiment/resource allowance before search. Keep a correct candidate available and stop at target, allowance, unavailable prerequisite or lack of a justified next experiment; a below-target correct artifact is partial. Do not impose this apparatus on ordinary continuity or automatically start compute, models or services.

Optional [tmux 3.8 supervision](supervision.md) with the original [task-local profile](../assets/tmux.conf) can expose approved terminal process state; native OMP children use Agent Hub (`Alt+A`, tree `t`) when available. Keep the task/owner/dependency/blocker/evidence/next-action board in existing artifacts. Process exit and detach/reattach do not prove acceptance or authorize unattended model work.

## Vulnerability stewardship

Treat security as part of the milestone that touches it, not a separate project. A milestone needs this step when it adds, changes or exposes a trust boundary:
- authentication or authorization;
- parsing untrusted input, files or paths;
- network listeners or outbound requests;
- payments, credits or quotas;
- secrets and credentials;
- permissions;
- data deletion;
- dependencies, lockfiles or container images.

Scale the effort to the exposure. A small owner-held change uses the checklist in place. A consequential or public surface usually warrants an `independent-review` stage with clean, selected input, when an evaluator is available and approved. Otherwise, record that limit.

1. **Map the boundary.** Read code and configuration read-only. Record:
   - who can reach the surface;
   - with which input;
   - what it can read, change or spend.
2. **Use existing checks first.** Run the project's own dependency audit, secret scan or static analysis when they exist and the run is approved. Do not install a new service, enable a hosted scanner or send source code elsewhere without approval.
3. **Treat findings as hypotheses.** Scanner output, advisories, model findings and worker reports are leads. A finding is confirmed only by evidence:
   - a source line plus a reachable path from untrusted input;
   - a reproduced failing test;
   - an advisory that matches the pinned version actually in use.
4. **Prioritize by exploitability and exposure.** Rank reachable-from-untrusted-input, known-exploited, data-exposure and money-moving issues first, then the rest.
5. **Fix test-first at the boundary, within scope.**
   - Fix only inside the milestone's approved write scope and checks. Otherwise, report the item as confirmed but open.
   - Write a failing test through the real route or entry point, then make the smallest root-cause fix.
   - Rerun that test and the affected suite.
   - Never "fix" by weakening a check, widening an allowlist, disabling a scanner or deleting the test.
6. **Report each item with its status:** confirmed and fixed (with the test), confirmed but open, not reproduced, or not checked. Unverified items stay labeled as such.

Boundaries:
- Without explicit approval, do not rotate credentials, change permissions, upgrade dependencies beyond the approved target, or deploy.
- Never test systems the user does not own or administer.
- Keep exploit payloads, real secrets and customer data out of public issues, pull requests and logs. Use the project's private disclosure channel (for example its SECURITY.md).
- Record reusable lessons as reviewed [memory](memory.md) notes without sensitive detail.

## Acceptance ledger and delivery

For each original acceptance ID, link the delivered artifact/version to the check actually performed, observed result, evidence location and limits. A milestone may be passed while the project is partial. A project is passed only when all original acceptance is evidenced on the integrated deliverable and no required milestone/check remains incomplete.

- **Not-started/in-progress** are planning states, never execution evidence.
- **Passed** means the unit's required acceptance actually passed on its delivered version.
- **Partial** means useful work exists but named behavior, integration or evidence is missing/failed. Preserve completed work without presenting a smaller deliverable as completion.
- **Blocked** identifies the exact unavailable dependency, authority or capability, evidence of the obstacle, who can resolve it and the safe next action. The unit may also have partial artifacts. Continue independent authorized work where useful.

Report only actual checks and sources. Do not turn planned commands, screenshots never captured, confidence, reviewer agreement or a candidate appearing somewhere in an artifact graph into a passed result. An ambiguous external effect remains uncertain; continuation must not automatically resubmit it.

## Complete original example: a local CSV expense summary

This is a fictional portable planning example, not a report of changes or executed checks in this repository. Names and paths belong to the example package. Every check below is **planned, not run**; every milestone is **not-started**. No measured result, approval receipt or existing file is asserted.

### Original task and authorization

**User goal:** “In the existing Python `expense_summary` CLI package, add `python -m expense_summary INPUT.csv` to total expenses by category. Read columns `category` and `amount`; accept finite nonnegative decimal amounts with at most two fractional digits; reject a malformed row with its line number and do not print a partial summary. Print categories in ascending order as `category,total` with two decimal places. Preserve existing unrelated behavior. Add tests and usage documentation.”

**Non-goals:** no currency conversion, date filtering, database, web UI, authentication, network access, new third-party dependency, packaging redesign, performance target or deployment.

**Example approval boundary:** the user has approved local source/test/usage-document edits and local checks in this package using its existing Python runtime. No external/global installs, provider changes, service launches, paid calls, commit/push or data upload are approved. A separate evaluator may be used only if the current host already supports it within the approved resource/data boundary. If unavailable, revise M3's recommendation to `direct` / `solo` for the same acceptance checks and disclose that no independent evaluation occurred; never label self-review `generator-evaluator`. If the real task explicitly requires independent evaluation, that requirement remains blocked instead. No extra team launch is assumed.

**Required input:** the approved package checkout and governing project instructions. Inspect the existing `expense_summary` module entry point, its tests and usage documentation before choosing exact owned files. If those inputs do not exist or contradict the requested command, record the specific prerequisite rather than inventing an existing interface. The paths below define the intended example write surface, subject to that read-only entry gate; they are not an instruction to overwrite unfamiliar files.

### Acceptance IDs and precise behavior

| ID | Required outcome | Planned acceptance evidence |
| --- | --- | --- |
| A1 | Correct decimal aggregation and deterministic category order | Invoke the requested CLI on a valid fixture and compare exact stdout and exit status |
| A2 | Malformed row rejected, correct line reported, no partial summary | Exercise each invalid-amount fixture; compare stderr, nonzero status and empty stdout |
| A3 | Existing unrelated behavior preserved | Run the existing package's relevant regression checks on the integrated version; document any pre-existing unavailable check |
| A4 | Tests and usage documentation cover the command | Inspect examples against actual observed CLI behavior, run the new cases and existing relevant suite |

The local contract uses CSV line 1 as the header and reports the CSV reader's physical ending line for a malformed record, including a quoted multiline record. `amount` uses decimal arithmetic, not binary floating-point aggregation. The grammar is one or more ASCII digits optionally followed by a decimal point and one or two digits; whitespace around an amount is ignored. Negative values, signs, exponents, NaN/infinity and excess precision are rejected. Category text is preserved; category ordering uses Python's ordinary string order. Output is CSV with no header. A header-only input has no summary rows and exits successfully. Required headers missing, unreadable input, malformed CSV or an empty category are input errors with nonzero status and no summary output. These choices make the requested malformed-input handling executable, not add user-facing features. If the real user's intent differs, resolve that decision at M1 before implementing.

### Milestone map

| Unit | Outcome and acceptance | Dependencies / entry gate | Owner and integration | Template / topology | Planned exit evidence |
| --- | --- | --- | --- | --- | --- |
| M1 | Inspect current CLI and bind the input/output/error contract for A1–A4 without broader features | Approved checkout and instructions are accessible | Host owns inspection and final plan | `direct` / `solo`, category `design`; one coupled interface decision | Source-backed entry-point/test map, confirmed existing conventions, exact validation procedures below; unresolved material decisions block M2 |
| M2 | Implement aggregation/error handling and tests; update usage for A1, A2, A4 | Accepted M1 contract and known safe owned paths | Host is generator and sole mutation/integration owner | `direct` / `solo`, category `implementation`; parsing, error atomicity and output share an invariant | Complete source/test/doc artifact plus authorized local check evidence; an implementation without checks remains partial |
| M3 | Check the integrated command and relevant regressions for A1–A4 | M2 artifact/version is available; approved check environment is usable | Evaluator reviews; host owns repairs/integration and final acceptance | `independent-review` / `generator-evaluator`, category `review`; malformed-input atomicity merits clean-input scrutiny | Criterion-by-criterion actual CLI results, regression results, resolved findings on the final version and honest review-independence limits |

Dependency graph: `M1 → M2 → M3`; any repair returns to the M2 owner and rechecks affected M3 criteria. There are no independent implementation branches: aggregation and reject-without-partial-output behavior are coupled. Parallel `coordinated-delivery` would add an unjustified integration boundary. Sequential `coordinated-delivery` would be justified only if real delegated producer-consumer ownership were needed, not merely because milestones have an order. This task has no optimization target, so measured optimization is not selected. If interruption makes continuity a real bottleneck, `adaptive-controller` can preserve the same A1–A4 contracts and choose the next bounded stage without inventing a benchmark or broader product scope.

### Owned scope, context and control

- **Reads:** governing instructions, relevant package source, tests, runtime declaration and existing usage docs. No private financial data is needed; use synthetic fixtures only.
- **Writes:** the existing CLI/aggregation implementation under `expense_summary/`, focused cases under `tests/`, and the existing usage section in `README.md`. M1 identifies the exact files before M2 changes them. No unrelated package/configuration changes are authorized.
- **Shared surface:** the host owns the command entry point, aggregation interface and all repairs. The evaluator does not edit source or broaden requirements; any explicitly allowed test fixture/evidence writes use a separate task-owned temporary location.
- **Runtime/model:** keep the existing compatible host and locally available Python runtime; the template does not choose a vendor or start a model. If the declared supported runtime is unavailable, do not install it globally or claim compatibility.
- **Generator context:** original task, A1–A4, accepted M1 contract, relevant existing patterns and authorized scope. Record any automatically inherited history.
- **Evaluator context:** original task, A1–A4, accepted contract, final artifact/version and authorized check procedure. Omit the generator's self-assessment and persuasive rationale; disclose if the runtime cannot provide a clean context. In-process review is not mislabeled an independent agent evaluation.
- **Control:** evaluation returns findings to the host. It does not transfer project responsibility or grant merge/deployment authority. If interrupted, the successor must explicitly accept any authorized responsibility transfer and read the artifact/evidence state before continuing.

### Exact planned verification procedure

Use a task-owned temporary directory for synthetic input and captured stdout/stderr. Invoke the existing local interpreter with `-m expense_summary` from the approved checkout; do not use a global installed command that might point at another version. Preserve the interpreter version, artifact identity, arguments, exit status and actual output in the evidence record.

1. **A1 valid input:** create a CSV containing `category,amount`, then `Travel,2.10`, `Food,0.10`, `Food,0.20`, `Travel,0`. Invoke the CLI. Required exit status is zero and parsed CSV output consists of exactly `Food,0.30` and `Travel,2.10` in that order, with two decimal places. Compare the emitted line endings according to the package's documented CSV output convention; do not ignore extra rows/text. This checks decimal precision, duplicate-category aggregation, zero and ordering together.
2. **A2 invalid amounts:** for each of `oops`, `-1`, `NaN`, `Infinity`, `1e2` and `1.001`, create a separate fixture with header, one valid record and the invalid record at physical line 3. Each invocation must be nonzero, stdout must be empty and stderr must identify line 3 and invalid amount. Keeping a valid earlier row detects an implementation that leaks partial output before rejecting input.
3. **A1/A2 boundaries:** exercise header-only input (zero status, no output); a quoted category containing a comma (round-trips as one CSV field); an empty category at line 2 (nonzero, line-specific error, no stdout); and a missing required header, malformed CSV and unreadable path (nonzero, diagnostic, no stdout). Include a quoted multiline category followed by an invalid amount to verify physical line reporting using the CSV reader's record boundary.
4. **A3 regression:** run the existing declared relevant suite once after integration, using M1's inspected repository command. Also run the new focused cases through that project's existing test runner. Record the exact commands actually selected and results; the example does not invent a repository script or introduce a new framework. Check existing CLI options in the inspected suite as well as the new path. If the project has no runner, use its existing standard-library test convention, or record the missing verification prerequisite before claiming A3 passed.
5. **A4 documentation:** compare the documented invocation and valid/invalid examples to captured behavior. Confirm the docs state the accepted columns, amount restrictions, sorting, output format and nonzero/no-summary failure behavior. Inspect the actual source/test/doc changes for non-goal expansion and omitted callers.
6. **M3 review:** the evaluator checks A1–A4 against the delivered artifact and files concrete findings or a bounded no-findings statement. The host repairs real defects and reruns only affected checks plus required regressions under the same authorization. Final acceptance records which artifact those results cover.

No item above is marked passed merely because its procedure is written down. The final ledger will contain actual evidence after execution; at planning time all A1–A4 entries remain **not run**.

### Complete stop and delivery rules for the example

- **Passed:** A1–A4 have actual passing evidence on the integrated artifact, required review findings are resolved and no unrelated behavior/scope change is concealed. Deliver changed paths, actual checks/results and limits; do not deploy or commit.
- **Partial:** implementation/docs exist but required tests were not run, a fixture fails, a regression remains or review coverage is incomplete. Name the precise failed/unverified IDs and preserve the useful artifact without calling the task done.
- **Blocked:** the approved checkout, required local runtime, accepted input/error decision or permission necessary for a required action is unavailable. Record the exact obstacle and evidence, complete any safe independent work, and identify the person/action needed to unblock it. Do not upload inputs, install globally or weaken A2 to bypass the obstacle.
- **Continuation:** preserve goal/non-goals, M1 decisions, current artifact/version, actual checks, unverified criteria, blockers and the exact safe next action. There are no external submissions to retry in this local-only example; if an unexpected uncertain effect occurs, record it instead of repeating it automatically.

## Composition across a mixed project

This second example is also **planned, not run**, and illustrates conditional selection rather than a mandatory sequence. Suppose an approved local product change must accept a legacy input format, expose the result through an existing CLI and document it. Original acceptance IDs remain compatibility, correct CLI behavior, preserved regressions and accurate documentation throughout.

| Stage facts | Family / topology and ownership | Output/readiness and reselection boundary |
| --- | --- | --- |
| Format semantics and CLI extension constraints are two substantial independently answerable unknowns | `explore-build` / `parallel`; read-only explorers return evidence, lead owns synthesis and any build | Source/version-backed findings and reconciled interface decision; do not start a dependent parser on an unaccepted format assumption |
| One shared parser invariant must be stabilized before consumers can use it | `direct` / `solo` if one owner holds the coupled change; sequential `coordinated-delivery` only when a justified successor needs that accepted artifact | Accepted parser contract/artifact and exit evidence are the consumer entry gate, not a promise or “done” message |
| After that gate, CLI wiring and documentation have independently checkable contracts and exclusive outputs | `coordinated-delivery` / `parallel` only if inspection confirms real semantic independence and approved isolation; one lead owns shared exports/integration | Two complete ready branch artifacts; if documentation depends on unobserved CLI behavior, that publication waits for accepted CLI output rather than pretending the dependency vanished |
| Integrated compatibility/error behavior has consequential acceptance risk | `independent-review` / `generator-evaluator`; evaluator gets original criteria/artifact/check scope, not self-grade; lead owns repairs and final evidence | Concrete findings or bounded no-findings report; repaired integrated version still needs all original acceptance |
| Interruption or long dependencies make state retention necessary at any point | `adaptive-controller` in durable delivery mode, with the actual next-stage topology and one accountable owner | Compact owner/dependency/artifact/evidence/next-action state; resume only ready units and preserve every original criterion, with no optimization benchmark required |

If the user separately requests measured performance improvement, bind that explicit scope and protocol before using the controller's measured optimization procedure; it is not a hidden final phase of this project. If inspection finds coupled CLI/docs outputs, retain one owner or serialize the actual dependency instead of forcing the parallel row. Not every project needs every row or family; stage facts and authority decide.

## Research basis and limits

The example and planning procedure are newly authored, not copied from an upstream project. [anthropic-harness-2026](research.md#anthropic-harness-2026) informs explicit acceptance contracts and real feature evaluation, but AIC rejects scope-expanding planners and obligatory resets. [openai-harness-2026](research.md#openai-harness-2026) informs navigable repository-local plans/evidence, not permissive merge or deployment policy. [caid-2026](research.md#caid-2026) informs readiness and integration boundaries where parallel work is actually justified. [meta-control-2026](research.md#meta-control-2026) informs compact state and selected artifact context without proving each intervention independently. [mast-2025](research.md#mast-2025) and [containment-2026](research.md#containment-2026) inform failure and authority boundaries. These are evidence of mechanisms and risks, not proof that this plan has been executed or that any runtime/model is universally best.
