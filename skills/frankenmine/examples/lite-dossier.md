# &lt;Product&gt;: Frankenmine lite dossier

> Lite: up to three donors, design only, one session. `scaffold-lite` writes this file with numbered rows; replace every prompt in angle brackets, let `stamp` fill the SHA-256 cells, and run `check-lite` until `lite-complete`. It names the checks lite skips and says when to move to the full tier. Write `none: <reason>` where nothing applies.

Date: &lt;...&gt;. Author: &lt;...&gt;.

## Brief
- **Outcome and users:** &lt;...&gt;
- **Target language:** &lt;...&gt;
- **Constraints and non-goals:** &lt;...&gt;
- **Implementation:** not-started

| Req | Criterion | Met by |
| --- | --- | --- |
| R1 | &lt;...&gt; | &lt;part IDs, new:component or existing:product&gt; |

## Donors and evidence
| Donor | URL | Pin | Language | Licence category | Status, scope and blind spots |
| --- | --- | --- | --- | --- | --- |
| D1 | &lt;...&gt; | &lt;full commit or tag@sha256&gt; | &lt;...&gt; | &lt;open-source, source-available, proprietary, public-domain or task-authored&gt; | &lt;reviewed, deferred or blocked: ...&gt; |

| Evidence | Donor | Path:lines | Snapshot file | SHA-256 |
| --- | --- | --- | --- | --- |
| E1 | D1 | &lt;...&gt; | &lt;...&gt; | &lt;stamp&gt; |

## Lessons
| Lesson | Donor | Direction | Problem → mechanism (invariant) | Need or hypothesis | Evidence | Falsifier |
| --- | --- | --- | --- | --- | --- | --- |
| L1 | D1 | target-led | &lt;...&gt; | &lt;...&gt; | E1 | &lt;...&gt; |
| L2 | D1 | donor-led | &lt;...&gt; | &lt;hypothesis: ...&gt; | E1 | &lt;...&gt; |

## Decision
| Option | What it is | Evidence | Wins on | Loses on |
| --- | --- | --- | --- | --- |
| Best existing | &lt;...&gt; | &lt;...&gt; | &lt;...&gt; | &lt;...&gt; |
| Minimal fresh | &lt;...&gt; | &lt;...&gt; | &lt;...&gt; | &lt;...&gt; |
| Fusion | &lt;...&gt; | &lt;...&gt; | &lt;...&gt; | &lt;...&gt; |

- **Decision:** &lt;fusion, minimal-fresh, best-existing or defer&gt;
- **Rationale:** &lt;...&gt;

## Parts
> Route: dependency, narrow-port, ffi, wasm, reimplementation from code or from idea, or pattern-only. Basis: licensed-reuse, permission or idea-only. Material seams: `dimension: note` for the [seam dimensions](../references/seams-and-bridges.md) that matter. Code routes add `| Dependency | Part | Pin | Licence category | Disposition |`.

| Part | Donor | Unit | Route | Basis | Touches | Owner | Material seams | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | D1 | &lt;...&gt; | &lt;...&gt; | &lt;...&gt; | &lt;state:...&gt; | &lt;...&gt; | &lt;...&gt; | E1 |

- **Other seam dimensions:** &lt;considered; not material because ...&gt;

## Tests and review
> Oracles must not be donor files. If anything is implemented, add `| Test | Result | Raw output | SHA-256 | Product file | Product SHA-256 |`.

| Test | Part | Purpose | Specification | Oracle file | SHA-256 |
| --- | --- | --- | --- | --- | --- |
| T1 | P1 | product | &lt;...&gt; | oracles/spec.md | &lt;stamp&gt; |
| T2 | P1 | negative-control | &lt;...&gt; | oracles/spec.md | &lt;stamp&gt; |

| Pair | Disposition | Test or reason |
| --- | --- | --- |
| &lt;P1 / P2&gt; | &lt;independent, compatible or resolved&gt; | &lt;integration test ID, or independent: ...&gt; |

| Reviewer | Independence | Report file | SHA-256 | Findings and adjudication |
| --- | --- | --- | --- | --- |
| &lt;...&gt; | &lt;fresh-context-same-model, different-model or human&gt; | &lt;review/...&gt; | &lt;stamp&gt; | &lt;...&gt; |

## Readiness
- [ ] Every donor in scope has a final status, and the pins are the revisions I read.
- [ ] Each donor-led lesson goes beyond its target-led lesson, or records a bounded no-gain search.
- [ ] Evidence rows cite source I read at the pin.
- [ ] Material seams are recorded, and the rest were considered.
- [ ] The three options were compared honestly, and the decision follows from them.
- [ ] Each negative control must fail when its part is disconnected.
- [ ] The reviewer saw the brief, evidence, oracles and options, not my decision.
- [ ] No design blocker remains.
