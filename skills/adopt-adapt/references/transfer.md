# SALVAGE: transfer a mechanism, not its accidental surroundings

Read when a repository, paper, workflow or blocked whole tool contains a potentially useful part. The route is:

**mechanism → dependency closure → semantic contract → target seam → portable tests**

Preserve the existing full five-axis hunt for every source; whole-tool rejection, language, purpose, platform and low score do not exempt a source. This reference strengthens how a discovered mechanism is specified, rather than adding a sixth axis or replacing the hunt. Keep reporting and deeper transfer analysis proportional to the size and consequence of the reuse unit. An abstract design idea does not require an exhaustive type matrix. A port of a stateful algorithm usually does.

## The protected five-axis hunt

For every source, compare Algorithms, Error handling, Data structures, Security/compliance and Performance against the selected target. Cite the source file/function and target evidence for each concrete yes/no. Algorithms include deduplication, ranking/scoring, scheduling, caching, retry and rate limiting; performance includes streaming, batching, memoisation and concurrency. “I did not see anything” without checking is not a supported no. Unavailable evidence leaves the affected axis BLOCKED/UNPROCESSED.

Every concrete yes becomes a salvage finding even below the old six-point triage mark. If preserving the historical SKIPPED label in a batch, use “SKIPPED (salvage found)” rather than plain SKIPPED; clearer new records separate whole-tool disposition from mechanism findings and completion. Breadth must reflect source size and likely hiding places, not an arbitrary fixed file count or only the advertised purpose.

## 1. Identify a concrete mechanism

Search from both ends. Start with known target needs and named donor symbols, algorithms, test techniques, data structures, interfaces or state transitions. Then briefly inspect what the donor does unusually well that might reveal an overlooked target need. Follow an entry point through implementation and its consumer instead of relying on the advertised purpose. A domain mismatch is a reason to look for a smaller transferable part, not a reason to skip the hunt.

For a promising part, describe the problem solved, invariant preserved and assumption that could break the analogy before doing a deep port analysis. This is an early discovery cue, not a second semantic-contract form: a short phrase or sentence is enough for a small idea. For example, save-game recovery can suggest consistent-state recovery after interrupted writes, while assumptions about a single local writer may prevent direct reuse in a concurrent service. Names can differ while behavior matches; similar names can hide incompatible semantics.

Ask what the target does today, what would change, and why the difference matters. Confirm an overlooked need in recipient code or a stated requirement; do not turn a donor strength or a conditional policy into a feature mandate. A part with no demonstrated receiving need is not a qualified transfer finding, but an evidence-backed clue may be retained as `promising` with its unknown seam, assumptions and next discriminating question. Source discovery need not finish its dependency closure before retaining that clue; ADOPT/ADAPT still needs the complete applicable transfer contract.

Use this donor-first look proportionally, especially for an unfamiliar source or an apparent whole-tool mismatch. Do not repeat analysis already covered by the five axes, require a fixed number of discoveries, or save every interesting detail. No useful part remains an acceptable outcome.

Choose the smallest viable reuse strategy:
- Adopt an existing compatible dependency when whole-package fit is genuinely better and policies allow it.
- Adapt a narrow implementation with its necessary notices and maintenance ownership.
- Reimplement a documented behavior/design when donor coupling or runtime makes source transfer inappropriate and rights permit the use.
- Borrow a test, measurement or interface pattern without importing runtime code.
- Keep a reference only, defer, or discard when evidence/value is insufficient.

Do not call copying across languages a clean-room implementation. Do not assume pseudocode, decompilation or paraphrasing eliminates rights obligations. Check the exact component's license and provenance before recommending copied material; no license is not public-domain permission.

## 2. Close dependencies and expose hidden premises

Trace direct helpers and relevant transitive dependencies until the proposed unit can be specified independently. Include, when applicable:
- Types, schemas, constants, tables, bundled models/data and generated artifacts.
- Configuration, environment variables, feature flags, package/runtime versions and native extensions.
- Mutable state, caches, persistence, initialization, global registries and callbacks.
- Side effects, network/file/database calls, subprocesses and installation/test hooks.
- Timing, ordering, concurrency, resource assumptions and failure/retry behavior.
- Legal notices, service assumptions and maintenance/security obligations.

