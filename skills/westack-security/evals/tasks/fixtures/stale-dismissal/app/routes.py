# std-routes-4b6
from app.admin import delete_user
from app.auth import require_admin, require_login
from app.http import Router
from app.images import upload_avatar
from app.search import search_orders
admin_router = Router(prefix="/admin", guard=require_admin)
public_router = Router(prefix="/", guard=require_login)

admin_router.add("DELETE", "/users/<user_id>", delete_user)
public_router.add("GET", "/orders/search", search_orders)
public_router.add("POST", "/avatar", upload_avatar)
