# Paginate orders from query parameters

Adds `parse_page` and `clamp_page_size` so the orders endpoint can take `?page=` and `?size=` straight from the query string, and refactors `page_slice` to use them. No behaviour change for existing callers of `page_slice`.

Tests: `python -m unittest` passes.
