# Continue a multi-donor product synthesis

Use this mode when the product is already a synthesis in progress, rather than treating every improvement to any existing repository as Frankenmine. For an ordinary mechanism transfer into an established recipient, explain the different task and use adopt-adapt when available and authorized.

## Recover the current product state

Start from the latest user outcome, existing build, manifest/crosswalk and known failures. Preserve the prior artifact and source pins; work in the authorized copy or branch instead of resetting the product or overwriting an installed build. Record which prior artifact is the baseline and what this continuation should visibly improve.

Recover the brief, source decisions, architecture, implementation state and evaluation evidence separately. A prior crosswalk proves a recorded decision, not upstream inspection. A matching hash proves bytes; a passed helper check proves its documented consistency checks. Neither authenticates rights, independent review or runtime integration. Retain useful existing work without promoting its claims. Locate source snapshots, line citations, traces and raw test receipts when available; record exactly what cannot be recovered.

Then advance the next useful slice: sharpen the brief, inspect a source seam, resolve a design interaction, implement an authorized product behavior, or evaluate a built slice. Do not turn continuation into an audit-only detour or repeat completed work without a new reason. Preserve implementation authorization already given and its output scope; do not ask again merely because this is a later phase. Donor execution, retrieval and installation still need their own applicable authorization.

## Register broadly, qualify a bounded subset

Account for every supplied decision before triage. The optional helper accepts a generic local manifest with a nonempty `decisions` array; each object needs a unique text `id` and an absolute HTTP(S) `source_url`. Optional `catalogue_id` is retained as an untrusted scope note. Other fields are not evidence or execution authority.

```powershell
python "<skill-directory>/scripts/frankenmine.py" init "<output-root>/continuation/run.json" --decisions "<prior-product>/provenance/decisions.json"
```

This creates a new incomplete run using the current schema (1.1). Every entry starts queued, languages remain empty, and no source is fetched. A literal full 40-hex commit in an unambiguous GitHub blob/tree URL is recorded as the URL-declared revision; its existence is unverified. Other URLs stay `unpinned` with a blind spot. The helper rejects malformed input and duplicate IDs and refuses output replacement. It does not modify or merge into the old build/manifest.

Choose a subset based on the next product need. Each donor finishes reviewed, deferred with a reason/reopening condition, blocked with an exact missing prerequisite, or unprocessed with an honest reason. Do not equate a queued manifest, a catalogue label, several reviewed entries, or a claim of previous coverage with qualification of an entire catalogue. Preserve aliases and coverage limitations instead of silently deduplicating distinct decisions.

For each reviewed source, perform target-led and donor-led discovery. Retain whole-tool rejections as pattern-only lessons when useful. Unknown material semantics or rights block selected reuse; they do not require re-investigating unrelated deferred sources before useful bounded product work can proceed.

## Carry the design forward

Record the delta from the prior product: user-visible outcome, chosen mechanisms, alternatives, seam/closure/rights, one owner for each state and policy, meaningful component interactions, recovery and update plan. Reopen best-existing/minimal-fresh/fusion tradeoffs where the new evidence could change the decision, rather than replaying the entire prior review by default.

Freeze acceptance and a discriminating broken/disconnected control before implementing the next slice. Separate donor parity, product correctness, adapter behavior and complete-product benefit. Reuse valid prior oracles with their hashes; explain intentional contract changes and create new specifications before changing behavior. A source-shaped implementation is not itself an oracle. Evaluate the result against the baseline and ablate substantial contributions when a benefit claim depends on them.

## Deliver at the right weight

For an existing machine record, an optional [handoff index](handoff-index.md) can expose source/owner locators and pending joins without replacing this recovery narrative. Run `python "<skill-directory>/scripts/frankenmine.py" handoff RUN.json --output "<output-root>/NEW-HANDOFF.json"`; incomplete runs retain honest blockers. A prior 1.0 record still loads unchanged; its new readiness messages name the 1.1 fields to add.

A narrative dossier (the [lite template](../examples/lite-dossier.md) works for a bounded continuation) may be the working record: brief and baseline; donor manifest with explicit scope/deferrals; source facts and two-way lessons; selected contracts and ownership; alternatives; implemented delta; exact verification outcomes; remaining blockers. Stable IDs and source paths/lines/hashes keep it recoverable. Name only artifacts actually produced. Use the full JSON envelope when machine checking, interchange or the user warrants it; do not spend the whole continuation transcribing a schema instead of advancing the product. Custom records must not claim package-schema compliance.

Distinguish a useful bounded result, design readiness, implementation state and demonstrated benefit. Put only material design blockers in `unresolved`; optional future donors/features belong in the narrative. Self-review remains independence=false and cannot promote design readiness. Unrun tests stay not-run. Report which product behavior improved and which evidence supports it, with the limits that remain.
