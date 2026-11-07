# std-http-6d9
class Router:
    """Routes under one prefix; guard(request) runs before every handler on this router."""

    def __init__(self, prefix, guard):
        self.prefix, self.guard, self.routes = prefix, guard, []

    def add(self, method, path, handler):
        self.routes.append((method, self.prefix.rstrip("/") + path, handler))

    def dispatch(self, request, handler, *args):
        self.guard(request)
        return handler(request, *args)
