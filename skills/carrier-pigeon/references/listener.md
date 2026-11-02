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
- `host/claude-settings.json` denies reads of:
  - `host/secrets/**`;
  - `~/.ssh`, `~/.aws` and `~/.config/gh`;
  - the Codex and Claude credential files;
  - `.env` files;
  - (since 0.8.2) `co/**`, the co-work store, which the listener's Claude reads only through `co_view`.

  How the host keeps the file current:
  - The host writes this file when it is missing.
  - It merges the deny list into a 0.3 settings file that has no `permissions` block.
  - It upgrades a file whose permissions are exactly an earlier host-written default.
  - It leaves any other `permissions` block, one you wrote or extended, alone.
  - The CLI applies the same list to its file flags, and the MCP `send` tool takes text only, never a file. So no mailbox route can carry one of those files either. Read refusal was seen in a real session (`tests/live/claude-deny.mjs`).
- **One session per conversation** (`claude.mode: "per-thread"`, the default).
  - Each mailbox thread is its own Claude session. Every later wake in that thread resumes it (`--resume <session>`), so the agent remembers the conversation and unrelated asks never share a context.
  - Wakes in one thread run one at a time; at most `claude.maxConcurrent` (2) run at once overall.
  - Session ids are kept in `host/claude-conversations.json`, so a listener restart keeps conversations.
  - A run that ends without a result is tried again, for at most 3 runs in all. A failed resume starts a fresh session.
- **`claude.mode: "shared"`** keeps the 0.5 behaviour: one warm session for everything, recycled once its context passes `claude.recycleAtContextTokens` (default 120000).
- **The listener's sessions are labelled `listener`.** Replies to its asks come back addressed to `listener` and wake it (with `wake_on_reply`). Mail addressed to any other session, such as an interactive Claude Code window, never wakes the listener; it only gets a toast. There are two exceptions:
  - Since 0.13.0, a Codex session in a Codex app thread the listener opened.
  - Since 0.14.0, an interactive Claude Code session, which hears about its own mail from its own MCP server (both below).

**Codex.** A local app-server on `ws://127.0.0.1:4500`: `turn/start` when idle, `turn/steer` when busy.
- Approvals are `never`, and the sandbox is workspace-write with the mailbox as the workspace. `tests/live/codex-sandbox.mjs` ran that sandbox profile: a write to a folder in the home directory was blocked, while the OS temp folder stays writable by design.
- **One Codex thread per conversation** (`codex.threads: "per-thread"`, the default).
  - Each mailbox thread runs in its own Codex thread on the app-server, with its own active turn, queue and memory-prefix state.
  - A follow-up lands in the thread that holds the earlier turns. `"shared"` keeps one thread.
  - `codex.maxThreads` (100) is an eviction target, not a hard cap: a new conversation is added first, then idle ones are evicted. Conversations with an active turn are never evicted, so the count can exceed 100 while that many turns are running.
- **Its own MCP server.** The listener's Codex gets this mailbox's own carrier-pigeon MCP server (`--as codex --session listener`) through launch overrides, whatever the user's Codex config registers. A registration that points at another install would otherwise reach older code.
- The override explicitly enables this server and sets its default tool approval mode to `approve`, so a disabled user registration or headless approval prompt cannot strand the worker. The overrides affect only this process.
- A native Codex fork is bound to the mailbox conversation; subsequent messages in that conversation reuse it. See [codex.md](codex.md) for recovery limits and manual-launch differences.
- Since 0.10.0, `host/codex-conversations.json` persists native mappings, prefix hashes and dispatch intents with client input ids. Restart and idle eviction resume recorded threads. Lost acknowledgements query native history; unavailable or incomplete evidence stays `recovery_needed`, and historical notified messages without a journal are not replayed automatically. See [reliable-tasks.md](reliable-tasks.md).
- Lean by default (`codex.lean: true`): plugins and apps are off, and every MCP server the user's config still enables is turned off by name (`-c mcp_servers.<name>.enabled=false`). 0.3.1 launched every one of them, including servers that failed auth on each start.
- If that MCP inventory fails, the Codex adapter stays down and logs `codex-lean-unavailable`; other adapters continue. Repair the inventory error and restart the listener. It does not launch a partially restricted profile.
- Lean mode does not shrink a wake much. One measured lean wake on 2026-10-30 read 153k input tokens (121k cached). 0.3.1's full-profile wakes read 109k to 448k. Most of a Codex wake is the provider's own base prompt, repeated across the turn's model calls.
- If the websocket can't connect, or drops later, the host kills the app-server so the supervisor restarts both, with backoff. 0.3.1 instead stayed "not ready" until the host itself was restarted.
- Every app-server call times out after `codex.rpcTimeoutMs` (default 60000), so a hung reply can't stall the host's scan loop.
- The MCP listing and the launch run in the background, so the other adapters and the first scan don't wait for Codex.
- The memory prefix counts as sent only after the turn is accepted. A failed delivery is retried with the prefix, not "unchanged".
- Point `codex.bin` in `host/config.json` at the Codex desktop app's own `codex.exe`; the npm copy may be too old for the models a ChatGPT login offers. Leave `codex.model` null to use its default.
- The user can watch with `codex --remote ws://127.0.0.1:4500`.

