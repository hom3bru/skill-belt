# INV-31: currency in the invoice export

`Invoice.to_dict()` in `billing/invoice.py` must include the invoice's currency code under the key `"currency"` (from `self.currency`), so the export to the ledger carries it.

Add a test. Scope: `billing/invoice.py` and `tests/test_invoice.py`.
