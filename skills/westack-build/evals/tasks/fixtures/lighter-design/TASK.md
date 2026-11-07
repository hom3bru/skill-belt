# SHOP-9: discount for large orders

Orders of 100.00 or more get 10% off the subtotal; smaller orders are unchanged.

Implementation, as the ticket's author wrote it: add a package `shop/discounts/` with an abstract `DiscountStrategy`, a `ThresholdDiscount` subclass, a `DiscountRegistry` and a `make_discount()` factory, and have `shop/pricing.py` look the strategy up in the registry, so more discount types can be added later. No other discount type is planned.

Acceptance: `total(100.00) == 90.00`, `total(99.99) == 99.99`, and the existing tests stay green.
