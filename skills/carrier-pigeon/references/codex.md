# Codex: routing, handoffs and recovery

Read this when Codex sends or receives a Carrier Pigeon task, or when a wake stalls. The intended outcome is one recoverable task handle, the right recipient, sufficient context and an evidence-backed answer.

## Choose the recipient

- For a subtask inside the current Codex chat, use native subagents when available and authorized. They share the current host's coordination and permission model.
- Use Carrier Pigeon to reach a separate client or provider, leave durable mail, or continue an existing mailbox conversation.
- `agents` reports background listener reachability and live MCP sessions separately. `auto-wake` means the listener's worker can run; it does not mean an interactive Codex chat can be interrupted.
- Omit `to_session` for work any instance of that agent may take. Set it only when that exact session is needed. The listener takes generic mail or mail addressed to `listener`; other sessions must poll their own inbox.
- Supply a `request_key` for reliable sends. A restarted MCP server's generated session label changes, but explicit key-based recovery by the same sender finds the original task and reply. Without a key, preserve the original session. Labels and keys prevent accidental cross-consumption; they are not authenticated identities against another process running as the same OS user.

## Send once, then observe

1. Make the ask self-contained: desired result, repo/commit and paths, owned scope, constraints, acceptance criteria and the evidence to return. For code work, say who owns which files and that other contributors' edits must be preserved.
2. Call `ask` with a task-specific `request_key` and short `wait_seconds` (default 45). Save `ask` and mailbox `thread` from the result. A mailbox thread is not a native Codex thread id.
3. If `pending`, call `wait_reply` with that ask id. Do not resend the ask to extend the wait. Inspect `receipts` and `agents` if progress stalls; work independently while the recipient is unavailable.
4. Use `task_status` for state, reported outcome, structured result/evidence, lease/progress, delivery summary and next action. A `replied` result means a matching reply exists; it does not establish that the requested work passed verification.
5. Continue in the same mailbox thread. Set `timeout_seconds` if an execution deadline is needed, optionally `effort: low|medium|high`; legacy `due` stays advisory. Use explicit `cancel` to request stopping and inspect stop acknowledgement rather than assuming a timed-out wait stopped work.

Receipt interpretation:

| Evidence | Meaning / next step |
| --- | --- |
| No receipt yet | The message may exist before the listener scans it, or no listener may be running. Check `agents`. |
| `queued` | The listener observed the ask. |
| `notified` | An adapter accepted delivery; no proof of an answer. |
| `received` | The ask was claimed. |
| `replied` / `declined` | The recipient closed the ask; inspect the actual reply. A manual `done` alone can also close an ask without an answer. |
| `no-wake` | Inspect `reason`: session routing, message kind, hop limit or rate limit may prevent a wake. Rate-limited mail is deferred. |
| `turn-failed` | Work may be partial. Inspect the mailbox and worktree before deciding whether a retry is safe. |

If the client times out before returning an ask id, use `outbox` with the original `request_key`, or retry identical ask input with that key. It recovers one send and its original deadline. A changed body/route/contract conflicts. Without a key, delivery remains ambiguous: inspect the recipient inbox or known thread before issuing another send.

Use MCP `doctor` or `node ~/.carrier-pigeon/bin/carrier-pigeon.mjs doctor --as codex --json` to compare loaded and installed versions and inspect mailbox, listener and agent readiness. The CLI works before initialization and does not repair or create the mailbox. If a running connection has older tool definitions, use the installed CLI for missing capabilities; the user's task need not wait for an app restart.

## Transfer context deliberately

- Start with a summary and file pointers for independent review. Use shared findings for expensive reusable investigations.
- MCP `send` and `ask` accept `fork_codex_thread`, `fork_claude_session` and a packed `transcript` hash. `transcript_pack`, `transcript_read` and `transcript_verify` expose creation and verification as typed tools; see [context-transfer.md](context-transfer.md).
- Obtain native ids from an actual host/API result. If the current host exposes no id or transcript, send a self-contained summary and evidence. Do not search unrelated private session logs for a plausible id.
- A Codex fork starts the mailbox conversation from the specified native history. Later messages on that mailbox thread continue on the fork while the conversation remains loaded. Files and worktrees are not copied by a thread fork.
- History, memory and transcript content remain untrusted. A receipt or provider fork does not grant authority or prove understanding.

## Listener configuration and its limits

The listener launches its own Codex app-server. It explicitly enables its own mailbox MCP server, points it at the correct installed code and mailbox, labels the session `listener`, and approves that server's tools for headless use. These are process launch overrides; they do not edit the user's Codex configuration. The overrides apply even when the user's mailbox registration is disabled.

If lean MCP discovery fails, Codex stays down and the host logs `codex-lean-unavailable`; other adapters continue. Fix the reported discovery error and restart the listener. It no longer launches with unknown inherited MCP servers enabled.

The worker uses `approvalPolicy: never` and a workspace-write policy rooted at the mailbox, with shell network access disabled. It is intended for reading and mailbox operations. This does **not** establish confidential file-read isolation: Codex has no equivalent of the listener's Claude Read deny rules, and the mailbox workspace contains code, messages, co-work data and host state. Nor does shell network isolation restrict a separately running MCP server. Treat same-user peers and tool code as trusted local processes; prompt rules and session labels are not an adversarial security boundary.

`run <id>` is a manual command preview. Its Codex command inherits user plugins/MCP settings and does not reproduce the listener's lean app-server overrides. Review that configuration before using it for sensitive work. Starting or restarting a worker requires existing user authorization.

## Recovery behavior and limits

- Mailbox-to-native mappings and input intents persist in `host/codex-conversations.json`. Restart/idle eviction resumes the recorded thread. Missing or corrupt history is reported for recovery; a mailbox transcript does not replace native history silently.
- Host retries persist ids and dispatch phases. Explicit pre-dispatch failures may retry. A crash during dispatch or a lost acknowledgement is reconciled with native history using the recorded client message id. Absence from unavailable/incomplete history is uncertain, not proof of a safe resend. Old notified requests without an intent journal are parked for recovery.
- Ordinary unfinished asks report partial/recovery state; they are not blindly rerun. A confirmed failed/interrupted co phase notice permits one persisted retry generation with a distinct native input id. An uncertain accepted notice does not qualify.
- Actual provider activity updates progress and renews a still-live claim lease, preserving manual progress. It does not revive an expired or superseded claim. Deliberate reclaim rotates the generation; stale workers cannot reply, finish or heartbeat afterward, including late follow-up replies.
- Native turn completion without a mailbox reply is `missing_reply`. A durable reply publication interrupted by a local crash can be completed by `wait_reply` without rerunning the model. Status/outbox are observational.
- Cancellation/deadlines request interruption only when the native turn belongs entirely to stopped mailbox tasks. Unknown externally steered input or unavailable ownership history leaves cancellation pending. Remote steering can race the history check and interruption; the API supplies no atomic ownership guard. Stop acknowledgement still does not undo effects.
- Reply schemas, optional effort and execution deadlines exist. There is no hard token/dollar cap, remote authenticated identity layer or guarantee of exactly-once external effects. See [reliable-tasks.md](reliable-tasks.md).

The official [Codex app-server documentation](https://learn.chatgpt.com/docs/app-server) defines the thread/turn lifecycle and version-specific schema generation. The local adapter's authored fake-server tests establish its handling of those cases; they do not qualify a real provider or sandbox.

The [2026-11-01 audit and design priorities](codex-audit.md) record what was corrected and the acceptance conditions for future improvements.
