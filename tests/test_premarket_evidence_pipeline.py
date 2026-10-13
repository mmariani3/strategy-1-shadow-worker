"""Invented offline fixtures only: never market/Strategy #1 observations."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

from fastapi import HTTPException
import pytest

import discovery_coordinator as coordinator
import premarket_collection as activity
import prior_session_evidence as prior
import premarket_evidence_collection as combined
import premarket_evidence_storage as storage

NOW = datetime(2026, 10, 13, 13, tzinfo=timezone.utc)
DAY = NOW.date()
CONTEXT = {"owner": "offline_acceptance", "implementation_version": "offline-v1",
           "reason": storage.LABEL, "strategy_evidence_eligible": False}


def provider(count=3, active=1, missing=(), daily_failure=None, mismatch=False):
    symbols = [f"S{i:05}" for i in range(count)]
    calls, tick = [], [0]
    calendars, daily_batches = [0], [0]

    def get(url, **kwargs):
        params = kwargs["params"]
        calls.append((url, deepcopy(params)))
        assert kwargs["allow_redirects"] is False
        if url == activity.CALENDAR_URL:
            calendars[0] += 1
            yesterday = "2026-10-09" if mismatch and calendars[0] > 1 else "2026-10-12"
            body = [{"date": yesterday, "open": "09:30"}, {"date": "2026-10-13", "open": "09:30"}]
        elif url == activity.ASSETS_URL:
            body = [{"symbol": s, "exchange": "NASDAQ", "class": "us_equity", "status": "active"}
                    for s in symbols] + [{"symbol": "OTCX", "exchange": "OTC", "class": "us_equity", "status": "active"}]
        elif url == activity.BARS_URL:
            requested = params["symbols"].split(",")
            assert params["feed"] == "sip" and params["adjustment"] == "raw"
            if params["timeframe"] == "1Day":
                daily_batches[0] += 1
                if daily_failure:
                    daily_failure(daily_batches[0], tick)
                when = "2026-10-09T04:00:00Z" if mismatch else "2026-10-12T04:00:00Z"
                include = [s for s in requested if s not in missing]
            else:
                when = "2026-10-13T12:59:00Z"
                include = [s for s in requested if s in set(symbols[:active])]
            body = {"bars": {s: [dict(t=when, o=10, h=12, l=9, c=11, v=100)] for s in include}}
        elif url == activity.SNAPSHOTS_URL:
            body = {s: {"prevDailyBar": {"t": "2026-10-09T04:00:00Z", "c": 8},
                        "dailyBar": {"t": "2026-10-12T04:00:00Z", "c": 11},
                        "latestQuote": {"t": "2026-10-13T12:59:59Z", "bp": 10, "ap": 11}}
                    for s in params["symbols"].split(",")}
        else:
            raise AssertionError("Unexpected endpoint")
        return SimpleNamespace(status_code=200, json=lambda: body)
    return get, calls, tick


def collect(**kwargs):
    get, calls, tick = provider(**kwargs)
    result = combined.collect_premarket_with_prior({}, DAY, now=NOW, get=get, clock=lambda: tick[0])
    return result, calls


def memory_store():
    saved, calls = [], []
    def write(method, table, *, body, context):
        assert method == "POST" and table == "strategy_discovery_items"
        assert context == CONTEXT
        calls.append(deepcopy(body))
        saved.extend(deepcopy(body))
        return deepcopy(body)
    def read(method, table, *, params):
        assert method == "GET" and table == "strategy_discovery_items"
        assert params["run_id"] == "eq.offline-run" and params["order"] == "symbol.asc,id.asc"
        ordered = sorted(saved, key=lambda r: r["symbol"])
        start, limit = int(params["offset"]), int(params["limit"])
        return deepcopy(ordered[start:start+limit])
    return write, read, saved, calls


def persist(collection, **overrides):
    write, read, saved, calls = memory_store()
    args = dict(write=write, read=read, context=CONTEXT, time_available=lambda: True, clock=lambda: 0)
    args.update(overrides)
    return storage.persist_universe("offline-run", collection, **args), saved, calls


def test_dated_close_preserves_old_snapshot_fields_and_distinguishes_no_activity():
    result, calls = collect()
    item = result["items"]["S00000"]
    assert item["previous_close_status"] == "UNAVAILABLE" and item["gap_percent_unadjusted"] is None
    assert item["previous_close_unavailable_reason"] == "WRONG_PREVIOUS_SESSION"
    assert item["dailyBar_session_date"] == "2026-10-12"
    assert item["prevDailyBar_session_date"] == "2026-10-09"
    assert item["quote_status"] == "SESSION_QUOTE_REVIEW_REQUIRED"
    dated = item["dated_prior_session_evidence"]
    assert dated["prior_session"] == "2026-10-12" and dated["item"]["close"] == 11
    assert result["integration"]["collection_complete"] is True
    assert len(result["items"]) == 1 and len(result["universe_items"]) == 3
    for symbol in ("S00001", "S00002"):
        assert result["universe_items"][symbol]["premarket_status"] == "NO_BARS"
        assert result["universe_items"][symbol]["premarket_activity"] is None
    assert result["collection"]["excluded_otc_symbols"] == ["OTCX"]
    assert not result["full_discovery_accepted"] and not result["strategy_eligible"]


def test_missing_prior_bar_is_retained_without_invalidating_successful_storage():
    result, _ = collect(missing=("S00001",))
    assert result["integration"]["collection_complete"] is True
    assert result["integration"]["all_prior_closes_available"] is False
    assert result["integration"]["prior_unavailable_reasons"] == {"NO_BAR_FOR_PRIOR_SESSION": 1}
    outcome, rows, calls = persist(result)
    assert outcome["storage_verified"] is outcome["collection_storage_accepted"] is True
    assert outcome["all_prior_closes_available"] is False and outcome["status"] == "PARTIAL"
    assert len(rows) == 3 and len(calls) == 1
    assert rows[1]["mover_snapshot"]["universe_coverage"]["dated_prior_session_evidence"]["item"]["reason"] == "NO_BAR_FOR_PRIOR_SESSION"


def test_large_full_universe_collection_and_storage_do_not_narrow_to_activity():
    result, calls = collect(count=13240, active=4286, missing=("S10000", "S12000"))
    daily = [p for url, p in calls if url == activity.BARS_URL and p["timeframe"] == "1Day"]
    assert len(daily) == 67 and sum(len(p["symbols"].split(",")) for p in daily) == 13240
    assert result["integration"]["coverage_only_count"] == 8954
    assert result["integration"]["dated_prior_close_count"] == 13238
    outcome, rows, batches = persist(result)
    assert outcome["storage_verified"] is True and outcome["expected_count"] == 13240
    assert len(rows) == 13240 and len(batches) == 133 and max(map(len, batches)) == 100
    assert all(row["promotion_status"] == "REVIEW_REQUIRED" for row in rows)


def test_calendar_disagreement_quarantines_close_but_preserves_activity():
    result, _ = collect(mismatch=True)
    assert result["integration"]["calendar_sessions_agree"] is False
    assert result["integration"]["collection_complete"] is False
    assert result["items"]["S00000"]["last_bar_close"] == 11
    assert result["prior_evidence"]["previous_close"]["rejected_calendar_prior_session"] == "2026-10-09"
    assert all("close" not in row["dated_prior_session_evidence"]["item"] for row in result["universe_items"].values())
    outcome, _, _ = persist(result)
    assert outcome["storage_verified"] is True and outcome["collection_storage_accepted"] is False


def test_later_daily_failure_preserves_completed_batch_and_all_unprocessed_symbols():
    def fail(batch, tick):
        if batch == 2: raise RuntimeError("PRIVATE_PROVIDER_TEXT")
    result, _ = collect(count=450, daily_failure=fail)
    assert result["integration"]["dated_prior_close_count"] == 200
    assert result["integration"]["prior_unavailable_reasons"] == {
        "BATCH_INCOMPLETE_OR_INVALID": 200, "NOT_COLLECTED": 50}
    assert len(result["prior_evidence"]["previous_close"]["unprocessed_symbols"]) == 250
    assert "PRIVATE_PROVIDER_TEXT" not in json.dumps(result)


def test_shared_budget_rejects_late_daily_response_and_does_not_retry():
    def late(batch, tick):
        tick[0] = 181
    result, calls = collect(count=450, daily_failure=late)
    daily = [p for u, p in calls if u == activity.BARS_URL and p["timeframe"] == "1Day"]
    assert len(daily) == 1 and result["integration"]["dated_prior_close_count"] == 0
    assert result["integration"]["collection_complete"] is False
    assert result["items"]["S00000"]["premarket_volume"] == 100


@pytest.mark.parametrize("when", [NOW-timedelta(days=1), NOW+timedelta(hours=1), NOW.replace(tzinfo=None)])
def test_invalid_current_premarket_does_not_start_either_provider(when):
    calls = []
    def get(*a, **kw): calls.append(a); raise AssertionError("unexpected")
    result = combined.collect_premarket_with_prior({}, DAY, now=when, get=get)
    assert calls == [] and result["integration"]["collection_complete"] is False
    assert result["prior_evidence"] is None and not result["universe_items"]


def test_daily_pagination_failure_never_commits_first_page_of_batch():
    get, calls, tick = provider()
    pages = [0]
    def paged(url, **kw):
        if url == activity.BARS_URL and kw["params"]["timeframe"] == "1Day":
            pages[0] += 1
            if pages[0] == 2: raise TimeoutError("PRIVATE")
            body = get(url, **kw).json()
            body["next_page_token"] = "PRIVATE_CURSOR"
            return SimpleNamespace(status_code=200, json=lambda: body)
        return get(url, **kw)
    result = combined.collect_premarket_with_prior({}, DAY, now=NOW, get=paged, clock=lambda: 0)
    assert pages[0] == 2 and result["integration"]["dated_prior_close_count"] == 0
    assert "PRIVATE" not in json.dumps(result)


def test_partial_activity_still_retains_full_daily_coverage_without_usable_volume():
    get, calls, tick = provider(count=250)
    def failing(url, **kw):
        if url == activity.BARS_URL and kw["params"]["timeframe"] == "1Min":
            raise TimeoutError("PRIVATE")
        return get(url, **kw)
    result = combined.collect_premarket_with_prior({}, DAY, now=NOW, get=failing, clock=lambda: 0)
    assert len(result["universe_items"]) == 250 and not result["items"]
    assert all(r["premarket_status"] == "UNPROCESSED" for r in result["universe_items"].values())
    assert result["integration"]["all_prior_closes_available"] is True
    assert result["integration"]["collection_complete"] is False


def test_storage_lost_ack_is_not_replayed_even_when_readback_matches():
    collection, _ = collect()
    write, read, rows, calls = memory_store()
    def lost_ack(*a, **kw):
        write(*a, **kw)
        raise TimeoutError("PRIVATE")
    result, _, _ = persist(collection, write=lost_ack, read=read)
    assert len(calls) == 1 and len(rows) == 3
    assert result["readback_outcome"] == "MATCH" and result["storage_verified"] is False
    assert result["ambiguous_symbols"] == result["unacknowledged_symbols"] == sorted(collection["universe_items"])
    assert "PRIVATE" not in json.dumps(result)


@pytest.mark.parametrize("damage", ["missing", "changed", "extra", "duplicate", "wrong_run", "offline"])
def test_storage_readback_damage_cannot_pass(damage):
    collection, _ = collect()
    write, read, rows, calls = memory_store()
    def damaged(*a, **kw):
        data = read(*a, **kw)
        if damage == "missing": return data[:-1]
        if damage == "changed": data[0]["notes"] = "changed"
        if damage == "extra": data.append(dict(data[0], symbol="EXTRA"))
        if damage == "duplicate": data.append(deepcopy(data[0]))
        if damage == "wrong_run": data[0]["run_id"] = "other-run"
        if damage == "offline": raise TimeoutError("PRIVATE")
        return data
    result, _, _ = persist(collection, write=write, read=damaged)
    assert result["storage_verified"] is False and result["collection_storage_accepted"] is False


def test_wrong_ack_stops_before_next_batch(monkeypatch):
    collection, _ = collect()
    monkeypatch.setattr(storage, "BATCH_SIZE", 1)
    write, read, rows, calls = memory_store()
    def bad(*a, **kw):
        data = write(*a, **kw)
        data[0]["notes"] = "changed"
        return data
    result, _, _ = persist(collection, write=bad, read=read)
    assert len(calls) == 1 and len(result["unacknowledged_symbols"]) == 3


def test_expired_storage_budget_and_oversized_row_do_not_write(monkeypatch):
    collection, _ = collect()
    result, rows, calls = persist(collection, time_available=lambda: False)
    assert rows == calls == [] and result["persistence_outcome"] == "TIME_BUDGET"
    monkeypatch.setattr(storage, "BATCH_BYTES", 1)
    result, rows, calls = persist(collection)
    assert rows == calls == [] and result["persistence_outcome"] == "PAYLOAD_LIMIT"


@pytest.mark.parametrize("damage", ["strategy", "eligible", "missing_symbol", "bad_row", "bad_context"])
def test_invalid_storage_contract_fails_before_any_write(damage):
    collection, _ = collect()
    context = deepcopy(CONTEXT)
    if damage == "strategy": collection["experiment_class"] = "STRATEGY_1"
    if damage == "eligible": collection["strategy_eligible"] = True
    if damage == "missing_symbol": collection["universe_items"].pop("S00001")
    if damage == "bad_row": collection["universe_items"]["S00002"]["strategy_eligible"] = True
    if damage == "bad_context": context["strategy_evidence_eligible"] = True
    calls = []
    with pytest.raises(ValueError):
        persist(collection, context=context, write=lambda *a, **k: calls.append(k))
    assert calls == []


@pytest.mark.parametrize("change", ["production", "production_db", "strategy", "postopen", "rules"])
def test_coordinator_opt_in_guard_precedes_run_claim(monkeypatch, change):
    monkeypatch.setattr(coordinator, "require_auth", lambda _: None)
    monkeypatch.setenv("RENDER_SERVICE_ID", "srv-dal8abbl550s73cj3jm0")
    monkeypatch.setattr(coordinator, "SUPABASE_URL", "https://cihwmameyylixouggwxk.supabase.co")
    monkeypatch.setattr(coordinator, "RULESET_VERSION", "v0.3")
    args = dict(session_date=DAY, run_class="INFRASTRUCTURE_TEST", include_dated_prior_evidence=True)
    if change == "production": monkeypatch.setenv("RENDER_SERVICE_ID", "srv-daie017qj5pc739nck1g")
    if change == "production_db": monkeypatch.setattr(coordinator, "SUPABASE_URL", "https://production.invalid")
    if change == "strategy": args["run_class"] = "STRATEGY_1"
    if change == "postopen": args["phase"] = "POST_OPEN"
    if change == "rules": monkeypatch.setattr(coordinator, "RULESET_VERSION", "v9")
    calls = []
    monkeypatch.setattr(coordinator, "create_run_once", lambda *a: calls.append(a))
    with pytest.raises(HTTPException) as exc:
        coordinator.run_scan(coordinator.ScanRequest(**args), None)
    assert exc.value.status_code == 403 and calls == []


def test_coordinator_persists_attached_activity_without_making_coverage_only_candidates(monkeypatch):
    evidence, _ = collect()
    monkeypatch.setattr(coordinator, "require_auth", lambda _: None)
    monkeypatch.setenv("RENDER_SERVICE_ID", "srv-dal8abbl550s73cj3jm0")
    monkeypatch.setattr(coordinator, "SUPABASE_URL", "https://cihwmameyylixouggwxk.supabase.co")
    monkeypatch.setattr(coordinator, "RULESET_VERSION", "v0.3")
    monkeypatch.setattr(coordinator, "alpaca_headers", lambda: {})
    monkeypatch.setattr(coordinator, "create_run_once", lambda *a: ({"id": "offline-run"}, True))
    for name in ("fetch_fred_release_calendar", "collect_ism_calendar", "collect_weekly_calendar"):
        monkeypatch.setattr(coordinator, name, lambda *a: [])
    for name in ("fetch_movers", "fetch_news", "fetch_ticker_map"):
        monkeypatch.setattr(coordinator, name, lambda *a: {})
    monkeypatch.setattr(coordinator, "collect_premarket_with_prior", lambda *a, **kw: evidence)
    rows, final = [], {}
    monkeypatch.setattr(coordinator, "sb_insert", lambda table, row: rows.append(row))
    monkeypatch.setattr(coordinator, "finalize_discovery_run", lambda key, row: final.update(row) or row)
    request = coordinator.ScanRequest(session_date=DAY, run_class="INFRASTRUCTURE_TEST", include_dated_prior_evidence=True)
    result = coordinator.run_scan(request, None)
    assert len(rows) == 1 and rows[0]["symbol"] == "S00000"
    assert rows[0]["mover_snapshot"]["premarket_activity"]["dated_prior_session_evidence"]["item"]["close"] == 11
    assert rows[0]["promotion_status"] == "REVIEW_REQUIRED" and result["status"] == "PARTIAL"
    assert '"prior_coverage_rows_persisted_by_coordinator": false' in final["notes"]
    assert '"S00002"' in final["notes"]
    # Existing deterministic claim remains in control; changing the collection
    # flag never authorizes replay of the same session/run key.
    monkeypatch.setattr(coordinator, "create_run_once", lambda *a: ({"id": "offline-run"}, False))
    monkeypatch.setattr(coordinator, "sb_select", lambda *a: [])
    monkeypatch.setattr(coordinator, "collect_premarket_with_prior", lambda *a, **kw: pytest.fail("replay"))
    again = coordinator.run_scan(request, None)
    assert len(rows) == 1 and again["run_id"] == "offline-run"
