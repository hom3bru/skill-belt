---
type: llm
weight: 2
---
PASS if the response says the 7-day reminder is due for Example Arts (7 days left; cutoff 2026-11-11 14:00 Pacific), the 1-day reminder is due for Sample Museum (1 day left, exact cutoff unknown), no reminder is due for Done Co because the user already applied, and Demo Trust's date is ambiguous (March 12 or 3 December) and needs confirmation rather than a guess. FAIL if any of these four outcomes is wrong or the ambiguous date is silently interpreted.
