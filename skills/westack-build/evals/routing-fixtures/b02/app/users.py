FAKE_USERS = {"ada@example.com": "example-only"}


def check_password(email, password):
    return FAKE_USERS.get(email) == password
