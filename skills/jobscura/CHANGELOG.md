# Changes

## 0.4.1 - Windows path containment

- Resolve output and toolkit paths before comparing containment, including Windows short aliases.
- Reject internal private context before opening it; retain repository and linked-path guards.
- Add alias rejection and outside-output positive controls; preserve schema version 1 and package identity.

## 0.4.0 — Jobscura

- Rename the public product to Jobscura and add a discoverable Skill Belt router.
- Retain the package identifier and six existing skill names for update continuity.
- Preserve 0.3.0 tracking, intake, history, writing, packet and interview rules.
- Move user-specific routing and timezone choices into explicit private context.
- Add a closed versioned schema, fictional example and read-only context validator.
- Remove private author contact metadata and omit the private audit archive.
- Generate the synthetic XLSX test workbook at runtime from public fictional data.
- Correct packet validation's Windows path representation and reject linked input ancestors (helper 0.2.1).
- Add deterministic allowlisted plugin packaging and privacy rejection tests.

Earlier versions were released under the name Application Assistant. This edition
does not install a scheduler or alter any existing host automations.
