<!-- task-scg-4b8 -->
# Task: quote CSV fields for the finance download

## Request

Finance opens the download in a spreadsheet, and a name such as `Smith, Jane` splits into two columns. Make `to_csv` in export.py quote fields the way RFC 4180 does.

## Acceptance

1. A field that contains a comma is wrapped in double quotes.
2. A double quote inside a field is doubled, and that field is wrapped in double quotes.
3. Tests cover both rules, and the project's check, `python check.py`, passes.

## Completion note (from the implementing agent)

Quoting added in export.py, with three tests in QuotingTests. `python check.py`: "6 tests, 0 failed. All checks passed." Done.
