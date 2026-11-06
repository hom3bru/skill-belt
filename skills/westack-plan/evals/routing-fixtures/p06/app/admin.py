from .auth import require_login


def dashboard(session):
    require_login(session)
    return "admin"
