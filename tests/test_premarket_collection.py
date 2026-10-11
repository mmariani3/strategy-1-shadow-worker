"""Invented offline fixtures only; these are not Strategy #1 observations."""
from datetime import date, datetime, timezone
import json
from types import SimpleNamespace

import pytest

import premarket_collection as p
import discovery_coordinator as d
from journal_projection import run_projection

NOW = datetime(2026, 10, 7, 13, 0, 30, tzinfo=timezone.utc)
DAY = NOW.date()
CALENDAR = [{"date": "2026-10-06", "open": "09:30"}, {"date": "2026-10-07", "open": "09:30"}]


def asset(symbol, exchange="NASDAQ"):
    return {"symbol": symbol, "class": "us_equity", "status": "active", "exchange": exchange}


def bar(t="2026-10-07T12:59:00Z", **changes):
    return {"t": t, "o": 10, "h": 12, "l": 9, "c": 11, "v": 100, **changes}


def snapshot(**changes):
    return {"latestQuote": {"t": "2026-10-07T13:00:20Z", "bp": 10, "ap": 10.1},
            "prevDailyBar": {"t": "2026-10-06T04:00:00Z", "c": 10}, **changes}


def provider(pages, assets=None, snapshots=None, calendar=None):
    pages, calls = iter(pages), []
    def get(url, **kw):
        calls.append((url, kw))
        if url == p.CALENDAR_URL:
            body = calendar if calendar is not None else CALENDAR
        elif url == p.ASSETS_URL:
            body = assets if assets is not None else [asset("AAA"), asset("BBB"), asset("OTCX", "OTC")]
        elif url == p.BARS_URL:
            body = next(pages)
        elif url == p.SNAPSHOTS_URL:
            body = snapshots if snapshots is not None else {"AAA": snapshot()}
        else:
            raise AssertionError("Unexpected URL")
        if isinstance(body, Exception):
            raise body
        return SimpleNamespace(status_code=200, json=lambda: body)
    return get, calls


def collect(pages, **kwargs):
    get, calls = provider(pages, **kwargs)
    return p.collect_premarket({}, DAY, now=NOW, get=get, clock=lambda: 0), calls


def test_broad_universe_pagination_fixed_window_and_safe_projection():
    result, calls = collect([
        {"bars": {"AAA": [bar("2026-10-07T08:00:00Z")]}, "next_page_token": "PRIVATE_TOKEN"},
        {"bars": {"AAA": [bar()], "BBB": []}, "next_page_token": None}])
    a, m = result["items"]["AAA"], result["collection"]
    assert a["premarket_volume"] == 200 and a["observed_volume"] == 200
    assert a["last_bar_close"] == 11 and a["gap_percent_unadjusted"] == pytest.approx(10)
    assert a["spread"] == pytest.approx(.1)
    assert a["quote_age_seconds"] == 10 and a["last_bar_age_seconds"] == 90
    assert a["instrument_eligibility"] == "REVIEW_REQUIRED" and not a["premarket_usable"]
    assert all(a[k] is None for k in ("rvol", "average_daily_volume", "liquidity_ok", "unusual_volume"))
    assert m["universe_symbols"] == m["completed_symbols"] == ["AAA", "BBB"]
    assert m["no_bars_symbols"] == ["BBB"] and m["excluded_otc_symbols"] == ["OTCX"]
    assert not m["unprocessed_symbols"] and not m["full_discovery_coverage"]
    assert "PRIVATE_TOKEN" not in json.dumps(result)
    bar_calls = [kw for url, kw in calls if url == p.BARS_URL]
    assert all(kw["params"]["feed"] == "sip" for url, kw in calls if url in (p.BARS_URL, p.SNAPSHOTS_URL))
    assert bar_calls[0]["params"]["end"] == bar_calls[1]["params"]["end"] == "2026-10-07T08:59:59.999999-04:00"
    assert bar_calls[0]["params"]["symbols"] == "AAA,BBB"
    assert all(kw["allow_redirects"] is False for _, kw in calls)


@pytest.mark.parametrize("now,phase", [
    (datetime(2026,10,7,8,0,tzinfo=timezone.utc), "PREMARKET"),
    (datetime(2026,10,7,13,30,tzinfo=timezone.utc), "PREMARKET"),
    (datetime(2026,10,8,13,0,tzinfo=timezone.utc), "PREMARKET"),
    (NOW, "POST_OPEN"), (datetime(2026,10,7,9,0), "PREMARKET")])
