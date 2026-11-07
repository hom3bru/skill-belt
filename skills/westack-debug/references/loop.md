# The loop, steps 3 to 7

Read in both modes once step 2 has a reproduction. Steps 1 (pin the symptom) and 2 (reproduce before theorising) are on the start page.

3. **Narrow.** Files, then functions, then lines. Follow the bad value backwards to where it first goes wrong; compare with a working sibling or a known-good revision.
4. **Rank three to five falsifiable hypotheses,** each with the observation that would differ if it were false. Test one at a time, changing one thing per probe, and record every verdict; a read or probe that settles several counts for each ([hypotheses](hypotheses.md)).
5. **Confirm with a counterfactual.** Change the suspected cause alone and the symptom flips; restore it and the symptom returns. Without that, the cause is probable, not confirmed. In fix mode, the regression test's red before a fix touching only that cause, and green after, is the counterfactual.
6. **Sweep for the same defect.** Turn the confirmed defect into a search pattern, look for it elsewhere in the agreed scope, and mark each hit as the same defect, safe, or unsure.
7. **Stop or fix.** Diagnose mode reports and asks. Fix mode continues in [fix](fix.md).

## Leads are not evidence

The line in the stack trace, an alarming comment, a TODO, the latest commit message and a library that must surely be buggy tell you where to look, not what is wrong. A hypothesis is ruled in only by a probe whose result would have come out differently if it were false. Inspect the data passing through the code, not only which code ran, and check for state left over from earlier runs. With no report and no change to read intent from (an unattended bug hunt), count a defect only when a comment, document, type or existing test states the intended behaviour; skip a bug another branch is already fixing, and list unprovable suspicions in the handoff.

## Stop rules

- The same probe gave the same result twice: change the probe rather than run it again.
- The same action failed with the same error twice: that approach is finished.
- Three hypotheses ruled out, or two fixes that failed on one shared assumption: write the assumption down and test it directly before anything else.
- At the attempt cap (five hypothesis rounds or three fix attempts unless the user set another): stop, report inconclusive or blocked with the ledger, and ask.
