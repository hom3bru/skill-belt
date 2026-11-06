# scb-pay-4b9
import os

API_URL = os.environ["PAYMENTS_API_URL"]
API_KEY = os.environ["PAYMENTS_API_KEY"]


def charge_headers():
    return {"Authorization": "Bearer " + API_KEY}
