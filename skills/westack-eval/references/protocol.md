# Protocol

One campaign answers one question. A campaign is a folder; everything it produces stays in it.

| Path | Written by | Holds |
| --- | --- | --- |
| `campaign.json` | you, before anything runs | the design ([cases and rubrics](cases-and-rubrics.md)) |
| `prereg.json` | `campaign.py register`, once | hashes of everything that decides the outcome, and the power plan |
| `ledger.jsonl` | the runner or `route.py proxy` | one line per run (status, usage, cost, decision), hash-chained, append-only |
| `runs/run-NNNN/` | the runner | prompt, stream, stderr, final message, work folder, changed files |
| `blind/` | `blind.py export`, once | what graders see: case prompts, rubrics, anonymous items |
| `sealed/` | `blind.py export` | the item-to-arm mapping and any leak report; graders never open it |
| `grades/` | the grader | one sheet per grader |
| `results/`, `analyses.jsonl` | `campaign.py analyse` | each analysis, and which grader's sheet it used |

Scripts below are in this skill's `scripts/` folder unless the path says `tools/eval/` (the westack repository).

## 1. Frame

Write down the hypothesis, the arms, the comparisons and the margin before writing cases.

- **Arms.** `bare` (nothing installed), the arm with the skill (its folder, plus the westack core beside a westack sub-skill), optionally the strongest single donor. The arm's `prefix` is how a user would invoke it, for example `/westack-eval `; the run command, environment, tools, fixture, timeout and budget are identical across arms. Only the installed skill folder and the prefix may differ, never a flag or an environment variable: the ledger holds each run's command and environment hashes, and the analysis refuses arms that differ.
- **Comparisons.** One `primary` (usually skill versus bare), one per host when several are wired (release: [reading results](reading-results.md), Promoting a change). `secondary` ones are reported but do not drive the decision. A `control` comparison (a broken copy versus its baseline) must never come out better, or the campaign is invalid.
- **Margin.** The smallest improvement worth having, on the net-win-rate scale: (wins - losses) / cases. For pass/fail rubrics it is the pass-rate difference in points.
- **Builder.** Who built what is under test. The grader must be someone else.
- **Independence and drops.** Write why the cases share no state, time, rate limit, cache or instruction file (`analysis.independence_argument`); fresh folders and shuffled order do not establish it, and without the argument every verdict stays descriptive. Register `analysis.max_dropped`, the share of cases that may lack a gradable run: beyond it the comparison is invalid.
- **Lineage.** A follow-up names, in its `hypothesis` (hashed), the earlier campaign and the result it builds on; if it cannot name one, it is a sibling and inherits nothing. The next round descends from the last round's winner (for a description, the version `route.py keep` kept), not from the start. A grader change after the outputs exist is such a follow-up: grade the kept outputs again in a new campaign that names the first and checks each output's hash against it, with no new host runs (a failed lookup is a grader error, excluded and listed, never a fail). No helper imports kept outputs yet, so until one does a re-grade is hand-made and reported as such.

## 2. Plan the power and the budget

```text
python scripts/campaign.py plan DIR
python scripts/evalstats.py plan --margin 0.3 --tie-rate 0.5
```

`plan` reports the cases needed for 80% power at alpha 0.05, the power at the planned number, the planned host runs (cases x replicates x arms) against the run cap, and the most the runs can cost against the dollar budget. When the planned cases cannot reach the power, the analysis can only say inconclusive (or worse): add cases or widen the margin first, or run it knowingly as a pilot. It also warns when the independence argument or `max_dropped` is missing.

Declare the tie rate honestly (the share of cases where both arms score the same). Power at a fixed margin changes with the tie rate (a declared rate above the one observed overstates it), so the analysis re-checks the power at the observed rate whenever it differs from the declared one, in either direction: below the target there, no better, worse or equivalent is returned.

## 3. Register

`python scripts/campaign.py register DIR` validates the design, hashes it and writes `prereg.json`; it refuses a second registration. To pool several campaigns into one claim, register the pool now, after its members and before any of them runs ([pooled studies](pooled.md)). A campaign that has run is frozen: a new idea is a new campaign (see Lineage), never an edit. `campaign.py verify DIR` names any component that changed: frame, cases, rubrics, arms, analysis, grading, budget, host, blind, fixtures, skills, population. The runner verifies before every launch and records the hash of each skill copy it installs; the analysis rejects a run whose copy differs from the registered one. Both hashes cover what ships (no `evals/`, `tests/` or `.validation/`), so editing a skill's cases is not editing the skill. Before replacing harness code (runner, fixture builder, grader), record what each case receives under the old and the new code (prompt, fixture, command and environment hashes): identical inputs keep the baseline; a difference is named and the baseline run again.

## 4. Run

Host runs need the westack repository and Claude Code (Codex and Cursor are not wired yet):

