# tdd-fixture: the production gateway calls the payment provider over the network
import json
import urllib.request


class PaymentGateway:
    def __init__(self, api_key, base_url="https://payments.internal.example/v1"):
        self.api_key, self.base_url = api_key, base_url

    def refund(self, charge_id, amount_cents):
        body = json.dumps({"charge": charge_id, "amount": amount_cents}).encode("utf-8")
        request = urllib.request.Request(self.base_url + "/refunds", data=body, method="POST",
                                         headers={"Authorization": "Bearer " + self.api_key})
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.load(response)
