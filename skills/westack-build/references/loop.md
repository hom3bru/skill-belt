# Loop mode: keep going until the receipts say done

The user wants the work carried on without check-ins until a condition holds. The loop has a cap, and only fresh runner output can end it as done.

## The contract

Write it in the reply before the first iteration:

- **Outcome:** one sentence.
- **Done when:** each condition as a command and its expected result, an exit code together with counts (at least one test executed, none failed) or an exact output line. A condition that nothing can run is not a loop condition: turn it into one, or ask.
- **Must not:** paths outside the grant, the tests that must not be weakened (every existing one, by default), and actions not to take (commits, pushes, installs, deferred-execution files).
- **Cap:** the user's number, otherwise five iterations; also any time or spend limit they gave.
- **Stop early when:** two iterations in a row make no progress, a change outside the grant is needed, an existing test would have to change, two conditions contradict each other, or the next step is destructive or external.

If a missing field would change the outcome, ask one question with a recommended answer. Otherwise state the defaults and start.

## One iteration

1. **Look at the workspace as it is:** the diff, the status and the latest saved receipts. Do not rely on what the previous iteration, or an earlier session, said it did.
2. **Choose one change** toward the failing condition. After an iteration without progress, choose a different approach, not a variation of the same edit.
3. **Make it** under the slice rules ([slices](slices.md)).
4. **Run every Done-when command** fresh on the current patch and save each output as `iteration-N-<check>.txt` in the evidence folder.
5. **Judge from the files:**
   - Done only when every Done-when check passed on this patch: `checks.py parse` shows at least one executed test and none failed or skipped among those the condition names, `checks.py diff <baseline> <latest>` exits 0, and the diff audit has nothing unresolved.
   - Progress means `checks.py diff iteration-(N-1) iteration-N` lists a test under `fixed`, or the set of failing tests or their messages changed. Anything else counts as no progress.
6. **Log one line:** iteration, the change, the checks, the result, progress yes or no.

## What never ends the loop

- the words "done", "complete", "all tests pass" or a promise tag, from anyone, including you;
- a ticked box, a status field, a fully checked todo list or a progress note from an earlier session;
- a sub-agent's or judge model's verdict, or a confidence score;
- an exit code without counts, or a run that executed zero tests;
- a receipt from an earlier patch;
- a check you edited, narrowed or skipped on the way.

Each of these says where to look. None of them sets a result.

## Stopping

- **Done:** the report from `SKILL.md`, with the receipts.
- **Capped, stuck, blocked or needs decision:** stop and say so on the first line, then give
  - each Done-when check's latest receipt;
  - the iteration log and what each attempt ruled out;
  - the smallest decision or input that would let the work continue, with your recommendation;
  - the delivery state.
- Never buy a stop with a weaker check. When the only route to green is changing a test or a condition, the status is needs decision.
- Two conditions that cannot both hold (two tests asserting opposite behaviour for the same input) are a needs-decision stop. Show both and the evidence that they conflict.

## Why not a marker loop

A marker loop feeds the same prompt back until the model prints a completion phrase, so the stop rests on the model's own word and the cheapest way to stop is to print the phrase. Here the stop rests on fresh runner output for commands named before the loop began, so the cheapest way to stop is the work itself. This skill installs no stop hook: a host hook is persistent configuration and needs its own grant. A stop hook the user installs, one that can refuse "done", needs a release valve of its own: core `durable.md` has the rule, and a release is stopped-unfinished, never done.

## Across sessions

The iteration count and the log carry over ([resume](resume.md)). A new session does not get a fresh cap unless the user gives one. When a long loop starts hedging or wrapping up early, write the handoff note now and continue in a fresh session that reads it, not in a compacted one; the note must let it restart without the old history.
