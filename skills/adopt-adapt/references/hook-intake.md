<!-- R5: new. Policy for any hook transplanted from a donor (Claude Code, Codex, Cursor, gstack-style). Modelled on Codex hook trust (openai/codex@07757f44) and gstack's mediated third-party hook (gstack@92cfd07a). Evidence notes: [build-time source, not shipped] process-read/group3.md P3.5, P4.A-P4.D, P5.7, P6.1. -->
# Hook intake policy

A donor hook is never "adopted as-is". A plan that transplants a hook must state each rule below as met, or the result is ADAPT-with-prerequisite. aa.py checks `ledger.hooks[]`.

| # | Rule | Evidence |
|---|---|---|
| H1 | **Trust by content hash — of the config entry AND every file it runs or loads.** Record `content_sha256` of event+matcher+command, plus `files[]` = sha256 of the hook script and every file it sources/imports; run only when all equal the approved values | Codex model: discovery.rs:84-115,660-720 (`current_hash` vs `trusted_hash`). **R5.2 correction:** Codex `hook_hash` covers only the config entry (event, matcher, command string, timeout, async, status message) — discovery.rs:768-794, called at :666 [re-opened]; the script the command points to is never read, so editing `hooks/x.sh` behind an approved command stays Trusted (group3 P7.4). adopt-adapt must go further than Codex here |
| H2 | **Any edit to the config entry or to any hashed file revokes approval** — only true when H1 hashes the files; Codex alone does not give this | aa.py: config mismatch → "hook edited: approval revoked"; file mismatch → "hook file … changed: approval revoked"; no files → rejected |
| H3 | **Project config cannot approve.** `approved_by ∈ user|session-flag` only | codex config_rules.rs `hook_states_from_stack` filters to User/SessionFlags; bypass only via per-run CLI `--dangerously-bypass-hook-trust` with warning (cli/src/main.rs:2032,3583; core/src/config/mod.rs:2696,3397) |
| H4 | **Strict output schema**: non-object/unknown fields/wrong types rejected; every block needs a non-empty reason; unsupported fields fail the run | codex output_parser.rs:345-358,365-367,381-414,441-507 |
| H5 | **Deny wins**, then most-specific allow, else no verdict | codex permission_request.rs:14-15,130-136,149-169 |
| H6 | **Visible log of every approval naming the hook** (`source=hook:<id>`), durable on disk | gap evidence: codex Allow leaves no entry (permission_request.rs:227-229), relabelled Config or None (approvals.rs:484-487; network_approval.rs:828-833), not persisted by default (log_db.rs:74). Do not log machine choices as `user_choice` (gstack KP11) |
| H7 | **Environment allowlist**, not full env or deny-list | gstack memorable-user-prompt-hook.ts allow-listed env (K9); REA MCP child gets PATH only (verify/electron/tool-contracts.mjs; verify-real-browser.mjs:402-406). Gap: codex passes full env minus 6 (P4.D) |
| H8 | **Fail toward asking, never fail open**: errors/ambiguity pass through to the user; guards fail closed | gstack question-preference-hook (K10); anti-pattern hookify (KP19) |
| H9 | **Bound everything**: stdin cap (1 MiB), bounded walk (bound hit = unscanned, not clean), output cap (8 KiB at UTF-8 boundary), one deadline under host kill, process-group kill on timeout | gstack K9; codex command_runner.rs ProcessTreeGuard (K15) |
| H10 | **Untrusted envelope**: only a string context field accepted from a vendor; decision/continue/systemMessage dropped; control chars stripped | gstack K9 |
| H11 | **Fail-closed egress receipt** (sha256 + bytes) before any data leaves; secret scan raw + decoded | gstack K9 (gap: MEDIUM secrets pass, no-policy-store skips veto, KP15) |
| H12 | **Parse-check before going live** with the shebang's interpreter; registration list equals checked list | gstack bin/gstack-hook-check:1-30 (K1); fix missing-hook `continue` (KP6) |
| H13 | **No auto-answer.** A hook may not answer the user's question; env-var auto-choose is INJECTION-RISK | gstack KP9/KP10 |
| H14 | **Stop hooks need a hard iteration cap > 0** | ralph-wiggum KP7 |
| H15 | **Abstain correctly** (empty stdout, exit 0; not `defer`) | gstack K11 (CC v2.1.89 `defer` semantics, #2035) |

| H16 | **Invalid matcher is an error, never match-all** | anti-pattern: Codex drops a bad matcher like `[` with no warning and the hook runs on every prompt (discovery.rs tests 1239-1276; :488) |
| H17 | **Quote substituted paths**; `${PLUGIN_ROOT}`-style values are shell-quoted before use | anti-pattern: Codex plain string replace, no quoting (discovery.rs:569-571; exploitability unverified) |
| H18 | **Broken hook config fails closed** (bad hooks.json/TOML, empty command → error, not warning) | anti-pattern: Codex warns only, except managed layers (discovery.rs:60-72,232,351-367,391-395,520-526) |
| H19 | **Managed/forced hooks are listed in the ledger with source and cannot be silently auto-trusted by allowlist name** | Codex managed + bundled-cleanup hooks always trusted and undisableable (discovery.rs:669-677,802-805,815-841) |
| H20 | **Durable per-session record of every hook run and decision** (adopt-adapt ledger, not host logs) | gap: Codex HookStarted/HookCompleted are transient, not in rollout files (rollout/src/policy.rs:160,213-214,224); SQLite log filter hard-coded, no override (log_db.rs:61-89; app-server/src/lib.rs:741-752); `codex exec` writes no SQLite log (exec/src/lib.rs:739) (group3 P7.4) |

Legal: Codex Apache-2.0 (design reuse GREEN; NOTICE presence **unverified**). gstack licence not re-checked in R5 (unverified) — ideas only until checked. Claude Code (hookify, security-guidance) is proprietary — ideas only (legal.md).
