# Premises, approaches and the design document

## Premise challenge

Before proposing anything, test the framing:

- Is this the right problem, or would another framing make the solution much simpler?
- What happens if nothing is built?
- What in the repository already partly solves it?
- If the result is a new artifact (a CLI, a package, an app), how will people get it?
- In demand mode: do the answers support this direction, and where are the gaps?

Write three to five premises as numbered claims and ask the user to mark each agreed or disagreed. A disagreement changes your understanding; loop back before going on.

## Looking outward (optional)

A search of how the space usually works can sharpen the premises. Ask first: it leaves the machine. Search general category terms only ("small-team CI flake tracking"), never the user's product or idea. Read two or three sources, then say what everyone believes, what the sources add, and whether this session's evidence says the usual view is wrong here. Declined or unavailable: say so and go on.

## Second opinion (optional)

When the user wants one and westack-review's different-model reviewer is installed, give it a short summary (problem, key answers, premises), not the conversation, and report what it disputes.

## Approaches

Two or three, each with a name, a one-line summary, effort (S, M, L or XL), risk, two or three pros and cons, and what it reuses. One is the smallest that ships; one is the best long-term; a third may reframe the problem. Recommend one in a line tied to the user's goal, then stop: write nothing more until the user picks.

## The design document

`Mode: demand` or `Mode: builder` on its own line near the top, then these `##` sections:

- **demand:** Problem, Demand evidence, Status quo, Who and the narrowest wedge, Constraints, Premises, Approaches, Recommendation, Choice, Open questions, Success criteria, Next action.
- **builder:** Problem, What makes it worth building, Constraints, Premises, Approaches, Recommendation, Choice, Open questions, Success criteria, Next action.

Premises are numbered, each ending "(agreed)" or "(disagreed: why)". Each approach is a `###` heading with `Effort:`, `Risk:`, `Pros:` and `Cons:` lines. Choice records that the user chose, which approach, and their words. Next action is one thing to do this week. Nothing goes in that the user did not say or a read source does not support.

The choice checker reads `user_name` from `~/.claude/skill-belt-profile.json`. Without a profile it accepts the neutral wording "the user". The optional `legacy_user_names` list supplies explicit owner aliases for older records. Keep names in that local profile. The neutral forms "the user" and "they" remain valid. A malformed profile is reported as invalid.

`python scripts/ohcheck.py doc <file>` checks this shape and the hedges ruled out in [questions](questions.md). Save the document where the user says, or the evidence folder; committing it is a separate grant. With the user's yes, note the decision in the host's memory (core `memory.md`).
