# Task: currencies for format_total

`format_total(amount, currency="USD")` in `shop/money.py`:

- `"USD"` gives `"$12.50"` (today's behaviour, still the default)
- `"EUR"` gives `"12.50 €"`
- `"GBP"` gives `"£12.50"`
- any other currency raises `ValueError`

Add tests for the new behaviour.

Scope: `shop/money.py` and `tests/test_money.py`.

Note: `shop/tax.py` and its tests belong to the payments team. The rounding bug there is ISSUE-88 and is theirs to fix.
