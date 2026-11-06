# Plan: monthly totals report

Goal: finance gets each month's totals per account as a PDF, in a monthly email.
Plan status: approved (Dana, 2026-10-20)

## Requirements
- R1: monthly totals per account
- R2: the totals as a PDF
- R3: a monthly email to finance with the PDF attached

## Decisions
- D1 [implementation, repository]: totals come from reports/totals.py, in cents

## Slices

### S1: Monthly totals query
- Depends on: none
- Delivers: R1
- Paths: reports/totals.py, tests/test_totals.py
- Acceptance:
  - A1 (automated): `python -m unittest tests.test_totals -v` shows test_totals_per_account passing
- Rollback: revert the commit
- Status: done
- Receipts: A1=run on 2026-10-24, 3 passed

### S2: PDF layout of monthly totals
- Depends on: S1
- Delivers: R2
- Paths: reports/pdf.py, tests/test_pdf.py
- Acceptance:
  - A1 (automated): `python -m unittest tests.test_pdf -v` shows test_pdf_has_one_row_per_account passing
- Rollback: revert the commit
- Status: active
- Receipts: none

### S3: Monthly email with the PDF
- Depends on: S2
- Delivers: R3
- Paths: reports/mail.py, tests/test_mail.py
- Acceptance:
  - A1 (automated): `python -m unittest tests.test_mail -v` shows test_email_attaches_the_pdf passing
  - A2 (human): Dana confirms the first email arrived with its attachment
- Rollback: revert the commit and turn the monthly job off
- Status: planned
- Receipts: none

## Progress
- 2026-10-24: S1 done (receipt above). S2 started: reports/pdf.py lays out the rows; its test is not written yet.
