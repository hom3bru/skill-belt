# Billing: usage-based plans

Customers pay a base fee plus usage. Usage is metered per API call and invoiced monthly.

## Product requirements

- Customers see current usage and projected cost on a dashboard.
- An email goes out at 80% and 100% of the included allowance.
- Sales can grant a one-off credit.

## Engineering requirements

- The meter service emits one event per call to the billing queue.
- Invoices are generated on the 1st at 02:00 UTC from the previous month's events.
- Events older than 90 days are archived.
