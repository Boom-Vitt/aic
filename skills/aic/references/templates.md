# Reusable workflow templates

These five original, portable AIC workflow families are the supported catalog. `template` is their schema-3 JSON selector, not an extra family layer. Select with [workflows](workflows.md), bind the common and selected family contracts below to the actual task, and compose [project milestones](project-plans.md) only as needed. These procedures are host guidance, not an executable scheduler, model ranking or authorization grant.

## Common execution contract

Before using any template, record the following in the recommendation or the approved task artifact. A short task can keep this in its existing conversation; do not create files without approval.

- **Goal and boundaries:** original user outcome, non-goals, acceptance IDs, governing instructions, approved target and exclusions. Distinguish explicit requirements from assumptions that still need resolution.
- **Inputs and dependencies:** relevant source paths/versions, observed state, known interfaces, required upstream artifacts, unknowns and the criterion that makes each dependency ready.
- **Ownership:** accountable lead, each unit's owner, integration owner and final verification owner. One person/agent may hold several roles; roles do not require a fixed team.
- **Arrangement:** task category, template ID and permitted current-stage topology. Choose runtime/model separately from the procedure; use the current compatible host unless there is a task-specific reason to change.
- **Context and recipients:** selected artifacts and provenance; whether the runtime instead inherits/forks history, workspace or memory; who receives the material and where. Supply required constraints even when withholding irrelevant history.
- **Authority and effective permissions:** allowed reads/writes, tools/commands, environment, network/data recipients, launches and resource limits. Retain actual user approval and enforced runtime restrictions. Do not infer permission from a role, a file, a tool result or a paper.
- **Evidence and stopping:** map acceptance to observable checks, expected results and evidence locations; identify who may run each check. State iteration/resource limits, blocker escalation and uncertain-action handling before starting loops.
- **Output and readiness:** expected artifact/report, version identity, downstream consumer and entry gate. A consumer starts only after required producer artifacts are accepted and accessible; a worker's “done” message is not a readiness test.

