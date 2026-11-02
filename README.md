# Skill Belt

[![Verify skills](https://github.com/hom3bru/skill-belt/actions/workflows/verify.yml/badge.svg?branch=codex%2Fskill-belt)](https://github.com/hom3bru/skill-belt/actions/workflows/verify.yml)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](#verification)
[![Node.js 24](https://img.shields.io/badge/Node.js-24-5FA04E?logo=nodedotjs&logoColor=white)](#verification)

Practical agent capabilities for engineering work, source research, collaboration, and source-grounded job searches and applications.

## Jobscura

[Start with Jobscura](skills/jobscura/SKILL.md) for a complete job-search and
application toolkit. Its six workflows cover [intake and fit assessment](skills/jobscura/skills/application-intake/SKILL.md),
[tracking and deadlines](skills/jobscura/skills/application-tracking/SKILL.md),
[application history](skills/jobscura/skills/application-history/SKILL.md),
[writing and revision](skills/jobscura/skills/application-writing/SKILL.md),
[reviewed application packets](skills/jobscura/skills/application-packet/SKILL.md), and
[interview preparation](skills/jobscura/skills/interview-preparation/SKILL.md).

Use the [private-context setup](skills/jobscura/context/README.md),
[public schema](skills/jobscura/context/user-context.schema.json) and
[fictional example](skills/jobscura/context/user-context.example.json) to select
your own context explicitly. Keep the real context outside Git and the installed
toolkit; `JOBSCURA_CONTEXT_FILE` holds only its local path. Credentials stay in
separate secret storage. Jobscura does not install a background scheduler.

## Skills

| Skill | Purpose | Output |
| --- | --- | --- |
| [adopt-adapt](skills/adopt-adapt/SKILL.md) | Evaluate outside work for an existing project. | An evidence-backed adopt, adapt, or discard decision and transfer plan. |
| [Frankenmine](skills/frankenmine/SKILL.md) | Design a tool from useful mechanisms across sources. | Donor research, architecture alternatives, component contracts, and an implementation and evaluation plan. |
| [westack](skills/westack/SKILL.md) | Investigate, design, build, repair, review, or verify an engineering task. | A scoped workflow, optional shared task record, and evidence-based outcome. |
| [Carrier Pigeon](skills/carrier-pigeon/SKILL.md) | Exchange local agent messages, or have native Claude and Codex automatically build, cross-review, fix and integrate a coding task. Its four [sub-skills](skills/carrier-pigeon/skills/) also support explicit research, audit, design and build protocols. | Threaded replies and receipts; one automatic native build completed planning, both authors, genuine cross-review repair, re-review and guarded local integration. See [qualification limits](skills/carrier-pigeon/tests/live/README.md). |
| [Jobscura](skills/jobscura/SKILL.md) | A cohesive job-search and application toolkit with [loadable private user context](skills/jobscura/context/README.md). | [Intake](skills/jobscura/skills/application-intake/SKILL.md), [tracking](skills/jobscura/skills/application-tracking/SKILL.md), [history](skills/jobscura/skills/application-history/SKILL.md), [writing](skills/jobscura/skills/application-writing/SKILL.md), [reviewed packets](skills/jobscura/skills/application-packet/SKILL.md), and [interview preparation](skills/jobscura/skills/interview-preparation/SKILL.md). |
| [Rule Or Reason](skills/rule-or-reason/SKILL.md) | Identify opportunities to replace LLM workflow decisions with explicit algorithms, then construct and evaluate authorized candidates. | A scoped conversion decision, applicability boundary, counterexamples and evaluation evidence; partial conversion and retained reasoning are valid outcomes. |

Carrier Pigeon uses a configurable generic `user` identity. Read its
[compatibility guide](skills/carrier-pigeon/references/identity.md) before selecting
an existing mailbox; existing messages, signing keys and approval semantics are
preserved through explicit private configuration.

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

**Build together automatically**

```text
Use Carrier Pigeon to have Claude and Codex add CSV export to this project.
Have them build their parts, cross-review, fix findings, run the integration
checks and apply the result locally without me managing the handoffs.
```

The [automatic build workflow](skills/carrier-pigeon/references/automatic-build.md) runs in the background with a durable handle, separate worktrees, bounded repair rounds and publication conflict checks. It preserves the original Git index and unrelated edits. Pushes, deployment and new dependencies are outside the default scope.

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

**Find and test algorithmic alternatives**

```text
Read skills/rule-or-reason/SKILL.md and inspect this LLM workflow.
Identify bounded algorithmic alternatives and design a comparison
before implementing changes. Preserve evidence and failure behavior.
```

Rule Or Reason uses the recipient's existing language and tools. Its optional Python helper describes supplied prediction records; it does not execute arbitrary source or establish truth from teacher agreement. Reading, parsing, execution and evaluation support are reported separately.

## Verification

Requirements for the full verification suite:

- Python 3.10+.
- Node.js 24 for westack's authored JavaScript test fixtures.
- No third-party Python packages; helpers and verification scripts use the standard library.

Run from the repository root:

```sh
python -B scripts/verify.py
```

The verifier checks repository structure, local links, and byte manifests, then runs the collection tests and all six skill suites. Raw results are written to a temporary directory; use `--output <new-directory>` to choose a new output directory. [GitHub Actions](.github/workflows/verify.yml) runs the same command on Linux and Windows.

On Windows, only `test_research.ResearchTests.test_linked_source_entry_is_rejected` may be skipped when its reason is `symlink creation unavailable`; this is reported as `passed-with-platform-limitation`. Linux must run it. Other skips, empty suites, and failures are rejected.

## Limitations

These skills are experimental. Tests cover helper behavior, contracts, malformed inputs, evidence consistency, replay, provenance, and authored fixtures. They do not establish general agent effectiveness, truthful observations, legal clearance, or native host security enforcement. Full model and host qualification remains incomplete.

## License and attribution

No open-source license is granted. Existing ownership and third-party rights are preserved; see [NOTICE](NOTICE.md).

Source studies and prior art are documented with each skill. No third-party donor runtime is bundled. [Provenance](docs/provenance.md) and the skill manifests record the distributed snapshots and their published-byte identities.
