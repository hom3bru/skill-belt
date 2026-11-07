<!-- draft-2a6 -->
Thanks for the review. Some background first: this PR adds connection pooling to the orders service, which we discussed in the planning document last month, and it touches the database client and its configuration.

I ran the load test again on staging. The p95 latency was 412 ms, against 655 ms before the change. The flaky test, test_checkout_timeout, failed 3 of 40 runs before the fix and 0 of 40 after it.

Given all of this, I think the PR is ready to merge.
