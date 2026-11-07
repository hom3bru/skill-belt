# Migration plan: archive orders

Status: approved 2026-10-20.

1. Add an index on `orders.status` (migration 0007). Done.
2. Backfill `status` for orders created before 2024. Done.
3. Add the `archived_at` column (nullable timestamp) and set it when an order is archived.
4. Stop reading archived orders in the dashboard queries.
5. Drop the old `is_archived` flag.
