# Document types (WD-5, WD-12 to WD-14, WD-16 to WD-18)

`prose.py lint` applies each rule at the level the document type sets: strict (its severity applies), relaxed (reported as a candidate) or skip (not audited, and the report lists it as skipped, never as clean). Pass `--type`, or let it infer one from the file name (CHANGELOG, README, AGENTS.md and CLAUDE.md, an `adr/` folder, release notes, migration and runbook names; anything else is `reference`). The full matrix is the `levels` of each rule in [rules.json](rules.json).

| Rule family | Strict | Relaxed | Skip |
| --- | --- | --- | --- |
| what no person types | every type | pasted lines in a reply | none |
| change narration | readme, guide, reference, runbook, instructions, as-built, ui | reply | changelog, release-notes, migration, adr, pr, commit |
| evidence (always candidates) | every other type | comparatives in a commit | causal and comparative checks in ui |
| secrets in arguments, implicit login | every other type | changelog (both); release-notes and migration (secrets) | none |
| as-built header | as-built | | every other type |
| line breaks | pr, reply | | every other type |
| UI strings | ui | | every other type |

## Current-state documents (WD-5)

A README, guide, reference page, runbook or instruction file describes the system as it is now, in the present tense. It does not narrate the change that produced it (`we added`, `now handles`, `this change adds`), describe its own revisions, or keep the previous version's story; a reader without the history gets archaeology. Change-bearing documents are exempt: changelogs, release notes, migration guides and decision records exist to narrate change, and "we" is fine in PR text and changelogs.

## As-built pages and doc maps (WD-12)

A page that describes the system as built carries three lines near the top: the commit it was last verified against, a last-updated date, and an applies-when line saying which version or setup it describes. `lint --type as-built` fails a page that lacks any of them. A docs map says that the code wins where the two disagree, and gives every count it states with the command that reproduces it and the commit it was taken at.

## Where docs live (WD-13)

Tracked documents live only under named roots. `lint --roots CONFIG` reads a file of this shape:

```json
{"format": "westack-docs-roots-1", "roots": ["docs/", "README.md"],
 "exceptions": [{"path": "SECURITY.md", "reason": "the forge reads it from the repository root"}]}
```

A file outside every root fails unless it is an exception. An exception is one exact file path with a written reason; a folder or a pattern is a hole, and the run stops (exit 2) rather than accept one.

## Policy and instruction files are tested like code (WD-14)

Instruction files, runbooks and setup guides tell agents and people what to do, so a test scans them for guidance that must never appear and names the file and line: a secret passed as the value of a command-line flag (it lands in process listings and shell history), signing in silently or with the user's browser session, and installing a package whose name matches the tool but is not it (a judgment check: read each install line against the project's own package name). westack's own pages are scanned the same way by `selflint`.

## UI copy (WD-16)

- A button names the outcome it causes (`Save changes`, `Publish`), never a generic `Submit` or `OK`.
- One action keeps one name through the flow: a `Publish` button is confirmed with `Published`, not `Done`.
- An error says what failed and one next step, without apology: `The file is over 25 MB. Choose a smaller file.`

`lint --type ui` reads one string per line (`key: text`) or a flat JSON object and checks the first two by their keys (button, action, toast, success, confirm, error); whether a whole flow keeps one name stays a judgment.

## Replies (WD-17)

When the thread is visible to the reader, a reply leads with the decision or verdict in its first sentence and leaves out the background the thread already holds. It keeps every new measurement, or links to where each is recorded; shortening a reply never drops a number.

## Line breaks at the destination (WD-18)

Before posting, check whether the destination shows a single newline as a break. Forge PR and issue bodies, comments and most chat tools do; Markdown files do not. For a destination that does, unwrap hard-wrapped paragraphs and keep intentional breaks (lists, addresses, a line ending in two spaces). `lint --type pr` and `--type reply` flag a wrapped paragraph; for a Markdown file the same text passes.

## Commit messages, PR bodies, changelogs

westack-ship owns their structure: the commit convention, the PR body sections and the changelog entry rules. This skill checks only the text inside them (meaning kept, nothing added, nothing no person types). No donor gave a README, ADR or changelog skeleton, and this skill invents none: follow the repository's own template, or ask.
