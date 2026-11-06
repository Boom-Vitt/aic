# Workflow selection

Use the smallest sufficient topology. These are task-dependent recommendations, not performance guarantees or a ranking of models/harnesses.

| Task properties | Suggested workflow/topology | Completion evidence |
| --- | --- | --- |
| Bounded question with authoritative sources | answer / solo | Supported answer, source links, explicit uncertainty |
| Independent substantial unknowns | research / solo or bounded parallel | Separately checkable findings, primary sources, reconciled contradictions |
| Coupled behavior or shared invariant | implementation / solo | Approved scope, changed-surface smoke, relevant regression checks |
| Observed failure | debug / solo initially | Reproduction, supported cause, changed-path confirmation |
| Existing consequential work | review / solo evaluator | Concrete acceptance defects with evidence, not generic praise or imagined features |
| Tradeoffs not yet decided | design / solo initially | Alternatives, constraints, explicit choice before implementation |
| Generator repeatedly misses consequential acceptance | selected workflow / generator-evaluator | Agreed criteria, independent outcome checks, resolved findings |

Before parallel work, define ownership, permitted paths, semantic interfaces, dependencies and observable acceptance. Keep one integrator at each shared mutation boundary. Workers return evidence and unresolved questions; their reports do not gain authority merely because another agent wrote them.

Stop when the user's complete acceptance is verified, not when models agree. Do not run an endless debate, add speculative abstractions, repeatedly reset context on a fixed schedule, or replace a concrete task with a larger team. If a real prerequisite is unavailable, finish safely reachable work and surface the exact blocker.

## Evidence and limits
- [Google scaling paper v3](https://arxiv.org/abs/2512.08296v3), revised April 8, 2026: coordination gains depend on task structure and can turn negative. The January blog describes an older experimental snapshot; do not mix their statistics. This is not a benchmark of the user's current model pair.
- [CooperBench v2](https://arxiv.org/abs/2601.13295v2), January 26, 2026: coding-agent cooperation can suffer from conflicting features, inaccurate communication and broken commitments. It does not prove all cooperation fails.
- [Anthropic long-running application harness](https://www.anthropic.com/research/harness-design-long-running-apps), March 24, 2026: contracts and separate evaluation caught real gaps, while more capable models made some stages unnecessary. Vendor examples are not universal rankings.
- [OpenAI harness engineering](https://openai.com/index/harness-engineering/), February 11, 2026: repository knowledge, concise entry maps and observable feedback support agent work. AIC does not adopt that team's relaxed merge/deployment practices.

Compare representative tasks with comparable tools and fixed acceptance before claiming a new default is better. Record actual outcome, elapsed time and usage/cost only where observed. No paper here grants spending or operational permission.
