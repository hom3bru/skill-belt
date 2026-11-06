# Order amounts in cents

The orders API returns `amount` as a float in euros (for example 12.5). Finance wants integer cents to end
rounding errors: the field should become `amount_cents` (1250).

Plan the change first. Nobody writes code until the plan is agreed.
