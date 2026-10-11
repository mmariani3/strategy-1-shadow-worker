"""Synthetic offline collection cases, never Strategy #1 evidence."""
from datetime import date, datetime, timezone
import json
from types import SimpleNamespace

import pytest
import requests

import discovery_collection as c
import discovery_coordinator as d
from journal_projection import run_projection

END = datetime(2026, 10, 5, 13, tzinfo=timezone.utc)


def article(id, **kw):
    return dict(id=id, symbols=["LOCAL"], created_at="2026-08-06T12:00:00Z",
                updated_at="2026-10-05T12:00:00Z", **kw)


def page(news, token=None):
    return SimpleNamespace(status_code=200, json=lambda: {"news": news, "next_page_token": token})


def test_news_paginates_deduplicates_and_keeps_fixed_window():
    replies = iter([page([article(3), article(2)], "next"), page([article(2), article(1)])])
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        return next(replies)
    body = c.collect_news({}, 96, end=END, get=get)
    assert [a["id"] for a in body["news"]] == [3, 2, 1]
    assert body["collection"]["feed_exhausted"] is True
    assert body["collection"]["full_discovery_coverage"] is False
    assert calls[0][1]["params"]["start"] == "2026-10-01T13:00:00+00:00"
    assert calls[0][1]["params"]["end"] == calls[1][1]["params"]["end"]
    assert "page_token" not in calls[0][1]["params"]
    assert calls[1][1]["params"]["page_token"] == "next"
    assert all(url == c.NEWS_URL and not kw["allow_redirects"] for url, kw in calls)


def test_news_full_page_continues_until_explicit_terminal_page():
    replies = iter([page([article(i) for i in range(50)], "second"), page([article(50)])])
    body = c.collect_news({}, 18, end=END, get=lambda *a, **k: next(replies))
    assert len(body["news"]) == 51 and body["collection"]["pages_received"] == 2


@pytest.mark.parametrize("failure", ["timeout", "http", "malformed", "redirect"])
def test_later_page_failure_preserves_earlier_evidence_without_diagnostics(failure):
    calls = []
    marker = "SYNTHETIC_PRIVATE_TOKEN"
    def get(*a, **k):
        calls.append(k)
        if len(calls) == 1:
            return page([article(1)], marker)
        if failure == "timeout":
            raise requests.Timeout("api_key=" + marker)
        if failure == "malformed":
            return SimpleNamespace(status_code=200, json=lambda: {"news": [{"id": 2}]})
        return SimpleNamespace(status_code=302 if failure == "redirect" else 429, text=marker)
    body = c.collect_news({}, 96, end=END, get=get)
    assert len(body["news"]) == 1
    assert body["collection"]["outcome"] == "PROVIDER_UNAVAILABLE"
    assert not body["collection"]["feed_exhausted"]
    assert marker not in json.dumps(body)


def test_repeated_token_and_page_cap_cannot_be_complete(monkeypatch):
    body = c.collect_news({}, 96, end=END, get=lambda *a, **k: page([article(1)], "same"))
    assert body["collection"]["outcome"] == "REPEATED_PAGE_TOKEN"
    monkeypatch.setattr(c, "NEWS_MAX_PAGES", 2)
    tokens = iter(["one", "two"])
    body = c.collect_news({}, 96, end=END, get=lambda *a, **k: page([article(1)], next(tokens)))
    assert body["collection"]["outcome"] == "PAGE_LIMIT"
    assert body["collection"]["pages_received"] == 2


def test_news_deadline_preserves_collected_page():
    times = iter([0, 0, 46])
    body = c.collect_news({}, 96, end=END, get=lambda *a, **k: page([article(1)], "more"),
                          clock=lambda: next(times))
    assert len(body["news"]) == 1 and body["collection"]["outcome"] == "TIME_BUDGET"


def test_empty_exhausted_feed_does_not_prove_channel_completion():
    body = c.collect_news({}, 96, end=END, get=lambda *a, **k: page([]))
    assert body["collection"]["feed_exhausted"]
    assert not body["collection"]["full_discovery_coverage"]


def calendar(month="October 2026", manufacturing="1", services="5"):
    return ("<table><tr><th>Month</th><th>Manufacturing PMI</th><th>Services PMI</th></tr>"
            f"<tr><td>{month}</td><td>{manufacturing}</td><td>{services}</td></tr></table>")


def test_ism_explicit_october_date_is_retained_without_inferred_time_or_importance():
    events = c.parse_ism_calendar(calendar(), date(2026, 10, 5))
    assert len(events) == 1
    assert events[0]["release_name"] == "ISM Services PMI"
    assert events[0]["release_date"] == "2026-10-05"
    assert events[0]["release_time"] is events[0]["major_or_imminent"] is None
    assert c.parse_ism_calendar(calendar(), date(2026, 10, 6)) == []


