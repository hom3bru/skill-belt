# The answer

## Shape

1. **The answer first,** tied to the decision, in one or two sentences, with the conditions under which it holds (the version, the configuration, the date of the pricing page). Then its state: answered, partial (what is missing) or blocked (why), in the core's end states (`durable.md`, `finish.md`).
2. **The ledger:** each row's sentence, strength, and source with location. A reader can find every excerpt in the saved originals.
3. **Sources:** accepted (URL, version or date, retrieval date, kind), rejected (each with its reason) and not reached (blocked, paywalled, behind a login), each named.
4. **Checks not done,** each with why: the probe that was not run, the index that did not answer, the source that was not read in full.
5. **Removed by the sweep,** each with why.
6. **Gaps,** each with its origin.
7. **The receipt:** the log's path and SHA-256 and the `research_log.py` result, in the Minimum Core's receipts table.

A one-fact answer keeps this shape in miniature: the answer line, one row, one source with its version and date.

## The sweep before saving

Before the answer is saved or sent, read the text you are about to deliver, not the notes behind it (core `finish.md`). Pull out every number, percentage, benchmark or dataset name, figure, dataset size and superiority claim ("faster", "the best", "outperforms"). Each must trace to the exact wording of a cited source, a note, a file or a command's output that supports it; otherwise remove it and list it under "removed by the sweep". Matching on topic is not tracing: a source about latency does not support "40% lower latency" unless it says 40%. `research_log.py` checks every number in the ledger's rows against their excerpts and sources; the prose around the rows is yours to sweep, and a claim the prose adds becomes a row or goes.

## Partial and blocked

A run whose tools failed still writes its final answer, labelled partial or blocked, with its provenance: the sources consulted, accepted and rejected, and the checks not done. Write no placeholder text before its stage, and never call a run complete with a check missing. The log's `status` and `reason` say the same as the answer's first line. A blocked answer names the action, the target, the reason and what was finished (core `finish.md`).

## Engineering summaries

When the deliverable summarises a source (a changelog, a standard's section, a paper), list its salient points in the source's own order, each with its location and a short excerpt. Add nothing the source does not say; put any inference in the ledger as a row with its strength. A summary is not redaction: remove secrets and private data before a summary leaves the session (core `guards.md`).

## Afterwards

- Save to memory only when the user asks (core `memory.md`); an entry built from web pages is agent-written, whatever its sources.
- A research library the repository keeps is updated only when its instructions say so and the user agrees.
- Evaluating outside work for adoption into one of the user's projects is not this answer: it is the core defer map's `research-adopt-adapt` entry.
