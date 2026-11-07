from .auth import login


def token(users, body):
    return login(users, body["email"], body["password"])
