# Shorter sessions; the cart subtotal moves to totals.py

Files changed (3): app/auth.py, app/cart.py, app/totals.py

- app/auth.py: the session cookie lifetime drops from 30 days to 12 hours, and the cookie gets SameSite=Lax.
- app/cart.py, app/totals.py: `subtotal` moves from cart.py into totals.py; cart.py imports it.

Tests: `python -m unittest` passes.
