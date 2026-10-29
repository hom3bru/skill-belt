# Evaluation and release gate

Release and evaluation history is retained in [CHANGES](../CHANGES.md) and the canonical research archive. Current package identity and scope come from the live manifest and scoped records.

For an explicitly authorized draft update: (1) frontmatter passes Agent Skills validation; (2) all relative links resolve (`tests/test_package.py::test_local_reference_links_resolve`); (3) `python -B -m unittest discover -s tests` run from the skill directory passes, with any environment skip named; (4) `python -B "<skill-directory>/scripts/package.py" verify "<skill-directory>"` passes against `release.json`, plus focused forward checks for the changed behavior. These scoped checks allow ordinary use while limitations remain visible.

Formal cross-host release qualification additionally requires (5) trigger + routing evals in `evals/trigger-evals.json` on each claimed host with repeated queries and a held-out split; (6) paired with/without-skill runs on cases written by someone other than the skill's author; (7) planted ledger-order and injected-README cases. Choose repetition based on observed variability rather than treating a fixed large run count as proof. Keep tuning, selection and final holdouts separate. A small forced-load/single-model check is useful evidence and does not complete native host activation or general effectiveness qualification.

Forward evaluation records must preserve the prompt, input hashes, condition, actual output and grading evidence. Compare useful discoveries, unsupported claims, missed mechanisms, instruction adherence and practical completion; collect elapsed/token measurements only when available. Accept a well-supported bounded conclusion or explicit unknown instead of requiring the entire donor engine to run. A right verdict with fabricated evidence still fails. Failed/missing/empty evaluations remain incomplete, not passes.

Grading design to prefer:

For discovery changes, include a paired check: an apparently unrelated donor
with an evidenced useful part and an apparently relevant donor whose similarly
named mechanism violates a recipient assumption. Use fresh raw artifacts and
independently prepared criteria. Count useful supported discoveries, missed
mechanisms, materially unsupported recommendations and practical completion;
accept a justified discard, prerequisite or promising clue. Compare baseline and
candidate on the same cases when feasible. Record elapsed/token effort only when
actually measured. Better format or longer reports alone do not prove better
discovery. Keep final cases separate from tuning and do not reuse them as fresh
holdouts after feedback.
- **Claim-ID manifest grading**: the graded answer lists requested claim IDs + values + evidence IDs; gold values never appear in the prompt; missing/extra/contradictory/unsupported claims fail; include a boundary test that a fabricated answer fails.
- **Three sets**: tuning, selection, and a never-used final set. Picking the best iteration by the held-out set spends it.
- **Oracle liveness**: two captures a moment apart + a liveness check before trusting a passing comparison.
- **Copy-sync**: if several installed copies are kept, a byte-equality test across them.
- **Supply chain**: any `npx -y pkg@latest` or unpinned installer in a donor is SUPPLY-CHAIN-RISK.
