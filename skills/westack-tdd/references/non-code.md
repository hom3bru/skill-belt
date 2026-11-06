# Check-only mode: prose, config and other non-behaviour changes

Some changes have no behaviour of their own to drive with a failing test: documentation, comments, wording that nothing parses, a configuration value, a dependency pin, a generated file, a pure rename. A red test for them is fabricated: written to fail on the old text and pass on the new one, it restates the file and protects nothing. Do not write one, and do not present the change as test-first.

## Give it the check that fits

| Change | Fitting check |
| --- | --- |
| config value (TOML, YAML, JSON, .env template) | the program's own loader or a dry run reads it without error; schema or lint if the project has one; the existing suite still passes |
| CI or build configuration | the project's validator or a dry run where one exists; otherwise a read-through with the risky lines named, and the first real run left as not-run |
| dependency pin | install or lock in the project's own way if the grant covers it, then the build and the suite |
| documentation or comments | links and code samples checked (run the samples when they are runnable); spelling or markdown lint if the project uses one |
| generated file | regenerate it with the project's generator and compare |
| rename or move | the build or import check and the full suite; search for leftover references |

Record each as a receipt and state what it shows: a config that loads shows the file is valid, not that behaviour changed.

## When a config change does change behaviour

If code reads the value and acts on it (a timeout, a retry count, a feature flag), and that behaviour lacks a test, the behaviour gets a test, not the file. Test it at the seam that reads the value: given a configuration with the setting, the client gives up after that long, retries that many times, or takes that branch. That is slice mode at the consumer, and it passes or fails for any value, not only the one in the file. A test asserting that the loaded value equals the number just typed is a change detector.

## Report

Say "check-only" as the order, list the checks with their receipts, and run the full suite against the baseline as usual: a config or rename change can still break tests elsewhere.
