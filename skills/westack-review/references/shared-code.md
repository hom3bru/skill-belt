# Shared-code lens (report-only)

Use it when the user asks where recent work repeats itself ("is there code worth sharing?"), or alongside a code review when the diff adds a near-copy of something that already exists. It proposes extractions and stops: no edits, no new files, no issues or PRs opened. Building one is westack-build's, under its own grant.

## Find

1. **Recent work first.** Take the window or the branch's changed files (a saved `git diff --name-only <base>...HEAD` or `git log --name-only --since`). Repeated fixes and similar additions are the best leads; frequent edits alone are not.
2. **Scan.** `python scripts/sharedcode.py scan <root> --changed <file of changed paths>`: Python functions copied into two or more files, matched once formatting, comments and docstrings are set aside (`exact`) or once local names are renamed (`renamed`). Bodies under four lines are left out. For other languages, search for the changed code's distinctive lines across the tree.
3. **Read every site.** A match is a lead. Confirm the copies do the same job: same inputs, outputs, errors and side effects. Copies that drifted on purpose (one handles a case the others must not) are not one helper.
4. **Check work underway.** Open branches or PRs that already extract it are reported apart and not counted as new ideas.

## Judge

Worth proposing when the copies are three or more, or two that have needed the same fix; when one shared helper would remove more lines than it adds, counting its tests and one import per site; and when the copies live where a shared home exists or is easy to name. Not worth it: two short copies in unrelated layers, test fixtures that are meant to stand alone, or code that would couple modules the project keeps apart.

## Report

1. The scope: the window or branch, the files scanned, and anything not covered (other languages, generated code, an unavailable history).
2. Up to five ideas in a table: the sites (`path:line`, symbol), exact or renamed, lines removed, added and net (marked as estimates), and whether it made the top three.
3. Up to three recommendations, ranked: the smallest helper and where it would live, both or all callers, the migration and the test that would prove the copies behave the same, why now, and the main risk, a concrete behaviour that could differ after the move or what breaks everywhere when the shared helper breaks. Never "none".
4. When nothing survives the reading, say so with what was checked. Fewer findings, including none, are a valid answer; never invent callers.

Provenance: gstack's deslop-shared-libs at the mirror pin (absorption.json `gstack.deslop-shared-libs`), in westack's words.
