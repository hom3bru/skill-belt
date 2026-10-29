# Frankenmine 0.2.0

Frankenmine is a standalone, source-led skill. It mines useful mechanisms from several repositories or sources to create a NEW product, or to continue such a synthesis through design, authorized implementation and evaluation.

It can reject fusion in favour of an existing product or a minimal fresh build, and a fresh build may carry donor lessons. It is a usable prototype with tested local helpers. General agent effectiveness has not been qualified. Changes are listed in [CHANGELOG.md](CHANGELOG.md).

## Install or invoke

- **Claude Code.** Install the folder at `~/.claude/skills/frankenmine`, then invoke `/frankenmine` or describe a multi-source new-product task.
- **Codex.** Install it at `$CODEX_HOME/skills/frankenmine` (normally `~/.codex/skills/frankenmine`) and invoke `$frankenmine` on your next turn.
- **Other hosts.** They need their own installation.

Automatic discovery stays enabled. Reading SKILL.md explicitly also works for a manual invocation:

> Read `<skill-directory>/SKILL.md` and use Frankenmine to design a new [tool] from [donor URLs or local roots]. Inspect sources without executing donors. Write the dossier to [new output directory outside the skill folder]. Look for unexpected lessons beyond each donor's stated purpose. Compare the best existing solution and a minimal fresh build.

Supply what you know of:
- requirements;
- host and runtime;
- redistribution intent;
- source access;
- budget.

A new-product brief can start with no donor list; Frankenmine then runs a bounded search first. To continue an existing multi-donor synthesis, supply the prior build or manifest and the outcome you want next; see [continuation](references/continue-synthesis.md).

Other skills cover neighbouring jobs:
- improving an established project with outside mechanisms uses adopt-adapt;
- recovering one opaque or shipped product uses authorized reverse-engineer-anything (REA).

## Choose the record

| Record | Use when | What is written |
| --- | --- | --- |
| Answer (default) | Every task, unless one of the rows below applies | The reply, plus only the files the user asked for, in the folder the user named. No helper and no side files |
| Lite | The user asks for a checked dossier: up to three donors, design only, one session | `scaffold-lite` writes [the lite dossier](examples/lite-dossier.md) with numbered rows; fill it, `stamp` it beside the draft, and run `check-lite` |
| Full | Large catalogues, an existing JSON record, implementation with receipts, or machine checking on request | JSON envelope (`schemas/run.schema.json`, [contracts](references/contracts.md)) checked by the helper |

`check-lite` reads the lite dossier's tables, bullets and checklist and machine-checks what matters most for a small design: donor pins and snapshot hashes; the best-existing, minimal-fresh and fusion options with a decision and rationale; requirement coverage; each reused unit's route against its rights basis and licence category; oracle independence; receipts bound to product-file hashes when anything was implemented; and the saved review report. Seams are recorded only where material, plus one declaration for the rest; dependencies only for code routes. It returns `escalate-to-full` when the job outgrows lite: more than three donors, a process or rpc route, cross-language code reuse, or a key touched by three or more parts. Its output lists the full-tier checks it does not perform; `lite-complete` is never design readiness or package-schema validation.

## Local helper

The helper needs Python 3.10+ and only the standard library (use `python3` where `python` is absent). It works from any directory and resolves its schemas from its own folder. Use absolute paths, and put every output outside the skill folder; the helper refuses to write inside its own package root. In PowerShell, quote paths that contain `&`.

