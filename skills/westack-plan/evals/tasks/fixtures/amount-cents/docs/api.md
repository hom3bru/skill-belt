<!-- docs-api-6b1 -->
# Orders API

Public API, used by our partner integrations (see the partner agreement for change notice periods).

`GET /orders` returns a list of orders:

| Field | Type | Meaning |
| --- | --- | --- |
| id | integer | order id |
| amount | number | order total in euros, for example 12.5 |
| currency | string | ISO 4217 code |
