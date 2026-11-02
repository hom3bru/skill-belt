# Reliable task handoffs (0.11.0)

The requested upgrade makes a cross-client ask recoverable without changing the local mailbox or installing a service or dependency. Existing messages, CLI commands and text replies remain usable. New lifecycle controls are opt-in where they change a request's contract.

## Goal and acceptance conditions

An agent can send one self-contained ask, recover its handle after a client restart, observe delivery separately from work outcome, continue the same Codex conversation after listener restart, and cancel without mistaking partial work for undone work.

The upgrade is checked against these observable conditions:

1. Concurrent or crash-retried sends with the same sender and request key produce one message; conflicting reuse fails before delivery. A new session can explicitly recover its original request by that key.
2. A stopped listener retains known retry attempts. An ambiguous dispatch is reconciled against provider history or reported as requiring recovery; it is never blindly treated as a safe new send.
3. Codex conversation mappings survive listener restart and idle eviction. A lost start/steer acknowledgement is checked with its recorded client message id before resubmission.
4. Unclaimed cancelled or expired tasks do not start. Active cancellation remains requested until the worker or adapter acknowledges stopping; cancellation never claims to undo effects.
5. Status reports sender/recipient, delivery evidence, outcome, lease/progress and the next actionable condition. A closed ask without a reply is distinguishable from a completed answer.
6. Explicit progress renews a claim lease. Expiry permits deliberate recovery with a reason; it does not silently launch a second worker.
7. Optional structured replies are validated against the requested supported schema before closing the ask. Human signatures cover the new execution and reply metadata.
8. MCP exposes these operations, transcript transfer and connection diagnostics without shell quoting. MCP cancellation stops a wait while retaining the delivered request.

## Contracts and boundaries

- A `request_key` names one logical send, scoped to the sending agent. Keep it with the task. Deliberate key-based recovery can cross session labels; ordinary operations retain session ownership checks. Keys are local recovery handles, not authentication against same-user processes.
- `timeout_seconds` is an explicit execution deadline. Legacy `due` remains advisory. Neither deadline nor transport cancellation proves that work was undone.
- Outcomes are `completed`, `declined`, `blocked` or `partial`. Completion describes the peer's report; verification still requires evidence. A transport/delivery receipt is not a verification result.
- Progress/leases detect abandoned work, not worker honesty. No automatic reclaim of partially performed work.
- Existing request authority and secret/file-read rules remain. The worker remains restricted to its configured permissions; peer text cannot expand them.
- No change can promise exactly-once external side effects. A message id and provider reconciliation prevent known duplicate submission; uncertain history stays visibly uncertain.

## Operations

| MCP tool | CLI | Contract |
| --- | --- | --- |
| `ask` / `send` with `request_key` | `ask` / `send --request-key KEY` | One immutable logical send per sender/key; identical replay recovers its original id and deadline. A changed body, route or contract conflicts. |
| `outbox` | `outbox --as A [--request-key KEY]` | Find the task without resending it. A key explicitly permits original-session recovery by the same sending agent. |
| `task_status` | `task ID --as A [--request-key KEY]` | Observe state, reported outcome, result/evidence, bounded delivery summary, progress, deadline, claim lease and next action. Status and outbox do not repair or mutate the mailbox. |
| `wait_reply` | `wait ID --as A [--request-key KEY]` | Wait on the same task; also completes a durably prepared reply's publication after a crash, without rerunning agent work. |
| `cancel` | `cancel ID --as A --reason TEXT` | Requester-owned cancellation. Queued work stops; accepted or claimed work waits for confirmed stop. |
| `heartbeat` | `heartbeat ID --as A --progress TEXT` | Claim-owner progress, lease renewal and cancellation/deadline check. Expired claims do not silently revive. |
| `reclaim` | `reclaim ID --as A --reason TEXT` | Recipient deliberately takes over an expired claim, after inspecting partial effects; the generation token rotates. Directed mail remains directed to its original session. |
| `reply` | `reply ID --as A --body TEXT --outcome completed --result JSON --evidence TEXT` | Validate the answer before closing the ask. CLI reply evidence may be repeated; MCP takes a string array. |
| `doctor` | `doctor [--as A] --json` | Shared read-only version, mailbox, listener and agent-readiness checks. Reports an uninitialized mailbox without creating it. Use the installed CLI for a capability absent from an already-running connection. |

For a new review, choose a task-specific key such as `project-pr23-review-v1`, send the ask with paths and acceptance criteria, then keep its id. If the client restarts, `outbox {request_key: ...}` recovers it. Reuse a key only for recovery of identical work; a new request gets a new key.

## State and recovery details

