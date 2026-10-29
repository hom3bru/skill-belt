# RE verification ladder and mechanisms

Use whenever a donor, a port, or a transfer plan makes a reverse-engineering, decompilation, recompilation, emulation, parser or "equivalent to the original" claim. Before assigning status, apply the [method contract](re-methods.md); it selects the required evidence for the claimed output, and hybrid projects get separate claims. The donor evidence, pins and per-donor legal postures behind each mechanism below are archived in `historical-findings.md` section E where an edition ships it (with the dated [2026-10-10 source review](re-source-review-2026-10-10.md)); they are history, not evidence about a new donor. Legal posture is a research flag, not legal advice ([legal](legal.md)).

## 1. Status ladder (aa.py `ledger.re_claims[].status`)
| Status | Meaning |
|---|---|
| `pass` | Declared claim checked by ≥1 assertion that can fail, plus ≥1 negative control that did fail when expected |
| `fail` | A check ran and refuted the claim |
| `mismatch` | Contract unresolved: a sub-check passed but another dimension diverged; scoped diagnostic, never promoted |
| `unknown` | Evidence missing, truncated or residual unknowns open; never "pass" |
| `unsupported` | Optional oracle not configured; recorded, not silent |
| `not-run` | Planned but not executed; prepared ≠ executed |

**Scope cannot be inflated.** `scope` is `unit`, `bounded` or `campaign`. A bounded run is never reported as a campaign pass; aa.py rejects `reported_as: campaign-pass` unless `scope: campaign`.

**`verified: true` needs ≥1 assertion and ≥1 negative control.** A verifier that prints `verified: true` with zero result assertions, or reports a count from a fabricated record, verifies nothing.

**Provenance on every RE claim:** `{tool, version, sha256 (64-hex of the tool executable or artifact), options, label}` with `label ∈ observed|derived|inferred`. Decompiler output is always `inferred`. Provider tags are provenance, not authority.

## 2. Mechanisms worth borrowing
Default legal posture: GREEN on own or synthetic fixtures; **methods-only** for commercial or unlicensed targets (borrow the method, never the target's assets or derived outputs); re-derive any donor's licence at its pin before copying code or text.
- **Behavioural roundtrip**: compile → decompile → recompile → run both; exit codes and stdout/stderr equal. A runner that only diffs text is not behavioural.
- **Committed residual snapshot**: known divergences recorded; any change, better or worse, fails; accept-modes that overwrite in place need diff review.
- **Multi-compiler matrix** as a differential; unsupported configurations stay visible as skipped.
- **Period-toolchain replay**: the original toolchain's object must reproduce a saved reference report; inputs re-hashed first; replay counted once.
- **Lockstep differential against the original** with an ordered event trace and first-divergence index.
- **Host/hardware oracle**: emulated operations bit-compared to the host over edge values (±0, denormals, NaN, ±inf); hardware rows pinned.
- **Independent byte-decode cross-check plus negative control** (a fixture that must yield nothing).
- **Decompiler output as labelled inference** with tool, version, executable hash, options and output hash; pseudocode marked non-source and non-compilable.
- **Typed error classification**, not message matching; exit codes untrusted without a marker.
- **Honest null/unknown labels**: keep the weaker label rather than invent a stronger one.
- **Corrupted-input rejection with unchanged input**: each malformed variant rejected with a specific typed error; input hash equal before and after.
- **Real resource-limit tests**: actual exhaustion under OS limits mapped to distinct categories.
- **Proof of passive analysis**: syscall tracing shows no ptrace/process-memory access, no network sockets and only allow-listed exec before reporting "executed: absent"; a label alone proves nothing.
- **Reviewed-dependency and reviewed-literal allowlists** on relocations.
- **Compile-time struct layout checks** against real SDK headers; two-compiler ABI agreement.
- **Tombstones and canaries**: freed blocks stay mapped; tail canaries checked after every call; reserved exit codes.
- **Read-only dynamic observation**: query/read access only, no writes, hooks or suspension; originals re-verified afterwards; never defeat platform protections.
- **Input freezing and re-hash around the run**; hashing then comparing with nothing in between is a tautology.
- **Exact expected-check list**: executed checks must equal the expected list; every tracked test discovered exactly once.
- **Negative controls on the oracle itself**: swap two IDs → the assertion must throw; each mutation of sealed evidence is rejected.
- **Container and surface equivalence**: the same artifact in different containers or through different interfaces yields identical results.
- **Byte-identical rebuild oracle** against hashes of the original, never the port's own past output; tree clean after.
- **Synthetic self-contained regression cases** with an intent comment and negative assertions.
- **Re-executed replay recomputes hashes**; typed-in "equal" hashes prove nothing.
- **Recompile-only is not verification**: require a behavioural or discriminating-input oracle.
- **Run counts on every RE pass**: `run_counts{total,skipped,failed}`; total 0 or unexplained skips cannot pass.
- **Mutate-then-verify** for every rename, retype or comment: before and after must differ.
- **Danger tiers as allowlists in every launch path**; an unknown config is never the most permissive.
- **Address-scoped commands / argv arrays**, never string-pasted addresses.
- **Generated RE subjects**: deterministic fixture writer with `--check`, independent re-parse and non-confusable exit codes.
- **Human boundary claims as checkable predictions**; exports attested against an independent parse with a fresh nonce.
- **Sandbox untrusted binaries; never run them on the host.**
- **Hypothesised names accepted only after re-hashing to the ID**; conservation over imports.
- **Find, then challenge with file:line**: a refute stage may drop a finding only with cited evidence of a real guard; a refute failure keeps all findings.
- **Earlier model output fed back only as escaped, delimited data.**
- **Locked-down reviewer environment**: read-only tools, repository settings not loaded, git hooks/pager/external diff neutralised, CLI resolved by absolute path.
- **Risk-ranked large diffs**: over-cap diffs prioritised by risk, never skipped.
- **Truncation is evidence**: mark it in the content, count truncated bytes, keep the omission as unknown/partial; an incomplete comparison is `unknown`, not `unchanged`.
- **Fail-closed review bookkeeping**: a diff failure ≠ an empty diff; never mark reviewed on failure.
- **Brute-force concrete oracle on small domains** against the abstract analysis; note when the oracle shares the implementation's behaviour.
- **Real calling-convention truth tables** with forward/backward tests on synthetic models.
- **Two-encoder round-trip** with must-throw negatives and an exact buffer boundary.
- **Planted secrets in every channel** and unchanged server hit counts across export/analysis.
- **Cleanup that cannot be confirmed is an error**; all cleanups run and the original error is kept.
- **Every case runs and prints before the assert**; failures carry phase and hash receipts.
- **A delivery limit must not lose evidence**: an oversize result fails with a retained-evidence reference.
- **Decoy-resistant detection**: an event needs two independent signals.

## 3. Runner anti-patterns (score as donor risk; see due-diligence.md)
Broken tests not counted or exit 0 on zero tests; no per-test timeout; bare `assert` without an `-O` guard; callbacks whose assertions cannot fail; a `pass` file written before shutdown checks; lineage checked only after a claim is already `verified`.

## 4. Required output per RE claim
`{id, claim, method, output, baseline, contribution, distribution, method_checks, status, scope, reported_as, provenance{tool,version,sha256,options,label}, assertions, negative_controls, verified, legal_posture}` — checked by `aa.py` (see records.md).
