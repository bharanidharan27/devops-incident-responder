from app.db.dal import init_db, record_incident


def seed_incidents() -> list[int]:
    init_db()
    samples = [
        {
            "service": "payment-service",
            "environment": "prod",
            "severity": "CRITICAL",
            "title": "Checkout HTTP 500 spike",
            "description": "Synthetic alert for checkout failures.",
            "alert_type": "HTTP 500",
            "source": "seed",
            "external_id": "seed-payment-http-500",
            "payload": {"details": "synthetic cloudwatch-like alert", "service": "payment-service"},
        },
        {
            "service": "postgres",
            "environment": "prod",
            "severity": "HIGH",
            "title": "Database connection refused",
            "description": "Application cannot connect to postgres:5432.",
            "alert_type": "db connection refused",
            "source": "seed",
            "external_id": "seed-db-conn-refused",
            "payload": {"details": "connection refused to postgres:5432"},
        },
        {
            "service": "payment-service",
            "environment": "prod",
            "severity": "HIGH",
            "title": "Container OOMKilled",
            "description": "Kubelet reported memory pressure for payment service.",
            "alert_type": "OOMKilled",
            "source": "seed",
            "external_id": "seed-payment-oom",
            "payload": {"details": "kubelet OOMKilled container payment-service"},
        },
    ]
    ids = []
    for sample in samples:
        ids.append(record_incident(status="OPEN", **sample))
    return ids


if __name__ == "__main__":
    print("Seeded incidents:", ", ".join(str(item) for item in seed_incidents()))
