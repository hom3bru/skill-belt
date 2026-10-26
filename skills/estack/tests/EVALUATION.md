# Evaluation boundaries and replay

Run `python tests/run.py` from the skill directory. It uses Python's standard library, runs named unittest cases, fails if zero tests are collected, and prints counts. Tests run in disposable temporary directories; no network, models, credentials or donor code are used. The suite exercises package contracts and real synthetic behavior, not model judgment. Frozen expected fixtures live under fixtures; malicious text remains data.

[acceptance-cases.json](acceptance-cases.json) preserves the supplied pilot intent, fixture and oracle summaries; it is an independently serialized implementation mapping, not a byte-identical copy of the parent JSON. [acceptance-results.json](acceptance-results.json) separates deterministic coverage from full-case qualification. E01/E03 require human judgments. E06 requires evaluator independence beyond metadata. E12 requires a real independently configured host denied-path boundary and remains blocked/unsupported. E20 includes only synthetic test-only credential text that no helper consumes.

To qualify a host, independently freeze source/config/tool/model versions, expected labels and oracles outside the candidate write scope. Compare native host, minimal instructions, estack and relevant lawful donor baselines with matched tasks/budgets. Capture actual actions, outputs, revisions, unauthorized attempts, duplicated side effects, unnecessary questions and cost. No new credentials or paid calls are authorized for this release.

For stochastic behavior, predeclare repeated trials, budgets/seeds and held-out tasks. Evaluate activation false positives/negatives using [trigger-cases.json](trigger-cases.json), separately from task quality. Do not call a text or metadata match a model activation result. No universal performance target or statistical superiority is inferred from this pilot.

Private development-trial transcripts and machine-specific receipts are omitted from this distribution. They do not promote the full E01–E20 protocols to passed. Run the deterministic suite for this checkout and use the protocol above for wider qualification.

Further required scenarios include stale receipts, malformed records, uncertain already-applied mutation, adversarial completion replay, changed action approval, forbidden donor instructions, missing dependencies and disconnected call paths. Contract checks do not replace the live audit for egress, persistent policy changes, deployment or credential access.

