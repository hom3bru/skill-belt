# vln-inv-5c6
from app.auth import require_owner
from app.db import Invoice


def list_invoices(request):
    require_owner(request.user, request.account)
    return [i.to_json() for i in Invoice.for_account(request.account)]


def get_invoice(request, invoice_id):
    invoice = Invoice.load(invoice_id)
    return invoice.to_json()
