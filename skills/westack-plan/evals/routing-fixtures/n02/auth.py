def find_user(users, email):
    for usr in users:
        if usr["email"] == email:
            return usr
    return None


def is_admin(usr):
    return usr.get("role") == "admin"
