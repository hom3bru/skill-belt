from flask import Blueprint, g, jsonify, request

from . import db

bp = Blueprint("payments", __name__)


@bp.post("/payments")
def create_payment():
    body = request.get_json()
    payment = db.create(g.user_id, body["amount"], body["currency"], body["card_token"])
    return jsonify(payment), 201


@bp.get("/payments/<payment_id>")
def get_payment(payment_id):
    return jsonify(db.get(payment_id))


@bp.post("/payments/<payment_id>/refund")
def refund(payment_id):
    return jsonify(db.refund(payment_id, request.get_json().get("amount")))