`queued`, `claimed` and `running` describe progress. `cancel_requested` describes a stop request, including an active deadline expiry. `completed`, `declined`, `blocked` and `partial` describe reported outcomes; `closed_without_reply` means an ask was closed without an answer. `missing_reply` means a native turn finished without closing its mailbox ask. `recovery_needed` means delivery or partial work requires inspection.

An expired wait can return `status: expired` while its attached task remains `cancel_requested`, `terminal: false`, `execution_stopped: false`. This reports that the deadline passed without pretending the worker stopped. A completed answer remains readable after its original deadline. No token/dollar budget is enforced; `effort` and the explicit execution deadline are the available controls.

Claim generations protect against stale workers after a deliberate reclaim. MCP caches a successful claim/reclaim token for that connection; callers can also supply it explicitly. A reconnect that loses a recipient's token can inspect its own task status, while a requester receives no claim token through status/outbox. Session labels and tokens are workflow fencing, not protection against arbitrary same-user file access.

Since 0.10.1, reclaim durably revokes the old generation before publishing the new message. If message publication or the final control commit fails, the task stays `recovery_needed` with its expired lease. Both mailbox operations and native events reject the old generation. Inspect partial effects and deliberately reclaim again to finish recovery; an interrupted takeover never silently resumes work.

Request-key journals store a prepared immutable message before publication and detect conflicting reuse or corrupted content. Reply controls similarly store a validated, hashed prepared reply before publishing it. `publication_pending` identifies an interrupted publication. Observational status reports what happened; retrying the same keyed send or calling `wait_reply`, as indicated by `next_action`, finishes protocol publication without repeating the underlying work.

Since 0.10.2, a recipient retry of `reply` while that prepared answer exists also finishes its publication and returns the original id/result with `publication_recovered: true`. It never replaces the committed content, even when the retried arguments differ. Once publication has finished, later replies remain ordinary follow-ups; this is not a promise of deduplicating arbitrary repeated replies after a lost acknowledgement. Keep-open replies do not create a prepared terminal answer and need separate reconciliation after uncertain publication.

Host retries store only ids, routing and dispatch phases. A confirmed pre-dispatch failure may retry. An in-flight crash or lost acknowledgement requires reconciliation. Codex correlates its persisted client input id with native history; a missing id in incomplete history does not prove that input was never accepted. Old notified requests from a version without native intent records are likewise uncertain and must not be replayed automatically.

The controls assume a 0.10.0 runtime on both sides. An older already-running MCP process retains its older implementation. If `doctor` is missing or reports a mismatch, use the installed CLI for the entire reliable-task lifecycle, including claim/reply/done, until that client refreshes. Old loaded code and raw same-user file writes are outside these workflow enforcement guarantees. The background listener supplies a fresh matching MCP server of its own.

## Supported reply schemas

The root has `type: object`. Nested properties support `object`, `array`, `string`, `number`, `integer`, `boolean` and `null`; `properties`, `required`, boolean `additionalProperties`, `items`, `enum`, numeric `minimum`/`maximum`, string `minLength`/`maxLength`, and array `minItems`/`maxItems`. `description` is allowed. There are no references, regexes, combinators, coercion or external schema fetches. Schema depth is capped at 8, schema bytes at 8 KB, result bytes at 16 KB and reply evidence at 8 KB/50 strings.

For example, `{type:"object", properties:{count:{type:"integer",minimum:0}}, required:["count"], additionalProperties:false}` asks for `result: {count:4}`. The peer still returns a readable body and should give the evidence supporting its reported outcome.

When a schema was requested, `completed` requires a valid result. `blocked`, `declined` and `partial` may return a truthful body without result data; they must not fabricate success fields to fit a schema. Any supplied result is still validated against the requested schema.

Raw message frontmatter keeps schema/result/evidence as canonical JSON strings for compatibility. `task_status` decodes them. New Windows Hello signatures use payload version 2 and bind task controls, results, sender session and handoff references; legacy signatures with uncovered execution metadata require signing again. No new Windows Hello gesture is performed by automated tests.

## Validation

Start with isolated temporary-mailbox tests for CLI lifecycle, MCP protocol and fake app-server restarts. Run the collection's required `python -B scripts/verify.py`, skill validation, byte manifests and diff review. A separate opt-in Codex recovery trial can exercise real persistence without touching the live mailbox; its result and limits must be recorded separately from authored tests.

The [official app-server documentation](https://learn.chatgpt.com/docs/app-server) describes `thread/resume`, `thread/read`, `turn/steer` and `turn/interrupt`. The configured local binary's generated schema governs the adapter's exact wire fields, including `clientUserMessageId` and returned user-item `clientId`.
