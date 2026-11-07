# Procedures (procedural memory)

A procedure is finished work saved as steps someone can follow again on a similar task: how this project cuts a release, how a flaky suite is quarantined, how a data fix was proven. It lives in the host's own memory, in its format, never a second store ([memory](memory.md)), and is written only on the user's explicit save.

## Saving one

Only after the work is done and its checks passed, and only when the user says to keep it ("remember how we did this"). Write one memory entry:

```markdown
---
name: release-a-skill-version
description: Procedure: cutting a westack skill version (changelog, version, package check)
metadata:
  type: project
  procedure: westack-procedure-1
---

## When it applies
Bumping one skill's version after its tests pass, on this repository.

## Steps
1. Bump `metadata.version` in the skill's SKILL.md.
2. Add the CHANGELOG entry under the stack version.
3. Run the package check.

## Checks that proved it
- `python -B skills/westack/scripts/validate.py package skills/westack-qa`: exit 0 (2026-11-04)

## Revision
bb709c1 on claude/westack-1.0

## Expiry
2027-02-04, or sooner when validate.py's package check changes

## Trust
user-confirmed: the user asked to save it after the run
```

`python scripts/procedure.py <entry.md> [--today YYYY-MM-DD]` checks it: the host's front matter with `metadata.procedure: westack-procedure-1`, at least two numbered steps, each check with its result, a revision, an expiry date (with `--today`, an expired entry fails), a trust mark ([memory](memory.md)) and no secret. Add its one-line pointer to the host's memory index as the host's rules say. Steps that needed a grant say so; the entry never carries the grant forward.

## Recalling one

Search the host's memory for procedures whose "When it applies" matches the task, and cite the one you use. Before relying on it, re-run its checks at today's revision: a procedure is a lead, never a receipt. Past its expiry, or when its revision or the files it names have changed, revalidate it first and update or retire the entry, on a save. A procedure grants nothing: each step that pushes, deploys or installs needs today's grant.

Provenance: gbrain's Memorable procedures at the mirror pin (absorption.json `gbrain.memorable`), kept in the host's memory rather than a new store.
