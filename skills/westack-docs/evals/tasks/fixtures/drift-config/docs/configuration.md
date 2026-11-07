<!-- config-doc-2c7 -->
# Configuration

fetchr reads three environment variables. Each one is optional.

| Variable | Default | Meaning |
| --- | --- | --- |
| `FETCHR_TIMEOUT` | 60 | seconds to wait for a response |
| `FETCHR_RETRIES` | 3 | attempts after the first failure |
| `FETCHR_FORMAT` | json | json or csv |

An unknown `FETCHR_FORMAT` stops fetchr with an error that lists the allowed values.

These defaults are covered by 6 tests in tests/test_settings.py.
