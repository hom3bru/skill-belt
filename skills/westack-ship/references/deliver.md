# Deliver

Each granted step runs the same loop: confirm the grant, run its pre-checks, take the one action, read the result back from the live target, record it. Stop at the first failure. Before every step, check whether it already happened (the commit exists, the remote ref already equals HEAD, a PR for the branch is open, the tag exists) and never do it twice. A step starts only from the states its pre-checks name (push, for one, from a committed branch whose commit was read back). Any other state, an unknown or missing one included, is refused with the recovery step named ("tests failed: fix, then re-run readiness"), and a failed action is retried only on the commit it started with.

Forge commands below are GitHub's (`gh`); on another forge use its equivalent read and say which. A read-only query of the forge or a fetch from the remote is covered by a grant that already reaches that remote; with no such grant, the pre-checks that need them are "unknown", and so is the step.

## Commit

- **Grant:** "commit", or a later granted step that needs one.
- **Pre-checks:** readiness passed, or the user accepted the named gaps. A commit that a push or PR will follow goes on a new branch named for the change, never on the default branch. In a worktree other agents also use, `git diff --cached --name-only` must show nothing or only your paths: anything else staged is theirs, so stop and ask, and never reset it away.
- **Act:** stage the intended paths by name; `git add -A` only when every changed and untracked path is intended. In a shared worktree commit with `git commit --only -- <paths>`. One commit per logical change, in the repository's message convention, with a body that says why. No `[skip ci]`, no `--no-verify`, no trailer the user did not ask for. Hooks run; a hook failure is a failed check: fix it within the grant or report it (a hook that assumes a stable HEAD is reported, not bypassed).
- **Never** amend, squash or rebase a commit that is already pushed without a grant that names it.
- **Read back:** `git log -1 --stat` and `git status`: the commit holds exactly the intended paths, and in a shared worktree the staged set before and the committed set after both equal your list.

## Push

- **Grant:** "push", naming or plainly implying the branch and remote. A push to the default branch, or to any protected branch, needs a grant that names that branch, and is never a bypass.
- **Pre-checks, before every push (repeat them before a second push):**
  1. **Target:** `git remote -v`, the branch and its upstream. Fetch the target ref and compare: behind or diverged stops the push (integrating is a new change that needs the gate again); never force.
  2. **Open PR:** for a branch with an open PR, an armed auto-merge or a merge-queue entry means the push can merge without anyone deciding it. Read both: `gh pr list --head <branch> --state open --json number,state,isDraft,headRefOid,baseRefName,autoMergeRequest` and, for the queue, the GraphQL field `mergeQueueEntry`. Report it and stop; disarming it is its own action that needs its own grant. A field you could not read is unknown, and unknown counts as armed.
  3. **Automation on push:** workflows that run on this push (branch or tag) and merge, open PRs, publish or deploy, and bots configured to merge (Mergify, Kodiak, bors, Renovate automerge, auto-merge actions). A push whose automation would merge, publish or deploy is that action: stop unless it is granted.
  4. **Protection:** branch protection and rulesets for the target and for the PR base: `gh api repos/{owner}/{repo}/branches/{branch}/protection` and `gh api repos/{owner}/{repo}/rules/branches/{branch}`. Name the required checks. A plain git remote with no protection system is recorded as such; an API error other than "Branch not protected" is unknown.
  5. **Content:** HEAD is the candidate the receipts cover, uncommitted changes are none or are meant to stay local (they are not in the push), and the diff holds no secret.
- **Summarise:** save each output above in the evidence folder and run

  ```text
  python "<this skill>/scripts/shipgate.py" --status status.txt --remotes remotes.txt --pr pr.json
      --rules <branch>=protection.json --rules <branch>=rules.json --repo <repo> --diff diff.txt
      --receipts checks-diff.json --default-branch main --grant push --output shipgate.json
  ```

  It reads the saved files, runs and pushes nothing, and prints the findings per step. Exit 0: nothing blocks the granted steps. 1: a blocker or a decision. 2: it cannot tell (a needed input is missing or unknown). Every input is optional except `--status`; a missing one shows as unknown for the steps that need it. `--pr none` and `--rules <branch>=none` record a remote with no pull requests or protection system (a plain git server or a local bare repository); say why in the report, since a mirror of a forge repository still runs the forge's workflows. Without Python, check the same list by hand and say so.
