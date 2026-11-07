# Document mode (plan review)

Review a plan, spec, RFC, migration or design document before anyone builds from it. The question is whether a builder following it would build the right thing correctly. An adequate document needs no changes, and saying so is a valid result.

Boundaries: this mode critiques a written document. Deciding an architecture or writing an ADR is `westack-architecture`; critiquing built UI, mockups or visual design is `westack-design`; writing the plan is `westack-plan` (each when installed). "Design review" of a design document comes here; of screens, there.

## 1. Read before judging

- The whole document, with its path and SHA-256 as the scope receipt.
- Its goal and constraints: the issue, ticket or request it answers, and decisions already settled (quote where they were made).
- The code and data it makes claims about. A plan that describes the existing system is checked against that system.

## 2. Set the scope posture

Ask, or infer and state, one posture before reviewing: **expand** (look for a better outcome worth more scope), **hold** (keep scope; harden it) or **reduce** (find the smallest version that proves the goal). Hold is the default. Under every posture, any change of scope is a proposal for the user, never a silent edit.

## 3. Extract the load-bearing claims

List the claims the plan stands on: facts about existing code, data volumes, dependencies, performance, user behaviour, effort. Check each one you can against the code or data, with the receipt. Those you cannot check become open questions with a recommended answer.

## 4. Apply the lenses the document needs

Each lens yields findings in the standard contract ([review rules](rules.md)), located by heading and line, and a 0 to 10 rating per dimension with what a 10 would need. Pick lenses from the content; say which you skipped and why.

**Product lens.** Is the problem and its user named, and does the premise hold? Is there a measurable outcome? Which items do not serve the goal (scope creep), and which must-haves are missing? What is the smallest version that proves it, and were alternatives, including not building, considered?

**Engineering lens.** Does the design fit the existing code (cite files)? For each new path: data flow, state, failure modes (what fails, how it surfaces, what the user sees), edge cases (empty, zero, concurrent, partial failure, retries, time). Migrations: reversible, a rollback plan, backfill, locks, deploy order and flags. Tests: each behaviour named with the test that would catch its regression. Observability, security and privacy touchpoints (hand a deep audit to `westack-security`), performance claims with numbers, dependencies and sequencing, effort realism. Decisions: each names the driver it serves, and each rejected alternative keeps a reason tied to a driver; a missing reason is a finding.

**Design lens (the experience the document specifies, in words).** Every user flow end to end; every state (empty, loading, error, partial, success); error messages and recovery; consistency with existing patterns; accessibility commitments; what users see during rollout or migration. Visual polish and built screens go to `westack-design`.

**Developer-experience lens**, when the users are developers (an API, CLI, SDK, library or developer tool): a persona, the journey, time to hello world and eight dimensions scored 0 to 10, recorded and checked ([dx lens](dx-lens.md)).

**A recommendation with no answer key.** List every factual or logical error first and cap the verdict by that list. State the fair case against the recommendation. Label what the list cannot settle as judgment, not verified.

## 5. Run the builder check

When a fresh context is available and authorised, give it only the document and ask it, as a builder who cannot reach the author, to do three things: restate what the document proposes and how the current system works, list the guesses it would have to make, and answer the questions a reader would predict. Sort each guess: answered elsewhere in the document, the author's own call (mark it), or a decision for the user. A wrong restatement, an unanswered predicted question or an unanswered guess that changes the build is a finding. A reader that also saw the author's summary or conclusions is contaminated: discard that run. Without a fresh context, run it yourself and record the level as self.

## 6. Validate and adjudicate

Re-check every finding against the whole document before it counts: a "missing" item is often in another section. Apply the exclusion list, then:
- **No leftovers.** Search the document for unfilled placeholders and template guidance comments (`{date}`, `[TODO]`, `<!-- ... -->`). Each hit is a finding with its line; a document with a leftover marker is not complete.
- **Amendments are proposed, not applied.** Write each as replacement text the user can accept. Edit the document only when the user asked for edits, and then only the accepted amendments.
- **No silent decisions.** You may settle a reversible, low-impact choice yourself when the user asked you to proceed; record each such decision and report it. Irreversible or high-impact choices go to the user.

## 7. Report

Scope (path, hash, posture), review level, then per lens a verdict (ready, ready with amendments, not ready) and its ratings, the findings by severity, open questions with recommended answers, the proposed amendments, and decisions you made on the user's behalf.
