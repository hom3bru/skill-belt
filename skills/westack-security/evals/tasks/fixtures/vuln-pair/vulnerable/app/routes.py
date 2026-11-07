# vln-routes-9e0
from app.invoices import get_invoice, list_invoices

# Every route runs after the session middleware, which sets request.user to the signed-in customer
# and request.account to the account named in the path.
ROUTES = {
    ("GET", "/accounts/{account}/invoices"): list_invoices,
    ("GET", "/invoices/{invoice_id}"): get_invoice,
}
