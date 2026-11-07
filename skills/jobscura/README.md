# Jobscura 0.5.0

Jobscura is a job-search toolkit in Skill Belt. It covers
the whole cycle: finding roles, fit assessment, one canonical tracker with deadline countdowns,
application history, evidence-checked writing, reviewed upload packets, networking drafts,
interview practice, and offer comparison and negotiation. Wherever the work is mechanical,
deterministic helpers do it instead of the model's judgment.

Begin with [Jobscura](SKILL.md), or load any of its nine linked workflows directly. To keep the
references and helpers, copy this whole directory into the host's skills directory. The host
decides how nested skills are discovered; the root entrypoint and its routing table give an
explicit route on every host.

## What it does

| Area | Workflow | Deterministic helper |
| --- | --- | --- |
| Discovery | [opportunity-discovery](skills/opportunity-discovery/SKILL.md) | ATS recognition and public board endpoints (`posting_intel.py`) |
| Fit and triage | [application-intake](skills/application-intake/SKILL.md) | `posting_intel.py`, `grounding.py coverage` |
| Tracking | [application-tracking](skills/application-tracking/SKILL.md) | `deadlines.py` (time zone and daylight-saving aware, reminder deduplication) |
| History | [application-history](skills/application-history/SKILL.md) | none |
| Writing | [application-writing](skills/application-writing/SKILL.md) | `grounding.py claims` (claim ledger), `ats_lint.py` |
| Upload packets | [application-packet](skills/application-packet/SKILL.md) | `application_packet.py` (hash-bound reviews, never overwrites) |
| Outreach | [networking-outreach](skills/networking-outreach/SKILL.md) | none |
| Interviews | [interview-preparation](skills/interview-preparation/SKILL.md) | `grounding.py coverage` for story mapping |
| Offers | [offer-negotiation](skills/offer-negotiation/SKILL.md) | `offer_compare.py` (vesting, cliffs, equity at 0-150%) |

Cross-cutting rules live in [integrity and safety](references/integrity-and-safety.md):
hidden and AI-directed text in postings (detection canaries, prompt injection, Unicode tag
smuggling), employer AI-use policies, scam screening, fairness and honesty limits. The
[output formats](references/output-formats.md) page defines the shape of each deliverable.

## Loadable user context

[Setup and privacy](context/README.md) explains the versioned public schema (v1 and v2) and the
fully fictional example. Your actual context stays outside this repository and outside the
installed toolkit. `JOBSCURA_CONTEXT_FILE` holds only its absolute local path. The loader validates
one explicitly selected JSON file, returns it to an authorised caller in memory, and opens none of
its source references. Version 2 adds optional monitoring cadences and search preferences. These
are conventions, never permissions.

## Tools and verification

Python 3.10+ is enough for every helper, the packaging step and the tests. Only the standard
library is used and nothing is fetched. XLSX matching uses `openpyxl` if it is already installed;
it is never installed automatically. Timezone-aware planning needs the host's IANA database. On
Windows, the `tzdata` package provides it. See the [helper index](references/helpers.md). The
packet helper is version 0.3.0 and the toolkit is version 0.5.0; they keep separate compatibility
versions.

```sh
python -B scripts/user_context.py --context /absolute/private/jobscura/user-context.json
python -B scripts/posting_intel.py analyze --input posting.html --url https://example.org/jobs/1 --employer "Example"
python -B -m unittest discover -s tests -v
python -B -m unittest discover -s skills/application-packet/tests -v
python -B scripts/package.py --output /absolute/output/jobscura-0.5.0.zip
```

The unit suites check the helpers' authored behaviour. The [behavioural evals](evals/README.md)
check how an agent with Jobscura behaves (triggering, canaries, AI-use policies, fabrication,
scams, deadline arithmetic, false action claims) using `claude plugin eval`. That run costs
model usage, and it is not part of the offline verification.

## Packaging and continuity

The product display name is Jobscura. The package identifier remains
`application-assistant-workflows`, and all six original skill names are kept so that an installed
plugin can be updated in place. Three workflows were added in 0.5.0. The root Jobscura entrypoint
is the Skill Belt discovery route, and the plugin metadata exposes the workflows in `skills/`. The
deterministic ZIP contains only the hash-pinned public inventory. Extra or changed files stop the
packaging, and local eval results are never packaged. No private audit archive or personal records
ship.

Derived from the 0.3.0 workflow source; see the [changes](CHANGELOG.md) and the root
[ownership notice](NOTICE.md). The tests verify authored contracts and helper behaviour, not general
agent effectiveness or native host enforcement.
