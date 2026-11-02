# Live checks (opt-in)

`tests/run.py` never runs these. They use real binaries; some also make real model calls. They use isolated mailboxes without sending requests to the live mailbox. Most use the OS temp folder; native builds use an explicitly chosen trial directory so commits and receipts can be retained. Conversation checks also compare the live mailbox's log timestamp.

Most scripts read binaries from `~/.carrier-pigeon/host/config.json` when it exists, otherwise from PATH. The native-build launcher expects that existing configuration and retains the normal client authentication profile; it does not configure credentials or global settings.

**0.9.2 qualification:** this audit added authored CLI, MCP and fake app-server regressions for session ownership, typed handoffs, launch overrides and failed delivery. It did not rerun a real-model live check. The results below remain evidence for their labeled earlier versions; they do not qualify the new release's provider or sandbox behavior. See [the Codex audit](../../references/codex-audit.md).

The current lifecycle/recovery contract is in [reliable-tasks.md](../../references/reliable-tasks.md). Authored crash fixtures and provider trials are reported separately below.

| Script | What it shows | Cost |
|---|---|---|
| `automatic-build.mjs [--operator MAILBOX] [--out FILE]` | One request builds a real dependency-free task-reporting library and CLI through the durable controller. Native Codex plans, native Claude checks the plan, each authors/tests a disjoint unit, each independently reviews, genuine findings return to their owner, and the controller integrates/checks/applies with a protocol report. Independent fixed probes and original Git HEAD are checked after publication. | At least six configured native sessions; findings add repair and re-review sessions |
| `build-profile.mjs [--operator MAILBOX] [--out FILE]` | Separate opt-in Claude authentication/profile check for the current private hook override, read-only tools and dedicated worker MCP. Checks a fresh file marker; does not implement or integrate code. | One configured native Claude session |
| `native-build.mjs TRIAL claude\|codex\|grok ROLE PROMPT_FILE WORKTREE` | Explicitly authorised writable native sessions for co-build, separate from the read-only listener. `TRIAL/mailbox` must contain an installed mailbox; worktrees and prompts must stay inside that trial. Uses the normal Claude authentication profile, its own strict MCP connection and Codex workspace-write. The lead handles protected Git metadata. `grok` is the independent Claude judge's mailbox role. Runtime exit alone never proves task acceptance: check units, commits, peer receipts and the co report. | One configured native model session per call |
| `doctor-parity.mjs [--skill DIR] [--out FILE]` | Six independent CLI/real-stdio MCP parity and read-only cases against a disposable installed mailbox, including no initialization, stale presence timestamps and mismatched/malformed/missing installed versions. | None (no model) |
| `collaboration.mjs [--minutes 20] [--verify-fixes]` | Claude leads a real review of the installed task lifecycle, delegates an independent review to Codex, challenges its strongest conclusion in a second round, then returns a schema-validated synthesis with both peer ask/reply IDs. Gates on real messages, source hashes, two resumed Claude wakes and one native Codex conversation. `--verify-fixes` checks the two operator-reproduced crash-recovery fixes. No planted defects or scripted peer answers. Temporary mailbox and receipts are retained. | Three Claude runs and two Codex turns, using configured models |
| `codex-recovery.mjs [--keep]` | Two real Codex turns in a throwaway mailbox, with a full listener/app-server restart between them. Both replies must satisfy an object schema; arithmetic must be correct; the native conversation id must stay the same; the live mailbox must stay untouched. Uses the existing Codex login/default model, low effort and a six-minute deadline per request. | Two Codex turns |
| `codex-sandbox.mjs` | Codex's workspace-write sandbox (`codex sandbox -P :workspace`, with the mailbox as the workspace) lets a write inside the mailbox through and blocks one into a fresh folder in the home directory. It also reports whether the OS temp folder is writable. | None (no model) |
| `codex-app.mjs [--minutes 4]` | The `codexApp` mechanics against the real Codex and the real desktop app, with no mailbox.<br>1. A named thread with no turn is started with the user's own Codex config, and its rollout must exist.<br>2. One prompt is queued and the thread is opened with `codex://threads/<id>`; the app must run it.<br>3. A second prompt is queued with no link; the app must run that too.<br>Each prompt asks for a fresh nonce word, and the run reads the reply from the thread's rollout. | Two tiny Codex turns in the app (Windows only) |
| `codex-app-fallback.mjs [--minutes 6]` | The `codexApp` fallback, with no hook able to take a follow-up. A throwaway mailbox and its own listener run a real hand-off in the app; installed hooks read the live mailbox, so they find nothing for this thread. A follow-up sent mid-turn must wait, be queued when the turn ends, and run as the next turn. | About three Codex turns in the app (Windows only) |
| `codex-window-followup.mjs [--minutes 6]` | A follow-up reaches a hand-off window. A throwaway mailbox and its own listener (`codexWindow` for hand-offs, `codexApp` with no kinds) open a real terminal window. The window's thread must be found from its rollout, and a follow-up sent once it is idle must be queued into it and run by the window. Allow minutes: a new window can wait on Codex's model-list fetch. | Two Codex turns in one terminal window (Windows only) |
| `toast.mjs [--show]` | PowerShell's parser finds only the expected commands in the toast script, and a hostile subject never appears in it. `--show` fires one real toast and checks it exits 0. | None (Windows only) |
| `claude-deny.mjs [--legacy]` | A real headless Claude, launched with the listener's arguments, can't read `host/secrets`. It can't do it with Read, or by sending the file with the mailbox CLI. An ordinary file stays readable. `--legacy` reruns the Read part with 0.3.1's settings as a negative control. | One Haiku session, about $0.003 |
| `mcp-claude.mjs` | A real Claude Code client with only the carrier-pigeon MCP server (no shell) reads and answers a seeded ask, then uses the blocking `ask` tool. The script plays "codex" and replies. | One Haiku session, about $0.003 |
| `conversation.mjs [--mode wake\|ask]` | A real multi-turn conversation between the listener's Claude (Haiku) and Codex. Grok asks Claude to get two answers from Codex; the second question ("add 100 to your previous answer") omits the number, so Codex must remember the conversation. In `wake` mode (the default) each answer has to wake Claude's resumed per-thread session. | 3 Haiku runs, 2 Codex turns |
| `co-research.mjs [--claude-model haiku]` | A real co-research project between the listener's Claude and Codex. The question is answerable from two files in the throwaway mailbox: the host code, and a docs copy with one planted mismatch (5 wakes per 10 minutes where the code says 6). The script is lead and judge. It rules "unresolved" on any defended dispute and writes a placeholder synthesis.<br>**Pass:**<br>- the project closes with a clean protocol check;<br>- each member adds cited claims and coverage, then challenges or passes;<br>- no member writes into the project thread;<br>- since 0.9.0, every member entry on disk stays sealed until one reveal, which opens them all with no failures.<br>Whether the mismatch surfaced is reported, not gated. | About 3 Haiku runs and 3 Codex turns |
| `co-modes.mjs --mode audit\|design\|build\|solo` | The other co modes, and a baseline. Every project mode gates on: closed, a clean protocol check, every real member doing its work, no member messages in the project thread.<br>`audit`: Claude and Codex audit a limiter with three planted defects; which ones the findings name is reported.<br>`design`: competing designs under three acceptance criteria, which the script rates untested.<br>`build`: real Codex builds a unit in its own git worktree, while the script plays Claude, cross-reviews, merges and rates criteria from the merged `node --test`.<br>`solo`: no project; Claude and Codex each answer the co-research question alone. | Per mode: about 3 Haiku runs and 1 to 3 Codex turns (`build`: Codex only) |
| `co-real.mjs setup\|listen\|codex\|report` | Every role is a real model, and the material is real: no scripted member, lead or judge, and no planted defects.<br>`setup --mode audit`: Claude and Codex audit carrier-pigeon's own sealed-round code at the version under test, with Codex as lead.<br>`setup --mode build`: two real builders in their own worktrees, Codex as lead.<br>Codex runs through `listen` (listener-woken members) or `codex` (a sandboxed write-capable session). The harness never launches Claude itself: Claude builders and the non-member judge (id `grok`, no grok runtime here) are the operator's Claude subagents, under that session's permission system.<br>`report` gates on:<br>- closed with a clean check;<br>- the lead's synthesis;<br>- a judge verdict on every defended dispute;<br>- no member message in the thread;<br>- audit: sealed until one clean reveal;<br>- build: C1 rated pass, and the merged tests pass when the harness reruns them. | Audit: listener Claude (Sonnet) and Codex, plus one subagent judge. Build: two Claude subagent rounds and 3 to 4 Codex sessions |
| `e2e.mjs` | The whole listener: install, real Claude (Haiku) and lean Codex on a spare port (default 4511). Each is woken with an ask that needs a read-only listing; the run checks the replies and the per-wake usage. | One Haiku wake and one Codex turn |

