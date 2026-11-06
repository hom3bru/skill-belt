# Plan: reports API

Approved.

1. `GET /reports` lists the user's reports.
2. `GET /reports/<id>` returns one report.
3. `POST /reports` creates a report from a JSON body with `title` and `query`.

Each endpoint returns JSON and uses the existing login check.
