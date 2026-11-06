# Test doubles

## Where doubles belong

Replace only what the project does not own and cannot run cheaply and deterministically in a test: third-party services (payments, email, SMS, remote APIs), the clock, randomness, and sometimes the file system or database when a temporary folder or a test database is impractical. Use the real code for the project's own modules and internal collaborators.

Preference, strongest first: the real implementation; a fake (a working in-memory version); a stub returning fixed data; a mock that records calls. Move down the list only for a reason you can state: slow, non-deterministic, costly, or a side effect you must not cause. Close the test world: any call across a boundary that has no double raises an error naming the call (`unmocked: send_email`), so a test cannot pass through an unnoticed side effect.

## Before replacing something

- List what the real thing does that the test depends on: writes it makes, state it updates, values it derives. Keep those real and replace only the slow or external layer beneath them. A double that swallows a write the code later reads makes the test pass while production breaks.
- Make the fake's data complete: every field the real response carries, not only the ones this test reads.
- Give each branch (success, failure, malformed reply) its own fake or fixture, so the wrong branch cannot satisfy the test.

## Design so the boundary is easy to replace

- Pass the dependency in (a parameter or constructor argument) rather than building it inside the function from global configuration.
- Give each external operation its own method (`create_ticket`, `get_ticket`) rather than one generic `request(method, path, body)`; then each fake returns one shape and the test shows which operations it uses.
- Code that is hard to test without mocking its own internals is telling you about its design: a wider seam or a smaller module usually fixes the test.

## What to assert

- Assert outcomes the caller can see. When the effect at the boundary is the behaviour (an email is sent, a card is charged, an event is published), assert what crossed the boundary through a recording fake: the recipient, the amount, the payload, and that it happened once when once is the rule.
- A bare "was called" assertion (`assert_called_once()`, `toHaveBeenCalled()`) checks the wiring only. It survives every mutation of what was sent: the wrong recipient, the wrong amount, an empty body. Pair it with the arguments, or replace it with an assertion on the recorded payload.
- Never assert on the double itself (that the mock object exists, that a test id of the mock is on screen).
- Assert call order or counts only when they are the contract (retries, rate limits, at-most-once delivery).

The controls in [controls](controls.md) check this: mutate what the code sends and the test must fail.

## Scripts and CLIs

Test a release or install script with stubbed externals (git, npm, the installer) on a temporary PATH and an isolated HOME, never the real tools. Prove its validator by showing that bad input fails before any subprocess starts: the stubs' call log is empty.
