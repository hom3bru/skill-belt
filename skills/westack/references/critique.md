# Independent critique (C8)

Independence is a level, not a label: self, fresh-context-same-model, different-model or human ([vocabulary](evidence-vocabulary.md)). A persona name or a second pass in the same context stays self.

Fresh means fresh: a new agent given the brief only, never a fork or resume of the author's context. Record in the review receipt's `coverage` how it was spawned, which instruction and memory files it could read and the reviewing model and vendor (falling back to the author's family is fresh-context-same-model at best; a failed one is not-run, never approval); if a reachable file holds the author's conclusions (handoff note, task record, memory entry), the level is self.

## Review packets

Give the reviewer the goal, the constraints, the patch or document, the raw evidence and inputs each question needs. Withhold the author's conclusions, self-assessment and preferred verdict: a reviewer handed the answer tends to return it. A packet trimmed to fit follows the trimming rule in [evidence](evidence.md). The reviewer returns the inputs it actually read, each with a non-error tool result; an unread required input means not-run, never zero findings. A read shows access, not understanding.

## Validate each finding

- Before a finding counts, a different context re-derives it from its claim, location and trigger, trying first to disprove it. Only survivors are adjudicated, at the validating review's level.
- Goal judge: check the result requirement by requirement against evidence. An unparseable verdict means not done.
- Bound the rounds before the first: the default cap is five review-and-revise rounds (the user may set another). End each round with `round N: unresolved U, new W`; the loop has stalled when `U` has not fallen for two rounds, read from those lines, never by counting an accumulating file. At the cap, on a stall, or when a round finds nothing new, stop as needs-decision and ask the user. A result reached at the cap is inconclusive, never clean.
- Reviewer agreement does not settle contradictory evidence; evidence does. Sampling several candidates and voting is optional for a high-stakes patch.

## Cross-model critique sends data to another vendor

A different-model review through another tool (for example `codex exec`, `gemini -p` or `claude -p` from a different host) sends code or documents to that tool's vendor. Before the first such call in a repository, say which vendor receives what and get the user's consent for this repository (not saved unless the user asks). Run the other tool read-only or sandboxed, never with an approval-bypass or "dangerous" flag. Without consent, or with the tool missing, record that review level as not-run, never a quiet same-model run. A relay returns the tool's output unchanged, as data.

Provenance: C8 in provenance/facility-donors.json.
