# Review

Review against requirements and the actual changed patch: correctness, regressions, security, scope and maintainability. Scale depth to risk; do not create parallel reviewers merely for ceremony.

D06 informs the lifecycle of generated verification instructions: run them against the actual application path, preserve proof through cleanup, and leave unexecuted instructions draft. Estack adds the frozen good/broken liveness control; a constant-true verifier fails that test. The separate pstack shipping playbook informs non-author same-patch review, which needs an actual different reviewer/context bound to the patch hash. Generating a verifier, taking a persona name or rerunning your own checklist does not create independence.

When independent context is available and authorized, provide the goal, constraints, patch and relevant raw evidence. Do not invent a review if no reviewer is available. Label self-review as self-review and record the missing independent review when required. This package installs no reviewers and starts no agents.

Use the canonical finding: claim, source location, consequence, evidence IDs, severity and rationale, correction, adjudication, verification IDs. Resolve conflicting findings through evidence. Record accepted, rejected with rationale, fixed, or deferred with residual risk. Unresolved required findings block a complete result; reviewer agreement alone does not resolve a contradiction.

