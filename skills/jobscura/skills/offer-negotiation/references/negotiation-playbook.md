# Negotiation playbook

## Before any conversation

- Get the offer in writing, or confirm every term in writing after a call.
- Know the deadline, and ask for reasonable time to review. Asking for time is normal.
- Separate what the user wants from what they would accept. Draft toward the first; keep the second private.
- Gather two or three sources of market data, each dated and matched to the level and location
  as closely as possible. The employer's posted range, where one exists, is the strongest anchor.

## Ask design

| Lever | Typical justification | Notes |
| --- | --- | --- |
| Base pay | Market data for the level and location; documented scope above the level | Compounds over years; often the hardest lever to move |
| Sign-on | Forfeited bonus or unvested equity; a gap while base is fixed | Check clawback terms |
| Equity | Level benchmarks; the risk the candidate is taking at an early-stage company | Ask about valuation basis, strike, refreshers and acceleration |
| Level or title | Documented scope against the employer's level definitions | Changes long-term pay bands |
| Start date, remote days, PTO, learning budget | Personal constraints; real cost differences | Often easier to grant |
| Review timing | A commitment to a pay review at 6 months | Get it in writing |

Consolidate the asks into one message. Several small, sequential asks erode goodwill.

## Honest leverage only

- A competing offer may be mentioned only if it exists, with any detail the user is comfortable
  sharing. Never invent one or overstate it.
- If asked about current pay where salary history questions are restricted, the user may decline
  and give their expectation instead. Explain the option; do not make the choice for them.
- Enthusiasm is leverage. "I'm excited to join, and I'd like to make the numbers work" usually works
  better than an ultimatum.

## Message skeleton

1. Thanks and genuine enthusiasm, specific to the role.
2. The consolidated ask, framed around the offer as a whole.
3. One or two lines of justification grounded in evidence or market data.
4. Flexibility: "If base is constrained, I'd also consider..."
5. The next step and timing.

## After an answer

Record the outcome in writing. Recompute with `offer_compare.py` whenever a term changes. If the
answer is no, help the user decide on the remaining terms; do not reopen the same ask. Acceptance
is the user's own action.


## Before the offer: stage handling

- Expected-salary form field: inspect whether it accepts text, a range or a required
  number and what currency, period and compensation components it means. Use the
  user's chosen expectation with dated, relevant range evidence. If only a number
  is accepted, ask the user to choose it; never invent current pay or a dummy value.
- Recruiter screen: clarify the budgeted range, level and package before anchoring
  an expectation. Offer wording based on the user's priorities and evidence;
  sharing a target is the user's choice, not a commitment to accept.
- Current-pay question: offer the choice to disclose truthfully, decline, or
  redirect to expectations. Tell the user to check current local rules; do not
  assert that a particular jurisdiction permits or forbids the question.
- Mid-process alignment: revisit range and scope when responsibilities, level or
  constraints change. Identify the mismatch early and ask for clarification without
  implying there is an offer or disclosing the user's private walk-away point.

## Review the response before deciding

Classify the response as accepted, countered, refused, conditional or unclear,
quoting the actual terms and unresolved conditions. Do not decide live: prepare a
request for time to review and leave acceptance, rejection or a further counter
to the user. A refusal is not a reason to repeat an unchanged ask.

Use the documentation ladder: contract, offer letter, email, verbal statement.
For each term, record its source, date and conditions; use this order to seek
stronger written confirmation, not as a legal ruling that one document overrides
another. Surface contradictions rather than silently selecting the most favorable
version. Seek written confirmation of agreed changes and qualified review where
needed. Recompute changed terms with the existing comparison workflow before the
user decides. A draft acknowledgement is not an acceptance or a sent message.
