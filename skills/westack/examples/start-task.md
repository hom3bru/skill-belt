# Start a persistent task

Keep tiny tasks in conversation when a saved record adds no value. For an ongoing build, the helper can create the existing canonical task shape without hand-transcribing the template. Choose an evidence directory (RUN) outside the skill folder and outside the observed paths: for example `.westack/import-v1` in the project (add `.westack/` to `.git/info/exclude` if you want a clean status), or a folder outside the repository. The record must be a new file inside RUN, and RUN must already exist.

From the project root:

```text
python "<skill-directory>/scripts/validate.py" init .westack/import-v1/task.0001.json --root .westack/import-v1 --repo . --goal "Build the agreed import slice" --scope import-v1 --author PATCH-AUTHOR --allow-path src --observe-path tests --allow-action read --allow-action local-write --forbid-action push --non-goal "No publication"
```

`--repo` fingerprints the allowed paths plus each `--observe-path` (here the tests you rely on but may not edit), skipping `.git`, RUN and the default caches and dependencies (`__pycache__`, `.pytest_cache`, `node_modules`, `.venv`, `venv`, `.mypy_cache`, `.tox`, `dist`, `build`, `.next`). `--exclude <name or path>` adds to that list and `--no-default-excludes` starts it empty. The record stores this definition as `fingerprint`, and RUN keeps the per-file hashes in `manifests/`. Zero hashed files is an error, as is a RUN that equals or contains an observed path. The revision comes from the nearest `.git`; pass `--revision` (from `git rev-parse HEAD`, or `no-vcs`) when it cannot be read. Without `--repo`, supply both `--revision` and a 64-character lowercase `--patch`. The scope is a label you choose for the user's current authority. `--author` names whoever produces the patch under review or verification; do not use the example labels as measured values. `--task-mode` and `--size` may select another existing contract mode/size. Existing output is never replaced.

The result is `created-incomplete`: framed, open, unverified, no action decisions, no evidence and no acceptance claims. The host starts unprobed. Inspect the current repository and host, write requirement-derived acceptance conditions, add further forbidden actions and non-goals as you learn them, and proceed through the relevant modules. An allowed-action flag is a record of existing scope, not a new permission; an action kind cannot be both allowed and forbidden. The helper launches no commands or agents.

Later versions are `task.0002.json` and onward. Write them with `receipt` and `refresh` ([build](../references/build.md)), or by hand when you add plans and acceptance conditions. Check the newest with the task command in SKILL.md, including on resume; a patch or scope mismatch fails until the record is refreshed and lists the changed files, and verifying or finishing requires current context. Never make an incomplete scaffold green by inventing a test, observer, reviewer or approval.
