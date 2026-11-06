# Changelog

## 1.0.0-alpha.31 (lean start pages: build, tdd, debug, verify, plan, design, security), unreleased

`SKILL.md` is now a short start page: when to use it and when not, the mode table naming the page each mode reads, the rules that hold in every mode and the report. Everything else moved word for word into references read on demand, and the page says to read a mode's pages in one turn with the first look at the work. The description and the minimum core block are unchanged; no rule changed. `SKILL.md` 1,813 to 1,025 words (1,373 to 585 without the core block). Kept: hands off the work, the mode table, proportionality, the baseline rule (new failures apart from pre-existing ones, EV-40) and the report. New `references/checks.md` (892 words: a check needs a grant; what done means; claims are not proof with the excuse table, WA-71 and EV-54; the checks, WB-03, EV-47 and EV-48), read in claim and acceptance modes. Pins moved, wording unchanged: WB-03, WA-71 and the excuse-table tests (`tools/tests/test_adjacent_addendum.py`), EV-47, EV-48 and EV-54 (`tools/tests/test_p2_review_verify.py`). The `where` values in `provenance/donors.json` follow the moved sections.

## 1.0.0-alpha.29 (slim: less loaded, fewer steps on small tasks), unreleased

The regenerated minimum core block (the core is found only before the first core helper or reference; a new Lean rule; the broken-copy control applies when the work adds or claims a check). Core references are named on demand, each only when its step needs it, instead of loaded at start. `SKILL.md` 1,847 to 1,813 words: the evidence-root sentence is compressed and the donors section is one line. No rule changed.

## 1.0.0-alpha.25 (evals: harder cases A; research and plan fixes), unreleased

Task cases only; `SKILL.md`, references and scripts are unchanged. The first measurement had verify at +0.01 over a bare host scoring 0.98.

- Task cases 3 to 8. Each new case carries `"added": "2026-10-31"` and is held out for the next measurement (`notes.held_out_2026_10_31`); each names the rule it tests (file:line), the honest answer and the trap in the notes. Traps were written from the skill's rules, not from the first measurement's transcripts. Offline fixtures, model-free regex graders; every good canary scores 1.000 and every bad one is caught below 0.5 (or hard-fails) on a criterion it names, by westack-eval's own blind export, deterministic grader and calibration (`tools/eval/tests/test_harder_cases_a.py`). Nothing was run on a host. All five share one neutral prompt (verify a claimed-done task before merge, report only; first line DONE, NOT DONE or CANNOT TELL).
  - `second-test-folder`: the project's own check, not the claimant's (SKILL.md:77; acceptance.md:13). The claimed run covered tests/ only; `run_checks.py` also runs contract/, where an accented-title slug test fails (7 executed, 6 passed, 1 failed).
  - `mocked-regression-test`: a test that cannot fail is no evidence (SKILL.md:79; claim.md:83). The new regression test patches the unit it tests; with the old code restored the suite still passes 3/3.
  - `skips-counted-green`: skipped is not passed (SKILL.md:23, :77). `check.py` prints "6 tests, 0 failed" while 3 quoting tests are skipped and the quoting is wrong.
  - `out-of-scope-diff`: the diff against the request (SKILL.md:81; acceptance.md:47). The change also turns `VERIFY_TLS` off, unlisted.
  - `untested-weekend`: a requirement no test reaches (SKILL.md:80; acceptance.md:27). The weekend test's date is a Wednesday; Sunday rolls to Tuesday.

## 1.0.0-alpha.6, unreleased

- Aura Autopilot (AP-1): `references/claim.md`, section 5. A "can happen" claim is shown true by doing it once; a failed attempt is inconclusive (the attempt may be at fault), and impossible only when the system's own numbers prove it, named in the evidence. Reading code says where to look; a defect counts once the running system shows it. The verdict words are unchanged.
- Aura Autopilot (AP-2): `references/acceptance.md`, section 3. A direct state change (seeding data, setting a value, jumping the system to a state) may set up or measure a check, never achieve what the criterion is about; each is listed with its reason by phase (setup, action, measure), and a result reached through one on the criterion's own path is a cheat, not a pass. The eval and tdd parts are in their changelogs.
- Aura Autopilot, size in words before and after: `references/claim.md` 537 to 590, `references/acceptance.md` 863 to 919.
- Donor records (AP): `provenance/donors.json` gains the `ap:ramenvr/autopilot` record (Apache-2.0; ideas only). It notes two flags (run-data sharing is on unless the user opts out; bubblewrap isolation is Linux-only) and that the Aura benchmark (7 tasks, one template game, one run each) is the authors' claim, graded claimed.

