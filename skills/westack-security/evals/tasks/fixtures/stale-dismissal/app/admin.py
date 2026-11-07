# std-admin-7v3
from app.db import execute


def delete_user(request, user_id):
    execute("DELETE FROM users WHERE id = ?", (int(user_id),))
    return {"deleted": int(user_id)}
