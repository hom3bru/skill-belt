# The claim ledger

Every statement the answer rests on is a row in the log's `claims`: the sentence as the report will say it, its strength, and its citations (source, location, basis, excerpt). Write a row only from a source you have read or a run you made.

## Strength in the core's words

Give each row one strength from the core vocabulary (`evidence-vocabulary.md`): claimed, present, wired, tested or observed. There is no second scale: no "high confidence", no letter grades, no tiers of your own. In research the words map like this:

| What backs the row | Strength |
| --- | --- |
| a snippet, listing, abstract or summary; a mirror or aggregator copy alone; one secondary source; documentation alone for how software behaves; a source's own benchmark you did not rerun | claimed |
| a text read at its pinned version and saved with its hash, for what that text says (a standard's rule, a paper's reported result, the docs' stated contract); the code read at the pinned tag, for behaviour; or two independent sources that agree | present |
| the behaviour traced through the source code from an entry point at the pinned tag | wired |
| a probe you ran against the pinned version, its receipt kept (basis `ran`) | tested; observed only for the real product path, as the vocabulary says |

Word each row as what its evidence shows (core `inspect.md` keeps maintainer documentation apart from inspected code): "the 1.4 docs say prepared statements are not supported in transaction mode" is present once the page is read and saved; "1.4 rejects them" stays claimed until the code at the tag is read or a probe runs. Say why a row moved down. A row is contested when sources disagree, the user doubts it, or the decision hinges on it: name the check run on it (the primary read, a probe, or a fresh-context review under core `critique.md`). A level belongs to one claim at one version: a new release puts the row back to claimed until it is read again.

## Read before citing

- Cite only what came back in this search's saved results, was given by the user, or was linked from a source you read. Never cite an identifier from memory: a recalled arXiv id or DOI is a lead to search for, like any other.
- Match duplicates by index id, then DOI or arXiv id, then URL, then exact title; keep one entry per work.
- A snippet, a listing or an abstract does not verify a finding. Read the cited location in the saved original.
- A paper's linked repository may be a framework the paper builds on rather than its own code. Confirm the link (the paper names the repository, the repository names the paper, the dates fit) before treating it as the implementation.

## Identifiers in two indexes

For each cited DOI or arXiv id, look it up in two independent indexes (the issuing service and a general scholarly index, for instance). The title, year and first author must match the citation. Record which record you matched, since a preprint and its published version can differ. A mismatch is flagged and either resolved or the citation is dropped and listed as removed; it is never kept silently. A lookup that only shows the id resolves is not a match.

## Gaps by origin

A gap is something the sources do not settle. Label each by origin:

- **stated:** a source says it (a limitations section, an open issue); cite its location;
- **inferred:** a pattern across two or more sources; name them;
- **speculative:** your own reading, with no source.

Never present an inferred or speculative gap as stated.

## Fact-check mode

For "is it true that", or a figure someone quotes, trace the claim through five stages:

1. **Scope it.** Who said it, the exact wording and number, the source they cite, and the period it covers.
2. **Publication.** Find the original, not a citation of it; check its identifiers in two indexes and that it says what is attributed to it.
3. **Methods.** What was measured, against which baseline, under which conditions; does the quoted number belong to that setting, or to a best case or a different benchmark?
4. **Data.** Are the data or tables available, and does the number appear there?
5. **Standing.** Later replications, critiques, errata and retractions.

Each stage ends passed, failed, inconclusive or not-run, in the core's words; a lookup that failed is not-run with its reason, never a verdict. The trace ends in one outcome:

- **supported**, with the row's strength;
- **overstated**: the source supports less, so restate what it supports;
- **not in the source**: the citation attributes something the source does not say;
- **retracted or disputed**, with the notice;
- **not traced**: inconclusive, never "false".

The fact check is a ledger row like any other: the outcome is its sentence, the stages are its citations.
