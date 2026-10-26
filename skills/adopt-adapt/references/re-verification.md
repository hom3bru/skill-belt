<!-- R5: new. Distilled from [build-time source, not shipped] process-read/group1.md (Pass 2-RE, 3-RE, 4-RE), group2.md (RE pass), group3.md (P2-P6). Every rule cites donor file:line at the pin listed in group notes; "notes:" names the section that holds the read. Legal posture = research flag, not legal advice (see legal.md). -->
# RE verification ladder and mechanisms

Use whenever a donor, a port, or a transfer plan makes a reverse-engineering, decompilation, recompilation, emulation, parser or "equivalent to the original" claim. Pins: ILSpy `ad2cc622`, Ghidra `c7bc89dd`, REA (morluto/rea) `1b73b5ab`, dx-ball `b92677e`, th04 `12fc47d`, pret/pokered `af51989`, radare2-mcp `d48078b`, ida-pro-mcp `c133c38`, AnyPS5 `0df342c6`.

Before assigning status, apply the [method contract](re-methods.md). It selects the required evidence for the claimed output; hybrid projects get separate claims. The [2026-10-10 source review](re-source-review-2026-10-10.md) records refreshed pins without silently relabelling historical citations below.

## 1. Status ladder (aa.py `ledger.re_claims[].status`)
| Status | Meaning |
|---|---|
| `pass` | Declared claim checked by ≥1 assertion that can fail, plus ≥1 negative control that did fail when expected |
| `fail` | A check ran and refuted the claim |
| `mismatch` | Contract unresolved: a sub-check passed but another dimension diverged; scoped diagnostic, never promoted (dx-ball test_windows_terminal.py:133-148,182-191) |
| `unknown` | Evidence missing, truncated or residual unknowns open; never "pass" (REA src/domain/reconstructionVerification.ts:138-157; conformanceTrustGate.ts:92-115) |
| `unsupported` | Optional oracle not configured; recorded, not silent (REA scripts/verify/managed/completion-report.mjs; notes: group3 P4.E R-new8) |
| `not-run` | Planned but not executed; prepared ≠ executed (dx-ball test_allocator_frames.py:38-58,162) |

**Scope cannot be inflated.** `scope` is `unit`, `bounded` or `campaign`. A bounded run is never reported as a campaign pass (dx-ball test_windows_campaign.py:4-5,257-268,302-303; anti-pattern test_campaign_differential.py:186-195 exits 0 on `bounded-frame-budget`). aa.py rejects `reported_as: campaign-pass` unless `scope: campaign`.

**`verified: true` needs ≥1 assertion and ≥1 negative control** (anti-patterns: REA scripts/verify/javascript/runtime-observation.mjs and application-workflows.mjs print `verified: true` with zero result assertions, notes: group3 P4.E KP20; REA verify-managed-native-boundaries reports `verified:1` from a fabricated record, verify-package-managed.mjs:215-243, KP31).

**Provenance on every RE claim:** `{tool, version, sha256 (64-hex of the tool executable or artifact), options, label}` with `label ∈ observed|derived|inferred`. Decompiler output is always `inferred`, `canonical_observation:false` (REA scripts/verify/managed/oracles.mjs:233-256; verify-package-managed.mjs:113-120). Provider tags are provenance, not authority (claude-code plugins/security-guidance/hooks/_base.py:56-67 — idea only, see legal).

## 2. Mechanisms (each with legal posture)
Posture key: **GREEN** own/synthetic fixtures; **YELLOW** needs a condition; **methods-only** = borrow the method, never the target assets.

