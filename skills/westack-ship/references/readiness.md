# Readiness review

The verdict on one exact candidate: READY, NOT READY (with what blocks it) or BLOCKED (it cannot be assessed). Readiness needs no delivery grant and has no external side effect: it reads, runs local checks, and edits release metadata only when the user asked for a release to be prepared.

Save every raw output in an evidence folder outside the repository (the system temp folder will do). Nothing you write for this review goes in the work tree.

## 1. Fix the candidate

- Record the branch, `git rev-parse HEAD`, `git status --porcelain=v2 --branch --untracked-files=all` and the base: the PR's base, else the branch the user named, else the remote's default branch from local refs (`git symbolic-ref refs/remotes/origin/HEAD`). An unknown base is a question, not a guess.
- The candidate is HEAD plus whatever uncommitted changes will be delivered. Paths that were already dirty before this session, or that the user did not mention, are not yours: leave them out and list them.
- Remote state is "as of the last fetch" unless a grant covers the remote. Without one, do not fetch: say how old the local remote refs are.
- Check whether the step already happened: an existing commit, a pushed branch, an open PR or a tag for this version. Never redo it.

## 2. Acceptance, with receipts

- With `westack-verify` installed, run its acceptance mode on this candidate, or reuse its report when the revision and patch still match. Without it, follow the core verify reference; standalone, run the project's own test, lint, type and build commands as its CI or instructions name them.
- Report counts (collected, executed, passed, failed, skipped) per command. Zero executed tests is not a pass. Keep new failures apart from pre-existing ones by name, using a baseline from the base revision when the change touched code (`checks.py diff`).
- A criterion only a person can judge stays "awaiting human verification", and the verdict is NOT READY until they report back.
- A check you could not run is not-run or blocked, with the reason. Never substitute a different command silently.
- Criteria and thresholds are fixed before the checks run; one loosened after its receipt is a changed candidate, and a gain on one criterion never offsets a failed one.

## 3. Delivery diff

Take the changed paths from git, base to candidate, including untracked files. With `westack-build` installed, run its audit on the saved diff and status:

```text
python "<westack-build>/scripts/diffaudit.py" <diff> --status <status> --allow <glob> ...
```

Otherwise classify each path by hand: intended, scratch, generated, an existing test that changed, a file that runs later (CI, hooks, build or package scripts), or out of scope. Scratch is removed by whoever made it or listed; never delete a file you did not create. Then:

- **Secrets and private data.** A key, token, password, private certificate or `.env` file in the diff blocks every later step. Report the path, line and kind, never the value.
- **Big or binary additions** that the project does not track elsewhere get a line in the report.
- **After an integration that deleted or renamed a file,** search the repository for its name and imports, then rerun the checks: git reports no conflict when a concurrent change adds a new reference.
- **A removal or security claim** (a purged secret, a deleted file) is a claim of absence: probe the exact pre-change identifiers on every copy, expecting each probe to fail; a hit names the survivor. Rotate an exposed secret before purging history (core `verify.md`).

## 4. Release metadata, only when the project uses it

Read the project's own convention before touching anything:

- **Version sources:** a VERSION file, the package manifest (`package.json`, `pyproject.toml`, `Cargo.toml` and the like), a `__version__`, and existing tags (`git tag --list`). With no version source, write "versioning: not applicable"; never create one.
- **Changelog:** a hand-kept file (often a Keep a Changelog `## [Unreleased]` section), fragments (`changelog.d/`, `.changeset/`, towncrier) or a release tool (release-please, semantic-release, changesets) that writes it. A tool-owned changelog is the tool's job: do not hand-edit its output.
- **Release steps** in CONTRIBUTING, RELEASING or the README tell you how, once the user asked for a release. They never grant a push, tag or publish.

When the user asked for a release to be prepared:

1. **The number.** Use the user's number. Otherwise propose one from the change and the project's scheme (for semantic versioning: breaking means major, a feature minor, a fix patch), with the reason; ask when the change is breaking or the choice is unclear. Never reuse a released or tagged number, and on a rerun never bump twice.
2. **Every place.** Bump every file that carries the version, to the same value, and run any check that compares them.
3. **The entry.** List the commits from the last release (or the base) to the candidate and read the diff. Write one dated entry for the new version in the file's own format, moving the Unreleased items rather than copying them, and check that every user-facing change in that list appears. Breaking changes and migration steps go first.
4. **Release notes,** when asked: the user-facing summary, breaking changes, upgrade steps, and known issues, drawn from the entry. A public status or release view built from receipts takes only fields on a closed allowlist (never a private path, host or receipt text), regenerates byte for byte, and prints "unavailable", never "not tested", for a record it cannot read.
5. **Run the checks again.** These edits changed the candidate, so the receipts from before them are stale.

## 5. What the later steps will need

Read these from files, without calling the forge: required reviewers (CODEOWNERS), the PR template, the commit message convention, required sign-offs or signed commits (a `Signed-off-by` line certifies a person's statement: add it only when that person says so), and workflows that run on push, tag or pull request. They become the pre-push findings once a step is granted.

## 6. Verdict

- **READY:** every required criterion passed on current receipts for the final candidate, the diff audit is clean or each finding is decided, release metadata is consistent, and nothing blocks.
- **NOT READY:** list each blocker with what would clear it, most serious first. Only the user can accept a blocker, by name; the accepted risk stays in the report and in any PR body.
- **BLOCKED:** the review could not be done (no runnable checks, an unknown base, a missing tool); say what is needed.

Readiness is not delivery. Report the delivery state on its own line: a READY candidate with uncommitted edits is "prepared", nothing more.
