from .auth import login, require_login


def home(session):
    require_login(session)
    return "home"


def sign_in(users, form):
    return login(users, form["email"], form["password"])
