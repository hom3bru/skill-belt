# Prose rules (WD-4, WD-6, WD-7, WD-8, WD-9)

The rules a pattern can check live in [rules.json](rules.json), each with its level per document type ([doctypes](doctypes.md)). The rest are judgment rules: the report lists them as not checked, never as passed.

## Evidence-bound prose (WD-4)

- A causal or proof verb (caused, drove, proved, led to) stays only when the source supports it; otherwise use the weaker relation the source does support (followed, coincided with) or mark a gap.
- A comparative names its baseline (faster than what, by how much); a universal names the cases it covers. Without them, weaken the sentence or mark a gap. Never invent a baseline to make the sentence pass.
- A summary adds no claim, recommendation or caveat, and keeps dissent and open questions at the weight they had. `preserve` catches added numbers and names; an added recommendation without either is yours to catch.
- `lint` reports `causal-verb`, `comparative-no-baseline` and `performed-hedge` as candidates only: they never change the exit code, and each one is a question for the reader, not a verdict.

## Hedges

Two kinds look alike and must be told apart:

- **Evidential hedges carry the claim.** A modal or qualifier that marks uncertainty, a condition or a limit stays, even under a blunt house voice: "the upload may fail when the disk is full", "we have not measured cold starts", "in our two runs". Removing one turns an honest result into an overclaim, the failure core `finish.md` hunts as hedges that hardened into facts.
- **Performed hedges carry nothing.** Phrases such as `it is important to note`, `could potentially` or `arguably` add length and no uncertainty. Cut them. Stacked qualifiers keep one.

Core `craft.md` lists performed hedges as prose slop; this split is how to apply that rule without deleting evidence.

## What no person types (WD-6)

One sighting fails in every document type and mode: leaked citation tokens, an assistant's tracking parameter on a link, lines addressed to the person who asked for the text, zero-width, soft-hyphen and private-use characters (emoji joiners and a leading byte-order mark are allowed), and template leftovers such as `[Your Name]`, `{{ customer_name }}`, `{date}`, a date of `2026-XX-XX` or a comment that asks for text (`<!-- Describe the context here -->`). A field set such as `{a, b}` is not a slot.

A gap marker is different: it is deliberate, says what is missing (`[churn figure needed]`) and is allowed in a draft. `lint --mode draft` lists each as open; in delivery (the default) each is also a finding, because delivered text with a gap is not finished.

## The rule contract (WD-7)

Every regex or builtin rule in `rules.json` carries at least one `must_match` example and one `must_not_match` example, in the shape core `scripts/ruletest.py` uses for guard rules. `prose.py` checks both as the file loads and refuses to run on a file where either disagrees, or where a rule has no counter-example. A rule that cannot be written that way is a judgment rule with a stated reason. A detector that was tried and dropped stays under `reverted` with the false positive that removed it, so nobody adds it again unaware.

## Self-lint (WD-8)

`prose.py selflint ROOT` lints westack's own Markdown with the same rules. For each rule it reports the naive count (no exclusions), the count kept after the exclusions and the count gated against its ceiling; for each exclusion, the hits it removed, so an exclusion that removes nothing shows zero and can be deleted. A gated count over its ceiling fails. A ceiling is 0 unless `rules.json` lists it with a dated log entry giving the reason, and every later entry may only lower it. A file that cannot be read as UTF-8 stops the run with exit 2; it never passes. This overlaps the adoption list's CM-34 (lint westack's own pages); the exclusion counts and the one-way ceilings are what it adds.

## Numeric gates (WD-9)

No rule ships as a rate. A rule that someone turns into one (more than N hits per 1,000 words fails) must be calibrated on the project's own existing documents first: the gate records its threshold, a corpus manifest and that manifest's SHA-256, the number of documents (at least 100) and the registers they cover (at least two). The helper hashes the manifest and every listed file before any run; a changed file stops the run. No rate is reported from fewer documents or from one register.

## Not rules

These were considered and left out (the provenance file has the sources):

- vocabulary ban lists: taste that dates, inherited rather than measured;
- uniform sentence length, type-token ratio and burstiness: the donor that measured them found them no better than chance;
- dash bans, unless the repository's own style has one;
- adding a reaction or opinion where the writer "would" have one: that is invented stance;
- omitting unfavourable results to make a document persuasive: a limit is stated once, plainly ([preserve](preserve.md#limits-stated-once)).

Agreement between the donor skills is weak evidence: three of them share a lineage and copied each other's lists.

## Other writing tools

An installed writing skill does not take over a westack-docs task. The one found on this machine rewrites files in place and strips every hedge, which breaks rules 1 and 3; no defer entry exists for it, and the provenance file records why.
