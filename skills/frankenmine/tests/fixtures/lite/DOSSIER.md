# Linkkeep: Frankenmine lite dossier

Date: 2026-10-28. Author: authored test fixture (not a real run).

## Brief
- **Outcome and users:** One deduplicated reading list from several bookmark exports, for a single user.
- **Target language:** Python
- **Constraints and non-goals:** Standard library only and offline; no sync or server.
- **Implementation:** not-started

| Req | Criterion | Met by |
| --- | --- | --- |
| R1 | Re-importing an export changes nothing | P1, new:Store |
| R2 | URLs differing only in scheme or host case are one entry | P2 |

## Donors and evidence

| Donor | URL | Pin | Language | Licence category | Status, scope and blind spots |
| --- | --- | --- | --- | --- | --- |
| D1 | https://example.invalid/seen | 1111111111111111111111111111111111111111 | Python | task-authored | reviewed: seen.py read, not run; fixture only |
| D2 | https://example.invalid/canon | 2222222222222222222222222222222222222222 | Go | task-authored | reviewed: canon.go read, not run; port handling absent |

| Evidence | Donor | Path:lines | Snapshot file | SHA-256 |
| --- | --- | --- | --- | --- |
| E1 | D1 | seen.py:1-5 | snapshots/d1/seen.py | 285b1d80ec33c157c72899744e0a7c35cd9680284cda26df4b035df848c0a06e |
| E2 | D2 | canon.go:5-8 | snapshots/d2/canon.go | d11debf10e133c17b84c7917cd45931415de53154e15117b903ef0c3215ea6df |

## Lessons

| Lesson | Donor | Direction | Problem → mechanism (invariant) | Need or hypothesis | Evidence | Falsifier |
| --- | --- | --- | --- | --- | --- | --- |
| L1 | D1 | target-led | Re-imports duplicate entries → membership check before insert (each key once) | R1 | E1 | A second import adds rows |
| L2 | D1 | donor-led | Callers cannot tell new from seen → insert returns a first-seen flag (one call records and reports) | hypothesis: report how many entries an import added | E1 | Users never read the count |
| L3 | D2 | target-led | Equivalent URLs stored twice → lower-case before comparing (idempotent) | R2 | E2 | canon(canon(u)) differs from canon(u) |
| L4 | D2 | donor-led | bounded no-gain search: the whole file read; nothing beyond lower-casing | hypothesis: none beyond R2 | E2 | A second mechanism turns up in the file |

## Decision

| Option | What it is | Evidence | Wins on | Loses on |
| --- | --- | --- | --- | --- |
| Best existing | An existing bookmark manager | https://example.invalid/manager, 2026-10-28 | Effort | GPL conflicts with the MIT intent; no import count |
| Minimal fresh | One fresh module | E1, E2 | Simplicity | No import count |
| Fusion | D1 lesson plus D2 canon rebuilt from the idea | E1, E2 | Import count and R2 | Lineage to keep |

- **Decision:** fusion
- **Rationale:** The D2 canonical form is rebuilt and the D1 lesson adds the import count at no extra runtime cost.

## Parts

| Part | Donor | Unit | Route | Basis | Touches | Owner | Material seams | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | D1 | seen.py remember | pattern-only | idea-only | state:entries | Store | state: Store owns the set; errors: never raises | E1 |
| P2 | D2 | canon.go Canon | reimplementation from idea | idea-only | policy:canonical-url | Canon | serialization: returns a plain string | E2 |

- **Other seam dimensions:** considered for both parts; not material because both are pure in-memory functions with no effects, resources or concurrency.

## Tests and review

| Test | Part | Purpose | Specification | Oracle file | SHA-256 |
| --- | --- | --- | --- | --- | --- |
| T1 | P1 | product | Spec item 1 | oracles/spec.md | b090013107979171e655eb8673ee6341a4b16fce38335b0a45f8c2f85f68ae2b |
| T2 | P1 | negative-control | Disconnected dedupe must fail item 1 | oracles/spec.md | b090013107979171e655eb8673ee6341a4b16fce38335b0a45f8c2f85f68ae2b |
| T3 | P2 | product | Spec item 2 | oracles/spec.md | b090013107979171e655eb8673ee6341a4b16fce38335b0a45f8c2f85f68ae2b |
| T4 | P2 | negative-control | Identity canon must fail item 2 | oracles/spec.md | b090013107979171e655eb8673ee6341a4b16fce38335b0a45f8c2f85f68ae2b |

| Pair | Disposition | Test or reason |
| --- | --- | --- |
| P1 / P2 | independent | independent: the store calls canon before the membership check; neither writes the other's key |

| Reviewer | Independence | Report file | SHA-256 | Findings and adjudication |
| --- | --- | --- | --- | --- |
| Fresh reviewer subagent | fresh-context-same-model | review/design-review.md | 3f6c00c54a961dfe11aa9ab7b204db1734d12d5800150059cb8777950de7a9b7 | Minor: IDN hosts out of scope; accepted as a non-goal |

## Readiness
- [x] Every donor in scope has a final status, and the pins are the revisions I read.
- [x] Each donor-led lesson goes beyond its target-led lesson, or records a bounded no-gain search.
- [x] Evidence rows cite source I read at the pin.
- [x] Material seams are recorded, and the rest were considered.
- [x] The three options were compared honestly, and the decision follows from them.
- [x] Each negative control must fail when its part is disconnected.
- [x] The reviewer saw the brief, evidence, oracles and options, not my decision.
- [x] No design blocker remains.
