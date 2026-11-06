# tdd-fixture: registration


class EmailTaken(Exception):
    pass


def register(store, mailer, email, name):
    """Add a user to `store` (a dict keyed by normalised email) and return the new record."""
    email = email.strip().lower()
    if email in store:
        raise EmailTaken(email)
    store[email] = {"name": name}
    return store[email]
