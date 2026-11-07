# Design: job queue for report generation

## Problem

Report generation runs inside the web request and times out for large accounts.

## Proposal

- Add a `jobs` table in Postgres and a worker process that polls it every two seconds.
- The web request inserts a job and returns its id; the page polls `/jobs/<id>` until it is done.
- The worker writes the finished report to object storage and stores the link on the job.

## Rollout

Behind a feature flag, starting with internal accounts.
