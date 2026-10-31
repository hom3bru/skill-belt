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
| `send` | Fire and forget (`ask`, `reply`, `handoff`, `fyi`, `review-request`). `wake_on_reply: true` asks the listener to wake you when the answer comes. |
| `inbox`, `read`, `claim`, `reply`, `done`, `thread` | The receiving side: the same rules as the CLI. |
| `memory_read`, `memory_add` | Shared project memory: instructions plus findings, which go stale when a recorded file changes. |

`ask` returns within `wait_seconds` on purpose. Codex's default MCP tool timeout is 60 s, and a longer wait would be cut off without an answer. The pattern is: `ask`, then `wait_reply` until the status is `replied`.

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
  - `default_tools_approval_mode = "approve"` is needed for any non-interactive Codex, including the listener's, which never prompts. Without it Codex refuses every MCP tool call ("requires approval"). These tools write only to the local mailbox. Seen with Codex 0.166 on 2026-10-30.
- **Cursor:** add `"carrier-pigeon": {"command": "node", "args": ["<home>/.carrier-pigeon/bin/carrier-pigeon-mcp.mjs", "--as", "cursor"]}` under `mcpServers` in `~/.cursor/mcp.json`.

On Windows, write the full path instead of `~`.

The listener's lean Codex turns off every MCP server except `carrier-pigeon`, so once it's registered the listener's Codex gets the mailbox tools too.

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
- Mail addressed to another session is hidden from your inbox (use `all_sessions` to see it) and can't be claimed.
- `to_session` on `send` or `ask` addresses one session directly.
- The listener's own sessions are `listener`.

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

## Not built yet (the rest of the design)

- **Structured replies.** An ask could declare the shape of the answer it wants (fields and types), and the reply would be checked against it.
- **Per-ask effort and budget.** For example low effort for triage and high for review, so a trivial ask doesn't cost a full Codex turn (about 150k input tokens today).
- **Machines other than this one.** Grok is pull-only through the user's approval. A relay that keeps the same message format would be next.
- **A separate low-privilege account for the agents.** This would stop a compromised agent from reading Matt's files or keystrokes. It's the layer after Windows Hello signing.

## Verified (2026-10-30, one Windows machine)

- **Protocol suite:** `bin/carrier-pigeon-mcp.test.mjs` covers the handshake, tool schemas, `ask`/`wait_reply`, the receiving side, isError results, and that every stdout line is JSON-RPC.
- **Live Claude client:** `tests/live/mcp-claude.mjs` ran real Claude Code (Haiku) with only this server. It read and answered a seeded ask, then used `ask`, which returned the reply in the same call.
- **Codex and Cursor** registration have not been run live yet.
