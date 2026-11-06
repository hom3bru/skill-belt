from flask import Flask, request

from .reports import export_pdf, monthly_total

app = Flask(__name__)


@app.get("/reports/total")
def total():
    return {"total": monthly_total(request.args["month"])}


@app.post("/reports/<int:report_id>/pdf")
def pdf(report_id):
    export_pdf(report_id)
    return {"ok": True}
