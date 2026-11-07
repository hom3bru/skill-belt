# Hypotheses and the elimination ledger

## Before any probe

List three to five candidate causes, ordered by how likely each is and how cheap it is to test. Give each a prediction: "if this is the cause, <probe> shows <result>; otherwise it shows <other result>". A candidate with no prediction is a hunch: sharpen it or drop it. If the user is present, show the list (they may already know which are dead) and carry on without waiting.

Sources for candidates: what changed recently, where the bad value first appears, differences from a working sibling, and the usual suspects (missing or null values, stale caches, the wrong configuration being loaded, shared state, time and time zones, text encoding, binary floating point, boundary off-by-ones, concurrency). Always list the check itself, or the data it reads, as a candidate (a key reused across entities, a filter at the wrong grain, a stale fixture), and audit the verification's premise in the first round, before blaming the code.

## Probing

- One hypothesis and one changed variable per probe.
- Before running, make sure the output will reach you: not discarded, not cut short, not a log left from an earlier run.
- Read all of the output. When it contradicts the hypothesis, the output wins.
- Record values at the two or three decision points that separate the candidates rather than logging everything. Mark each temporary log line with one unique tag (for example `DBG-7f3a`) so a single search finds them all for removal.
- Where a debugger or REPL is available, a breakpoint usually beats a print.

## The ledger

Keep it in the reply, the handoff note or the task record, never only in memory. One row per hypothesis:

| # | Hypothesis | Prediction | Probe (exact command) | Result | Verdict |
| --- | --- | --- | --- | --- | --- |
| H1 | the session cache serves a stale token | the reproduction passes once the cache is cleared first | `node scripts/repro.js --clear-cache` | still fails, same error | ruled out |

Verdicts: confirmed, ruled out, inconclusive (with what would settle it), untested. A ruled-out row keeps the output that killed it, so no later context retests it. A rare cause is not ruled out by one failed attempt to trigger it (inconclusive); only the system's own numbers, named in the row, show it cannot happen. With the core's task record, write each verdict as an `observations` entry (kind `ruled-out`, `confirmed` or `surprise`, citing its receipt); entries are append-only; correct one by adding another. Anything that overturned an assumption is a surprise. Give each row's evidence its strength in the core's words, with no second scale: a reproduction you ran is observed; a primary artefact (source at a revision, a saved log) or independent sources that agree is present; one source's inference, a clue or a hunch is claimed. Say why a row moved down, and run a check on a contested one.

## Confirming

A cause is confirmed when its prediction came true, the rival candidates are ruled out, and a counterfactual flips the symptom: change only the suspected cause and the reproduction passes; undo the change and it fails again. In diagnose mode the counterfactual runs on a temp copy or inline. Without it the cause is probable. A claim never moves up a level because it feels right.

## When progress stalls

- The same probe returned the same result twice: change the probe.
- Two rounds of reasoning with no new observation between them: run a probe instead of thinking further.
- Three hypotheses ruled out, or two fixes that failed: name the assumption every one of them relied on (the input arriving here is well formed; this is the configuration actually loaded; the test runs the code I think it runs) and test that assumption directly.
- Failures that keep returning in the same files, or a fix that moves the problem somewhere else, point at the design rather than a line. Say so, and ask before any larger change.
- At the attempt cap, stop with the ledger and an honest status.

## Using history

With a known-good revision, `git bisect run <reproduction>` finds the first bad commit mechanically. Bisect moves the checkout, so run it in a separate clone or worktree, and in diagnose mode only after the user agrees. The first bad commit is a lead: what it changed still needs a confirming probe.
