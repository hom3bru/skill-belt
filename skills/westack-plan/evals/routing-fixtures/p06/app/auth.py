import hashlib


def hash_password(password, salt):
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def login(users, email, password):
    user = users.get(email)
    if user and user["hash"] == hash_password(password, user["salt"]):
        return {"user": email}
    return None


def require_login(session):
    if "user" not in session:
        raise PermissionError("login required")
