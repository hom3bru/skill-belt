# vln-auth-3b4
class Forbidden(Exception):
    pass


def require_owner(user, account):
    if user.account_id != account.id:
        raise Forbidden("not your account")
