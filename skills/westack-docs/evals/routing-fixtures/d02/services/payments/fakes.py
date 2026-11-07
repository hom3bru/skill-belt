class FakeProvider:
    def __init__(self):
        self.charges = []

    def charge(self, **kwargs):
        self.charges.append(kwargs)
        return {"status": "succeeded", **kwargs}