**Codex app (visible hand-offs and their follow-ups, 0.13.0).** On Windows, a `handoff` to Codex opens a new thread in the Codex desktop app (the program is `ChatGPT.exe`), and the rest of that conversation goes into the same thread.
- **Why:** the Codex window below starts a terminal session, and nothing can wake a terminal session. Every follow-up named the window's session and got `no-wake` (`session-addressed`), so each conversation stopped after its first message. It was reached only when the window happened to check its inbox mid-task.
- **How a hand-off starts:**
  1. A short-lived `codex app-server` with Matt's own Codex config starts the thread (`thread/start`) and names it `carrier-pigeon hand-off from <sender> (<id>)`. Naming writes the thread to disk without a model turn; a thread with no name and no turn isn't saved, and `codex queue` then fails with "no rollout found". The thread keeps the creating process's settings, so it runs with Matt's own approvals and sandbox, never the worker's mailbox-only profile.
  2. The fixed prompt goes on Codex's own durable queue: `codex queue --thread <id> --message <prompt>`.
  3. `explorer.exe codex://threads/<id>` opens the thread, and the app runs the queued prompt live.
- **Follow-ups** are queued into the same thread with `codex queue`. A message is a follow-up when it is to `codex` and either:
  - names a Codex session that has written from that thread; or
  - names no session but belongs to the same mailbox thread.

  The app runs queued messages for any thread it has loaded, even when that thread isn't on screen, so a follow-up doesn't take focus. Only when one hasn't started within `codexApp.pickupMs` (default 90 s) is the link opened again, once; after another wait the host raises an alert.
- **Waking:** a session-addressed message reaches the app only when `codexApp` owns that session.
  - `fyi` still never wakes.
  - A `reply` wakes the app session when it answers an ask that session sent with `wake_on_reply`.
  - Mail for a session the listener did not open (a terminal window, another client) is still `session-addressed`.
- **Records:** `host/codex-app.json` binds each mailbox thread to its app thread, the sessions seen there and the message ids already queued, so a retry never queues a message twice.
  - Receipts: `notified:codexApp` means the message is queued, and `app-turn-started` means the queued prompt appeared in the thread.
  - Unclaimed after `codexApp.claimTimeoutMs` (10 min): one alert.
- **The prompt** is a fixed template over plain ids, like the window's. The subject and body never reach a command line.
- **Config** (`codexApp` in `host/config.json`): `enabled`, `kinds` (default `["handoff"]`), `cwd` (default: the home folder), `bin` (default: `codex.bin`), `opener` (an argv prefix for the `codex://` link; needed off Windows), `pickupMs`, `pollMs`, `startTimeoutMs`, `claimTimeoutMs`. Add `codexApp` before `codexWindow` in `adapters` and in `routes.codex`; install keeps an existing config, so an older one needs this edit.
- **Live-tested on 2026-11-01** (Codex 0.166.0-alpha.5.1, app 26.1027):
  - The app ran queued messages for a thread it had just opened, for one already on screen, and for one off screen.
  - A named thread with no turns was filled from the queue.
  - A thread started without a name was not saved.
  - Probes: `tests/live/codex-app.mjs`.
  - Through the installed listener and the live mailbox:
    1. A Claude hand-off opened an app thread, and its first turn started 6 s after queueing.
    2. A follow-up addressed to the Codex session that replied ran as a second turn in the same thread, 2 s after queueing.
    3. Codex answered it with the earlier turn's nonce from memory.
    4. Both turns ran with Matt's own settings.
