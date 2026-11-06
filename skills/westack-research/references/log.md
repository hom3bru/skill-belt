# The research log

One JSON file per question, format `westack-research-log-1`, beside the saved sources and result sets it names. It is the run file: update it after every stage (frame, each round, reading, the ledger, the sweep) so that an interrupted run still says what it did. Counts come from the saved files, never from memory.

The log is an artefact, not a second task record. In a recorded task, cite it with a receipt of type `source` whose `artifact_sha256` is the log's hash, and an observation that names that receipt; `research_log.py check --record` checks both through the core's `record.py` and contract.

## Shape

```json
{
  "format": "westack-research-log-1",
  "question": "Can the orders API use prepared statements through the pooler in transaction mode?",
  "decision": "keep or drop prepared statements before the pooler migration",
  "depth": "depth-first", "follow_up_cap": 1, "status": "complete",
  "pacing": {"export.arxiv.org": 3},
  "searches": [{"id": "Q1", "round": 0, "query": "verbatim text", "where": "web search",
                "window": "any", "ranking": "relevance", "results": "results/Q1.json",
                "calls": [{"at": "2026-10-30T10:00:00Z", "url": "...", "window": "any",
                           "ranking": "relevance", "status": "ok", "attempt": 1}]}],
  "fetches": [{"at": "...", "url": "...", "status": "failed", "attempt": 1, "source": "S3"}],
  "sources": [{"id": "S1", "title": "...", "url": "...", "kind": "primary", "version": "1.6.0",
               "retrieved": "2026-10-30", "saved": "sources/S1.md", "sha256": "...",
               "found_by": {"search": "Q1"}, "status": "accepted"}],
  "claims": [{"id": "C1", "text": "the sentence the report says", "strength": "present",
              "cites": [{"source": "S1", "location": "line 3", "basis": "read", "excerpt": "..."}]}],
  "gaps": [{"id": "G1", "text": "...", "origin": "stated", "source": "S3", "location": "section 6"}],
  "searched_for": [{"text": "No release note states a connection limit.", "queries": ["Q3"]}],
  "delegates": [{"id": "w1", "found": ["S2"], "nothing_found": [{"what": "...", "queries": ["Q3"]}],
                 "not_searched": ["vendor forums"]}],
  "removed": [{"text": "40% faster", "why": "only a copy of the notes says it"}],
  "not_done": [{"check": "ran the pooler locally", "why": "no environment granted"}],
  "spend": {"limit_usd": 1.0, "entries": [{"what": "pilot", "usd": 0.05, "pilot": true}]}
}
```

| Field | Holds |
| --- | --- |
| `depth`, `follow_up_cap` | the class (straightforward, depth-first, breadth-first) and the cap of 0, 1 or 2, set before searching ([frame](frame.md)) |
| `status`, `reason` | complete, partial or blocked; the reason is required unless complete |
| `searches[]` | each query verbatim, its round (0 first, then the follow-ups, each with its `gap`), where it ran, one `window` and `ranking`, the saved `results` (a JSON list, or `{"results": [...]}`) and every call |
| `fetches[]` | source fetches, for pacing and failures; a failed one may add `http` (the status) and `result` (what the row concluded) |
| `sources[]` | `kind` primary, secondary, mirror or aggregator; a mirror adds `original_url`; a paper adds `doi` or `arxiv`, `year`, `first_author` and `index_check` (`records` from two indexes, inline or as saved files, and `matched`); `found_by` is `{"search": id}`, `{"given": "..."}` or `{"link": source id}`; a binary original adds a `text` copy; a rejected source gives its `reason`; a repository whose licence the log names adds `licence`: `name`, `status` (verified or unverified), the saved licence `file` and the `host` field as read, each null when there is none; a source that bundles, wraps, ports or cites another tool lists that tool's row id in `includes` |
| `claims[]` | `basis` read, ran (with a `receipt`), snippet, listing or summary; `contested` with its `check` |
| `searched_for[]`, `delegates[]` | every claim to have searched, with its query ids; each delegate's three lists |
| `removed[]`, `not_done[]` | the sweep's removals; checks not done, each with why |

## The checker

```text
python "<this skill>/scripts/research_log.py" check log.json [--record task.NNNN.json] [--core DIR]
```

| Check | Findings |
| --- | --- |
| shape | `field-missing`, `bad-value`, `duplicate-id`, `empty-log` (complete with no claims) |
| rounds | `round-over-cap`, `round-no-gap`, `round-many-gaps`, `repeated-query` |
| window | `window-changed`, `no-calls` |
| results | `results-unsaved`, `recalled`, `duplicate-source` |
| reading | `snippet-only`, `copy-only`, `single-secondary`, `no-run-receipt` |
| strength | `unknown-strength`, `contested-unchecked` |
| identifiers | `identifier-unchecked`, `index-not-independent`, `index-incomplete`, `index-mismatch`, `index-unmatched` |
| queries | `query-floor`, `search-claim-unlogged` |
| pacing | `too-fast`, `failure-unrecorded`, `bad-time`, `404-read-as-absent` (a GitHub fetch, call or rejected source with a 404 and wording such as "does not exist"; write "not found or not visible to this account") |
| delegates | `delegate-lists`, `found-unknown`, `lead-dropped` |
| gaps | `bad-origin`, `stated-unlocated`, `inferred-unsourced` |
| trace | `unknown-source`, `no-excerpt`, `excerpt-not-in-source`, `excerpt-unverifiable`, `number-untraced`, `uncited-source` |
| sources | `rejected-without-reason`, `unpinned`, `mirror-unrecorded`, `not-saved`, `saved-changed`, `status-unreasoned` |
| licence | `licence-unverified` (verified with no saved licence file), `licence-mismatch` (the host's field is null or names another licence), `bad-value`; an unverified licence is a note |
| artifacts | `artifact-merged` (a part with no row of its own, or the row itself), `artifact-unpinned` (an accepted part, or its source, without its own pin or licence entry), `bad-value` |
| spend | `over-budget`, `no-pilot` |
| record | `record-shape`, `record-no-receipt`, `record-uncited` |

Each check reports passed, failed, not-applicable (nothing of that kind in the log) or not-run. The strength words come from the core vocabulary's Claim strength table, so without the core the strength and reading checks are not-run, as is the record check when `--record` is given, and the exit is 2. Exit 0 clean, 1 findings, 2 unreadable, another format or a check not run, 64 usage.

## What stays judgment

Every report lists what the checker cannot see, and the report you write keeps them as your own checks:

- a paraphrased query: only repeats after case, punctuation and word order are set aside are caught;
- whether a source labelled primary, mirror or aggregator really is one;
- whether a paper's linked repository is its code or a framework it builds on;
- relevance: whether an excerpt answers the question at all;
- whether a stated gap is really stated where the log says;
- whether a GitHub 404 hid a private resource or a missing one: only the wording is caught;
- whether a saved licence file is the repository's own and grants what its name says;
- whether a source bundles, wraps, ports or cites a tool its `includes` leave out, or a claim credits one artifact's parts to another;
- whether a row's strength fits its subject: read documentation supports what the docs say, not how the software behaves ([ledger](ledger.md));
- whether the report's prose says only what the ledger supports (sweep it: [answer](answer.md)).