Classify each dependency as retained existing target facility, rewritten locally, isolated behind an approved seam, deliberately excluded with a contract change, or unresolved. Do not omit inconvenient dependencies to make a port look small. A wrapper is justified only when it concentrates real semantic, security or compatibility work. Compare the cost of a local equivalent before importing a large runtime.

A paid/service/prohibited dependency blocks that integration; preserve the original DISCARD. Continue only if an independently useful zero-cost unit can be specified without the blocked behavior. If a particular closure becomes larger than its benefit or cannot be inspected, stop that extraction with the reason; continue the other required axes/parts unless blocked. Inaccessible areas remain BLOCKED/UNPROCESSED rather than a completed negative result.

## 3. Define the semantic contract

Specify relevant inputs/outputs, preconditions, invariants, state transitions and failure behavior. Distinguish:
- Required target behavior.
- Observed donor behavior, including quirks and suspected defects.
- Behavior deliberately changed by adaptation, with a reason and acceptance test.
- Unresolved behavior needing a probe or explicit design decision.

For cross-language/runtime reuse, inspect numeric precision/overflow; null/missing/defaults; strings/Unicode/regex; ordering and equality; serialization; date/time; exceptions/cancellation; resource lifecycle and concurrency when relevant. Read the Python → TypeScript reference for that specific boundary. Do not transplant an API-shaped surface whose semantics differ under malformed, boundary or interrupted inputs.

For a retained process or stateful boundary, specify canonical state ownership and hand-back, snapshot versus event/command delivery, stale/duplicate/overflow handling, units/precision, protocol-version rejection and restart identity. Emitting a version field is not enforcing compatibility; test an incompatible peer. Validate a complete snapshot before publishing it, and do not assume loopback alone supplies authorization.

## 4. Select a real target seam

Name a verified module/interface and its caller/configuration, without inventing files. Use the target's existing dependency injection, data/egress boundary, error vocabulary and ownership model where present. Keep target architecture and public contracts authoritative. State whether this replaces, augments or makes an existing capability usable, and what will not be copied.

For implementation plans, include the smallest reversible slice, before/after flow, files allowed to change, compatibility/migration consequences and a rollback or forward-recovery strategy appropriate to the data. Plans remain plans; do not build the port during an assessment.

## 5. Propose portable tests with two distinct oracles

**Donor parity** asks whether a port matches the donor on a specified input domain. Capture representative donor input/output/state/error behavior only in an authorized environment. Preserve exact versions and normalization rules. Differential tests can detect port drift but reproduce donor bugs.

**Independent correctness** asks whether the result satisfies the user's actual requirement. Use a specification, independently reviewed labels, domain invariants or approved blind human gold. Keep human-gold answers outside the editor's readable development context where required. A port matching donor outputs is not proof of funding-extraction truth, security, numerical correctness or general usefulness.

Useful cases include normal, boundary, malformed, missing/ambiguous, conflicting, reordered, repeated and interruption/restart inputs, chosen for the contract. Add metamorphic/property checks where the relation is valid: idempotence, permutation invariance, conservation, monotonicity or round-trip behavior. Do not assert a relation the donor/target contract does not promise.

Test a pure semantic core separately from adapters and end-to-end integration. Compare recipient-before versus recipient-after to protect existing behavior, then separately prove the intended entry point reaches the new mechanism; unchanged regressions alone may never exercise it. Check failures, not only success-shaped schemas. Use a deliberate broken implementation/fixture to check that the verifier detects the failure it claims to detect. Record what did not run and why.

For a measurable benefit, declare the receiving baseline, representative workload, acceptance/falsification criteria and resource budget before seeing results. Compare quality, latency, resource use and operational complexity only where relevant. A faster microbenchmark does not establish faster user-visible work.

## Stop conditions and useful output

A finding is ready when its value, closure, contract, receiving seam and smallest test are clear enough to decide, and required per-source mining coverage is accounted for. Report axis/area coverage and skipped/unread boundaries; do not claim full coverage from a promising first hit. If a material piece remains unknown, use ADAPT-with-prerequisite with the exact missing evidence and next probe. No useful transfer is a valid result. Put this mechanism record inside the existing dossier, not beside a new mandatory reporting system.
