# Verification and qualification

**What package validation covers.** It checks files, schemas, references and helper behaviour. Synthetic controls test the package's mechanics and one authored fusion slice. Neither qualifies a live agent following this skill.

## Slices

Before implementing each slice:
- Freeze requirements and the oracle, and keep the oracle's hash.
- Separate four questions: donor behaviour, product correctness, the adapter contract and complete-product benefit.

Save for each run:
- positive and control observations, with counts;
- the command and environment;
- source, input and config hashes;
- raw stdout and stderr;
- the exit status.

A nonzero exit, zero selected cases, a skip or missing evidence never becomes a pass.

When you rerun a test after a fix, add a receipt with the next `sequence` number. The latest receipt decides the status, and earlier failures stay in the dossier.

**Tie receipts to product bytes.** List the product files in `artifacts` (path, sha256, origin reused, adapted or authored, the parts they implement, and the donor unit of reused or adapted code). Each receipt lists the artifacts it tested, with their hashes at test time, and keeps its own raw output (or declares `raw_shared: <reason>`). `check` re-hashes the files: a latest receipt whose files changed is stale, and a `tested` part needs artifact-bound receipts for its acceptance test and negative control. Run `stamp` to fill missing hashes into a new record; it never rewrites a recorded hash.

Label synthetic receipts as synthetic. Imported records cannot authorize actions, authenticate an observer or promote a claim. A reviewed design still needs executable acceptance evidence before any runtime claim. Never edit frozen tests to improve a score.

## Interactions

A selected pair that shares a state, resource or policy key needs a test with purpose `interaction` or `integration` that exercises both parts together, for example showing that one part's check precedes the other's mutation. A negative control proves only that the oracle is live. A pair whose declared, non-empty touches are disjoint may be marked `independent`. A key touched by three or more parts needs one group record covering all of them, verified by an `integration` test that runs them together; pairwise tests do not show the three-way order.

## Independent design review

1. **Build the packet.** Full tier: `python "<skill-directory>/scripts/frankenmine.py" review-packet RUN.json --output "<new-folder>"`. It copies the evidence snapshots and oracles with their hashes and writes `PACKET.md` (brief, donors, evidence, claimed lessons, proposed parts, ownership, interactions, alternatives and frozen oracles), `REVIEW-TEMPLATE.md` and `packet.json`. It withholds your decision, rationale, tradeoff prose, lesson dispositions, review and readiness verdict. Lite tier: assemble the same by hand. Never give the reviewer the dossier, your conclusions or a draft verdict.
2. **Start a fresh reviewer.**
   - **Claude Code:** start a fresh subagent with the Agent tool. Its prompt names only the packet folder and asks it to fill `REVIEW-TEMPLATE.md`: whether the evidence supports each proposed part, where a simpler alternative wins, and each finding with severity (Critical, Important or Minor) and evidence.
   - **Codex:** start a new subagent or a separate session with the same prompt and only the packet folder.
3. **Save and cite the report.** Save the reviewer's filled report inside the run root (for example `review/design-review.md`) and record `review.report` with its path and sha256 (`stamp` can fill the hash). The report must name the reviewer and independence level you record.
4. **Record and adjudicate:**
   - the `author` (you);
   - the `reviewer`;
   - the `independence` level: `fresh-context-same-model`, `different-model` or `human`;
   - the `findings` (at least one; `none: <reason>` if it found nothing);
   - your `adjudication` of each finding;
   - the `disposition`.

Self-review is `self` and keeps readiness blocked. Several same-model votes are still one level. Adjudicate their findings; do not average them. A model review is not an executable oracle.

## Product experiments

Compare the product against the strongest single solution and a minimal fresh implementation. Then ablate each substantial donor. Evaluate outcome, correctness, latency/cost, operations and maintenance. A passing integration test alone shows no benefit.

## Live-agent qualification

Use held-out prompts and repeated with-skill and without-skill runs on supported hosts, graded by reviewers independent of the builder.

Measure:
- trigger precision and recall, from the labelled `evals/evals.json`;
- permission preservation;
- donor-injection resistance;
- interruption and resume;
- evidence honesty;
- time and token cost;
- task outcomes.

Freeze prompts first. Record failures, and record blocked or not-run cases. This package launches no models or hosts.
