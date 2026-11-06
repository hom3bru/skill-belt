<!-- notes16-9c3 -->
# tidepool 1.6.0 (2026-08-12)

- Prepared statements now work in transaction mode. Set prepared_cache above 0 to turn this on.
- prepared_cache defaults to 0 (off), so upgrading changes nothing until you set it.
- Upgrading from 1.4 needs no other configuration change.
