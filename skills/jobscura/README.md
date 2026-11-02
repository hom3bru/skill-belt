# Jobscura 0.4.0

Jobscura is a job-search and application toolkit in [Skill Belt](https://github.com/hom3bru/skill-belt).
It connects opportunity intake, one canonical tracker, application history,
evidence-grounded writing, reviewed attachment packets and interview preparation.

Begin with [Jobscura](SKILL.md), or load any of its six linked workflows directly.
Copy this whole directory into the host's skills directory to retain references
and helpers. The host controls automatic discovery of nested skills; the root
entrypoint and capability table provide an explicit route on every host.

## Loadable user context

[Setup and privacy](context/README.md) explains the versioned public schema and
fully fictional example. Actual context stays outside this repository and the
installed toolkit. `JOBSCURA_CONTEXT_FILE` holds only its absolute local path.
The loader validates one explicitly selected JSON file, returns context to an
authorized caller in memory, and opens none of its source references. Its CLI
prints only validation status and section names. No real user profile ships here.

## Tools and verification

Python 3.10+ is sufficient for context validation, JSON/CSV/TSV packet workflows,
packaging and tests. XLSX matching uses already-installed `openpyxl`; it is optional
and never installed automatically. The packet helper version is 0.2.1; the toolkit
version is 0.4.0. They use separate compatibility versions.

```sh
python -B scripts/user_context.py --context /absolute/private/jobscura/user-context.json
python -B -m unittest discover -s tests -v
python -B -m unittest discover -s skills/application-packet/tests -v
python -B scripts/package.py --output /absolute/output/jobscura-0.4.0.zip
```

The [packet command guide](skills/application-packet/references/command-guide.md)
covers source capture, exact upload requirements, byte-bound review, assembly and
validation. Packets and personal documents stay in private work locations.
The toolkit supplies tracking procedures, not an independent background scheduler;
reminders require actual authorized host automation and verified send receipts.

## Packaging and continuity

The product display name is Jobscura. The package identifier remains
`application-assistant-workflows`, and all six existing skill names are retained
so the same installed plugin can be updated. The root Jobscura entrypoint is the
Skill Belt discovery route; plugin metadata exposes the six workflows in `skills/`.
The deterministic ZIP includes only the hash-pinned public inventory. Extra or
changed files stop packaging. No private audit archive or personal records ship.

Derived from the 0.3.0 workflow source; see [changes](CHANGELOG.md) and the root
[ownership notice](NOTICE.md). Tests verify authored contracts and helper behavior,
not general agent effectiveness or native host enforcement.
