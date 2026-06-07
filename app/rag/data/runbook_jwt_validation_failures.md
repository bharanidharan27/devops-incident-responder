# Runbook: JWT Validation Failures

Signals:
- Logs include `JWT validation failed`, `unknown signing key`, `signature verification failed`, or stale JWKS cache.
- API gateway or user-service returns elevated 401s across multiple endpoints.
- Incident starts near an identity provider key rotation or auth deployment.

Likely root cause:
- Service cache has stale JWKS keys.
- The token issuer, audience, or key ID configuration changed unexpectedly.
- Identity provider key rotation did not propagate to consumers.

Immediate mitigation:
- Force refresh JWKS cache in affected services.
- Verify issuer, audience, and `kid` values against the identity provider.
- Roll back key rotation or auth config if a broad outage is active.

Validation:
- New tokens validate successfully.
- 401 rate returns to baseline.
- JWKS cache age is recent and contains the current key ID.

Follow-up:
- Add alerting on JWKS refresh failures and cache age.
- Test key rotation in staging with production-like cache TTLs.
- Make auth errors structured by issuer, audience, and key ID.
