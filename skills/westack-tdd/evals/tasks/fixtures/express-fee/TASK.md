# Express shipping

From the product spec (v3, section 4.2):

> Express parcels pay the standard fee doubled, plus a flat handling charge of 3.00.
> Worked example: a 4 kg express parcel costs 15.00.

`shipping_fee(weight_kg, express=False)` in `shipping/fees.py` already takes the flag but ignores it.
