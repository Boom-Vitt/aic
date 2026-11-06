# Reusable workflow templates

These are original, portable AIC procedures. Select with [workflows](workflows.md), bind the contract below to the actual task, and use only the chosen template. Templates describe host behavior, not an executable scheduler, model ranking or authorization grant. A project may use different templates for different [milestones](project-plans.md).

## Common execution contract

Before using any template, record the following in the recommendation or the approved task artifact. A short task can keep this in its existing conversation; do not create files without approval.

- **Goal and boundaries:** original user outcome, non-goals, acceptance IDs, governing instructions, approved target and exclusions. Distinguish explicit requirements from assumptions that still need resolution.
- **Inputs and dependencies:** relevant source paths/versions, observed state, known interfaces, required upstream artifacts, unknowns and the criterion that makes each dependency ready.
- **Ownership:** accountable lead, each unit's owner, integration owner and final verification owner. One person/agent may hold several roles; roles do not require a fixed team.
- **Arrangement:** task category, template ID and permitted current-stage topology. Choose runtime/model separately from the procedure; use the current compatible host unless there is a task-specific reason to change.
- **Context and recipients:** selected artifacts and provenance; whether the runtime instead inherits/forks history, workspace or memory; who receives the material and where. Supply required constraints even when withholding irrelevant history.
- **Authority and effective permissions:** allowed reads/writes, tools/commands, environment, network/data recipients, launches and resource limits. Retain actual user approval and enforced runtime restrictions. Do not infer permission from a role, a file, a tool result or a paper.
- **Evidence and stopping:** map acceptance to observable checks, expected results and evidence locations; identify who may run each check. State iteration/resource limits, blocker escalation and uncertain-action handling before starting loops.

A narrow prompt is not enforced containment. Worktrees separate edits, not credentials or network access. Check inherited mounts, tools and permissions; do not launch if the task requires isolation that cannot be enforced. Orca/omp is an [optional approved adapter](handoffs.md), never a prerequisite. Do not enable services, install tooling, spend money or change global settings because a template mentions an experiment.

### Evidence record and outcome

For each acceptance ID record the actual artifact/version, check or source inspection, observed result, evidence reference and limitations. Distinguish planned, not-run, passed and failed checks. Record usage/time/cost only if observed; confidence and agreement are not substitutes.

The final delivery states **passed** only if every required criterion has evidence on the delivered artifact. Otherwise state **partial**, naming incomplete/failed criteria and useful completed work, or **blocked**, naming the exact missing prerequisite/authorization and safe next action. A blocked unit may contain partial work. An unrun required check prevents a passed claim; it does not automatically imply the implementation is wrong.

