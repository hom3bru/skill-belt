from flask import Flask, jsonify

app = Flask(__name__)


@app.get("/orders/<int:order_id>")
def get_order(order_id):
    return jsonify({"id": order_id, "status": "open"})


@app.post("/orders")
def create_order():
    return jsonify({"id": 1}), 201
