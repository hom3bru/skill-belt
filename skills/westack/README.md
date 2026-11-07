# westack core 1.0.0-alpha.0

The router and shared core of the westack skill stack: one discoverable [SKILL.md](SKILL.md) (explicit invocation only), the facility references it loads on demand, the optional task-record contract and its standard-library helpers. It uses the host's own tools and permissions. It installs no runtime, hooks, services, telemetry or third-party skills.

Maturity: alpha. Wave 0 built this core; wave 1 added `westack-eval`, `westack-verify`, `westack-debug`, `westack-review`, `westack-build` and `westack-tdd` beside it, then `westack-plan` and `westack-ship`, and `westack-orchestrate` (wave 3, manual only), `westack-research`, `westack-docs`, `westack-security` and `westack-design` (wave 3) followed; [stack.json](stack.json) lists these and the planned skills. Deterministic local tests cover the helpers and the contract. One Claude Code probe loaded the router; Codex is blocked and Cursor not-run ([hosts](hosts/README.md)). No efficacy or multi-host claim.

## Layout

| Path | What it is |
| --- | --- |
| `SKILL.md` | the router: owner choice, stack commands, shared rules, sub-skill invocation policy |
| `references/` | facility references (evidence, isolation, authority, guards, handoff, durable, delegation, critique, context, memory, craft, defer) and the core workflow modules (route, frame, inspect, plan, build, review, verify, finish, learn) |
| `references/minimum-core.md` | source of the Minimum Core block embedded in every sub-skill |
| `references/defer-map.json` | when a sub-skill may hand work to an installed third-party skill ([defer](references/defer.md)) |
| `contracts/` | the task-record contract (schema 1) and the defer-map schema |
| `scripts/` | helpers, standard library only, never running commands: `validate.py` (task-record CLI over `record.py`, `evidence.py`, `skillmeta.py`), `checks.py`, `registry.py`, `core_check.py`, `ruletest.py`, `build_core_block.py` |
| `hosts/` | host adapters and the capability matrix |
| `provenance/` | donor decisions, facility donors, rights, and the rename record (`lineage.json`) |
| `tests/` | the core suite (`python tests/run.py`) |

## Helpers

- `python scripts/validate.py package .` checks this package; the eight record commands are in [handoff](references/handoff.md) and [build](references/build.md).
- `python scripts/checks.py diff <baseline> <after>` compares saved test-runner outputs by test name ([evidence](references/evidence.md)).
- `python scripts/registry.py` lists installed skills from the documented host roots, as JSON.
- `python scripts/core_check.py --skill <sub-skill folder>` checks a sub-skill's core range.
- `python scripts/ruletest.py <rules.json>` checks that each guard rule matches its own must-match example and not its must-not example, and that a deny or ask rule also matches its unresolved, alternate and twin examples ([guards](references/guards.md)).
- `python scripts/build_core_block.py check` checks every sub-skill's embedded Minimum Core block byte for byte; `inject` rewrites them.

Python 3.10 or later runs the helpers; the suite also needs an installed Node with node:test support. This build used Python 3.14.3 and Node 24 on Windows. Scripts execute no recorded task commands, and an exit of zero means consistency, not semantic proof.

## Install

Use `tools/install.py` in the repository (dry run by default). By hand: copy this folder, without `tests/`, to one host skill root as `westack` (see [hosts](hosts/README.md)), after checking that no folder of that name exists. Remove only the copied folder to uninstall.

See the [contract](contracts/README.md), [source decisions](provenance/decisions.json) and [changelog](CHANGELOG.md). The evaluation notes (`tests/EVALUATION.md`) and the suite stay in the repository; an installed copy leaves out `tests/`.
