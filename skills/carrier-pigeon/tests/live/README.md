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
| `co-research.mjs [--claude-model haiku]` | A real co-research project between the listener's Claude and Codex. The question is answerable from two files in the throwaway mailbox: the host code, and a docs copy with one planted mismatch (5 wakes per 10 minutes where the code says 6). The script is lead and judge. It rules "unresolved" on any defended dispute and writes a placeholder synthesis. Pass: the project closes with a clean protocol check, and each member adds cited claims and coverage, then challenges or passes. Whether the mismatch surfaced is reported, not gated. | About 3 Haiku runs and 3 Codex turns |
| `e2e.mjs` | The whole listener: install, real Claude (Haiku) and lean Codex on a spare port (default 4511). Each is woken with an ask that needs a read-only listing; the run checks the replies and the per-wake usage. | One Haiku wake and one Codex turn |

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
