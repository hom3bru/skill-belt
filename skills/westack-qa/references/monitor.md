# Monitor a deploy

Watches a live app for a while after a deploy and alerts on what got worse. Read-only: it loads pages and reads them; it never submits, signs in or changes anything.

## Baseline first

Before the deploy, capture `baseline.json`: for each page, its URL, the console errors it already has, the links already broken, its load time (the navigation timing's duration), and its snapshot and screenshot hashes. Without a baseline, a check taken before the first deploy step stands in and is labelled a starting reference, not proof of pre-deploy health. Never overwrite a baseline during monitoring.

## The checks

Every 60 seconds by default, for 10 minutes (up to 30; `thresholds.json`), re-open each page from its URL with a cache-busting query so a cached copy cannot pass for the new one, and record: loaded or not, console errors from that load only, broken links, load time. Append each check to `checks.json`.

A run longer than one turn uses the host's loop or a scheduled task; creating a schedule is persistent configuration and needs its own grant. Without either, run the checks within the turn and say how long the window really was.

## Alerts: changes, not absolutes

`python scripts/qacheck.py monitor baseline.json checks.json` compares each check with the baseline:

| What changed | Severity |
| --- | --- |
| the page did not load | critical |
| a console error the baseline did not have | high |
| load time more than twice the baseline's | medium |
| a broken link the baseline did not have | low |

A pattern becomes an alert only when it shows on two consecutive checks; a single check of it is an observation (`transient` if it went away, `pending` if the window ended). After a critical or high alert is confirmed, tell the user at once rather than waiting for the end. An alert that later clears keeps its place, marked resolved.

Page and overall status: broken with any confirmed critical alert, degraded with any other confirmed alert, otherwise healthy.

## What it does not claim

No pixel comparison: screenshots are evidence for a person to look at, and a changed snapshot or text hash is an observation, not an alert. Thresholds are relative to the baseline; 1.5 times slower may be normal variance.

## After a healthy run

Offer to make the latest capture the new baseline; replace it only on the user's yes.
