"""Authored new product slice. No imports from donor fixtures."""
import re


class ReplayTotal:
    """One owner of event identity/state; total is derived rather than separately stored."""
    def __init__(self):
        self.entries = {}

    def add(self, identity, amount):
        if not isinstance(identity, str) or not identity:
            raise ValueError("nonempty identity required")
        # ASCII-only canonical spelling: no '-0', leading zeros, signs, whitespace, underscores
        # or non-ASCII digits, which Python int() would otherwise accept.
        if not isinstance(amount, str) or re.fullmatch(r"0|-?[1-9][0-9]*", amount) is None:
            raise ValueError("canonical decimal-string integer required")
        canonical = amount
        if identity in self.entries:
            if self.entries[identity] != canonical:
                raise ValueError("conflicting duplicate")
            return False
        self.entries[identity] = canonical
        return True

    def total(self):
        return str(sum(int(value) for value in self.entries.values()))

    def snapshot(self):
        return {"version": 1, "entries": dict(self.entries)}

    @classmethod
    def restore(cls, snapshot):
        if (not isinstance(snapshot, dict) or set(snapshot) != {"version", "entries"}
                or type(snapshot["version"]) is not int or snapshot["version"] != 1
                or not isinstance(snapshot["entries"], dict)):
            raise ValueError("unsupported or malformed snapshot")
        ledger = cls()
        for identity, amount in snapshot["entries"].items():
            ledger.add(identity, amount)
        return ledger