```text
python tools/eval/campaign_run.py DIR --dry-run
python tools/eval/campaign_run.py DIR
```

- **Smoke first.** `--dry-run` proves setup, not inference: run one case in a scratch copy of the campaign (own registration) and read its stream for a model call, the skill listing and the cost. A clean exit with no model call (an expired login) is `blocked`: excluded, and counted as a host error.
- Each run gets a fresh work folder: a copy of the case fixture plus what ships of the arm's skill folders under `.claude/skills/`. A skill's own `evals/`, `tests/` and `.validation/` are never copied: they hold the rubrics and canaries, and the host could read them.
- Command line: `claude -p --output-format stream-json --setting-sources project --strict-mcp-config --settings <read block> --tools ... --allowedTools ... --disallowedTools WebFetch,WebSearch,... --permission-mode acceptEdits --permission-prompts none --no-session-persistence --max-budget-usd <cap>`. Any `--dangerously-*`, bypass or approval-skipping flag is refused before launch.
- Reads stay in the work folder: a bare Read, Glob or Grep in `host.allow` becomes `Read(./**)`, a read rule naming a path outside the folder is refused, and the settings block (`permissions.blockReadsOutsideWorkingDirectories`) refuses reads outside it in every mode. A shell command or a script is not covered.
- The child process alone gets `CLAUDE_CODE_PWSH_PARSE_TIMEOUT_MS=20000`, `DISABLE_AUTOUPDATER=1` and `PYTHONDONTWRITEBYTECODE=1` (no `__pycache__` in the work folder); pwsh is warmed twice first, because under load the PowerShell permission parser times out and denies allowed commands; such denials are recorded as host noise.
- A hard timeout (`host.timeout_min`) kills the process tree that run started and nothing else.
- **Budget.** Before each run: the run cap, then the dollar budget (the next run's cap must still fit), then the token budget. After each run the stream's usage and cost go to the ledger; an unknown cost is charged at the cap. The campaign stops when it exceeds its budget, when a run costs more than 1.5 times its cap, on a rate or usage limit, or after three host errors in a row. Exit 0 complete, 1 refused, 2 stopped early. A later invocation resumes the runs not yet in the ledger.
- **Ledger.** A run's start and cap are written before launch, one terminal entry after (with `model_calls`, `outcome`, and `engaged`: true, false, or `unobservable` when the host exposes no events). A start with no terminal is a crash: charged at its cap, never re-run silently (the next invocation stops as `unfinished` until `--rerun-unfinished`, which repairs the run in place, at most twice per run, the core's retry limit in `durable.md`; a third crash stops and asks). A run with a terminal entry is never run again. Never stop on the outcome being estimated; a stop the runner must make is recorded `truncated`, and the analysis leaves the unrun cases out.

Routing with the proxy spawns nothing: `python scripts/route.py proxy DIR`.

## 5. Blind

`python scripts/blind.py export DIR` writes each gradable run (completed, timeout, budget stop) and each canary as an item with a random id, scrubs paths, skill names, prefixes and run ids, and drops the arm's slash prefix from the prompt. An independent scan then normalises every file and file name and looks for the same identifiers; any hit marks the export `rejected`, and grading and analysis refuse it. Common-word skill names (a donor called `review`) can be listed in `blind.weak_names` so only their slash and path forms count; that weakens the blind and is reported. A declared `blind.sentinel` is first proven findable in a scratch folder, then rejects the export if it turns up in a fixture, skill folder, host run or link out of either.

## 6. Grade

- `python scripts/grade.py auto DIR`: the deterministic grader applies each criterion's pre-registered regex `check` to the blind items.
- `python scripts/grade.py template DIR --grader-id ID --independence human|different-model|fresh-context-same-model`: a sheet for a separate grader, who reads `blind/` only.

A grader is rejected when it is the builder, when it claims independence `self`, when an item is missing, when a model grader breaks its contract (no quote for a credit, a tool exposed or undeclared; see [cases and rubrics](cases-and-rubrics.md)), or when it fails calibration: every known-good canary must score at least 0.5 without a hard fail, every known-bad one below 0.5 or hard-failed, a bad canary that names its targets must fail one of them, and not every item may get the same score. A grader from another vendor needs consent first (`critique.md`).

## 7. Analyse

`python scripts/campaign.py analyse DIR --grades FILE` (exit 0 valid, 1 invalid, 2 not-run). It re-verifies the registration and the ledger chain, re-scans the blind, unblinds against the sealed hash, validates and calibrates the grader, checks the skill copies, tabulates each criterion across the arms, then compares arms case by case. For each arm that installs a skill it counts the runs where the host loaded and used the skill; an arm with none makes that comparison inconclusive. Exit 3: valid, but a golden case failed. Read the result with [reading results](reading-results.md); decide with [drop or slim](drop-or-slim.md).
