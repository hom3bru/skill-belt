from .pager import paginate


def export_page(items, page):
    return paginate(items, page, 100)
