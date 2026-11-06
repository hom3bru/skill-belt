# The cycle: slice and regression modes

## Before the first test

- **Commands.** Learn how this repository runs one test and the whole suite: checked-in wrappers (`./gradlew`, `make test`, a package script), the test configuration, and the CI workflow that gates merges. Use those commands for every red, green and after-run.
- **Baseline.** Run the full suite once before editing and keep the raw output. Failures already there are pre-existing; name them now so they are never blamed on the slice or silently fixed.
- **Seam.** Test at the highest public boundary that exercises the behaviour, through as few seams as possible. When the seam itself is in question on bounded or cross-cutting work, propose one or two with what each would catch and miss, and recommend one. For a small slice, pick and say which.
- **Slices.** One behaviour per cycle, each a thin tracer bullet through the layers it needs. Never write the whole test list first: a batch drafted up front guesses at behaviour and fixes the code's shape before any cycle has shown what the problem needs. Keep a short list of the next behaviours instead.

## Red

1. Write one test for the next behaviour. Name it for the behaviour, in the project's domain words.
2. Before running, say which production change should make it fail and where its expected value came from.
3. Run it focused and keep the raw output. Classify the result:

| What the run shows | Meaning | Next |
| --- | --- | --- |
| the new test fails on its assertion, with the expected-against-actual you predicted | a clean red | green |
| no tests ran; an import, collection or module-load error | not red | create the missing name as an empty stub, rerun |
| an error before the assertion (wrong signature, a call that throws) | not red | adjust the signature or return a minimal constant, no logic, rerun |
| a different assertion fails, or other tests break too | wrong reason | fix the test or its setup; a stub that breaks neighbours is too big |
| it passes | it tests behaviour that already exists | rewrite it to name a missing behaviour, or switch to characterise |

Reaching a clean red may add stubs and signatures, never logic. With the helper and the core present, `controls.py judge --reference <later green> --run red=<red output> --assertion-only --min-kills 1` checks the red run against the green one: same selection, an assertion failure, nothing blocked.

## Green

- Write the least code that passes this test: no options, branches or error handling a future test might want.
- Rerun the focused test, then the tests around the changed code.
- If the test turns out to assert the wrong behaviour, say so, correct the test, and show it red again against code without the change before going green. Editing a test after red so that it passes is weakening it.

## Refactor

- Only on a green you ran. Restructure code or tests without adding behaviour: names, duplication, extracting helpers whose behaviour existing tests already cover. A function whose behaviour is new needs its own failing test first.
- Rerun the same selection. The collected count does not drop between green and refactor; if a test is removed or merged, say which and why.

## Controls and finishing

Run the controls in [controls](controls.md) for each slice's claim, then the next slice. At the end rerun the baseline command, keep the raw output, and compare by name with `python "<core>/scripts/checks.py" diff <baseline> <after>`. Exit 0 is no new failures and nothing missing; 1 is new failures; 2 cannot tell. Report new and pre-existing failures as two lists.

## Regression

For a bug whose cause is known (diagnosed by `westack-debug`, or plain from the code):

1. Baseline as above.
2. One test at the seam where the bug lives, asserting the behaviour the user expected. Its red must fail on that assertion with the user's symptom in the actual value; a different failure means the test does not reproduce the bug.
3. Fix where the bad value starts, not where it surfaces. Smallest change; no tidying on the side.
4. Green: the test and the original reproduction both pass.
5. Controls: the red run before the fix is one control when the test has not changed since. Add one more broken copy of a different kind at the fix site (for a boundary fix, the other wrong boundary; for a missing guard, the guard inverted). `controls.py plan --min-variants 1` writes it. If the test changed after its red run, rerun it with the fix undone in a copy instead.
6. After-run and `checks.py diff`.

That is the whole ceremony for a one-line fix: one test, two controls, one diff.

## Order honesty

When code already exists before its test (the user wrote it, or an earlier session did), do not delete it. Write the test, then prove it can fail with controls, and report the order as test-after. "Test-first" in a report means a red run exists for that test.
