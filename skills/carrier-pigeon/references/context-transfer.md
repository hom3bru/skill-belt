# Cross-agent context transfer: details

Read this when you hand context to another agent beyond a short context pack, or when you need to say what a receipt shows.

Providers never share KV caches. So carrier-pigeon moves the context itself, as faithfully as each provider allows, and lets each provider's own prompt cache do the rest.

## The four fidelity levels

1. **Exact history (same provider).**
   - `send --to codex --fork-codex-thread <threadId>`: the listener calls the app-server's `thread/fork` and runs the ask on the fork. The fork carries the full history, encrypted reasoning included.
   - `send --to claude --fork-claude-session <uuid or .jsonl path>`: a one-shot `claude -p --resume … --fork-session`.
   - The CLI accepts only a Codex thread id, a Claude session UUID, or an existing `.jsonl` path (stored absolute). The listener refuses any value that starts with `-`, so a fork id can never become a command-line option.
2. **Byte-exact transcript (any provider).**
   - `transcript pack FILE --as A [--last N]` reads a Claude Code session `.jsonl` or a Codex rollout `.jsonl`. It writes `transcripts/<sha256>.jsonl` and `<sha256>.index.json`.
   - The `.jsonl` holds the raw records byte for byte: call ids, error flags, unknown fields, inline images, line endings.
   - The index holds ordered byte spans with a per-record sha256.
   - Reasoning and thinking records are always left out and listed in the index as omitted spans.
   - A slice containing a secret-looking string is refused, never edited.
   - `send … --transcript <sha256>`: the listener verifies every span and inlines the transcript as DATA ONLY, never as system or tool roles.
   - `--render` produces a lossy text view instead, with secrets redacted.
3. **Digest.** `memory digest PROJECT --as A --note/--body-file … --files p1,p2 [--sha X]` stores a reusable result of expensive work. It goes stale when a listed file's hash changes.
4. **Summary.** The context pack's `--summary`, for when the details don't matter.

**Measured on one Windows laptop on 2026-10-29 (PDT).** The test used 4 detail questions that only the sender's Codex session could answer.

| Handoff | Codex | Claude |
|---|---|---|
| Summary only | 1/4 (the one hit came from a digest) | 1/4 (the one hit came from a digest) |
| Transcript pack (the earlier lossy render) | 4/4 | 4/4 |
| Codex thread fork | 4/4 | not tested |

The byte-exact pack was unit-tested only, not run live.

**Native alternative, not used by the listener.** The Claude plugin `codex@openai-codex` has `/codex:transfer`, a Claude → Codex import. It is a continuation import, not byte-faithful: it truncates generic tool-result notes and omits some metadata. Run it only when the user says so.

## Cache-friendly wakes

Each wake turn starts with a byte-stable prefix (`prefix PROJECT` shows it): fixed rules, then `instructions.md`, then findings and digests oldest first. A new finding only appends.

- **Warm sessions get only what changed.**
  - When the prefix is unchanged, the session gets a one-line note.
  - When only findings were appended, the session gets just the new findings.
  - When the instructions change, the whole prefix is sent again.
  - A fresh or recycled session always gets the whole prefix.
- **The prefix is capped at 64 KB.** Findings past the cap are counted in one trailing line, not inlined. The part that is inlined stays byte-stable, and `memory read` shows the newest findings.
- The variable message always goes last. Don't inline big files.

## What receipts show

Receipts are evidence of delivery and use, never proof of understanding.

- **`transcript-submitted`** (written by the listener) records the sha256 and byte count of exactly what was handed to the session. That shows submission, not that every byte reached the model's active context.
- **`transcript read ID --for MSG`** records the sha256, byte count and truncation flag of what the read returned. That shows a read attempt and its result, not comprehension.
- **Canary lines.**
  - `transcript read` puts a per-record HMAC canary line (`<<cp-record N canary=cpk-…>>`) before each verbatim record. The key stays in `host/secrets/canary.key` and is never sent.
  - `transcript verify SHA --text-file REPLY [--for MSG]` lists which records' canaries came back.
  - That is **possession of the marker only**. It shows the responder had the string, not that it read, understood or used the record.
  - Any local process running as the same user can read the key, so a canary detects omission, not deliberate forgery.
- **`transcript pack … --repo DIR`** records the branch, HEAD, and the dirty and untracked paths at capture time, with sha256 for the files the pack references.
  - `read` re-hashes those files and reports which ones changed.
  - This covers capture time only; it doesn't show what the sender saw earlier.
  - If `git status` fails, the index says so and lists no files.
- **"No repeated command"** means only that the identical command wasn't logged. Equivalent commands can still repeat work, and revalidating can be correct.
- **Digests** hash the files at the moment they are recorded. A git SHA alone does not show which file contents were seen. Dirty or untracked files and concurrent edits are not captured unless they are listed with `--files`.
- **Fidelity A/B tests** should check three things:
  - Change a decisive fact: the answer must change.
  - Change irrelevant text: the answer must stay the same.
  - Remove necessary evidence: the receiver must say it doesn't know.
