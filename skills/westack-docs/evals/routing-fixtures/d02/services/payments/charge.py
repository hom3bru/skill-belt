def charge(provider, card_token, amount_cents, currency="EUR"):
    if amount_cents <= 0:
        raise ValueError("amount must be positive")
    return provider.charge(card_token=card_token, amount=amount_cents, currency=currency)
