# Paginate /api/orders

- GET /api/orders accepts `page` (default 1) and `size` (default 20, at most 100).
- The response keeps the `orders` key and adds `page` and `size`.
- An out-of-range page returns an empty list, not an error.
- A `size` above 100 is a 400.
