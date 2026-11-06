from flask import Flask, jsonify

app = Flask(__name__)


@app.get("/users/<int:user_id>")
def get_user(user_id):
    return jsonify({"id": user_id, "name": "Ada"})
