# db-src-8f2
# The orders API reaches Postgres through the tidepool pooler and prepares its order lookup once per connection.
POOL_MODE = "transaction"
USE_PREPARED = True
ORDER_LOOKUP = "SELECT id, total_cents FROM orders WHERE id = $1"