## Delivery into running sessions on 2026-11-01 (one Windows machine, 0.14.0)

**Donor.** Read at reason-network `bcf045c` (MIT OR Apache-2.0); see `references/listener.md`.

**Claude Code session push**, on Claude Code 2.1.309:
1. A frame posted from the session's own shell into its `CLAUDE_CODE_MESSAGING_SOCKET`, with its own token, arrived mid-turn, between tool calls. Claude Code labelled it as another session's message, not the user's.
2. Then the real 0.14.0 MCP server ran with a throwaway mailbox and that session's variables. An ask addressed to its session produced exactly the fixed pointer in the conversation, with no subject or body. The receipt read `pushed:session` via `env`, and the server reported `session push on (env)`.
3. **An idle session starts a turn** (0.15.0):
   - The setup: the session's own MCP server predated 0.14, so the installed 0.15.0 server ran beside it, with that session's carrier-pigeon name and inbox variables.
   - With the session idle, Codex in the desktop app sent it an ask. The listener marked it `no-wake (session-addressed)`, the server posted the pointer (`pushed:session` via `env`), and one second later the session began a new turn from a `peer` entry.
   - The session answered the ask with its nonce.
4. Not tested: the registry fallback against a real session. It is covered by an authored fixture.

**Codex mid-turn delivery**, in the Codex desktop app (Codex 0.166.0-alpha.5.1, with the `PostToolUse` hook trusted in `/hooks`):
1. A Claude hand-off asked for six 12-second shell steps.
2. A follow-up sent after the second step started was held by the listener (`codex-app-deferred`), and 2 s later the hook took it (`app-hooked`).
3. The rollout shows the pointer at the next tool call as a developer message with `"hook":true`, mid-turn.
4. Codex read, claimed and answered the follow-up with its nonce within 20 s, then finished the remaining steps. The turn ended 2.5 minutes after the follow-up was answered.

