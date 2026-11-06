# Durable evaluation records

Read for every evaluation, including quick calls ([Palette](palette.md)). Record all evaluated sources and source/recipient pairs, not only accepted transfers. Use the recipient's existing research library/dossier and its live rules, or an authorized run directory chosen at the start. A quick call needs only a concise entry in that existing record. Do not create a new memory service or bypass write/freeze rules. If the destination is unresolved or writing fails, keep the actual saved/unsaved status visible and resolve recording before claiming completion.

Start with the queued inputs; update after meaningful research and before final publication. For each source retain:

- Original and resolved identities, aliases, parent social post/linked-artifact relationships, source revision or captured identity, retrieval date and actual methods/outcomes. Every substantive associated artifact gets its own entry or explicit pointer.
- Selected recipients and the rules/snapshot used, inspected files/sections/media, evidence references and limits. Keep read, merely found, inaccessible and not inspected distinct; never imply an entire repo/paper was read from selected files or an abstract.
- Per-recipient findings, whole-tool disposition, useful parts, verdict or unresolved state, reasoning, uncertainty and cost basis. Original intent/purpose/domain/language never supplies a rejection reason. Preserve different recipient outcomes and retained research leads.
- Proposed experiments and what would change the verdict; distinguish proposed, authorized, run and result. Actual measurements/tests cite their inputs/workload, units, revisions and receipts; estimates retain assumptions, unknowns and their estimated status.
- Remaining work, failed retrieval attempts, blockers and the next method/test, so another session can resume without treating missing evidence as a completed negative finding.

Use one canonical donor record with recipient-specific references; preserve all parent links when deduplicating. A re-evaluation records its new identity/date and supersedes or amends the prior entry explicitly, preserving its history. Prior verdicts remain history, never evidence for a fresh judgment (§0.8).

Verify the saved record using existing schema/consistency checks. For schema-2 runs, `aa.py finalize RUN/run.json --output RUN/report.md` combines readback and checked rendering ([gates](gates.md)); separate commands remain available. `--complete` requires complete coverage and readback; partial work stays valid. A captured `--index` binds source/item IDs and bytes without authenticating an external catalog update. Manual text cannot change queued machine states. If live-library writing fails, retain a permitted durable review with explicit indexing status. Claim “catalogued,” “validated,” “all assessed” or “saved” only to the checked scope. Link the final answer to the record and state any recording gap.
