# Source-led continuation — 26 October 2026

This iteration uses Frankenmine to continue an existing multi-donor product synthesis. All twenty decision units remain registered; D06, D16 and D18 were the bounded raw-source subset. The full catalogue was not inspected. No donor runtime, source code or skill prose was transplanted. The new helper and guidance are independently authored against estack's existing task contract.

At their pinned revisions, the source study inspected the selected units, load-bearing Archon callers, relevant source tests and three MIT licence notices. Twenty-three downloaded source/licence blobs matched their GitHub tree identities. Runtime behavior, tests and database compare-and-swap implementation were not executed or qualified. The complete source study, raw snapshots, rights notes, exact ranges/hashes and alternatives remain in the sibling build's `source-qualification/`; a portable structured ledger is retained here as `source-qualification.json`.

## Qualified mechanisms and intentional changes

- D06: [pstack verifier creation](https://github.com/cursor/plugins/blob/99b609a72323b70204eab407c622f436e858e112/pstack/skills/create-verification-skill/SKILL.md) informs usable-instance preflight, actually driving the application, retaining proof through cleanup, and leaving unexecuted verification instructions draft. [Maintenance](https://github.com/cursor/plugins/blob/99b609a72323b70204eab407c622f436e858e112/pstack/skills/maintain-verification-skill/SKILL.md) motivates rechecking readiness after failed interaction. The separate [shipping playbook](https://github.com/cursor/plugins/blob/99b609a72323b70204eab407c622f436e858e112/pstack/skills/poteto-mode/playbooks/shipping.md) motivates non-author same-patch review. Frozen good/broken controls are estack additions, not attributed to the verifier generator.
- D16: [Archon workflow control](https://github.com/coleam00/Archon/blob/761952e62b1d6db36fedf2ec69bc892b8ab90185/packages/cli/src/commands/workflow-control.ts) distinguishes validation-only acknowledgment from executed work. Wait can return successfully while work is failed, cancelled or awaiting attention. An occurrence token targets a decision; actor authority remains a separate check. [Stale resume](https://github.com/coleam00/Archon/blob/761952e62b1d6db36fedf2ec69bc892b8ab90185/packages/workflows/src/stale-resume.ts) motivates a conservative retry rule: a confirmed pre-execution rejection differs from an uncertain side effect. Estack keeps manual reconciliation and imports no Archon runtime or automatic waker.
- D18: [Ralph's loop](https://github.com/snarktank/ralph/blob/6c53cb0b831ebe8739c6a003e22af14902d8b0b5/ralph.sh) remains rejected as estack's controller. Its bounded-attempt and persistent-progress patterns can inform a small task record, while permission bypass flags, swallowed failures, broad policy mutation and completion-marker proof are not retained. The new starter populates estack's existing version-1 record rather than importing another state format.

## Ownership and alternatives

Keep the existing dispatcher/modules as the smallest coherent continuation. A pstack or Archon dependency would add instance, lifecycle, provider and persistence ownership without demonstrated need. A fresh tiny dispatcher would lose existing recovery/receipt coverage. The chosen route retains native host permissions, one canonical record and small optional helpers; it makes no measured superiority claim.

The coordinator owns the instance and teardown; evidence survives outside disposable instance state. The host/user owns permissions and execution. The task record owns progress; occurrence identity prevents stale targeting but cannot grant authority. A validator checks only structural consistency. Exact source/language/closure and rights limitations remain in the structured ledger; future source copying needs a fresh exact-unit assessment and notices.

Falsifiers include proof deleted during cleanup, a successful observer command over failed work, a stale or unrelated failure used as a current negative control, a renamed denied action, and a timeout replay that duplicates an already-applied effect. Deterministic guards and bounded usage trials address different parts of those risks. No host boundary or broad agent effectiveness is certified here.

## Source-level review — 28 October 2026

A read-only review fetched all twenty pinned sources, plus HEAD, linked siblings and licence files. It ran no donor code, and its notes stay outside this package. Grades use the shared vocabulary:
- present for seventeen (D06, D16 and D18 re-confirmed, with their recorded hashes matching at the pin and HEAD);
- wired for D12 (its hooks call a script read at the pin);
- claimed for D14 and D15 (vendor documentation, baseline hashes now recorded).

Drift since the pins is low: fifteen unchanged, three changed-minor (D11, D16, D17), none material. D14 and D15 have no earlier snapshot. Each decision's `source_review` in decisions.json records the grade, drift and observed licence.

Five attributions were corrected:
- D01's pinned file only delegates to an exhaustive interview and to glossary/ADR capture; "decision-changing questions only" is estack's restriction.
- D04's donor supplies red-green; executed broken-copy controls are estack's addition.
- D07's pin is a distilled file. The richer revision e8d856f0 is cited as a supporting source. The pin stays, because the file is unchanged at HEAD and the pstack decisions share it.
- D13's donor CLI documents a `--version` option (claimed); only freshness and revalidation are estack's.
- D20's donor supplies persona GO/NO-GO with a mandatory rollback plan; "no deployment or credential use" is estack's restriction.

D10's promised inconclusive verdict is now an estack result.
