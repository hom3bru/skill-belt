<!-- blog-s5e -->
# Hookline now requires timestamp checks

Posted 2026-09-20.

Good news for security: the Hookline webhook spec now requires receivers to reject stale deliveries. Anything older
than five minutes MUST be refused, so update your receivers before your partners start testing for it.
