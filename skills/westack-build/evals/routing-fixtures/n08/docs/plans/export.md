# Plan: export feature

1. S1: add `GET /export` that streams all of the user's notes as JSON.
2. S2: add a `format=csv` option.
3. S3: add the "Export" button to the notes page.
4. S4: document the endpoint in `docs/api.md`.

Rollback: each slice is its own commit; revert S3 first if the button misbehaves.
