# tokens-src-3e5
"""Issue and check API tokens; the table comes from db/schema.sql."""
import secrets


def issue_token(conn, user_id, created):
    token = secrets.token_hex(16)
    conn.execute("INSERT INTO api_tokens (user_id, token, created) VALUES (?, ?, ?)", (user_id, token, created))
    return token


def check_token(conn, presented):
    row = conn.execute("SELECT user_id FROM api_tokens WHERE token = ?", (presented,)).fetchone()
    return row[0] if row else None
