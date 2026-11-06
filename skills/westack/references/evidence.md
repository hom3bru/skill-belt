# Evidence and verification (C2)

Every westack skill reports evidence the same way. The terms are in the [evidence vocabulary](evidence-vocabulary.md); the detail is in [verify](verify.md), [review](review.md) and [finish](finish.md).

## Rules

- A claim needs a receipt: the exact command or read, tool versions, the revision and content fingerprint, counts (collected, executed, passed, failed, skipped), the exit code, and the raw output saved with its SHA-256 (long output is spilled to that file: [context](context.md)). No marker, checkbox, confidence score or self-report counts as done.
- A user accepting or merging a change is not evidence it was right. Record the delta between what was proposed and what was kept, for retros and new eval cases.
- Zero executed tests is not a pass, whatever the exit code. Skipped is not passed. A crash, timeout or unparseable output is blocked, not failed, unless the same command finished on the baseline ([verify](verify.md)).
- A run with an oracle-update flag is an update run: say so, with the oracle files created, updated and deleted. Its pass never supports a parity or regression claim; cite a rerun of the same selection without the flag. A selection narrows an audit too: an unused-oracle finding holds only for tests that ran; nothing is deleted on that evidence.
- A check that found no target, got malformed input or could not apply a rule is blocked or inconclusive, never passed or clean. A lookup that returns nothing is an error, and a protection rule that matches nothing protects nothing. An empty result, NaN, zero denominator or several matching series is no data, never zero or the first row; series of different identity are not compared; a mostly empty roll-up is inconclusive.
- Whenever a list, search, transcript, packet or output is trimmed or capped, record the cap, what was cut and why, and keep the tail. A result reached at a cap is inconclusive, never clean, and a shortened list must not look complete.
- A read-back after an apply names the revision it describes; a mismatch is not yet observed, neither ready nor failed, and the wait ends inconclusive at a deadline set before the apply.
- Results are passed, failed, skipped, blocked, inconclusive (it ran but cannot settle the claim; say what would) or not-run. Claim strength never rounds up: claimed, present, wired, tested, observed. A numeric gate has a pass bound and a fail bound; between them is inconclusive (one bound: say so).
- Give each blocked, inconclusive or skipped result a fixed reason code (missing prerequisite, denied, timeout, crash, unparseable, no oracle, flaky, cap reached, none given) with the observed value and limit; a skip with no reason is outstanding.
- Broken-copy control: when a check claims to detect a mechanism, run the same check, selecting the same cases, against a deliberately broken copy (a different artifact). It must fail there, and you keep the failing output.
- A detection claim needs at least two distinct broken copies (different mutations, each realistic), each failing on an assertion rather than on an import or setup error: one copy can be caught by accident. `westack-tdd` judges them (`scripts/controls.py`).

## Baseline and new failures

Before changing code, save the raw output of the relevant suite (the whole suite when practical); after the change, save the same command's output. Then compare by test name:

```text
python "<core>/scripts/checks.py" diff before.txt after.txt
```

`checks.py` parses saved unittest, pytest, TAP (node:test) and jest or vitest JSON output and runs nothing; [verify](verify.md) gives its exit codes and `--rename`. It lists new failures, pre-existing failures (failure text must match too), fixed tests, and tests that went missing or became skipped. Report new and pre-existing failures as two lists, by name.

## Cheap critics before "done"

- An empty diff, or one that changes no source, is not a fix.
- Every changed path is intended, scratch (remove it or say why) or a modified existing test (that needs a decision).
- A criterion reserved for human verification stays "awaiting human verification" until a person checks it. Agent receipts cannot satisfy it.

## Two modes

- **Inline** (default): a receipts table in the reply and no files.

  | Check | Command | Exit | Collected / executed / passed / failed / skipped | Status |
  | --- | --- | --- | --- | --- |

- **Recorded** (persistent or cross-session work): the [task record](../contracts/README.md) and its validator; see [handoff](handoff.md).

Provenance: C2 in provenance/facility-donors.json.
