# Local execution receipts

`scripts/execution.py` is an explicit runner for a separately authorized,
bounded local check. The normal `aa.validate`, research, and capture flows do
not invoke it. Use it only for a command that the user has authorized to run.

The Python API is:

```python
evidence = execution.execute(
    run_dir, command, cwd, harnesses, inputs, authorization, timeout,
    env_keys, subject="fixture", revision="owned",
)
receipt = execution.verify_evidence(evidence, run_dir, live=True)
```

`command` is a nonempty argument list and runs with `shell=False` in the named
working directory. `authorization` records why this run was approved; do not
put credentials in command arguments or authorization text. The child receives
only the Windows runtime variables `SystemRoot`, `WINDIR`, `TEMP`, and `TMP`
when present, plus names explicitly listed in `env_keys`. No other caller
environment variables are inherited. The executable is resolved and hashed
before launch. Declared harness and input files are hashed before and after.

The command writes one JSON object to stdout, optionally with
`"schema_version": 1`:

```json
{
  "schema_version": 1,
  "checks": [
    {"id": "behavior", "kind": "positive", "status": "pass", "detail": "expected behavior observed"},
    {"id": "wrong-answer", "kind": "negative-control", "status": "pass", "detail": "incorrect result rejected"},
    {"id": "optional-case", "kind": "positive", "status": "skip", "detail": "not run", "reason": "fixture unavailable"}
  ]
}
```

Check IDs must be unique. Each row requires nonempty `id`, `kind`, `status`,
and `detail`; only skipped rows may include a nonempty `reason`. Counts are
derived from rows, never accepted from command output. `run_counts.total`,
`skipped`, and `failed` count positive rows only. Positive passing rows count
as assertions, and only passing negative-control rows count as controls.
Skipped or failed controls make the receipt ineligible. A receipt is eligible
only when the command exits zero, completes within its timeout, has parseable
output, has at least one passing positive assertion and one passing negative
control, contains no failed positive rows, and has no skipped/failed negative
control. Ineligible receipts retain their output, checks when parseable, exit
status, and reason for diagnosis.

The runner stores stdout, stderr, and the receipt itself as content-addressed
artifacts below `run_dir/artifacts/`. Each stream is drained while retaining at
most 4 MiB; stdout parsing is limited to 1 MiB and 10,000 check rows. Truncated
or malformed output cannot be eligible. `verify_evidence` checks receipt and
log hashes, reparses captured stdout, recomputes totals and eligibility, and
with `live=True` checks the current tool/harness/input bytes against the run.
Use `live=False` only for historical inspection; it still verifies the stored
receipt/log consistency.

The CLI form is:

```text
python -B "<skill-directory>/scripts/execution.py" RUN_DIR --authorization "user-approved fixture run" \
  --cwd OWNED_WORKDIR --timeout 60 --harness HARNESS.py --input fixture.json \
  --subject example --revision local -- COMMAND ARGUMENT ...
```

CLI exit code 0 means the captured check is eligible, 1 means an ineligible run
was captured for diagnosis, and 2 means the invocation or receipt failed.

This mechanism creates local diagnostic evidence. It is not an OS sandbox,
does not prove process ancestry or remote authenticity, and does not establish
that the checks use a semantically adequate or independent oracle. Reviewers
must assess those claims separately. On POSIX, timeout kills the process group;
on Windows, the standard-library implementation kills the direct process and
cannot guarantee that descendants stop. Use an external OS sandbox when the
command is untrusted. Anyone who can edit the local files can forge this
receipt, so it is not cryptographic attestation.

## Controlled tool-verification handoff

Before a separately requested experiment, record the tool/version and pinned
artifact, owned target or fixture, independently expected observation, one
wrong-result/disconnected-check control, allowed working directory and writes,
process/network access, credential/environment policy, time/output/resource
budget and ownership-aware cleanup. Reuse the user's existing authorization;
do not add another confirmation for an already scoped command. Installation,
production access, spending and permissions outside that scope still require
their own authorization. Do not treat the authorization text field as proof
that permission was granted.

For trusted owned fixtures, a timeout and bounded output may be sufficient.
For an unfamiliar donor binary, use the host's real sandbox rather than this
runner as the security boundary. An unavailable tool can leave the research
conclusion ready and the proposed runtime experiment `not-run`; it does not
force rejection of a useful source-derived mechanism. REA inspecting its own
packaged artifact is one possible experiment: compare its observations with
independently read source and deliberately faulty artifacts, then describe
only the paths actually exercised. Agreement between two copies of the same
analyzer cannot establish independence on its own.
