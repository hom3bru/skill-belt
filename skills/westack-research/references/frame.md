# Frame the question

Frame before the first search, and write the frame into the research log ([log](log.md)): the question, the decision, the depth class and the follow-up cap.

## The decision

Say in one line what the research serves: the decision, and who makes it. "Which pooler" is a question; "keep or drop prepared statements before the pooler migration" is the decision, and it tells you which version, configuration and trade-off matter. Restate the question exactly: the library and the version the project pins, the standard and its section, the claim and who made it. A question with no decision behind it is still answered; say what the answer would change.

## Depth class and size

Classify the question before searching:

- **Straightforward:** one fact with one place it should live (a default, a flag, how one call behaves at one version).
- **Depth-first:** one question that needs several angles (whether a claim holds, why two vendors' figures disagree).
- **Breadth-first:** independent sub-questions (four libraries against five criteria).

| Class | Query floor | Follow-up cap | Workers |
| --- | --- | --- | --- |
| straightforward | one distinct query, or none when the user supplied the page | 0 (1 with a reason) | none |
| depth-first | three distinct queries | 1 or 2 | none unless the user asked |
| breadth-first | three distinct queries | 1 or 2 | one per sub-question, only if the user asked |

**The proportionality rule.** The three-query floor exists so that "I searched" means something: it applies where the answer depends on coverage, which is depth-first and breadth-first work. A straightforward lookup's evidence is the page that answers it, so its floor is one logged query, or none when the user gave the page or it was linked from one. Every query is still logged verbatim, whatever the class. A straightforward question that turns out contested (sources disagree, the answer depends on a setting) is reclassed in the log, with the reason, before any more searching. Never add queries, rounds or rows to reach a number: ceremony is not evidence.

**Follow-up rounds.** Set the cap (0, 1 or 2) before the first search; round 0 is the first pass. Each follow-up round targets one named gap that the earlier rounds left, and never re-asks an earlier query in other words. Stop as soon as coverage suffices, below the cap if it can; reaching the cap with a gap still open ends partial, never with an extra round.

## What is already known

Before any outside search:

- **The host's memory** (core `memory.md`): search it, cite the entries you use, and in a task record list them in a `memory-read` observation. A remembered fact with a dated source is reused with its date; one without a source is a lead to check, never a citation.
- **Research libraries and earlier reviews** that the repository's instruction files name (core `context.md`): read them first and build on what they already assessed.
- **An earlier research log** on the same question: reuse its saved originals when their versions still match the pin, and search again only for what changed.
- **The project's pins** (lockfiles, manifests, the runtime in CI): the question is about the version the project uses, not the newest one. A version you cannot find is asked about, never assumed.

## Egress

Searches and fetches leave the machine. A request to research grants reading public pages and running searches through the host's own web tools, within the host's permission settings: the destinations are the search service and the pages read, which is the egress the user asked for. It does not grant sending this repository's code, private names (internal hosts, project or customer names), credentials or personal data in a query, a URL or a form. Write queries from public terms: the library, the version, an error message with private parts removed. If the question cannot be asked without private detail, ask first, naming the destination and what it would receive (core `authority.md`, Egress). Never log in, submit a form, post or upload anything while researching.

## Workers

Workers only when the user asked for them (core `hosts/README.md`); a narrow question is searched directly. Brief each as a search worker (westack-orchestrate's brief and collect pages when installed, else core `delegation.md`): one sub-question, the window and ranking to keep, and a return of three lists (found, searched with nothing found, not searched) with every query verbatim and the hits saved, never retyped. Copy the lists into the log; each not-searched lead becomes a later round's gap or a not-done entry. Facts a worker took from snippets stay claimed until you read the source.

## Spend

When a paid search or crawl service is used:

- Tell the user the expected total before any loop. A cap on one call does not bound a loop.
- Keep a running total in the log's `spend`, from the costs the service reported, not a price list.
- Run a small pilot and read its parsed output before any bulk run: a parse error after a bulk run throws away work already paid for.
- Stop before the call that would pass the limit, and return partial with what remains.
- Once credits are exhausted, stop; never retry.

Caps and end states are core `durable.md`; reserving the checking first is westack-orchestrate's `decide.md` (Budget).