- **Follow-ups during a running turn (0.14.0).** The app runs a queued message only after the current turn ends. So when the thread's rollout says a turn is running, the follow-up waits on a pending list in `host/codex-app.json` instead, for carrier-pigeon's Codex hook (`bin/cp-hook.mjs`):
  - At the turn's next tool call, the `PostToolUse` hook hands the pointer over as `additionalContext`. At the turn's end, the `Stop` hook hands it over as `decision:block`, which Codex runs as a new prompt in the same turn.
  - If no hook takes it, because the hooks aren't installed or not yet trusted, it is queued when the turn ends, exactly as before.
  - A mark file in `host/codex-app-hooked/` decides who delivers. The hook and the listener each create it with `wx`, and only the one that creates it first delivers, so a turn ending mid-queue can't get it twice.
  - Receipts: `app-hooked` means the hook took it.
  - A turn is "running" when the rollout's last turn event is `task_started` or `turn_started`, rather than `task_complete`, `turn_complete` or `turn_aborted` (`turnRunning`; the rule follows reason-network's `src/codex.rs`, MIT OR Apache-2.0).
  - Install the hooks with `carrier-pigeon codex-hooks install` (also `status` and `remove`). It adds a `PostToolUse` and a `Stop` group to `~/.codex/hooks.json` (or `CODEX_HOME`), keeps every other tool's hooks, and backs the file up once as `hooks.json.before-carrier-pigeon`.
  - **Codex skips a new hook until it is trusted in `/hooks`.**
  - Codex runs the hook after every tool call in every session. So it reads one small file, prints nothing for a thread with nothing pending, never fails loudly, and exits within 8 s.
  - `codexApp.hooks: false` turns the waiting off.
  - **Live-tested 2026-11-01** in the Codex desktop app: a follow-up sent while a turn ran six slow steps reached the turn at its next tool call, as developer context marked as from a hook, and was answered 2.5 minutes before the turn ended. One sent while Codex was writing its final answer, with no tool call to follow, was handed over by the `Stop` hook as the turn tried to end, and answered in the same turn.
- **Cost of the hook.** Codex runs it after every tool call in every session. On this machine one no-mail run took a median 0.21 s, against 0.16 s for starting Node at all.
  - A shell check that would skip Node when nothing is pending was slower still: 0.36 s with `cmd.exe`, 1.6 s with PowerShell. So the hook stays as it is.
  - `carrier-pigeon codex-hooks remove` takes it out.
