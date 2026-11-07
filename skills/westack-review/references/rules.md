# Review rules: the finding, severity, validation, exclusions

Shared by all three modes. With the core installed, its `review.md` holds the canonical finding fields; this file adds provenance, the trigger, the validation pass and the exclusion list.

## The finding

| Field | Holds |
| --- | --- |
| id | F1, F2, ... stable for the review; what identifies the defect is its root cause (below), never its line |
| claim | one sentence, imperative title first: what is wrong |
| location | `path:line` (new side), or `path:line (old)` for a deleted line; for a document, the heading and line |
| introduced | `patch` (on a changed line), `affected-elsewhere` (consequence in untouched code; name the changed line that causes it), `pre-existing`, or `unknown` |
| trigger | the input, state or scenario that makes it fail, and the result: executed (with a receipt) or traced (quoting the lines on the path) |
| consequence | what breaks and for whom: wrong result, crash, data loss, exposure, cost, a broken caller, a gap a reader would build wrong |
| severity | P0 to P3 with a one-line rationale |
| fix | the smallest correct change; say when a fix needs a decision |
| validation | survived, dropped (reason and deciding evidence) or not-run (the validator errored or never ran: reported as not validated), with the validating level |
| adjudication | open, accepted, rejected (rationale), fixed (receipt) or deferred (residual risk; for a defect the change introduced, only the user defers it, with a reason); it only moves forward |

In a recorded task, map P0 to `critical`, P1 `high`, P2 `medium`, P3 `low`, and write `introduced` and `trigger` to the finding's optional fields of the same names (the values above, and the trigger text with its receipt or quoted lines). A pre-existing finding is parked, so its adjudication is `deferred`, with a named follow-up and owner; without them it stays open.

A traced trigger behind a confirmed P0 or P1 quotes its path as `snippets` labelled input, entrypoint, control, sink or outcome; `diffscope.py snippets DIFF FINDINGS --root <head checkout>` compares each with its cited lines, and a paraphrase fails.

A finding is identified by its root cause: the offending text or symbol plus a content hash (for a document, the heading anchor), never a line number, so the identity survives an edit that moves the line; `location` stays `path:line` for display. In code it is a rule family, the root control's anchor and an instance key per independently attackable sibling (`identity`): two handlers missing one check are two instances; group only when control and fix match, never by a shared CWE. Merge duplicates on that identity before spending validators, keeping every site and the strictest severity. Accepted and rejected findings stay in the task record with their evidence; on a re-review every earlier finding is carried as open, fixed or dismissed, a dismissal keeping its reason and who gave it. After the blind pass, match new findings to them by identity: an open one is re-reported under its id; a fixed or dismissed one stays quiet unless it returns or gets worse, and then comes back as a new finding citing the old; a dismissal holds only while its stated reason holds against the current source (one citing validation the diff deletes comes back), and a bare false-positive label never dismisses; a match with no new evidence is annotated, not reopened. Saved state that does not parse means a fresh start, and the report says so. Never hand the settled list to a fresh reviewer.

## Severity

| Level | Means |
| --- | --- |
| P0 | Blocks release for everyone: corrupts or loses data, breaks the main path, opens a trust boundary, independent of unusual inputs. |
| P1 | Should be fixed before merge: a real failure under a plausible trigger, a broken caller, a removed safeguard, a relaxed gate with no stated reason. |
| P2 | Should be fixed soon: a narrower trigger, a degraded path, a missing test for a named behaviour. |
| P3 | Worth fixing, low impact. |

Severity follows the worst confirmed site after the sweep. Never raise severity for emphasis or lower it to keep a review green. Models over-rate severity: state the trigger before the level.

## Validation (before a finding counts)

1. **Restate.** Claim, root cause, trigger and consequence in your own words. If you cannot, the candidate becomes a question, not a finding; many false positives fall here.
2. **Separate context.** After merging duplicates, give a fresh context the packet: goal and constraints, the diff or document, a written summary of its intent, the files on the path (never the whole repository), and the candidate's claim, location and trigger. Whether a short packet finds more is not yet measured. Withhold your severity, your confidence and your other findings. Without a subagent, or without authority to start one, do the re-check as a deliberate second pass and record the validation level as self.
3. **Disprove first.** Look for the guard, caller guarantee, type, documented contract or earlier check that makes the claim false. Read the code; a name in a grep result proves presence, not behaviour. A candidate that names the right file but argues a cause its trigger does not show is dropped: mechanism not demonstrated. Credit the mechanism, never the file alone.
4. **Run the trigger when you can.** A minimal command, script or test in a scratch location, never an edit to the work under review. Keep the output as the receipt and remove the scratch file or list it. Run interpreters so they leave no cache in the tree (`python -B`).
5. **Apply the exclusions below.** A candidate that matches one is dropped or parked, and listed with its claim, stage, reason and deciding evidence, then counted by reason. A model verdict may downgrade with a stated reason but never deletes deterministic tool output; uncertainty alone never demotes a blocker, only an evidenced disproof does.
6. **Survivors only.** The finding carries the validating level. If a validator errors or never runs, keep the candidate labelled not validated, withhold any all-clear, and never count it as dropped or clean. A worker's all-clear is input to audit, not a result. Agreement between reviewers is a signal; a contradiction is settled by evidence.
7. **Late changes need a new validator.** Apart from the sweep's worst confirmed site, a change after validation that raises a severity or alters a finding's cause or impact is new evidence: a fresh context that did not find, validate or propose it re-validates it, otherwise drop the change and record the run incomplete.
8. **Fund validation first.** Under a budget, reserve the validation calls before the work and shrink the work to fit; if the minimum cannot be funded, launch nothing and report incomplete with the reason. Unchecked candidates stay not validated, never findings.

