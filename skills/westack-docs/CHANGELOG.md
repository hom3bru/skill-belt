# Changelog

## 1.0.0-alpha.49 (diagram mode), unreleased

westack-docs 1.0.0-alpha.1 adds a diagram mode (`references/diagram.md`): mermaid source first, every node and edge from the source; SVG, PNG and an editable Excalidraw file rendered in the host's browser from one offline bundle found in a fixed order (a copy shipped in `assets/` with its pin, a bundle the user names and `diagramcheck.py renderer` verifies, or none, with renders reported not-run); never a CDN. `scripts/diagramcheck.py` reads flowchart labels back from every render and checks the PNG and scene shapes. The "Not this skill" line that sent Excalidraw diagrams to gstack's diagram skill is gone. Ideas from gstack's diagram at the mirror pin. Shipping the bundle itself waits on a licence check of its 248 bundled packages (the donor's licence table is stale), which needs a network grant. `tests/test_diagramcheck.py`: 7 tests; a copy that skips the label comparison fails them. A live render with the mirror's pinned bundle produced all three formats for the fixture flowchart, every label present.

## 1.0.0-alpha.34 (lean start pages: review, ship, docs, research, orchestrate), unreleased

`SKILL.md` is now a short start page: when to use it and when not, the mode table naming the page each mode reads, the rules behind the measured wins that hold in every mode, and the report. Everything else moved word for word into a reference read on demand, and the page says to read a mode's pages in one turn with the first look at the work. The description and the minimum core block are unchanged; no rule changed; rule numbers are kept on both sides of the split. `SKILL.md` 1,200 to 977 words (805 to 582 without the core block). Kept: the mode table, rules 1 (inventory first, WD-1: preserve meaning) and 2 (add nothing, WD-3: no stance, stakes or figure the source lacks), not this skill and the report. New `references/every-mode.md` (325 words: rules 3 to 8, WD-4, WD-11, WD-15, WD-10, WD-18 and WD-17, and the `prose.py` check), read in every mode; its two links now point within `references/`. No pinned phrase moved. The `where` values in `provenance/donors.json` follow the moved sections.

## 1.0.0-alpha.30 (dsh-superagent: DS-5), unreleased

