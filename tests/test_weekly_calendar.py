"""Offline calendar cases, not market observations."""
from datetime import date, datetime, timezone
import json
from types import SimpleNamespace

import pytest

import discovery_collection as c

CHECKED = datetime(2026, 10, 6, 15, tzinfo=timezone.utc)
DAY = date(2026, 10, 6)


def event(**changes):
    return dict(title="Synthetic event", country="USD",
                date="2026-10-06T08:30:00-04:00", impact="High", **changes)


def test_provider_labels_never_become_major_event_or_verified_time():
    data = c.parse_weekly_calendar([event()], DAY, checked_at=CHECKED)
    assert len(data) == 1
    assert data[0]["major_or_imminent"] is None
    assert data[0]["time_verification_status"] == "REVIEW_REQUIRED"
    assert data[0]["provider_impact_label"] == "High"
    assert data[0]["source_type"] == "secondary_economic_calendar"


@pytest.mark.parametrize("body", [
    [], {}, [None], [{"title": "Incomplete"}],
    [{**event(), "date": "2026-10-06T08:30:00"}],
    [{**event(), "date": "2026-09-29T08:30:00-04:00"}],
    [{**event(), "date": "2026-10-13T08:30:00-04:00"}],
    [event(), {**event(), "date": "not-a-date"}],
])
def test_invalid_stale_or_mixed_week_payload_rejected(body):
    with pytest.raises(ValueError):
        c.parse_weekly_calendar(body, DAY, checked_at=CHECKED)


def test_request_for_other_week_is_rejected_even_if_payload_matches():
    with pytest.raises(ValueError):
        c.parse_weekly_calendar([{**event(), "date": "2026-09-29T08:30:00-04:00"}],
                                date(2026, 9, 29), checked_at=CHECKED)


def test_near_midnight_uses_new_york_calendar_date_and_keeps_non_us_events():
    data = [{**event(), "country": "All", "date": "2026-10-07T01:00:00Z"}]
    parsed = c.parse_weekly_calendar(data, DAY, checked_at=CHECKED)
    assert parsed[0]["release_date"] == "2026-10-06"
    assert parsed[0]["provider_currency"] == "All"


def test_exact_duplicate_removed_but_conflicting_times_retained_and_flagged():
    first = event()
    second = {**first, "date": "2026-10-06T08:31:00-04:00"}
    parsed = c.parse_weekly_calendar([first, first, second], DAY, checked_at=CHECKED)
    assert len(parsed) == 2 and all(e["same_name_multiple_times"] for e in parsed)


def test_day_without_rows_does_not_add_no_event_claim():
    body = [{**event(), "date": "2026-10-05T10:00:00-04:00"}]
    assert c.parse_weekly_calendar(body, DAY, checked_at=CHECKED) == []


class Response:
    status_code = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def iter_content(self, _):
        yield json.dumps([event()]).encode()


def test_getter_is_fixed_public_bounded_read_without_credentials(monkeypatch):
    calls = []
    class FrozenDatetime:
        @staticmethod
        def now(tz):
            return CHECKED
    monkeypatch.setattr(c, "datetime", FrozenDatetime)
    # Preserve the real datetime parser on the lightweight clock stand-in.
    FrozenDatetime.fromisoformat = staticmethod(datetime.fromisoformat)
    monkeypatch.setattr(c.requests, "get", lambda url, **kwargs: calls.append((url, kwargs)) or Response())
    parsed = c.collect_weekly_calendar(DAY)
    assert len(parsed) == 1
    assert calls == [(c.FOREX_FACTORY_URL, {"timeout": (3, 10), "allow_redirects": False, "stream": True})]


@pytest.mark.parametrize("failure", ["redirect", "oversized"])
def test_getter_rejects_redirect_and_oversized_response(monkeypatch, failure):
    response = Response()
    if failure == "redirect":
        response.status_code = 302
    else:
        response.iter_content = lambda _: iter([b"x" * 1_000_001])
    monkeypatch.setattr(c.requests, "get", lambda *a, **k: response)
    with pytest.raises(ValueError):
        c.collect_weekly_calendar(DAY)
