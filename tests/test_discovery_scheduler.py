from copy import deepcopy
from datetime import date, datetime, timezone
from types import SimpleNamespace
import json

import pytest
import requests
from fastapi.testclient import TestClient

import discovery_scheduler as s
import discovery_coordinator as d

UTC = timezone.utc
NOW = datetime(2026, 9, 28, 13, 0, 20, tzinfo=UTC)
KEY = "STRATEGY_1|2026-09-28|PREMARKET|v0.3|INFRASTRUCTURE_TEST"
CHANNELS = {k: "Checked" for k in ("earnings_guidance", "corporate_news", "analyst_actions",
    "sector_industry", "premarket_movers_unusual_activity", "macro_economic_calendar", "cross_source_verification")}


def record(status="PARTIAL"):
    return dict(id="local-run", run_key=KEY, session_date="2026-09-28", phase="PREMARKET",
        ruleset_version="v0.3", experiment_class="INFRASTRUCTURE_TEST", status=status,
        created_at="2026-09-28T13:00:05Z", updated_at="2026-09-28T13:00:15Z",
        candidates_discovered=2, items_persisted=2, channel_status=CHANNELS.copy())


def evidence(run=None):
    return dict(run_key=KEY, run=run, mode="SHADOW", broker_execution_enabled=False,
        calendar_source="ALPACA_PAPER_MARKET_CALENDAR", checked_at=s.now().isoformat(),
        session=dict(date="2026-09-28", is_trading_day=True,
                     open="2026-09-28T09:30:00-04:00", close="2026-09-28T16:00:00-04:00"))


def response(data, status=200):
    return SimpleNamespace(status_code=status, json=lambda: deepcopy(data))


@pytest.fixture
def wired(monkeypatch):
    for key, value in dict(DISCOVERY_URL="https://discovery.invalid", DISCOVERY_SCHEDULER_TOKEN="private-token",
        SCAN_PHASE="PREMARKET", RUN_CLASS="INFRASTRUCTURE_TEST", RULESET_VERSION="v0.3",
        LOCAL_TIMEZONE="America/Los_Angeles", LOCAL_HOUR="6", LOCAL_MINUTE="0",
        SCAN_LOCAL_HOUR="6", SCAN_LOCAL_MINUTE="0", SCHEDULER_ACTION="RUN",
        MOVERS_TOP="20", NEWS_HOURS="18", WARMUP_MINUTES="0").items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(s, "now", lambda: NOW)
    monkeypatch.setattr(s.time, "sleep", lambda _: None)
    state = dict(run=None, posts=0, queries=[])
    def get(url, **kwargs):
        assert kwargs["allow_redirects"] is False
        if url.endswith("/health"):
            return response(dict(mode="SHADOW", broker_execution_enabled=False, ruleset_version="v0.3"))
        assert url.endswith("/runs/scheduled")
        state["queries"].append(kwargs["params"])
        return response(evidence(state["run"]))
    def post(url, **kwargs):
        assert url.endswith("/scan/run-once") and kwargs["allow_redirects"] is False
        state["posts"] += 1
        state["run"] = record()
        return response(dict(run_id="local-run"))
    monkeypatch.setattr(s.requests, "get", get)
    monkeypatch.setattr(s.requests, "post", post)
    return state


def output(capsys):
    return [json.loads(line) for line in capsys.readouterr().out.splitlines()]


def test_launch_readback_partial_is_visible(wired, capsys):
    assert s.main() == 1
    events = output(capsys)
    assert events[-1]["outcome"] == "COLLECTED_REVIEW_REQUIRED"
    assert events[-1]["run_id"] == "local-run"
    assert wired["posts"] == 1 and len(wired["queries"]) == 2
    assert wired["queries"][0]["run_class"] == "INFRASTRUCTURE_TEST"


@pytest.mark.parametrize("status,outcome,code", [
    ("IN_PROGRESS", "RUN_UNFINISHED", 1), ("PARTIAL", "COLLECTED_REVIEW_REQUIRED", 1),
    ("DATA_UNAVAILABLE", "COLLECTION_FAILED", 1), ("FAILED", "COLLECTION_FAILED", 1),
    ("UNKNOWN", "COLLECTION_FAILED", 1), ("COMPLETE", "COMPLETED", 0)])
