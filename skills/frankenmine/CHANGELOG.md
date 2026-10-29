# Changelog

## 0.2.0 — 2026-10-29

Released after the round-3 pre-registered blind before/after comparison on Claude Code (2026-10-29): not worse than the installed 0.1.4 at n=8 pairs (3 wins, 2 losses, 3 ties; no new hard fail; sign-test p=1.0, so no superiority is claimed). Codex not run.

This release implements the adjudicated independent review of 0.1.3, dated 2026-10-27. Earlier release notes are in [BUILD_REPORT.md](BUILD_REPORT.md).

### Fix round after the 2026-10-28 blind comparison
A blind before/after comparison against 0.1.3 failed this candidate: over six pairs it had no wins, one loss and five ties, and the grader preferred 0.1.3 in three. The losses shared one pattern: process artefacts and ceremony on tasks too small to need them. This round makes proportionality concrete and default-on, mostly by deleting and tightening. Each new check was written as a failing test first (`tests/v0_2_fix_round_tests.py`, 4 cases, all red against e8d5718), and six broken-copy controls show the tests fail when a rule is removed.

- **What drove the losses.**
  - The lite tier was the default for up to three donors. Its template asks for donor snapshot copies, an oracle file and a saved review report, and `check-lite` rejects a self review, so one design-only run wrote nine side files.
  - `stamp` writes a new file. One run stamped its dossier into a folder outside the work folder.
  - SKILL.md told every run to "hash snapshots" and to save a review report in the run root.
  - Nothing asked for a claim about code behaviour to be checked, and one run stated an untested edge case wrongly.
- **Keep it proportionate.** A new section comes before the steps and overrides them:
  - a request answerable in one reply gets the reply, plus only the files the user asked for;
  - records, ledgers, dossiers, snapshots and other side files appear only when the task needs persistence or the user asks, and the steps say what to check, not what to write;
  - writes go only inside the output folder the user named, helper outputs and drafts included, or nowhere;
  - a claim about how code behaves on an input is checked with an authored snippet (never by running donor files) when that is cheap and allowed, or marked untested.
- **Records.** A third record, **Answer**, is the default: the reply plus any dossier asked for, as narrative, with no helper. Lite is now for a checked dossier on request; Full is unchanged. The independent-review gate applies to lite and full records, and an answer says once that it is self-reviewed. The README and `evals/evals.json` case 11 follow.
- **Helper.** `stamp` on a lite dossier refuses an output outside its source's folder, where `check-lite` could not resolve the dossier's file paths. Full-tier `stamp` is unchanged.
- **Deleted from SKILL.md** (each still lives where it is used):
  - the unconditional "hash snapshots";
  - the `init --decisions`, `inspect-python`, `scaffold`, `stamp`, `report` and `review-packet` command lines (README, continuation and verification references);
  - the seam inspection list (seams reference);
  - the receipt and result rules, now by reference to the evidence vocabulary;
  - the ten-item tradeoff list, now "the dimensions that matter";
  - a duplicated authority sentence.
