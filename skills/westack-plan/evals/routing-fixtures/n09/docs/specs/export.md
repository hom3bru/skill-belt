# Export

A user can export all of their notes.

- `GET /export` streams the notes as JSON, newest first.
- `GET /export?format=csv` returns the same notes as CSV with a header row.
- The notes page gets an "Export" button that downloads the JSON file.
- Notes marked private are included; deleted notes are not.
