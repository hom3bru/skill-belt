# Design: flaky-test triage bot

Mode: builder
Date: 2026-11-04

## Problem

The team reruns CI by hand when a test flakes, about six times a week, and nobody records which tests flake.

## What makes it worth building

A weekly list of the five flakiest tests, with the commit that made each one flaky, would turn a chore into a fix list.

## Constraints

GitHub Actions only; no new paid service; read-only access to CI logs.

## Premises

1. Flakes are concentrated in a few tests (agreed).
2. The CI logs keep enough history to find when a test started flaking (agreed).
3. People will fix tests when they see a ranked list (disagreed: they want an owner named too).

## Approaches

### Weekly report
- Effort: S
- Risk: Low
- Pros: one scheduled job; no new storage
- Cons: a week of delay

### Live dashboard
- Effort: L
- Risk: Med
- Pros: current at a glance
- Cons: a service to run; more than the problem needs

## Recommendation

Weekly report: it ships in a day and answers the question the team asked.

## Choice

The user chose the weekly report and said "start with the list, add owners from CODEOWNERS".

## Open questions

- How far back do the Actions logs go on this plan?

## Success criteria

The flake count in the weekly list falls for three weeks running.

## Next action

Pull the last 30 days of Actions logs and count reruns per test.
