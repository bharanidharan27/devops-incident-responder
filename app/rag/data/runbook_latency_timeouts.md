# Runbook: Latency And Upstream Timeouts

Signals:
- Logs include `upstream_timeout`, `HTTP 504`, `p95_latency_ms`, `thread_pool saturated`, or retry budget exhaustion.
- The frontend or gateway reports slow checkout responses while some requests eventually succeed.
- Dependency logs show slow database queries, saturated thread pools, or queued work.

Likely root cause:
- Checkout is blocked on a slow upstream service such as inventory, pricing, or fraud checks.
- Retries amplify load and increase queueing.
- Dependency capacity is exhausted or a lock/contention issue is delaying responses.

Immediate mitigation:
- Identify the slow dependency from traces and logs.
- Scale the dependency or reduce concurrency to protect it from overload.
- Lower retry count, enable circuit breaker, or temporarily bypass non-critical enrichment.

Validation:
- p95 and p99 latency return below SLO.
- HTTP 504 rate falls.
- Dependency thread pool and queue depth normalize.

Follow-up:
- Add per-dependency latency budgets.
- Use bulkheads and circuit breakers for non-critical dependencies.
- Alert on queue depth and retry amplification, not only final 5xx/504 rate.
