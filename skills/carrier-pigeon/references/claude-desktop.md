# Native Claude Desktop delivery (experimental)

The `desktop-bridge` companion delivers explicitly addressed mail to an existing Claude Desktop Remote Control environment. It does not start a headless Claude worker, open a chat, type into a window, or inject renderer code. Desktop's existing Remote Control server receives the work and creates the local Code session itself.

This uses the account session API implemented by the native client, rather than a supported public automation API. It can change between Claude releases. The currently implemented credential provider supports the local Claude CLI OAuth credential file; it does not unlock a keychain, refresh tokens or change sign-in state.

## Start and address

Only the operator enables Desktop Remote Control and serves a project folder. Use the environment ID already registered by Desktop for that folder. This companion cannot register an environment, grant folder trust or enroll a trusted device. New sessions start in Auto permission mode, the operator-selected bridge default; this uses Claude's normal classifier and does not enable bypass mode.

After the operator approves installation, run the installed CLI in PowerShell:

```powershell
node "$HOME\.carrier-pigeon\bin\carrier-pigeon.mjs" desktop-bridge `
  --environment env_EXISTING_DESKTOP_ENVIRONMENT `
  --cwd 'C:\approved\project' `
  --org ORGANIZATION_UUID --account ACCOUNT_UUID
```

The command stays running and prints a `desktop-remote-ready` record. It publishes a session address through `agents --json` with `wake_via: desktop:remote-control`. Send through the normal MCP `send` or `ask` tool using `to: claude` and that `to_session`. Generic Claude mail keeps its existing route.

The account and organization must match the existing CLI sign-in. Expired credentials require the user's normal login. Tokens remain in memory, are sent only to `https://api.anthropic.com`, and never enter presence, mailbox content, delivery journals or error messages. Redirects are refused.

The API receives a fixed pointer containing checked mailbox identifiers and installation paths. Subject, body, context and response nonce stay in the mailbox. Before that pointer, creation sends the native `set_permission_mode` control event for Auto, reflecting the operator's explicit preference. No platform/source identity or tool-approval response is asserted. Desktop selects the actual working directory from its registered environment; its configured worktree policy still applies. Follow-ups retain the existing session's mode.

## Native conversation identity

First delivery creates a native Remote Control session and records its association with the mailbox thread. Follow-ups use the same remote session. Replies wake it only when its original ask requested `wake_on_reply`. FYI mail does not wake it.

An updated carrier-pigeon MCP server can use the durable address without shell commands. Before each recipient operation it verifies:

- its own native session UUID and parent PID;
- one live registry record with the Desktop entrypoint;
- the native host-session identity and Remote Control session ID;
- the exact environment/thread association in the mailbox.

The checks fail closed on missing, changing, ambiguous or unsafe metadata. A transient MCP label alone cannot claim another Desktop conversation's mail. The existing claim generation, cancellation, deadline and reply rules still apply. These are routing checks, not a new authority boundary between processes running as the same operating-system user.

Older MCP connections use CLI fallbacks under the recipient's existing permissions. In Manual mode that can require the user's approval. The companion never answers that prompt; Auto is requested when creating a new session, and follow-ups preserve its existing mode. Installing updated files does not update already running MCP processes; a newly created native session loads the updated server.

## Recovery and limits

Delivery records live in `host/claude-remote-deliveries/`; thread associations in `host/claude-remote-threads/`; process ownership in `host/claude-remote-owners/`. Ownership records include the process birth fingerprint so a reused PID cannot block startup. Unknown process identity fails closed; a live legacy PID record is replaced only when OS creation time proves PID reuse. A live companion advertises its stable address in `sessions/`.

Three submissions per environment per minute are allowed. Further requests remain deferred until the window clears. Threads stop automatic delivery after eight messages. Cancellation and execution deadlines prevent a new submission.

An API success produces `desktop-remote-submitted`, which means submission only. Inspect native Desktop admission/process evidence, then the mailbox's claim and reply receipts. A timeout, lost connection, malformed success response or server error can mean the request was accepted: it remains `uncertain` and is not automatically replayed. Inspect the native session before deliberately retrying. Explicit API rejection is recorded separately. The companion does not forcibly interrupt an already accepted native turn when a mailbox deadline expires; the receiver must check task controls before acting.

The Desktop app must remain open, its existing environment server must be reachable, and the network must work. Trusted-device and organization policy remain applicable. Installation, startup registration and changing the default Claude route are separate operator actions.

## Qualification

Offline fixtures cover HTTP framing, credential privacy, identity binding, real MCP stdio claim/reply, thread continuity, cancellation, deferred rates and uncertain delivery. They do not prove native wake.

On 2026-11-02, a Windows trial with Claude Desktop 4.4212 and its bundled Claude Code 2.1.309 initiated a real MCP mailbox send and observed Desktop admit new work and spawn its engine as a child of the existing Desktop application. The first trial used an older MCP connection and expired at a Manual-mode CLI-read prompt. After installing the native-bound MCP route, a fresh Desktop conversation completed MCP read, claim and reply with the exact mailbox nonce. A follow-up used the same remote and native conversation, returning the prior nonce with a new suffix without rereading the first ask.

After the operator selected Auto as the bridge default, another fresh handoff started with native `permissionMode: auto` and completed the MCP read/claim/reply round trip. Native process parentage, session metadata, transcripts and mailbox receipts were inspected independently of the peer's report. No GUI automation or manually opened recipient was used for these trials. This qualifies the tested Windows build and existing Remote Control environment, not every provider, policy or platform.

A later follow-up to a saved Auto conversation whose native engine had been released was submitted and admitted by Desktop, but Desktop reported a Remote Control connect timeout while reattaching. No mailbox claim or reply was observed at that check. Waking a released engine is not qualified by the successful fresh-session and live-follow-up trials. The adapter retains the accepted submission and does not replay it automatically.

Native resume links were also investigated. Navigation/import alone did not establish backend startup and is not used by this adapter.

Primary documentation: [Remote Control](https://code.claude.com/docs/en/remote-control), [Desktop session messaging](https://code.claude.com/docs/en/desktop#work-across-sessions), [per-session messaging controls](https://code.claude.com/docs/en/cross-session-messaging).