def test_outside_window_does_not_request_network(now, phase):
    def fail(*a, **k):
        pytest.fail("No request allowed")
    result = p.collect_premarket({}, DAY, now=now, phase=phase, get=fail)
    assert result["collection"]["outcome"] in ("OUTSIDE_CURRENT_PREMARKET", "INVALID_CHECK_TIME")
    assert not result["items"]


def test_holiday_does_not_enumerate_assets():
    result, calls = collect([], calendar=CALENDAR[:1])
    assert result["collection"]["outcome"] == "NOT_A_TRADING_SESSION"
    assert [url for url, _ in calls] == [p.CALENDAR_URL]


def test_winter_window_uses_eastern_standard_time():
    now = datetime(2026,12,7,14,0,tzinfo=timezone.utc)
    get, calls = provider([{"bars": {}}], calendar=[
        {"date": "2026-12-04", "open": "09:30"}, {"date": "2026-12-07", "open": "09:30"}])
    result = p.collect_premarket({}, now.date(), now=now, get=get, clock=lambda: 0)
    assert result["collection"]["requested_start"] == "2026-12-07T04:00:00-05:00"
    assert result["collection"]["previous_session_date"] == "2026-12-04"


@pytest.mark.parametrize("last,expected", [
    (RuntimeError("OFFLINE_PRIVATE_MARKER"), "BAR_PROVIDER_UNAVAILABLE"),
    ({"bars": {}, "next_page_token": "same"}, "REPEATED_PAGE_TOKEN"),
    ({"bars": {"WRONG": [bar()]}}, "BAR_PROVIDER_UNAVAILABLE")])
def test_incomplete_feed_keeps_partial_evidence_without_false_volume(last, expected):
    result, _ = collect([{"bars": {"AAA": [bar()]}, "next_page_token": "same"}, last])
    a, m = result["items"]["AAA"], result["collection"]
    assert a["observed_volume"] == 100 and a["premarket_volume"] is None
    assert m["outcome"] == expected and not m["completed_symbols"]
    assert m["unprocessed_symbols"] == ["AAA", "BBB"]
    assert "OFFLINE_PRIVATE_MARKER" not in json.dumps(result)


def test_page_cap_preserves_unprocessed_symbols(monkeypatch):
    monkeypatch.setattr(p, "MAX_PAGES", 1)
    result, _ = collect([{"bars": {"AAA": [bar()]}, "next_page_token": "more"}])
    assert result["collection"]["outcome"] == "PAGE_LIMIT"
    assert result["items"]["AAA"]["premarket_volume"] is None


def test_budget_stops_new_requests_and_preserves_completed_batch(monkeypatch):
    monkeypatch.setattr(p, "BATCH_SIZE", 1)
    ticks = [0]
    get, calls = provider([{"bars": {"AAA": [bar()]}}])
    def wrapped(url, **kw):
        response = get(url, **kw)
        if url == p.BARS_URL:
            ticks[0] = 121
        return response
    result = p.collect_premarket({}, DAY, now=NOW, get=wrapped, clock=lambda: ticks[0])
    assert result["collection"]["outcome"] == "TIME_BUDGET"
    assert result["collection"]["completed_symbols"] == ["AAA"]
    assert result["collection"]["unprocessed_symbols"] == ["BBB"]
    assert result["items"]["AAA"]["premarket_volume"] == 100
    assert len(calls) == 3


@pytest.mark.parametrize("bad", [bar("2026-10-07T13:00:00Z"), bar("2026-10-06T12:00:00Z"),
    bar("2026-10-07T07:59:00Z"), bar(v=-1), bar(c=float("nan")), bar(c=True), bar(l=15)])
def test_invalid_page_never_becomes_evidence(bad):
    result, _ = collect([{"bars": {"AAA": [bar(), bad]}}])
    assert not result["items"]
    assert result["collection"]["outcome"] == "BAR_PROVIDER_UNAVAILABLE"


def test_duplicate_bars_are_not_double_counted_and_conflicts_fail_closed():
    result, _ = collect([{"bars": {"AAA": [bar()]}, "next_page_token": "next"},
                         {"bars": {"AAA": [bar()]}}])
    assert result["items"]["AAA"]["premarket_volume"] == 100
    bad, _ = collect([{"bars": {"AAA": [bar()]}, "next_page_token": "next"},
                      {"bars": {"AAA": [bar(v=200)]}}])
    assert bad["items"]["AAA"]["premarket_volume"] is None


@pytest.mark.parametrize("snap", [
    snapshot(latestQuote={"t": "2026-10-06T13:00:00Z", "bp": 10, "ap": 11}),
    snapshot(latestQuote={"t": "2026-10-07T13:31:00Z", "bp": 10, "ap": 11}),
    snapshot(latestQuote={"t": "2026-10-07T13:00:20Z", "bp": 11, "ap": 10}),
    snapshot(latestQuote={"t": "2026-10-07T13:00:20Z", "bp": 0, "ap": 10})])
