# What done means, claims and the checks

Read in claim and acceptance modes (and after resume). The start page keeps the hands-off rule, the baseline rule (new failures apart from pre-existing ones) and the report.

## A check needs a grant

Running a check is an action. Run only what the user's grant covers. A check that reaches beyond the workspace needs its own grant: network services, shared databases, deploys, paid APIs. Without one, give the user the exact command and where to save its output, then parse what they return; otherwise the check is blocked.

## What "done" means

1. Take the criteria from the user's request in this conversation first. Then use the task record's acceptance list, then the plan, issue or PR description. The claimant's summary is a claim to check, never a criterion.
2. Restate each criterion so that a check could fail it: the condition, what you will observe and the threshold.
3. Mark each criterion `agent` or `human`. It is `human` when a person must judge it: a visual or product sign-off, real-device feel, a policy or rights call, or a task record that says `verifier: human`.
4. When no checkable criterion can be derived and the answer would change the verdict, ask one question and recommend an answer. Otherwise the criterion is inconclusive; say what would settle it.

## Claims are not proof

These are claims: a ticked box, "COMPLETE", a status field, `passes: true`, a commit message, a green badge without its run log and a todo list. So are an exit code without counts and any model's verdict, whether it comes from the claimant, a sub-agent, an LLM judge or your own earlier turn. They tell you what to check. They never set a result. A gate blocks only on machine-checkable facts a stub cannot satisfy; a count, a wording hit or a phrase such as "pre-existing" or "skipping for now" only prompts a second look, reported as "look again" beside the facts that decided, and changes no result by itself.

Derive every result from the receipts when you read, never from a stored pass flag or a saved aggregate: recompute status from the separate facts (artifact present, review passed, claim live) and name the file or step of any fact that fails. A task record's `state`, `completion` and `verification` are a cache that must agree with the evidence; `python "<core>/scripts/validate.py" task` recomputes them and fails when they do not.

A stock excuse for skipping a check prompts that check; it is never a result.

| Excuse | First action | Report |
| --- | --- | --- |
| "pre-existing" | match the name against the baseline receipt | pre-existing with that receipt; no baseline: unattributed unless proved at the parent commit |
| "flaky" | rerun it alone, same command | both runs; failing again is failed |
| "should work" | run the check that reaches it | its receipt, or not-run and why |
| "tiny change" | run the same checks as any change | the same receipts table |
| "tested by hand" | ask for the command and output, or rerun | a claim until a receipt exists |

## The checks

- **Run what was claimed, as claimed.** Record the options and inputs in effect for each check. A run-selection flag (a name or path filter, `-k`, `--grep`, `--lf`, fail-fast) or an input the runner or CI action ignores makes the receipt a narrower claim: the skipped part is not-run, and a green exit is never a full pass. An oracle-update flag makes it an update run, which supports no parity claim (core `evidence.md`). Then run whatever exercises the claim. Save each raw output and parse it with `python "<core>/scripts/checks.py" parse <raw>`. When nothing was collected or executed, the result is not passed, whatever the exit code. A check script with no runner counts passes on exit zero plus a success marker it prints after its last assertion; record the exit and the marker line. Error text never passes a nonzero exit, truncated output fails, and exit zero without the marker is inconclusive.
- **Baseline.** The start page's rule: new and pre-existing failures as two lists.
- **Controls.** When the claim is that a test or check detects something, run the same selection against a broken copy outside the work. It must fail on the assertion, not on an import or collection error, and you keep that failing output. Before trusting an automated gate, read it for tautologies (a fixed-output command, a weak expectation such as "ok", a path used as a regex, an unmeasured number); that read never replaces the broken-copy run.
- **Exercise the claim.** A passing suite that never reaches the changed behaviour does not show a behaviour criterion. Name the test or observation that does, or mark the criterion inconclusive. Derive expected values without the code under test, and from source data, never from the request text: a number copied from the brief is not its own expectation.
- **Delivery diff audit** (acceptance). Take the changed paths from version control or the PR diff, not from the claimant's list. Flag scratch files, edits to existing tests, and anything outside the asked scope.
- **Human-only criteria** stay "awaiting human verification" until a person reports back. Agent receipts never pass them.
