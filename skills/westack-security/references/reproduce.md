# Reproduce a confirmed finding in a container

For one confirmed finding, prove it in an isolated container built from the target, then try at most three repairs on a scratch copy. The label on the finding is never more than the evidence: `static` (read only), `reproduced` (a container run showed it), `repair-tested` (a repair candidate was run against it too).

## Before the run

1. **One finding, a budget.** Name the finding's id and set the budget before starting: minutes (ten by default) and workers (one by default). Stop at the budget and keep the label the evidence has reached.
2. **The grant.** Each `docker build` and `docker run` needs the user's grant naming it: the image, what it copies in, and whether it touches the network. Building usually pulls a base image (network); the run itself gets `--network none` unless the user grants more, recorded as `network_grant`. Docker not running is `blocked`, never a reason to run the target on the host instead.
3. **A scratch copy.** Build from a copy of the target in the task folder, never the user's tree. Copy in only what the reproduction needs; no credentials, `.env` files or home-folder mounts.

## The run

1. Build the image; record its tag and id (`docker image inspect --format {{.Id}}`).
2. Run the reproduction with `--rm --network none --read-only` and a non-root user where the image allows. Save the full output to the evidence folder and hash it.
3. Compare what happened with the finding's claim: the same principal, sink and result. A run that does not show it leaves the label at `static` and the finding stays as the audit left it; say what differed.
4. Remove the container (`--rm`) and, when finished, the image, unless the user wants it kept.

## Repairs

At most three candidates, each the smallest change that would close the path, on its own scratch copy. Rebuild and re-run the same reproduction for each; record the patch's SHA-256, the run receipt and `fixed` or `not-fixed`. A repair here is evidence for the fix, never the fix: shipping one is westack-security's fix mode and westack-build, under their own grants.

## The record

On the confirmed finding:

```json
"reproduction": {"label": "repair-tested", "budget": {"minutes": 10, "workers": 1},
  "container": {"image": "...", "image_id": "sha256:...", "command": "docker run --rm --network none ...",
                "exit": 0, "log_sha256": "<64 hex>", "network": "none"},
  "observed": "what the run showed, against the claim",
  "repairs": [{"candidate": "...", "patch_sha256": "<64 hex>", "scratch_copy": true, "result": "fixed",
               "run": {"image": "...", "image_id": "...", "command": "...", "exit": 1, "log_sha256": "...", "network": "none"}}]}
```

`secaudit.py check` refuses a reproduced or repair-tested label without the container receipt, the observation or the budget; a networked run without `network_grant`; repair-tested with no repair, more than three, one without its own run, or one off a scratch copy; and a reproduction on anything but a confirmed finding. The report prints the label beside the finding.

`evals/fixtures/repro-traversal` is a worked target: a file server whose `resolve` lets `/%2e%2e/secret.txt` out of `public/`, its `repro.py` (exit 0 when the secret is served) and a `Dockerfile` for the run.

Provenance: gstack's cso isolated reproduction mode at the mirror pin (absorption.json `gstack.cso.isolated-reproduction`), in westack's words.