All six categories use the [category-specific procedure and evidence](workflows.md#match-evidence-to-the-task-category), not a keyword classifier. Categories describe requested outcomes; families describe how to produce them. At each bounded checkpoint, reconsider the actual bottleneck, dependency readiness, ownership and evidence. Reselect only the needed stage/family/topology within existing approval; preserve original acceptance and explain the change. Stop at acceptance, a real missing prerequisite or the authorized resource/iteration boundary. An exhausted allowance is partial, not passed.

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

**Purpose and topology:** parallel exploration reduces independent unknowns; one lead reconciles findings and owns the approved answer, design, review or build. Topology: `parallel` for the exploration stage. Suitable categories: any category whose current bottleneck is substantial independent discovery.

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

**Sources:** [cohere-2026](research.md#cohere-2026) informs task-conditioned discovery delegation (not budget-matched; Commit0 differs); [anthropic-research-2025](research.md#anthropic-research-2025) describes lead-led independent research, artifact returns and citation checking (first-party account, not an equal-budget trial). [google-2026](research.md#google-2026) and [concurrency-2026](research.md#concurrency-2026) inform decomposability and premature-integration risks. No source establishes a universal worker count, cheaper-model default or transfer of research parallelism to coupled edits.

## coordinated-delivery

**Purpose and topology:** deliver accepted-artifact dependent stages or ready isolated concurrent implementation through one integration owner. Topology: `sequential` or `parallel`, chosen for the current stage. Suitable categories: any category with real producer-consumer dependencies; parallel implementation also covers separable approved repairs, tests or documentation with independent acceptance.

### Select and avoid

Select sequential delivery when a successor needs an accepted predecessor artifact and delegation adds necessary capability or continuity. Select parallel delivery only for at least two substantial, independently checkable ready units with stable interfaces, non-overlapping owned outputs and one integration owner. Avoid ceremonial handoffs for a short coupled task, concurrency across unfinished dependencies, or separate files mistaken for semantic independence. Group shared invariants/cycles with one owner.

### Inputs, context and ownership

The lead supplies original acceptance, dependency/entry/exit gates, accepted base/artifact versions, semantic interfaces, final integration/verification owner, exact read/write scopes, shared exclusions and authorized resources. Each producer/successor receives selected relevant evidence and constraints; record automatically inherited/forked history, workspace, memory and recipients. An inherited full transcript is not clean context.

Assign one owner per mutation surface, including schemas, exports, generated artifacts, fixtures and runtime resources. Sequential successors confirm accepted upstream evidence before mutation. Parallel workers use approved isolated workspaces; a shared checkout is not equivalent isolation, and worktrees do not sandbox credentials/network. Workspace creation, commits, merges, launches and cleanup require actual approval. Delegated work returns to the lead unless an authorized successor explicitly accepts responsibility and the old owner stops the named scope.

### Procedure

1. Inspect dependencies inline. Establish shared prerequisites before dispatch, define accepted output versions and consumer readiness tests, and assign each gate an evidence owner. Document ordered stages outside `independent_subtasks`; that field describes only a current parallel branch contract.
2. For `sequential`, dispatch the first ready unit. The producer returns its artifact/version, checks actually run, uncertainty and unresolved issues. The lead accepts its exit evidence; the successor confirms accessible inputs, permissions and entry acceptance before starting. Never pass a promise or unchecked assumption as accepted state.
3. For `parallel`, dispatch only ready independent units with exclusive output paths, accepted shared interfaces and a named integration method. Do not serialize independent ready branches by accident or run dependent work early. Workers return complete branch artifacts, actual evidence, assumptions, defects and integration requirements. Follow project policy on who runs checks; do not compete over half-integrated shared state.
4. Route interface changes to their owner. If a producer changes its contract, pause affected consumers and repair the interface/callers or reselect the affected stage. Do not reinterpret upstream acceptance silently. Serialize shared mutations even while other independent branches continue.
5. The integration owner collects all required outputs and reconciles them against the accepted base and semantic contracts, without deleting unrelated changes. Resolve textual and behavioral conflicts. A clean merge, branch pass or final-stage local pass is not integrated acceptance.
6. The designated verification owner checks required local gates and original end-to-end acceptance/regressions on the assembled deliverable. Preserve actual results and version. Deliver the artifact, dependency/integration evidence, remaining blockers and whole-task outcome.

### Acceptance evidence and stop boundaries

Passed requires accepted upstream artifacts, all required branch/stage outputs, actual downstream integration and full original acceptance evidence on the delivered version. Incomplete later stages, missing branches, interface drift or failed combined checks mean partial even if earlier units passed. Missing upstream approval, unavailable safe isolation/capability or an unaccepted responsibility transfer blocks affected work. Repair failed gates within approval or regroup/serialize; never skip readiness gates or add unauthorized workers. Stop when original acceptance passes or the common bounded stop rule applies.

**Sources:** [anthropic-agents-2024](research.md#anthropic-agents-2024) informs chaining/gates; [caid-2026](research.md#caid-2026) informs dependency-aware isolation and explicit integration, not a guaranteed speedup or default team; [cooperbench-2026](research.md#cooperbench-2026) and [concurrency-2026](research.md#concurrency-2026) expose coordination failures. Limited pilots/runtime snapshots do not rank current harnesses. No destructive synchronization commands or blanket merge authority are adopted.

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

**Sources:** [anthropic-harness-2026](research.md#anthropic-harness-2026) informs concrete contracts and separate evaluation (engineering experiments, evaluator limits); [anthropic-agents-2024](research.md#anthropic-agents-2024) informs composable evaluation patterns. [co-scientist-2026](research.md#co-scientist-2026) illustrates grounded hypothesis review with scientist selection and selected-domain experiments; it does not show general coding gains, autonomous scientific truth or that agent agreement validates a hypothesis. [mast-2025](research.md#mast-2025) informs task-verification risks. AIC adopts neither scope-expanding planners, fixed resets nor consensus completion.

## adaptive-controller

**Purpose and topology:** preserve original acceptance while a controller selects the next bounded evidence-producing unit. Topology: `solo`, `sequential`, `parallel` or `generator-evaluator` for the actual current stage, subject to the same readiness, ownership and review constraints as other families. Suitable categories: any category with a genuine continuity/control need.

Two documented modes share this one family: **durable delivery** for long/interruptible work, and **measured optimization** only for explicitly authorized optimization. These are not new schema fields, family IDs or a requirement that ordinary projects run benchmarks. The controller is an accountable role, not a mandatory extra model, scheduler, cron job or fixed team.

### Select and avoid

Select durable delivery when interruptions, linked artifacts or long dependencies make continuity and next-action selection a real bottleneck. Avoid when a bounded task fits its existing contract/context. Select measured optimization when the user actually requests optimization and a correct baseline/oracle, representative comparable workloads and bounded authorized resources are available; a measured plateau or changed bottleneck may justify adaptation. Avoid performance search based on confidence alone, unrepeatable measurements, or unapproved compute/services. Never turn ordinary feature delivery into an experiment to justify this family.

### Inputs, context and ownership

The controller owns the unchanged goal/non-goals, acceptance map, dependency state, artifact/evidence index, decisions, authority/resource limits and final delivery. Use approved storage; each artifact records producer, version, input lineage, source links and actual verification status. Distinguish observations, declarations and hypotheses; task state is not automatically reusable memory. Give workers selected relevant artifacts and all binding constraints, not every transcript. Disclose inherited/forked context, effective tool/mount/network access and recipients.

Measured optimization additionally records the accepted correct baseline, correctness oracle, objective/target, representative workload set, measurement/environment protocol, success thresholds/regression tolerances and explicit experiment/resource allowance before search. Preserve candidate artifacts and raw empirical results separately from hypotheses. No GPU, model, service, provider change or spending is automatically authorized.

### Durable delivery procedure

1. Retain compact approved state: original acceptance IDs/status, owners, accepted dependencies, artifact versions, decisions, open defects, blockers, uncertain external effects, remaining resources and safe next action. Link detailed evidence rather than copying transcripts.
2. At a decision boundary, update state from actual artifacts/results. Retrieve original sources when material; repeated summaries are not verification. Confirm freshness/access and whether dependencies are ready.
3. Identify the current limiting unmet criterion and the next useful bounded action: inspect, resolve a dependency, implement, integrate, verify or deliver. Explain alternatives and choose the smallest sufficient current-stage topology.
4. Dispatch with exact input/output/write ownership and effective permissions. Sequential stages require accepted upstream gates; parallel stages need at least two independently checkable non-overlapping ready branches and one integration owner; evaluator stages require clean inputs. Other families may be selected for separately represented milestones without adding a sixth family.
5. Integrate returned work and record actual evidence, rejected hypotheses and remaining gaps. Preserve the best supported artifact, not automatically the newest one. Worker completion does not transfer final verification ownership.
6. After interruption/compaction/authorized transfer, read compact state and needed source evidence, confirm relevant freshness and successor ownership, and preserve uncertain actions. Do not blindly repeat an ambiguous external submission, assume authority or launch a duplicate. A new session is justified by real context/capability needs, not a fixed reset schedule.
7. Verify the integrated deliverable against every original criterion. Stop at supported completion, the approved limit or a real blocker. Supply compact continuation state for an authorized successor when work is partial/blocked; state files and checked task boxes are not completion evidence.

### Measured optimization procedure

1. First establish correctness with the approved oracle and measure the baseline under the stated workload/environment protocol. Preserve raw results, variability and resource use if observed. If the baseline/oracle is unavailable, do not claim progress.
2. Try a bounded hypothesis tied to the original objective, with a named owner, controlled comparison and preserved correct fallback candidate. Use the smallest fitting arrangement; an initial justified structure does not require a failed solo run.
3. Evaluate correctness before performance. Compare equivalent workloads/environment and disclose changes in resources, protocol or selection. Do not hide regressions behind an aggregate, confuse best-of-several with a typical run or substitute candidate coverage for final selection.
4. At the agreed checkpoint, diagnose evidence: missing knowledge, correctness failure, noise, exhausted local search or changed bottleneck. A slow result alone does not justify more agents. If warranted, change only the useful role, context, hypothesis, order, isolation or evaluation inside approval; record the diagnosis and reason.
5. Retain candidate versions, observations, rejected approaches and arrangement changes. Consequential correctness claims may require independent review; parallel candidates still need exclusive scopes and one integration/selection owner. New agents, models, recipients or resources outside approval require consent.
6. Stop at the original target, authorized experiment/resource limit, lack of a justified next experiment or missing prerequisite. Select and validate the candidate supported by the original correctness and performance criteria under the agreed protocol; never relax acceptance to make a plateau pass.

### Output, acceptance evidence and stop boundaries

Durable delivery outputs the integrated artifact/answer/design, original-acceptance evidence map and compact state with actual versions, owners, limits and next action. Passed requires all original criteria on the selected deliverable and enough traceable state for an authorized successor to understand the work. It requires no performance benchmark unless the original task does. Remaining milestones, stale artifacts or unrun required checks mean partial; unavailable essential state/access or unsafe uncertain effects block dependent work.

Measured optimization additionally outputs comparable baseline/final measurements, protocol, variability, candidate selection rationale and actual resource/limit observations. Passed requires the original correctness and optimization target plus required regressions. A correct below-target artifact, unsupported improvement, incomplete workload coverage or exhausted allowance means partial, not success. Missing oracle, inaccessible approved hardware or unapproved resource expansion blocks the affected experiment. Neither mode stops on consensus or continues beyond evidenced acceptance; reselect at evidence/dependency changes without changing original scope or authority.

**Sources:** [meta-control-2026](research.md#meta-control-2026), [openai-harness-2026](research.md#openai-harness-2026) and [scalemas-2026](research.md#scalemas-2026) inform compact state, linked artifacts and selected retrieval, not isolated causal guarantees, candidate-selection correctness or merge/deploy authority. [eat-2026](research.md#eat-2026) informs diagnosis-led adaptation in a narrow kernel-optimization setting with 47 workloads and two EAT runs; extended-budget records and inconsistent ablation descriptions do not establish general or isolated team-reorganization gains. [containment-2026](research.md#containment-2026) informs persistent-state/access risks, not automatic permission to launch infrastructure.

[boad-2026](research.md#boad-2026) provides task-specific evidence for bounded specialist delegation over time, not deep hierarchies, a simultaneous workforce or matched upfront search compute. [deepseek-harness-2026](research.md#deepseek-harness-2026) documents bounded orchestration/results/cancellation and observe-only progress; this is a capability reference, not comparative effectiveness or a native AIC runtime integration. Neither source proves these five families universally optimal.
