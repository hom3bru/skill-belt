# What verification establishes

The collection verifier runs the root rejection controls and all three bundled skill suites. It checks published-byte manifests and local references before and after those tests. The package fixtures are authored local cases; no model service, donor runtime, credentials or external product is needed.

| Layer | Evidence | Limit |
| --- | --- | --- |
| Collection checks | Snapshot hashes, local links, privacy-pattern controls and nonempty test counts | A bounded scan is not proof that every possible sensitive value was identified. |
| Helper and contract tests | Valid and invalid records, stale evidence, rights/provenance relationships, task startup and recovery | Consistency cannot authenticate a reviewer, receipt or permission. |
| Authored product fixtures | Executed positive/broken examples | Small cases do not establish general task quality or benefit. |
| Agent and host evaluation | Protocols retained with each skill | General effectiveness, native host enforcement and comparative model results remain unqualified. |

The one Windows exception is `test_research.ResearchTests.test_linked_source_entry_is_rejected` with reason `symlink creation unavailable`. It is reported visibly, cannot count as passed, and is not allowed on Linux. All-skipped suites and every other skip are rejected. The verifier never changes host permissions to force that test to run.

## Updating a snapshot

Make the intended source change and preserve the skill's existing scope and tests. For an adopt-adapt change, first refresh its own manifest:

```sh
cd skills/adopt-adapt
python -B scripts/package.py manifest .
cd ../..
```

Then refresh the collection's published-byte identities and verify:

```sh
python -B scripts/generate_manifest.py
python -B scripts/verify.py
```

Changing a source note with a pinned expected digest also requires an explicit provenance update in that skill; do not change a hash merely to hide an unexpected difference. A regenerated manifest identifies the chosen bytes, not their truth or historical fidelity.
