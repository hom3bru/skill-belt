# Test quality

## A test has a job

Before writing the body, name the break it catches: the production change that would make it fail. If you cannot name one, the test has no job yet; find the behaviour a caller can observe. If the only change that fails it is a deliberate decision (a constant's value, the wording of a message nobody parses, a private structure), it is a change detector: it fires on every redesign and sleeps through bugs. Test the behaviour that depends on the decision instead.

## Behaviour, not implementation

- Exercise the code through the interface its callers use, and assert what they can observe: return values, state readable through the interface, output, errors raised.
- A test that breaks when the internals are restructured but behaviour is unchanged is coupled to the implementation. Signs: it calls private functions, asserts call counts or order on the project's own collaborators, or verifies results by going around the interface (querying the table directly rather than fetching the record back through the API).
- Test your code's contract, not the framework's: assert the route you register, the query you build, the payload you send, not that the framework calls handlers.
- One behaviour per test, named for that behaviour. Arrange, act, assert. Prefer readable repetition to shared helpers that hide what each test checks.

## Expected values come from outside the code

- Use literals, worked examples from the spec or the issue, published reference values, and fixtures a person has checked. For rules, a table of inputs with literal answers is the clearest shape.
- Never compute the expected value with the function under test, a helper it calls, or a reimplementation of its formula. `assert total(items) == sum(i.price for i in items)` and `expected = discounted(100); assert discounted(100) == expected` agree with any implementation.
- A snapshot written by the code is a recording of current output, not an oracle. Review it against an independent source before it protects anything.
- Floating point: compare with a stated tolerance chosen from the domain (a cent, a millisecond), never one widened until the test passes.

## Deterministic and isolated

- Inject time, randomness and ids; never sleep to wait for a result.
- Each test builds and cleans up its own state; running alone, in another order or in parallel gives the same result.
- Teardown used only by tests belongs with the test helpers, never as a method on a production class.
- Replace a volatile field (id, timestamp, path) by its path in the output, assert its type or shape first, and give equal values the same numbered token (`id0`, `id1`) so a golden still shows same versus different; a constant placeholder hides a swap. List the redacted paths in the receipt: a redacted field is unprotected. Keep the typed check and the scrub as separate steps. Scrubbers are code under test ([controls](controls.md)).

## Never weaken a test to get green

Weakening includes: loosening an assertion (`==` to `<=`, exact to "contains"), widening a tolerance, adding a skip, xfail or retry, deleting or commenting out a case, catching the exception inside the test, and replacing an expected value with whatever the code printed. Each needs the user's decision with the reason, and a control run showing the changed test still fails on the break it names.

## Coverage is not protection

A line that ran is not a line that is checked. Coverage tells you where no test reaches; only failing controls show that a test catches a break there. Do not add tests just to raise a number.

## Transforms

A codemod or rewrite script needs negative fixtures: lookalike inputs it must leave byte-identical, one per bail-out guard. The test plan counts positive, edge, no-op and negative fixtures; a transform with no negative fixture is unproven, and the over-eager copy that rewrites a lookalike is its control ([controls](controls.md)).

## Auditing existing tests

When asked whether tests are any good, run controls against them ([controls](controls.md)) and report each survivor with the input or assertion that would kill it. Flag tests with no assertion, tests that only read source text, and near-duplicates as candidates, with evidence. Delete or rewrite existing tests only in batches the user approves. For golden files, have the check list the files it compared and the pairs that differed, with hashes; call a golden an orphan only if its owning test was selected and ran, a partial run being inconclusive for the rest, and delete nothing on that evidence.
