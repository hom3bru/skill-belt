# Developer experience (DX) rubric

Shared by westack-review's DX lens (a plan or spec for something developers use) and westack-qa's live DX audit (the built thing, tried). Use it when the users are developers: an API, a CLI, an SDK, a library, a framework, a developer tool or an agent skill.

## Persona first

Name one developer before scoring: who they are, what they want done, their environment (language, operating system, tools) and what they already know. Every score is for that person.

## The journey

Discover, evaluate, install, hello world, integrate, debug, upgrade, scale. Walk it as that developer; each step where they would stop, search or ask someone is a friction point.

## Eight dimensions

| Id | Dimension | A 10 looks like |
| --- | --- | --- |
| getting-started | first run to a working result | install and hello world without docs detours, sign-ups or a sales call |
| api-cli | the API, CLI or SDK surface | names and defaults a developer guesses right; the simple case is real, not a toy; escape hatches exist |
| errors | errors and debugging | each error says what happened, why, and the exact next command or what to ask a human |
| docs | documentation and learning | findable, runnable examples, versioned, matching the code |
| upgrade | upgrades and migration | boring: changelogs, deprecation warnings, migration guides or codemods |
| environment | the development environment | works across the operating systems and editors the persona uses; fast local loop |
| community | community and ecosystem | answers findable; issues triaged; examples from others |
| measurement | measuring DX | the team can see where developers drop off and hear from them |

## Scores

| Score | Meaning |
| --- | --- |
| 9-10 | best in class; developers recommend it |
| 7-8 | good; minor gaps |
| 5-6 | works, with friction developers tolerate |
| 3-4 | poor; developers complain and adoption suffers |
| 1-2 | broken; most give up on the first try |
| 0 | not addressed |

For each dimension say what a 10 looks like for this product, then the gap. Mark the evidence: `tested` (you ran it), `partial` (you ran part), `inferred` (you read it). A plan review is inferred throughout; nothing in it ran.

## Time to hello world (TTHW)

| Tier | Minutes |
| --- | --- |
| champion | under 2 |
| competitive | 2 to 5 |
| needs-work | over 5, up to 10 |
| red-flag | over 10 |

Count from "I found this" to the first result the persona wanted, with the steps listed.

## The record

`westack-dx-record-1` JSON: `kind` (plan or live), `product`, `persona` (who, goal, environment, knows), `tthw` (minutes, tier, evidence, steps), `dimensions` (each id once: score, evidence, gap, notes) and `overall` (the mean score, one decimal). The skills' helpers check it.

Provenance: ideas from gstack's plan-devex-review and devex-review rubric (absorption.json `gstack.plan-devex-review`, `gstack.devex-review.live`), in westack's words.
