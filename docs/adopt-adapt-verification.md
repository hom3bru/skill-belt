# adopt-adapt r18: scoped verification

Published edition: `3.0.0-grok-draft.r18`, from canonical commit `4d3322dd52e6ff2057ac53e22b0267ac6f0a736e`. The tested canonical package remains unchanged. The public source additionally retains the concurrent base's anonymous owner labels in SKILL.md and the SELF profile, and its two structural ownership-privacy tests. The declared overlays, omissions and regenerated manifest then produce the public edition; proprietary terms are preserved. The skill retains DRAFT status and incomplete formal multi-host qualification.

## Citation defect and engineering checks

The old validator required an HTTP(S) URL even for an inspected local LICENSE. R18 also accepts captured source-evidence IDs from the current donor/recipient pair. Existing checks bind captures to bytes and revision; unread, wrong-owner, unknown, duplicate and mutated evidence fail. Both provided provenance forms must validate. Paths alone are insufficient. Citation representation does not grant permission or clear legal flags.

The canonical suite ran 353 tests: 352 passed and one Windows symlink test was skipped because symlink creation was unavailable. All 13 focused citation tests passed. The independent reviewer recorded 62/62 controlled observations, 13 new tests and 7 existing legal tests passing, including unchanged hard-line, patent, terms and waiver boundaries. Fifteen publication-recovery checks and frontmatter validation passed. Instruction budgets remain within their unchanged caps. These controls establish helper behavior, not legal conclusions or general model benefit.

The collection's required `python -B scripts/verify.py` checks this public edition's byte manifests, links, privacy patterns, rejection controls and toolkit suites. It reports the documented Windows symlink exception visibly; that skip does not count as passed. Raw private development and host-session logs are omitted from the public collection.

## CI follow-up

The original failures had two concrete causes: Carrier Pigeon co-skill metadata still declared `0.15.0` while the parent declared `0.15.1`, and Windows short-path aliases were compared using inconsistent canonicalization. Commit `7935abe` synchronizes the metadata and uses native path resolution for repository, run and existing-worktree roots. Its regressions cover short/long alias equivalence, resume behavior, subdirectory/containment/link rejection, UTF-8/binary publication and inherited environment isolation. The portable Git/fixture corrections remain intact; no assertion or test was weakened to obtain a pass.

PR #1 incorporates those fixes and the current six-toolkit base `8869d6759031850f6f3b73df0d659b4afc0daafc`. All five other toolkit trees are preserved exactly from that base. The focused repository suite passes all 20 tests. Full collection CI for integrated code `fa5b104df6b2100da27d276390138f0d3796a16e` passes on [Ubuntu and Windows](https://github.com/hom3bru/skill-belt/actions/runs/41554070430). The complete local verifier also passes all 11 stages with the documented Windows symlink exception: adopt-adapt collects 340 tests (339 passed, one skipped), and Carrier Pigeon passes all 330. The local command uses the documented `--timeout 1800` allowance for the busy Windows host; fixture assertions and per-test safeguards are unchanged. The original local timeout and failed hosted runs remain retained as historical evidence in the canonical research archive; they were not relabeled as passes. The pre-integration public adopt-adapt suite ran 339 tests, including one documented Windows skip. The build, 67 collection controls, 26 focused privacy/version/budget checks and manifest verification also passed before this follow-up.

## Initial native host results (2026-11-02)

An independent evaluator froze an authored Python donor, TypeScript recipient, local LICENSE, prompts and criteria before running native sessions. Positive prompts provided fixture paths and evaluation intent, without pasted skill instructions or a skill-file path. Source-only scope prohibited code execution, edits, network use and installation. Exact prompts, native traces, before/after hashes, failures and grading remain in the canonical research archive.

| Surface / condition | Observed result | Limit |
| --- | --- | --- |
| Claude Code 2.1.310, implicit | Native `Skill(adopt-adapt)` call and attached installed r18 body; exact body binding and unchanged installed hashes. Source-only scope, grounding and local-license checks passed. | One authored case; no broad trigger-accuracy or verdict-quality claim. |
| Claude Code 2.1.310, explicit `/adopt-adapt` | Completed grounded evaluation within read scope. Discovery was visible. | Loaded identity was not proven by the trace. An unsupported claim that independent re-expression created no material license obligation failed the legal-grounding criterion. This condition does not count as verified r18 activation. |
| Claude Code 2.1.310, negative | Answered `42`, with no tool call or skill attachment. | One arithmetic control. |
| Codex CLI 0.142.5 | Account rejected the default, configured and one live-enumerated model before a usable response; final explicit/negative attempts failed and the interrupted implicit attempt remained incomplete. | Native activation unverified. A model-list response did not establish inference access. No authentication or saved configuration was changed. |
| Cursor 3.27.12 | Standalone agent CLI unavailable. Existing GUI showed a usage cap, and unreliable project-picker input prevented a scoped test. | Native activation unverified; no installation or account-setting change was attempted. |
| Codex Desktop GUI | No fresh GUI activation test. | CLI evidence does not qualify this surface. |

