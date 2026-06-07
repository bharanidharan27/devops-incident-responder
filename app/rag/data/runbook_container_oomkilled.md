# Runbook: Container OOMKilled

Signals:
- Kubelet or ECS logs include `OOMKilled`, `exit_code=137`, or memory pressure.
- Service logs include `OutOfMemoryError`, high heap usage, long GC pauses, or growing request queues.
- Pod restart count rises and readiness checks fail intermittently.

Likely root cause:
- Container memory limit is too low for current traffic or workload.
- A recent code path introduced a leak or memory-heavy operation.
- A traffic spike increased concurrent in-flight requests beyond capacity.

Immediate mitigation:
- Increase memory limit or scale replicas to reduce per-pod pressure.
- Roll back recent changes if OOM started after deploy.
- Disable memory-heavy features such as PDF generation or large export jobs if possible.

Validation:
- Restart count stops increasing.
- Memory usage stabilizes below 80 percent of limit.
- GC pause time and request queue depth return to baseline.

Follow-up:
- Capture heap profiles during elevated memory usage.
- Add memory and restart alerts before availability impact.
- Load test memory-heavy endpoints with production-like payloads.
