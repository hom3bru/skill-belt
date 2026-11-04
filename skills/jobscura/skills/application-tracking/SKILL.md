---
name: application-tracking
description: Keep the one canonical job tracker current - audit status, retire verified closures, investigate reposts, compute deadline countdowns and reminder windows in the user's time zone, plan status checks, and prepare the morning digest of what is due, closing, new or changed. Use when the user asks what is due or closing, for a status audit, a morning job update, deadline reminders, or to reconcile the tracker. Uses existing host tools; never claims a reminder was sent without a receipt.
---

# Job status, deadlines and morning delivery

For explicitly selected private context, read [loadable user context](../../context/README.md).
Current user instructions and live permissions override saved preferences.


Read [tracking procedure](references/tracking-procedure.md) and the existing
[assessment method](../application-intake/references/assessment-method.md).
This skill is a workflow, not an independent scheduler or live vacancy database.
Use the host's actual file, browsing, conversation and automation tools. Never
claim a scheduled check, save or reminder exists merely because this file says so.

1. Read the current canonical tracker, all relevant tabs, and the user's latest
   instructions and live approval rules. Preserve its identity and version guard.
2. Resolve each employer and requisition. Verify current application acceptance
   with an official page; record inaccessible or contradictory evidence as unknown.
3. Reconcile new discoveries, prior assessments, closures and reposts. Keep
   application history and user decisions separate from public vacancy status.
4. Maintain days to a stated date, deadline type, cutoff/timezone, last checked,
   next check, evidence, and actual reminder receipts. Compute them with
   `scripts/deadlines.py` on a read-only export when an executor is available
   ([helpers](../../references/helpers.md)). Model date arithmetic is a known failure
   point. Cadence, reminder windows and horizon come from the user's current
   instructions or validated context `preferences.monitoring`. When neither sets them,
   the documented defaults apply: daily for dated roles, every other day for undated
   roles, reminders at 14/7/3/1/0 days, a 14-day horizon.
5. Prepare and deliver the requested morning changes in the [morning digest](../../references/output-formats.md)
   format: worthwhile new discoveries, every active role closing within the horizon,
   and newly closed roles once. Use [opportunity-discovery](../opportunity-discovery/SKILL.md)
   for the fresh search.
   When the user wants reminders without a scheduler, `deadlines.py --ics` writes a
   calendar file they can import into their own calendar. Importing it is their action;
   report it as prepared, not as reminders set.
6. Before saving a tracker edit, compare exports taken before and after it with
   `scripts/tracker_diff.py`. Do not save while it reports `blocked` (lost records,
   changed identities, dropped columns, application history moving backwards), unless
   the user confirms each item. Link repost candidates; never merge them.
7. Verify edits and supported automation changes, then report what changed and
   what remains unverified. A successful fetch or old search snippet is not proof
   a job is open. Never submit an application or contact an employer from this skill.