def test_existing_run_never_reposts(wired, capsys, status, outcome, code):
    wired["run"] = record(status)
    assert s.main() == code
    assert output(capsys)[-1]["outcome"] == outcome
    assert wired["posts"] == 0


def test_watchdog_missing_is_read_only(wired, monkeypatch, capsys):
    monkeypatch.setenv("SCHEDULER_ACTION", "AUDIT")
    monkeypatch.setenv("LOCAL_MINUTE", "15")
    monkeypatch.setattr(s, "now", lambda: NOW.replace(minute=16))
    assert s.main() == 1
    assert output(capsys)[-1]["outcome"] == "MISSED_RUN"
    assert wired["posts"] == 0


@pytest.mark.parametrize("field,value,outcome", [
    ("run_key", "yesterday", "RUN_IDENTITY_MISMATCH"),
    ("experiment_class", "STRATEGY_1", "RUN_IDENTITY_MISMATCH"),
    ("phase", "POST_OPEN", "RUN_IDENTITY_MISMATCH"),
    ("items_persisted", 1, "PERSISTENCE_MISMATCH"),
    ("items_persisted", True, "PERSISTENCE_MISMATCH"),
    ("candidates_discovered", -1, "PERSISTENCE_MISMATCH"),
    ("created_at", "2026-09-28T12:59:50Z", "RUN_OUTSIDE_SCHEDULED_MINUTE"),
    ("created_at", "2026-09-27T13:00:05Z", "INVALID_RUN_TIMESTAMPS"),
    ("updated_at", "2026-09-28T13:00:04Z", "INVALID_RUN_TIMESTAMPS"),
    ("created_at", "2026-09-28T13:00:05", "READBACK_UNAVAILABLE_OR_INVALID")])
def test_corrupt_or_wrong_records_fail(wired, capsys, field, value, outcome):
    wired["run"] = record()
    wired["run"][field] = value
    assert s.main() == 1
    assert output(capsys)[-1]["outcome"] == outcome
    assert wired["posts"] == 0


def test_complete_does_not_hide_coverage_gaps(wired, capsys):
    wired["run"] = record("COMPLETE")
    wired["run"]["channel_status"]["cross_source_verification"] = "REVIEW_REQUIRED"
    assert s.main() == 1
    assert output(capsys)[-1]["outcome"] == "COVERAGE_STATUS_INCONSISTENT"


@pytest.mark.parametrize("committed,outcome", [(True, "COLLECTED_REVIEW_REQUIRED"), (False, "DISPATCH_OUTCOME_UNRESOLVED")])
def test_timeout_only_reconciles(wired, monkeypatch, capsys, committed, outcome):
    def post(*args, **kwargs):
        wired["posts"] += 1
        if committed:
            wired["run"] = record()
        raise requests.Timeout("private-token must not appear")
    monkeypatch.setattr(s.requests, "post", post)
    assert s.main() == 1 and wired["posts"] == 1
    events = output(capsys)
    assert events[-1]["outcome"] == outcome and "private-token" not in str(events)


def test_response_id_must_match_persisted_run(wired, monkeypatch, capsys):
    def post(*a, **kw):
        wired["run"] = record()
        return response(dict(run_id="wrong"))
    monkeypatch.setattr(s.requests, "post", post)
    assert s.main() == 1
    assert output(capsys)[-1]["outcome"] == "RESPONSE_ID_MISMATCH"


@pytest.mark.parametrize("mode,execution", [("LIVE", False), ("SHADOW", True), ("SHADOW", None)])
def test_unsafe_health_blocks(wired, monkeypatch, capsys, mode, execution):
    monkeypatch.setattr(s.requests, "get", lambda *a, **k: response(dict(
        mode=mode, broker_execution_enabled=execution, ruleset_version="v0.3")))
    assert s.main() == 1 and wired["posts"] == 0
    assert output(capsys)[-1]["outcome"] == "DEPENDENCY_UNAVAILABLE_OR_UNSAFE"


