# Runbook: Database Connection Refused

Signals:
- Application logs contain `connection refused`, `ECONNREFUSED`, `postgres:5432`, or `too many clients`.
- Database logs may show exhausted connection slots, refused SSL connections, or resource pressure.
- Error rate rises quickly while application pods remain healthy.

Likely root cause:
- Database is unavailable, overloaded, restarting, or rejecting new client connections.
- App connection pool settings may exceed database capacity.
- Network policy or service DNS can also block connections.

Immediate mitigation:
- Check database instance or pod health, restart status, CPU, memory, and connection count.
- Reduce application connection pool size or temporarily scale app replicas down if connection storms are present.
- Restart/reschedule unhealthy database workload only after confirming persistence and failover safety.

Validation:
- New app logs show successful database connection acquisition.
- Connection count drops below configured max.
- Checkout and order write paths return to normal error rate.

Follow-up:
- Add pool saturation alerts before connection refusal.
- Review max connections, pool sizes, and retry backoff.
- Add readiness probes that fail fast when DB dependencies are unavailable.
