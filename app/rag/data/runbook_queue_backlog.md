# Runbook: Queue Backlog And Consumer Lag

Signals:
- Logs include `visible_messages`, `oldest_age_seconds`, `consumer lag`, or worker pool saturation.
- Producers continue to enqueue while consumers process slowly.
- Customer-visible operations become delayed rather than immediately failing.

Likely root cause:
- Consumer throughput is below producer rate.
- Downstream service throttling slows workers.
- Worker pool is saturated, deadlocked, or blocked on retries.

Immediate mitigation:
- Scale consumers or increase worker concurrency within safe downstream limits.
- Pause or rate-limit non-critical producers.
- Inspect dead-letter queues and retry storms.

Validation:
- Oldest message age decreases steadily.
- Visible message count trends down.
- Worker error rate and downstream throttling return to baseline.

Follow-up:
- Alert on oldest message age before backlog affects users.
- Add autoscaling based on queue age and message count.
- Cap retry amplification and isolate poison messages.
