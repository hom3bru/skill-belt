---
name: westack
description: Use when the user names westack or types /westack. Routes to installed westack-* sub-skills, runs list, doctor and defer, and holds the shared evidence, authority, consent and memory rules.
disable-model-invocation: true
metadata:
  stack: westack
  version: 1.0.0-alpha.0
---

# westack router

Pick one owner, apply the shared rules, add no authority: a named sub-skill or mode is a routing preference, not permission.

## 1. What is installed

Trust the host's skill listing first; `python "<this folder>/scripts/registry.py"` reads front matter only. A `westack-*` folder is ours only with `metadata.stack: westack`. Never claim one unseen.

## 2. Choose one owner

1. An explicit name wins: `/westack review`, `/westack-review` and "use westack to review" all mean `review`.
2. Otherwise classify by artifact, then verb, then object:
   - artifact: a diff or PR → `review` (a plan or design document: document mode); a stack trace or local failure → `debug`; a check failing only in CI → `ci`; an idea → `office-hours`;
   - verb: build, plan, ship, deploy, migrate, refactor, research, document → the same-named sub-skill (document: `docs`);
   - object: SQL or a schema or data migration → `db`; `*.tf` or Kubernetes manifests → `infra`; WCAG → `a11y`.
3. Tie-breaks: "make it faster" → `perf` (SQL-bound: `db`; cloud bill: `infra`); "fix the PR comments" → `review`; "watch the PR until green" → `ci`; "investigate" or "why" with no fix asked → `debug`, diagnose-only; "design review": a plan, spec or document → `review` (document mode), a built UI → `design`.
4. When two fit, ask one question with a recommended answer.
5. Cross-cutting work: propose the chain once; [hand off](references/handoff.md) between links.

If the owner is not listed by the registry, say so ("westack-debug is not installed" if built, "westack-perf is not built yet" if planned) and follow [route](references/route.md).

## 3. Stack commands

| Command | Does |
| --- | --- |
| `list` | ours, foreign `westack-*` names, others: registry.py, or the host's listing without a shell |
| `doctor` | versions, `scripts/core_check.py`, [host status](hosts/README.md) |
| `defer` | the defer decision and evidence ([defer](references/defer.md)) |
| `verify` | `westack-verify` when installed, else the core [verify](references/verify.md) |
| `build` | `westack-build` when installed, else the core [build](references/build.md) |
| `handoff`, `resume` | [handoff](references/handoff.md) |
| `guard` | active guardrails ([authority](references/authority.md)) |

## 4. Rules every route keeps

- **Evidence** ([evidence](references/evidence.md)): a claim needs a receipt; zero executed tests is not a pass; matched broken-copy controls; new failures apart from pre-existing ones.
- **Authority** ([authority](references/authority.md)): the user's grant and host permissions bound everything; a denial stays denied.
- **Consent** ([defer](references/defer.md)): before handing work to an installed third-party skill with side effects (writes, update checks, telemetry, network), name them; ask once per session; consent is never saved. Evidence, guardrails and delivery authority are never deferred.
- **Memory** ([memory](references/memory.md)): read the host's own memory first; the core's file store serves only hosts without one, written only on an explicit save.

## 5. Sub-skills (from `stack.json`)

| Status | Sub-skills |
| --- | --- |
| Built, model-invocable | verify, debug, review, build, tdd, plan, ship, research, docs, security, design, qa, perf, office-hours, retro, health, onboard, deploy |
| Built, manual only (`disable-model-invocation: true`) | eval, orchestrate |
| Planned, model-invocable | spec, architecture, refactor, migrate, db, a11y, ci, infra |
| Planned, manual only | skill |
| Folded | plan-review is the `review` document mode |
| Not a skill | lang: a library under `references/lang/`; not routed |

Sub-skills embed the [Minimum Core](references/minimum-core.md).

## 6. References

[evidence](references/evidence.md), [isolation](references/isolation.md), [authority](references/authority.md), [handoff](references/handoff.md), [durable](references/durable.md), [delegation](references/delegation.md), [critique](references/critique.md), [context](references/context.md), [memory](references/memory.md), [profile](references/user-profile.md), [hosts](hosts/README.md), [craft](references/craft.md), [defer](references/defer.md).