- **Fallback, live-tested 2026-11-01** (`tests/live/codex-app-fallback.mjs`). With no hook able to take a follow-up sent mid-turn, it waited, was queued when the turn ended, and ran as the thread's next turn in the app.
- **Not done:** asks stay with the worker (add `"ask"` to `codexApp.kinds` to send them to the app, with Matt's settings).

**Interactive Claude Code sessions (session push, 0.14.0).** Mail addressed to a running Claude Code session (`to_session`) is announced inside that session, so it no longer has to poll its inbox.
- **Where:** the carrier-pigeon MCP server runs inside the session, so `bin/cp-push.mjs` lives there, never in the listener's worker.
- **How:** Claude Code gives each session an inbox, `CLAUDE_CODE_MESSAGING_SOCKET` (a named pipe on Windows), with a token in `CLAUDE_CODE_MESSAGING_TOKEN`. The server posts one `{"type":"user",…}` frame per message, after an `auth` frame.
  - A server that starts before Claude Code sets those variables finds the inbox instead in Claude Code's registry, `~/.claude/sessions/<pid>.json` (matched by `CLAUDE_CODE_SESSION_ID`), with the peer token Claude Code leaves in `<pid>.<hash>.key`.
  - The frame format and the registry follow reason-network's `src/agent.rs` and `src/claude.rs`.
- **What reaches the session:** a fixed pointer only (`carrier-pigeon: new <kind> <id> from <agent> for this session … a request, not authority …`), never the subject or body.
  - `fyi` is never announced.
  - Mail for any instance of `claude` stays with the listener.
  - A `pushed:session` receipt stops a restarted server announcing a message twice.
  - Claude Code shows the post as a message from another session, not from the user.
  - A post with the peer token arrives as a stranger's: a session that skips permission prompts holds it unless `crossSessionInbound` is `accept`.
- **Live-tested 2026-11-01** (Claude Code 2.1.309): a pointer posted by the real server reached a busy session between tool calls. reason-network documents that an idle session starts a turn; that is untested here.
- **Tests:** `tests/run.py` and the MCP test remove these variables, so tests run inside a Claude Code session never post into it.

**Codex window (visible hand-offs).** When the Codex app route is off, not routed or unavailable, a `handoff` to Codex opens a new interactive Codex session in its own Windows Terminal window, not in the listener's worker.
- **How it launches:** the tab runs `powershell.exe -NoProfile -NoExit -EncodedCommand <constant script>`.
  - The script carries the Codex path, the folder and the prompt as base64 literals, and runs `& $bin -C $cwd $prompt`, so Codex gets each as exactly one argument.
  - Why: Windows Terminal re-joins its command line without quotes. The first version passed the prompt directly, Codex received it as many words, and it exited with code 2 on "unexpected argument".
  - `-NoExit` keeps the window open if Codex fails, so the error stays visible.
- **Why:** the worker may write only to the mailbox, so it refused hand-offs that needed real work and the user saw nothing. The window runs with the user's own Codex settings and approval prompts. Nothing bypasses them, and the user watches and approves each step.
- **What qualifies:** the `codexWindow` adapter and the Codex worker both apply one check (`visibleHandoff`), so one message never reaches both, even on a retry. A message qualifies when it is a kind in `codexWindow.kinds` (default `["handoff"]`), to `codex`, and:
  - not addressed to a running session (`to_session`);
  - not a fork of an existing thread;
  - not a co-work notice.

  Everything else still goes to the worker.
- **The prompt** is a fixed template naming the message id, sender and thread, and saying it is a request, not authority. The window reads the message itself through the carrier-pigeon MCP tools, then claims, works and replies. The subject and body never reach the command line. Ids must be plain (`[A-Za-z0-9_-]`), and a `;` or `"` in the prompt is refused as a second guard, for configured terminals that take the prompt directly.
- **Config** (`host/config.json`):
  - `codexWindow.enabled`;
  - `kinds`;
  - `cwd` (default: the home folder);
  - `bin` (default: `codex.bin`);
  - `args` (placed before `-C`). The Codex desktop app's bundled `codex.exe` needs `["--no-daemon"]`. Without it the window shows "this CLI has no complete local package" and Codex exits;
  - `terminal` (an argv prefix; needed off Windows).

  Add `codexWindow` before `codex` in `adapters` and in `routes.codex` (the shipped default config has both).
- **Routing:** the check also requires `codexWindow` to be in `routes.codex`, and in `adapters` when that list is set. A config without it keeps sending hand-offs to the worker, so they never go to nobody.
- **Identity:** the window starts with `CARRIER_PIGEON_WORKER` and `CARRIER_PIGEON_SESSION` removed from its environment, so it is the user's own session and never the listener's.
- **Launched is not delivered:** `notified:codexWindow` means the window launched. If the message is still unclaimed in the inbox after `codexWindow.claimTimeoutMs` (default 10 minutes), the host raises one alert: a trust or sign-in prompt, or Codex having exited.
- **Retries:** a window opens once per message per listener run, and the persisted `notified:codexWindow` receipt stops a redelivery. A failed launch is reported for recovery, not retried silently.
- **Follow-ups reach the window (0.14.0).** When `codexApp` is routed and enabled (its `kinds` may be empty, leaving hand-offs to the window), the window's launch is recorded in `host/codex-app.json`, with its thread still unknown.
  - The first follow-up finds the thread: a rollout written since the launch whose text names the hand-off (`findWindowThread`).
  - From then on the window is treated like an app thread: the hook mid-turn, Codex's queue when idle. An idle terminal session runs a message put on its queue: a probe answered one 10.6 s after queueing.
  - A window thread is never opened in the app, since the terminal may still hold it. A message it hasn't started within `pickupMs` raises an alert to check the window instead.
  - A window that never writes its thread is no longer looked for after a day.
  - **A new terminal window can take minutes to start.** Codex fetches its model list first, and on 2026-11-01 one fetch timed out and the retry came about 4.5 minutes later.
- **Not done yet:**
  - a per-message working folder;
  - attaching with `codex --remote` instead. That needs a controlled test of who receives approvals.
- **An interactive session can't be woken** unless something reaches it. There are three exceptions (above): a Codex app thread opened by the listener, a hand-off window whose thread was found, and an interactive Claude Code session, which gets a pointer from its own MCP server. Any other session must check its inbox while it works; `wait_reply` only waits for replies to its own asks.

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
  - A failed delivery is never retried twice at once, even when the adapter's ready signal and a rescan retry at the same moment. 0.4.0 could deliver it twice.
  - A Codex turn can end in error, for example from a provider refusal ("flagged for possible cybersecurity risk"). Then each unfinished ask it held gets a `turn-failed` receipt and an alert, whether it started the turn or was steered in.
    - Interrupted turns and dropped connections also report unfinished tracked asks through this failure path.
    - A co phase notice among them is delivered once more, since its work is safe to repeat.
    - Any other ask is only reported, because the agent may have half done it.
    - Before 0.9.1, such a notice was silently lost.
  - A steer failure falls back to starting a turn only after an observed completion. Transport and other server failures propagate while the turn remains active; an acknowledgement timeout can still be ambiguous and needs inspection before retrying work.
  - Adapter errors must identify a pre-dispatch/retry-safe failure for automatic retry. Other transport failures remain uncertain. Retry metadata (ids, routing, attempts and phase) is durable; dispatch is recorded before calling the adapter. The host reconstructs and revalidates original mail and refreshes signed authority before recovery.
  - Codex checks native client input ids before accepting a recovery decision. A confirmed failed/interrupted co notice may have one persisted retry generation with a distinct input id; ordinary asks and uncertain notices do not get this retry.
  - Actual worker events update heartbeat and renew a still-live claim lease without replacing manual progress. Expired/reclaimed generations do not revive through late events. Native completion without a mailbox answer becomes `missing_reply`.
  - Cancellation and explicit execution deadlines gate new dispatch and retries. For active Codex work, interruption requires every tracked task to be stopping and current native history to show no unknown user input. Missing history or externally steered input leaves the request pending. The native API cannot atomically prevent a new external steer racing the check.
- **Loop limits.**
  - `fyi` never auto-wakes. A `reply` auto-wakes only through `wake_on_reply`: the ask it answers set it, the asker is the recipient, and both are in the same thread. The hop and rate limits still apply.
  - A thread stops auto-waking after 8 messages (`maxHops`), and the user gets an alert. A co-work project's thread (`co-…`) carries every phase notice, so its limit is 60 (`coMaxHops`; see [co.md](co.md)).
  - Message ids are deduped across rescans and restarts.
- **Rate limit.** Each agent gets at most 6 auto-wakes per 10 minutes. An ask over the limit is deferred (receipt `no-wake` with reason `rate-limit`), not dropped.
  - Deferred asks are retried oldest first once the window frees (`rate-retry`).
  - The deferral survives a listener restart.
  - An ask that leaves the inbox in the meantime is dropped (`rate-retry-dropped`).
  - A delivery retried after an adapter error (above) is not checked against the window again; its successful wake still counts toward the next ones.
- **Stats.** Per-wake usage goes to `host/logs/usage.jsonl`.
  - Claude: stream-json `result.usage`, plus `context_tokens`.
  - Codex: `thread/tokenUsage/updated` deltas per turn. Steered asks are attributed to the turn they joined.
  - `carrier-pigeon stats` prints per-agent cached and total input and the hit rate. Hit rates are provider-reported; they are not proof of subscription savings.

## Running it

- **Start and stop.** `host/start-host.ps1 [-Background]` and `host/stop-host.ps1`. The stop script kills the child tree, including the Claude session and the Codex app-server. Only the user registers it to start at logon (`host/install-task.ps1`, if present).
- **Upgrade.** `install` replaces the code on disk. The running process keeps the old code until it is stopped and started again.
- **Files.** `host/state.json` holds the dedup set, pending receipts, rate windows, deferred asks, delivery phases and bounded co-retry records. It is rewritten only when state changes. Task controls and request journals live in `tasks/`; native Codex mappings/intents live in `host/codex-conversations.json`. Durable JSON writes use a synced temporary file and rename. Logs are in `host/logs/`: `host.jsonl`, `claude.jsonl`, `codex.log` and `usage.jsonl`.
- **Repeated warnings.** A Codex warning with the same text is logged once per listener run.
