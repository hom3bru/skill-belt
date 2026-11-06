# Resume mode: re-check before trusting earlier "done"

Use it when the claim of done, or the receipts behind it, come from an earlier session, another agent, or before you reuse any old receipt.

1. **Refresh the context.** Read the revision, the working-tree status and the scope now. With a task record, run `python "<core>/scripts/validate.py" task <newest record> --root <evidence root> --repo <repo> --scope <scope> --chain <record folder>`. Passing means the record is consistent, not that it is true. The record's stored `state`, `completion`, `verification` and per-criterion status are a cache: the command recomputes them from the receipts and fails on a disagreement, so read the result from the receipts, never from the stored field.
2. **Smoke check first.** Before anything else, run the cheapest check that a required criterion depends on: the record's `resume_check`, or the test of the most central behaviour. Do this even when the patch fingerprint matches; dependencies, services, data and tool versions sit outside the fingerprint.
3. **Read the result.**
   - Passed, same environment: earlier receipts for the same patch and scope stay current. Say which ones you are reusing.
   - Failed, or the environment changed (tool versions, dependency lock, service versions): earlier receipts are stale. Every criterion they backed goes back to not-run and is checked again.
4. **Never resume from ticks.** Checked boxes, a "COMPLETE" line or a progress note decide what to look at first. They never decide that a criterion passed.
5. Continue in [claim](claim.md) or [acceptance](acceptance.md) mode. The smoke check is the first row of the receipts table.
