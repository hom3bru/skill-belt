# Listener: details

Read this when you start, configure or debug `host/carrier-pigeon-host.mjs`, or when you need to explain a receipt or a missing wake.

The listener watches every inbox (fs.watch plus a 15 s rescan) and wakes the recipient right away.
- The wake prompt tells the agent to read the context pack and run `memory read <project>`, using the message's `repo` as the project. It does not inline files.
- The wake prompt allows reading (files and read-only commands), and only the mailbox commands may write. 0.4.0 said "read-only (mailbox commands only)", and Codex once took that as a ban on listing a folder.
- It never changes the mailbox rules. A message the listener delivers is still only a request.
- Live-tested with 0.3.1 on one Windows laptop on 2026-10-29: about 45 s from ask to reply, for both Claude and Codex.

## Adapters

**Claude.** One background headless session (`claude -p --input-format stream-json`), launched lean.
- No MCP servers (`--strict-mcp-config` with an empty config) and no claude.ai connectors.
- Tools: Read, Grep and Glob, plus the carrier-pigeon MCP server (`host/claude-mcp.json`, speaking for `claude`). The session has no shell at all.
  - 0.4.x gave it a shell limited to `node bin/carrier-pigeon.mjs *`. Claude Code 2.1.310 matched that rule inconsistently: in one session `read` and `reply` were allowed while `claim` and `status` were denied, so a woken Claude could stall without replying.
  - MCP tool permissions are exact. A live run of 0.5.0 went from wake to reply in 81 s.
- `host/claude-settings.json` denies reads of `host/secrets/**`, `~/.ssh`, `~/.aws`, `~/.config/gh`, the Codex and Claude credential files, and `.env` files.
  - The host writes this file when it is missing.
  - It merges the deny list into a 0.3 settings file that has no `permissions` block.
  - It leaves a `permissions` block you wrote alone.
  - The CLI applies the same list to its file flags, and the MCP `send` tool takes text only, never a file. So no mailbox route can carry one of those files either. Read refusal was seen in a real session (`tests/live/claude-deny.mjs`).
- The session is recycled once its context passes `claude.recycleAtContextTokens` (default 120000; 0 turns it off).
  - Context is measured from the last API call of a wake.
  - Recycling waits until no wake is in flight. Wakes that arrive during the restart are retried.

**Codex.** A local app-server on `ws://127.0.0.1:4500`: `turn/start` when idle, `turn/steer` when busy.
- Approvals are `never`, and the sandbox is workspace-write with the mailbox as the workspace. `tests/live/codex-sandbox.mjs` ran that sandbox profile: a write to a folder in the home directory was blocked, while the OS temp folder stays writable by design.
- Lean by default (`codex.lean: true`): plugins and apps are off, and every MCP server the user's config still enables is turned off by name (`-c mcp_servers.<name>.enabled=false`). 0.3.1 launched every one of them, including servers that failed auth on each start.
- Lean mode does not shrink a wake much. One measured lean wake on 2026-10-30 read 153k input tokens (121k cached). 0.3.1's full-profile wakes read 109k to 448k. Most of a Codex wake is the provider's own base prompt, repeated across the turn's model calls.
- If the websocket can't connect, or drops later, the host kills the app-server so the supervisor restarts both, with backoff. 0.3.1 instead stayed "not ready" until the host itself was restarted.
- Every app-server call times out after `codex.rpcTimeoutMs` (default 60000), so a hung reply can't stall the host's scan loop.
- The MCP listing and the launch run in the background, so the other adapters and the first scan don't wait for Codex.
- The memory prefix counts as sent only after the turn is accepted. A failed delivery is retried with the prefix, not "unchanged".
- Point `codex.bin` in `host/config.json` at the Codex desktop app's own `codex.exe`; the npm copy may be too old for the models a ChatGPT login offers. Leave `codex.model` null to use its default.
- The user can watch with `codex --remote ws://127.0.0.1:4500`.

**The user.** A desktop toast for every message (Windows; `notify-send` elsewhere). A toast addressed to Cursor opens a Cursor prompt deeplink that only prefills and never sends.
- The toast's PowerShell script is a constant; the title, text and XML reach it only through environment variables.
- 0.3.1 spliced the subject into the script source. PowerShell also ends a quoted string at a curly quote, so a crafted subject could run commands as the user.

**Grok webhook / Cursor cloud agent.** Dormant unless `host/secrets/grok-webhook.json` or `host/secrets/cursor-cloud.json` exists.
- The webhook payload is capped at 8 KB. The subject is cut to 300 characters, then the longest body prefix that fits is kept, measured in encoded bytes.
- An ask counts as sent to the webhook only after the POST succeeds, so a failure is retried. The `idempotency-key` header makes a repeat safe.
- The Cursor adapter never retries, since a failed request may still have been delivered.

## Inbox files are checked again

The host does not trust that the CLI wrote a file. Before handling one, it checks:
- the frontmatter `id` is the ULID file name;
- `to` is the inbox's owner;
- `from` is a known agent;
- the thread is a safe name;
- fork ids and the transcript sha have the expected shape.

A file that fails is logged as `bad-message` with the reason and skipped. So a hand-written file can't steer a receipt path, a route or a spawned process's arguments.

## Receipts, loop limits, rate limit

- **Receipts.** `carrier-pigeon receipts <id>` shows `queued → notified:<adapter> → received → replied|declined`, or `no-wake (reason)`.
  - A delivery that fails because a session is starting or recycling is retried automatically, up to 20 times.
  - Each failed delivery is retried exactly once, even when the adapter's ready signal and a rescan retry at the same moment. 0.4.0 could deliver it twice.
- **Loop limits.**
  - `reply` and `fyi` never auto-wake.
  - A thread stops auto-waking after 8 messages, and the user gets an alert.
  - Message ids are deduped across rescans and restarts.
- **Rate limit.** Each agent gets at most 6 auto-wakes per 10 minutes. An ask over the limit is deferred (receipt `no-wake` with reason `rate-limit`), not dropped.
  - Deferred asks are retried oldest first once the window frees (`rate-retry`).
  - The deferral survives a listener restart.
  - An ask that leaves the inbox in the meantime is dropped (`rate-retry-dropped`).
- **Stats.** Per-wake usage goes to `host/logs/usage.jsonl`.
  - Claude: stream-json `result.usage`, plus `context_tokens`.
  - Codex: `thread/tokenUsage/updated` deltas per turn. Steered asks are attributed to the turn they joined.
  - `carrier-pigeon stats` prints per-agent cached and total input and the hit rate. Hit rates are provider-reported; they are not proof of subscription savings.

## Running it

- **Start and stop.** `host/start-host.ps1 [-Background]` and `host/stop-host.ps1`. The stop script kills the child tree, including the Claude session and the Codex app-server. Only the user registers it to start at logon (`host/install-task.ps1`, if present).
- **Upgrade.** `install` replaces the code on disk. The running process keeps the old code until it is stopped and started again.
- **Files.** `host/state.json` holds the dedup set, pending receipts, rate windows and deferred asks, and is rewritten only when that state changes. Logs are in `host/logs/`: `host.jsonl`, `claude.jsonl`, `codex.log` and `usage.jsonl`.
- **Repeated warnings.** A Codex warning with the same text is logged once per listener run.
