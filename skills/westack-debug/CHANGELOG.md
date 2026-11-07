# Changelog

## 1.0.0-alpha.36 (the user's first line first; debug PAIR grader), unreleased

`evals/tasks/campaign.json`, order-leak PAIR: also accepts a receipts row with the command prefix elided to `...` (suspect before test_report, a failure on the line); calibration adds that form as good. In the second measurement PAIR scored 0 in every run of both arms. Found after those results were read; the registered result is not re-scored.

## 1.0.0-alpha.31 (lean start pages: build, tdd, debug, verify, plan, design, security), unreleased

`SKILL.md` is now a short start page: when to use it and when not, the mode table naming the page each mode reads, the rules that hold in every mode and the report. Everything else moved word for word into references read on demand, and the page says to read a mode's pages in one turn with the first look at the work. The description and the minimum core block are unchanged; no rule changed. `SKILL.md` 1,355 to 1,051 words (910 to 606 without the core block). Kept: the mode table (diagnose writes nothing in the project), steps 1 and 2 (pin the symptom, reproduce before theorising), the flaky pointer, the never list and the report. New `references/loop.md` (406 words: steps 3 to 7, leads are not evidence with WA-68, the stop rules), read in both modes. Pin moved, wording unchanged: WA-68 (`tools/tests/test_p2_build.py`). The `where` values in `provenance/donors.json` follow the moved sections.

## 1.0.0-alpha.29 (slim: less loaded, fewer steps on small tasks), unreleased

The regenerated minimum core block (the core is found only before the first core helper or reference; a new Lean rule; the broken-copy control applies when the work adds or claims a check). Core references are named on demand, each only when its step needs it, instead of loaded at start. `SKILL.md` 1,348 to 1,355 words. Fix mode: the regression test's red before a fix touching only the suspected cause, and green after, is the counterfactual, so no separate probe runs. A read or probe that settles several hypotheses counts for each. The intro is compressed.

## 1.0.0-alpha.25 (evals: harder cases A; research and plan fixes), unreleased

Task cases only; `SKILL.md`, references and scripts are unchanged. The first measurement had debug at +0.03 over a bare host scoring 0.91.

- Task cases 3 to 8. Each new case carries `"added": "2026-10-31"` and is held out for the next measurement (`notes.held_out_2026_10_31`); each names the rule it tests (file:line), the honest answer and the trap in the notes. Traps were written from the skill's rules, not from the first measurement's transcripts. Offline fixtures, model-free regex graders; every good canary scores 1.000 and every bad one is caught below 0.5 (or hard-fails) on a criterion it names, by westack-eval's own blind export, deterministic grader and calibration (`tools/eval/tests/test_harder_cases_a.py`). Nothing was run on a host. The campaign gains a `notes` object (`fixture_truth_added`, `held_out_2026_10_31`).
  - `order-leak`: order-dependent shared state (flaky.md:32; SKILL.md:73). One test writes USD into the dict `settings.load()` caches; a decoy test touches the cache and restores it. Trap: call it flaky, fix the victim, or blame the decoy.
  - `upstream-newline`: fix where the value first goes wrong (fix.md:9; SKILL.md:49). The loader keeps each line's newline on the email; the error is raised two files later. Trap: fix it in notify.py.
  - `why-bom`: a "why" question stays read-only (diagnose.md:7; SKILL.md:40). A UTF-8 byte order mark renames the first CSV header, so every amount defaults to 0. Trap: edit the script or add prints to it.
  - `ci-cwd`: environment against code (SKILL.md:73; reproduce.md:33). A path relative to the working directory, and a CI job that changes into tests/. Trap: blame the runner.
  - `stale-golden`: audit the check's premise before blaming the code (hypotheses.md:7; SKILL.md:71). The golden file predates recorded decision D7 (VAT 20% to 21%). Trap: set the rate back to match the test. Regenerating the golden after citing D7 costs only the "asks first" point, because the user asked for a fix.
- Three checks were widened in review, before any run: ci-cwd's reproduction accepts the command (`cd tests`, from inside tests/) as well as the word "reproduce"; order-leak's pair accepts "test_admin before test_report ... fails" as well as one unittest line; stale-golden's hard fails no longer fire on regenerating the golden.
- The existing cases are unchanged. Their good canaries still score below 1.0 (clock-flake 0.583, tiny-typo 0.625), because those criteria read the artefacts and canaries carry none; westack-eval's calibration passes them.

