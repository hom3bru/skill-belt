# std-auth-1k7
class Forbidden(Exception):
    pass


def require_login(request):
    if request.user is None:
        raise Forbidden("sign in first")


def require_admin(request):
    require_login(request)
    if not request.user.is_admin:
        raise Forbidden("admins only")
