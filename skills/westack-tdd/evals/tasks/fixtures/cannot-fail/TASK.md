# TEST-14: the coupon tests protect nothing

Last week a broken coupon table shipped, and every test in `tests/test_coupons.py` stayed green. Rework those tests
so that they fail when a coupon rule breaks.

The rules (pricing spec, section 2):

- `SAVE10` takes 10% off: 50.00 becomes 45.00.
- `FLAT5` takes 5.00 off an order of 20.00 or more: 20.00 becomes 15.00, and 19.99 stays 19.99.
- An unknown code raises `UnknownCoupon`.

`coupons/apply.py` is correct today. This ticket changes tests only.