| # | Mechanism | Evidence | Legal posture |
|---|---|---|---|
| M1 | **Behavioral roundtrip**: compile → decompile → recompile → run both; both exit 0 and stdout/stderr equal | ILSpy Helpers/Tester.cs:1092-1132; CorrectnessTestRunner.cs:455-497; whole-project RoundtripAssembly.cs (notes: group3 P2.2 I1, P3.1 I9) | GREEN (MIT; self-written fixtures). Caveat: Ugly runner only diffs text despite docs (IP6) |
| M2 | **Committed residual snapshot**: known divergences in `*.residual.txt`; any change, better or worse, fails | ILSpy Tests/AGENTS.md:72-89 | GREEN. Accept-mode `ILSPY_ACCEPT_PDB_RESIDUAL=1` overwrites in place (:86) → require diff review |
| M3 | **Multi-compiler matrix** as a differential; unsupported configs stay visible as skipped | ILSpy Tests/AGENTS.md:5-21; CorrectnessTestRunner.cs:52-92; Tester.cs:218-221 | GREEN |
| M4 | **Period-compiler replay**: VC4 object loaded and must reproduce saved reference report; inputs re-hashed first; replay counted once | dx-ball test_raster_coff.py:113-146; test_rotation_coff.py:76-117 | methods-only (commercial EXE private, dx-ball notes Pass 4-RE B7-1) |
| M5 | **Lockstep differential vs original** with ordered event trace and first-divergence index | dx-ball tests/test_core_differential.py:89-92,221-250 (notes: group1 P2-RE #1) | methods-only; run only on owned/OSS targets without separate user authorization for a broader target |
| M6 | **Host/hardware oracle**: emulated float ops bit-compared to host FPU over ±0, denormals, NaN, ±inf cross product; hardware rows pinned | Ghidra testfloatemu.cc ASSERT_FLOAT_ENCODING (notes: group3 P3.2 G6, P4.C); AnyPS5 docs/dev/HW_ORACLE.md:1-9,37,76-82 | GREEN (host-dependent: x87 vs SSE) |
| M7 | **Independent byte-decode cross-check + negative control**: recovered jump table must match bytes decoded independently; a comparison-only fixture must yield no table | REA verify-real-ghidra-switch-assertions.mjs:11-18,59-67; 12-fault oracle mutation catalogue :187-365 | GREEN (repo-built fixtures, Ghidra Apache-2.0) |
| M8 | **Decompiler output as labelled inference** with tool, version, exe sha256, options, method token, signature/IL sha256; pseudocode `decompiler-generated-non-source`, `compilable:false` | REA scripts/verify/managed/oracles.mjs:233-256; verify-real-ghidra-assertions.mjs:131-145 | GREEN |
| M9 | **Typed error classification**, not message matching (ENOMEM text inside ENOENT ≠ allocation failure; exit codes untrusted without marker) | REA verify-binary-layout.mjs:76-116,1058-1123. Anti-patterns: dx-ball string "instruction limit reached" (test_effects_differential.py:250-254); REA prose-prefix oracle (switch-assertions.mjs:153-185) | GREEN |
| M10 | **Honest null/unknown labels**: keep weaker label rather than invent stronger; `nx_indicator null` not false; unverifiable location `unresolved` | REA verify-binary-layout.mjs:212-234,289-298; inspector/runtime-observation.mjs (P4.F R-new18) | GREEN |
| M11 | **Corrupted-input rejection with unchanged input**: ~30 malformed ELF/FAT64/core variants each rejected with a specific typed error; input sha256 equal before/after | REA verify-binary-layout.mjs:467-553,1012-1057; verify-real-hopper-fat.mjs:166-214; verify-recorded-crash.mjs:160-215 | GREEN |
| M12 | **Real resource-limit tests**: actual exhaustion under prlimit (AS 96 MiB, CPU 1 s, fsize) mapped to distinct categories | REA verify-binary-layout.mjs:843-1011; verify-evm-interface.mjs:313-450 | GREEN |
| M13 | **strace proof of passive analysis**: no ptrace/process_vm_*, no AF_INET sockets, execve allow-list; historical-PID sentinel must survive. Only then report `exec-syscalls-verified-absent` | REA scripts/verify/recorded-crash/trace.mjs; verify-recorded-crash.mjs:62-63,216-226; verify-evm-interface.mjs:451-520,554-559; verify-binary-layout.mjs:1128-1182,1226. Anti-pattern: label-only `apk_executed:false` (P4.F KP24), IDA "never executed" from digest only (verify-real-ida.mjs:225) | GREEN |
| M14 | **Reviewed-dependency + reviewed-literal allowlists** on relocations ("Unreviewed dependency"/"Unreviewed literal") | dx-ball test_rotation_coff.py:28-58; test_raster_coff.py:46-66; link-map closure test_windows_allocator.py:81-93 | methods-only |
| M15 | **Compile-time struct layout checks** against real SDK headers (negative-size array typedef) | dx-ball windows_core_abi.c:12-65; windows_directx_abi.c:12-55; two-compiler ABI agreement test_windows_abi.py:36-77 | GREEN as a method (SDK headers under their own licence) |
| M16 | **Tombstones + canaries**: freed blocks stay mapped; 16-byte tail canary checked after every call; 0xDD poison; reserved exit codes 254/255 | dx-ball test_sound_differential.py:4-6,84,225-227,257-289; test_entities_differential.py:345-356 | methods-only |
| M17 | **Read-only dynamic observation**: QUERY\|VM_READ only, no writes/hooks/suspension; LOAD_LIBRARY_AS_DATAFILE; originals re-verified in `finally` | dx-ball windows_state_reader.c:1-2,140; windows_resource_reader.c:1,89; test_windows_campaign.py:38-39,286-290,336-344 | lowest-risk dynamic posture; still methods-only for commercial targets; hardened-runtime refusal = do not defeat protections (REA verify-native-calls.mjs:211-262) |
| M18 | **Input freezing + re-hash around the run**: hash before imports, re-verify after; bind /proc/self/maps libs; fail on `(deleted)` | dx-ball test_allocator_terminal.py:61-90,232-235; test_termination_differential (notes Pass 3-RE #7). **Anti-pattern P4-16**: test_windows_gameover.py:195-200 hashes then compares with nothing in between (tautology); play/ddraw/runtime/storage/round/resources hash only at report time | GREEN |
| M19 | **Exact expected-check list**: executed `checks` must equal the expected 32-name list; vitest discovers every tracked test exactly once | REA verify-real-ghidra-switch-controls.mjs (P4.H R-new26); verify-test-discovery.mjs (R-new22); Ghidra exact min==max counts (619 assertions, P3.2 G7) | GREEN |
| M20 | **Negative controls on the oracle itself**: swap two transaction IDs → assertion must throw; re-linked build without resources must enumerate zero; evidence sealer rejects each mutation | REA scripts/lib/browser-network-e2e.mjs:80-99; dx-ball test_windows_resources.py:44-78; test_campaign_retention.py:90-99,232-334 | GREEN |
| M21 | **Container + surface equivalence**: same app as folder/ZIP/DMG gives identical anatomy; CLI and MCP results deep-equal | REA apple/macos-bundle.mjs, macho-occurrences.mjs (P4.F R-new12/13); verify-reconstruction-readiness.mjs:60-69 | GREEN |
| M22 | **Byte-identical rebuild oracle** vs hashes of the original, never the port's own past output; tree clean after | pret/pokered Makefile:96-97; roms.sha1:1-5; checkdiff.sh:4-8 | methods-only (commercial ROM; donor has no LICENSE) |
| M23 | **Synthetic self-contained regression cases** with intent comment and negative `max=0` assertions | Ghidra datatests (testfunction.cc restoreXml; concat.xml:3-6) | GREEN (Apache-2.0, synthetic bytes) |
| M24 | **Re-executed replay must recompute hashes** (fix for typed-in "equal" hashes) | th04 validate_tracking (P3-1, notes Pass 3-RE) | GREEN |

## 3. Runner anti-patterns (score as donor risk; see due-diligence.md)
Broken tests not counted / exit 0 on 0 tests (Ghidra testfunction.cc runTestFiles; test.cc:158-173 gatherDataTests); no per-test timeout (Ghidra GP5); bare `assert` without `-O` guard (dx-ball P3-4); unwrapped ctypes callbacks whose asserts cannot fail (dx-ball rotation_oracle.py:148-171, P4-3); `pass` file written before shutdown checks (dx-ball test_windows_round.py:152-160, P4-17); lineage checked only when already `verified` (REA verify-real-ghidra-switch.mjs:181-182, KP32).

## 4. Required output per RE claim
`{id, claim, method, output, baseline, contribution, distribution, method_checks, status, scope, reported_as, provenance{tool,version,sha256,options,label}, assertions, negative_controls, verified, legal_posture}` — checked by `aa.py` (see records.md).

## 5. R5.1 additions (ai-re-trend-2026.md, group1 Pass 3, group2 RE pass)
| # | Mechanism | Evidence | Legal posture |
|---|---|---|---|
| M25 | **Recompile-only is not verification**: recompilability can hide lost behaviour; require a behavioural or discriminating-input oracle (aa.py rejects `verified` with `oracle_kind` recompile-only/self-roundtrip) | Decompile-Diverge arXiv 2609.05370; CHISEL arXiv 2608.27981 (ai-re-trend-2026.md P02/P03); ILSpy IP6 | n/a |
| M26 | **Run counts on every RE pass**: `run_counts{total,skipped,failed}`; total 0 or unexplained skips cannot pass | ghidra-mcp tests.yml:129-171; AnyPS5 check_skips.py:34-44 | GREEN |
| M27 | **Mutate-then-verify** for every rename/retype/comment: before/after must differ | ida-pro-mcp api_composite.py:449-541 (group2 RE #3) | GREEN on operator-owned IDBs |
| M28 | **Danger tiers as allowlists in every launch path**; unknown config ≠ most permissive | radare2-mcp tools.c:283-320,1549-1581; ida-pro-mcp http.py:51-93 (GUI path enables unsafe) | GREEN |
| M29 | **Address-scoped commands** / argv arrays, never string-pasted addresses | radare2-mcp tools.c:848-895 | GREEN |
| M30 | **Generated RE subject** (deterministic PE writer, `--check`, independent re-parse, executable self-proof with non-confusable exit codes) | ghidra-mcp make_fixture.py:19-39,795-811; test_benchmark_fixture.py:115-372 | GREEN (Apache-2.0, generated) |
| M31 | **Human boundary claims as checkable predictions**; decompiler export attested against independent MZ parse with a fresh nonce | th04 test_function_review, test_ghidra (group1 Pass 3-RE #3-4) | methods-only (ZUN binaries) |
| M32 | **Sandbox untrusted binaries; never run them on the host** | Hex-Rays IDA MCP blog 2026-09-25 (ai-re-trend-2026.md T01) | n/a |
| M33 | **Hypothesised names accepted only after re-hashing to the ID; conservation over imports** | AnyPS5 import_audit.py:186-234 (group3 P2.3 A10/A11) | idea only (GPL-2.0; console HLE) |

## 6. R5.2 additions (process-read/group3.md P7.1-P7.4; pins as above, Claude Code @2301018b)
| # | Mechanism | Evidence | Legal posture |
|---|---|---|---|
| M34 | **Find, then challenge with file:line**: recall pass, optional "find something different" pass, then a refute stage that may drop a finding only with cited file:line evidence of a real guard; refute schema failure keeps all findings | claude-code llm.py:1295-1567 (refute 1455-1527, keep-all 1536-1538) | **Claude Code proprietary — idea only, RED to copy prompt/code text** |
| M35 | **Earlier model output fed back only as escaped, delimited data** ("data only" wrapper) | claude-code llm.py:1335-1361 | idea only (proprietary) |
| M36 | **Locked-down reviewer environment**: read-only tools; repo settings not loaded (`setting_sources=[]`); git config/external diff/pager/ssh/fsmonitor/hooksPath neutralised; `--no-ext-diff`; CLI resolved by absolute path, never PATH/cwd | claude-code llm.py:333,1029-1047,1161-1185,1216-1222; gitutil.py:25-29,203,414 | idea only (proprietary) |
| M37 | **Risk-ranked large diffs**: over-cap diffs prioritised by risk-path tokens, not skipped | claude-code gitutil.py:481-547 | idea only (proprietary) |
| M38 | **Truncation is evidence**: mark truncation inside the content, count truncated bytes, list truncated sections; downstream keeps the omission as unknown/partial; incomplete comparison = `unknown`, not `unchanged` | claude-code llm.py:158-183, review_api.py:31-64; REA scripts/lib/browser-capture-metadata-budget-e2e.mjs:160-208, browser-popup-e2e.mjs:216-226 | Claude Code idea only; REA GREEN (own fixtures) |
| M39 | **Fail-closed review bookkeeping**: diff failure ≠ empty diff; never mark reviewed on failure; restore consumed paths on transient failure | claude-code gitutil.py:193-210; diffstate.py:116-137 (anti-pattern P7-CC1 in the same plugin) | idea only |
| M40 | **Brute-force concrete oracle on small domains** vs the abstract analysis (enumerate every element, apply op, rebuild, compare incl. "not representable") | Ghidra unittests/testcirclerange.cc:158-374 (caveat: oracle shares the emulator's op behaviour, 228-279; both-unrepresentable compares nothing, 194-195) | GREEN (Apache-2.0; NOTICE for code) |
| M41 | **Real calling-convention truth tables** as compact signature→storage strings (SysV x86-64, Go, PPC64 BE, MIPS32 BE, AArch64) + forward/backward tests on synthetic models | Ghidra testparamstore.cc:81-121,219-410; testfuncproto.cc:77-190,278-680 | GREEN; ABI facts are functional |
| M42 | **Two-encoder round-trip with must-throw negatives and exact buffer boundary** | Ghidra testmarshal.cc:68-555 (gap: close-mismatch Packed only) | GREEN |
| M43 | **Planted secrets in every channel** (cookies, auth header, body, query, WebSocket, storage) + **no-refetch** server hit counts unchanged across export/analysis | REA fixtures/browser-verifier-site.mjs:131-194; browser-script-export-e2e.mjs:48-91 | GREEN own fixtures; YELLOW on third-party sites |
| M44 | **Cleanup that can't be confirmed is an error**; owned process-group teardown polled to empty; all cleanups run, original error kept | REA browser-runtime-termination-e2e.mjs:52-68; browser-runtime-fixture-lifecycle.mjs:74-153 (skipped on win32 :122) | GREEN |
| M45 | **Every case runs and prints before the assert**, failures carry phase + hash receipt | REA browser-nested-source-map-e2e.mjs:35-53,170-184 | GREEN |
| M46 | **Delivery limit must not lose evidence** (oversize result fails with a retained-evidence reference that exports byte-identical) | REA browser-screenshot-e2e.mjs:153-188 | GREEN |
| M47 | **Decoy-resistant detection**: an event needs two independent signals | claude-code security_reminder_hook.py:575-591,935-945 | idea only |
Unverified: REA verifyManagedNativeBoundaries.ts:79,103 optional-chained recorders may silently drop an Unknown; Ghidra `getModel` map operator[] (testparamstore.cc:71) may crash rather than fail.
