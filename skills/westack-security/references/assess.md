# Assess a candidate

Read this before a candidate becomes a finding, in any mode. The record fields named here are the ones `secaudit.py check` reads ([record](record.md)).

## 1. The class step

Classify before you trace, so effort goes where a finding can exist.

- **Surface** (`surface`): `shipped`, `test-fixture`, `example` or `dev-only`. Only shipped code yields a finding. A path that exists only in a test fixture, an example or a developer tool is filed `not-applicable`, citing the class.
- **Reach** (`reach`): `other-users`, `self-only` or `privileged-only`. A path that hurts only the person who triggers it, or needs a privilege that already allows the effect, drops out unless it gains privilege (`gains_privilege: true`).
- An unknown surface or reach sends the candidate to `needs-review`, naming the fact that would settle it.

## 2. The admission tuple

A confirmed finding states every one of these; `check` refuses a record that leaves one empty.

| Field | What it says |
| --- | --- |
| `principal` | the lower-trust actor who starts the attack |
| `source` | the input that actor controls, and where it enters |
| `control` | the check meant to stop it |
| `sink` | where the value takes effect |
| `path` | how the source reaches the sink, step by step |
| `boundary` | the trust boundary crossed |
| `resource` | what is read, changed or lost |
| `result` | what was observed, with its receipt |
| `counterevidence` | what you looked for that would disprove it, and what you found |
| `proof_gaps` | what is still assumed |

If the principal, boundary or result cannot be filled, it is a hardening note or needs review, never a finding. A gap elsewhere goes in `proof_gaps` and lowers likelihood ([severity](severity.md)).

## 3. Check the control where the value is used

A control protects only the exact value the sink receives. Walk from the check to the use and look for:

- decoding or re-encoding after the check (URL, HTML, Unicode normal forms, path separators);
- a redirect followed after an allowlist approved the first URL;
- the value changed after validation (merged defaults, trimmed, concatenated);
- a retry or fallback that rebuilds the value without the check;
- a name resolved again later: DNS, a path through a link, a lookup by id.

An allowlist checked before a redirect does not cover where the redirect lands.

## 4. Find the sibling that does it right

Look for how the codebase already handles the same risk on a neighbouring route or function. If one sibling calls the owner check and this one does not, cite the sibling as the `expected-control` snippet: it shows the intended control exists and was missed here.

## 5. Evidence

- Quote snippets by role, from input to outcome: `input`, `entrypoint`, `root-control`, `sink`, `outcome`, and `expected-control` for the sibling. Copy each exactly from the cited lines; `check` compares it with the file and fails a paraphrase or a shifted range.
- Reproduce only within core `verify.md`'s rule for code you did not write, on local fixtures with dummy accounts and tenants. Never probe a live or shared service. A trace with no run is at most `likely`; `demonstrated` needs an observed run on the real path.
- Validate in a fresh context that tries first to disprove the candidate (core `critique.md`), then apply the [exclusions](exclusions.md).

## 6. Identity

Give each record a `rule` (the family), an `anchor` (the root control by file and symbol, never a line number) and an `instance` for each sibling an attacker can reach on its own: two controllers missing the same check are two instances. Group records only when the control and the fix are the same, never because they share a CWE.

## 7. When you stop

A candidate you did not finish is `not-assessed` with what would settle it (`settle`), or `needs-review` with its `missing_fact`. Neither is clean, and the report counts both.
