# CI-57: a session test is flaky

`test_session_expires_after_its_ttl` in `tests/test_sessions.py` fails on CI about one run in thirty:

    FAIL: test_session_expires_after_its_ttl (tests.test_sessions.SessionTests)
    AssertionError: False is not true

Make the session tests reliable. The expiry rule in `auth/sessions.py` is correct and must not change: a session
expires once `ttl_seconds` have passed since its last activity, and at exactly `ttl_seconds` it has expired.
`touch()` records new activity.
