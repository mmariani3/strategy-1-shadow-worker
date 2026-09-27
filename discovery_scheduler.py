"""Bounded discovery launch and read-only audit. No promotion or broker calls."""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import requests

SCHEDULER_VERSION = "0.3.0-discovery-scheduler"


def now():
    return datetime.now(timezone.utc)


def config():
    c = dict(url=os.environ["DISCOVERY_URL"].rstrip("/"),
             token=os.environ["DISCOVERY_SCHEDULER_TOKEN"],
             action=os.getenv("SCHEDULER_ACTION", "RUN"),
             phase=os.getenv("SCAN_PHASE", "PREMARKET"),
             run_class=os.getenv("RUN_CLASS", "STRATEGY_1"),
             rules=os.getenv("RULESET_VERSION", "v0.3"),
             zone=ZoneInfo(os.getenv("LOCAL_TIMEZONE", "America/Los_Angeles")),
             hour=int(os.getenv("LOCAL_HOUR", "6")),
             minute=int(os.getenv("LOCAL_MINUTE", "0")),
             scan_hour=int(os.getenv("SCAN_LOCAL_HOUR", os.getenv("LOCAL_HOUR", "6"))),
             scan_minute=int(os.getenv("SCAN_LOCAL_MINUTE", os.getenv("LOCAL_MINUTE", "0"))),
             warmup=int(os.getenv("WARMUP_MINUTES", "0")),
             movers=int(os.getenv("MOVERS_TOP", "20")),
             news=int(os.getenv("NEWS_HOURS", "18")))
    url = urlsplit(c["url"])
    if c["action"] == "AUDIT" and not {"SCAN_LOCAL_HOUR", "SCAN_LOCAL_MINUTE"} <= os.environ.keys():
        raise ValueError("Audit requires the expected scan time separately from audit time")
    if (url.scheme != "https" or not url.hostname or url.username or url.password
            or url.query or url.fragment or not c["token"]
            or c["action"] not in {"RUN", "AUDIT"}
            or c["phase"] not in {"PREMARKET", "POST_OPEN"}
            or c["run_class"] not in {"STRATEGY_1", "INFRASTRUCTURE_TEST"}
            or c["rules"] != "v0.3" or not 0 <= c["hour"] < 24
            or not 0 <= c["minute"] < 60 or not 5 <= c["movers"] <= 50
            or not 0 <= c["scan_hour"] < 24 or not 0 <= c["scan_minute"] < 60
            or not 0 <= c["warmup"] < 60 or (c["action"] == "AUDIT" and c["warmup"] != 0)
            or not 1 <= c["news"] <= 48):
        raise ValueError("Invalid scheduler configuration")
    return c


def emit(outcome, code=1, **fields):
    print(json.dumps(dict(event="discovery_schedule", outcome=outcome,
                         observed_at=now().isoformat(), version=SCHEDULER_VERSION,
                         exit_code=code, **fields), sort_keys=True))
    return code


def get(c, path, params=None):
    response = requests.get(c["url"] + path, params=params,
        headers={"Authorization": "Bearer " + c["token"]},
        timeout=(5, 45), allow_redirects=False)
    if response.status_code != 200:
        raise ValueError("Dependency HTTP failure")
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("Invalid response")
    return data


def health(c):
    for attempt, delay in enumerate((0, 2, 5, 10)):
        if delay:
            time.sleep(delay)
        try:
            d = get(c, "/health")
            return (d.get("mode") == "SHADOW" and d.get("broker_execution_enabled") is False
                    and d.get("ruleset_version") == c["rules"])
        except (requests.RequestException, ValueError):
            if attempt == 3:
                return False


def stamp(value):
    d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if d.utcoffset() is None:
        raise ValueError("Naive timestamp")
    return d


def readback(c, day, key):
    requested_at = now()
    data = get(c, "/runs/scheduled", dict(session_date=day, phase=c["phase"], run_class=c["run_class"]))
    if (data.get("run_key") != key or data.get("mode") != "SHADOW"
            or data.get("broker_execution_enabled") is not False
            or data.get("calendar_source") != "ALPACA_PAPER_MARKET_CALENDAR"
            or data["session"]["date"] != day
            or type(data["session"]["is_trading_day"]) is not bool):
        raise ValueError("Readback identity mismatch")
    # Clock disagreement or cached results fail closed, not an invented freshness allowance.
    if not requested_at <= stamp(data["checked_at"]) <= now():
        raise ValueError("Stale readback or clock disagreement")
    return data