- **Kept:** every 0.2.0 gate, schema and helper; donor and best-existing search; product-led or exploratory framing; real pins; both discovery directions; rights categories checked against routes; conditional deltas and protocols; the modular-monolith default; the Pareto view; one owner per state; pair and group interaction tests; artifact-bound receipts; the independent-review procedure; outputs outside the skill folder.
- **Size.** SKILL.md went from 1,698 to 1,617 words. SKILL.md plus the lite template and the evidence vocabulary (0.2.0's default reading path) went from 3,140 to 3,059; the template is unchanged at 726. The default path no longer reads the template, so it is now SKILL.md plus the vocabulary: 2,333 words. The new test ratchets both counts.
- **Not verified.** The package tests show the wording, the budget and the helper guard. Whether agents now write less, stay inside the named folder and check behaviour claims is a live-agent question. It needs a fresh blind campaign on cases not seen in this one.
- **Round 3: snippet checks run inline or inside the named folder.** The 2026-10-29 blind comparison failed this candidate on one hard fail: a run wrote a check file to the host's scratchpad, which the host suggests for temporary files but which is outside the named folder. In both ties the grader gave to 0.1.4, the new side left an unrequested check file in the output folder whose run was denied and which no decision used; one had re-typed donor logic to run it.
  - The write rule now says the host's scratchpad and temp folders count as outside.
  - The snippet rule runs snippets inline (`node -e`, `python -c`, literal paths); a file only when truly needed and only inside the named folder; inline only when no folder is named; never donor code, even re-typed. A skipped or denied check leaves the claim untested, and a denial is never worked around elsewhere. The closing line already asks for the paths of files written.
  - Size: SKILL.md grew by the 53 words this needs, from 1,617 to 1,670 (write rule +9, snippet rule +44), and the default reading set from 3,059 to 3,112. The ratchet rose by exactly that; both stay below e8d5718's 1,698 and 3,140.
  - Tests: one new case in `tests/v0_2_fix_round_tests.py`, red against 65546d6; nine broken-copy controls each fail it. Whether agents now check inline is a live-agent question for a fresh campaign.

### Rename (2026-10-28)
- **Name.** westack (then called estack) is the skill Frankenmine uses as its worked example. It was renamed because singularityhacker/Estack owns the `estack` names. Every live reference now says westack, including the example file (`examples/westack-planning.md`) and the links to it.
- **Vocabulary.** `references/evidence-vocabulary.md` is the shared v3 copy, byte for byte (sha256 `bde4fc98…bbd2`, 4,064 bytes).
- **No behaviour change.** Scripts, schemas and the examples' records are untouched; the package checklist and the test runner only register the new guard. Receipts, logs, release notes of earlier versions, the hash-pinned `research/` sources and the `research/2026-10-26/` archives keep the old name, because rewriting them would forge what ran.
- **Guard.** `tests/westack_rename_tests.py` fails on any use of the old name outside an allowlist that names each kept file, its keep rule and its exact count, and on a doubled prefix. It was written red first.

### Contract
- **Run schema 1.1** (`schemas/run.schema.json`). Every addition is optional. `schemas/run-1.0.schema.json` is the unchanged 1.0 contract (sha256 `3300aec4…`), and records are validated by their declared `schema_version`. A 1.0 record parses with the same structural result as before. It may fail the stricter readiness gates; each such message names the 1.1 field to add. The schema validator now supports a list in `type`.
- **New fields:**
  - `brief.question`: product-led or exploratory;
  - `supporting_evidence`: documentation, product-observation, screenshot and static-graph, all weaker than source snapshots;
  - `requirement_coverage`: maps requirements to candidate IDs or `new:<component>`;
  - `candidate.touches`;
  - `seam.evidence`;
  - `rights.category`;
  - `receipt.sequence`;
  - `review.author` and `review.independence`;
  - interaction status `independent`;
  - test purpose `interaction`.
- **Fields that became conditional:** `candidate.need` accepts a list. `protocol` is required only for process and rpc routes. `deltas` are required only when a reuse route crosses a language boundary. An interaction's `test` and `evidence` are optional for `independent` pairs.

### Readiness gates
- **Outcomes.**
  - `fusion` now needs at least one selected donor unit on a reuse route; the old "two selected donors" rule is gone.
  - `minimal-fresh` and `best-existing` may keep pattern-only lessons selected, with full provenance.
  - Fusion requirement coverage may name new glue code through `requirement_coverage`.
- **Placeholders.** One placeholder rule now applies across the brief, donors, evidence, discoveries, selected candidates, ownership, interactions, alternatives, decision, tests and receipts. It catches TODO, TBD, FIXME and `?` prefixes, and short unknown/pending phrases. `n/a: <reason>` is the only accepted not-applicable form.
- **Donors and ownership.**
  - Selected donors need a real pin: a full commit, or `<immutable-tag>@sha256:<digest>`.
  - Ownership keys are normalised for case, whitespace and separators.
  - A touched key needs an owner.
- **Review.** Design readiness needs an accepted review by a reviewer who is not the author, at a level other than `self`.
- **Seams and interactions.**
  - Seams must link source evidence from their own donor.
  - A process or rpc protocol cannot be entirely n/a.
  - An interaction is verified only by an interaction or integration test. A pair may instead be marked `independent` when its declared touches are disjoint.
- **Discovery.** A donor-led discovery that duplicates a target-led one is rejected.
- **Receipts.** A test may keep an ordered receipt history; the latest receipt decides its status, and earlier failures are kept.

### Helper behaviour
- **Report.** `report` now renders the dossier: brief, donors, evidence, a both-direction lesson ledger, contracts (seams, rights, deltas, protocol), requirement coverage, ownership, interactions, alternatives, tests with receipt history, and review. Raw JSON appears only with `--include-record`. Design readiness and implementation evidence are reported separately. An implementation run whose tests are not run reports `design-ready; implementation-unverified`.
- **Writes.** Every helper write refuses paths inside the package root.
- **Inspection.** `inspect-python` records imported names and aliases (graph format 1.1). A run can cite the graph as `static-graph` evidence.

### Examples
- **Flagship example** (`examples/synthetic`), now schema 1.1 and built by `tests/fixture_builder.py`:
  - donor-led lessons that differ from the target-led ones;
  - real semantic deltas, including the string-parsing deltas (`BigInt("")` is `0n`; Python `int("٣")` is 3);
  - seam evidence and an integration test for the pair;
  - real pins, written as tag@sha256 for the fixtures.
- **Slice and oracle.** The slice now rejects `-0` and other noncanonical spellings. The oracle tests them, so int()-lenient and BigInt-style mutants are caught.
- **No-fusion example.** It now records `minimal-fresh` with both lessons selected as pattern-only, instead of misfiling used lessons as deferred.
- **Lite tier.** New `examples/lite-dossier.md` template.

### Documentation
- **SKILL.md** gained:
  - a tier choice (lite or full);
  - donor and best-existing search;
  - product-led or exploratory framing;
  - a modular-monolith default;
  - a Pareto review;
  - reused-versus-authored provenance;
  - rights categories, including for dependencies;
  - an independent-review procedure for Claude Code and Codex.

  Every command now uses `"<skill-directory>/scripts/frankenmine.py"` with outputs outside the skill folder. The lineage paragraph moved to `references/research.md`. The trigger description now names reverse-engineer-anything (REA), states the new-product versus adopt-adapt boundary, and adds everyday phrasings (511 characters).
- **README.** Adds the Claude Code install path (`~/.claude/skills/frankenmine`, `/frankenmine`), tiers, the 1.1 contract and the new commands.
- **References.** The contracts, seams-and-bridges and verification references were rewritten more tightly. The continuation and handoff references gained the absolute command form.
- **Corrections.** `references/research.md` now records that the 0.1.2 continuation registered westack's manifest and that westack 0.2.0 was built through a Frankenmine run. The westack example now presents westack as a worked example, not a planning-only restriction.
- **Evals.** `evals/evals.json` gains `should_trigger` and `route` labels, plus six new cases: everyday phrasing, no donors supplied, a best-existing win, the lite tier, and two near-miss negatives.

### Round-2 review (2026-10-28)
A second independent review found that every 0.2.0 gate could be passed by declaration. This round binds records to files and closes the consistency holes it demonstrated; each change was written as a failing test first (`tests/v0_2_round2_tests.py`, 65 cases, including the review's fooling cases).

- **Rights against the route.** A selected 1.1 unit needs `rights.category`. A route that keeps donor code (dependency, narrow-port, ffi, process, rpc, wasm, or `reimplementation` with the new `basis: code`) needs rights route licensed-reuse or permission; source-available and proprietary code needs permission; idea-only rights allow only pattern-only or `basis: idea`. Retained dependencies on code routes are structured closure items `{name, pin, category, disposition}` (or `none: <reason>`), with exact pins.
- **Receipts tied to product bytes.** New `artifacts` manifest (path, sha256, origin reused, adapted or authored, parts, donor unit) gives product-file provenance. Receipts list the `artifacts` they tested; `check` re-hashes them and marks a changed latest receipt stale. `tested` and `demonstrated` need artifact-bound receipts. Each receipt has its own raw output unless it declares `raw_shared`. An oracle may not be a donor snapshot or sit in a donor snapshot folder.
- **Lite path** (superseded by the slim lite tier below). The template now assigns evidence IDs, says the hash is of the copied snapshot file, carries the 11 seam dimensions, the 10 tradeoff dimensions, the 13 delta names, a touches column, one meaning of "route" (the rights field is "rights basis"), a dependency table and an 11-item readiness checklist. New `check-lite DOSSIER.md` checks its tables, checklist and file hashes; SKILL.md tells the lite path to run it.
- **Interactions.** `independent` needs non-empty touches on every part. A key touched by three or more selected parts needs one group record covering all of them, verified by an integration test.
- **Review as an artifact.** An accepted review needs `review.report` (path and sha256 in the run root) whose text names the recorded reviewer and level, and at least one finding. New `review-packet RUN --output DIR` writes brief, evidence, oracles, proposed parts and alternatives for a fresh reviewer and withholds the decision, rationale, tradeoff prose and readiness verdict. The Claude Code and Codex how-to is in `references/verification.md`.
- **Authoring helpers.** `stamp` fills every missing file hash (and missing evidence revisions) into a new record and never rewrites a recorded hash. `scaffold` appends a candidate stub whose values are `TODO(scaffold)` placeholders (13 unknown deltas across languages) and an unresolved line, so scaffolding never makes a record pass. A not-applicable delta needs only `n/a: <reason>`. `none: <reason>` is accepted content; To do, WIP and Not yet known are placeholders.
- **Language identity.** `source_language` must agree with the candidate's evidence file extensions (small map).
- **Coverage.** In 1.1 every requirement must be covered under every decision, by a selected part's need or `requirement_coverage`; `existing:<product>` covers a best-existing product.
- **Handoff.** Integration status is now `verified`, `declared` or `not-recorded`, and counts interaction and integration tests. In design mode not-run tests are expected, and the closing step is the implementation authorization.
- **Donor searches and licence scans.** Optional `discovery_searches[]`; supporting-evidence kind `license-scan` (tool, version, saved output and hash; the helper never installs a scanner), citable by rights.
- **Pareto view.** Alternatives may carry `dimensions` (name, value, higher or lower is better). `report` prints the non-dominated set, the dominated alternatives and a note when the decision chooses a dominated one.
- **Docs.** `references/contracts.md` documents the manual 1.0 to 1.1 upgrade (there is no migrate command). The size table below is corrected. Schema 1.1 changes stay additive: new optional fields, closure items that may be strings or objects, and delta fields that are optional for not-applicable deltas.

### Slim lite tier (2026-10-28)
The round-2 lite template made lite heavier than the full tier had been (about 328 hand-written fields for a two-donor design). Lite is now short again, with machine checks kept on what matters most and an explicit exit to the full tier. Every change was written as a failing test first (`tests/v0_2_lite_tests.py`, 31 cases).

- **Template.** One page: brief bullets, a requirement table that carries coverage, donors, evidence, lessons, three options with a decision and rationale, parts (route, rights basis, touches, owner, material seams, evidence), one "Other seam dimensions" declaration, tests, pairs, review and an 8-item checklist. Dependencies appear only for code routes; receipts only if anything was implemented; no delta or protocol tables.
- **`scaffold-lite`** writes the dossier with numbered donors, evidence, both lesson directions, parts, acceptance and negative-control tests, and pair rows; every judgement stays a prompt, so it never passes until filled. **`stamp`** on a `.md` dossier fills empty SHA-256 cells into a new file and never rewrites a recorded hash.
- **`check-lite` checks:**
  - pins and snapshot hashes, with donor language checked against snapshot extensions;
  - the three options, the decision and its rationale, and fusion against reused units;
  - requirement coverage, and rights basis and licence category against each reused unit's route;
  - oracle independence, the saved review report (hash, reviewer and level), and receipts bound to product-file hashes when implementation is claimed.
- **Escalation and limits.** `check-lite` returns `escalate-to-full` for more than three donors, a process or rpc route, cross-language code reuse, or a key touched by three or more parts. It lists the full-tier checks it does not perform, so `lite-complete` cannot stand for checks lite skipped. The full tier is unchanged.
- **Job (a), re-run.** The two-donor design needs 87 hand-written fields, plus 4 review cells once a review is run. Before the slim tier it needed about 328, and in round 1 about 184. `stamp` filled 6 hashes, and `scaffold-lite` supplied the IDs, directions, purposes, oracle names and pair labels.

### Size
- SKILL.md: 1,451 words in 0.1.3; 1,607 after the first 0.2.0 pass (the earlier "1,600" predates the evidence-vocabulary link); 1,722 after round 2; 1,698 after the slim lite tier; 1,617 after the fix round.
- Reading cost, measured as SKILL.md plus the references a tier requires (whitespace-separated words; table pipes count):

  | Tier | 0.1.3 | 0.2.0 first pass | Round 2 | Now (words) | Now (bytes) |
  | --- | --- | --- | --- | --- | --- |
  | Lite, design only (SKILL.md and template) | 2,640 | 2,437 | 3,705 | 2,424 | 16,634 |
  | Lite with a reuse route (adds seams) | 2,640 | 3,096 | 4,537 | 3,256 | 22,232 |
  | Full (SKILL.md, contracts, seams and verification) | 2,640 | 3,652 | 4,853 | 4,829 | 34,050 |

  Following the evidence-vocabulary link adds 665 words to any tier. Before 0.2.0 the full set was mandatory for every run, at 20,643 bytes.

### Later (not in 0.2.0)
- Library and API mapping as its own delta surface, in the style of TransLibEval.
- Property-based differential tests and mutation testing of oracles.
- Import contracts generated from the ownership record.
- Schema compatibility checks for rpc protocols (OpenAPI, protobuf).
- A workflow-shaped record for skill and prompt donors.

### Not changed
- `research/` (pinned provenance hashes).
- Historical `evidence/` files.
- Installed or public copies.
- Release archives.
