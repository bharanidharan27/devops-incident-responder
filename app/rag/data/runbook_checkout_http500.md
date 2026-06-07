# Runbook: Checkout HTTP 500 Spike

Signals:
- HTTP 500 rate rises on `/checkout` or `/payments/authorize`.
- Logs include `NullPointerException`, `null payment_method`, `HTTP 500`, or canary failure after a deploy.
- Upstream services such as card gateway may still be healthy, which points back to application logic.

Likely root cause:
- A recent payment-service deploy introduced unsafe null handling or a request payload compatibility bug.
- The checkout route fails before or after authorization, producing 500s while dependencies remain mostly healthy.

Immediate mitigation:
- Roll back payment-service to the last known good revision.
- If using canary release, stop the canary and route traffic to stable pods.
- Enable circuit breaker or fallback for non-critical checkout enrichments.

Validation:
- HTTP 500 rate drops below alert threshold.
- New checkout traces complete without `NullPointerException`.
- Synthetic checkout canary succeeds for card and wallet payment methods.

Follow-up:
- Add regression tests for missing or null payment method fields.
- Require deploy annotations in logs and dashboards.
- Add structured error codes around checkout payment validation.
