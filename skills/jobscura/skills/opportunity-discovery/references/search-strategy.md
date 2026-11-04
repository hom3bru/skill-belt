# Search strategy

## Title and keyword sets

Build three short lists from the user's own evidence and direction.

- **Core titles:** what the user does now or wants next. Include seniority variants only where the
  evidence supports that level.
- **Adjacent titles:** the same function under another name, such as "programme officer",
  "community engagement coordinator" or "partnerships associate". Check each one by reading a few
  real postings. A similar name is not a similar job.
- **Must-not terms:** exclusions the user stated, such as commission-only, a specific sector, or
  roles requiring a credential they do not hold.

Combine them with quotes and OR. Keep each query narrow enough to read through.

## Board-scoped searches

Many employers post first, or only, on their applicant-tracking system. A web search limited to
the board's domain finds those postings directly:

```
site:boards.greenhouse.io OR site:job-boards.greenhouse.io "program coordinator"
site:jobs.lever.co "community" ("coordinator" OR "officer")
site:jobs.ashbyhq.com "partnerships"
site:myworkdayjobs.com "program coordinator" "Fictional City"
site:jobs.smartrecruiters.com "programme officer"
site:apply.workable.com "coordinator" remote
```

Add the location or "remote" and the exclusions with a minus sign. Search results go stale. Open
each posting and verify it.

## Public board endpoints

When the host can fetch URLs, these public JSON patterns list or confirm postings without parsing
HTML. Formats change, so treat a failed request as "unverified", never as "closed".

| Board | Pattern |
| --- | --- |
| Greenhouse | `https://boards-api.greenhouse.io/v1/boards/{board}/jobs` (append `/{id}` for one job) |
| Lever | `https://api.lever.co/v0/postings/{company}?mode=json` |
| Ashby | `https://api.ashbyhq.com/posting-api/job-board/{board}` |
| SmartRecruiters | `https://api.smartrecruiters.com/v1/companies/{company}/postings` |

`posting_intel.py` recognises these boards (and Workday, iCIMS, Workable, BambooHR, Recruitee,
Teamtailor, Jobvite, Taleo, Oracle, SuccessFactors, Personio, JazzHR, Rippling and others) from a
posting URL. It reports the vendor, the board and the job ID, and the endpoint pattern where one is
known.

## Verification ladder

1. The employer's own careers page or its applicant-tracking posting, observed by you with a date. This is the best source.
2. The board's public endpoint, which confirms that the listing is live.
3. A saved snapshot analysed offline. It shows what was stated, not what is current.
4. An aggregator listing or search snippet. Treat it as a lead only.

Record the rung reached for each find, and report anything below rung 1 as unverified.

## Finding roles before they are posted

Some roles are filled before they are advertised. With the user's agreement, look for dated,
sourced signals: new funding or grants, expansion announcements, new leadership hires, or teams
posting many related roles. Turn these into outreach ideas for
[networking-outreach](../../networking-outreach/SKILL.md), not into claims that a role exists.

## Signs a listing may be stale

These signals call for verification, not rejection: a listing open beyond the user's long-open
threshold, repeated reposts with the same text, no deadline and no recent activity, a posted date
that keeps refreshing, or the same role appearing under several requisitions. Record what you saw
and when.
