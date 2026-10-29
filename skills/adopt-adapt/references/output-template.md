# Output template (shared donor facts, then each recipient pair)

A quick call (SKILL.md §1) uses its few evidence lines and the bounded route its manual ledger ([bounded-ledger template](bounded-ledger-template.md)) instead of the scored template below; both keep queued pairs, decisive support, applicable constraints and uncertainty visible. Structured records and full-route reviews retain this template.

1. Manifest line: `#n source → recipient — STATE`
2. Shared donor ledger once: source identity, map, read/total coverage and blind spots, subsystem stages when relevant, five lenses and their evidence. Distinct variants name affected pairs. Then each recipient ledger references that basis and shows recipient HEAD/dirty files, overlap evidence, due-diligence lines, gates and flags, **LEGAL:** `flag` / `route` / ladder steps / escalate? ([legal](legal.md)), closed-source confidence and/or web-forensics hashes when applicable, evidence-ladder table (claim → CLAIMED/PRESENT/WIRED/TESTED/OBSERVED → file:line, plus the run for TESTED/OBSERVED; inferred claims carry their confidence label; `aa.py render` prints it from each claim's `level`), the independent review when one is required (level, packet or report hash, strongest disconfirming observation), and target doubt (against, for, deciding evidence).
3. Verdict line: `VERDICT: <ADOPT|ADAPT|ADAPT-with-prerequisite|ALREADY-COVERED|DISCARD|OPPORTUNITY|INCONCLUSIVE> | fit x/10 or not scored | mechanism y/3 | confidence <low|medium|high>` (anchors: SKILL.md §4). A promising but unconfirmed transfer (value 1, one check would confirm the need) prints `DISCARD (promising: <check to run>)` as its result. A pair that is not READY prints `STATE: <BLOCKED|UNPROCESSED|CANCELLED> — reason` instead and no verdict.
4. Plain summary: what it is, the mechanism, recipient benefit, limit, next step.

Nothing that reads as a final verdict may appear above step 2. Provisional leanings inside doubt are labelled PROVISIONAL.

For skill, hook, MCP, plugin and agent-config donors, include the [behavior inventory](due-diligence.md#donor-risk-audit-required-for-skill--hook--mcp--agent-config-donors-recommended-for-all) in step 2's existing shared donor map; keep risk classification in `ledger.donor_risks[]` and avoid duplicate descriptions.

For RE sources, step 2 includes the [method contract](re-methods.md): one row per method/claim, output, original/recovered baseline, inherited versus new contribution, distribution boundaries, per-check status and evidence. Show matching, behavior, readability and portability separately; show progress numerator/denominator and exclusions when quoted. Never turn a structural match, compiled build, isolated fixture or claimed donor result into whole-system behavioral verification.
