---
name: opportunity-discovery
description: Find job openings that fit the user's direction and evidence. Builds target-employer lists, writes precise searches (including searches of employer applicant-tracking boards), verifies each find on the employer's own site, removes duplicates against the existing tracker and hands finds to intake. Use when the user asks to find jobs, what is out there, who is hiring, to build a target list, or to set up job alerts. Not for assessing one posting (application-intake) or for auto-applying.
---

# Opportunity discovery

For explicitly selected private context, read [loadable user context](../../context/README.md).
Version 2 `preferences.search` holds the target roles, locations, working arrangements, pay floor
and exclusions. Treat them as filters to explain, not hard rules, unless the user says so. Current
instructions override saved preferences.

Read [search strategy](references/search-strategy.md) and
[integrity and safety](../../references/integrity-and-safety.md). Use only the search, browsing and
automation tools that are actually available. Without web access, give the user the exact searches
to run and the way to verify what they find. Do not present remembered listings as current.

1. **Anchor the search in the user's case.** Take target titles and adjacent titles from the user's
   evidence and stated direction, not from generic lists. Include titles that differ in wording but
   match in function, since employers name the same work differently. Note which constraints are
   firm (location, work authorisation, pay floor) and which are preferences.
2. **Search the primary sources first.** Use employer careers pages and their applicant-tracking
   boards (Greenhouse, Lever, Ashby, Workday, SmartRecruiters and others) before aggregators. Use
   the board-scoped search patterns in the reference. When the host can fetch, prefer the board's
   public JSON endpoint where one exists. Aggregators are useful for leads but never final proof of
   status or dates. For a target employer's board, save the public JSON response with the host's
   fetch tool, then run `scripts/board_feed.py` on it with `--tracker` and `--previous`. It
   normalises the postings, applies the user's title and location filters, and marks roles
   already tracked and possible reposts. It also lists what is new and what has disappeared since
   the last run, which tracking verifies before any closure.
3. **Verify each find.** Use the official posting URL, the employer, the requisition or ATS job ID,
   location and arrangement, pay if stated, the posted date and the deadline. Record when you
   observed it. If you have a saved snapshot and an executor, `scripts/posting_intel.py analyze`
   extracts the structured data and the warning signs. Keep "first seen by us", "date posted" and
   "reposted" as separate facts. An unknown date is never called "new".
4. **Screen out noise.** Exclude what the user excluded. Flag scam signals, origins you could not
   confirm, listings that have been open a long time or keep reappearing, and roles whose pay or
   location conflicts with a firm constraint. Say why each one was dropped, so the user can override.
5. **Remove duplicates against the canonical tracker.** Match on exact URL or requisition and
   employer, using the tracker identity rules. A related role with a new requisition is a new
   record linked to the old one. Do not add rows unless the user has authorised tracker edits.
6. **Deliver a ranked shortlist.** List only roles worth the user's attention, each with a one-line
   reason grounded in their evidence, the verification status and the next step. Usually the next
   step is intake. Include the search log: the queries run, the date, the sources checked and the
   sources that could not be reached. "No worthwhile new roles" is a valid result.

Saved searches and alerts need the user's permission and a real host automation or site feature.
Never claim an alert exists until a tool has confirmed it. Respect site terms. Do not scrape behind
logins, bypass CAPTCHAs or rate limits, or bulk-apply. A target list and searches are preparation,
not applications.

Resolve shared local paths through the [user profile](../../references/user-profile.md). Private application context still requires explicit selection.
