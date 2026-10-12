from datetime import date, datetime
import json

import pytest

import prior_session_evidence as module
from prior_session_evidence import collect_prior_session_evidence


def bar(at="2026-10-09T04:00:00Z", **changes):
    return dict(t=at, o=10, h=12, l=9, c=11, v=1234, **changes)


class Response:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


def run(pages, *, calendar=None, symbols=None, now="2026-10-12T13:00:00+00:00", clock=None):
    calls = []
    pages = iter(pages)

    def get(url, **kwargs):
        calls.append((url, kwargs))
        assert kwargs["allow_redirects"] is False
        if url == module.CALENDAR_URL:
            return Response(calendar if calendar is not None else [{"date": "2026-10-09"}, {"date": "2026-10-12"}])
        assert url == module.BARS_URL
        payload = next(pages)
        if isinstance(payload, Exception):
            raise payload
        return Response(payload)

    now = datetime.fromisoformat(now)
    result = collect_prior_session_evidence({}, symbols or ["TEST"], now.date(), now=now, get=get, clock=clock)
    return result, calls


def test_monday_requests_friday_explicit_sip_raw_not_relative_snapshot():
    result, calls = run([{"bars": {"TEST": [bar()]}}])
    params = calls[1][1]["params"]
    assert params == dict(symbols="TEST", timeframe="1Day", feed="sip", adjustment="raw",
                          asof="2026-10-12", sort="asc", start="2026-10-09T00:00:00-04:00",
                          end="2026-10-09T23:59:59.999999-04:00", limit=10000)
    assert result["items"]["TEST"]["close"] == 11
    assert result["items"]["TEST"]["status"] == "RAW_DAILY_CLOSE_REVIEW_REQUIRED"
    assert result["strategy_eligible"] is False


def test_holiday_and_dst_use_calendar_and_new_york_midnight():
    result, calls = run([{"bars": {"TEST": [bar("2026-11-25T05:00:00Z")]}}],
        calendar=[{"date": "2026-11-25"}, {"date": "2026-11-27"}], now="2026-11-27T14:00:00+00:00")
    assert result["prior_session"] == "2026-11-25"
    assert calls[1][1]["params"]["start"].endswith("-05:00")
    assert result["items"]["TEST"]["close"] == 11


def test_pagination_exhaustion_and_identical_overlap():
    result, calls = run([{"bars": {"TEST": [bar()]}, "next_page_token": "page2"},
                        {"bars": {"TEST": [bar()]}}])
    assert calls[2][1]["params"]["page_token"] == "page2"
    assert result["completed_symbols"] == ["TEST"]


@pytest.mark.parametrize("at", ["2026-10-08T04:00:00Z", "2026-10-12T04:00:00Z",
                                  "2026-10-09T14:00:00Z", "2026-10-09T00:00:00"])
def test_wrong_or_naive_daily_timestamp_rejected(at):
    result, _ = run([{"bars": {"TEST": [bar(at)]}}])
    assert result["outcome"] == "PARTIAL"
    assert "close" not in result["items"]["TEST"]


@pytest.mark.parametrize("field,value", [("c", float("nan")), ("c", -1), ("c", True),
                                          ("h", 5), ("l", 20), ("v", 1.2), ("v", True)])
def test_bad_numeric_bars_fail_closed(field, value):
    item = bar()
    item[field] = value
    result, _ = run([{"bars": {"TEST": [item]}}])
    assert result["items"]["TEST"]["status"] == "UNAVAILABLE"


@pytest.mark.parametrize("tail", [RuntimeError("SENSITIVE_DIAGNOSTIC"),
    {"bars": {"TEST": [{**bar(), "c": 10}]}, "next_page_token": None},
    {"bars": {}, "next_page_token": "page2"}, {"bars": {"OTHER": [bar()]}},
    {"bars": {}, "next_page_token": 7}])
def test_incomplete_or_conflicting_batch_never_publishes_first_page(tail):
    result, _ = run([{"bars": {"TEST": [bar()]}, "next_page_token": "page2"}, tail])
    assert result["items"]["TEST"]["status"] == "UNAVAILABLE"
    assert result["completed_symbols"] == []
    assert "SENSITIVE_DIAGNOSTIC" not in json.dumps(result)


def test_missing_symbol_retained_as_unavailable_even_when_collection_complete():
    result, _ = run([{"bars": {"TEST": [bar()]}}], symbols=["TEST", "ABSENT"])
    assert result["outcome"] == "COLLECTION_COMPLETE_REVIEW_REQUIRED"
    assert result["items"]["ABSENT"]["reason"] == "NO_BAR_FOR_PRIOR_SESSION"


@pytest.mark.parametrize("calendar", [[], [{"date": "2026-10-09"}],
    [{"date": "2026-10-12"}], [{"date": "2026-10-09"}, {"date": "2026-10-12"}, {"date": "2026-10-13"}],
    [{"date": "2026-10-09"}, {"date": "2026-10-09"}, {"date": "2026-10-12"}]])
def test_missing_inconsistent_calendar_no_bars_request(calendar):
    result, calls = run([], calendar=calendar)
    assert result["outcome"] == "CALENDAR_UNAVAILABLE"
    assert len(calls) == 1


def test_page_cap_discards_pending_batch(monkeypatch):
    monkeypatch.setattr(module, "MAX_PAGES", 1)
    result, calls = run([{"bars": {"TEST": [bar()]}, "next_page_token": "more"}])
    assert result["items"]["TEST"]["status"] == "UNAVAILABLE"
    assert len(calls) == 2


def test_budget_stops_new_requests():
    ticks = iter([0, 0, 121])
    result, calls = run([], clock=lambda: next(ticks))
    assert result["outcome"] == "PARTIAL"
    assert len(calls) == 1


def test_batch_failure_preserves_earlier_completed_batch(monkeypatch):
    monkeypatch.setattr(module, "BATCH_SIZE", 1)
    result, _ = run([{"bars": {"TEST": [bar()]}}, RuntimeError()], symbols=["TEST", "OTHER"])
    assert result["items"]["TEST"]["close"] == 11
    assert result["unprocessed_symbols"] == ["OTHER"]


@pytest.mark.parametrize("symbols", [["BAD,INJECTION"], ["TEST", "TEST"], [None]])
def test_invalid_request_never_calls_provider(symbols):
    result, calls = run([], symbols=symbols)
    assert result["outcome"] == "INVALID_REQUEST"
    assert calls == []
