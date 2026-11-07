<!-- task-hash-1d7 -->
# Hash API tokens

API tokens are stored in plain text in the `api_tokens` table (`db/schema.sql`). Store them hashed (SHA-256)
instead, including the tokens that already exist. Plan it; nobody writes code until the plan is agreed.
