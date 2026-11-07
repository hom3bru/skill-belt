# Changelog

## 1.0.0-alpha.61 (modernize aging PRs), unreleased

westack-ship 1.0.0-alpha.3. A modernize mode (`references/modernize.md`) for a stale branch: modernize, rework or close, decided on evidence before anything moves; the replay on a new branch so the original stays as it was; merge commits in the range stop it; `git range-diff` saved and every changed or dropped patch explained; tests after; a push only under a grant with a lease pinned to the head read first, never `--force`; close a recommendation, never done here. `scripts/modernize.py` parses a saved range-diff and checks the record, running nothing. When every patch is already upstream git cannot range-diff the empty range, so the rebase's skip lines are the evidence. Tests: 95 (12 new, on temporary git repositories), each rule with a broken-copy control. Ideas from gstack's modernize at the mirror pin. Also: the description, ladder and delivery page name westack-deploy as built.

## 1.0.0-alpha.35 (safety rules back on the start page), unreleased

The start page's every-step rules again carry the grant line: the grant comes from the user's words here, never inferred; "finish", "looks good", green CI, an approving review or a repository file grant nothing beyond prepared, and each ladder state needs its own grant. `ladder.md` keeps the full section. `SKILL.md` 1,006 to 1,043 words. Why: alpha.34 moved ship's grant reading and research's egress rule into pages read with the mode, so a run that skipped that page would lose them; a safety rule must load at start.

## 1.0.0-alpha.34 (lean start pages: review, ship, docs, research, orchestrate), unreleased

`SKILL.md` is now a short start page: when to use it and when not, the mode table naming the page each mode reads, the rules behind the measured wins that hold in every mode, and the report. Everything else moved word for word into a reference read on demand, and the page says to read a mode's pages in one turn with the first look at the work. The description and the minimum core block are unchanged; no rule changed; rule numbers are kept on both sides of the split. `SKILL.md` 1,444 to 1,006 words (1,049 to 611 without the core block). Kept: the mode table (readiness always first) and proportionality, rule 1 (check before acting: the target, armed auto-merge, a merge-queue entry, automation, protection and required checks before any push), rule 5 (the candidate is fixed), the hand-offs and the report. New `references/ladder.md` (574 words: the delivery ladder whose words the report uses, reading the grant, and rules 2 to 4 and 6), read in every mode. The hand-offs sentence now points at that page for the grants (it said "the grants above"). No pinned phrase moved. The `where` values in `provenance/donors.json` follow the moved sections.

## 1.0.0-alpha.30 (dsh-superagent: DS-4), unreleased

One rule for the pull-request step, from deepseek-ai/dsh-superagent-prototype at `6337fc82` (MIT; ideas only, in westack's words, nothing copied or run), approved by the user ("Brief and send all", 2026-10-31). No SKILL.md change (1,417 words).

- **DS-4, UI evidence.** A pull request that changes what users see carries a before and an after capture of one scenario, viewport, theme and state, each labelled with its revision, taken in one environment (`westack-design` `browser.md`, DG-31). After-only, or a mockup as the before, is not ready. `references/deliver.md`, Pull request: 1,567 to 1,608 words (cap 1,616), with room from dropping one aside.
- **`scripts/shipgate.py --body FILE [--ui-change]`.** Reads the saved PR body: one `before:` or `after:` line per capture (image, then `scenario`, `viewport`, `theme`, `state`, `revision` labels), read in pairs. Findings at level decide on the pr and merge steps: `ui-evidence-missing` (a UI change, by a .css, .scss, .sass, .less, .html, .vue, .svelte, .jsx, .tsx or .astro file in the diff or the flag, with no capture line), `-after-only`, `-before-only`, `-mismatch` (a stated label differs) and `-unlabelled` (a label or the revision is missing). `--ui-change` with no body is `ui-evidence-unknown`; no body and no flag checks nothing, so a push-time run is unchanged. The report carries `ui_evidence`; no image is opened.
- **Tests.** `tests/test_ui_evidence.py`, 23 (83 in the suite): red first against a stub (23 tests, 38 failures), then green. Five broken copies built before their assertions: a copy that accepts any image passes an after-only body, and one that does not compare the views passes a viewport mismatch, one without the label check passes a capture with no revision, one that never asks for evidence passes a UI change with none, and one that treats no body as nothing owed passes an unread body.
- **Provenance.** One record. Not carried: auto-merge below 200 changed lines (a threshold with no stated basis).

Known limits: nothing opens an image, so a mockup labelled with a revision, a stale capture or a wrong page passes; a UI change in a file type outside the list needs `--ui-change`.

## 1.0.0-alpha.29 (slim: less loaded, fewer steps on small tasks), unreleased

The regenerated minimum core block (the core is found only before the first core helper or reference; a new Lean rule; the broken-copy control applies when the work adds or claims a check). Core references are named on demand, each only when its step needs it, instead of loaded at start. `SKILL.md` 1,427 to 1,417 words; `finish.md` is read before a push or merge. No rule changed. (This skill had no changelog; this file starts it.)