def assess(c, data, key):
    run = data.get("run")
    if run is None:
        return emit("MISSED_RUN", run_key=key)
    if (run.get("run_key") != key or run.get("session_date") != data["session"]["date"]
            or run.get("phase") != c["phase"] or run.get("experiment_class") != c["run_class"]
            or run.get("ruleset_version") != c["rules"] or not run.get("id")):
        return emit("RUN_IDENTITY_MISMATCH", run_key=key)
    fields = dict(run_key=key, run_id=run["id"], phase=c["phase"],
                  collection_status=run.get("status"), candidates=run.get("candidates_discovered"))
    start, end = stamp(run["created_at"]), stamp(run["updated_at"])
    if (start > end or end > stamp(data["checked_at"])
            or start.astimezone(c["zone"]).date().isoformat() != run["session_date"]):
        return emit("INVALID_RUN_TIMESTAMPS", **fields)
    if run.get("status") == "IN_PROGRESS":
        return emit("RUN_UNFINISHED", **fields)
    if c["phase"] == "PREMARKET" and end >= stamp(data["session"]["open"]):
        return emit("PREMARKET_NOT_FINISHED_BEFORE_OPEN", **fields)
    if c["phase"] == "POST_OPEN" and not stamp(data["session"]["open"]) <= start < stamp(data["session"]["close"]):
        return emit("WRONG_MARKET_PHASE", **fields)
    started_local = start.astimezone(c["zone"])
    if (started_local.hour, started_local.minute) != (c["scan_hour"], c["scan_minute"]):
        return emit("RUN_OUTSIDE_SCHEDULED_MINUTE", **fields)
    count = run.get("candidates_discovered")
    if (type(count) is not int or count < 0 or type(run.get("items_persisted")) is not int
            or count != run["items_persisted"]):
        return emit("PERSISTENCE_MISMATCH", **fields)
    channels = run.get("channel_status")
    expected = {"earnings_guidance", "corporate_news", "analyst_actions", "sector_industry",
                "premarket_movers_unusual_activity", "macro_economic_calendar", "cross_source_verification"}
    checked = {"Checked", "CHECKED_ALPACA_NEWS", "CHECKED_ALPACA_SCREENER",
               "CHECKED_FRED_RELEASE_CALENDAR", "VERIFIED"}
    gaps = sorted(k for k in expected if not isinstance(channels, dict) or channels.get(k) not in checked)
    fields["coverage_gaps"] = gaps
    if run.get("status") == "PARTIAL":
        return emit("COLLECTED_REVIEW_REQUIRED", **fields)
    if run.get("status") == "COMPLETE":
        if gaps:
            return emit("COVERAGE_STATUS_INCONSISTENT", **fields)
        return emit("COMPLETED", 0, **fields)
    return emit("COLLECTION_FAILED", **fields)


def main():
    try:
        c = config()
    except (KeyError, ValueError, TypeError):
        return emit("CONFIGURATION_ERROR", 2)
    local = now().astimezone(c["zone"])
    target = local.replace(hour=c["hour"], minute=c["minute"], second=0, microsecond=0)
    if local.weekday() >= 5:
        return emit("WEEKEND", 0)
    # The paired UTC schedules produce one known extra invocation across DST.
    beginning = target - timedelta(minutes=c["warmup"])
    deadline = target + timedelta(minutes=1)
    if any(beginning + timedelta(hours=h) <= local < deadline + timedelta(hours=h) for h in (-1, 1)):
        return emit("OTHER_DST_INVOCATION", 0)
    if c["action"] == "RUN" and not beginning <= local < deadline:
        return emit("MISSED_LAUNCH_WINDOW")
    if c["action"] == "AUDIT" and local < target:
        return emit("AUDIT_NOT_DUE")
    day = local.date().isoformat()
    key = "|".join(("STRATEGY_1", day, c["phase"], c["rules"], c["run_class"]))
    if not health(c):
        return emit("DEPENDENCY_UNAVAILABLE_OR_UNSAFE", run_key=key)
    if c["action"] == "RUN" and now() < target:
        emit("WARMED_WAITING_FOR_LAUNCH", 0, run_key=key, launch_at=target.isoformat())
        time.sleep(max(0, (target - now()).total_seconds()))
        if not health(c):
            return emit("DEPENDENCY_UNAVAILABLE_OR_UNSAFE", run_key=key)
    try:
        data = readback(c, day, key)
        if not data["session"]["is_trading_day"]:
            return emit("MARKET_CLOSED", 0, run_key=key)
        opened, closed = stamp(data["session"]["open"]), stamp(data["session"]["close"])
        if opened >= closed:
            raise ValueError("Invalid session")
        if c["action"] == "AUDIT" or data.get("run") is not None:
            return assess(c, data, key)
        # Cold starts must not silently push submission outside the authorized launch minute.
        current = now()
        if current.astimezone(c["zone"]).replace(second=0, microsecond=0) != target:
            return emit("MISSED_LAUNCH_WINDOW", run_key=key)
        if ((c["phase"] == "PREMARKET" and current >= opened)
                or (c["phase"] == "POST_OPEN" and not opened <= current < closed)):
            return emit("WRONG_MARKET_PHASE", run_key=key)
        emit("DISPATCH_INTENT", 0, run_key=key, action="RUN")
        # Exactly one POST. Ambiguous delivery is reconciled by GET, never replayed.
        response_id = None
        try:
            response = requests.post(c["url"] + "/scan/run-once",
                headers={"Authorization": "Bearer " + c["token"]},
                json=dict(session_date=day, phase=c["phase"], run_class=c["run_class"],
                          movers_top=c["movers"], news_hours=c["news"]),
                timeout=(5, 240), allow_redirects=False)
            if response.status_code == 200:
                response_id = response.json().get("run_id")
        except (requests.RequestException, ValueError, AttributeError):
            pass
        data = readback(c, day, key)
        if data.get("run") is None:
            return emit("DISPATCH_OUTCOME_UNRESOLVED", run_key=key)
        if response_id is not None and response_id != data["run"].get("id"):
            return emit("RESPONSE_ID_MISMATCH", run_key=key)
        return assess(c, data, key)
    except (requests.RequestException, ValueError, TypeError, KeyError, AttributeError):
        return emit("READBACK_UNAVAILABLE_OR_INVALID", run_key=key)


if __name__ == "__main__":
    sys.exit(main())