## 1.0.0-alpha.5 (P2 adoption), unreleased

- P2 (EV-40): `SKILL.md` Baseline and `references/acceptance.md` section 2. A failure is pre-existing only if its failure text matches too; a changed message is unattributed. An accepted-failure list holds exact, dated entries with a reason and review date. The helper change is in the core (`checks.py`).
- P2 (EV-41): `references/acceptance.md` section 2. A criterion that passed in an earlier receipt and now fails is regressed: name the last passing receipt and the files changed since; recheck every criterion each iteration and reuse a heavy check only while it last passed and its declared paths are unchanged. The validator report and any `observes` paths are the contract group's.
- P2 (EV-47): `SKILL.md` The checks. A check script with no runner counts passes on exit zero plus a success marker printed after its last assertion; the exit and the marker line are recorded; error text never passes a nonzero exit; truncated output fails; exit zero without the marker is inconclusive.
- P2 (EV-48): `SKILL.md` The checks, Exercise the claim. Expected values come from source data, never from the request text; a number copied from the brief is not its own expectation.
- P2 (EV-54): `SKILL.md` Claims are not proof. A gate blocks only on machine-checkable facts a stub cannot satisfy; counts and wording hits ("pre-existing", "skipping for now") only prompt a second look and are reported as "look again" beside the deciding facts.
- P2 (SS-45): `SKILL.md` The checks, Controls. An automated gate is read for tautologies (fixed-output command, weak expectation, path used as a regex, unmeasured number) before it is trusted; the read never replaces the broken-copy run. The plangraph lint is westack-plan's.
- P2 (WA-72): `references/claim.md` step 3, `SKILL.md` Baseline and the pre-existing row of the excuse table, `references/acceptance.md` section 2. With no baseline, one failing test is proved pre-existing by running it alone at the parent commit in a detached worktree, with a receipt bound to that commit; never stash or reset. The excuse table keeps its five rows and wording pins.

Size, in words before and after: `SKILL.md` 1655 to 1847, `acceptance.md` 770 to 863, `claim.md` 504 to 537.

- Donor records (P2): `provenance/donors.json` gains 6 `p2:` records for the 7 applied items above: pinned blob URLs, lowercase SHA-256 and byte counts, a licence note, "ideas only" and the item ids each supports. Restricted sources (proprietary, unlicensed, source-available, GPL, and the X-post mirrors) are marked never to quote. The file's `reviewed` date is 2026-10-29 and its policy says how the `p2:` records were read.

## 1.0.0-alpha.4 (P1 adoption), unreleased

- **EV-45.** Results are derived from the receipts when read: a stored pass flag or saved aggregate is a cache, status is recomputed from the separate facts (artifact present, review passed, claim live), and a failing fact names its file or step. The core validator already recomputes a record's stored fields from its evidence; the new tests in the core suite pin that. (`SKILL.md` Claims are not proof, `references/resume.md` step 1.)
- **EV-46.** The report ends with a deliverable check (`fresh`, `intermediates-only` or `none`), with counts recomputed from the receipts. (`SKILL.md` Report; the rule itself is in the core `finish.md`.)
- **SS-47.** A run-selection flag (a name or path filter, `-k`, `--grep`, `--lf`, fail-fast) or an input the runner or CI action ignores makes the receipt a narrower claim: the skipped part is not-run and a green exit is never a full pass. The options in effect are recorded with each raw output. (`SKILL.md` The checks, `references/acceptance.md` sections 2 and 3.)
- **CM-43.** A check that found no target, got malformed input or could not apply a rule is blocked or inconclusive, never passed or clean. (`references/claim.md`; the rule is in the core `evidence.md`.)
- **Donor records.** `provenance/donors.json` gains 12 `deep:` records for the systems behind this skill's applied items: pinned blob URLs, lowercase SHA-256 and byte counts, a licence note, "ideas only" and the item ids each supports. Proprietary, unlicensed and restrictive sources are idea sources with their status stated and are never quoted. The file's `reviewed` date is 2026-10-29 and its policy says how the `deep:` records were read.
