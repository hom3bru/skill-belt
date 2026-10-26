# One canonical contract

[contract.json](contract.json) is the normative version 1 shape and transition table. [validate.py](../scripts/validate.py) reads it directly; there is no donor-specific task schema.

A task owns requirements, work units, acceptance criteria, actions, evidence, findings, lessons and documentation references. Record identities bind scope, revision and patch; they are not host permissions. The task state is framed, inspected, planned, authorized-work, implemented, verified, delivered, blocked, needs-decision or partial. Read-only investigation/design/review may deliver source-audited findings without claiming implementation or runtime checks.

Evidence has claim, observed artifact hash/revision/patch, operation, environment, raw output digest, executed/pass/fail/skip counts, status, negative-control evidence and coverage limits. Files use portable relative slash paths under the selected evidence root. A digest cannot prove who ran a command. The root and current context supplied to validation must come from the host/user, not a candidate's untrusted instructions.

Review findings bind author/reviewer context, patch, location, consequence, evidence, severity rationale, correction, adjudication and verification. Self-review stays self-review. The helper detects missing independent review metadata when required; it cannot authenticate reviewer identity.

Append history events once with unique IDs. On a scope/patch change, mark old approvals stale and refresh current context. With `--previous`, the helper checks append-only history and preserved action outcomes; without a prior snapshot it cannot detect history deletion. Keep snapshots through the host's existing storage; no service is installed.

Reconciliation states are applied/not-applied/uncertain/denied. Inspect uncertain targets before replay; caller observations are not independent proof. Examples use synthetic identities and cannot authorize real mutations.

Resolving uncertainty against `--previous` requires current passing evidence whose claim ID is the action ID. Negative controls used for acceptance must match that claim's current context and contain actual failing cases; process failure alone is insufficient. Current-scope approved actions still need an allowed action kind after they are applied. Reintroducing an identical denied occurrence under another ID cannot approve it. Historical applied actions remain retainable after a scope change. Complete records require all recorded work units done; reduce scope explicitly or retain a partial outcome when work remains. Requirement supersession is acyclic.

The optional `validate.py init` starter creates this same version-1 shape. It requires caller-selected output/evidence scope and observed context, refuses replacement and starts open/unverified with no receipts or action decisions. Supplied allowed actions record an existing scope snapshot; they do not grant permission. JSON records are capped at 8 MiB; evidence digests stream regular files so large artifacts need not be loaded into memory. Package validation rejects symlinks and Windows reparse points before directory traversal. All path checks remain diagnostic, with no concurrent-filesystem sandbox claim.

The checker supports the contract's deliberately small type/required/enum/range vocabulary. Reject extra keys and malformed JSON. It is not a general JSON Schema implementation, runtime, policy engine or OS boundary. Version changes require explicit migration; do not silently reinterpret old records.

