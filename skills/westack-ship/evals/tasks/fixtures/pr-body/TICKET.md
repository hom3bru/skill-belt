# Issue #311: retry once when the billing API answers 503

The billing API sometimes answers 503 Service Unavailable for a moment during deploys. `fetch()` should try once more when the first answer is a 503, and still raise for any other error and for a second 503.
