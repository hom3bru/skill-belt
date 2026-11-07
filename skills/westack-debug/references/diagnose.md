# Diagnose mode (read-only)

The default whenever the user asks why something happens, asks you to investigate or find the cause, or has not asked for a fix. The deliverable is a diagnosis, not a patch.

## What read-only means

- No edits, new files or deletions inside the project: no scratch scripts, debug lines, test changes or notes files there. Git stays as you found it: no checkout, stash, bisect, worktree, branch or commit.
- Reading files and running the project's existing tests and commands is allowed. Prefer runs that leave nothing behind (for Python, `python -B`; switch off test-runner caches where a flag exists), and name any cache or build output a run created anyway.
- Probes run where the project is not: an inline command (`python -c`, `node -e`), a REPL or debugger session, or a copy of the relevant files in the system temp folder. Instrument the copy, never the original.
- If the host refuses writes outside the project, use inline probes. A refusal never makes the project folder acceptable for scratch work; ask instead.
- A step that needs a write in place (bisecting history, a log line in code that only runs where it is deployed) becomes a question to the user: the step, why it is needed, and the smallest scope.

## Steps

1. Say "diagnose mode: nothing in the project will change".
2. Run the loop in SKILL.md, steps 1 to 6.
3. Do the counterfactual of step 5 on the temp copy or inline: alter the suspected cause there, rerun the reproduction against it, and show the symptom change.
4. Delete the temp copy, or say where it is.

## Ending

Report as SKILL.md describes. Then ask one question, whether to fix it, with the recommended change: the file and line, the smallest edit, the regression test you would add, and what it would leave uncovered (for example the other sites the sweep found). A yes moves you to [fix mode](fix.md) for that change only.

When the user only wanted to know why, the question is an offer, not a gate.
