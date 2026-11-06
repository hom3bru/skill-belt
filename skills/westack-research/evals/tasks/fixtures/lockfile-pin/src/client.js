// client-l3c
// The orders API client. Bursts of retries from many browsers hit the API at the same moment after an outage.
import { createClient } from "fetchwell";

export const api = createClient({
  baseUrl: "/api",
  retry: { attempts: 3, backoff: "exponential" },
});