def test_invalid_quotes_do_not_assert_spread_or_liquidity(snap):
    result, _ = collect([{"bars": {"AAA": [bar()]}}], snapshots={"AAA": snap})
    a = result["items"]["AAA"]
    assert a["quote_status"] == "UNAVAILABLE" and "spread" not in a
    assert a["liquidity_ok"] is None


def test_wrong_previous_session_cannot_compute_gap():
    result, _ = collect([{"bars": {"AAA": [bar()]}}], snapshots={"AAA": snapshot(
        prevDailyBar={"t": "2026-10-05T04:00:00Z", "c": 10})})
    assert result["items"]["AAA"]["gap_percent_unadjusted"] is None


@pytest.mark.parametrize("assets", [[asset("AAA"), asset("AAA")], [asset("SECRET?token")],
    [dict(asset("AAA"), status="inactive")], []])
def test_invalid_universe_is_not_silently_truncated(assets):
    result, calls = collect([], assets=assets)
    assert result["collection"]["outcome"] == "UNIVERSE_OR_CALENDAR_UNAVAILABLE"
    assert len(calls) == 2


def test_auth_failure_and_redirect_have_no_fallback_or_raw_diagnostics():
    for status in (301,401,403,429):
        calls = []
        def get(url, **kw):
            calls.append(url)
            return SimpleNamespace(status_code=status, text="OFFLINE_PRIVATE_MARKER")
        result = p.collect_premarket({}, DAY, now=NOW, get=get)
        assert calls == [p.CALENDAR_URL]
        assert not result["items"] and "OFFLINE_PRIVATE_MARKER" not in json.dumps(result)


def test_scan_keeps_new_activity_leads_review_required_and_coverage_partial(monkeypatch):
    evidence, _ = collect([{"bars": {"AAA": [bar()], "BBB": [bar()]}}],
                          assets=[asset("AAA"), asset("BBB"), asset("CCC")])
    monkeypatch.setattr(d, "require_auth", lambda _: None)
    monkeypatch.setattr(d, "alpaca_headers", lambda: {})
    monkeypatch.setattr(d, "create_run_once", lambda *a: ({"id": "offline-run"}, True))
    for name in ("fetch_fred_release_calendar", "collect_ism_calendar", "collect_weekly_calendar"):
        monkeypatch.setattr(d, name, lambda *a: [])
    monkeypatch.setattr(d, "fetch_movers", lambda *a: {"gainers": [{"symbol": "AAA", "price": 9}]})
    monkeypatch.setattr(d, "fetch_news", lambda *a: {"news": []})
    monkeypatch.setattr(d, "fetch_ticker_map", lambda: {})
    monkeypatch.setattr(d, "collect_premarket", lambda *a, **kw: evidence)
    saved, final = [], {}
    monkeypatch.setattr(d, "sb_insert", lambda table, row: saved.append(row))
    monkeypatch.setattr(d, "finalize_discovery_run", lambda key, row: final.update(row) or row)
    result = d.run_scan(d.ScanRequest(session_date=DAY, run_class="INFRASTRUCTURE_TEST"), None)
    assert len(saved) == 2 and {row["symbol"] for row in saved} == {"AAA", "BBB"}
    assert saved[1]["discovered_via"] == ["alpaca_sip_premarket_bars"]
    assert saved[1]["promotion_status"] == "REVIEW_REQUIRED"
    row = saved[0]
    assert row["mover_snapshot"]["price"] == 9
    assert row["mover_snapshot"]["premarket_activity"]["last_bar_close"] == 11
    assert row["provisional_tier"] is None and row["promotion_status"] == "REVIEW_REQUIRED"
    assert "alpaca_sip_premarket_bars" in row["discovered_via"]
    assert result["status"] == "PARTIAL" and result["automatic_promotion"] is False
    assert "no_bars_symbols" in final["notes"] and '"CCC"' in final["notes"]
    projected = run_projection({**final, "id": "offline-run", "session_date": DAY.isoformat(),
        "phase": "PREMARKET", "created_at": NOW, "ruleset_version": "v0.3"})
    assert projected["values"]["Premarket Movers / Unusual Activity"] == "Unavailable"


