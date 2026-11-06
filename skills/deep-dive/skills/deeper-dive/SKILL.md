---
name: deeper-dive
description: "Use when the user asks to 'go deeper', 'dig further' or 'deeper dive' on a topic that already has a deep-dive report. Works from that report's coverage map and log: searches the categories and branches the first pass did not reach, follows the consequential leads recursively, tests distinctions and claims against primary sources, and appends a dated section to the same report. A deep-dive sub-skill: run deep-dive first if no report exists. Not for one fact (westack-research) or a first survey (deep-dive)."
metadata:
  version: "0.1.0"
  parent: deep-dive
---

# deeper-dive

Depth, not volume. A deeper dive goes where the first pass did not: the categories it never searched, the branches it saw but did not follow, and the claims it could not verify. It never re-runs the first pass's queries in other words. Everything in deep-dive's standards still applies; the method is §8 of deep-dive's [playbook](../../references/playbook.md).

Use the shared [user profile](../../references/user-profile.md) for personal values and local paths.

## Steps

1. **Load the first pass.** Open the existing `REPORT.md` and `log.md` in `<research_root>/<date>-<topic>/` (find it with Palette if needed). No report means run deep-dive first. A report with no coverage map means rebuild the map from its log and sources before searching, and say you had to.
2. **Choose targets from the map.** List, with a reason for each:
   - categories marked **not searched** or **partly searched** that could change the decision;
   - **branches seen but not followed**;
   - claims marked *unverified* that the recommendation leans on;
   - the decision's weakest point: the evidence most likely to be wrong.
   Write the targets and the queries you will not repeat into `log.md` before searching.
3. **Go deep on each target** (playbook §8):
   - follow citations backward to foundations and forward to refinements and rebuttals;
   - follow repositories to dependencies, forks, dependents and successors; check whether tools that look different share an upstream model, dataset, library or backend;
   - search other disciplines, other terms, other languages and other eras for the same problem;
   - read the most consequential papers, appendices, code, tests, datasets and primary records in detail, tracing claims to their definitions and methods;
   - look for evidence against the preferred option: failure reports, reproducibility problems, negative results, dead predecessors, terms and practical blockers.
4. **Combinations, where the question is a design.** Component and method combinations, deterministic and hybrid alternatives, integration seams and prerequisites, each with a concrete evaluation design. A proposed fusion is a hypothesis until tested; hand real fusion design to frankenmine and borrowing for one project to adopt-adapt.
5. **Append, correct, update.** Add `## Deeper dive <YYYY-MM-DD>` to the same `REPORT.md` with each lineage chain (source, relationship, finding, why it matters). Correct earlier claims in place, marked `(corrected <date>)`, never silently. Update Top picks, Recommendation, the coverage map and Gaps. Log every query.
6. **Saturation.** Say which lanes are now explored, what remains, and whether more depth could still change the decision. If it could not, say so and stop; do not pad.
7. **Save and read back** as in deep-dive, and save any new sources relied on to Palette with why.
8. **Check work** on the deeper-dive section and everything it changed, using the [check-work](../check-work/SKILL.md) sub-skill. The skip rule is the same as in deep-dive.

## Traps

| Rationalization | Reality |
| --- | --- |
| "Deeper" means more of the same searches. | Re-asking the first pass's questions in new words is not depth. Targets come from the coverage map. |
| Adding twenty more tools. | A deeper dive that does not change, confirm or sharpen the decision has not done its job. |
| Leaving a wrong earlier claim in place. | Correct it in place and mark it; the report is the record. |
| "No results, so nothing exists." | An empty index or a failed fetch proves nothing (playbook §6). Record it as blocked or not found. |
| "Complete census." | Only with a defensible method; otherwise describe saturation honestly. |

## Reply

Lead with what changed: new leaders, corrected claims, and whether the recommendation moved. Then the saturation call, the remaining gaps and the report path.
