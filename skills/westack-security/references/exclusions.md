# Exclusions

The general false-positive exclusions are westack-review's (`rules.md`, "False-positive exclusions"): apply them as they stand. This page adds the security ones.

Each exclusion is a default with a condition. It applies only when its condition is shown, and the record cites that condition as the reason. A dropped candidate is filed `rejected` with the exclusion and its condition as `reason`, or `not-applicable` when the class step removed it ([assess](assess.md)). An exclusion whose condition you have not shown does not apply, and the candidate stays.

| Exclusion | Applies only when, shown and cited |
| --- | --- |
| Memory-safety claims (overflow, use after free, out-of-bounds) | the code is in a memory-safe language with no `unsafe` block, FFI call or native extension on the path |
| Resource exhaustion | the cost lands only on the requester's own quota or process, with no shared pool, queue or downstream service affected |
| Findings in tests | the file is test-only: not shipped, and not imported by shipped code |
| Input an attacker cannot reach | the trace names every entry point read and shows no lower-trust principal can supply the value |
| Missing headers, flags or hardening | no exploit path uses the gap; file a hardening note instead |
| Regular-expression denial of service | the engine is linear-time, or the input length is capped before matching |
| Prompt injection with no crossed control | no harness-enforced control is crossed ([severity](severity.md)) |
| A vulnerable dependency version | the vulnerable function is not reachable from shipped code, shown by a trace or a reachability result |
| A value that looks like a secret | it is a public key, a documented placeholder or an identifier that grants nothing ([secrets](secrets.md)) |
| A path an operator alone controls | the operator already holds the power the path would grant |

Worked case: an integer-overflow claim in Rust code with no `unsafe` on the path is rejected, citing "memory-safe language, no unsafe or FFI on the path". The same claim in C survives to validation.

A prohibition in a skill or document exempts a scanner match only in an exact listed phrasing ([intake](intake.md)).