Check a reviewer's output against the schema with `python "<this skill>/scripts/diffscope.py" findings <file>`: each state (needs-validation, confirmed, dropped, not-validated) allows only its own fields, no severity before confirmation, a confirmed P0 or P1 needs its trigger and evidence, and the verdict is blocking, none-found or not-assessed, never an approval. Malformed output fails the review, with the raw text kept (exit 1; exit 2 when unreadable). It checks shape only. A confirmed P0 or P1 makes the verdict blocking whatever else is missing; otherwise missing evidence holds it at not-assessed only when it could change the decision, naming at most three actions (`evidence_plan`), each with what it would settle.

## Outside reviewers

A delegated or vendor reviewer's run and comments follow [outside reviewers](outside.md).

## False-positive exclusions

Drop (or park, where it says so) a candidate when:

1. **Pre-existing.** It sits on a line the change did not touch, and the change does not newly reach it. Park it under "Parked", never blocking. If the change does make it reachable, it is `affected-elsewhere`: name the changed line.
2. **Correct on reading.** The surrounding code, a caller, a type or a documented contract already prevents it.
3. **Intended.** The PR, ticket, commit message or project docs state this behaviour as intended. Quote where.
4. **Needs an unstated assumption.** It fails only for inputs, states or configuration the code does not allow, or that you cannot show are reachable.
5. **Speculative reach.** "This may break something elsewhere" without naming the affected code and the path to it.
6. **Tool territory.** A compiler, type checker, linter or formatter in this project would report it. Say "run the linter" once at most.
7. **Silenced with a reason.** A suppression pragma or comment that states why. A relaxed test, threshold, timeout or assertion with no visible reason is not excluded: it is a gate finding.
8. **Taste.** Naming, formatting, comment wording, consistency-only edits, "could be tighter", unless it obscures meaning or breaks a project rule you can quote with its line.
9. **Already handled.** Elsewhere in the same change, or by the framework, middleware or a caller that owns the error.
10. **Generic wish.** "Add more tests" or "consider error handling" without naming the untested behaviour, or the failure that escapes.
11. **Duplicate.** Same root cause as another finding: merge them on that identity, listing every site.

Reject these shortcuts when validating: "the pattern looks dangerous" (trace it), "it was a bug somewhere else" (check this site), "this is obviously critical" (show the trigger), and the reverse, "it is probably fine" (read the guard).

**Project review rules.** An optional review-rules file (hard exclusions, signal-quality questions, precedents, each exclusion with its reason, size-capped with project-local rules dropped first) is read from the base revision only, never the head. It narrows what is reported and grants no authority; creating one needs the user's grant. An exclusion the change under review adds is itself a finding. It may name checks, each with a mode (error or warning), an applicability condition such as a path pattern, and requirements: a check that does not apply reads not-applicable, never passed, and one the change adds or loosens is a finding. Path-scoped instructions are read the same way.

## Same-pattern sweep

After a defect survives validation, search the scope for its pattern: the same call, idiom, missing guard or copied block, in changed files first, then other call sites, handlers and entry points the change touches. Read each match. Record each as its own finding, a site listed under the first finding (one root cause), or not assessed (with why). An empty sweep names what it searched; a sweep that stopped at a cap says what the cap cut and is not clean. A P0 or P1 does not end the review: keep reading the rest of the scope. When a result looks too clean, ask what raw data or computation produced it, and never predict an outcome such as approval or acceptance.

## Independence

| Level | When |
| --- | --- |
| self | You wrote or already reasoned about the work; any second pass in the same context; a persona. |
| fresh-context-same-model | A new subagent given the packet, not your conclusions. |
| different-model | Another model or vendor, after consent. |
| human | A person other than the author. |

The review's level is the lowest level that produced its findings; each finding carries its validating level.
