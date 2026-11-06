from typing import Protocol


class PaymentProvider(Protocol):
    def charge(self, amount_cents: int, currency: str, token: str) -> str:
        """Charge the card and return a payment id."""

    def refund(self, payment_id: str, amount_cents: int) -> None:
        """Refund part or all of a payment."""