```powershell
python "<skill-directory>/scripts/frankenmine.py" init "<output-root>/run.json"
python "<skill-directory>/scripts/frankenmine.py" init "<output-root>/continuation/run.json" --decisions "<prior-product>/provenance/decisions.json"
python "<skill-directory>/scripts/frankenmine.py" inspect-python "<output-root>/donor-snapshot" --revision PINNED-REVISION --output "<output-root>/python-graph.json"
python "<skill-directory>/scripts/frankenmine.py" check "<output-root>/run.json"
python "<skill-directory>/scripts/frankenmine.py" report "<output-root>/run.json" --output "<output-root>/DOSSIER.md"
python "<skill-directory>/scripts/frankenmine.py" report "<output-root>/run.json" --output "<output-root>/DOSSIER-FULL.md" --include-record
python "<skill-directory>/scripts/frankenmine.py" handoff "<output-root>/run.json" --output "<output-root>/HANDOFF.json"
python "<skill-directory>/scripts/frankenmine.py" scaffold-lite --output "<output-root>/DOSSIER-draft.md" --donors 2 --parts 2 --requirements 3
python "<skill-directory>/scripts/frankenmine.py" stamp "<output-root>/DOSSIER-draft.md" --output "<output-root>/DOSSIER.md"
python "<skill-directory>/scripts/frankenmine.py" check-lite "<output-root>/DOSSIER.md"
python "<skill-directory>/scripts/frankenmine.py" scaffold "<output-root>/run.json" --donor D1 --unit src/x.rs --route narrow-port --id P1 --output "<output-root>/run-2.json"
python "<skill-directory>/scripts/frankenmine.py" stamp "<output-root>/run-2.json" --output "<output-root>/run-3.json"
python "<skill-directory>/scripts/frankenmine.py" review-packet "<output-root>/run-3.json" --output "<output-root>/review-packet"
python -B "<skill-directory>/tests/run_tests.py" --output "<new-results-directory>"
```

**Outputs and exit codes.**
- Choose unused output names; init, inventory, report, handoff, scaffold, stamp and review-packet never replace a file or folder. To resume, edit your own run record with ordinary file tools and run `check` again.
- `scaffold` appends a candidate stub (seam, rights, protocol for process/rpc, and the 13 deltas across languages) whose values are `TODO(scaffold)` placeholders, plus an unresolved line; the record stays blocked until they are filled.
- `stamp` fills every missing file hash, and missing evidence revisions, into a new record. A recorded hash that disagrees with its file is reported (exit 2) and never rewritten: a changed oracle or snapshot needs a new decision, not a new hash.
- `review-packet` writes a new folder for a fresh reviewer: `PACKET.md`, copied evidence and oracles, `REVIEW-TEMPLATE.md` and `packet.json`. It withholds the decision, rationale, tradeoff prose and readiness verdict. See [verification](references/verification.md).
- `check-lite` exits **0** for `lite-complete` and **2** for `lite-incomplete` or `escalate-to-full`. `stamp` on a `.md` dossier fills its empty SHA-256 cells into a new file beside its source and never rewrites a recorded hash; it refuses any other folder, where the dossier's file paths would not resolve. `scaffold-lite` takes one to three donors.
- Initial skeletons fail readiness on purpose, and they name their TODO fields.
- `check` and `report` exit **0** for a design-ready record and **2** for a blocked or invalid one.
- In implementation mode, a ready record reports `design-ready; implementation-unverified` until every selected part is tested and its required tests pass. Implementation evidence never masquerades as design readiness.
- `report` writes the full dossier: brief, donors, evidence, both-direction lesson ledger, contracts with seams and rights, requirement coverage, ownership, interactions, alternatives, tests with receipt history, and review. It also writes for a valid but incomplete record while returning 2. Raw JSON is included only with `--include-record`. Invalid JSON or schema records produce errors and no report.
- The inventory is a static graph that records imported names and visible omissions. Zero nodes is not qualification. A run may cite the graph file as `static-graph` supporting evidence.

