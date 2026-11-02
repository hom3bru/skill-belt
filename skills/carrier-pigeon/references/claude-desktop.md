# Native Claude Desktop delivery (experimental)

The `desktop-bridge` companion delivers explicitly addressed mail to an existing Claude Desktop Remote Control environment. It does not start a headless Claude worker, open a chat, type into a window, or inject renderer code. Desktop's existing Remote Control server receives the work and creates the local Code session itself.

This uses the account session API implemented by the native client, rather than a supported public automation API. It can change between Claude releases. The currently implemented credential provider supports the local Claude CLI OAuth credential file; it does not unlock a keychain, refresh tokens or change sign-in state.

## Start and address

Only the operator enables Desktop Remote Control and serves a project folder. Use the environment ID already registered by Desktop for that folder. This companion cannot register an environment, grant folder trust, change permission mode or enroll a trusted device.

After the operator approves installation, run the installed CLI in PowerShell:

```powershell
node "$HOME\.carrier-pigeon\bin\carrier-pigeon.mjs" desktop-bridge `
  --environment env_EXISTING_DESKTOP_ENVIRONMENT `
  --cwd 'C:\approved\project' `
  --org ORGANIZATION_UUID --account ACCOUNT_UUID
```

The command stays running and prints a `desktop-remote-ready` record. It publishes a session address through `agents --json` with `wake_via: desktop:remote-control`. Send through the normal MCP `send` or `ask` tool using `to: claude` and that `to_session`. Generic Claude mail keeps its existing route.

The account and organization must match the existing CLI sign-in. Expired credentials require the user's normal login. Tokens remain in memory, are sent only to `https://api.anthropic.com`, and never enter presence, mailbox content, delivery journals or error messages. Redirects are refused.

The API receives a fixed pointer containing checked mailbox identifiers and installation paths. Subject, body, context and response nonce stay in the mailbox. No platform/source identity, permission-control event or tool-approval response is asserted. Desktop selects the actual working directory from its registered environment; its configured worktree policy still applies.

## Native conversation identity

First delivery creates a native Remote Control session and records its association with the mailbox thread. Follow-ups use the same remote session. Replies wake it only when its original ask requested `wake_on_reply`. FYI mail does not wake it.

An updated carrier-pigeon MCP server can use the durable address without shell commands. Before each recipient operation it verifies:

- its own native session UUID and parent PID;
- one live registry record with the Desktop entrypoint;
- the native host-session identity and Remote Control session ID;
- the exact environment/thread association in the mailbox.

The checks fail closed on missing, changing, ambiguous or unsafe metadata. A transient MCP label alone cannot claim another Desktop conversation's mail. The existing claim generation, cancellation, deadline and reply rules still apply. These are routing checks, not a new authority boundary between processes running as the same operating-system user.

Older MCP connections use CLI fallbacks under the recipient's existing permissions. In Manual mode that can require the user's approval. The companion never answers that prompt or changes permission mode. Installing updated files does not update already running MCP processes; a newly created native session loads the updated server.

## Recovery and limits

Delivery records live in `host/claude-remote-deliveries/`; thread associations in `host/claude-remote-threads/`; process ownership in `host/claude-remote-owners/`. A live companion advertises its stable address in `sessions/`.

Three submissions per environment per minute are allowed. Further requests remain deferred until the window clears. Threads stop automatic delivery after eight messages. Cancellation and execution deadlines prevent a new submission.

An API success produces `desktop-remote-submitted`, which means submission only. Inspect native Desktop admission/process evidence, then the mailbox's claim and reply receipts. A timeout, lost connection, malformed success response or server error can mean the request was accepted: it remains `uncertain` and is not automatically replayed. Inspect the native session before deliberately retrying. Explicit API rejection is recorded separately. The companion does not forcibly interrupt an already accepted native turn when a mailbox deadline expires; the receiver must check task controls before acting.

The Desktop app must remain open, its existing environment server must be reachable, and the network must work. Trusted-device and organization policy remain applicable. Installation, startup registration and changing the default Claude route are separate operator actions.

## Qualification

Offline fixtures cover HTTP framing, credential privacy, identity binding, real MCP stdio claim/reply, thread continuity, cancellation, deferred rates and uncertain delivery. They do not prove native wake.

A Windows prototype initiated a real MCP mailbox send, submitted the pointer, and observed Desktop admit new work and spawn its bundled Claude engine. The engine's parent was the existing Desktop application, and the native transcript shows the pointer followed by an assistant tool call. No recipient was manually opened. That trial reached a Manual-mode mailbox-read permission prompt, then its execution deadline expired without a claim/reply. It proves native cold startup; the end-to-end mailbox acknowledgement remains unqualified pending a fresh run with the native-bound MCP routing.

Native resume links were also investigated. Navigation/import alone did not establish backend startup and is not used by this adapter.

Primary documentation: [Remote Control](https://code.claude.com/docs/en/remote-control), [Desktop session messaging](https://code.claude.com/docs/en/desktop#work-across-sessions), [per-session messaging controls](https://code.claude.com/docs/en/cross-session-messaging).
