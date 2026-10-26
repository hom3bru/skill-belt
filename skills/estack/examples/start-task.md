# Start a persistent task

Keep tiny tasks in conversation when a saved record adds no value. For an ongoing build, the helper can create the existing canonical task shape without hand-transcribing the template. Choose an existing isolated evidence directory and a new task filename; the output must stay in that directory.

From the skill directory:

```text
python scripts/validate.py init RUN/task.json --root RUN --goal "Build the agreed import slice" --revision OBSERVED-REVISION --scope import-v1 --patch OBSERVED-SHA256 --author CURRENT-AUTHOR --allow-path src --allow-path tests --allow-action read --allow-action local-write
```

Replace the observed revision/hash and author with the current host evidence; do not use the example labels as measured values. `--patch` must be a 64-character lowercase SHA-256. `--task-mode` and `--size` may select another existing contract mode/size. The directory RUN must already exist in authorized scope. Existing output is never replaced.

The result is `created-incomplete`: framed, open, unverified, no action decisions, no evidence and no acceptance claims. The host starts unprobed. Inspect the current repository and host, write requirement-derived acceptance conditions, record any forbidden actions and non-goals, and proceed through the relevant modules. An allowed-action flag is a record of existing scope, not a new permission. The helper launches no commands or agents.

Check the saved record with the task command in SKILL.md and supply current host-observed context when verifying or finishing. Keep earlier snapshots for interruption reconciliation using `--previous`. Never make an incomplete scaffold green by inventing a test, observer, reviewer or approval.
