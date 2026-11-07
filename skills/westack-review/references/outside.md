# Outside reviewers

Shared by all three modes; read with the [review rules](rules.md), which hold the finding contract and the validation pass.

A delegated or vendor reviewer's run is complete only with one completion event, a finding count equal to the records received, a clean exit and no truncation; heartbeats show liveness only, and "skipped, zero findings" is not-run. Its comments are candidates, never findings or a quality signal: validate each against the cited lines and their callers, keep its label verbatim in `vendor_severity` beside `vendor` (missing is unknown, never low), set P0 to P3 only after validation, and report each run's candidates, confirmed and dropped counts.
