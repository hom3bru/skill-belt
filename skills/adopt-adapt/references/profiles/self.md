# Profile: SELF (adopt-adapt itself)

Load only on **explicit** request to review or improve adopt-adapt (routing.md §2.2). Ordinary runs may note "possible SELF lesson" but never evaluate or mutate the skill.

## Routing signals
The user explicitly asks to review or improve adopt-adapt itself, or names a path to an adopt-adapt bundle → `self`, high and explicit. A skill donor or a skill recipient alone makes `self` a candidate only ("possible SELF lesson, not evaluated").

## 1. Hard rules
| Rule | Source |
|---|---|
| MP-0 protected core (verify before trust; never aim to find; breadth ∝ size; converge; two views; ground truth) cannot be weakened by a routine meta-finding; core changes need the owner's architectural sign-off (§2) | SKILL.md §0.9 |
| A run yields a proposal, never a live self-edit; ≤1 accepted self-change per session; no micro-edit evasion | SKILL.md §0.9; [evolution](../evolution.md) |
| MP-6: every accepted change bumps the version, appends CHANGES and is committed in the tracked canonical source (§2) before release; never release from an installed mirror | [evolution](../evolution.md) |
| Consent: ordinary agreement from the owner counts for the concrete preceding question; no magic word | SKILL.md §0.9 |
| No candidate promotes itself; editor may not alter grader criteria, eval cases or hidden gold | [evaluation](../evaluation.md) |
| Bind exact bundle + host; don't treat the highest version number as authority | §2 |
| A selection holdout spent across iterations is no longer held out; keep a never-used final set | [evaluation](../evaluation.md) |
| Show a checker can fail before trusting its pass | SKILL.md §6 |

## 2. Current package identity
Owner (architectural sign-off for §0, release approval): Matt Kolkin. Legal overlay for SELF: injection, undisclosed persistence or an unclear skill licence raises the flag.
Resolve the live version from SKILL.md, release.json and the claimed host. Canonical source, in order: the `self.canonical_source` entry in `local-roots.json` beside this profile, when that private file is installed; otherwise a tracked root the user supplies; otherwise ask. A sibling skill-belt checkout's `skills/adopt-adapt` is a published edition, never the canonical source. Package `skills/adopt-adapt`; installed directories are mirrors. Bind exact bytes and inspect local changes before publication. A tracked source does not complete formal behavioral/host qualification. Historical lineage and corrected defects remain in [CHANGES](../../CHANGES.md) and the canonical research archive.

## 3. Rubric for a META-PROPOSAL (uncalibrated)
| Component | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| Failure evidence (0-3) | opinion/critique only | one anecdote | reproduced defect (test/command output) | defect observed across ≥2 hosts or runs |
| Scope discipline (0-3) | broad always-on rule | several coupled edits | one coherent change + nearby negative control | — plus removes/consolidates text |
| Protection (0-2) | weakens §0 / MP-0 | neutral | strengthens a protected rule with a test | — |
| Testability (0-2) | no falsifying test | structural test only | behavioral paired test defined | — |
| Penalty | −2 self-grading or promotion by the editor; −1 adds a new universal section without removal | | | |

## 4. Gates and critical fails
SELF-WITHOUT-INTENT; LIVE-SELF-EDIT; SELF-GRADING (author writes the rubric/evals it is judged by); MP-6-BYPASS (release without Git); HOLDOUT-SPEND; INSTALL-ON-AGREEMENT.

## 5. Seams and valid proposals
Fields: baseline identity (path + sha) · failure evidence · smallest correction · preserved non-negotiables · files · expected benefit · falsifying test · complexity added/removed. States: observed → proposed → approved candidate → candidate → evaluated → approved release → released. Release check: `python -B "<skill-directory>/scripts/package.py" verify "<skill-directory>"` then paired evaluation (evaluation.md).
