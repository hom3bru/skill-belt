ADMINS = {"ada": "example-only"}


def check_password(user, password):
    return ADMINS.get(user) == password
