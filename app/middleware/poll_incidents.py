import time

from app.config import POLL_INTERVAL_SECONDS
from app.db.dal import get_open_incidents, init_db


def main() -> None:
    init_db()
    last_seen = 0
    print("Watching for open incidents. Press Ctrl+C to stop.")
    while True:
        for incident in get_open_incidents():
            if int(incident["id"]) > last_seen:
                print("New open incident:", incident)
                last_seen = int(incident["id"])
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
