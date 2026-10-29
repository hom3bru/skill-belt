# Tiny repair

User: “add returns subtraction; fix this bug.” Read repository rules and add's callers/test. No design interview is needed.

Run the existing assertions add(2,3) === 5 and add(-2,3) === 1 on the broken implementation: two failures. Change subtraction to addition only. Re-run: two passes. Without a saved record, that red run is the broken-copy control because the test did not change, so do not rerun a reverted copy or snapshot files for a record you are not keeping. Report both runs (command, counts, exits) and deliver the local change, with no implied commit or push.

If you keep a record, write the red run with `validate.py receipt` before the fix (it snapshots the pre-fix file), `validate.py refresh` after it, then record the passing run with `--control` naming the red receipt. This release's tests reproduce that data path; it is a deterministic fixture, not evidence that a model autonomously followed the skill. [Task record](task.json) illustrates the shared contract with synthetic identifiers and source-audited evidence.