- **Act:** `git push origin <branch>` (`-u` the first time). One branch by name: never `--force`, `--force-with-lease`, `+refspec`, `--mirror`, `--all` or `--tags`.
- **Read back:** `git ls-remote origin refs/heads/<branch>` equals `git rev-parse HEAD`. A rejected push (non-fast-forward, hook, protection) stops: quote the message; never force, never switch remote, protocol or credentials.

## Pull request

- **Grant:** "open a PR" (covering a commit on a new branch and a push of it). Base: the default branch unless the user named another; ask when it is not obvious.
- **Pre-checks:** the push read back; workflows that act on a new PR (auto-merge on `pull_request`, auto-approve) are reported and stop the step unless granted. Never add a label, reviewer or milestone the user did not ask for: labels can trigger automation.
- **Draft or ready:** what the user said; otherwise ready when the readiness verdict is READY and draft while anything is open, with the reason in the body.
- **Body:** written to a file outside the repository, never passed inline on a command line. Follow the repository's PR template; otherwise: why, what changed, verification (the receipts table with counts, not-run checks, pre-existing failures by name), risk and how to revert, and open items (human-only criteria, decisions). Search the body for unfilled placeholders and template guidance comments before opening: each hit is a finding, and a body with one is not finished. After a transform, name each rule with its version and the hunks it made. On a public repository the body is public: no secrets, no private paths.
- **UI evidence:** a change to what users see carries a before and an after capture (one line each; format in `shipgate.py --body`) of one scenario, viewport, theme and state, in one environment (`westack-design` `browser.md`), each labelled with its revision. After-only, or a mockup as the before, is not ready.
- **Act:** `gh pr create --base <base> --head <branch> --title "<title>" --body-file <file>` (add `--draft` when draft). Never `gh pr merge --auto`, never a merge queue.
- **Read back:** `gh pr view <number> --json number,url,state,isDraft,headRefOid,baseRefName,autoMergeRequest`. If the forge CLI is missing or not signed in, do not sign it in: hand over the compare URL and the body file. That is "PR prepared", not "PR open".

## Merge

- **Grant:** "merge" or "land" for a named PR (or the current branch's PR, by number, read back).
- **Pre-checks, on the live PR:** open, not a draft, its head SHA equal to the commit your receipts cover, the base unchanged since readiness, mergeable, every required check passed on that SHA (pending is not passed, and a check on another SHA does not count), and the required approvals given by people. Never approve your own PR, never `--admin`. No review thread is unresolved and no change request is open (GraphQL `reviewThreads` and `reviewDecision` in the saved `--pr` file; unread is unknown). A commit a bot pushed may never have triggered CI, so each required check must exist for that exact SHA.
- **Act:** `gh pr merge <number> --<method> --match-head-commit <sha>`, with the method the repository allows. `--auto` only when the user asked for auto-merge by name, and never on a base with no required checks. Deleting the branch is a separate step that needs its own grant.
- **Read back:** `gh pr view <number> --json state,mergedAt,mergeCommit,autoMergeRequest`. "Queued" or "auto-merge enabled" is reported as that, not as merged. If someone else merged or closed it, report that instead.

## Release

- **Grant:** names the release action: "tag v2.1.0 and push the tag", "create the GitHub release", "publish to PyPI". Each is its own step.
- **Pre-checks:** the release commit is where the project releases from (usually merged to the default branch) and read back; the version is not already tagged, locally or on the remote; a tag push whose workflows publish or deploy is that publish or deploy, so it needs that grant too.
- **Act:** an annotated tag (`git tag -a v<version> -m "<summary>"`; signed only with a key the user already has configured), then `git push origin v<version>`, one tag by name. Publishing a package or a forge release only when named, with the project's own release command.
- **Read back:** `git ls-remote --tags origin v<version>`, the release record, or the package version on the registry. Deploying is `westack-deploy`, under its own grant: stop at released and say it was not deployed.

## Failure or doubt

Report the action, target, exact error, the state read back now, and whether the outcome is denied, pending or uncertain. An uncertain step (a timeout, a lost connection) is inspected, never replayed: a push that timed out may have landed. Continue only work the failure does not touch, and offer the next safe step.
