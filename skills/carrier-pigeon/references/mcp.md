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

## Not built yet (the rest of the design)

- **Per-thread sessions.** Today one warm Claude session and one Codex thread serve every wake. Continuity comes from `thread`, not from session memory. A Codex thread per mailbox thread would carry it natively.
- **Structured replies.** An ask could declare the shape of the answer it wants (fields and types), and the reply would be checked against it.
- **Per-ask effort and budget.** For example low effort for triage and high for review, so a trivial ask doesn't cost a full Codex turn (about 150k input tokens today).
- **Machines other than this one.** Grok is pull-only through the user's approval. A relay that keeps the same message format would be next. Authentication can't be solved while every agent runs as the same OS user.

## Verified (2026-10-30, one Windows machine)

- **Protocol suite:** `bin/carrier-pigeon-mcp.test.mjs` covers the handshake, tool schemas, `ask`/`wait_reply`, the receiving side, isError results, and that every stdout line is JSON-RPC.
- **Live Claude client:** `tests/live/mcp-claude.mjs` ran real Claude Code (Haiku) with only this server. It read and answered a seeded ask, then used `ask`, which returned the reply in the same call.
- **Codex and Cursor** registration have not been run live yet.
