# Tracking procedure

These are default workflow and presentation conventions. The user's current
instructions and validated private context (`preferences.monitoring`, schema
version 2) override every default named below. Nothing here grants permission.
Current user instructions and the live approval rules govern every action; a
packaged procedure must never reinstate a changed or deleted permission rule.

| Convention | Context field | Default |
| --- | --- | --- |
| Status check, dated roles | `dated_check_days` | every day |
| Status check, undated roles | `undated_check_days` | every 2 days |
| Reminder windows | `reminder_windows_days` | 14, 7, 3, 1 and 0 (deadline morning) |
| Closing list horizon | `closing_horizon_days` | 14 days |
| New-find shortlist | `shortlist_size` | up to 3 |
| No-deadline urgency flag | `urgency_open_days` | open more than 14 days |
| Long-open warning | `long_open_days` | open more than 60 days |
| Delivery channel and shape | `delivery_note` | the user's existing channel |

`scripts/deadlines.py` applies these conventions deterministically to a read-only
tracker export ([helpers](../../../references/helpers.md)).

## One tracker, distinct states

- Continue the existing canonical workbook rather than starting a parallel list.
  Inspect every tab in an explicitly requested full audit, including historical,
  parked, applied, undecided and unrated records. Daily checks need not repeat a
  completed exhaustive audit.
- Track stable record ID, employer, official requisition, URL, assessment date,
  qualification gap, confidence, interest, public posting status, application
  status and explicit user decision separately.
- Read the inclusive main-list qualification-gap boundary from the user's
  current instructions or validated private context (`preferences.routing`).
  On the established 0-5 scale the boundary is inclusive: for example, a
  configured 3.5 keeps 3.5 in main; higher gaps go to Stretch and unrated roles
  stay pending. With no
  established scale/boundary, leave routing unresolved. Consult current approval
  rules before additions. A boundary is not authorization. Never silently change
  a score to make a role fit a list.
- When asked to backfill, reconcile chat-assessed roles by employer/requisition,
  preserving source assessment and its date. Original fit ranks are not gap scores.
- Retire verified closed opportunities from active views, preserving their full
  application, draft, exam, decision, score and source history. An applied role's
  public closure does not mean rejection. An assistant recommendation to skip is
  not the user's decline. Unknown completion is not missed work.
- Keep unavailable and unverified distinct from explicitly closed. A blank page,
  timeout, access restriction, search miss or generic redirect alone may be an
  identity/retrieval problem. Record the narrow finding and its evidence.

## Exact identity, reposts and freshness

Use official employer sources before aggregators. Record when observed and the
source's own posting/closing dates. Inspect role-specific application availability,
not just an HTTP success or cached description.

Search for reposts when auditing closures. Compare employer, old/new requisition,
title, function, location and requirements. New IDs receive linked separate records;
never overwrite an earlier application or reset its history. Same-ID availability
after a prior retrieval failure is not proof of a repost. A differently scoped or
more senior role is a related opportunity, not automatically a replacement.

Distinguish first publication, repost, refresh and first discovery. Unknown dates
must not be labeled newly published within 24 hours. Do not invent a closing date
from posting age. No deadline plus more than `urgency_open_days` open is an urgency
flag; more than `long_open_days` receives a long-open warning, not automatic rejection.

## Dates and countdowns

Store deadline date and exact local cutoff separately, with IANA timezone when
verified. Types include hard cutoff, date-only close, anticipated close, first
review, minimum-open date, rolling and unknown. A priority review or minimum-open
date is not a hard deadline. A passed priority date does not close a rolling role.
Do not invent midnight when the employer gives only a date.

Maintain calendar days to the stated date in the user's local timezone. A zero
means today; a negative value means the date passed, not proof of closure or a
missed application. For a first-review or anticipated date label what the
countdown measures. Unknown deadlines remain unknown, not zero or infinity.
Spreadsheet TODAY() follows the spreadsheet environment; scheduled delivery must
calculate independently in the user's explicitly selected IANA timezone, from
current instructions or validated context, and respect DST. If it is unknown or
unavailable in the host, resolve it before a timezone-dependent countdown; do not
infer it from the machine or the public example.

For capped recruitments, keep announcement date, filing opening, exact closing
cutoff and applicant cap distinct. Surface worthwhile upcoming windows before
opening, with verified requirements. An advertised closing date does not promise
availability after the cap is reached. Keep past applications/exam results separate.

## Monitoring and reminders

- Dated active/undecided roles are checked every `dated_check_days`, regardless of
  gap or shortlist.
- Active/uncertain roles without explicit closing dates are checked every
  `undated_check_days` calendar days after the last recorded check. A material new
  signal can justify earlier verification. Avoid duplicate checks by the briefing prep.
- Keep last attempted check and last successful verification distinguishable;
  failures do not refresh old evidence. Record next due date and exact blockers.
- Include active Stretch and pending/unrated opportunities. Suppress application
  nudges for applied, rejected, explicitly declined, withdrawn and verified closed
  roles; do not reopen parked decisions silently.
- Remind at first entry into each `reminder_windows_days` window (0 is deadline
  morning) if outstanding. Alert discoveries already inside a window promptly, once,
  for the tightest window entered. Deduplicate by employer/requisition/deadline/window
  against actual sent messages, not plans.
- Combine due reminders with exact local cutoff, days remaining, official link
  and a concrete next step. Unanswered calls or skipped briefings do not suppress
  a due reminder. Avoid duplicate separate morning notifications.
- Do not create redundant automations. Update existing authorized routines and
  verify tool success. No scheduler or outbound action is created by this package.

## Morning search and delivery

Before the morning briefing, search fresh for worthwhile roles first published in
the preceding 24 hours, plus relevant advance filing announcements and material
changes to existing opportunities. Favor the user's longer career story and
personal fit. Verify official opening, pay, seniority, location/eligibility and
date evidence where accessible. Report unknowns; no useful new find is acceptable.

Prepare a small actionable shortlist of up to `shortlist_size` roles with gap on the
user's scale, confidence, fit and one concrete next step. Also provide every active
role closing within `closing_horizon_days`, not just the shortlist, and newly verified
closed roles since the previous delivered update. Report a closure once rather than
repeating old closed history. Include verified reposts and material scope changes.
Use the [morning digest](../../../references/output-formats.md) shape.

Deliver through the user's existing channel and shape (their instructions or
`delivery_note`). Keep the complete written deadline/change list available even
when the main delivery is short or spoken. Do not leave the actionable update only
in silent preparation. Preserve existing invitation/acceptance rules and never start
a call or message channel the user has not set up. Prioritize already-selected
applications and authorized drafting instead of repeatedly asking the user to choose again.

## Boundaries and verification

Follow the user's current delegation and additional-task permissions.
Use permitted direct tools for supported work. Check current
permissions rather than treating this document as standing approval. No automatic
submissions, employer contact, payments, registrations or credential handling.

Before saving, verify record conservation, duplicate IDs, moved-row formulas,
counts, dates, sources and original application/decision history. Test the configured
boundary value exactly, plus unrated, overdue, date-only, priority-review, newly closed
and changed-ID cases.
Validate the actual exported workbook and affected views. Distinguish sources
checked, status established and unresolved verification. Never report all clear
when reconciliation or source checks are incomplete.
