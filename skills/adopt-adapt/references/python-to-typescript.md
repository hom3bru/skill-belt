# Python → TypeScript: preserve the contract, choose the boundary

Read for a concrete Python mechanism proposed for a TypeScript/JavaScript target. This is a planning checklist, not authorization to install Python, add a service or execute donor code.

## Choose an implementation strategy from the actual closure

1. Prefer an equivalent existing target primitive when it meets the behavior and maintenance need.
2. A small pure algorithm may be directly reimplemented in TypeScript after its dependency closure and contract are understood.
3. A complex native/scientific/model-backed Python stack may be cheaper to keep behind an already-authorized local process/service boundary. Account for packaging, lifecycle, serialization, failures, resource limits and operations. A new bridge is not automatically cheaper or permitted.
4. A zero-cost idea or fixture can be salvaged without adopting either runtime. If none of the strategies earns its complexity, discard or defer.

Never rewrite by syntax substitution alone. Read the consuming Python call sites, explicit and implicit defaults, relevant dependency versions, tests and failure behavior. TypeScript type declarations disappear at runtime; validate the external boundary where the target already does so.

## Semantic traps to check when applicable

| Boundary | Contract to specify/test |
|---|---|
| Integers and floating point | Python's arbitrary-precision integers versus JS Number's safe-integer range; BigInt representation and JSON restrictions; decimal/money policy; overflow, infinities, NaN, signed zero, rounding and tolerance. Do not silently serialize a large integer through Number. |
| Division/modulo/rounding | `/`, floor division, truncation and remainder differ, especially for negative operands and half-way rounding. State the required rule and test signs and ties. |
| Missing/null/truthiness | None, absent key, null, undefined, empty collection, zero, false and empty string are distinct where the contract says so. Python empty containers are false; JS arrays/objects are truthy. A default using `or` is not necessarily equivalent to `||` or `??`. |
| Dictionaries/sets/equality | Key types, insertion ordering, integer-like JS object keys, identity versus value equality and hash behavior. Choose Map/Set/object deliberately; inspect assumptions about key collisions and deterministic output. |
| Iteration/copying | Lazy iterator consumption, generators, mutability, shallow/deep copy and aliasing. Repeated access to an iterator need not replay data. |
| Strings and bytes | Unicode code points versus UTF-16 code units, normalization/case folding, locale, encoding/error policy, byte lengths and slices. Regex engines/flags, named groups and Unicode classes need actual equivalence checks. |
| Dates and times | Naive/aware values, timezone and DST, month/index conventions, parsing ambiguity, seconds versus milliseconds and serialization. Preserve unknown dates rather than silently using the current time. |
| Exceptions and results | Exception classes, missing-key/index behavior, rejected promises, partial outputs, error codes and cleanup. Do not convert failures into empty successful results merely to satisfy a schema. |
| Async and concurrency | Python sync/async boundaries, event loops, thread/process assumptions, JS Promise scheduling, cancellation, timeout, retry and backpressure. A Promise is not CPU parallelism. Preserve order only where promised. |
| Serialization and schema | Field names, optional values, big numbers, bytes, sets, tuples, floats and stable ordering. State lossy transformations and reject unsupported values where appropriate. |
| Files and processes | Path/case rules, newline/encoding, temporary-file lifecycle, process exit/stdout/stderr, quoting, signals and cleanup. A temporary directory is not a security sandbox. |
| Numerical/scientific packages | Dtype, shape/broadcasting, indexing, random generator/seeds, tolerances and native library behavior. A similarly named JS package does not prove equivalent algorithms. |

## Exact quantities and evidence spans

For financial extraction, preserve currency, scale and amount separately; do not assume every currency has two minor-unit decimals. Parse exact decimal/integer values from strings, check intermediate bounds, and never route a large quantity through Number before converting to BigInt or a decimal representation. A new numeric dependency still needs target-policy approval.

Name span units: UTF-8 bytes, Unicode code points, UTF-16 code units, or grapheme clusters. Python string indices and JavaScript string/regex offsets are not interchangeable; Python AST columns use UTF-8 byte offsets. Bind half-open spans to the exact stored text revision and verify that slicing in the declared unit reconstructs the exact quote. Retain original text/provenance when normalizing; do not invent original HTML offsets from extracted or normalized text without a reliable mapping.

## Port validation plan

Extract a language-neutral contract and serialized fixture format with explicit numeric/encoding rules. Include expected success, expected error and state transitions. Generate the input corpus once and feed identical serialized cases to both sides; equal PRNG seeds across languages do not ensure equal inputs. Check original donor → extracted core and extracted core → port separately when extraction can itself change behavior. Propose:
- Characterization/differential cases against the pinned donor where donor execution is authorized.
- Independently specified cases for target correctness, including known donor quirks that must be changed.
- Property/metamorphic tests for relevant invariants and deliberate invalid fixtures for verifier sensitivity.
- Adapter/integration tests proving the actual target caller and configuration use the port.
- A representative cost/latency check only when the benefit depends on it.

Keep reference answers and blind gold separate. A matching implementation that preserves a donor's mistaken funding amount is parity, not correctness. Do not derive the supposedly independent oracle by running the same donor or candidate twice.
