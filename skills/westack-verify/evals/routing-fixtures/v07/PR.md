# Add CSV export for reports

Meets all five acceptance criteria:

1. `GET /reports/<id>.csv` returns a CSV file.
2. The header row matches the on-screen columns.
3. Large reports stream instead of loading in memory.
4. Only users who can see the report can download it.
5. The download is logged.
