# Profile: generic recipient

Use for a user-specified repository or workflow without an inspected dedicated profile. Read its current AGENTS.md / CLAUDE.md / CONTRIBUTING, relevant entrypoints, tests and dependency manifests. Record the exact root, revision, instructions and receiving seam. Missing rules remain UNKNOWN, not permission. A legacy profile name never supplies architecture or policy.

Use the generic fit rubric: relevance 0–3, novelty 0–3, fit 0–2, surface/reversibility 0–2, then one strongest penalty. Retain every-input accounting, source evidence, applicable legal/trust gates, two-way mechanism discovery and a falsifying transfer test. Do not import another recipient's privacy, dependency, freeze or data-access rules.

## Optional caller-supplied path classification

`python -B scripts/aa.py classify-path path/to/file --rules recipient-rules.json` classifies paths from an explicitly supplied JSON file. The compatibility alias `radar-path` requires the same file; no private policy is bundled and no-rules use is refused. These commands do not inspect the recipient or authorize edits.

The caller must derive and review all fields against current recipient instructions. Empty lists mean no such declared match, not that the repository has no controls. Use a revision/hash identifying those inspected rules. The following is a **synthetic format example**, not default policy:

```json
{
  "revision": "synthetic-rules-v1",
  "governed_prefixes": ["src/protected/"],
  "governed_exact": ["src/exact.ts"],
  "measurement_dependencies": ["metrics/bridge.ts"],
  "policy_prefixes": [".policy/"],
  "preflight_self": ["tools/preflight.ts"],
  "documentation_prefixes": ["notes/"],
  "test_suffixes": [".test.ts"]
}
```

All fields are required; path lists may be empty. Paths are relative and canonical, Windows separators normalize to `/`, and directory prefixes end in `/`. Absolute/traversal paths, malformed rules and duplicate JSON keys are refused. Classification order is governed (except explicitly listed test suffixes), policy drift, declared preflight self, measurement dependency, declared documentation, then ungoverned-needs-disposition. Unlisted paths default to `safe_to_change:false`; even a true classification does not grant authorization or supersede the live recipient policy.