def test_sip_permission_error_preserves_manifest_and_never_falls_back():
    get, calls = provider([])
    def wrapped(url, **kw):
        if url == p.BARS_URL:
            calls.append((url, kw))
            return SimpleNamespace(status_code=403, text="OFFLINE_PRIVATE_MARKER")
        return get(url, **kw)
    result = p.collect_premarket({}, DAY, now=NOW, get=wrapped)
    assert result["collection"]["outcome"] == "BAR_PROVIDER_UNAVAILABLE"
    assert result["collection"]["unprocessed_symbols"] == ["AAA", "BBB"]
    assert len(calls) == 3 and calls[-1][1]["params"]["feed"] == "sip"
    assert "OFFLINE_PRIVATE_MARKER" not in json.dumps(result)


def test_quote_arriving_after_start_is_measured_at_snapshot_read_time():
    ticks = [0]
    get, calls = provider([{"bars": {"AAA": [bar()]}}], snapshots={"AAA": snapshot(
        latestQuote={"t": "2026-10-07T13:00:35Z", "bp": 10, "ap": 11})})
    def wrapped(url, **kw):
        response = get(url, **kw)
        if url == p.SNAPSHOTS_URL:
            ticks[0] = 10
        return response
    result = p.collect_premarket({}, DAY, now=NOW, get=wrapped, clock=lambda: ticks[0])
    assert result["items"]["AAA"]["quote_age_seconds"] == 5
    assert result["items"]["AAA"]["snapshot_checked_at"] == "2026-10-07T13:00:40+00:00"


def test_completed_first_batch_and_incomplete_second_are_distinct(monkeypatch):
    monkeypatch.setattr(p, "BATCH_SIZE", 1)
    result, _ = collect([{"bars": {"AAA": [bar()]}}, RuntimeError("private")])
    assert result["collection"]["completed_symbols"] == ["AAA"]
    assert result["collection"]["unprocessed_symbols"] == ["BBB"]
    assert result["items"]["AAA"]["premarket_volume"] == 100


def test_operational_asset_cap_fails_closed_before_bar_requests(monkeypatch):
    monkeypatch.setattr(p, "MAX_ASSETS", 1)
    result, calls = collect([])
    assert result["collection"]["outcome"] == "UNIVERSE_OR_CALENDAR_UNAVAILABLE"
    assert len(calls) == 2 and not result["items"]


def test_large_audit_manifest_remains_in_source_with_bounded_journal_excerpt():
    notes = "Collection evidence " + json.dumps({"universe_symbols": [f"SYMBOL{i}" for i in range(20000)]})
    run = {"id": "offline-run", "session_date": DAY.isoformat(), "phase": "PREMARKET",
           "created_at": NOW, "ruleset_version": "v0.3", "status": "PARTIAL", "notes": notes}
    projected = run_projection(run)
    assert len(projected["values"]["Notes"]) < 41000
    assert "EXCERPT ONLY" in projected["values"]["Notes"]
    assert "discovery run offline-run" in projected["values"]["Notes"]
    assert run["notes"] == notes


def test_october9_sized_universe_can_fit_page_cap_without_narrowing():
    # Invented symbols, not a reconstruction or replay of actual market evidence.
    universe = [asset(f"X{i:05}") for i in range(13241)]
    result, calls = collect([{"bars": {}} for _ in range(67)], assets=universe)
    meta = result["collection"]
    assert meta["outcome"] == "FEED_EXHAUSTED"
    assert len(meta["completed_symbols"]) == 13241 and not meta["unprocessed_symbols"]
    assert meta["bars_pages_received"] == 67
    assert p.MAX_PAGES == 120 and p.BUDGET_SECONDS == 120
    assert max(len(kw["params"]["symbols"].split(",")) for url, kw in calls if url == p.BARS_URL) == 200


def test_snapshot_diagnostics_preserve_dates_without_inventing_prior_close():
    result, _ = collect([{"bars": {"AAA": [bar()]}}], snapshots={"AAA": snapshot(
        dailyBar={"t": "2026-10-06T04:00:00Z", "c": 10},
        prevDailyBar={"t": "2026-10-05T04:00:00Z", "c": 9})})
    row = result["items"]["AAA"]
    assert row["dailyBar_session_date"] == "2026-10-06"
    assert row["prevDailyBar_session_date"] == "2026-10-05"
    assert row["previous_close_unavailable_reason"] == "WRONG_PREVIOUS_SESSION"
    assert row["gap_percent_unadjusted"] is None and "previous_close" not in row


def test_snapshot_diagnostics_do_not_keep_private_malformed_fields():
    row = p.snapshot_fields({"dailyBar": {"t": "PRIVATE_ERROR"}, "prevDailyBar": None},
                            NOW, NOW, date(2026, 10, 6))
    assert "PRIVATE_ERROR" not in json.dumps(row)
    assert row["previous_close_unavailable_reason"] == "MISSING_OR_INVALID_PREVIOUS_DAILY_BAR"