**Records.**
- Schema 1.1 is current. A 1.0 record is still validated against its frozen schema (`schemas/run-1.0.schema.json`), so it parses exactly as before, but it cannot become design-ready until it is upgraded by hand ([steps](references/contracts.md#upgrading-a-10-record)).
- Implementation receipts name the product files they tested; `check` re-hashes them, so a receipt for changed bytes is stale. Product files carry their provenance (reused, adapted or authored) in `artifacts`.
- Copy bounded, lawful source evidence into the run root, with portable relative paths, revision, line range and SHA-256. Documentation, product observations and screenshots go in `supporting_evidence`, which is weaker than a source snapshot. Each needs a URL or snapshot plus a retrieval date.
- Evidence links and escapes are rejected.
- Commands recorded in a run are data; the helper never executes them. It never contacts network services, creates credentials, installs anything or changes host settings.

**`handoff`** is an opt-in, derived JSON view: exact source and owner locators, and the next pending interaction, ownership decision, review or contract check. It also refuses to replace a file. Add `--decisions PATH` to compare against an original manifest by exact donor ID and source URL.
- Exit **2** keeps a useful incomplete view when validation or manifest joins block it. Malformed envelopes and duplicate IDs produce no index.
- Exit **0** means only that the record is consistent.

See [handoff details and limits](references/handoff-index.md).

**`init --decisions`** accepts a local manifest of this shape, including the existing westack provenance shape: `{ "decisions": [{ "id": "D01", "source_url": "https://example.com/source", "catalogue_id": "optional-label" }] }`.
- Every unique decision becomes a queued donor. Catalogue labels are kept only as untrusted scope notes. Languages stay empty, and inspection, rights and review are not fabricated.
- A literal full GitHub blob/tree commit is parsed without retrieval. Other sources stay `unpinned` with a blind spot. A selected donor needs a real pin before readiness.
- Malformed or ambiguous input, duplicate IDs, missing URLs and output replacement are rejected. No URL is fetched, and the input manifest is left unchanged.

## Examples and tests

**[Authored synthetic case](examples/synthetic/README.md).** It applies a game-checkpoint identity lesson and reimplements JavaScript exact-decimal arithmetic in a new Python ReplayTotal slice. It shows:
- donor-led lessons that differ from target-led ones;
- all 13 semantic dimensions, including the string-parsing delta (`BigInt("")` is `0n`; Python `int("٣")` is 3);
- one state owner, with seam evidence;
- requirement coverage that names new code;
- an integration test for the pair;
- rights and provenance, alternatives and recovery contracts.

Its frozen oracle is independent of donor test suites but authored by the builder. No independent reviewer or multi-host agent success is claimed.

**Shipped records.** Both examples are schema 1.1 and are built by `tests/fixture_builder.py`.
- `examples/synthetic/run.json` is a design record with tests not-run.
- `examples/no-fusion/run.json` shows a minimal-fresh decision that keeps both donor lessons selected as pattern-only provenance; successful fusion is not a quota.
- Both stay blocked only by honest self-review and an unresolved blocker.

**westack.** [westack](examples/westack-planning.md) is a worked example of continued synthesis.

**Tests.** The suite covers:
- CLI flows and package-root write refusal;
- tampered or omitted rights, provenance, revisions and pins;
- ownership (including normalized key variants), interactions and independence claims;
- semantic deltas, protocols, seams and supporting evidence;
- oracle bytes, receipt history, zero-case runs and receipt honesty;
- placeholder text, malformed JSON and unsafe paths;
- loading every shipped 1.0 record;
- rights by route, retained dependencies, artifact-bound and stale receipts, group interactions, saved review reports, `check-lite`, and the `stamp`, `scaffold` and `review-packet` helpers, including the fooling cases from the round-2 review.

It runs the authored product oracle and ablates both material contributions, including permissive-parsing mutants. No third-party donor code is executed. All test inputs and outputs stay under the caller's new results directory.

## Limits and release state

**Helper limits.** The Python AST adapter inventories syntax-level imports, imported names and calls only; it neither resolves complete closure nor qualifies runtime seams. The worked ReplayTotal slice handles integer-string amounts in memory; fractional currency parsing and durable file persistence are outside that example's contract. These are unavailable, and manual contracts cover the decisions:
- other language frontends;
- automatic source transplantation and translation;
- FFI/RPC/WASM generation;
- universal compatibility.

Helpers reject ordinary evidence links and package junctions, but they are not a sandbox against a concurrently hostile filesystem.

**What a pass does not prove.** A matching hash proves bytes, not truth. Records cannot grant authority or prove their own independent review; the independence level is declared by the author and must be honest. None of these has been established:
- trigger precision or recall;
- general benefit or model cost improvement;
- multi-host agent behaviour;
- a representative cross-language release.

The [live-agent protocol](evals/LIVE_AGENT_PROTOCOL.md) and the labelled prompts are supplied with status **not-run**.

**Earlier reviews.** The v0.1.1 audit's independent package design review and exploratory offline usage trial are build records, omitted from this public edition with the other historical 0.1.x `evidence/` files. Only `evidence/synthetic-run/`, a schema 1.0 record the tests load, is kept. The packaged synthetic product's independent review is a separate gate that has still not been run.

**Research inputs** were provided by the parent task and verified by hash, not materialized locally from Library. In this public edition the design specification's private citations are replaced with public links, so it is not byte-identical to its input. [Research lineage](references/research.md) distinguishes previous source inspection from this build's checks. No external donor tool was installed or rerun.
