# Skill Belt

Three complementary agent skills for deciding what to reuse, designing coherent tools from multiple sources, and carrying engineering work through to a verifiable result.

Built by **Matt Kolkin**, with agent-assisted research, implementation, adversarial review, and testing. The focus is practical judgment: inspect the source, preserve the user's intent, make a concrete change, and show evidence for what works.

| Skill | Use it when | It produces |
| --- | --- | --- |
| [adopt-adapt](skills/adopt-adapt/SKILL.md) | You want to assess outside work for an existing project. | A source-backed adopt, adapt, or discard decision and a concrete transfer plan. |
| [Frankenmine](skills/frankenmine/SKILL.md) | You want to create or continue a product built from useful mechanisms across sources. | Donor research, architecture alternatives, component contracts, and an authorized implementation and evaluation path. |
| [estack](skills/estack/SKILL.md) | You have an engineering task to investigate, design, build, repair, review, or verify. | A proportionate workflow, shared task record when useful, and an evidence-based outcome. |

The skills can be used independently. None installs a daemon, grants permissions, or requires another skill to perform ordinary source analysis.

## Try a skill

Give your agent a concrete goal and explicitly load the relevant `SKILL.md`:

```text
Use adopt-adapt to assess this repository for my existing project.
Find transferable mechanisms, inspect the source, and make a grounded recommendation.
```

```text
Use Frankenmine to design a new tool from these sources.
Compare composition with the strongest existing solution and a minimal fresh build.
Implement the agreed slice in this isolated output directory and test it.
```

```text
Use estack to repair this failing behavior.
Inspect the relevant code, make the smallest useful correction, and verify the result.
```

For persistent work, estack can [start its canonical task record](skills/estack/examples/start-task.md). Frankenmine can [continue an existing synthesis](skills/frankenmine/references/continue-synthesis.md) and register a prior donor-decision manifest.

## Installation

Clone the collection, then copy the **entire** selected skill directory into your host's skills directory. Keep its references, scripts, contracts, and fixtures together. Check for an existing installation before copying; preserve local changes.

```sh
git clone https://github.com/hom3bru/skill-belt.git
```

Common project-local destinations are `.agents/skills/<name>` for Codex, `.claude/skills/<name>` for Claude Code, and `.cursor/skills/<name>` for Cursor. Explicitly reading `skills/<name>/SKILL.md` is also a portable manual invocation. Native discovery and invocation remain host-dependent; see each skill's host notes.

## Verify the collection

Requires Python 3.10+ and Node.js 24 for the authored estack test fixtures. The helpers and collection verifier use Python's standard library; no Python packages are required.

```sh
python -B scripts/verify.py
```

The verifier checks the collection, local links and manifests, then runs every bundled skill suite. Raw outputs go to a temporary directory, or to a new directory selected with `--output`. [GitHub Actions](.github/workflows/verify.yml) runs the same command on Linux and Windows.

On Windows, one inherited symbolic-link test may report `symlink creation unavailable`; only that exact test/reason is allowlisted and reported as `passed-with-platform-limitation`. Linux must execute it. All other skips, empty suites, and failures are rejected.

Tests cover helper behavior, contracts, malformed inputs, stale or unrelated evidence, replay, provenance, and authored product fixtures. They do not establish general agent effectiveness, truthful observations, legal clearance, or host security enforcement. These are experimental skills; full model/host qualification remains incomplete.

## About this portfolio edition

This collection contains portable snapshots, not a dump of a personal workspace. Private project architecture, machine inventories, session identifiers, local audit transcripts, credentials, and installed host settings are excluded. The installed personal versions remain separate. The distribution changes and published-byte identities are recorded in [provenance](docs/provenance.md) and each skill's manifest.

The work draws on documented prior art and source studies; attribution and limitations remain with each skill. No third-party donor runtime is bundled. Existing ownership is preserved: **this repository does not grant an open-source license**. See [NOTICE](NOTICE.md).