def test_cold_start_crosses_launch_minute(wired, monkeypatch, capsys):
    original = s.health
    def health(c):
        result = original(c)
        monkeypatch.setattr(s, "now", lambda: NOW.replace(minute=1))
        return result
    monkeypatch.setattr(s, "health", health)
    assert s.main() == 1 and wired["posts"] == 0
    assert output(capsys)[-1]["outcome"] == "MISSED_LAUNCH_WINDOW"


@pytest.mark.parametrize("stamp,outcome", [
    ("2026-09-28T13:01:00+00:00", "MISSED_LAUNCH_WINDOW"),
    ("2026-09-28T14:00:00+00:00", "OTHER_DST_INVOCATION"),
    ("2026-11-02T13:00:00+00:00", "OTHER_DST_INVOCATION"),
    ("2026-09-27T13:00:00+00:00", "WEEKEND")])
def test_timing_skip_or_failure(wired, monkeypatch, capsys, stamp, outcome):
    monkeypatch.setattr(s, "now", lambda: datetime.fromisoformat(stamp))
    s.main()
    assert output(capsys)[-1]["outcome"] == outcome
    assert wired["posts"] == 0 and not wired["queries"]


def test_winter_target_dispatches(wired, monkeypatch):
    monkeypatch.setattr(s, "now", lambda: datetime(2026, 11, 2, 14, 0, 20, tzinfo=UTC))
    # Verify winter invocation reaches health; fail it safely without using a summer fixture.
    calls = []
    monkeypatch.setattr(s, "health", lambda c: calls.append(True) or False)
    assert s.main() == 1 and calls == [True]


def test_closed_day_never_dispatches(wired, monkeypatch, capsys):
    monkeypatch.setattr(s, "readback", lambda *a: {**evidence(), "session": {
        "date": "2026-09-28", "is_trading_day": False}})
    assert s.main() == 0 and wired["posts"] == 0
    assert output(capsys)[-1]["outcome"] == "MARKET_CLOSED"


def test_stale_readback_cannot_certify(wired, monkeypatch, capsys):
    original = s.get
    def get(c, path, params=None):
        data = original(c, path, params)
        if path == "/runs/scheduled":
            data["checked_at"] = "2026-09-28T12:59:00Z"
        return data
    monkeypatch.setattr(s, "get", get)
    assert s.main() == 1 and wired["posts"] == 0
    assert output(capsys)[-1]["outcome"] == "READBACK_UNAVAILABLE_OR_INVALID"


@pytest.mark.parametrize("calendar", [None, {}, [{"date": "2026-09-27"}],
    [{"date": "2026-09-28", "open": "16:00", "close": "09:30"}]])
def test_bad_calendar_is_not_a_holiday(monkeypatch, calendar):
    monkeypatch.setattr(d, "alpaca_headers", lambda: {})
    monkeypatch.setattr(d.requests, "get", lambda *a, **k: response(calendar))
    with pytest.raises(d.HTTPException) as error:
        d.scheduled_market_session(date(2026, 9, 28))
    assert error.value.status_code == 503


@pytest.mark.parametrize("rows,trading", [([], False), (
    [dict(date="2026-11-27", open="09:30", close="13:00")], True)])
def test_calendar_holiday_and_early_close(monkeypatch, rows, trading):
    monkeypatch.setattr(d, "alpaca_headers", lambda: {})
    monkeypatch.setattr(d.requests, "get", lambda *a, **k: response(rows))
    result = d.scheduled_market_session(date(2026, 11, 27))
    assert result["is_trading_day"] is trading
    if trading:
        assert result["close"] == "2026-11-27T13:00:00-05:00"