One rule for drift reports, from deepseek-ai/dsh-superagent-prototype at `6337fc82` (MIT; ideas only, in westack's words, nothing copied or run), approved by the user ("Brief and send all", 2026-10-31). No SKILL.md change (1,173 words, ceiling 1,180).

- **DS-5, inventories both ways.** A document that lists a folder's files, tests or commands is checked in both directions: every item that exists is listed, and every listed item exists; in a numbered series read in order, a document links only to earlier ones. `references/sync.md`, Drift: 426 to 498 words.
- **`scripts/prose.py inventory DOC FOLDER [--glob PATTERN] [--recursive]` and `series FOLDER [--glob PATTERN]`.** `inventory-unlisted` and `inventory-stale`; `series-forward-link` (a link to a numbered document of the same or a higher number). A document names a file in a code span or a link target (a bare name is the folder's, a path is read from the document's folder); fenced blocks and bare names in prose are not read.
- **Tests.** `tests/test_inventory.py`, 22 (90 in the suite): red first against a stub (22 tests, 8 failures, 12 errors), then green. Four broken copies: one that checks only the unlisted direction misses the stale row, one that checks only the stale direction misses the unlisted module, one that reads every path as the folder's flags another folder's file, and one without the order check lets `002` link to `004`.
- **Provenance.** One record. Not carried: the 100-word message cap (needs calibration first; `rules.md:37`).

Known limits: names only. A listed item's description can be wrong and pass; a file mentioned only in prose or a fence is not read.

## 1.0.0-alpha.29 (slim: less loaded, fewer steps on small tasks), unreleased

The regenerated minimum core block (the core is found only before the first core helper or reference; a new Lean rule; the broken-copy control applies when the work adds or claims a check). Core references are named on demand, each only when its step needs it, instead of loaded at start. `SKILL.md` 1,197 to 1,173 words. No rule changed.

## 1.0.0-alpha.25 (evals: harder cases A; research and plan fixes), unreleased

Task cases only; `SKILL.md`, references and scripts are unchanged, and so is `evals/routing-fixtures/`. The first measurement had docs at +0.38 on its 2 cases.

- Task cases 2 to 8. Each new case carries `"added": "2026-10-31"` and is held out for the next measurement (`notes.held_out_2026_10_31`); each names the rule it tests (file:line), the honest answer and the trap in the notes. Traps were written from the skill's rules, not from the first measurement's transcripts. Offline fixtures, model-free regex graders; every good canary scores 1.000 and every bad one is caught below 0.5 (or hard-fails) on a criterion it names, by westack-eval's own blind export, deterministic grader and calibration (`tools/eval/tests/test_harder_cases_a.py`). Nothing was run on a host.
  - `drift-config`: drift against the code's real behaviour (sync.md:3, :27). A constant marked as the documented default is never read: the default is 25, the doc says 60, and the doc's test count is wrong. Trap: trust the constant.
  - `sync-flag-rename`: instruction files owe an edit for a contract, not a private rename, and a fact lives once (sync.md:7-21). A flag rename, a helper rename, and a build command in two AGENTS.md files. Trap: update the command in both. In review, C3 was widened to credit removing the duplicate from either file.
  - `pr-claims-tests`: the author's errors stay visible (SKILL.md:54; preserve.md:61). The draft PR claims retry tests the diff does not add. Trap: polish it to READY TO POST.
  - `runbook-token`: a secret passed as a flag value (doctypes.md:34). `--token "$DEPLOY_TOKEN"` on a shared host where `--token-stdin` exists. Trap: CLEAN.
  - `draft-unshipped`: shipped behaviour only (SKILL.md:55). The parser lists a PDF format the code refuses. Trap: document PDF or promise 2.4.
  - `causal-claim`: a causal claim needs support (SKILL.md:53; rules.md:7). Two runs, a coincidence and an unruled-out cache change behind "cuts peak memory by 25%". Trap: SUPPORTED because the arithmetic holds.

## 1.0.0-alpha.18 (test integrity fixes), unreleased

- WB-20, the two gaps closed: `references/rules.json` `template-placeholder` now also fails a single-curly slot (`{date}`, `{title of option 1}`) and a guidance comment that does not begin with a to-do word (`<!-- Describe the context here -->`, an optional-section note), in every mode with its line; `gap-marker` is unchanged. Field sets such as `{code, observed, limit}`, path templates (`/users/{id}`), globs, set and math notation and code stay clean. Examples for each new form and for filler text are in the rules file; `tests/test_prose.py` gains 9 tests (59 to 68), red first, with a control for each of the pattern's 8 alternatives. `references/rules.md` names the new forms (873 to 897 words). `prose.py selflint` over the repository: clean before and after, no ceiling or exclusion changed. The earlier entries below say these two forms were not matched; that was true at 1.0.0-alpha.13.

## 1.0.0-alpha.13 (build follow-ups), unreleased

- WB-20 recorded as a P2 application (line below, record `p2:adr/madr`). No rule or code changed: WD-6's `template-placeholder` and `gap-marker` rules already carry the docs half. A probe found two forms they do not match, MADR's single-curly `{date}` and a guidance comment that does not begin with a to-do word; both are listed as gaps, not fixed here. The architecture half waits for the planned westack-architecture.

## 1.0.0-alpha.10, unreleased

First build of `westack-docs` (skill version 1.0.0-alpha.0), model-invocable. It writes, revises and audits prose a person reads and keeps instruction files true to the code, in six modes that are each their own grant: audit, revise-wording, revise-structure, draft, sync and drift. Ideas only, in westack's own words. The core's craft, context, finish, evidence-vocabulary, authority and guards references are pointed to, not restated.

- Package: `SKILL.md` (1,197 words with its Minimum Core block; description 409 characters), `references/preserve.md`, `rules.md`, `doctypes.md`, `sync.md` and `rules.json` (18 checked rules, 7 judgment rules, 1 detector measured and not adopted, no numeric gate, the self-lint exclusions and one logged ceiling), `scripts/prose.py` (`preserve`, `lint`, `selflint`; reads files and prints JSON, writes nothing, runs nothing, opens no network connection), `tests/test_prose.py` (59 tests: 58 written first, 55 of them red against a stub, the other three being the static no-write scan and two usage exits; one more added after the first green run, a rules file without each checked rule in turn, so every rule has a broken-copy control), `evals/` (20 trigger cases with a held-out split; two offline task cases with model-free graders), `provenance/donors.json` (13 records).
- Core amendment, one word: core `references/craft.md` line 7 now lists "performed hedges" as prose slop, not every hedge (416 to 417 words against the P2 cap of 417.6 in `tests/test_p2_memory.py`). The split between evidential and performed hedges is in `references/rules.md` (Hedges).
- Lint findings are candidates for a reader. The helper never rewrites a file, and a test hashes every input before and after an audit run; its control, a copy that writes back, changes a hash.
- Self-lint calibration on westack's own pages (2026-10-30, 148 files): clean after the three exclusions, each of them live. One quoted example in westack-verify `references/claim.md:3` is logged as the diff-narration ceiling of 1, which can only move down. The bare 'no longer' form of that rule matched two present-state sentences and no narration, so it was not adopted; `rules.json` lists it under `reverted` with both locations.
- Integration (the commit after this one): the core manifest lists `docs` as built (model-invocable, wave 3, excluding review, ship and research), the router's table moves it to the built row and its verb line maps "document" to `docs`, the README lists it with its suite command, and the donor test counts this file's one `p2:` record and drops SS-105 from its deferred list; its two id patterns now accept three-digit ids, since SS-105 is the first applied.

Items from the writing reads (the brief's ids; sources and pins in `provenance/donors.json`):

- WD-1 (preservation inventory): `SKILL.md` rule 1, `references/preserve.md` (The inventory). `prose.py preserve` counts hedge, condition, attribution, negation, scope and strength words per class: a dropped hedge, condition or attribution word, a changed negation or scope count or an added strength word fails; contractions expand first.
- WD-2 (mechanical comparison): `prose.py preserve` fails on changed fences, front matter, quotations, tables, inline code, links, paths and heading levels; warns on dropped numbers or names, heading wording and a shrink below 60%; its claim says it is not semantic proof.
- WD-3 (add nothing): `SKILL.md` rule 2, `references/preserve.md` (Add nothing, Map every change). `preserve` fails on a number or name the original lacks, reports a byte-identical rewrite as the no-op result, and with `--map` fails every changed hunk that no finding or request covers.
- WD-4 (evidence-bound prose): `SKILL.md` rule 3, `references/rules.md`. `lint` reports causal verbs, comparatives with no baseline and performed hedges as candidates that never change the exit code; universals and summaries are judgment rules.
- WD-5 (current-state documents): `references/doctypes.md`, `rules.json` levels. Change narration fails in a README and is skipped (listed as not audited) in a changelog; a reply gets it as a candidate.
- WD-6 (what no person types): `rules.json`. Leaked citation tokens, an assistant's tracking parameter, pasted assistant lines, invisible characters (emoji joiners and a leading byte-order mark allowed) and template leftovers fail in every mode; a gap marker is open in a draft and a finding in delivery.
- WD-7 (the rule contract): `rules.json` and `prose.py`. Every checked rule has must-fire and must-not-fire examples, checked as the file loads; a judgment rule has a reason; a detector not adopted stays listed with its false positive.
- WD-8 (self-lint): `prose.py selflint` and `tools/tests/test_docs_selflint.py`. Per-exclusion hit counts beside the naive scan, ceilings logged and only lowered, exit 2 on a file that is not UTF-8. Overlaps the adoption list's CM-34 (lint westack's own pages).
- WD-9 (calibrated gates): `rules.json` (`gates_about`) and `prose.py`. A numeric gate needs a hashed corpus of at least 100 documents in two registers; a changed corpus file stops the run. No gate ships.
- WD-10 (precedence): `SKILL.md` rule 6.
- WD-11 (the author's errors): `SKILL.md` rule 4, `references/preserve.md`.
- WD-12 (as-built pages): `references/doctypes.md`; `lint --type as-built` fails a page without its last-verified commit, last-updated date or applies-when line.
- WD-13 (docs roots): `lint --roots`; a file outside the roots fails, and an exception that is a folder, a pattern or unreasoned stops the run.
- WD-14 (policy documents tested like code): `references/doctypes.md`, `rules.json` (secret-in-argument, implicit-login), `tools/tests/test_docs_selflint.py` (a seeded line in a copy of core `authority.md` fails with its file and line).
- WD-15 (shipped behaviour only): `SKILL.md` rule 5; a judgment rule, exercised by the audit-readme task case (a documented flag the code lacks).
- WD-16 (UI copy): `references/doctypes.md`, `lint --type ui` (a generic button, a generic confirmation and an apologising error give three findings).
- WD-17 (replies lead with the decision): `references/doctypes.md`; a judgment rule, exercised by the reply task case (decision first, every number kept, no computed figure).
- WD-18 (line breaks at the destination): `references/doctypes.md`, `lint --type pr` and `--type reply` flag a hard-wrapped paragraph; a Markdown file passes.
- SS-106 (adoption list, P3): `references/sync.md` (Drift). Differences only, with an explicit no-drift line per document and a not-checked line for anything not compared.

Defers and references: `docs-gstack-diagram` stays as it is. The installed iceberg plugin is recorded in the provenance file as a reference only, with its flags (an edit that writes in place, a description that applies itself to every document, a rule set that strips every hedge, a Stop hook that injects a score file into a system message); there is no defer to it, and nothing of it was run.

Not carried (recorded as rejected in the provenance file): anti-defensive-writing's policy of leaving out unfavourable results, vocabulary ban lists, stylometry, dash bans other than a repository's own style, and added reactions. No donor gives a README, ADR or changelog skeleton, and none is invented here.

Known limits: the trigger cases and both task cases are not-run, so nothing here is a measured effect; `preserve` compares words, not meaning; the evidence candidates are noisy on purpose (29 comparatives and 45 causal verbs kept on westack's own pages, none gated).

## 1.0.0-alpha.5 (P2 adoption), unreleased

The P2 backlog items whose home is this skill: SS-105, applied in its first build (1.0.0-alpha.10 above), and WB-20, recorded in the build follow-ups (1.0.0-alpha.13).

- P2 (SS-105): `references/sync.md` (Sync: instruction files). An instruction file owes an edit only for a changed boundary, contract, pattern, pitfall or dependency, never for an internal refactor; edit leaf first, put each fact in the shallowest file whose folder covers all the code it describes, and never twice; each edit needs the user's grant for that file, otherwise it is delivered as proposed text. Reading instruction files stays in core `context.md`.
- P2 (WB-20): `references/rules.json` (`template-placeholder`, `gap-marker`) and `prose.py lint`, carried by WD-6 and recorded in 1.0.0-alpha.13. A template leftover fails in every mode with its line; a deliberate gap marker is open in a draft and a finding in delivery. Not matched: MADR's single-curly `{date}` and a guidance comment that does not begin with a to-do word. The architecture half stays deferred to the planned westack-architecture.
