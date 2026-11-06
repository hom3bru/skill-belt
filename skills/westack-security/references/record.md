# The findings record and the report

`scripts/secaudit.py` reads one JSON record and generates the report from it.

## The record

```json
{"format": "westack-security-findings-1", "mode": "audit",
 "scope": {"target": "...", "receipt": "revision or scope digest", "paths": ["."],
           "coverage": {"status": "complete", "receipt": "diffscope.py coverage: exit 0, ..."},
           "excluded": [{"what": "vendor/", "reason": "..."}]},
 "records": [{"id": "F1", "state": "confirmed", "claim": "one sentence", "rule": "...", "anchor": "...", "instance": "..."}]}
```

- `mode` is audit, intake, host, triage or fix. `paths` is `["."]` for the whole tree; anything narrower makes the audit partial.
- `coverage.status` is complete, partial or not-run; complete names its receipt. Without it the coverage is not-run.
- `excluded` lists what was considered and left out, each with its reason; excluded paths stay counted as unchecked.
- Every record has an `id`, a `state`, a one-sentence `claim` and an identity: `rule`, `anchor` (no line number) and `instance` ([assess](assess.md)). Identity, not line position, matches a finding across runs.

| State | Also needs |
| --- | --- |
| `confirmed` | `surface`, `reach`, the tuple, `impact`, `demonstrated_impact`, `likelihood`, `severity` (and `critical_evidence` for critical), `snippets`; optional `confidence`, `scanner_severity`, `harness_effect` |
| `hardening` | nothing more; no severity |
| `needs-review` | `missing_fact` |
| `not-assessed` | `settle` (the identity may be left out) |
| `not-actionable` | `positive_evidence` |
| `not-applicable` | the `surface` or `reach` that removes it |
| `rejected` | `reason`; kept so the same unchanged claim is not raised again |
| `dismissed` | `reason` and `basis`, a snippet that must still match ([triage](triage.md)) |

A snippet is `{"role", "file", "lines": [start, end], "text"}`, with the file relative to the root.

Any record may carry `risk`, `{"level", "checks": [{"name", "level"}]}`: high, medium, low or unknown (could not assess, never low); a check may also be `error`. The label is the worst concrete level among independent checks: one that raised counts as high, all unknown stays unknown, and unknown asks, so only `needs-review` or `not-assessed` carries it (core `guards.md`).

A removal claim carries `absence`: the exact pre-change `identifiers` and each copy's `probe` and `result` ([fix](fix.md)).

## The checks

`check` refuses: a severity off the table, a critical without named evidence, an impact above the demonstrated one, a severity on any state but confirmed; a missing tuple field, a non-shipped surface or a self-only or privileged-only reach on a confirmed finding; a snippet that differs from its lines or leaves the root; a repeated identity or an anchor with a line number; a bare or lapsed dismissal; prompt injection with no harness effect; a risk label its checks do not give, or unknown on a record that does not ask; an unprobed copy, a probe naming no identifier, a surviving copy or an unrotated secret; and each state without its own field.

## The report is generated

Generate the report with `secaudit.py report`; never write, repair or edit it by hand. To change it, change the record and regenerate: the output file is rewritten whole, and its first line names the record's SHA-256. The report computes the audit status: partial while coverage is not complete, the run is path-scoped, anything is not assessed or needs review, or snippets were not checked. A run that stopped early therefore never reads as clean, and a report with no confirmed findings says it does not mean the system is secure.

## Publishing findings

Only under a tracker-write or publish grant (core `authority.md`):

- Put the finding's id and identity in every item you create. Search open and closed items before creating one. Settle a write that timed out by reading the tracker, never by sending it again.
- Vulnerability detail goes to a private destination by default. A public one needs a warning to the user, their approval of the exact text, and no exploit detail.
