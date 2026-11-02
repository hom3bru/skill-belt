# The MCP server: agents call each other as tools

Read this when you set up carrier-pigeon for a client that speaks MCP (Claude Code, Codex, Cursor), or when an `ask` returned `pending`.

## Why

The CLI works anywhere, but every call through a shell costs quoting, permissions and a parse of the output. Over MCP the mailbox becomes typed tools the model calls directly:
- **Arguments are validated by schema.** Agent ids are an enum, and the required fields are declared.
- **No shell is involved**, so there's no PowerShell or Bash quoting and no shell allow-rule to get right.
- **Errors come back as tool errors**, not exit codes.

The server is `bin/carrier-pigeon-mcp.mjs`. It needs no dependencies and uses MCP's stdio transport (JSON-RPC 2.0, one message per line). One server speaks for one agent (`--as <id>`). It never reads stdin for message bodies and never prints anything but protocol messages.

## Tools

| Tool | Does |
|---|---|
| `ask` | Sends an ask and waits up to `wait_seconds` (default 45) for the reply. Returns `{status:"replied", reply}`, or `{status:"pending", ask}` to pass to `wait_reply`. |
| `wait_reply` | Waits again for the reply to an ask you sent. A reply it finds is marked done unless `keep`. |
| `agents` | Who is reachable now: `auto-wake` (the listener wakes them), `notify-only` (a toast) or `pull` (they see mail only when they check). Also inbox sizes and median wake time. |
| `receipts` | Delivery events for one message id, including deferral and failure reasons. Acceptance or closure is not proof of a verified answer. |
| `doctor` | Loaded/installed versions, current session and listener readiness; detects stale connections. Also `initialized`, `health` (`ready`, `attention`, `uninitialized`) and `checks` with a `next_action` per warning. Read-only and shared with the CLI `doctor`; it works before `init`. |
| `task_status`, `outbox` | Recover original task ids and observe delivery, outcome, progress, lease, cancellation and next action. |
| `cancel`, `heartbeat`, `reclaim` | Request a stop, renew a live claim, or deliberately take over an expired claim with a new generation. |
| `transcript_pack`, `transcript_read`, `transcript_verify` | Transfer verified context without shell quoting; reads report truncation and can record receipts. |
| `send` | Fire and forget (`ask`, `reply`, `handoff`, `fyi`, `review-request`). `wake_on_reply: true` asks the listener to wake you when the answer comes. |
| `inbox`, `read`, `claim`, `reply`, `done`, `thread` | The receiving side: the same rules as the CLI. |
| `memory_read`, `memory_add` | Shared project memory: instructions plus findings, which go stale when a recorded file changes. |

`doctor` compares the loaded version with the `VERSION` declared in the mailbox's `bin/cp-context.mjs`, read as text and never executed. `needs_reconnect` is true only when that file declares a version that differs from the loaded one. A mailbox initialised without `install` has no such file, so `installed_version` is `null` and the `version` check warns. The `listener` check trusts `agents`' liveness validation. `agent:claude` and `agent:codex` are `ok` only for reach exactly `auto-wake`. `ready` health needs an initialised mailbox and every check `ok`. Session bookkeeping when the server starts is transport behaviour; the doctor call itself writes nothing.

Successful results include both `structuredContent` and JSON text for clients with different MCP support. Tool arguments are checked before execution, including required fields, types, enums and unknown fields.

`send` and `ask` expose `due`, `transcript`, `fork_codex_thread`, `fork_claude_session`, `request_key`, `timeout_seconds`, `effort` and `reply_schema`. `due` stays advisory; the explicit timeout controls execution expiry. A request key recovers one identical task after a client/session restart; it is not authority to change its content. See [reliable-tasks.md](reliable-tasks.md) for state and reply contracts, and [context-transfer.md](context-transfer.md) for context fidelity.

`ask` returns within `wait_seconds` on purpose. Keep that wait below the client's timeout; the default 45 seconds fits Codex's default 60-second MCP timeout. On `pending`, retain the ask id and call `wait_reply` for the same ask. Inspect `receipts` and `agents` if progress stalls; do not issue duplicate asks or wait indefinitely for a pull-only recipient. A transport timeout or cancellation does not undo a delivered message. See [Codex recovery](codex.md).

MCP `notifications/cancelled` aborts an active ask/wait promptly and returns its original handle when the channel remains open. It preserves the delivered task; use the explicit `cancel` tool to request stopping work. Closing the connection also stops outstanding waits. The caller can recover by request key in a new session.

`claim`/`reclaim` return a generation token. This MCP connection remembers it for `reply`, `done` and `heartbeat`, so normal work needs no manual token plumbing. After reclaim, an older connection cannot write, including late follow-up replies. Explicit `claim_token` arguments support recipient recovery; requester status/outbox omit the token.

## Registering it (once per client)

Use the installed copy, `~/.carrier-pigeon/bin/carrier-pigeon-mcp.mjs` (`node <skill>/bin/carrier-pigeon.mjs install` puts it there), and give each client its own id.

- **Claude Code:**
  ```
  claude mcp add --scope user carrier-pigeon -- node ~/.carrier-pigeon/bin/carrier-pigeon-mcp.mjs --as claude
  ```
