import sqlite3
import subprocess

DB = "reports.db"


def monthly_total(month):
    conn = sqlite3.connect(DB)
    query = "SELECT SUM(total) FROM invoices WHERE month = '%s'" % month
    return conn.execute(query).fetchone()[0]


def export_pdf(report_id):
    html, pdf = "/tmp/report-%d.html" % report_id, "/tmp/report-%d.pdf" % report_id
    subprocess.run("wkhtmltopdf %s %s" % (html, pdf), shell=True, check=True)