Initial parallel Claude runs were interrupted during installed SessionStart-plugin MSYS fork failures. Three fresh sequential runs used the documented invocation-only `disableAllHooks` setting, retaining ordinary native skill discovery and existing authentication. These results qualify only that exact scoped invocation. No stored host setting changed. Interrupted and failed attempts were retained, not counted as passes. No donor or recipient program was executed.

In the initial study, the native implicit attachment matched that installed SKILL.md body (comparison removed YAML frontmatter and surrounding blank lines and normalized line endings; the native attachment did not include frontmatter); the full file SHA-256 recorded before and after was `262ff78f18bc35299c721a757a8a9c7ca41a94a8d1e9dff703779b47ddba8b40`.

## Native activation follow-up

Fresh project-local copies bind this follow-up to the exact public r18 package, without overwriting the newer global installation or concurrent canonical work. Full public `SKILL.md` SHA-256: `a7b12657d4e6b686cb7e8f9b3a8ca9c7285e618ce0a510eec0dc565613dbf351`; helper SHA-256: `1b7b5291df90046a5eea5840f6f724d183529350347d44b5d480c4320ad8b0b9`. Prompts, criteria and authored fixtures were frozen before inference. All 12 final identity/protocol/boundary checks pass; isolated fixture and loaded-package bytes are unchanged. No donor or recipient program was executed.

| Surface / condition | Follow-up evidence | Limit |
| --- | --- | --- |
| Codex bundled runtime `0.166.0-alpha.5.1`, native protocol explicit | Native skill discovery, structured skill selection, complete native attachment and successful full-file read bind r18. Activation, identity, source-only scope, grounding and local-license criteria A–E pass. | Native protocol surface, with ephemeral thread, read-only sandbox and network disabled for model tools; this is not a Desktop GUI test. |
| Same native protocol, implicit | Prompt contains no skill name/path or structured skill selection. Native discovery leads to a complete project skill read; A–E pass. | One authored fixture case. |
| Same native protocol, negative | Answers `42`, with no model tools, skill attachment or skill read; C/F pass. | Controller discovery/diagnostic actions are separate from model actions. |
| Claude Code `2.1.310`, implicit | Native Skill call, exact project body/path binding, grounded source/license review; A–E pass. | Scoped invocation uses read tools, project/local settings, plan mode and invocation-only hooks disabled. |
| Claude, explicitly named native Skill-tool invocation | Actual Skill call and full project attachment prove r18 activation/identity and source-only behavior; A/B/C pass. | D/E fail: the answer proposes a wrong final FIFO expected value and makes an unsupported categorical no-obligation license claim. Activation does not prove evaluation quality. |
| Claude, direct slash invocation | Native command metadata/discovery are visible, but the stream/debug evidence does not establish loaded path/body; A/B remain UNKNOWN. | Named-tool success does not qualify direct slash identity. Grounding/license failures in these runs are retained. |
| Claude negative | Answers `42`, with no tools or attachment; C/F pass. | One arithmetic control. |
| Codex standalone CLI text-marker path | Updated runtime can infer; source-read process policy still blocks the tested direct CLI route. | Explicit/implicit activation remain UNKNOWN for this route. Successful native protocol tests do not relabel these attempts. |
| Cursor GUI/isolated official CLI | GUI stopped after competing user-input/window-state errors. Official Windows CLI `2026.10.22-27dcf5f` runs and reports `Not logged in`. The user chose to leave Cursor unverified and merge when CI passes. | Zero model requests; all activation criteria UNKNOWN. No login, account, PATH or spending change was made. |
| Desktop GUI surfaces | No fresh completed activation case. | Native protocol/CLI evidence does not qualify a GUI. |

The npm Codex runtime `0.142.5` exposed stale model availability for the existing account. The desktop-bundled runtime advertises and successfully runs configured `gpt-6.1-sol`, fixing the inference prerequisite without authentication changes. The successful native protocol condition uses its documented default execution environment. Earlier quoted-key and empty-environment harness faults, direct CLI policy rejections and incomplete attempts are retained explicitly as their actual outcomes. An accepted selection alone was never counted as a load; successful cases have native attachment/read evidence and exact hashes.

The explicit Claude answer's proposed `a,b,c,a,d,a,b,c` sequence incorrectly suppresses the final `c`; FIFO eviction makes that last admission true. Its independent-reexpression statement does not establish that license obligations disappear. These are remaining output-quality failures, not silently repaired expected answers. The broader routing, repeated-host, planted-injection and comparative-effectiveness qualification remains incomplete, and the skill retains DRAFT status.

The [research thesis](adopt-adapt-thesis.md) remains separate from effectiveness evidence: the r17 baseline/candidate comparison tied at 6/6 cases and 53/54 points, so discovery superiority was not established.
