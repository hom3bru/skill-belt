# Running a health check

## 1. The stack

`healthcheck.py detect <repo>` reads files and PATH only. A `## Health Stack` section in AGENTS.md (then CLAUDE.md) is used exactly as written, one `- category: command` line each (`typecheck`, `lint`, `tests`, `deadcode`, `shell`; `test`, `types` and `dead-code` are accepted; `none` declares a category unavailable). Without one, it looks for configuration: tsconfig, mypy or pyright for types; biome, eslint or ruff for lint; a package.json test script or pytest for tests; knip or vulture for dead code; shell scripts plus shellcheck on PATH. Anything else, such as a repository with its own test runner, needs a declared section or the user naming the command.

Show the commands before running them. Offer to save them as a Health Stack section only as a question: it is an instruction-file edit.

## 2. Running the tools

For each category with a command, in sequence (tools can share caches and locks):

1. Note the start time.
2. Run the command from the repository root with its full output (stdout and stderr) going to `<evidence>/<category>.log`. Never pipe the checker into a parser or `tail`: the exit code you record must be the checker's own.
3. Record the exit code and the duration, then hash the log (SHA-256).
4. Parse the counts from the whole log, never the displayed tail:
   - typecheck: `errors` (tsc: lines with `error TS`; mypy: the `Found N errors` line).
   - lint: `warnings`, every finding the linter reports (ruff: the `Found N errors` line; eslint and biome: the summary line).
   - tests: `collected`, `executed`, `passed`, `failed`, `skipped`. Errors count as failed; skipped tests are not executed. A runner that reports only its exit code leaves the counts out.
   - deadcode: `unused` (knip and vulture: one per reported item).
   - shell: `issues` (shellcheck: one per `In <file> line` block).
   - index: `verdict`, the `verdict` field of westack-onboard's `codeindex.py doctor` JSON (OK, WARN or ERR). When doctor finds no index for the repository at all, or westack-onboard is not installed, the category is `skipped` with that reason, not ERR: its weight is shared out.
5. One tool failing never stops the next.

A tool is `skipped` only when it is shown to be unavailable (not configured, not on PATH, no files to check), with that reason. If the log could not be written or read, the category is `error` with the reason. Never install a tool to fill a gap without a grant.

## 3. results.json

```json
{"format": "westack-health-results-1", "repo": "<path or name>", "date": "2026-11-04", "branch": "main",
 "revision": "<short sha>",
 "categories": {
   "tests": {"status": "ran", "command": "python -m pytest -q", "exit": 0, "duration_s": 41,
             "counts": {"collected": 120, "executed": 118, "passed": 118, "failed": 0, "skipped": 2},
             "log": "tests.log", "log_sha256": "<64 hex>"},
   "shell": {"status": "skipped", "reason": "no shell scripts"}}}
```

Every weighted category appears once. `healthcheck.py score` refuses a file that leaves one out, runs without a log hash, or has tests whose passed and failed do not add up to executed.

## 4. Scoring

The numbers are in [thresholds](thresholds.json). Each category scores 10, 7, 4 or 0:

| Category | Weight | 10 | 7 | 4 | 0 |
| --- | --- | --- | --- | --- | --- |
| typecheck | 22 | exit 0, no errors | under 10 errors | under 50 | 50 or more |
| lint | 18 | exit 0, no warnings | under 5 | under 20 | 20 or more |
| tests | 28 | exit 0, all executed passed | over 95% passed | over 80% | 80% or less, or none executed |
| deadcode | 13 | exit 0, nothing unused | under 5 | under 20 | 20 or more |
| shell | 9 | exit 0, no issues | under 5 | 5 or more | |
| index | 10 | doctor OK | doctor WARN | | doctor ERR |

A non-zero exit with nothing counted scores 4; tests that exited 0 without counts score 7. The composite is the weighted mean over the scored categories, one decimal: a skipped category's weight is shared among the others in proportion, and the report says "partial coverage" with the skipped reasons. With nothing scored, or any capture error, there is no composite.

Labels: 10 CLEAN, 7 to 9 WARNING, 4 to 6 NEEDS WORK, 0 to 3 CRITICAL.

## 5. Trend and recommendations

`history <history.jsonl> results.json` reads the last 10 lines and compares with the newest one only when both scored the same categories: improving, unchanged or declining (exit 1), with each declining category. A first run says so; changed coverage gives no delta.

`recommend results.json` lists categories below 10 by impact, weight times (10 minus score): first high, second medium, the rest low. Name the command that shows the detail (the tool's own verbose or report mode), never an auto-fix.

Keep the history file where the user says (the evidence folder by default, outside the work tree). Append the `history_line` only with the user's yes, and never for an unscored run.

Provenance: gstack's health skill at the mirror pin (absorption.json `gstack.health`), in westack's words.
