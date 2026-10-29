# adopt-adapt 3.0.0-grok-draft.r16 - released 2026-10-29 PT

Released after the round-3 pre-registered blind before/after comparison on Claude Code (2026-10-29): not worse than the previous version (r15.1) at n=8 pairs (2 wins, 1 loss, 5 ties; no new hard fail; sign-test p=1.0, so no superiority is claimed). Codex was not run. The only changes from the evaluated candidate are this version label and the SKILL.md status line, which no longer says the candidate awaits evaluation. License remains **Proprietary (Matt Kolkin)**; this edition grants no new reuse rights.

This file is the public edition of the changelog. It summarizes the r16 line without the private project details, machine paths and internal review notes that the full history carries. See "Public edition" at the end.

## What r16 changed

Section 0 (the fail-closed contract): the 2026-10-27 passes defined each evidence-ladder level in 0.7 (a test that was not run never earns TESTED) and, with the skill owner's sign-off, reworded 0.2, 0.5, 0.6, 0.9 and 0.10; the fix rounds changed nothing in it. No eval case or grader criterion was edited.

### Fix rounds after the blind comparisons (2026-10-29)

The first r16 candidate failed its pre-registered comparison against r15: both dispreferred runs added ceremony or artefacts that changed no decision. The fix rounds answer the diagnosed causes.

- **Quick call (SKILL.md section 1, the default for a small idea).** A snippet, one function or one idea for a named seam, when no governed or frozen seam, skill/hook/MCP/config donor, new dependency or whole-tool adoption is at stake. A few lines of evidence with file:line are its ledger; then the verdict with its reason and the strongest reason against, the transfer step, and one test that fails without the mechanism. It adds no template, refutation targets, lens list, printed numbers or files.
- **What the user states is input.** The user's need, constraints, project facts and acceptance are built on, not re-verified or hedged; a doubt is raised only where read material contradicts them. Value 1 is never `promising` for a stated need, and value 2 counts the user's own statement as a stated requirement. A gap alone is still not a need.
- **Prerequisites** must be able to change the verdict or plan; checks that reading can settle are settled, and checks that change nothing are dropped. The patent-signal check reads the material you hold, not a patent database: nothing found in what you read is `none`, and `unknown` means a file that could carry a notice went unread.
- **Write scope.** Only the files the user asked for or authorised. The host's scratchpad and temp folders count as outside, and any check is run inline with literal paths; when running is denied, or a needed file has no named folder, the claim is marked untested and nothing is written or run elsewhere to get round the denial.
- **Claims of work.** A claimed search, run or read needs the matching tool call in the session, else the report says it was not done; each citation is checked against the file as read, never from memory.
- **Salvage.** A DISCARD names every separable part that passed the screen, a line each, not just the first found.
- **Budgets and tests.** Word budgets were lowered to measured values where deletions paid for the new rules and raised by the measured amount where they did not. `tests/test_r16e.py` and `tests/test_r16f.py` pin the rules, and an in-suite broken-copy control removes one rule at a time and shows its check fails. These tests pin wording, not behaviour.

### Recipient rename (2026-10-28)

The recipient skill westack (then called estack) was renamed because a separate public project owns the old names. The profile id is `westack`; the routing evals, required-file list and tests follow, and `references/evidence-vocabulary.md` follows the collection's shared copy. `tests/test_westack_rename.py` fails on the old name, or on the doubled prefix a naive replace produces, outside a short allowlist that cites its keep rule. No routing rule, rubric, score or validator logic changed.

### Consolidated self-change (2026-10-27 and its passes)

- **Numbers.** Anchored 0-3 mechanism value and low/medium/high confidence, and which route needs which number. The validator enforces the thresholds: a transfer result needs mechanism value 2 or more, and whole-tool ADOPT also needs a scored fit of 8 or more. A level on every claim (claimed, present, wired, tested, observed) caps confidence and value.
- **Consistency.** One five-lens reporting rule, one doubt rule shared by the instructions, `aa.py doubt` and the validator, and one verdict vocabulary. A whole-tool legal RED or UNKNOWN can be recorded together with a clean-part transfer, and the part's own flag gates the transfer.
- **Path rules.** `classify-path --rules FILE [--root DIR]` applies explicit caller-supplied rules; rules that pin a source fail closed when the live file differs, is missing or was not checked.
- **Context diet.** Per-donor verdicts, worked examples, host inventories and provenance comments moved out of the files an agent loads by default, and the bounded-review and skill-donor loads shrank. `tests/test_r16.py` pins the budgets.
- **Routing.** The description sends a new multi-source product to frankenmine and recovery of one opaque product to reverse-engineer-anything. `aa.py routing-index` prints every installed profile's routing signals, generated from the profiles so it cannot drift. Helper commands use `"<skill-directory>/scripts/..."`, so they work from a recipient's directory.
- **Evidence vocabulary and bias controls.** `references/evidence-vocabulary.md` is a byte-identical copy of the collection's shared vocabulary. Bounded-route refutation targets are written before the deep recipient read; an independent reviewer above level `self` gets the ledger without the verdict. `aa.py outcome` appends an implemented plan's acceptance-test result next to the original result and is never an input to a fresh judgment.
- **Legal.** GREEN(idea-only) applies to a public source with no terms restriction and no patent signal; the validator requires both checks on every idea-only route and refuses GREEN unless both are `none`. Code or text reuse from a source with no licence is RED.
- **Recipient-neutral core.** The instructions and every non-profile reference and script are free of project-specific terms (this is tested); routing signals and legal overlays live in each profile.
- **One source, two editions.** `scripts/package.py` declares private files by rule (every profile file except the public profiles, plus the historical archive and the tests that need them) and never requires them. `tests/test_r16c.py` scans every public file for the publication patterns and proves that a copy without the private files passes the manifest check and core routing.
- **Per-mechanism workaround.** `references/records.md` documents registering a second good mechanism as its own source (`<locator>#mechanism-<name>`).
- **Later, not now:** calibration analysis once about 20 outcomes exist; GRADE-style confidence downgrades; per-mechanism decisions inside one pair; deps.dev or ClearlyDefined lookups (verify their APIs first); FeatureGraft-style donor lineage for upstream fixes. **Not doing:** seam graphs, more risk codes, more legal case notes, structural tests for their own sake.

## Earlier history

Entries for r15 and earlier, back to the 2.x line, record private projects, machine paths and internal review notes and are not redistributed. Baseline lineage: adopt-adapt 2.11.0, adopt-adapt-v2 2.0.0 and the 3.0.0 proposal. This changelog does not import past verdicts or private research records into new assessments.

## Public edition

This edition is generated from the r16 release by the collection's public build.

- **Omitted by rule:** every profile file except `generic`, `coding-workflow`, `self`, `frankenmine` and `westack`, the profile-owned rules and alias files, the machine-root hints, the historical archive and `tests/test_private_profiles.py`. The shipped files are byte-identical to the release apart from the overlays below.
- **Overlays:** this changelog; `evals/trigger-evals.json`, whose routing cases are rewritten against the public profiles with the same intent and expected routing logic; and the one-line `description` in `SKILL.md`, which names a user-specified recipient instead of listing private projects.
- **Regenerated:** `release.json`, by the skill's own `python -B scripts/package.py manifest .`, so it hashes exactly the published files.
- **Limits:** tests and package validation establish only their stated local scopes; no trigger accuracy, verdict quality, native host activation or general effectiveness claim follows.
