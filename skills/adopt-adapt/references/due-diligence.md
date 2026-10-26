<!-- R2: new. Each check cites the public source verified 2026-10-09 (see [build-time source, not shipped] research.md verification log). -->
# Due-diligence block (repos and packages)

Pin everything to the commit SHA you read. Record the command or URL used for each line.

| Check | How (read-only, no install on the recipient machine) | What it does not prove |
|---|---|---|
| OpenSSF Scorecard | `https://api.securityscorecards.dev/projects/github.com/<o>/<r>`. Compare its `repo.commit` with your pinned SHA; if they differ, say so. | Code quality or fitness for the recipient |
| Vulnerabilities | `POST https://api.osv.dev/v1/query` with exact ecosystem/name/version. Check `MAL-` IDs separately. | Absence of unknown bugs |
| License | Read the LICENSE file at the SHA, and the header of every file you would salvage. GitHub "NOASSERTION" usually means several license blocks (feedparser: BSD-style code plus a separate docs license). No license is not permission. AGPL is not an automatic DISCARD, but whole-tool reuse needs the user's explicit decision. | Legal clearance |
| Maintenance | Last commit, last release, open-issue trend over 12 months (GitHub API). CHAOSS Contributor Absence Factor if bus-factor matters. | Future maintenance |
| Registry existence | For every package a plan names: `https://pypi.org/pypi/<name>/json` or `https://registry.npmjs.org/<name>`. 404 means the plan names a package that does not exist (slopsquatting guard; USENIX Sec '25 found 5.2% / 21.7% hallucinated package names). | That the package is safe |

<!-- R5: donor-risk audit. Each code is an aa.py `ledger.donor_risks[].code`; evidence cites donor file:line at the pins in re-verification.md / group notes. -->
## Donor-risk audit (R5; required for skill / hook / MCP / agent-config donors, recommended for all)
Record `ledger.donor_risks[] = {code, evidence, status: present|absent|unknown, scope}`. Any `present` risk on the salvaged mechanism forces ADAPT-with-prerequisite (fix named) or excludes that part; never ADOPT. Score penalty: one `present` high risk = −1 on the whole-tool score; two or more = −2 (single strongest penalty rule still applies).

For skill, hook, MCP, plugin and agent-config donors, put a compact **behavior inventory** in the existing `ledger.map.content`, with support in `map.evidence` and unread or dynamic paths in `map.limitations`. For each relevant entrypoint, connect its host and activation conditions to commands or delegation, file reads/writes and persistence, network destinations and data, consent/opt-out controls, and pinned source evidence. Distinguish automatic execution, agent instructions, optional actions and inert links. Follow load-bearing helpers, configuration and browser assets, including conditions that disable the behavior; source wiring is not observed execution. State coverage and unknowns rather than claiming every path was scanned. Include instruction size only when useful for assessing footprint. Concise prose or a table is enough; HTML and whole-repository inspection are not requirements. Reuse the existing risk rows without repeating their findings.

| Code | What to look for | Evidence (donor file:line) |
|---|---|---|
| FAIL-OPEN-GUARD | Guard/hook that lets everything through on error or broken state | hookify pretooluse/stop/userpromptsubmit.py exit 0 on any exception (group3 P4.B KP19); claude-code security_reminder_hook.py:306-308 rate limiter fails open, session_state.py:150-152 |
| RUNNER-MISCOUNT | Broken/crashing tests not counted; 0 tests → exit 0 | Ghidra testfunction.cc runTestFiles, test.cc:158-173, gatherDataTests (P2.1 GP1, P3.2 GP6) |
| NO-ASSERT-VERIFIED | "verify" prints `verified:true` with no result assertions | REA scripts/verify/javascript/runtime-observation.mjs, application-workflows.mjs (P4.E KP20) |
| SILENT-SKIP-PASS | Optional lane skipped silently, run still PASS | REA firmware `REA_FIRMWARE_VERIFY_EXT4` (P4.F KP25); verify-real-ghidra-nativeaot.mjs:322-346 (KP34); verify-windows-native.mjs:153-167,505-557 (KP43). Counter-example: verify-binary-layout.mjs:1224 reports `not-requested` |
| HARDCODED-CLAIM | Report counts/booleans are literals, not measured | REA conformance.mjs `verified: 11 + optional` (KP21); verify-package.mjs:136-170; verify-real-ghidra-windows.mjs:249-253 (KP33); dx-ball test_raster_differential.py:176 (P4-4) |
| HOOK-AUTO-ANSWER | Hook answers user questions; machine choices logged as the user's | gstack question-preference-hook.ts:506 env `OPENCLAW_SESSION`/`GSTACK_SESSION_KIND=spawned` auto-chooses every question, one-way doors only text-annotated (P4.A KP9); audit `user_choice: recommended` (:343; KP11). Corrected scope: stored-preference path is conservative (P4.A KP1 corrected) |
| HOOK-APPROVAL-UNLOGGED | Hook-granted approvals with no durable, attributed record | codex permission_request.rs:227-229 (Allow adds no output entry); approvals.rs:484-487,804-815 (source relabelled Config); network_approval.rs:828-833,857-862,1053-1058 (source None); log_db.rs:74, types.rs:679 (not persisted by default) (P5.7, P6.1) |
| ENV-LEAK | Full parent env (API keys) passed to hooks/child tools | codex hooks/src/registry.rs:79 + shell_environment.rs deny-list of 6 (P4.D, KP17 corrected); REA oracles.mjs `runIlspy` (KP23), verify-agent-experience.mjs:326 (KP37), browser-runtime-e2e.mjs:72-76 |
| UNPINNED-SESSION-INSTALL | Installs packages at session start without version/hash | claude-code ensure_agent_sdk.py:119-133 (P5-CC1); REA verify-package-update.mjs:59-64 proxies live registry |
| INSTRUCTION-TRUNCATION | Shared size budget cuts most specific file first, warn-only | codex agents_md.rs load order root→cwd, shared budget, `tracing::warn` (P4.B KP3 refined); claude-code extensibility.py:45,92-124 8 KiB (P5-CC3) |
| OVERRIDE-FILE | Override file silently replaces instructions | codex `AGENTS.override.md` first, one file per dir (agents_md.rs:44-45; P4.B). Note: project AGENTS.md not loaded for untrusted projects |
| COMMENT-SUPPRESSION | Repo-controlled text can suppress reviewer findings | **R5.2 correction:** in-code "why this is safe" comments do **not** suppress Claude Code findings — prompts say distrust them (llm.py:893 [re-opened]; review_api.py:109 [re-opened]); refute needs cited file:line (llm.py:1476-1482). README:108 contradicts the code (doc/behaviour mismatch, P7-CC9). Real channels: prior findings told "do NOT re-flag" for 3600 s (llm.py:767-782; diffstate.py:36); project/project-local guidance appended to every prompt (llm.py:962,1666; review_api.py:173); path filters never review node_modules/, dist/, vendor/, *.min.js, dotfiles (gitutil.py:472-479,550-584); re-added/re-indented lines treated as unchanged (gitutil.py:657-722) |
| CLIENT-CONFIG-WRITE | Donor writes itself into other AI clients' configs | REA setup → Claude Desktop/Codex/Cursor/Copilot configs (P4.G KP30). Mitigations seen: consent, dry-run, backups, byte-exact uninstall (verify-package-setup.mjs:71-688) |
| UNBOUNDED-STOP-HOOK | Stop hook can loop forever | ralph-wiggum stop-hook.sh `max_iterations: 0` "loop runs infinitely" (P3.5 KP7) |
| TAG-PINNED-ACTIONS | Workflow actions pinned to tags, not SHAs | ILSpy `codeql-action@v4.38.2`, `lock-threads@v6.0.2` (P3.1 IP12). Counter-example: gstack test-health.yml SHA-pinned (P4.A) |
| HAND-PATH-FILTERS | CI path filters maintained by hand, drift from import graph | REA real-*.yml 20-30 globs each (P3.3 RP11) |
| PUBLISH-NO-HASH | Publish/verify compares names, not tarball hash | REA verify-published-package.mjs (P3.4 RP12) |
| NO-TEST-TIMEOUT | No per-test timeout; a hang never fails | Ghidra testfunction.cc/test.cc (P3.2 GP5) |
| WARN-ONLY-LINT | Safety lint can only warn | claude-code hook-linter.sh:51-129 (P3.5 KP8) |
| MISSING-HOOK-PASSES | Hook checker `continue`s on a missing hook | gstack bin/gstack-hook-check (P3.5 KP6) |
| PERMISSIVE-DEFAULT | Unknown config value → most permissive | ida-pro-mcp http.py:89-90 CORS `*`; GUI path enables unsafe tools (group2 RE #2) |
| AUTO-EXEC | SessionStart/project hooks, project MCP, PATH/env-file writes run on open | UM hooks/add-to-path.sh:9, .claude/settings.json:3-9, .codex/config.toml:2-4 ([checker-honesty](checker-honesty.md) §D) |
| INSTRUCTION-TAMPER | Tool rewrites agent instruction files | REA AGENTS.md:115-124 |
| AGENT-ADDRESSED-TEXT | Donor text gives imperatives to agents | N64Recomp CONTRIBUTING.md; ghidra-mcp CLAUDE.md:11 |
| DONOR-STEERED-MAP | Donor steers the architecture map (`.devin/wiki.json`), or map is unpinned | missed-sources.md P2.6 |
| ERROR-BODY-SUCCESS | 200 / `is_error:false` counted as success | ghidra-mcp conformance/README.md:61-68; ghidra_server_health_check.py:686-694 |
| SELF-ATTESTED-EVIDENCE | Pass record writable by hand, no raw-output hash | ghidra-mcp release_evidence.py:172-197; th04 P3-1 |
| CONTINUE-ON-ERROR | `|| true` / continue-on-error / warn-and-ship on gating steps | radare2-mcp test2.sh:60, ci.yml:203-205; ghidra-mcp tests.yml:173-177 |
| UNRUN-SUITE | Tests built/committed but run by no runner | ida-pro-mcp idalib-tests.yml:50-53; dx-ball (group1 §2) |
| ABSENT-METRIC-PASS | Missing metric defaults to pass/1.0/0 | skill-evolver gate.py:266-267,295-296; photocraft scorecard.rs:542 |
| RATCHET-LOWERED | Floor/threshold lowered or only convention-enforced | photocraft parity.rs:93; ghidra-mcp tests.yml:247-248 |
| REVIEW-MARKED-ON-FAILURE | Work marked "reviewed/done" even when the review call failed | claude-code security_reminder_hook.py:1248-1265,1313-1316,1622-1623 (P7-CC1) |
| DROPPED-FILES-MARKED | File cap drops files but the range is still marked reviewed; top-N findings only | claude-code hook :1569-1576, :644, :1651-1655 (P7-CC2) |
| LAST-COMMIT-ONLY | Only the last of several commits is reviewed | claude-code hook :1050-1051 (P7-CC3) |
| BASE-URL-EXFIL | Env base-URL override sends diffs + API key/token to another host | claude-code llm.py:90-99,191-203,420-422; NO_PROXY rewrite :113-141 (P7-CC7; repo-settable unverified) |
| MATCHER-MATCH-ALL | Invalid matcher silently becomes match-all | codex discovery.rs tests 1239-1276, :488 (P7.4) |
| UNQUOTED-PATH-SUBST | Plugin path substituted into a shell command unquoted | codex discovery.rs:569-571 (exploitability unverified) |
| FORCED-MANAGED-HOOK | Hooks always trusted and undisableable (managed / allowlisted builtin) | codex discovery.rs:669-677,802-805,815-841 |
| HOOK-CONFIG-WARN-ONLY | Broken hook config only warns | codex discovery.rs:60-72,351-367,520-526 |
| HOOK-RUN-UNRECORDED | No lasting record of which hook ran or what it decided | codex rollout/src/policy.rs:160,213-214,224; log_db.rs:61-89; exec/src/lib.rs:739 |
| CONFIG-HASH-ONLY-TRUST | Hook trust hash covers config, not the script it runs | codex discovery.rs:768-794 [re-opened] |