This also shows that the desktop app runs trusted hooks.

**The `Stop` path**, once that hook was trusted:
1. A hand-off asked for an essay with no tools after reading the message.
2. The follow-up was sent after the turn had gone 6 s without a tool call, while Codex was writing. The listener held it, and 16 s later, as the turn tried to end, the hook took it.
3. The rollout shows it as a `HookPrompt` from `stop:…hooks.json`. Codex then read, claimed and answered the follow-up in the same turn.

An earlier attempt went through `PostToolUse` instead, because Codex was still making tool calls.

**The queue fallback** (`codex-app-fallback.mjs`): pass. The follow-up was deferred, no hook took it, it was queued when the first turn ended, and the app ran it as the next turn and answered with its nonce.

**Hand-off windows:**
- An idle Codex terminal session (`codex --no-daemon`) ran a message put on its queue 10.6 s later. This was a direct probe.
- `codex-window-followup.mjs` twice timed out waiting for a new window to start. Codex logs show the window held before its first frame: its model-list fetch timed out, and the retry came 4.5 minutes later. The window that did start wrote a rollout naming the hand-off, which is what the window lookup searches for.

**The hook's cost:** a median 0.21 s per no-mail run, against 0.16 s for starting Node. A `cmd.exe` or PowerShell flag check measured slower (0.36 s, 1.6 s), so none was added.

**Other hooks:** in that probe window, "Hook failed (exit 1)" came from the security-guidance plugin's hooks, which run `bash` and have no Windows command. carrier-pigeon's and impeccable's hooks exit 0 when run with their Windows command through either `cmd.exe` or PowerShell.

## Codex app route on 2026-11-01 (one Windows machine, 0.13.0)

**What 0.12.0 did.** Matt shared nine Codex threads that "never progressed past a single message", and their local rollouts and mailbox receipts were read.
- Hand-offs opened a terminal session. Every follow-up named that session and was marked `no-wake` (`session-addressed`).
- One grading hand-off read two follow-ups only because it happened to check its inbox mid-task.
- Six automated test threads did get a second turn, because their follow-ups named `codex` rather than a session.
- Four 10/29 pings sat in `recovery_needed`, and the listener added a receipt for each on every 15 s rescan: about 3,400 apiece.

**Native mechanisms probed** (Codex 0.166.0-alpha.5.1, app 26.1027):
- `codex queue` writes to Codex's shared queue. Nothing runs a queued message until an app-server loads the thread.
- When the app opened a thread with `codex://threads/<id>`, it ran the waiting message. It also ran a message queued while the thread was on screen, and one queued while another thread was on screen.
- A thread started over the app-server protocol with no turn is not saved; `codex queue` then reports "no rollout found". `thread/name/set` saves it, and the app then fills it from the queue.
- A thread keeps the settings of the process that created it. Here those were Matt's own: approval `never`, full access.

