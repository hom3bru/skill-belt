# Codex workflow audit, 2026-11-01

This records the 0.9.2 audit. The subsequent authorized 0.10.0 upgrade implements the request lifecycle, persisted recovery, leases, reply contracts, diagnostics and typed context tools described in [reliable-tasks.md](reliable-tasks.md); its verification is recorded separately in [the live-test record](../tests/live/README.md).

Scope: the 0.9.1 skill, CLI, MCP server, Codex listener adapter, authored tests and earlier live-test record. The 0.9.2 changes preserve the local file mailbox and existing permission boundaries. No new dependency, daemon, external messaging route or real-model trial was introduced for this audit.

## Design target

Carrier Pigeon should let an agent say: **ask this peer for this result, with this context and authority, and give me a durable handle whose outcome I can recover.** The file mailbox already supplies durable artifacts, atomic claims, explicit threads, provenance and a useful distinction between peer requests and human authority. Keep those foundations.

Optimize the ordinary path for one typed ask and a typed result. Make context transfer and co-work available when the task needs them. A human should be involved for a decision or missing authority, not for shell quoting or figuring out whether an answer was silently lost.

## Findings addressed in 0.9.2

| Finding | Consequence | Correction and evidence |
| --- | --- | --- |
| The listener replaced MCP command/args without enabling the server or approving its tools. | A disabled user registration or approval requirement could strand a headless worker. | Explicit process-local enable/approval overrides; host regression test. |
| A failed lean MCP inventory still launched Codex with unknown inherited servers. | The promised mailbox-only tool profile could silently expand. | Leave Codex down with `codex-lean-unavailable`; other adapters continue. Repair discovery and restart; host regression. |
| Session routing stopped at inbox/claim checks. Wait, reply and completion paths lacked equivalent ownership checks. | Two Codex sessions could consume or finish each other's task accidentally. | Validate sender/session and matching reply ownership; preserve claim ownership through reply/done and co phase completion; CLI/MCP regressions. |
| A native Codex fork was not registered as the mailbox conversation. | The next follow-up could lose exactly the history the handoff was intended to preserve. | Bind the fork to the mailbox thread; host regression. |
| Any steer error fell through to a fresh turn. | A connection, timeout or server failure could be misclassified as an ended turn. | Start a replacement only after an observed turn completion; propagate other failures; host regression. |
| Concurrent delivery could create two native conversations or overlap turn starts. | One mailbox conversation could split across histories, or a start could race another pending start. | Share in-flight conversation creation and defer delivery while a turn start is pending; host regressions. |
| Interruption/disconnection could lose visibility of unfinished active work. | The caller could keep waiting without a failure record. | Route unfinished active and steered asks through existing failure reporting; host regressions. |
| MCP omitted the existing CLI's handoff fields and receipt reader. | Codex had to abandon typed tools for the capabilities the skill recommended. | Expose optional handoff/deadline fields and receipts; preserve JSON text while also returning MCP structured content; protocol regressions. |
| MCP advertised schemas without enforcing them and could crash on a valid JSON `null` request. | An invalid call could mutate the mailbox or take the server down. | Validate inputs before execution and reject malformed request objects while keeping the connection usable; protocol regressions. |
| The skill promised broad session memory, described manual launch as listener-equivalent and prescribed unlimited waits. | Agents could rely on continuity or delivery guarantees the code does not provide. | Document exact routing, bounded observation, native ids, timeout ambiguity, restart limits and launch differences in [codex.md](codex.md). Shorten discovery metadata and remove contradictory tool preference. |

The tests exercise local protocol and adapter behavior. Earlier live results retain their original version labels in [the live-test record](../tests/live/README.md). No new claim is made about model effectiveness, provider availability, actual Windows Hello signing or confidential read isolation.

The locally configured Codex 0.166.0-alpha.5.1 generated its app-server JSON schemas successfully. A no-turn `config/read` probe confirmed that the new process overrides resolve to `enabled: true` and approval mode `approve`, including over a disabled registration. This configuration probe made no model call; it does not prove tool execution inside a real turn.

## Priorities recorded at 0.9.2

These are design proposals, not implemented features or permission to expand the architecture.

| Priority | Capability | Observable acceptance condition |
| --- | --- | --- |
| 1 | Recoverable request lifecycle: idempotency key, outbox/status lookup, receipts, terminal result and explicit cancellation. Separate delivery state from work outcome. | Kill the client after send but before acknowledgement. Reconnect and recover the same ask by caller key without a second task. Cancellation reports whether work stopped, was already completed or may be partial. |
| 1 | Persisted delivery retry state, Codex conversation mapping and turn reconciliation. | Restart after a failed delivery and recover its pending retry; restart between turns and continue on the same native thread. Drop an acknowledgement after an accepted start/steer and reconcile without blindly submitting again. |
| 2 | Claim leases and explicit recovery. | Kill a worker after claim; status identifies abandoned work and supports a deliberate reclaim while preserving its history and partial artifacts. |
| 2 | Small typed answer contract: completed/declined/blocked/partial, evidence, changed files and verification. | A closed mailbox item cannot masquerade as a verified implementation; invalid reply shapes return useful errors before closing the ask. |
| 2 | Per-ask effort, deadline, resource budget and progress heartbeat. | A stalled request becomes visibly actionable; progress never extends a fixed budget silently. Idle healthy tasks do not spam the caller. |
| 3 | Capability-based worker access and stronger identity separation. | A compromised worker cannot read another private session, change host code/state, open sealed work or use unrelated credentials. Verify with adversarial OS/tool tests, not prompt compliance alone. |
| 3 | Context diagnostics and low-overhead tool profiles. | Report which context artifact was sent, its verified bytes and truncation, without claiming comprehension or savings. Measure quality and latency against summary-only baselines before adding more context by default. |

For the current local prototype, reliability comes before a remote relay, more providers, a dashboard or another orchestration layer. The next two priorities require task-state and recovery design decisions; they should be reviewed as a separate change.

A temporary-mailbox restart probe reproduced the delivery gap: before shutdown `retryQ.size` was 1; after restart with a healthy fake adapter it was 0, delivery count was 0, and the ask still appeared `queued`. `Host.saveState` persists dedup/pending/rate-limit state, but not adapter retries. Recovery must distinguish undelivered work from a lost acknowledgement before it can safely automate resubmission.
