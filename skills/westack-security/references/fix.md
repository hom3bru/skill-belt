# Fix mode

Use this when the user hands over a fix for a known vulnerability, or asks for one. Writing the fix needs the user's grant for those files; checking one does not.

## Attack the patch before verifying it

1. Read every caller of each helper the patch changed, and both branches of each condition it changed.
2. Look for one input that still gets through: double or mixed encoding, other case or Unicode forms, other path separators, the same value by a second route.
3. Look for one legitimate input the patch now refuses.

Report both searches, including when they found nothing.

## Verify on the original attack path

- Run the original attack on the original path: it must now fail.
- Run variant inputs as well, and the regression suite. A patch can stop the proof of concept and stay exploitable, or break normal behaviour.
- Show the attack succeeds without the fix: revert it in a disposable worktree and rerun the same attack, as westack-verify's before-and-after check does (`westack-verify` `references/claim.md`).
- These are not proof: an empty rescan, a closed ticket, passing tests that do not touch the path, or code that was renamed or moved. Follow renamed and moved code; renaming is not removal.
- When the target may not run (core `verify.md`, code you did not write), a static check is allowed; the runtime checks are then not-run, never passed.

## A removal is a claim of absence

For a removed secret, file or code path, follow core `verify.md`: probe the exact pre-change identifiers on every copy (each clone and remote, forks, caches, build output); a hit names the survivor. Rotate an exposed secret before purging history. Record it as `absence` ([record](record.md)).

## Record it

Update the finding's record with what the patch changed and the receipts above, regenerate the report, and keep the original attack in the record so a later run can repeat it.
