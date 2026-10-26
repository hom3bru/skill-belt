# Verify

Define a falsifiable acceptance condition, then run checks that exercise the changed path. Capture exact command/read operation, environment/tool versions, output file and hash, artifact/revision/patch identity, count, exit and limitations in the Evidence Record.

Separate source audit, unit, contract, integration, end-to-end and host evidence. A source reading or valid schema cannot become runtime-tested. A successful shell exit with zero executed tests is incomplete. Skipped tests are not passes. Mark unavailable tests not-run or blocked; report flaky/retried results together rather than replacing the failure.

Where the check claims to detect a mechanism, run a frozen broken/removed-path control and show that it is rejected. E04's broken arithmetic and E06's constant verifier are examples. Store the raw failing output. Do not let current candidate writes change an independent evaluator's oracle.

A negative control must address the same acceptance claim and current revision/patch/scope, with runtime evidence when the claim requires it. An unexpected process exit after all cases passed does not show that the broken mechanism was detected. A stale failure from another task is not a current control.

Before reusing receipts, compare current revision, patch, scope and observed artifact hashes; re-run authorized checks after material change. Check that the raw output exists and matches its digest. These checks detect stale/missing/contradictory records, not forged evidence.

Validate optional records with [validate.py](../scripts/validate.py). Its output always says consistency-only. It does not execute the recorded command, parse arbitrary test logs into truth or qualify the host. Assertions supplied by the builder and confidence scores are not independent validation.

Evaluate model behavior separately using [evaluation protocol](../tests/EVALUATION.md). Deterministic fixture checks and bounded developer usage trials provide different evidence. Do not infer multi-host effectiveness or benchmark superiority from either.

## Applications and harnesses

When the task needs a running UI, service or CLI harness, identify the exact instance/build and who owns its lifetime. Establish that it is usable before interaction. After a failed interaction, recheck the instance rather than reusing an earlier readiness assumption. Exercise the user's path and capture the observable result, not only a successful launch or health check.

Keep proof outside disposable instance state. Clean up only resources owned by this task under the existing authorization, then confirm that the receipt's files still exist and retain their hashes. If evidence was destroyed during cleanup, leave verification incomplete and recover or rerun the authorized check. These are extensions of the existing evidence contract; no lifecycle daemon or sandbox is supplied.

Control-plane success must be recorded for its actual claim: a request was acknowledged, an observer returned, or validation succeeded. Inspect payload fields such as executed, state and errors before claiming product work or completion. An exit of zero alone cannot establish those outcomes.