def test_read_endpoint_auth_identity_and_no_mutation(monkeypatch):
    monkeypatch.setattr(d, "DISCOVERY_SERVICE_TOKEN", "test-service")
    monkeypatch.setattr(d, "DISCOVERY_SCHEDULER_TOKEN", "test-scheduler")
    monkeypatch.setattr(d, "scheduled_market_session", lambda day: evidence()["session"])
    seen = []
    def read(key):
        seen.append(key)
        return record()
    monkeypatch.setattr(d, "get_existing_run_by_key", read)
    monkeypatch.setattr(d, "sb_select", lambda table, params: [{"id": "one"}, {"id": "two"}])
    with TestClient(d.app) as client:
        url = "/runs/scheduled?session_date=2026-09-28&run_class=INFRASTRUCTURE_TEST"
        assert client.get(url).status_code == 401
        assert seen == []
        result = client.get(url, headers={"Authorization": "Bearer test-scheduler"})
        assert result.status_code == 200
        assert seen == [KEY] and result.json()["run"]["items_persisted"] == 2
        assert client.get(url + "&phase=INVALID", headers={"Authorization": "Bearer test-scheduler"}).status_code == 422


def test_early_warmup_waits_on_host_then_dispatches(wired, monkeypatch, capsys):
    monkeypatch.setenv("WARMUP_MINUTES", "5")
    clock = [NOW.replace(hour=12, minute=55)]
    monkeypatch.setattr(s, "now", lambda: clock[0])
    def sleep(seconds):
        assert wired["posts"] == 0
        clock[0] = NOW
    monkeypatch.setattr(s.time, "sleep", sleep)
    assert s.main() == 1 and wired["posts"] == 1
    assert output(capsys)[0]["outcome"] == "WARMED_WAITING_FOR_LAUNCH"


def test_warmup_oversleep_does_not_backfill(wired, monkeypatch, capsys):
    monkeypatch.setenv("WARMUP_MINUTES", "5")
    clock = [NOW.replace(hour=12, minute=55)]
    monkeypatch.setattr(s, "now", lambda: clock[0])
    monkeypatch.setattr(s.time, "sleep", lambda _: clock.__setitem__(0, NOW.replace(minute=2)))
    assert s.main() == 1 and wired["posts"] == 0
    assert output(capsys)[-1]["outcome"] == "MISSED_LAUNCH_WINDOW"


def test_completed_after_open_is_reported(wired, monkeypatch, capsys):
    monkeypatch.setenv("SCHEDULER_ACTION", "AUDIT")
    monkeypatch.setattr(s, "now", lambda: NOW.replace(minute=40))
    wired["run"] = record("COMPLETE")
    wired["run"]["updated_at"] = "2026-09-28T13:35:00Z"
    assert s.main() == 1
    assert output(capsys)[-1]["outcome"] == "PREMARKET_NOT_FINISHED_BEFORE_OPEN"


@pytest.mark.parametrize("key,value", [("DISCOVERY_URL", "https://user:secret@example.com"),
    ("DISCOVERY_URL", "http://example.com"), ("SCHEDULER_ACTION", "EXECUTE"),
    ("SCAN_PHASE", "POSTMARKET"), ("RUN_CLASS", "UNKNOWN"), ("WARMUP_MINUTES", "60"),
    ("DISCOVERY_SCHEDULER_TOKEN", ""), ("LOCAL_HOUR", "invalid")])
def test_bad_config_never_contacts_dependencies(wired, monkeypatch, capsys, key, value):
    monkeypatch.setenv(key, value)
    assert s.main() == 2
    assert output(capsys)[-1]["outcome"] == "CONFIGURATION_ERROR"
    assert wired["posts"] == 0 and not wired["queries"]


def test_calendar_http_failure_is_not_closed(monkeypatch):
    monkeypatch.setattr(d, "alpaca_headers", lambda: {})
    monkeypatch.setattr(d.requests, "get", lambda *a, **k: response([], 403))
    with pytest.raises(d.HTTPException) as error:
        d.scheduled_market_session(date(2026, 9, 28))
    assert error.value.status_code == 503


def test_audit_requires_explicit_expected_scan_time(wired, monkeypatch, capsys):
    monkeypatch.setenv("SCHEDULER_ACTION", "AUDIT")
    monkeypatch.delenv("SCAN_LOCAL_MINUTE")
    assert s.main() == 2 and wired["posts"] == 0
    assert output(capsys)[-1]["outcome"] == "CONFIGURATION_ERROR"
