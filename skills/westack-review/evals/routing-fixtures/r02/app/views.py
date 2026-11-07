from .pager import paginate


def list_page(items, request):
    return paginate(items, int(request.get("page", 1)))
