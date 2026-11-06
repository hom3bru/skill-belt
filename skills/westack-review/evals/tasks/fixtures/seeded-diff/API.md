# Orders API

`GET /orders?page=N&size=M`

- `page`: 1-based. A missing or malformed value is treated as page 1, on purpose: crawlers that follow stale links get the first page instead of an error.
- `size`: items per page. The default is 20; other values are clamped to 1..100.
