# Modernize an aging PR

For a branch that has gone stale, often someone else's: is it still worth landing, and if so, does it survive today's base? The answer is one of three, decided before anything moves.

| Disposition | When | Then |
| --- | --- | --- |
| modernize | the change is still right on today's base, after a replay and perhaps a mechanical fix | replay, prove nothing was lost, push only under a grant |
| rework | the problem is real, but this diff is no longer how to solve it | push nothing; say what the new change would be and where it belongs |
| close | the problem is gone, solved another way, or decided against | push nothing; recommend closing with the commit or PR that superseded it |

You never close a PR yourself: close is a recommendation, and the owner or the person who asked decides.

## Read it as a claim

What did the PR set out to do, and is that still wanted? Read its description, its commits and the base's history since the merge base (`git log --oneline <merge-base>..origin/<base>`). Textual cleanliness proves nothing: a branch that rebases without conflicts onto a contract that moved is more dangerous than one that conflicts.

## Replay (modernize only)

1. Record the branch's head now (`old_head`), the merge base and the count of merge commits in `<merge-base>..<old_head>`. Any merge commit stops the replay: a plain rebase drops what it changed and range-diff never shows it. That is rework.
2. Replay on a new branch, so the original stays as it was: `git switch -c modernize/<branch> <old_head>`, then `git rebase origin/<base>`. Resolve conflicts by the PR's intent, not the base's.
3. Prove it: `git range-diff <merge-base>..<old_head> origin/<base>..modernize/<branch>`, saved to the evidence folder. Every patch marked `!` (changed) or `<` (dropped) gets one line of explanation: a conflict resolution, a renamed symbol, already upstream. A change you cannot explain is a finding, not a footnote.
4. Run the tests on the replayed branch. When every commit was already upstream, the replay ends on the base itself and there is nothing to range-diff (git refuses an empty range): `git rev-list --count origin/<base>..modernize/<branch>` of 0 is the evidence (git usually, not always, also says "skipped previously applied commit"), and the disposition is usually close.

## Push (modernize only, under a grant)

The grant names the branch: "push the modernized feature branch". Replace the PR's branch only with a lease pinned to the head you read in step 1, `git push --force-with-lease=<branch>:<old_head> origin modernize/<branch>:<branch>`, so a push someone made meanwhile is refused instead of overwritten. Never `--force` and never a bare `--force-with-lease`. A refused push means the PR moved: read it again and start over. Pushing to someone else's fork needs their permission; without it, push to a new branch and say so.

## The record

`scripts/modernize.py rangediff <saved range-diff>` parses the pairs; `scripts/modernize.py check modernize.json` checks the record (`westack-ship-modernize-1`): branch, base, old head and merge base; the disposition and its reason; for modernize, no merge commits, a new branch, the range-diff's sha256 and pairs with every changed or dropped patch explained, and the tests after; rework says the next change, close names what superseded it; rework and close push nothing; a push carries a grant naming the branch and the pinned lease; `closed` only with the owner's yes quoted.

Provenance: gstack's modernize at the mirror pin (absorption.json `gstack.modernize`), in westack's words.
