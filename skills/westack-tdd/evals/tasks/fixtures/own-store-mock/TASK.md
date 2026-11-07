# ORD-31: refunds

Add `OrderService.refund(order_id)` in `orders/service.py`:

- the order is marked `refunded` in the order store, so `store.get(order_id).status == "refunded"` afterwards;
- the full amount is refunded through the payment gateway exactly once, as `gateway.refund(charge_id, amount_cents)`;
- an order that is not `paid` raises `NotRefundable`, and then the store is unchanged and the gateway is not called.

Example: order `o-1`, paid 2599 cents with charge `ch_9`, ends up `refunded`, and the gateway receives
`refund("ch_9", 2599)`.

`orders/store.py` is our own in-memory store (the SQL store has the same interface). `orders/gateway.py` talks to
the real payment provider over the network.
