# Live checks (opt-in)

`tests/run.py` never runs these. They use real binaries and, for two of them, real model calls. Every one works in a throwaway mailbox under the OS temp folder and never touches `~/.carrier-pigeon`. `e2e.mjs` also reports whether the live mailbox's `log.jsonl` changed during the run.

Binaries come from `~/.carrier-pigeon/host/config.json` when it exists, otherwise from `claude` and `codex` on PATH.

| Script | What it shows | Cost |
|---|---|---|
| `codex-sandbox.mjs` | Codex's workspace-write sandbox (`codex sandbox -P :workspace`, with the mailbox as the workspace) lets a write inside the mailbox through and blocks one into a fresh folder in the home directory. It also reports whether the OS temp folder is writable. | None (no model) |
| `toast.mjs [--show]` | PowerShell's parser finds only the expected commands in the toast script, and a hostile subject never appears in it. `--show` fires one real toast and checks it exits 0. | None (Windows only) |
| `claude-deny.mjs [--legacy]` | A real headless Claude, launched with the listener's arguments, can't read `host/secrets`. It can't do it with Read, or by sending the file with the mailbox CLI. An ordinary file stays readable. `--legacy` reruns the Read part with 0.3.1's settings as a negative control. | One Haiku session, about $0.003 |
| `e2e.mjs` | The whole listener: install, real Claude (Haiku) and lean Codex on a spare port (default 4511). Each is woken with an ask that needs a read-only listing; the run checks the replies and the per-wake usage. | One Haiku wake and one Codex turn |

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
