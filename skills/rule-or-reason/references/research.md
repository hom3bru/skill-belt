# Research basis and limits

Primary sources were reviewed November 2, 2026. This skill uses operating lessons, not donor code. Author-reported empirical results were not reproduced during research.

| Source | Lesson used | Limit retained |
| --- | --- | --- |
| [TraceCompiler, August 2026](https://arxiv.org/html/2608.02680v1) | Evidence-backed argument provenance, separating retries/loops, explicit uncertainty | Its limitations report narrow end-to-end evidence, incomplete auditability, and no net efficiency result |
| [Skill-DisCo, June 2026](https://arxiv.org/html/2606.26669v1) | Parameterized procedural structure, interfaces, pre/postconditions, execution-grounded verification | Procedural scope; model skill selection remains; later publication should not be assumed identical |
| [SemBaker, August 2026](https://arxiv.org/html/2608.06677v1) and [source](https://github.com/iDB-Research-Group/SemBaker) | Operator-level conversion and amortization; inspectable intermediate representations | Current heuristic eligibility, pseudo-label agreement, and direct generated-code execution do not establish semantic fidelity or containment |
| [SemPipes, February 2026](https://arxiv.org/html/2602.05134v1) | Fit-time synthesis and downstream evaluation | Generated implementations may use pretrained models |
| [CACHE-ED2, 2026](https://www.amazon.science/publications/cache-ed2-compiling-llm-reasoning-into-reusable-extraction-programs-for-document-extraction-at-scale) | Reusable extraction programs and program-level corrections | Format-specific scope, learned format routing, and workshop evidence do not establish model-free general extraction |
| [Compiled AI, July 2026 revision](https://arxiv.org/html/2604.05150v2) | Separate deterministic orchestration from remaining semantic model tools | Its mixed document task retains inference; compilation is not universal model removal |
| [ASI, 2025](https://arxiv.org/html/2504.06821v1) | Executable program skills and validation trajectories | Model-based episode filtering is not independent ground truth |
| [NSI, May 2026](https://arxiv.org/html/2605.01293v1) | Explicit state, conditions, variable binding | Released induction and evaluation still make model calls |
| [Same Query, Different Answer, October 2026](https://arxiv.org/html/2610.13823v1) and [artifact](https://github.com/semviews/sqp-variance-study) | Per-item outputs, repeated baselines, answer reproduction separate from scores | Published observations have their own workloads/deployments and are not measurements of a new candidate |
| [SemBench, March 2026 revision](https://arxiv.org/html/2511.01716v2) | Diverse semantic-operator workloads and explicit evaluators | External benchmark data need their own rights, contracts, and suitability checks |
| [Evaporate, 2023; revised 2025](https://arxiv.org/html/2304.09433v3) | Direct extraction versus generated functions and weak supervision | Teacher-output scoring does not establish independent correctness |
| [TWIX, 2025; revised 2026](https://arxiv.org/html/2501.06659v2) | Recover repeated input structure before repeated extraction | Same-template visual documents differ from arbitrary prose |

Practitioner sources: [AgentRun Show HN](https://news.ycombinator.com/item?id=49821438), [LogicPearl Show HN](https://news.ycombinator.com/item?id=47764455), and [Modiqo's trace/procedure article](https://modiqo.ai/blog/extract-a-reusable-procedure-from-an-agent-trace). These supply implementation questions and first-party descriptions, not independent comparative evidence.

A maintainer's [Palimpzest removal PR](https://github.com/mitdbg/palimpzest/pull/198) establishes that code synthesis was removed at one revision; it does not establish why or the state of every later branch.

Selection: a minimal fresh skill using these pattern-only lessons. No donor runtime, dependency, service, or code port is included. This is a combination of ideas and evaluation discipline, not a measured superiority claim over the cited systems.
