# Watch CI after a push

Watching is reading, and only inside the user's request: "push it and tell me when CI is green", "watch the checks", "merge once it's green" (which also needs a merge grant). Without such a request, report the checks as they stand at the push and stop.

1. **Pin the SHA.** Watch the checks for the commit you pushed, read back from the remote. A result for any other SHA does not count.
2. **Bound it.** Use the user's limit; otherwise say the limit you will use (20 minutes is a sensible default) before you start. Poll the forge read-only (`gh pr checks <number> --watch --interval 60`, or `gh run list --commit <sha>` then `gh run watch <id>`), and stop at the limit.
3. **Report each check by name:** passed, failed, cancelled, skipped or still pending, with its link. Pending at the limit is pending, not passed. A check that is required but never started is reported as missing.
4. **On a failure, stop.** Quote the failing job's name, link and first error lines. Do not re-run jobs, push a fix, change CI configuration or mark anything flaky. Fixing CI is `westack-ci`, which is pending (not built yet): say so and offer the choice, a local reproduction with `westack-debug` when the failure reproduces locally, or the user's own fix.
5. **Green grants nothing.** All checks passing does not authorise a merge, a release or a deploy. Merge only under a merge grant, after the merge pre-checks in [deliver](deliver.md).

Report the delivery state as before (for example `pushed; PR open; checks 6 passed, 1 pending at the 20-minute limit`).
