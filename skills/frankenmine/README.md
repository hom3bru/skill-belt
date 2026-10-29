# Frankenmine 0.1.2 — portfolio edition

A standalone source-led skill for mining useful mechanisms from multiple repositories to create or continue a coherent product synthesis, through design, authorized implementation and evaluation. It can reject fusion in favor of an existing product or a minimal fresh build. It is a usable prototype with tested local helpers; general agent effectiveness is not qualified.

## Invoke without installing

Ask your agent:

> Read `<this-directory>/SKILL.md` and use Frankenmine to design a new [tool] from [donor URLs or local roots]. Inspect sources without executing donors. Write the dossier to [new output directory]. Look for unexpected lessons beyond each donor's stated purpose. Compare the best existing solution and a minimal fresh build.

Supply requirements, host/runtime, redistribution intent, source access and budget if known. A new-product brief can start discovery without a fixed donor list. To continue an existing multi-donor synthesis, supply the prior build/manifest and desired next outcome; read [continuation](references/continue-synthesis.md). Ordinary transfers into an established recipient use adopt-adapt; recovery of one opaque product uses authorized REA. Reading SKILL.md explicitly is sufficient for a manual invocation. When installed at `$CODEX_HOME/skills/frankenmine` (normally `~/.codex/skills/frankenmine`), invoke `$frankenmine` on your next turn. Automatic discovery remains enabled; other hosts need their own installation.

## Local helper

Requires Python 3.10+ and standard library only. Run from this directory in PowerShell (use `Set-Location -LiteralPath '<absolute package path>'` when paths contain `&`):

```powershell
python scripts/frankenmine.py init ../my-new-run/run.json
python scripts/frankenmine.py init ../continuation/run.json --decisions ../prior-product/provenance/decisions.json
python scripts/frankenmine.py inspect-python ../my-new-run/donor-snapshot --revision PINNED-REVISION --output ../my-new-run/python-graph.json
python scripts/frankenmine.py check ../my-new-run/run.json
python scripts/frankenmine.py report ../my-new-run/run.json --output ../my-new-run/DOSSIER.md
python tests/run_tests.py --output ../my-new-validation
```

Choose unused output names. Init/inventory/report refuse replacement; edit your owned run record with ordinary file tools and recheck to resume. Initial skeletons intentionally fail readiness. Check/report exit **0** for structurally design-ready records; **2** for blocked/invalid records. Report writes a dossier for a valid incomplete envelope even when returning 2. Invalid JSON/schema envelopes return errors without a misleading report. Inventory returns a static graph and visible omissions; zero nodes is not qualification.

`init --decisions` accepts a local `{ "decisions": [{ "id": "D01", "source_url": "https://example.com/source", "catalogue_id": "optional-label" }] }` manifest, including the existing westack provenance shape. Every unique decision becomes a queued donor in the unchanged run schema, preserving optional catalogue labels only as untrusted scope notes. Languages stay empty and inspection/rights/review are not fabricated. Literal full GitHub blob/tree commits are parsed without retrieval; other sources remain `unpinned` with a blind spot. Malformed/ambiguous input, duplicate IDs, missing URLs and output replacement are rejected. Absolute HTTP(S) source URLs are supported; no URL is fetched and the input manifest is unchanged.

For bounded work, a lightweight narrative dossier with explicit evidence and deferrals is sufficient; a custom record is not package-schema validation. Use `schemas/run.schema.json` and [contracts](references/contracts.md) when machine checking is useful or requested. Copy bounded lawful source evidence into the run root, with portable relative paths, revision/line range and SHA-256. Evidence links/escapes are rejected. Commands recorded in a run are data: the helper never executes them. It does not contact network services, create credentials, install anything, or change host settings.

## Examples and tests

[Authored synthetic case](examples/synthetic/README.md) demonstrates game-checkpoint identity and JavaScript exact-decimal ideas in a new Python ReplayTotal slice. It includes all 13 semantic dimensions, one state owner, rights/provenance, alternatives and recovery contracts. Its frozen oracle is independent of donor test suites, but authored by the builder: no independent reviewer or multi-host agent success is claimed.

`examples/synthetic/run.json` is a **design** fixture with tests not-run. Tests generate an **implementation** dossier with executed receipts and controls, while keeping independent review and its unresolved queue blocked. `examples/no-fusion/run.json` shows a coherent minimal-fresh decision; successful fusion is not a quota. The bundled westack example remains [planning only](examples/westack-planning.md); the generic continuation workflow can also support an actual separately authorized synthesis. Registering its decisions does not qualify its donors or whole catalogue.

The development suite validates CLI flows and tampered/omitted rights, provenance, revisions, ownership, interactions, semantic deltas, oracle bytes, zero-case runs, receipt honesty, malformed JSON and unsafe paths. Continuation regressions cover complete queued registration, pin boundaries, malformed/ambiguous manifests, duplicates, inert metadata, invalid Unicode and exclusive output. It also runs the authored product oracle and ablates both material contributions. No third-party donor code is executed. All test inputs/outputs remain under the caller's new results directory for inspection.

## Limits and release state

The Python AST adapter inventories syntax-level imports/calls only; it neither resolves complete closure nor qualifies runtime seams. The worked ReplayTotal slice handles integer-string amounts in memory; fractional currency parsing and durable file persistence are outside that example's contract. Other language frontends, automatic source transplantation, translation, FFI/RPC/WASM generation and universal compatibility are unavailable. Manual contracts cover those decisions. Helpers reject ordinary evidence links and package junctions, but are not a sandbox for a concurrently hostile filesystem.

A matching hash proves bytes, not truth. Records cannot grant authority or prove their own independent review. No trigger precision/recall, general benefit, model cost improvement, multi-host agent behavior or representative cross-language release claim has been established. [Live-agent protocol](evals/LIVE_AGENT_PROTOCOL.md) and prompts are supplied with status **not-run**.

This portable distribution retains the runnable helpers, authored fixtures and qualification protocol. Machine-specific audit logs and private build transcripts are excluded; run the tests to produce evidence for your own checkout. Full agent/host qualification remains unrun.

Research inputs are parent-provided and hash-verified, rather than locally materialized from Library. [Research lineage](references/research.md) distinguishes previous source inspection from this build's checks. No external donor tool was installed or rerun.
