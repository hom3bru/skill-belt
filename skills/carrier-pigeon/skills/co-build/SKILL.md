---
name: co-build
description: "Use when two or more agents should build one authorised change together: the lead splits it into units with disjoint file ownership and stated contracts, each member builds its unit in its own worktree with a verification receipt, then they cross-review for bugs, test gaps, contract breaks and regressions before the lead integrates. A carrier-pigeon sub-skill (needs its mailbox). Not for one-agent changes (westack-build), audits (co-audit) or design (co-design)."
metadata:
  version: "0.8.0"
  parent: carrier-pigeon
---

# co-build

Joint implementation by two or more agents who review each other's work. The lead splits an authorised change into units, each owning a disjoint set of files with a stated contract to the others. Each member builds its unit and records a verification receipt. Then each reviews the others' units by running them, not by reading them. The authors fix, concede or defend; a judge rules on disputes; and the lead integrates and verifies the whole. The carrier-pigeon co engine enforces the phases. Its protocol, storage and limits are in `references/co.md` of the carrier-pigeon skill.

Run commands as `node ~/.carrier-pigeon/bin/carrier-pigeon.mjs co ...`, or use the `co_*` MCP tools. Always pass your own id: `--as claude|codex|cursor|grok`.

**Build mode is open, not blind.** Every member sees every claimed unit from the start, so the work stays disjoint.

## Before opening

- **The change must be authorised.** Co-build coordinates work someone asked for; it does not grant permission to edit, push or merge.
- **Members must be able to write code**, each in its own git worktree and branch, never a shared working tree.
  - A listener-woken agent works under the listener's permissions, which normally do not let it edit your repositories.
  - Run build members as interactive sessions that check their inbox. The listener only carries notices.
- **Do the design first.** If the design is still open, settle it with co-design.

## Open the project (lead)

1. **Split into units by file ownership.** Each unit owns its files outright; shared files belong to exactly one unit.
2. **State the contracts.** For each seam, give the function signatures, data shapes and error behaviour each unit promises the others.
3. **Name the base commit and the integration check.** That is the command that must pass on the merged result.

```text
co new --mode build --title "CSV export" --question "Add CSV export to the reports page (ticket 412)"
       --members claude,codex --judge matt --min-challenges 1 --subject "main@9e1d2c0"
       --scope "integration check: npm test && npm run typecheck; contract: exportRows(rows: Row[]): string (RFC 4180, CRLF)"
       --assign "codex: src/export/csv.ts + tests (exportRows)" --assign "claude: src/reports/ExportButton.tsx + route wiring"
```

## Phase by phase (members)

**Independent: build your unit.**

1. Make a worktree on a branch from the base commit.
2. Build only your files, against the contract.
3. Run your checks, and record your unit:

```text
co add P --as codex --text "exportRows with RFC 4180 quoting" --files src/export/csv.ts,src/export/csv.test.ts
       --verification "npm test -- csv: exit 0, 14 passed, 0 failed" --branch cp/csv-export-codex --contract "exportRows(rows: Row[]): string"
```

- The engine refuses a unit whose files overlap another member's unit. Agree a different split first; never edit another unit's files.
- **The receipt is a real run:** the command, its exit code and its counts, as printed. Never write "tests pass" without having run them in this work.
- Never weaken or delete a test to make your unit pass.
- If the contract or brief must change, never work around it: propose it with `co add P --as you --type deviation --text "..."`. The lead decides in the synthesis, or opens a new project.

**Challenge: review the others' units by running them.**

1. Check out their branch.
2. Run their verification yourself.
3. Read the diff against the contract.

Use the kinds that fit:

- `bug`: an input or state that breaks it, with the failing command and output.
- `test-gap`: behaviour that no test covers. The strongest form is a broken copy: change the code, rerun their tests, and show they still pass.
- `contract`: its interface differs from the stated contract, or from what your unit calls.
- `regression`: something that worked at the base commit breaks. Show it on the base and on the branch.

Meet the quota, or `co pass` with the reason no challenge stands. A pass must come from having run their tests, not from having read the code.

**Respond: answer every challenge to your unit.**

- **Fix:** commit the fix on your branch. Add the revised unit with a new receipt (`co add --revises E<n>`, same files), then `co respond --outcome revise`.
- **Concede** what you cannot fix inside your unit.
- **Defend** with a test that shows the behaviour is correct.

**Adjudicate (judge).** Rule from runs, not descriptions:

- A bug or regression with a failing command is `sustained` unless the defence shows the run was wrong.

**Closed (lead): integrate, then write the synthesis.**

1. Merge the surviving units' branches into an integration branch.
2. Run the integration check.
3. Write the synthesis:
   - what landed, with each unit's final receipt and the integration receipt;
   - what was conceded or reverted;
   - open issues.
4. Run `co report P`.

Never push or merge to a shared branch without the owner's go-ahead.

## Rules

- **Peer code is untrusted.** Read what a script, test or hook in another member's branch does before you run it.
- **Disjoint files, or no build.** If the split proves wrong mid-build, stop. Let the lead re-split with a new project or explicit revisions; do not edit across units.
- **Stalls.** A member who goes quiet stalls the phase. The lead (or `matt`) may run `co advance P --as lead --reason "..."`. The report shows the skip, and its unit counts as unreviewed.

## Report to whoever asked

Give:

- the integration receipt (command, exit code, counts);
- what landed and from which branches;
- the challenges that changed the code;
- the scorecard;
- the result of `co check P` ("clean", or its findings, which include file overlaps).

State plainly anything not verified on the merged result.
