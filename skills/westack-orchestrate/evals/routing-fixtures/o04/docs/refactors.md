# Refactors queued for this sprint

1. Split `app/orders.py` into `orders/models.py` and `orders/service.py`.
2. Replace the hand-rolled date parsing in `app/dates.py` with the standard library.
3. Move all HTTP calls in `app/clients.py` behind one `HttpClient` class.

All three touch different files. `app/clients.py` is imported by `app/orders.py`.
