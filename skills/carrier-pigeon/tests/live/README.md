# Live checks (opt-in)

`tests/run.py` never runs these. They use real binaries and, for two of them, real model calls. Every one works in a throwaway mailbox under the OS temp folder and never touches `~/.carrier-pigeon`. `e2e.mjs` also reports whether the live mailbox's `log.jsonl` changed during the run.

Binaries come from `~/.carrier-pigeon/host/config.json` when it exists, otherwise from `claude` and `codex` on PATH.

| Script | What it shows | Cost |
|---|---|---|
| `codex-sandbox.mjs` | Codex's workspace-write sandbox (`codex sandbox -P :workspace`, with the mailbox as the workspace) lets a write inside the mailbox through and blocks one into a fresh folder in the home directory. It also reports whether the OS temp folder is writable. | None (no model) |
| `toast.mjs [--show]` | PowerShell's parser finds only the expected commands in the toast script, and a hostile subject never appears in it. `--show` fires one real toast and checks it exits 0. | None (Windows only) |
| `claude-deny.mjs [--legacy]` | A real headless Claude, launched with the listener's arguments, can't read `host/secrets`. It can't do it with Read, or by sending the file with the mailbox CLI. An ordinary file stays readable. `--legacy` reruns the Read part with 0.3.1's settings as a negative control. | One Haiku session, about $0.003 |
| `mcp-claude.mjs` | A real Claude Code client with only the carrier-pigeon MCP server (no shell) reads and answers a seeded ask, then uses the blocking `ask` tool. The script plays "codex" and replies. | One Haiku session, about $0.003 |
| `conversation.mjs [--mode wake\|ask]` | A real multi-turn conversation between the listener's Claude (Haiku) and Codex. Grok asks Claude to get two answers from Codex; the second question ("add 100 to your previous answer") omits the number, so Codex must remember the conversation. In `wake` mode (the default) each answer has to wake Claude's resumed per-thread session. | 3 Haiku runs, 2 Codex turns |
| `co-research.mjs [--claude-model haiku]` | A real co-research project between the listener's Claude and Codex. The question is answerable from two files in the throwaway mailbox: the host code, and a docs copy with one planted mismatch (5 wakes per 10 minutes where the code says 6). The script is lead and judge. It rules "unresolved" on any defended dispute and writes a placeholder synthesis.<br>**Pass:**<br>- the project closes with a clean protocol check;<br>- each member adds cited claims and coverage, then challenges or passes;<br>- no member writes into the project thread;<br>- since 0.9.0, every member entry on disk stays sealed until one reveal, which opens them all with no failures.<br>Whether the mismatch surfaced is reported, not gated. | About 3 Haiku runs and 3 Codex turns |
| `co-modes.mjs --mode audit\|design\|build\|solo` | The other co modes, and a baseline. Every project mode gates on: closed, a clean protocol check, every real member doing its work, no member messages in the project thread.<br>`audit`: Claude and Codex audit a limiter with three planted defects; which ones the findings name is reported.<br>`design`: competing designs under three acceptance criteria, which the script rates untested.<br>`build`: real Codex builds a unit in its own git worktree, while the script plays Claude, cross-reviews, merges and rates criteria from the merged `node --test`.<br>`solo`: no project; Claude and Codex each answer the co-research question alone. | Per mode: about 3 Haiku runs and 1 to 3 Codex turns (`build`: Codex only) |
| `co-real.mjs setup\|listen\|codex\|report` | Every role is a real model, and the material is real: no scripted member, lead or judge, and no planted defects.<br>`setup --mode audit`: Claude and Codex audit carrier-pigeon's own sealed-round code at the version under test, with Codex as lead.<br>`setup --mode build`: two real builders in their own worktrees, Codex as lead.<br>Codex runs through `listen` (listener-woken members) or `codex` (a sandboxed write-capable session). The harness never launches Claude itself: Claude builders and the non-member judge (id `grok`, no grok runtime here) are the operator's Claude subagents, under that session's permission system.<br>`report` gates on:<br>- closed with a clean check;<br>- the lead's synthesis;<br>- a judge verdict on every defended dispute;<br>- no member message in the thread;<br>- audit: sealed until one clean reveal;<br>- build: C1 rated pass, and the merged tests pass when the harness reruns them. | Audit: listener Claude (Sonnet) and Codex, plus one subagent judge. Build: two Claude subagent rounds and 3 to 4 Codex sessions |
| `e2e.mjs` | The whole listener: install, real Claude (Haiku) and lean Codex on a spare port (default 4511). Each is woken with an ask that needs a read-only listing; the run checks the replies and the per-wake usage. | One Haiku wake and one Codex turn |

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
