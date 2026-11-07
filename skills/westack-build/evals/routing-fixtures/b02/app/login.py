from flask import Blueprint, jsonify, request

from .users import check_password

bp = Blueprint("login", __name__)


@bp.post("/login")
def login():
    body = request.get_json(silent=True) or {}
    if not check_password(body.get("email", ""), body.get("password", "")):
        return jsonify({"error": "invalid_credentials"}), 401
    return jsonify({"ok": True})
