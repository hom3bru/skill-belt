# vln-db-7d8
class Invoice:
    def __init__(self, invoice_id, account, total):
        self.id, self.account, self.total = invoice_id, account, total

    @classmethod
    def load(cls, invoice_id):
        return STORE[invoice_id]

    @classmethod
    def for_account(cls, account):
        return [i for i in STORE.values() if i.account.id == account.id]

    def to_json(self):
        return {"id": self.id, "account": self.account.id, "total": self.total}


STORE = {}
