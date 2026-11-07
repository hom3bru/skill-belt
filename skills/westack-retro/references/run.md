# The repository retro

## The log

Run exactly this in the repository (read-only), with the window's dates, and save the output:

```text
git log <ref> --since=<since>T00:00:00 [--until=<until>T00:00:00] --date=iso-strict --numstat
    --pretty=format:@@%H%x1f%an%x1f%ae%x1f%aI%x1f%P%x1f%s%x1f%(trailers:key=Co-authored-by,valueonly,separator=%x3b)
```

`<ref>` is `origin/<default>` after a granted fetch, otherwise the local default branch, and the report says which. For compare mode, save a second log for the previous window of the same length (its `--until` is this window's start).

## What the helper reports

| Field | Meaning |
| --- | --- |
| commits, merge_commits, contributors | non-merge commits in the window; merges counted apart |
| insertions, deletions, net | from numstat, binary files as 0; context, not impact |
| test_insertions, test_ratio | lines added under test paths (`tests/`, `spec/`, `test_*.py`, `*.test.*`, ...) and their share |
| weighted_commits | each commit counts its files, capped at 20 |
| active_days | distinct dates with commits |
| sessions | commits less than 45 minutes apart form a session: deep (50 minutes or more), medium (20 to 50), micro (under 20) |
| types, fix_ratio | conventional-commit prefixes; a fix ratio over half suggests changes landing before they are reviewed |
| sizes | lines per commit: small under 100, medium to 500, large to 1,500, xl beyond |
| hours, peak_hour | commits by the hour of the commit's own timezone |
| focus | the share of file changes in the busiest top-level folder |
| hotspots, biggest_commit | the ten most-changed files; the largest commit, a candidate for ship of the week |
| authors, ai_assisted_commits, human_coauthors | per-contributor counts; AI co-author trailers counted apart |
| team_streak, you_streak | consecutive days with commits, ending at the newest commit's date; live only if that is today or yesterday |

## Features shipped

Read the changelog's changes on the ref in the window (`git log <ref> --since=... -p -- CHANGELOG.md`) and, with a grant for the hosting service, merged pull requests in the window. Count user-visible capabilities only, each with its commit or pull request; no source means "unavailable".

## The narrative

1. **What shipped**, with evidence, then the ship of the week and why it matters.
2. **Patterns:** sessions and active time, peak hours and late-night clusters, the fix ratio, hotspots changed five or more times, the focus share.
3. **People:** for a team, two or three sentences per contributor, one cited piece of praise and one data-backed suggestion; for a solo repository, skip this.
4. **Trends** for windows of 14 days or more, and the comparison with the last saved retro.
5. **Three wins and three things to try**, each tied to a number or a commit.

Tone: direct and specific; no generic praise, no blame.

## History

`python scripts/retro.py compare <previous.json> <current.json>` gives the deltas. Save each retro's JSON (with the user's yes) in the folder they name, by date; a retro never overwrites an earlier one.