**`codex-app.mjs`:** pass. The first reply came 14 s after the link was opened; the second, queued with no link, came 6 s after queueing.

**Through the installed 0.13.0 listener and the live mailbox:**
1. A Claude hand-off opened a named app thread, and its first turn started 6 s after queueing. Codex claimed it and replied with the nonce, and the listener recorded its session.
2. A follow-up addressed to that session was queued into the same thread and started 2 s later.
3. Codex answered it with both nonces, recalling the first from the conversation rather than re-reading the mailbox.
4. Both turns ran with Matt's own settings.

**Limits:**
- This is one machine and one app version.
- A terminal window's session still can't be woken.
- Asks still go to the listener's worker unless `codexApp.kinds` includes `ask`.

## Automatic co-build on 2026-11-01 (one Windows machine, 0.12.0 development)

- **One automatic request completed:** native Codex planned; native Claude approved the plan; Codex authored the task-reporting library and 12 tests; Claude authored its CLI and 13 initial tests. The controller created dependency-ordered worktrees, verified actual sandboxed check receipts and committed both units without manual Git operations.
- **Genuine peer finding and automatic repair:** Codex found that valid multiline task titles broke the CLI's one-line-per-task output. The controller returned this to Claude, which escaped CR/LF in human output and added a regression while preserving exact JSON output. Its 14 CLI tests passed. Both agents independently checked/reviewed the resulting units again in round two.
- **Integration and application:** all 26 merged unit tests and independent fixed acceptance probes passed. The protocol report accepted all criteria with no disputes or forced phases. Integration commit `883493667cf1a7c910a836519515190f229fbad7` was applied as four new source/test files; the original source Git HEAD stayed at its initial commit. Nine real native jobs completed: planning, plan review, two authors, four cross-reviews and one fix. No operator phase advancement, fix prompt or integration commit was needed after the initial request.
- **Failures fixed during qualification:** the first attempt exposed a helper import incorrectly pointing inside the empty data-only mailbox. Runtime imports now resolve to the job's frozen engine. An unrelated inherited Claude startup hook later produced Windows fork errors; new jobs use a private `disableAllHooks` override while retaining normal authentication. A separate real current-runtime Claude probe passed in 16.2 seconds: authenticated, used `build_context`, read a fresh unknown file marker, returned valid structured output and left the repository unchanged.
- **Limits:** the main run used a frozen development engine; later cancellation, environment, stdin transport and scoped hook fixes have separate authored regression evidence, with the hook/authentication change also covered by the real profile probe. This qualifies one dependency-free local task on one Windows machine, not dependency installation, every operating system/provider, production deployment, arbitrary-project success or sandbox confidentiality. Source, jobs, receipts, conflict controls and qualification reports are retained privately by the operator.

## Real coding co-build on 2026-11-01 (one Windows machine, released as 0.11.0)

- **Actual product task:** add a read-only CLI `doctor`, share its diagnostics with the existing MCP tool, and preserve compatibility. Native Codex implemented the diagnostics module and tests (two files); native Claude implemented the CLI/MCP wiring, tests, runner registration and docs (seven files). Each used a separate Git worktree. Claude carried the unchanged, committed Codex dependency before implementing its unit.
- **Cross-review ran code:** Codex pinned Claude's commit and ran its CLI **39/39** and real-stdio MCP **18/18** checks, plus four scratch probes. Claude pinned Codex's commit and ran its **23/23** diagnostics checks. The peer worktrees stayed unchanged.
- **A review changed the code:** Claude raised a contract challenge against blanket reconnect advice, which was misleading for standalone CLI calls and newer source copies. Codex revised the advice and tests: immediate installed-CLI use, installation from the intended source, and MCP refresh only when applicable, without guessing version order. The original advice failed three regressions; the revised suite passed **24/24**. Claude reran those 24 tests and accepted the fix in a separate peer message before integration.
- **Integrated, then measured:** the lead merged the two final branches one at a time (integration `ba9ee1f`), verified both heads are ancestors and each authored range touches only its assigned files, and ran **241/241** integrated Carrier Pigeon tests across eight suites, zero failures/skips, in 86 seconds. Independent CLI/MCP parity passed all six cases on the merged tree and again on the release source. All **four acceptance criteria passed**; the co report is accepted, its protocol check is clean, and no phase was forced or challenge left unresolved. Adjudication was unnecessary because the author revised the challenged entry.
- **Build-environment failures were retained and fixed:** Codex's native sandbox protected the worktree Git index, even with an explicit writable root. The authorised lead reviewed and committed only the named Codex files; the builder sandbox stayed enabled. The collection verifier incorrectly scanned a worktree's root `.git` pointer as authored content; it now excludes that metadata while retaining private-file and nested-file rejection controls (67 collection tests pass). An over-minimized Claude launch skipped its authentication setup; the launcher now retains the normal profile and its authentication helper. The initial failures and uncommitted unit attempt remain in the local receipts.
- **Release checks:** all eight required collection checks completed and the release Carrier Pigeon suite passed **241/241**. One documented Windows symlink skip belongs to another skill. Native-launcher negative controls reject human identity, worktree escape and log-label traversal without starting a model. The installed CLI/MCP and listener readiness are checked after installation.
- **Scope:** real providers authored and cross-reviewed real product code. Diagnostic readiness is an observed local snapshot; `doctor` does not contact a provider to verify authentication or run a model. This run does not qualify an independent judge or sandbox confidentiality.

