# Seams, closure and representation bridges

A candidate seam becomes qualified only after its contract can be stated independently of the donor's folder layout. Collect syntax/type, import/call, control/data, build/config, persistence/state, test/workflow and (when authorized) runtime/co-change views. Label each edge static, observed or inferred with revision, tool/version and missing edges.

Inventory exports/consumers, closure dependencies, initialization order and registries, resources/callbacks/lifetime, shared state/transactions, concurrency/cancellation/retry, errors, serialization, security principal, permissions/effects, fixtures and per-part rights. Preserve alternative seam locations and raw tradeoffs; a low graph cut is a hint.

## Route decisions

| Route | When useful | Required extra contract |
| --- | --- | --- |
| dependency | Runtime/obligations fit unchanged unit | Version, API, closure, update strategy |
| narrow-port | Small semantic core and tractable closure | Per-part notices, semantic deltas, parity oracle |
| ffi | Native core with justified in-process boundary | ABI/layout, ownership, threading, unwind and callbacks |
| process | Runtime isolation justifies protocol overhead | Version reject, identity, serialization, restart and backpressure |
| rpc | Remote boundary is justified | Process terms plus auth, deadlines, duplicates/reordering and side effects |
| wasm | Toolchain/platform/host capabilities fit | Bindings, resources, host grants, conversion and budgets |
| reimplementation | Understood behavior; chosen rights route fits | Independent requirements/oracles and intentional deviations |
| pattern-only | Schema/test/operating lesson carries the gain | Provenance, adaptation assumptions, falsifier |
| defer | Unknown semantics/rights/cost dominates | Exact blocker and reopening evidence |

Every cross-language contract covers integer overflow/float, null/missing/defaults, Unicode/regex, equality/order, time/zones/units, errors, async/cancellation, ownership, memory/threads, persistence/transactions, ABI/layout, serialization and initialization. Each typed delta states donor semantics, target semantics, same/mapped/not-applicable/unknown, conversion/deviation, test and reason. Reasoned not-applicable is preferable to fictional coverage. Same-language seams still require behavioral contracts.

Process/RPC contracts also cover authentication, version negotiation/rejection, idempotency, reordered/duplicate messages, backpressure, shutdown/restart identity and performance. Cancellation does not imply rollback of side effects.

## Implemented capability matrix

| Capability | v0.1 |
| --- | --- |
| Manual source-led discovery and new-product synthesis | Skill workflow; not agent-qualified |
| JSON contract/reference/rights/ownership checking | Implemented standard-library helper |
| Python AST import/call inventory | Implemented static inventory, no import execution |
| Complete Python closure or semantic slicing | Unavailable; manually inspect unresolved behavior |
| TS/JS graph or types | Manual; no bundled engine |
| Joern/CodeQL/tree-sitter/co-change adapters | Future candidates; not installed |
| Automatic translation, FFI/WASM generation | Unavailable |
| Runtime/semantic equivalence verification | User-authorized independent harness required |

Unknown language support remains visible. Do not imply that an adapter supporting syntax has qualified semantics.
