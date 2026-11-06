# sec-client-2c3
import os

API_KEY = os.environ["PAYMENTS_API_KEY"]


def headers():
    return {"Authorization": "Bearer " + API_KEY}