- **Codex:** run
  ```
  codex mcp add carrier-pigeon -- node ~/.carrier-pigeon/bin/carrier-pigeon-mcp.mjs --as codex
  ```
  Or add this to `~/.codex/config.toml`:
  ```
  [mcp_servers.carrier-pigeon]
  command = "node"
  args = ["<home>/.carrier-pigeon/bin/carrier-pigeon-mcp.mjs", "--as", "codex"]
  tool_timeout_sec = 120
  default_tools_approval_mode = "approve"
  ```
  - `tool_timeout_sec` lets `ask` wait longer than Codex's 60 s default.
  - `default_tools_approval_mode = "approve"` approves this server's tools for a non-interactive client that cannot prompt. Without it, Codex 0.166 refused MCP calls with "requires approval" in the 2026-10-30 trial. Mailbox writes can also trigger configured listener wakes or external adapters, so approving tools is not authorization for arbitrary peer contact.
- **Cursor:** add `"carrier-pigeon": {"command": "node", "args": ["<home>/.carrier-pigeon/bin/carrier-pigeon-mcp.mjs", "--as", "cursor"]}` under `mcpServers` in `~/.cursor/mcp.json`.

On Windows, write the full path instead of `~`.

The listener supplies its own `carrier-pigeon` registration through process-local overrides: the correct executable, mailbox root, `--session listener`, `enabled=true` and approval mode `approve`. It does not depend on the user's registration, including when that registration is disabled. Lean mode disables other discovered MCP servers, plugins and apps. Interactive clients still need their own registration.

The listener's own Claude session needs no registration. The host writes `host/claude-mcp.json` with this server and launches Claude with only these tools plus Read, Grep and Glob.

## Conversations between agents

A plain reply never wakes anyone, which stops two listener-run agents from looping. For a real back-and-forth, the asking agent sets `wake_on_reply` (CLI: `--wake-on-reply`).
- When the answer arrives in the same thread, the listener wakes the asker with a "continue the conversation" prompt instead of "answer this".
- The hop limit (8 messages per thread) and the rate limit (6 wakes per 10 minutes) still apply.
- Every later wake in a thread points the agent at `thread <id>`, so the conversation carries across wakes and providers.

## Sessions

An agent id (`claude`, `codex`, …) names a kind. Any running Claude may take an ask sent to `claude`. A session names one running instance.
- Each MCP server is a session: `--session <label>`, or `CARRIER_PIGEON_SESSION`, or a generated label like `claude-mvw2ra04mbu`. While it runs it keeps `sessions/<agent>~<session>.json`, so `agents` lists it, with the client's name.
- A message records the sender's session (`from_session`). A reply goes back to that session (`to_session`).
- Mail addressed to another session is hidden from your inbox (use `all_sessions` to see it) and can't be claimed. An explicit sender request key recovers that sender's original task across a session restart; ordinary no-key ownership checks remain.
- `to_session` on `send` or `ask` addresses one session directly.
- The listener's own sessions are `listener`.
- Waiting validates the original ask's sender/session and matches the reply's sender, thread and recipient/session. Replying or closing claimed work also checks claim ownership. New claims store the session explicitly; legacy `agent:pid` records retain their old interpretation. These prevent accidental cross-session handling; a local process with mailbox access can still forge labels or edit files.

## Signed authority (Windows Hello)

A message from `matt` carries Matt's authority only when it is signed with his Windows Hello key.
- **Setup:** `hello init`, once, in Matt's own terminal. Windows Hello creates the key in the TPM, and it never leaves it.
- **Signing:** `send --from matt … --sign` (or `reply … --as matt --sign`) prints what is about to be signed. Windows Hello then asks for his PIN, face or fingerprint in Windows' own prompt.
  - The signature covers that message's id, sender, recipient, session, thread, reply-to, kind, subject, body and context hashes, and an expiry (`--expires-min`, default 60).
  - Changing any of them breaks it.
- **Checking:** `read` (CLI and MCP) and the listener check the signature themselves, so no model decides. They read the public key from the same Windows Hello credential, never from a file, so an agent that can write the mailbox can't substitute its own key. The listener records the result as an `authority` receipt.
  - `verified`: Matt's authority for exactly what the message says, until it expires.
  - `unsigned`, `expired`, `invalid` or `unverifiable`: unauthenticated.
- **What it stops:** an agent or malware running as Matt can request a signature, which shows a Windows Hello prompt on his screen. It can't complete that prompt.
- **What it doesn't stop:** malware that already controls Matt's session could change a message between the moment it's displayed and the moment it's signed. A separate low-privilege account for the agents is the next layer.
- There is no MCP tool for signing: only a human at the terminal signs.

## Remaining boundaries

- **Hard token/dollar budgets.** Optional effort and an execution deadline exist; exact provider token or spending caps do not.
- **Exactly-once external effects.** Idempotent local sends and native reconciliation do not undo partial work or guarantee an external operation ran once.
- **Machines other than this one.** Grok is pull-only through the user's approval. A relay that keeps the same message format would be next.
- **A separate low-privilege account for the agents.** This would stop a compromised agent from reading Matt's files or keystrokes. It's the layer after Windows Hello signing.

## Verified (2026-10-30, one Windows machine)

- **Protocol suite:** `bin/carrier-pigeon-mcp.test.mjs` covers the handshake, tool schemas, `ask`/`wait_reply`, the receiving side, isError results, and that every stdout line is JSON-RPC.
- **Live Claude client:** `tests/live/mcp-claude.mjs` ran real Claude Code (Haiku) with only this server. It read and answered a seeded ask, then used `ask`, which returned the reply in the same call.
- **0.9.2 regression coverage:** typed validation, handoff fields, structured results, receipts and session ownership are tested with a spawned stdio server and a temporary mailbox. There was no new real Codex or Cursor client trial for this release.
