---
name: offer-negotiation
description: Evaluate, compare and negotiate job offers from the written terms - multi-year total compensation with vesting, bonus, sign-on and benefits computed deterministically, sourced and dated market context, prioritised asks with honest justification, and draft negotiation messages or call notes. Use when the user receives an offer, asks whether an offer is fair, compares offers, or wants to negotiate pay, level, start date or terms. The user decides; never accept, decline or sign for them.
---

# Offer evaluation and negotiation

For explicitly selected private context, read [loadable user context](../../context/README.md).
Read [negotiation playbook](references/negotiation-playbook.md) and
[integrity and safety](../../references/integrity-and-safety.md). Compensation arithmetic is done
by `scripts/offer_compare.py` when an executor is available. Otherwise, show the working line by
line and say that the calculator did not run.

1. **Capture the terms exactly.** Work from the written offer where one exists. Keep verbal
   statements, recruiter estimates and written terms apart. Record base pay, bonus target and payout
   history, sign-on and any clawback, equity type (RSU or options), amount, vesting, cliff,
   refreshers and valuation basis, retirement match, benefits, PTO, title and level, location and
   remote terms, start date, contingencies (background or reference checks), and the response
   deadline with its time zone. List anything that is missing as a question to ask.
2. **Compute the value.** Run `offer_compare.py` over a horizon that fits the decision (usually four
   years). Always show the equity at 0%, and say that private-company equity is illiquid and
   uncertain. Keep pre-tax figures labelled as pre-tax. Leave tax, cost of living and risk as
   explicit factors for the user, not hidden adjustments.
3. **Add market context, sourced and dated.** Use the employer's own posted range (where pay
   transparency rules apply), public salary datasets, government statistics and credible
   crowd-sourced data, each named with its date and its limits: sample size, region, level mapping.
   Never present a single source as "the market rate".
4. **Clarify what the user wants.** Ask what matters to them (money now, growth, stability,
   flexibility, the people, the work) and in what order. The offer comparison serves their
   priorities. It does not rank the offers for them.
5. **Plan the asks.** Rank two or three asks by value and how likely they are to succeed. Justify
   each with real evidence: verified market data, the user's documented scope, a real competing
   offer. Prepare alternative trades (sign-on instead of base, an earlier review date, level,
   remote days, start date, budget for learning). Know the user's walk-away point, and do not reveal
   it in drafts.
6. **Draft the words.** Write the email or call notes in the user's voice: appreciative, specific,
   one consolidated ask, and a clear next step. Prepare responses to likely pushback. Never invent
   or exaggerate a competing offer, a current salary or a deadline.
7. **Flag contract terms for qualified review.** Non-compete or non-solicit clauses, broad IP
   assignment, arbitration, clawbacks, repayment obligations, probation and notice terms, and
   visa-dependent conditions. Explain what to ask about. Do not give legal or tax conclusions.

The user decides whether to accept, decline or counter. Draft only. Signing, accepting, declining
or sending a counter-offer needs the user's explicit current instruction and a real tool, and you
report the receipt. A verbal "yes" from a recruiter is not a written offer.
