# Classify the reconstruction before judging its evidence

Use for reverse-engineering, reconstruction, recompilation, replacement-runtime or recovered-source port claims. This is an assessment contract; it does not authorize running donor code, decompiling a new target or distributing artifacts. Ordinary algorithm reuse does not require game-specific checks.

## Method and output

Each `ledger.re_claims[]` row names one `method`. A hybrid project has separate rows with unique IDs and separate evidence: success in one row cannot establish another. Use `other` with `method_reason` for emulation, parser analysis or a narrower investigation outside these five methods; do not force them into a game category.

| Method value | Output being assessed | Required `method_checks` and acceptance evidence |
|---|---|---|
| `matching-decompilation` | Source reproducing specified original machine code | `target_toolchain`: target revision/hash, architecture, compiler/linker versions and flags. `original_bytes`: exact comparison against original bytes, scope and denominator; distinguish functions/objects from a complete executable. `link_targets`: relocation normalization rules and resolved call/data destinations. |
| `functional-reconstruction` | Source reproducing specified behavior | `reference_behavior`: lawful reference executable, specification or independent oracle. `differential_cases`: identical input/state, ordered outputs/events and first divergence. `edge_cases`: invalid inputs, overflow, timing/state transitions and persistence relevant to the declared scope. Byte equality is not required. |
| `static-recompilation` | Translated instructions compiled for a different platform | `instruction_semantics`: ISA, arithmetic, endianness, branches/delay slots and indirect control flow. `runtime_dependencies`: imported calls, overlays, memory model, graphics/audio/input/timing services and explicit stubs. `platform_behavior`: reference comparison on the target host, including runtime integration. Compiling emitted C alone is insufficient. |
| `engine-reimplementation` | Replacement runtime consuming existing content | `content_compatibility`: identified content revision and format coverage. `runtime_behavior`: rendering, audio, input, timing and progression appropriate to the claim. `save_script_compatibility`: scripts, saves/reloads and exceptional states, including declared intentional incompatibilities. Keep engine code and required content separate. |
| `recovered-source-port` | Platform adaptation of an existing reconstruction | `recovered_baseline`: upstream source SHA, license, build and inherited completeness. `platform_semantics`: ABI/layout, pointer width, arithmetic, OS/API, rendering/audio and timing changes. `end_to_end_regression`: original-platform baseline versus target build, exercised through the real entrypoint and relevant persistence/progression paths. |
| `other` | Explicitly scoped RE result outside those five outputs | `scoped_acceptance`: discriminating evidence appropriate to `method_reason`; no claim of five-method coverage. |

Every check is `{status, evidence}`. Use the existing status ladder. For an irrelevant subsystem, explain why it is outside the declared claim and cite the inspected boundary; never silently omit it. Missing evidence stays `unknown`, `unsupported` or `not-run`. A partial investigation may use `other` to report its narrow result, but must not relabel a failed full reconstruction claim to make it pass.

## Artifact lineage and separate results

Every row also records:

- `output`: exactly what was produced or proposed, identified by revision/hash when available. Distinguish handwritten source, generated C, assembly, interpreter fallback and replacement routines.
- `baseline`: original input identity and, when relevant, recovered-source ancestor; unknown identities remain explicit and prevent equivalence claims.
- `contribution`: inherited tools, maps, templates, runtime and human work versus this project's change. Do not credit an entire port to the latest agent.
- `distribution`: actual/proposed package contents and rights status for tools, recovered/translated code, runtime, binaries and assets separately. Link the legal ledger. Tool licensing and user-supplied content do not establish permission for every output.

Report **matching**, **behavior**, **readability/maintainability**, and **portability/integration** separately, with evidence or `not assessed`. Do not collapse them into a completion score. If reporting progress, add `{numerator, denominator, unit, basis, exclusions[]}` to that claim. Name assembly/stub/fallback exclusions and the revision used to count; a passing bounded check does not increase a whole-project completion percentage by itself.

Matching claims require an `exact` original-byte oracle. The other four methods require a behavioral oracle (`exact` observable-output comparison, `behavioral`, `differential`, `hardware`, `tolerance`, `statistical` or `cross-impl`), appropriate to the declared observable and scope; independent byte decoding alone is insufficient. Passing claims require actual run counts, at least one executed check, a negative control and every required method check marked pass. A build-only, fallback or self-roundtrip oracle cannot establish a pass. Keep intentional improvements separate from fidelity results; donor parity can reproduce donor bugs.

Select observable contracts before collecting results. Separate structural claims from behavioral claims; a matching symbol/AST/output-text structure cannot stand in for runtime behavior. For concurrent programs, compare required causal/partial order rather than demanding an accidental total event order. Record tick scheduling, float precision, aliasing, error continuation/rollback and resource limits when relevant. Keep incomplete or truncated captures unknown even when one observed dimension clearly differs. Count implemented, throwing-stub, ignored and absent functions separately; exercise unsupported paths instead of treating symbol presence or successful loading as implementation.

The helper checks schema, count consistency and incompatible claims; evidence strings still need human/agent review against pinned sources and retained outputs. It cannot authenticate execution receipts, tie reported assertions to actual runs, or prove that hybrid rows use independent evidence. A report can be well formed and false. During plans-only evaluation, report checks as `not-run` or attribute a donor's reported results; do not present source inspection as a local test run.

## Minimal example (proposed, not executed)

```json
{
  "id": "port-1",
  "claim": "Proposed port of the existing recovered runtime",
  "method": "recovered-source-port",
  "output": "Proposed target-host source/build; no artifact yet",
  "baseline": "Record upstream source SHA and original target revision before work",
  "contribution": "Port OS/audio adapters; inherit recovered gameplay code",
  "distribution": "Plan only; assess source, runtime and content rights in legal ledger",
  "status": "not-run",
  "scope": "bounded",
  "verified": false,
  "assertions": 0,
  "negative_controls": 0,
  "legal_posture": "UNKNOWN pending artifact-specific review",
  "provenance": {"tool": "source-review", "version": "record reviewer version", "sha256": "0000000000000000000000000000000000000000000000000000000000000000", "options": "example only; replace hash with inspected artifact hash", "label": "inferred"},
  "method_checks": {
    "recovered_baseline": {"status": "not-run", "evidence": "Pin upstream and establish baseline build"},
    "platform_semantics": {"status": "not-run", "evidence": "Compare pointer/layout and timing assumptions"},
    "end_to_end_regression": {"status": "not-run", "evidence": "Exercise entrypoint, save/reload and progression on both targets"}
  }
}
```

## Sources and limits

The five-way distinction was supplied by the skill owner and compared with [Kingy AI, 2026-10-03](https://kingy.ai/blog/ai-video-game-decompilation-legality/). Primary anchors include [N64Recomp](https://github.com/N64Recomp/N64Recomp), [OpenMW FAQ](https://openmw.org/faq/), and the original-byte/behavioral mechanisms M1, M5 and M22 in [re-verification](re-verification.md). The acceptance contracts above are this skill's engineering requirements, not claims that every source implements them. See [the pinned re-audit](re-source-review-2026-10-10.md) for refreshed source evidence and limits.
