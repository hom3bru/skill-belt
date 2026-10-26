# Estack 0.2.0 — portfolio edition — experimental portable skill

A manually usable engineering workflow with one discoverable [SKILL.md](SKILL.md), nine selectively loaded modules and a shared task/evidence/review contract. It uses the host's tools and permissions. It installs no runtime, hooks, model routing, telemetry or donor packs.

Maturity: phase 1 skill with a small phase 2 consistency validator and deterministic local fixtures. Live model evaluations, independent human rubrics and actual host qualification are not-run. No comparative efficacy or multi-host behavior claim.

This continuation adds canonical task startup, source-qualified harness/recovery guidance, and stricter evidence, replay and package checks. The preserved v0.1.0 had 43 deterministic tests. The current suite has 73 cases, including 24 adversarial relationship/path cases and six task-starter checks. All 20 pilot cases retain their deterministic fixture mapping; full independent pilot qualification remains 19 not-run and E12 blocked/unsupported. Bounded development trials are separate evidence.

## Manual installation (not performed)

Inspect [rights/provenance](provenance/RIGHTS.md) and [host limits](hosts/README.md). Unzip the release into a temporary location and review it. In a project you choose, copy the entire `estack` folder into one supported skill location:

- Codex: `<project>/.agents/skills/estack/`.
- Claude Code: `<project>/.claude/skills/estack/`.
- Cursor: `<project>/.cursor/skills/estack/` (or its documented `.agents/skills/` location).

Keep `SKILL.md`, references, contracts and scripts together. Check for an existing estack folder first; do not overwrite unrelated work. Reload discovery as your installed host requires and inspect the skill picker. Claude/Cursor document slash selection; Codex supports its skill selection surface. If discovery is unavailable, explicitly ask the host to read `estack/SKILL.md` and follow the relevant references; label this as manual loading, not a successful native installation. No global installation is needed. Remove only the copied folder to uninstall.

These locations were checked against [OpenAI](https://learn.chatgpt.com/docs/build-skills), [Claude Code](https://code.claude.com/docs/en/skills) and [Cursor](https://cursor.com/docs/skills) documentation on 2026-10-26; installation/invocation has not been tested.

## Use

Examples: “Use estack to fix this one failing arithmetic test”; “estack investigate: find the cause without editing”; “estack review this patch against the supplied acceptance criteria.” Clear tiny work takes the short path. Missing independent reviewers or sandbox boundaries remain explicit limitations.

Python 3.10+ is optional for the validator; the test suite also requires an already installed Node with node:test support. This build used Python 3.14.3 and Node 24.13.1 on Windows. The instruction skill can be read without either. No dependencies are installed. From this folder run:

```text
python scripts/validate.py package .
python tests/run.py
```

To check a persistent task, use the command in [SKILL.md](SKILL.md) with host-observed revision/scope/patch and an authorized evidence root. Scripts execute no recorded task commands. An exit of zero means consistency-only, not semantic proof.

See [examples](examples/tiny-repair.md), [contract](contracts/README.md), [evaluation](tests/EVALUATION.md), [source decisions](provenance/decisions.json), [acceptance results](tests/acceptance-results.json), and [changelog](CHANGELOG.md). The full donor corpus is intentionally absent.

For a persistent build, [start a canonical task](examples/start-task.md) with `validate.py init`; it records context without granting permissions or inventing completed work. New source qualification for three of the twenty decision units is in [continuation findings](provenance/continuation.md). The remaining units retain their previous inspection depth.

