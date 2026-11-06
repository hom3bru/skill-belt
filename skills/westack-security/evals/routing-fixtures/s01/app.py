import sqlite3

from flask import Flask, abort, jsonify, send_from_directory

app = Flask(__name__)
DB = "invoices.db"
PDFS = "invoices"


def db():
    return sqlite3.connect(DB)


@app.get("/invoices/<int:invoice_id>")
def get_invoice(invoice_id):
    row = db().execute("SELECT id, customer, total FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if row is None:
        abort(404)
    return jsonify(id=row[0], customer=row[1], total=row[2])


@app.get("/invoices/<int:invoice_id>/pdf")
def get_pdf(invoice_id):
    return send_from_directory(PDFS, "%d.pdf" % invoice_id)
