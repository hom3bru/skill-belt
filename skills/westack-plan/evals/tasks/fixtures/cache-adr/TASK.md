<!-- task-cache-2a4 -->
# Faster quotes

Every `GET /quote` call fetches the exchange rate from the rates provider (`quotes/rates.py`, about 300 ms each),
and the quote page makes several calls per view. Add a shared Redis cache in front of `fetch_rate` so repeated
quotes are fast.

Plan the change first; no code yet.