## Collaboration on 2026-11-01 (one Windows machine, 0.10.0–0.10.2)

- The first real task reviewed the actual lifecycle implementation, with no planted defects. Claude led, Codex supplied an independent review, Claude challenged its strongest finding, and Codex revised its severity rather than defending unsupported production impact. The structured synthesis arrived in **414 seconds**, after three Claude runs (two resumed) and two Codex turns in one native conversation. The live mailbox was unchanged.
- Both reviewers identified an interrupted reclaim that could split message/control claim generations. They correctly qualified their static evidence: public reply/heartbeat/done already fenced stale workers, and the native-event writer was initially outside their scope.
- The operator reproduced the missing production link: after final control publication failed, `Host.taskState` accepted a displaced generation's late event and changed the task to `missing_reply`. The new regression failed on 0.10.0. In 0.10.1, reclaim revokes the old control generation before publishing the new message, status exposes the authoritative token, and mailbox ownership checks consult the durable fence. Failures before message publication or final commit stay `recovery_needed`; deliberate retry recovers the task. The same native event is rejected on the fixed code.
- The 0.10.1 repeat completed in **395 seconds**, again with three Claude runs and two Codex turns, and included the native-event writer in scope. Codex identified a second issue: another `reply` before pending publication recovered could replace the already committed reply. Claude challenged its reachability and failure windows; the finding survived. The operator reproduced it with a failing regression. In 0.10.2, the retry finishes publication and returns the original id/result with `publication_recovered: true`. Regressions cover failure before reply publication, during thread indexing, before ask finalization, and after the ask moved to done but before clearing its prepared answer. Static model review is not a substitute for these failure-injection tests.
- The final 0.10.2 verification collaboration passed in **416 seconds**: three Claude runs (two resumed), two Codex turns in one native conversation, all peer ask/reply IDs validated, a structured synthesis, matching pinned source hashes and no live-mailbox changes. Claude challenged recovery after lease/deadline expiry, the repair guard and another session's recovery. Both reviewers found the two specified invariants intact. Their remaining notes were the two direct-test gaps subsequently covered above and the keep-open limitation now stated in the contract. This is one environment and a focused review, not a general proof of correctness.
- Final authored verification: **208/208** Carrier Pigeon tests with no skips, including 25 lifecycle fixtures. All eight required collection checks completed; one documented Windows symlink skip belongs to another skill. Expanded stale `done`/heartbeat and post-done reply-recovery cases also passed the lifecycle suite after the full run. Skill validation and diff whitespace checks passed.

## Results on 2026-11-01 (one Windows machine, 0.10.0)

- The first real recovery attempt used a three-minute deadline and failed before a reply: the Codex wake still prescribed CLI commands, the agent tried to discover new reply flags, and its shell-escaped result was invalid JSON. The deadline returned `expired` with task state `cancel_requested`, `terminal: false` and `execution_stopped: false`; it did not claim successful completion or undone effects.
- Normal and forked Codex wakes were changed to prescribe the connected MCP tools and typed result/evidence fields. The subsequent two-turn trial returned **391 then 491**, satisfied the structured reply contract, resumed the **same native conversation after restart**, and left the live mailbox untouched, in **93 seconds** overall.
- The aggressive 500 ms fixture rescan also exposed a spurious recovery alert while a dispatch was still active in the same process. This prompted an additional concurrency regression and process-local dispatch guard; provider acceptance still requires persisted reconciliation after an actual restart.
- The final repeat with that guard passed all gates in **57 seconds**: **391 then 491**, the same native conversation across restart, structured `completed` outcomes, **zero false recovery receipts**, and no live-mailbox changes.
- The first full authored run found a transient Windows `EPERM` while replacing a control record during concurrent wait/reply. Atomic replacement now retries the same staged bytes with a fixed bound; fault fixtures verify transient recovery and preservation of the last committed record on permanent denial. Successful-result schemas also allow truthful blocked/declined/partial replies without fabricated success fields.
- These results exercise one provider, model selection and Windows environment. They do not establish sandbox confidentiality, human signing, exactly-once effects or performance guarantees.
- Final authored verification: **206/206**, no skipped Carrier Pigeon tests (CLI 32, lifecycle 23, host 68, context 18, MCP 16, signing 7, co-work 42). The required collection verifier completed all eight checks; its one documented Windows symlink skip belongs to another skill. The required runner clears developer test filters before executing suites.

