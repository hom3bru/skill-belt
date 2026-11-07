<!-- task-utw-5d2 -->
# Task: weekend due dates

## Request

Invoices can come due on a Saturday or a Sunday, when the bank does not process payments. Move a due date that falls on a weekend to the following Monday.

## Acceptance

1. A due date that falls on a Saturday or a Sunday moves to the following Monday.
2. Due dates on weekdays do not change.
3. `python -m unittest -v` passes.

## Completion note (from the implementing agent)

due_date in invoice.py now moves weekend dates forward; test_weekend_due_dates_roll_to_monday covers it. `python -m unittest -v`: 3 tests, OK. Done.
