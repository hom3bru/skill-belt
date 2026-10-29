# westack 0.3.1 — experimental portable skill

A manually usable engineering workflow with one discoverable [SKILL.md](SKILL.md), nine selectively loaded modules and a shared task/evidence/review contract. It uses the host's tools and permissions. It installs no runtime, hooks, model routing, telemetry or donor packs.

Maturity: phase 1 skill with a small phase 2 consistency validator and deterministic local fixtures. Live model evaluations, independent human rubrics and actual host qualification are not-run. No comparative efficacy or multi-host behavior claim.

0.3.1 is the 0.3.0 build of westack (then called estack), renamed with no behaviour change (see [lineage](provenance/lineage.json)). It binds records to the observed repository: `validate.py fingerprint` hashes a stored set of observed paths (minus caches and dependencies) and reads Git HEAD from disk, `snapshot` keeps tested files as hash-named evidence, `receipt` and `refresh` write the next numbered record version without hand-editing, and `reconcile` exposes the uncertain-action recommendation. Staleness follows content (patch and scope), so a commit does not invalidate evidence. Finish conditions only get stricter within a scope, negative controls must rerun the same check, and `task --chain` checks every version in order. Counts and per-case mapping are in [acceptance results](tests/acceptance-results.json). All 20 pilot cases retain their deterministic fixture mapping; full independent pilot qualification remains 19 not-run, with the host denied-path case blocked/unsupported. Bounded development trials are separate evidence.

## Manual installation (not performed)

Inspect [rights/provenance](provenance/RIGHTS.md) and [host limits](hosts/README.md). Unzip the release into a temporary location and review it. In a project you choose, copy the entire `westack` folder into one supported skill location:

- Codex: `<project>/.agents/skills/westack/`.
- Claude Code: `<project>/.claude/skills/westack/`.
- Cursor: `<project>/.cursor/skills/westack/` (or its documented `.agents/skills/` location).

Keep `SKILL.md`, references, contracts and scripts together. Check for an existing westack folder first; do not overwrite unrelated work. Reload discovery as your installed host requires and inspect the skill picker. Claude/Cursor document slash selection; Codex supports its skill selection surface. If discovery is unavailable, explicitly ask the host to read `westack/SKILL.md` and follow the relevant references; label this as manual loading, not a successful native installation. No global installation is needed. Remove only the copied folder to uninstall.

These locations were checked against [OpenAI](https://learn.chatgpt.com/docs/build-skills), [Claude Code](https://code.claude.com/docs/en/skills) and [Cursor](https://cursor.com/docs/skills) documentation on 2026-10-26; installation/invocation has not been tested.

## Use

Examples: “Use westack to fix this one failing arithmetic test”; “westack investigate: find the cause without editing”; “westack review this patch against the supplied acceptance criteria.” Clear tiny work takes the short path. Missing independent reviewers or sandbox boundaries remain explicit limitations.

Python 3.10+ is optional for the validator; the test suite also requires an already installed Node with node:test support. This build used Python 3.14.3 and Node 24.13.1 on Windows. The instruction skill can be read without either. No dependencies are installed. From this folder run:

```text
python scripts/validate.py package .
python tests/run.py
```

To check a persistent task, use the command in [SKILL.md](SKILL.md): `validate.py task` with `--repo` recomputes patch and revision from disk, and you supply the scope label and an authorized evidence root. Scripts execute no recorded task commands. An exit of zero means consistency-only, not semantic proof.

See [examples](examples/tiny-repair.md), [contract](contracts/README.md), [evaluation](tests/EVALUATION.md), [source decisions](provenance/decisions.json), [acceptance results](tests/acceptance-results.json), and [changelog](CHANGELOG.md). The full donor corpus is intentionally absent.

For a persistent build, [start a canonical task](examples/start-task.md) with `validate.py init`; it records context without granting permissions or inventing completed work. New source qualification for three of the twenty decision units is in [continuation findings](provenance/continuation.md). The remaining units retain their previous inspection depth.