## Results on 2026-11-01 (one Windows machine, 0.9.1): every role real, real material

- **`co-real` audit of the sealed first round (0.9.0 code, `54ddb89`):** passed the protocol gate.
  - **Roles:** the members were the listener's Claude (Sonnet) and Codex; the lead was Codex; the judge was a separate Claude Sonnet under the `grok` id.
  - **Seal and reveal:** the project was itself sealed (13 entries opened at the reveal, none failed, no plaintext before it), and the check was clean.
  - **Findings (the lead's synthesis):** six defect classes survived, 2 high, 3 medium and 1 low.
    - A member could decrypt a peer's sealed work by naming the peer with `--as`, because the view opened "own" entries.
    - The CLI accepted `--_coEngine` and so bypassed the thread guard, and `reply` skipped the guard.
    - A crash during the reveal could wedge the project or half-reveal it.
    - An entry added during the reveal could stay sealed for good.
    - A failed reveal could not be retried.
    - A low metadata count leak.
  - **Reproductions:** Codex reproduced most of them in memory-only harnesses.
  - **Challenges:**
    - Codex overturned two of Claude's findings: a lead deviation never reaches members, and record relabelling was not reachable with the tools.
    - Claude argued Codex's thread-bypass finding down from high to medium.
    - The judge dismissed Claude's challenge to the low leak, citing `cp-co.mjs` line by line.
  - **All fixed in 0.9.1.** Each has a regression test named after its finding (`cp-co.test.mjs`, "audit E…").
  - **`co-real` build, two real builders:** passed.
    - **Builders:** Claude (a Sonnet subagent) built `formatList` with 10 tests, and Codex (`codex exec`, sandboxed) built `slugify` with 16. Each committed in its own worktree.
    - **Cross-review:** each reran the other's tests before passing.
      - Claude also checked 34 edge cases and 20,000 random strings against an independent reference.
      - It confirmed that 9 deliberately broken `slugify` variants all fail Codex's tests.
      - Neither found a defect, so no challenge was filed.
    - **Lead (Codex):** merged `co/claude`, then `co/codex`, one at a time. It rated C1 pass (`node --test` exit 0, 26 passed) and C2 pass (each branch touched only its own two files), with the commands as evidence, and wrote the synthesis.
    - **Harness rerun:** `node --test` on the merged branch, exit 0, 26 passed.
    - Codex used 750k, 430k, 295k and 469k input tokens across its four sessions.
  - **A second real finding:** OpenAI's filter ended Codex's listener turn mid-audit ("flagged for possible cybersecurity risk"), and the challenge notice steered into that turn was lost. 0.9.1 reports such asks and redelivers co notices once. Codex's challenge round then ran in a fresh sandboxed session, framed as the authorized review it was.

## Results on 2026-10-31 (one Windows machine, 0.9.0)

- **`co-research` with a sealed first round:** passed in 839 s.
  - Every member entry on disk stayed a sealed record while the first round was open, with no plaintext entries, and the single reveal opened all 18 and checked each against its commitment, with none failing.
  - Clean protocol check; no member wrote into the project thread.
  - Claude made 8 cited claims and Codex 12, each with coverage. Each challenged twice, Codex also passed once, and every challenge ended in a revision.
  - The planted docs/code mismatch surfaced in four challenge and response entries.
  - Claude (Haiku) $0.071 over 3 resumed runs; Codex one 571 s turn (1.35M input tokens).

## Results on 2026-10-31 (one Windows machine, 0.8.2)

- **`claude-deny`, now with a co-work canary:** passed.
  - A real headless Claude, launched with the listener's arguments, was denied both `host/secrets/probe.txt` and a planted co entry ("File is in a directory that is denied by your permission settings"). It read the ordinary file.
  - The `--legacy` negative control (no deny list) read both canaries, so the check detects the leak it guards against.
  - $0.004 + $0.003.
- **`co-modes --mode solo-audit` (baseline for co-audit):** each agent got the same limiter audit as one ordinary ask.
  - Claude (Haiku) named all three planted defects in 113 s for $0.0045.
  - Codex confirmed one contract defect (the off-by-one, with a Node reproduction) in 201 s with 327k input tokens. It mentioned the boundary but did not claim it.
  - The co-audit run named all three too, in 585 s with about 1.3M Codex tokens.
  - Across both baselines (research and audit), a single agent found the planted items faster and much more cheaply on tasks this small.
  - What co-work added was argument over the findings: reproductions run, severity calibrated, contract violations separated from policy observations, and claims re-checked against their sources.
  - This is two small tasks, one run each, not a matched-budget study. The measured case for co-work rests on its error-catching (run 1 of co-research found four real defects in this skill), not on raw detection.

## Results on 2026-10-31 (one Windows machine, 0.8.1)

- **`co-modes --mode audit`:** passed in 585 s, going through all five phases including adjudication.
  - Clean check; no member wrote into the project thread.
  - Claude made 6 findings and Codex 2, and each challenged three times. Codex reproduced findings by running assertions.
  - The surviving and disputed findings name all three planted defects: the inclusive boundary, the off-by-one and the missing eviction.
  - Codex defended its three challenged findings, and the script, as judge, ruled them unresolved.
  - Claude (Haiku) $0.019 over 2 runs; Codex 919k + 344k input tokens.
  - An earlier attempt's members did the work, but it stalled at adjudication because of a bug in this script's judge hook (a filter that referred to the loop variable before it existed). In that attempt Codex argued two of the planted defects down: the boundary only makes the guard stricter, and memory growth breaks no line-1 promise. Claude conceded both.
- **`co-modes --mode build`:** the co-build protocol ran end to end with a real Codex: closed, clean check, no member messages in the thread. Codex worked in its own git worktree, one `codex exec` session per phase:
  - **Independent:** implemented `slugify` with 12 tests, committed it and recorded the unit with its receipt (562 s, 1.24M input tokens).
  - **Challenge:** reran Claude's tests, wrote 27 extra cases of its own, then passed with that reason (262 s).
  - **Respond:** answered the script's test-gap challenge with a new test and commit, then re-recorded the unit with a fresh receipt of 13 passed (346 s).
  - **Integration:** the script's own merge failed. An octopus merge runs git's shell-script strategy, and Git-Bash's `sh` cannot fork on this machine (0xC0000142), so the script rated C1 fail. It now merges one branch at a time. Redone that way on the kept mailbox: `node --test` on the merged branch passed 15 of 15, and C2 (each branch changed only its own files) passed.
  - **A listener-woken Codex refuses to build, as designed.** In the first attempt the notice only woke Codex through the listener. Codex declined to write code, because an unsigned notice allows mailbox writes only. It filed a deviation saying so, quoting co-build's "does not grant permission to edit". That is why the check launches write-capable sessions instead.
- **`co-modes --mode design`:** passed in 667 s. Clean check; no member wrote into the project thread.
  - Claude proposed 6 entries and Codex 2; Codex challenged 4 times, Claude once, and every challenge landed.
  - Codex's failure-mode challenges found real gaps in Claude's token-budget design:
    - its check points missed `Host.retry()`, which dispatches straight to an adapter;
    - a completion-only usage log treats a crashed run as free.
  - One of Claude's proposals was overturned. The three criteria were rated untested by design (the script does not judge designs), so the report reads "NOT accepted".
  - Claude (Haiku) $0.195 over 3 runs. Codex used one 643 s turn (1.19M input tokens).
- **`co-modes --mode solo` (baseline for co-research):** Claude and Codex each answered the co-research question alone. Both named the planted mismatch (docs 5, code 6).
  - Claude: 143 s, $0.0125, 184k input tokens. Codex: 229 s, 677k input tokens.
  - Co-research run 2 found the same mismatch in 661 s, at $0.076 plus 1.55M Codex tokens.
  - On this small, single-fact task, one agent was faster and cheaper. Co-research's extra yield came in run 1: four real defects in the skill, found by cross-checking code against docs.
  - The solo runs came after those defects were fixed, so this is not a matched comparison of what each finds.
- **Parallel runs exhausted memory.** Running four live checks at once on this machine made Claude and Node exit with 0xC0000409, which here means commit-memory exhaustion (39 of 49 GB was committed even after they ended). The audit project stalled because its Claude never woke; the build run's process died. Run live checks one at a time.

## Results on 2026-10-31 (one Windows machine, 0.8.0)

- **`co-research`, run 1 (pre-release build):** passed the protocol gate in 612 s. The project closed and `co check` was clean.
  - Claude (docs) and Codex (code) added 7 and 14 claims, all cited, each with a coverage statement.
  - Codex made 3 challenges and Claude 1. All 4 ended in revisions; nothing was overturned or left disputed.
  - **Planted mismatch:** both members flagged it in challenges. Codex challenged Claude's docs-only "5 per 10 minutes"; Claude challenged Codex's "6" for omitting the docs comparison.
  - **Real defects in the skill:** the members found four, all since fixed:
    - the co-thread hop alert named `maxHops`;
    - `listener.md` said a reply never auto-wakes;
    - the 100-thread Codex cap is only an eviction target;
    - the citation parser rewrote `||` inside excerpts.
  - **Blind-phase leak:** Claude replied to every phase notice with a summary of its work. Codex read the thread during the blind phase and said so in its coverage statement.
  - Fix: notices refuse replies; the wake prompt for a notice no longer points at the thread or asks for a reply; and `thread` hides other members' messages until the blind phase ends.
- **`co-research`, run 2 (with those fixes):** passed in 661 s. Clean check; 9 + 10 claims; 3 challenges and 1 pass; every challenge ended in a revision.
  - No member wrote into the project thread, which is now part of the gate.
  - **Planted mismatch:** neither member challenged on it. Codex instead recorded it in its pass reason: the docs claim quotes the docs accurately, but the docs do not match the code.
  - Pass reasons were missing from the report, so the report now lists them.
  - Claude (Haiku) cost $0.076 over 3 resumed runs.
  - Codex handled all three notices in one 451 s turn (later notices were steered into it), using 1.55M input tokens.

## Results on 2026-10-31 (one Windows machine, 0.6.0)

- **`conversation --mode wake`:** "A=391 B=491", correct, in 363 s, all six messages in one thread.
  - Claude ran 3 times on one session; runs 2 and 3 resumed it, each woken by Codex's reply.
  - Codex ran both turns in one Codex thread and answered "add 100 to your previous answer" from memory.
  - Replies were addressed `listener` → `listener`; only the final reply to Grok did not wake anyone, as intended.
  - Cost: Claude (Haiku) $0.014 over 3 runs; Codex 200k + 147k input tokens.
- **`conversation --mode ask`** (on a pre-release build): also correct. Claude used the blocking `ask` tool and stayed in one run.
  - That run showed the listener's Codex picking up a user-registered carrier-pigeon MCP server that pointed at an older install.
  - The listener now always gives Codex its own mailbox's server.

## Results on 2026-10-30 (one Windows machine, 0.5.0)

- **`mcp-claude`:** a real Claude Code client used inbox, read, reply and ask through the MCP server alone. `ask` returned the reply within the same call.
- **`e2e --only claude`:**
  - Under 0.4.x the listener's Claude was woken but stalled: Claude Code 2.1.310 denied `claim` under the shell allow rule while allowing `read` and `reply`.
  - In 0.5.0 its mailbox is the MCP server and it has no shell: queued → notified → received → replied in 81 s.
- **`e2e`** (both agents, 0.5.0 host): Codex replied correctly.
- **`claude-deny`** on the 0.5.0 setup: Read of `host/secrets` was denied.

## Results on 2026-10-30 (one Windows machine, 0.4.x)

- **`codex-sandbox`:** the write inside the mailbox succeeded; the write to the home folder was blocked; the OS temp folder was writable, as workspace-write intends.
  - This tests the sandbox profile the listener's turns use, not the app-server turn path itself.
- **`claude-deny`:**
  - With 0.4 settings, Read of `host/secrets` was denied.
  - With 0.3.1 settings (`--legacy`), the secret was read.
  - With 0.4.1, the model also tried to send the file with the mailbox CLI, and the CLI refused it.
- **`e2e`:**
  - Both agents were woken and replied.
  - One lean Codex wake read 153k input tokens (121k cached), within 0.3.1's 109k–448k range, so lean mode showed no token saving.
  - Under 0.4.0's wake prompt Codex once declined a read-only ask.
  - Under 0.4.1, in one run, both agents listed the folder and answered correctly. Codex then read 178k input tokens.
  - That run's receipts showed a retried Codex ask delivered twice, now fixed: a race between the ready signal and the rescan.
