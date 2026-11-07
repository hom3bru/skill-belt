# Sync and drift (SS-105, SS-106)

Both modes compare documents with the code. Sync edits instruction files; drift only reports. Read instruction files as core `context.md` says, and where a file and the code disagree, the code's demonstrated behaviour wins and the mismatch is reported with file references.

## Sync: instruction files (SS-105)

Hierarchical instruction files (`AGENTS.md`, `CLAUDE.md` and their per-folder copies) owe an edit only when a change touched something an agent needs to know before working there:

- a boundary (what a folder owns, what may import what);
- a contract (an interface, a schema, a command and its flags);
- a pattern the code now follows, or a pitfall someone hit;
- a dependency added, removed or pinned.

An internal refactor that keeps all of these owes no edit. "Check AGENTS.md is still right" is a sync request: read the files, compare each statement with the code, and propose edits only where one of the above changed.

How to edit:

1. **Leaf first.** Start with the file closest to the changed code and move up only when the fact covers more than that folder.
2. **Shallowest node that covers it.** Each fact sits in the one file whose folder contains all the code it describes, and nowhere else.
3. **Once.** The same fact never appears in two files; a deeper file refines a shallower one, it does not repeat it.
4. **Scoped.** An instruction file is read by every later session, so each edit needs the user's grant for that file (core `authority.md`). Without it, deliver the edits as proposed text.

Report each file as edited, proposed or unchanged, with the change in the code that required each edit.

## Drift: documents against the source (SS-106)

A drift report compares each named document with the current source at a stated commit and lists differences only: what the document says, what the code does, and the file and line of each. Every document checked and found current gets an explicit line, `no drift (checked against <commit>)`, so a reader can tell "checked and current" from "not checked". A document that was not checked, or only partly, is listed as not checked with the reason; it never reads as no drift.

Counts and versions inside documents are checked against their source too: a stated number of tests, sections or supported versions is re-derived with the command that produces it, and the command is given beside the result.

Inventories are checked both ways. A document that lists a folder's files, tests or commands owes two facts: every item that exists is listed, and every listed item exists. Report each unlisted item and each stale row apart; one direction alone misses half the drift. For files, `prose.py inventory DOC FOLDER --glob "*.py"` does it. In a numbered series read in order, a document links only to earlier ones (`prose.py series FOLDER`).

Drift mode edits nothing. Fixing what it finds is a revise or a sync, on its own grant.
