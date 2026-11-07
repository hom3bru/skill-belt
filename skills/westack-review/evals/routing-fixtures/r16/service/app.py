import os
import sqlite3

from flask import Flask, jsonify, request

app = Flask(__name__)
DB_PATH = os.environ.get("DB_PATH", "service.db")


def db():
    return sqlite3.connect(DB_PATH)


@app.get("/items")
def items():
    term = request.args.get("q", "")
    rows = db().execute("SELECT id, name FROM items WHERE name LIKE ?", ("%" + term + "%",)).fetchall()
    return jsonify([{"id": r[0], "name": r[1]} for r in rows])


@app.post("/items")
def add_item():
    name = request.get_json()["name"]
    conn = db()
    conn.execute("INSERT INTO items (name) VALUES (?)", (name,))
    conn.commit()
    return jsonify({"ok": True}), 201
