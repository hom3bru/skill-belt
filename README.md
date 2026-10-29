# Skill Belt

[![Verify skills](https://github.com/hom3bru/skill-belt/actions/workflows/verify.yml/badge.svg?branch=codex%2Fskill-belt)](https://github.com/hom3bru/skill-belt/actions/workflows/verify.yml)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](#verification)
[![Node.js 24](https://img.shields.io/badge/Node.js-24-5FA04E?logo=nodedotjs&logoColor=white)](#verification)

Agent skills for evaluating existing work, designing tools from multiple sources, and completing engineering tasks with verifiable results.

## Skills

| Skill | Purpose | Output |
| --- | --- | --- |
| [adopt-adapt](skills/adopt-adapt/SKILL.md) | Evaluate outside work for an existing project. | An evidence-backed adopt, adapt, or discard decision and transfer plan. |
| [Frankenmine](skills/frankenmine/SKILL.md) | Design a tool from useful mechanisms across sources. | Donor research, architecture alternatives, component contracts, and an implementation and evaluation plan. |
| [westack](skills/westack/SKILL.md) | Investigate, design, build, repair, review, or verify an engineering task. | A scoped workflow, optional shared task record, and evidence-based outcome. |

westack (then called estack) was renamed in 0.3.1, with no change in behaviour.

Each skill works independently. Loading a skill does not install a daemon, grant permissions, or authorize implementation or publication.

## Quick start

```sh
git clone https://github.com/hom3bru/skill-belt.git
cd skill-belt
```

Open the repository in your agent host, then explicitly load the relevant `SKILL.md`:

```text
Read skills/adopt-adapt/SKILL.md and use it to assess this repository
for my existing project. Identify transferable mechanisms and recommend
what to adopt, adapt, or discard.
```

## Installation

To make a skill available in another project, copy its **entire directory** from `skills/` into your host's skills directory. Keep references, scripts, contracts, and fixtures together. Check for an existing installation first and preserve local changes.

| Host | Project-local destination |
| --- | --- |
| Codex | `.agents/skills/<name>` |
| Claude Code | `.claude/skills/<name>` |
| Cursor | `.cursor/skills/<name>` |

Discovery and invocation depend on the host; see each skill's host notes. Explicitly reading a skill's `SKILL.md` is also supported as a manual invocation.

## Usage

Give the agent a concrete goal and the relevant sources or project context.

**Design from multiple sources**

```text
Read skills/frankenmine/SKILL.md and use it to design a tool from these sources.
Compare composition with the strongest existing solution and a minimal fresh build.
Produce an implementation and evaluation plan before making changes.
```

**Investigate and repair**

```text
Read skills/westack/SKILL.md and use it to repair this failing behavior.
Inspect the relevant code, make the smallest useful correction, and verify the result.
```

For longer-running work, westack can [start a canonical task record](skills/westack/examples/start-task.md). Frankenmine can [continue an existing synthesis](skills/frankenmine/references/continue-synthesis.md) using a prior donor-decision manifest.

## Verification

Requirements for the full verification suite:

- Python 3.10+.
- Node.js 24 for westack's authored JavaScript test fixtures.
- No third-party Python packages; helpers and verification scripts use the standard library.

Run from the repository root:

```sh
python -B scripts/verify.py
```

The verifier checks repository structure, local links, and byte manifests, then runs the collection tests and all three skill suites. Raw results are written to a temporary directory; use `--output <new-directory>` to choose a new output directory. [GitHub Actions](.github/workflows/verify.yml) runs the same command on Linux and Windows.

On Windows, only `test_research.ResearchTests.test_linked_source_entry_is_rejected` may be skipped when its reason is `symlink creation unavailable`; this is reported as `passed-with-platform-limitation`. Linux must run it. Other skips, empty suites, and failures are rejected.

## Limitations

These skills are experimental. Tests cover helper behavior, contracts, malformed inputs, evidence consistency, replay, provenance, and authored fixtures. They do not establish general agent effectiveness, truthful observations, legal clearance, or native host security enforcement. Full model and host qualification remains incomplete.

## License and attribution

No open-source license is granted. Existing ownership and third-party rights are preserved; see [NOTICE](NOTICE.md).

Source studies and prior art are documented with each skill. No third-party donor runtime is bundled. [Provenance](docs/provenance.md) and the skill manifests record the distributed snapshots and their published-byte identities.
