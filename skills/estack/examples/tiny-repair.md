# Tiny repair

User: “add returns subtraction; fix this bug.” Read repository rules and add's callers/test. No design interview is needed.

In a disposable fixture, run the existing assertions add(2,3) === 5 and add(-2,3) === 1 on the broken implementation. Capture two failures. Change subtraction to addition only. Re-run: two passes. Restore subtraction in a separate control copy: assertions fail again. Record source/output hashes, command, test count and exits.

Deliver the local change and those observations, with no implied commit or push. This release's tests reproduce that data path; it is a deterministic fixture, not evidence that a model autonomously followed the skill. [Task record](task.json) illustrates the shared contract with synthetic identifiers and source-audited evidence.

