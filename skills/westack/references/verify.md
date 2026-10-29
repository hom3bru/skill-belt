# Verify

Define a falsifiable acceptance condition, then run checks that exercise the changed path. Capture exact command/read operation, environment/tool versions, output file and hash, artifact/revision/patch identity, count, exit and limitations in the Evidence Record.

Before editing, run the repository's relevant test command (the whole suite when practical, even if the task names one file) and keep a baseline receipt that lists the failing tests by name. After the change, rerun the same command and compare failing names: report every failure by name, pre-existing ones included, and keep new failures apart from pre-existing ones. A task's scope limits what you deliver, not what you verify.

Receipts record tool versions and environment variable names (or whether each is set), never their values. Do not capture `env`, `printenv`, `set -x` or other credential-bearing output in raw output; when output may hold secrets or private data, keep a redacted excerpt unless the user agrees to storing it in full.

Results are passed, failed, inconclusive, blocked or not-run. `inconclusive` means it ran, but the result can't settle the claim (flaky outcome, missing oracle, environment limitation or ambiguous observation). Never counts as passed; record why and what would settle it. A check that ends without a structured result (missing tool, crash, timeout, unparseable output) is a tooling error: record it as blocked, neither failed nor coverage. Retry the same command at most twice. Never silently substitute another check; record any substitution and why.

Keep evidence out of the files you fingerprint: use an evidence root outside the repository, or pass it as `--root` so the fingerprint skips it. Write raw outputs into that root. `validate.py receipt` (see [build](build.md)) records a run: it snapshots the tested file to `snapshots/<sha256><suffix>`, hashes the raw output and binds the record's current patch and scope; `validate.py snapshot <file> --root <evidence-root>` makes a snapshot on its own. A snapshot keeps a red-phase receipt valid after an in-place fix. Reads and reviews (types `source`, `review`) run no process: set both exit fields to null and `executed` to the number of observations. Runtime receipts need both exit fields. Record the operation exactly as run; put where the artifact came from in coverage or limitations, not in the operation.

Separate source audit, unit, contract, integration, end-to-end and host evidence. In the shared vocabulary, source-audited reaches at most present or wired; a passing runtime receipt makes a claim tested; an e2e or host receipt on the real product path makes it observed. A source reading or valid schema cannot become runtime-tested. A successful shell exit with zero executed tests is incomplete. Skipped tests are not passes. Mark unavailable tests not-run or blocked; report flaky/retried results together rather than replacing the failure.

Where the check claims to detect a mechanism, run a frozen broken/removed-path control and show that it is rejected. For a bug fix, the red run before the fix is the control when the check itself has not changed since; otherwise rerun the check against a copy with the fix reverted. For a generated verifier, a constant-true check must fail against the broken copy. Every passing receipt behind a criterion that requires a control names its own failed control: the same claim and scope, the same evidence type and operation, the same collected count (both runs selected the same cases), and a different artifact (a different snapshot hash). Store the raw failing output. Do not let current candidate writes change an independent evaluator's oracle.

Derive expected values independently of the code under test; an expectation computed by that code always agrees with it. Choose each broken copy from realistic mutation kinds: a wrong constant or argument, the wrong branch, a missing side effect or state change, an empty or default return, missing validation. Pair the failing control with a run showing that legitimate behaviour still passes, so the failure is specific to the mechanism. Counts reported by a process the candidate code controls are self-reported; the control is what gives them meaning.

An unexpected process exit after all cases passed, a crash before collection or a different selection does not show that the broken mechanism was detected. A failure from another scope or task is not a control.

Before reusing receipts, compare current patch, scope and observed artifact hashes; re-run authorized checks after material change. A new commit with identical content leaves receipts current (the revision change is reported). A receipt may be marked `stale` only once its patch or scope differs; stale receipts keep their files. Check that the raw output exists and matches its digest. These checks detect stale/missing/contradictory records, not forged evidence.

Validate optional records with [validate.py](../scripts/validate.py) (`task --repo`, as in SKILL.md). It does not execute the recorded command, parse test logs into truth or qualify the host. Assertions supplied by the builder and confidence scores are not independent validation.

Evaluate model behavior separately using [evaluation protocol](../tests/EVALUATION.md). Deterministic fixture checks and bounded developer usage trials provide different evidence. Do not infer multi-host effectiveness or benchmark superiority from either.

## Broken-copy control in a disposable worktree

When the control must run after the fix, keep the working tree (and its fingerprint) untouched, under existing authority to create a temporary worktree:
1. `git worktree add --detach <temp>/control HEAD`, outside the observed paths and the evidence root. With the fix still uncommitted, HEAD already holds the pre-fix code.
2. Copy in the current versions of any new or changed test files the check needs, then break the mechanism there (revert the fix, or disconnect the call).
3. From `<temp>/control`, run exactly the same command as the passing run, writing the raw output into the evidence root.
4. Record it with `validate.py receipt ... --repo <the real repository> --artifact <temp>/control/<broken file>` and the same `--operation`. It binds to the working tree's patch, and the snapshot keeps the broken file.
5. `git worktree remove <temp>/control` after the receipt is written.

## Applications and harnesses

When the task needs a running UI, service or CLI harness, identify the exact instance/build and who owns its lifetime. Establish that it is usable before interaction. After a failed interaction, recheck the instance rather than reusing an earlier readiness assumption. Exercise the user's path and capture the observable result, not only a successful launch or health check.

Keep proof outside disposable instance state. Clean up only resources owned by this task under the existing authorization, then confirm that the receipt's files still exist and retain their hashes. If evidence was destroyed during cleanup, leave verification incomplete and recover or rerun the authorized check. These are extensions of the existing evidence contract; no lifecycle daemon or sandbox is supplied.

Control-plane success must be recorded for its actual claim: a request was acknowledged, an observer returned, or validation succeeded. Inspect payload fields such as executed, state and errors before claiming product work or completion. An exit of zero alone cannot establish those outcomes.