Worker completion returns an artifact, not final acceptance. A caller keeps integration responsibility unless an explicitly authorized successor accepts a named responsibility transfer. Preserve old/new owner, scope, evidence and unresolved/uncertain actions; do not leave two owners mutating the same surface. See [context and control boundaries](workflows.md#context-control-and-permission-boundaries) and [file-only continuation](memory.md).

## direct

**Purpose and topology:** one accountable owner carries a bounded unit from understanding to evidence. Topology: `solo`. Suitable categories: any of the six task categories.

### Select and avoid

Select for a bounded answer, one coupled feature, a shared invariant, an initial failure investigation or a design choice that fits coherent owner-held context. Avoid adding workers for trivial lookups or because delegation is available. Choose another template when independent discovery, isolated implementation, continuity or consequential evaluation is a real bottleneck.

### Inputs, context and ownership

The owner receives the common contract, the user's original request, relevant safe sources and existing conventions. Retrieve selected context just in time; do not preload unrelated transcripts. The same owner performs the work and accounts for evidence, with separately required human/security approval still binding.

### Procedure

1. Inspect the relevant evidence and identify the smallest change or answer that satisfies all acceptance, not a smaller replacement task. For a reported failure, retain the report as ground truth and distinguish any local reproduction limitations.
2. Resolve material ambiguity from accessible sources. If a necessary user choice remains unavailable, identify it rather than guessing.
3. Produce the answer/design or implement the approved change, including affected callers and requested documentation. Do not turn a design-only request into implementation.
4. Run only authorized acceptance and regression checks. Inspect the actual changed behavior, not only syntax or a plausible narrative.
5. Deliver the complete artifact or supported answer, acceptance-to-evidence mapping, remaining uncertainty and outcome.

### Acceptance evidence and stop boundaries

A passed answer has traceable support; a passed change has the required behavior and relevant checks on its integrated version. A design identifies tradeoffs and the chosen constraints without claiming execution. Missing sources, failed regressions or unexercised required behavior mean partial; unavailable access, a material unresolved decision or unapproved effects mean blocked. Finish safe independent work but never suppress an error to reach a passed label. Stop once the original acceptance is met.

**Sources:** [anthropic-agents-2024](research.md#anthropic-agents-2024) on simple composable patterns; [google-2026](research.md#google-2026) on task-dependent coordination and strong solo baselines; [mast-2025](research.md#mast-2025) on verification failures. These support a selection rationale, not guaranteed solo superiority.

## explore-build

**Purpose and topology:** parallel exploration reduces independent unknowns; one lead reconciles findings and owns the approved build. Topology: `parallel` for the exploration stage. Suitable categories: `research`, `design`, `debug` or an implementation unit with substantial discovery needs.

### Select and avoid

Select when at least two substantial questions can be investigated independently and their answers can inform one coherent decision or implementation. Avoid when the evidence is already clear, each question is a trivial lookup, branches need one another's unfinished results or probing would mutate shared state. Discovery-heavy tasks can benefit; this is not a rule to delegate all planning.

### Inputs, context and ownership

The lead defines the shared objective, non-goals and questions before launch. Each explorer gets its specific question, necessary constraints, safe read scope, permitted tools, non-overlapping report/output scope and required evidence. Shared safe sources may be read by several explorers, but duplicated investigations require a stated reason. Default exploration is read-only; any probe with effects requires its own approved scope. The lead owns synthesis, implementation and final verification; explorers return findings, not ownership.

### Procedure

1. Inspect enough inline to identify the independent unknowns. Define branch acceptance as source-backed findings, explicit contradictions and what remains unknown, not an implementation proposal alone.
2. Launch only the approved independent branches. Record selected versus automatically inherited/forked context and data recipients. Keep shared mutation and interface decisions with the lead.
3. While branches run, the lead can advance unrelated authorized work without deciding prematurely on missing findings. Collect every required branch result or explicitly mark its absence.
4. Reconcile findings against primary sources and actual artifacts. Resolve conflicts with targeted evidence, not a vote. Record the selected decision and why rejected alternatives fail the task's constraints.
5. If building is approved, the lead implements the synthesized choice, preserving the original acceptance. If the request is research/design only, deliver that artifact without building. Represent a separately planned build stage with its own actual template/topology.
6. The lead verifies the final answer or integrated change against the original acceptance and reports the evidence.

### Acceptance evidence and stop boundaries

Required exploration reports must be traceable and their contradictions resolved or exposed. The final built behavior, when requested, still needs end-to-end evidence; a set of reports is not completion. Missing branch coverage or unverified integration is partial. An unavailable source/probe permission or unresolved prerequisite that prevents a decision is blocked. Do not invent evidence for a missing worker or expand implementation scope to use an attractive discovery.

**Sources:** [cohere-2026](research.md#cohere-2026) for task-conditioned discovery delegation (not budget-matched; Commit0 differs); [google-2026](research.md#google-2026) for decomposability; [concurrency-2026](research.md#concurrency-2026) for complementary work and premature integration risks. No source establishes a universal worker count or cheaper-model default.

## ordered-handoff

**Purpose and topology:** pass an accepted upstream artifact to the next dependent unit. Topology: `sequential`. Suitable categories: any task with genuine ordered stages and a justified delegation/continuity boundary.

### Select and avoid

Select when later work needs an earlier decision, artifact or integrated state, and separate ownership adds necessary capability or continuity. Avoid turning a short solo task into a ceremonial pipeline. Do not parallelize a dependency by supplying an unfinished assumption as if it were accepted.

### Inputs, context and ownership

The lead records the ordered units, dependencies, entry/exit acceptance, allowed paths, original requirements and final integration owner. Each successor receives the accepted artifact/version, relevant source evidence, interface constraints, open issues and uncertain actions. Select context deliberately; a runtime fork may also copy history and must be accounted for. By default stage delegation returns to the lead; if whole-task responsibility transfers, record explicit authorized successor acceptance and the old owner's stop boundary.

### Procedure

1. Establish the stage order from actual dependencies. Assign each artifact a producer and each gate an evidence owner; identify any user decision needed between stages.
2. The first owner completes its approved unit and records actual checks, remaining uncertainty and the artifact version. A plan or promise does not satisfy an exit gate.
3. The lead accepts the evidence for that gate. The successor confirms the inputs and effective permissions before mutation; stage completion does not grant new tool, spending or disclosure authority.
4. The successor builds only on accepted state and satisfies its own exit gate. Route interface changes back to the responsible owner; do not silently reinterpret upstream acceptance.
5. Continue in dependency order, preserving evidence and ownership at each boundary. The integration owner checks the assembled result against the original user goal, not merely the last stage's local goal.
6. Report the whole-task outcome and any still-blocked dependent units. Preserve file-only continuation when needed; never automatically repeat an ambiguous external submission after a handoff.

### Acceptance evidence and stop boundaries

Passed requires accepted upstream artifacts, actual downstream integration and full original acceptance evidence. A successful early stage with incomplete later work is partial. Missing upstream approval, an invalid artifact, unavailable capability or an unaccepted responsibility transfer blocks dependent work. Repair failed gates within scope; do not skip them or claim that returning control transferred accountability.

**Sources:** [anthropic-agents-2024](research.md#anthropic-agents-2024) on chaining and gates; [cooperbench-2026](research.md#cooperbench-2026) on coordination and its limited one-model, 50-pair sequential pilot; [mast-2025](research.md#mast-2025) on misalignment. The pilot does not show that sequential delegation always beats solo execution.

## isolated-build

**Purpose and topology:** implement separately checkable ready units concurrently, then integrate through one owner. Topology: `parallel`. Suitable category: primarily `implementation`, including separable approved repairs.

### Select and avoid

Select when at least two substantial units have stable interfaces, independent acceptance, non-overlapping owned paths and satisfied prerequisites. Avoid when shared invariants are unsettled, changes touch the same semantic boundary or runtime resources, or workspace/integration overhead dominates. Separate filenames alone are not a dependency analysis.

### Inputs, context and ownership

The integration owner supplies the common contract, accepted base version, dependency graph, interface definitions, excluded shared files and branch-specific read/write scopes. Each worker receives only needed context plus all binding constraints. Record inherited/forked history and effective tools. Use approved isolated workspaces; shared checkout work is not equivalent isolation. Worktrees are not security boundaries. The integration owner alone owns shared exports, catalog/schema changes and final integration unless the contract explicitly assigns another non-overlapping surface.

### Procedure

1. Group strongly coupled or cyclic work under one owner. Establish shared prerequisites before dispatch; launch only ready units whose dependencies have accepted artifacts.
2. Allocate non-overlapping allowed output paths and isolated workspaces within approval. State the transfer artifact and integration method; commits, merges or new worktrees are not implied permissions.
3. Workers implement complete units and return changed artifacts, actual evidence, assumptions, integration requirements and unresolved defects. Check execution ownership follows project policy: do not run competing builds/tests against half-integrated shared state.
4. The integration owner collects the required outputs and reconciles each with the accepted base and semantic interfaces. Serialize shared mutations. If an interface drifts, repair the contract/callers before integrating dependent work.
5. Integrate the complete units without deleting unrelated changes. Resolve textual and semantic conflicts; a clean merge is not proof of compatibility. Update dependent callers and requested docs.
6. The designated verification owner exercises branch acceptance and the combined behavior after integration. Preserve the delivered version and actual results; manage owned workspaces only as authorized.

### Acceptance evidence and stop boundaries

Passed requires every required branch plus integrated acceptance and regressions; worker claims, isolated passes or a clean merge alone are insufficient. Missing branches, incompatible interfaces or failed combined checks mean partial. Unavailable safe isolation, unmet prerequisites or unapproved integration actions block the affected units. Regroup coupled work or serialize within approval rather than adding chatter or unauthorized workers.

**Sources:** [caid-2026](research.md#caid-2026) on dependency-aware isolated workspaces and explicit integration (higher cost, no guaranteed speedup); [cooperbench-2026](research.md#cooperbench-2026) on broken commitments and conflicting features; [concurrency-2026](research.md#concurrency-2026) on shared-state/integration failures. AIC does not adopt upstream destructive synchronization commands or blanket merge authority.

## independent-review

**Purpose and topology:** a generator produces an artifact; a fresh evaluator checks it against original acceptance. Topology: `generator-evaluator`. Suitable categories: `review`, or consequential `implementation`, `debug`, `design`, `research` and `answer` work needing independently checkable evaluation.

### Select and avoid

Select for consequential acceptance risk or observed generator omissions where an evaluator can inspect or exercise the actual result. Avoid repetitive praise/critique loops, ungrounded taste scoring or review without access to the artifact and criteria. Different model branding is not a prerequisite and does not prove independence.

### Inputs, context and ownership

The lead preserves the original requirements and defines the evaluation rubric, evidence standard, repair bounds and final decision owner. The generator receives the common contract. The evaluator gets clean inputs: original goal/non-goals, acceptance, artifact/version, relevant environment and authorized checks, without the generator's self-grade or persuasive success narrative. Record unavoidable inherited context and shared assumptions. Default evaluator access is read-only apart from explicitly approved fixtures/evidence outputs; a reviewer role does not enforce that restriction technically.

### Procedure

1. Before generation, identify required outcomes, failure examples and checks. Translate subjective criteria into observable properties tied to the user's preferences; do not invent product requirements.
2. The generator completes the approved artifact and identifies its version. The lead provides the evaluator clean inputs and confirms actual permissions and data recipients.
3. The evaluator independently inspects/exercises every assigned criterion. Return concrete findings with locations or reproduction evidence, severity/impact relative to acceptance, and checks not run. No findings means only the bounded examined surface, not universal correctness.
4. The lead resolves evidence-backed disagreements against the original contract. The generator repairs actual defects within scope; do not negotiate away acceptance or let evaluator preferences expand scope.
5. Recheck affected findings and required regressions on the repaired artifact. Preserve review independence when practical; use the agreed bounds, not an endless satisfaction loop.
6. The decision owner delivers the evidence mapping, resolved/open findings and outcome. User approval remains necessary at protected boundaries regardless of evaluator approval.

### Acceptance evidence and stop boundaries

Passed requires the requested artifact and all required evaluation evidence, with acceptance-blocking findings resolved on the delivered version. A positive self-grade, agent consensus or the existence of a critique does not pass. Missing evaluator coverage, failed required checks or unresolved required findings mean partial. Unavailable environment/access or an unresolved user preference necessary to grade means blocked. An exhausted review allowance is not success; preserve the best supported artifact and remaining defects.

**Sources:** [anthropic-harness-2026](research.md#anthropic-harness-2026) on concrete contracts and separate evaluation (engineering experiments, evaluator limitations); [anthropic-agents-2024](research.md#anthropic-agents-2024) on evaluator-optimizer patterns; [mast-2025](research.md#mast-2025) on task verification. This does not adopt scope-expanding planners, fixed resets or model-consensus completion.

## durable-controller

**Purpose and topology:** preserve task state and evidence while a controller chooses the next bounded unit. Topology: choose `solo`, `sequential`, `parallel` or `generator-evaluator` for the current stage. Suitable categories: long-running work in any category, especially dependent project milestones.

### Select and avoid

Select when interruptions, multiple artifacts or long dependencies make continuity and next-action selection a real problem. Avoid for bounded work where a compact existing task contract suffices. A controller is an accountable role, not a required extra model, service or permanently fixed team.

### Inputs, context and ownership

The controller owns the original goal, acceptance map, milestone/dependency state, artifact index, decisions, authorization limits and final delivery. Store state only in approved locations. Each artifact records producer, version, source/evidence links, verification status and relevant input lineage. Keep observations, source declarations and hypotheses distinct; task state is not automatically reusable memory. Workers receive selected task-relevant artifacts, not the entire history. Account for inherited/forked context and data recipients separately.

### Procedure

1. Build a compact state record: approved objective/non-goals, acceptance status, owners, accepted dependencies, current artifact versions, open defects, blockers, uncertain actions and remaining authorized resources. Link detailed evidence rather than copying every transcript.
2. At a decision boundary, update state from actual returned artifacts and observations. Retrieve original sources when a conclusion matters; repeated claims do not become verified facts.
3. Identify the next useful bounded unit: resolve a dependency, implement, inspect, verify or deliver. Explain its contribution to unmet acceptance and choose the smallest suitable stage topology.
4. Dispatch under the common contract, checking readiness, ownership, effective permissions and context recipients. Parallel stages still need at least two independent, non-overlapping units; evaluator stages still need clean inputs.
5. Integrate returned work and record actual results, rejected hypotheses and remaining gaps. Preserve candidate versions; do not assume the newest artifact is the best supported deliverable.
6. If continuing after interruption/compaction/transfer, read the compact state and required evidence, verify relevant freshness, and preserve unresolved external effects. Use a clean session only when justified by actual context needs and approved runtime capabilities, not a periodic reset rule.
7. Stop when all original acceptance is evidenced, or report partial/blocked at a real boundary. The controller owns final integrated verification even if many local units passed.

### Acceptance evidence and stop boundaries

Passed requires original acceptance on the selected integrated deliverable plus enough state/evidence for another authorized owner to understand what was actually done. State files, task-list ticks and candidate coverage are not completion evidence themselves. Stale/missing artifacts, unverified selection or remaining required milestones mean partial. Missing state essential to safe continuation, inaccessible prerequisites or uncertain actions that cannot safely be repeated mean blocked for dependent work. Never resume by guessing authority or launching a replacement for an ambiguous existing action.

**Sources:** [meta-control-2026](research.md#meta-control-2026) on staged control, compact state and selected artifacts (combined intervention; equal call allowances are not equal token cost); [openai-harness-2026](research.md#openai-harness-2026) on repository-local knowledge and plans (case study, not permission to merge/deploy); [scalemas-2026](research.md#scalemas-2026) on persistent linked artifacts and bounded retrieval (candidate coverage is not final selection); [containment-2026](research.md#containment-2026) on persistent poisoning/trust escalation.

## adaptive-optimization

**Purpose and topology:** adapt the work arrangement in response to measured optimization bottlenecks without changing the objective or correctness constraints. Topology: choose `solo`, `sequential`, `parallel` or `generator-evaluator` for the current stage. Suitable categories: authorized optimization-oriented `implementation`, `debug`, `design` or `research`, not ordinary feature completion by default.

### Select and avoid

Select when there is a valid correctness oracle, representative workloads, a comparable objective metric and an observed plateau or changed bottleneck that warrants a different approach. Avoid if the task lacks repeatable evaluation, only confidence suggests a plateau, or experiments need unapproved hardware, agents, services or spending. A fixed team and continuous cron/controller service are not required.

### Inputs, context and ownership

The supervisor owns the unchanged user objective, correctness constraints, baseline artifact, workload set, measurement procedure, environmental assumptions, authorized resource/iteration limits and final selection. Record success thresholds and regression tolerances before search. Preserve candidate artifacts and empirical results separately from hypotheses and reusable lessons. Workers get selected relevant successes/failures with evidence; inspect inherited context, actual tool access and data recipients before any reconfiguration.

### Procedure

1. Establish a correct baseline using the approved oracle. Measure the baseline under the stated environment and workload protocol; record raw results and known variability. If correctness or baseline measurement is unavailable, do not claim optimization progress.
2. Try a bounded hypothesis tied to the objective, with a named owner and controlled comparison. Reuse the simplest fitting template arrangement; keep an accepted correct candidate available.
3. Evaluate correctness before interpreting performance. Compare equivalent workloads/environment and disclose changes in resources, measurement procedure or selection. Do not hide regressions behind an aggregate score or treat best-of-several as a typical run.
4. At the agreed checkpoint, diagnose actual results: knowledge gap, correctness blockage, measurement noise, exhausted local search or a newly changed bottleneck. A slow result is not by itself proof that more agents help.
5. If warranted and authorized, change the narrowest useful aspect: role, context selection, hypothesis, ordering, isolation or evaluation. Record the diagnosis and proposed benefit. New workers, models, resource use or recipients outside approval need new consent; organization changes never expand the task.
6. Preserve confirmed observations, rejected approaches, candidate versions and the reason for each arrangement change. Use independent review for consequential correctness claims; parallel candidates require non-overlapping scopes and an integration/selection owner.
7. Stop at the original target, the authorized experiment limit, lack of a justified next experiment or an unavailable prerequisite. Select the best candidate supported by the original correctness and performance criteria, not the latest or most confidently defended output. Validate the final candidate under the agreed protocol.

### Acceptance evidence and stop boundaries

Passed requires the user's correctness and optimization target on the selected deliverable, comparable baseline/final measurements, disclosed variability and required regression checks. A correct but below-target candidate, unsupported speedup, partial workload coverage or exhausted allowance means partial, not success. Missing oracle, inaccessible authorized hardware or unapproved additional resource use means blocked for the affected experiment. A plateau permits diagnosis, not endless retries, relaxed correctness or benchmark manipulation.

**Sources:** [eat-2026](research.md#eat-2026) on diagnosis-driven team adaptation for optimization (few main kernel tasks, best-of-two; extended-budget records are not matched-budget effects); [meta-control-2026](research.md#meta-control-2026) on next-action selection and artifact reuse; [containment-2026](research.md#containment-2026) on effective access boundaries. These do not establish broad feature-development superiority or authorize GPU/model launches.