@pytest.mark.parametrize("document", [
    calendar("October 2025"), calendar() + calendar(),
    calendar(services="TBD"), calendar(services="32"), "<html>Access denied</html>",
])
def test_ism_stale_ambiguous_or_changed_pages_fail_closed(document):
    with pytest.raises(ValueError):
        c.parse_ism_calendar(document, date(2026, 10, 5))


def test_ism_footnote_does_not_change_explicit_date():
    assert c.parse_ism_calendar(calendar(services="5<sup>**</sup>"), date(2026, 10, 5))


def test_ism_login_redirect_is_not_followed_or_treated_as_an_empty_calendar(monkeypatch):
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(status_code=302, content=b"redirect")
    monkeypatch.setattr(c.requests, "get", get)
    with pytest.raises(ValueError):
        c.collect_ism_calendar(date(2026, 10, 5))
    assert len(calls) == 1 and calls[0][1]["allow_redirects"] is False


def test_monday_default_and_explicit_lookback_are_distinct():
    assert d.ScanRequest(session_date="2026-10-05", run_class="INFRASTRUCTURE_TEST").news_hours == 96
    assert d.ScanRequest(session_date="2026-10-05", run_class="INFRASTRUCTURE_TEST", news_hours=18).news_hours == 18


def test_mover_and_news_do_not_fabricate_freshness_or_issuer_relationship():
    [(symbol, mover)] = d.normalize_mover_rows({"gainers": [{"symbol": "LOCAL", "price": 2}]})
    assert symbol == "LOCAL" and mover["price"] == 2 and not mover["premarket_usable"]
    by_symbol, _ = d.normalize_news({"news": [article(1, headline="Old earnings transcript")]})
    news = by_symbol["LOCAL"][0]
    assert news["published_at"].startswith("2026-08-06")
    assert news["updated_at"].startswith("2026-10-05")
    assert news["event_timestamp"] is None and not news["event_timestamp_verified"]
    assert news["symbol_specific"] is False
    assert "BELOW_GENERAL_$5_UNIVERSE_GUIDELINE" not in d.build_quality_flags(symbol, mover, [news], [])


def test_scan_retains_funnel_and_calendar_gap_without_promotion(monkeypatch):
    monkeypatch.setattr(d, "require_auth", lambda _: None)
    monkeypatch.setattr(d, "create_run_once", lambda *a: ({"id": "local-run"}, True))
    monkeypatch.setattr(d, "fetch_fred_release_calendar", lambda *a: [])
    monkeypatch.setattr(d, "collect_ism_calendar", lambda day: c.parse_ism_calendar(calendar(), day))
    monkeypatch.setattr(d, "collect_weekly_calendar", lambda day: [])
    monkeypatch.setattr(d, "fetch_movers", lambda *a: {"gainers": [{"symbol": "MOVER", "price": 2}]})
    monkeypatch.setattr(d, "fetch_news", lambda *a: {
        "news": [article(1)], "collection": {"feed_exhausted": False, "outcome": "PAGE_LIMIT"}})
    monkeypatch.setattr(d, "fetch_ticker_map", lambda: {})
    saved = []
    monkeypatch.setattr(d, "sb_insert", lambda table, row: saved.append(row))
    final = {}
    monkeypatch.setattr(d, "finalize_discovery_run", lambda key, row: final.update(row) or row)
    result = d.run_scan(d.ScanRequest(session_date="2026-10-05", run_class="INFRASTRUCTURE_TEST"), None)
    assert len(saved) == 2 and {r["symbol"] for r in saved} == {"MOVER", "LOCAL"}
    assert all(r["promotion_status"] == "REVIEW_REQUIRED" and r["provisional_tier"] is None for r in saved)
    assert result["status"] == "PARTIAL" and result["automatic_promotion"] is False
    assert final["macro_events"][0]["release_name"] == "ISM Services PMI"
    assert final["channel_status"]["macro_economic_calendar"].startswith("PARTIAL")
    assert final["channel_status"]["earnings_guidance"] == "NEWS_FEED_INCOMPLETE"
    assert "PAGE_LIMIT" in final["notes"]
    projected = run_projection({**final, "id": "local-run", "session_date": "2026-10-05",
        "phase": "PREMARKET", "created_at": END, "ruleset_version": "v0.3"})
    assert all(projected["values"][header] == "Unavailable" for header in [
        "Premarket Movers / Unusual Activity", "Macro / Economic Calendar", "Earnings / Guidance"])
