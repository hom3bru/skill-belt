# Output formats

These are the shapes Jobscura delivers in. Each one puts the decision first and keeps what is known
apart from what is uncertain. Drop any section that has nothing in it, and never pad one. Keep
helper statuses, provenance and audit notes out of anything the employer will see.

## Fit brief (application-intake)

```
<Role>, <Employer> (<official link>, checked <date>; open: yes / unverified / closed)
Recommendation: Apply / Apply as a stretch / Hold for <missing fact> / Skip. <One-line reason.>
Qualification gap: <score on the user's own scale, or "unrated"> (confidence <low/med/high>)
Strongest matches: <2-3 requirements, each with the evidence that meets it>
Real gaps: <requirements with no supporting evidence, and whether each is essential>
Unknowns that matter: <pay, location, sponsorship, deadline type... and how to settle each>
Flags: <AI-use stance, hidden or AI-directed text, scam signals, long-open listing> (omit if none)
Next step: <one concrete action, e.g. draft letter / ask recruiter X / add to tracker (needs approval)>
```

Keep the qualification gap, confidence, interest and availability as four separate lines of
thought. Do not combine them into one number.

## Morning digest (application-tracking)

```
<Date, user's time zone>
Due today: <reminders now due: role, employer, local cutoff, days left, link, next step>
Closing in the next <horizon> days: <every active role, soonest first, with what the date measures>
New finds (posted in the last 24 h): up to <shortlist size>, each with gap, confidence, fit and next step
Newly closed or changed: <verified closures (reported once), reposts, scope changes>
Not verified: <checks that failed or were not run, with the reason>
```

## Draft delivery (application-writing)

Lead with the complete recommended text. After it, give a short change note covering what changed
and why, any claim that needs the user's confirmation (from the claim ledger), any check that did
not run (such as a layout render or the helpers), and the employer's AI-use stance if it constrained
the work.

## Interview cue card (interview-preparation)

```
Question type: <overview / motivation / past behaviour / situation / knowledge / work sample>
Point to land: <one-sentence proposition>
Evidence: <2-3 real anchors with scale and role, sourced>
Qualifiers: <what not to overstate>
If probed: <the honest follow-up>
```

Label any hypothetical example clearly so that it is never mistaken for history.

## Offer memo (offer-negotiation)

```
Offers compared over <N> years, pre-tax, <currency>
Year 1 and N-year totals per offer, with equity also shown at 0% (from offer_compare.py)
What the numbers leave out: <tax, cost of living, risk, growth, people, flexibility>
Decision factors the user named: <their priorities, in their own words>
Negotiation asks: <ranked, each with its justification and the evidence or market source behind it>
Deadlines: <offer expiry and response dates, with the time zone>
```

The user decides whether to accept, decline or negotiate. Draft messages only on request, and
never send them on the user's behalf.
