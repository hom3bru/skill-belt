# Seams, closure and representation bridges

A seam is qualified only once its contract can be stated independently of the donor's folder layout.

**Views to collect:**
- syntax and type;
- import and call;
- control and data flow;
- build and config;
- persistence and state;
- test and workflow;
- runtime and co-change, when authorized.

Label each edge static, observed or inferred, and record its revision, the tool and version, and any missing edges. Link the seam to its evidence (`seam.evidence`). An `inspect-python` graph can support a source citation but cannot replace it.

**Inventory for each seam:**
- exports and consumers;
- closure dependencies;
- initialization order and registries;
- resources, callbacks and lifetime;
- shared state and transactions;
- concurrency, cancellation and retry;
- errors;
- serialization;
- security principal;
- permissions and effects;
- fixtures;
- per-part rights.

Keep alternative seam locations and their raw tradeoffs. A low graph cut is only a hint.

## Route decisions

Prefer an in-process modular monolith. Add a process, service, database or orchestration layer only for evidenced isolation, runtime or scaling needs.

| Route | When useful | Required extra contract |
| --- | --- | --- |
| dependency | Runtime and obligations fit the unchanged unit | Version, API, closure, update strategy |
| narrow-port | Small semantic core and a tractable closure | Per-part notices, semantic deltas, parity oracle |
| ffi | Native core with a justified in-process boundary | ABI/layout, ownership, threading, unwind and callbacks |
| process | Runtime isolation justifies the protocol overhead | Version rejection, identity, serialization, restart and backpressure (checked) |
| rpc | A remote boundary is justified | Process terms plus auth, deadlines, duplicates/reordering and side effects (checked) |
| wasm | Toolchain, platform and host capabilities fit | Bindings, resources, host grants, conversion and budgets |
| reimplementation | Behavior is understood and the rights route fits | `basis`: code (rewritten from the source) or idea; independent requirements and oracles; intentional deviations |
| pattern-only | A schema, test or operating lesson carries the gain | Provenance, adaptation assumptions, falsifier; no deltas |
| defer | Unknown semantics, rights or cost dominate | Exact blocker and reopening evidence |

The helper enforces the process and rpc protocol rows and, for every route, the rights that route needs. Review alone checks the other extra contracts.

**Rights by route.** Dependency, narrow-port, ffi, process, rpc, wasm and reimplementation from code keep donor code in the product: they need rights route licensed-reuse or permission, and source-available or proprietary code needs permission. Idea-only rights allow only pattern-only or reimplementation from the idea. On a code-keeping route, list each retained dependency as `{name, pin, category, disposition}` (retain, replace, bridge, exclude or unresolved), or write `none: <reason>`. A licence scanner's saved output (ScanCode, ORT, Syft) can be cited as `license-scan` evidence; it is detection, not a legal ruling.

## Semantic deltas

A delta is required when a reuse route moves behavior across a language boundary.

Cover all 13 dimensions:
- integer overflow and float;
- null, missing and defaults;
- Unicode and regex;
- equality and order;
- time, zones and units;
- errors;
- async and cancellation;
- ownership;
- memory and threads;
- persistence and transactions;
- ABI and layout;
- serialization;
- initialization.

Each delta states donor semantics, target semantics, its status (same, mapped, not-applicable or unknown), the conversion, a test and the reason. A not-applicable delta needs only its reason, written `n/a: <reason>`.

Prefer a reasoned not-applicable entry over fictional coverage, but check before dismissing a dimension. JavaScript `BigInt("")` is `0n` and Python `int("٣")` is 3: both are string-parsing deltas in an "arithmetic" unit. Same-language seams still need behavioral contracts.

**Process and RPC contracts** also cover:
- authentication;
- version negotiation and rejection;
- idempotency;
- reordered and duplicate messages;
- backpressure;
- shutdown and restart identity;
- performance.

Cancellation does not imply rollback.

## Implemented capability matrix

| Capability | v0.2 |
| --- | --- |
| Manual source-led discovery and new-product synthesis | Skill workflow; not agent-qualified |
| JSON contract/reference/rights/ownership checking | Implemented standard-library helper, including rights by route, retained dependencies and receipt-to-artifact hashes |
| Lite dossier checking | `check-lite`: pins, hashes, options, coverage, rights by route, oracle independence, review report; escalates to the full tier for cross-language code reuse, process/rpc, shared state across three parts or more than three donors; no deltas or protocols |
| Authoring aids | `stamp` (missing hashes into a new record or lite dossier), `scaffold` and `scaffold-lite` (blocking stubs), `review-packet` |
| Licence scanning | Not bundled; saved scanner output is accepted as `license-scan` evidence |
| Python AST import/call inventory | Static inventory with imported names; no import or execution; citable as `static-graph` |
| Complete Python closure or semantic slicing | Unavailable; inspect unresolved behavior manually |
| TS/JS graph or types | Manual; no bundled engine |
| Joern/CodeQL/tree-sitter/co-change adapters | Future candidates; not installed |
| Automatic translation, FFI/WASM generation | Unavailable |
| Runtime/semantic equivalence verification | Requires a user-authorized independent harness |

Keep unknown language support visible. An adapter that parses syntax has not qualified semantics.
