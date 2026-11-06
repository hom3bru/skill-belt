<!-- pr-desc-6d4 -->
## Summary

This PR makes the HTTP client retry. A failed request is now tried up to 5 times in all, with a 200 ms backoff between attempts, which should make the nightly sync a lot more robust.

## Testing

I added unit tests for the retry logic in tests/test_client.py, and all tests pass.
