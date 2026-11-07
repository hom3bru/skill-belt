Add retry with backoff to the export uploader

The uploader gave up after the first failed request, so a single
timeout from the storage API failed the whole export. This change
retries failed uploads up to five times with exponential backoff
(0.5 s, 1 s, 2 s, 4 s, 8 s) and only for errors that are safe to
retry: timeouts, 429 and 5xx responses.

Testing: added unit tests for the retry schedule and ran a 2 GB
export against the staging bucket with fault injection turned on;
it completed with 14 retries and no failed parts.
