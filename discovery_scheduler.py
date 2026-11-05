import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import time

SCHEDULER_VERSION = "0.2.0-discovery-scheduler"

DISCOVERY_URL = os.getenv(
    "DISCOVERY_URL",
    "https://strategy-1-discovery-coordinator.onrender.com",
).rstrip("/")
DISCOVERY_SCHEDULER_TOKEN = os.getenv("DISCOVERY_SCHEDULER_TOKEN")

SCAN_PHASE = os.getenv("SCAN_PHASE", "PREMARKET")
RUN_CLASS = os.getenv("RUN_CLASS", "STRATEGY_1")
MOVERS_TOP = int(os.getenv("MOVERS_TOP", "20"))
NEWS_HOURS = int(os.getenv("NEWS_HOURS", "18"))

LOCAL_TIMEZONE = os.getenv("LOCAL_TIMEZONE", "America/Los_Angeles")
LOCAL_HOUR = int(os.getenv("LOCAL_HOUR", "6"))
LOCAL_MINUTE = int(os.getenv("LOCAL_MINUTE", "0"))


def wait_for_discovery() -> bool:
    delays = (0, 2, 5, 10)
    last_error = "unknown dependency error"
    for attempt in range(4):
        if attempt:
            time.sleep(delays[attempt])
        try:
            response = requests.get(
                f"{DISCOVERY_URL}/health",
                timeout=(5, 45),
            )
            if response.ok:
                return True
            last_error = (
                f"HTTP {response.status_code}: "
                f"{response.text[:300]}"
            )
        except requests.RequestException as exc:
            last_error = (
                f"{type(exc).__name__}: {str(exc)[:300]}"
            )
    print(
        "ERROR: Discovery Coordinator unavailable "
        f"after cold-start retries: {last_error}"
    )
    return False


def main() -> int:
    if not DISCOVERY_SCHEDULER_TOKEN:
        print("ERROR: DISCOVERY_SCHEDULER_TOKEN is not configured.")
        return 2

    now_local = datetime.now(ZoneInfo(LOCAL_TIMEZONE))

    # Render cron schedules are UTC. The cron job is deliberately
    # configured to fire at both UTC offsets that can correspond to
    # the desired Pacific time. Only the correct local-time invocation
    # actually calls the coordinator. This makes DST changes fail-safe.
    if (
        now_local.hour != LOCAL_HOUR
        or now_local.minute != LOCAL_MINUTE
    ):
        print(
            "SKIP: local time is "
            f"{now_local.isoformat(timespec='minutes')}; "
            f"target is {LOCAL_HOUR:02d}:{LOCAL_MINUTE:02d} "
            f"{LOCAL_TIMEZONE}."
        )
        return 0

    payload = {
        "session_date": now_local.date().isoformat(),
        "phase": SCAN_PHASE,
        "run_class": RUN_CLASS,
        "movers_top": MOVERS_TOP,
        "news_hours": NEWS_HOURS,
    }

    if not wait_for_discovery():
        return 1

    try:
        response = requests.post(
        f"{DISCOVERY_URL}/scan/run-once",
        headers={
            "Authorization": f"Bearer {DISCOVERY_SCHEDULER_TOKEN}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=(5, 240),
        )
    except requests.RequestException as exc:
        print(
            "ERROR: discovery scan request failed after health check: "
            f"{type(exc).__name__}: {str(exc)[:500]}"
        )
        return 1

    print(f"HTTP {response.status_code}")
    print(response.text[:4000])

    if not response.ok:
        return 1

    data = response.json()
    if data.get("run_id") is None:
        print("ERROR: coordinator response did not include run_id.")
        return 1

    print(
        "PASS: "
        f"phase={SCAN_PHASE} "
        f"run_id={data.get('run_id')} "
        f"status={data.get('status')} "
        f"idempotent_replay={data.get('idempotent_replay')}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
