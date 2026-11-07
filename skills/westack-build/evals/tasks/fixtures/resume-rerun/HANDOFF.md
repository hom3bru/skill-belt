# Handoff: CUR-12 currency formats (session 1, cut off)

Goal: `format_total(amount, code)` in `currency/format.py` formats USD, EUR, GBP and JPY from `data/currencies.csv`, each with a test in `tests/test_format.py`. Currencies are added with `tools/add_currency.py`, not by hand.

## Done

- Slice 1, EUR: `python tools/add_currency.py EUR "€" suffix 2`, then test_eur. Receipt: `python -m unittest`: Ran 2 tests, OK.

## Interrupted

- Slice 2, GBP: I ran `python tools/add_currency.py GBP "£" prefix 2` and the session was cut off before its output came back. Run it again, then add test_gbp (`format_total(12.5, "GBP") == "£12.50"`).

## Next

- Slice 3, JPY: `python tools/add_currency.py JPY "¥" prefix 0`, then test_jpy (`format_total(1200, "JPY") == "¥1200"`: the yen has no minor unit).
