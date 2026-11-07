# Changelog

## 1.0.0-alpha.1 (the index dimension), unreleased

A sixth category, `index` (weight 10), scores westack-onboard's `codeindex.py doctor` verdict: OK 10, WARN 7, ERR 0. A repository with no index, or no westack-onboard, records it as skipped, so its weight is shared among the others; `detect` names the doctor command. Composites move accordingly (the worked example is 8.7 over six categories). Tests: 22, with a broken copy that scores WARN as clean.

## 1.0.0-alpha.0 (first build), unreleased

westack-health is built: a report-only code-health check that runs the project's own type checker, linter, tests, dead-code finder and shell linter, scores each category 10, 7, 4 or 0, and combines them into a weighted score (typecheck 22, lint 18, tests 28, dead code 13, shell 9) with a skipped category's weight shared among the scored ones. `scripts/healthcheck.py` runs nothing: `detect` reads a declared `## Health Stack` section or configuration files, `score` checks and scores the agent's `results.json`, `history` compares only runs with the same coverage, and `recommend` ranks categories by weight times deficit. Zero executed tests, a failing exit with nothing counted and tests without counts are never clean; a capture failure leaves the run unscored. Ideas from gstack's health skill at the mirror pin, in westack's words; its gbrain sub-score waits for westack-onboard's index (plan slice S17). Tests: 20, with in-suite broken copies for the weights, the redistribution, the bands and the ranking.
