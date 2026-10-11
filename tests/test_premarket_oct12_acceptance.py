"""Offline infrastructure-only endpoint guards and storage verification."""
from datetime import timedelta
import json
from types import SimpleNamespace

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

import premarket_oct12_acceptance as a


def test_oct12_is_distinct_from_preserved_oct9_and_storage_rehearsal():
    import premarket_acceptance as old
    import storage_rehearsal as rehearsal
    assert a.DAY.isoformat() == "2026-10-12"
    assert old.DAY.isoformat() == "2026-10-09"
    assert len({a.RUN_KEY, old.RUN_KEY, rehearsal.KEY}) == 3
    assert a.source_hash() != old.source_hash()


def test_diagnostics_report_date_mismatch_without_accepting_daily_bar():
    rows = {"AAA": {"dailyBar_session_date":"2026-10-09", "prevDailyBar_session_date":"2026-10-08",
        "previous_close_status":"UNAVAILABLE", "previous_close_unavailable_reason":"WRONG_PREVIOUS_SESSION"},
        "BBB": {}}
    result = a.previous_close_diagnostics(rows, "2026-10-09")
    assert result["daily_bar_matches_expected_but_previous_bar_does_not"] == 1
    assert result["histograms"]["previous_close_unavailable_reason"] == {"UNAVAILABLE":1,"WRONG_PREVIOUS_SESSION":1}
    assert result["acceptance_rule_changed"] is False and result["fallback_close_used"] is False
    assert "previous_close" not in rows["AAA"]


def test_authenticated_preflight_retains_only_snapshot_dates(configured, monkeypatch):
    responses = [
        [{"date":"2026-10-12","open":"09:30","close":"16:00"}],
        {"quotes":{"SPY":{}}},
        {"SPY":{"dailyBar":{"t":"2026-10-09T04:00:00Z","c":123.45},
                "prevDailyBar":{"t":"2026-10-08T04:00:00Z","c":122.5},
                "private":"DO_NOT_RETAIN"}}]
    calls=[]
    def get(url, **kwargs):
        calls.append((url,kwargs))
        body=responses.pop(0)
        return SimpleNamespace(status_code=200,json=lambda: body)
    monkeypatch.setattr(a.requests,"get",get)
    monkeypatch.setattr(a,"get_run",lambda: None)
    result=a.preflight("Bearer offline-token")
    assert result["snapshot_endpoint_authenticated"] is True
    assert result["snapshot_diagnostic"]["dailyBar_session_date"] == "2026-10-09"
    assert result["snapshot_diagnostic"]["prevDailyBar_session_date"] == "2026-10-08"
    assert "123.45" not in json.dumps(result) and "DO_NOT_RETAIN" not in json.dumps(result)
    assert len(calls)==3 and all(not kw["allow_redirects"] for _,kw in calls)


@pytest.fixture
def configured(monkeypatch):
    for k,v in {"RENDER_SERVICE_ID": a.SERVICE, "SUPABASE_URL": a.DB, "RULESET_VERSION": "v0.3",
                "ALPACA_API_KEY": "offline-key", "ALPACA_API_SECRET": "offline-secret",
                "SUPABASE_SECRET_KEY": "offline-db", "DISCOVERY_SERVICE_TOKEN": "offline-token"}.items():
        monkeypatch.setenv(k,v)
    monkeypatch.setattr(a, "now", lambda: a.LAUNCH)


def test_no_trading_journal_or_normal_scan_routes():
    assert {(next(iter(r.methods)),r.path) for r in a.app.routes} == {
        ("GET","/health"),("GET","/acceptance/preflight"),("POST","/acceptance/run"),("GET","/acceptance/result")}


def test_auth_and_fixed_staging_guard(configured, monkeypatch):
    with pytest.raises(HTTPException) as exc:
        a.guard(None)
    assert exc.value.status_code == 401
    a.guard("Bearer offline-token")
    monkeypatch.setenv("SUPABASE_URL", "https://zgegtiqsjotszaspcgzf.supabase.co")
    with pytest.raises(HTTPException):
        a.guard("Bearer offline-token")


@pytest.mark.parametrize("instant", [a.LAUNCH-timedelta(days=1), a.LAUNCH-timedelta(minutes=30),
                                      a.LAUNCH-timedelta(seconds=1), a.LAUNCH+timedelta(minutes=1)])
def test_execute_only_one_minute_no_network(instant, monkeypatch):
    monkeypatch.setattr(a, "now", lambda: instant)
    with pytest.raises(ValueError):
        a.execute()


def test_existing_run_cannot_replay(configured, monkeypatch):
    monkeypatch.setattr(a,"get_run",lambda: {"id":"old"})
    with pytest.raises(ValueError):
        a.execute()


def test_write_expiry_and_production_target_fail_before_network(configured, monkeypatch):
    monkeypatch.setattr(a,"now",lambda: a.STOP)
    with pytest.raises(ValueError):
        a.db_call("POST","strategy_discovery_runs",body={})
    monkeypatch.setattr(a,"now",lambda: a.LAUNCH)
    monkeypatch.setenv("SUPABASE_URL","https://production.invalid")
    with pytest.raises(ValueError):
        a.db_call("GET","strategy_discovery_runs")


def test_errors_do_not_leak_provider_diagnostics(configured, monkeypatch):
    def fail():
        raise RuntimeError("SYNTHETIC_SECRET_ERROR")
    monkeypatch.setattr(a,"execute",fail)
    response = TestClient(a.app).post("/acceptance/run",headers={"Authorization":"Bearer offline-token"})
    assert response.status_code == 503
    assert "SYNTHETIC_SECRET_ERROR" not in response.text


def test_paginated_readback_requires_every_field(configured, monkeypatch):
    expected = {f"X{i:03}": a.digest(a.item_payload("run",f"X{i:03}",{"v":i})) for i in range(201)}
    rows = [a.item_payload("run",f"X{i:03}",{"v":i}) for i in range(201)]
    calls=[]
    def db(method, table, params):
        calls.append(params)
        start=int(params["offset"])
        return rows[start:start+100]
    monkeypatch.setattr(a,"db_call",db)
    assert a.verify_items("run",expected)
    assert len(calls)==3
    rows[200]["mover_snapshot"]={}
    assert not a.verify_items("run",expected)


@pytest.mark.parametrize("ambiguous",[False,True])
def test_real_contract_payloads_are_infrastructure_only_and_ambiguity_stops_writes(configured,monkeypatch,ambiguous):
    items={s:{"value":i} for i,s in enumerate(["AAA","BBB","CCC"])}
    monkeypatch.setattr(a,"collect_premarket",lambda *args: {"items":items,"collection":{
        "outcome":"FEED_EXHAUSTED","unprocessed_symbols":[]}})
    record={}
    writes=[]
    def db(method,table,params=None,body=None):
        if table=="strategy_discovery_runs":
            record.update(body)
            record["id"]="offline-run"
            return [dict(record)]
        writes.append(body)
        if ambiguous:
            raise RuntimeError("SYNTHETIC_PRIVATE")
        return list(reversed(body))
    monkeypatch.setattr(a,"db_call",db)
    monkeypatch.setattr(a,"get_run",lambda: dict(record) if record else None)
    monkeypatch.setattr(a,"verify_items",lambda rid,expected: not ambiguous)
    result=a.execute()
    assert record["experiment_class"]=="INFRASTRUCTURE_TEST" and record["status"]=="PARTIAL"
    summary=json.loads(record["notes"])
    assert summary["strategy_evidence_eligible"] is False
    assert result["accepted"] is (not ambiguous)
    assert len(writes)==1
    assert "SYNTHETIC_PRIVATE" not in record["notes"]
    assert summary["unacknowledged_symbols"]==(["AAA","BBB","CCC"] if ambiguous else [])


def test_operational_item_cap_is_explicit_not_full_acceptance(configured,monkeypatch):
    monkeypatch.setattr(a,"MAX_ITEMS",1)
    monkeypatch.setattr(a,"collect_premarket",lambda *args: {"items":{"AAA":{},"BBB":{}},
        "collection":{"outcome":"FEED_EXHAUSTED","unprocessed_symbols":[]}})
    record={}
    def db(method,table,params=None,body=None):
        if table=="strategy_discovery_runs":
            record.update(body); record["id"]="offline-run"
            return [dict(record)]
        return body
    monkeypatch.setattr(a,"db_call",db)
    monkeypatch.setattr(a,"get_run",lambda: dict(record) if record else None)
    monkeypatch.setattr(a,"verify_items",lambda *args: True)
    result=a.execute()
    assert result["accepted"] is False and result["acknowledged_items"]==1
    assert json.loads(record["notes"])["unacknowledged_symbols"]==["BBB"]


def test_bulk_real_http_contract_includes_each_rows_audit_context(configured, monkeypatch):
    captured = []
    def request(method, url, **kwargs):
        captured.append((method, url, kwargs))
        return SimpleNamespace(status_code=201, json=lambda: kwargs["json"])
    monkeypatch.setattr(a.requests, "request", request)
    rows = [a.item_payload("run", s, {"fixture": True}) for s in ("AAA", "BBB")]
    result = a.db_call("POST", "strategy_discovery_items", body=rows)
    assert len(result) == 2 and all(r["transition_context"]["strategy_evidence_eligible"] is False for r in result)
    assert all("transition_context" not in r for r in rows)  # Do not mutate expected digests.
    method, url, kw = captured[0]
    assert method == "POST" and url == a.DB + "/rest/v1/strategy_discovery_items"
    assert kw["headers"]["Prefer"] == "return=representation"
    assert not kw["allow_redirects"] and kw["timeout"] == (3, 10)
    assert "resolution=" not in kw["headers"]["Prefer"]  # No upsert/replay.


@pytest.mark.parametrize("case", ["runs", "patch", "empty", "too_many", "keys", "bytes"])
def test_invalid_bulk_requests_fail_before_network(configured, monkeypatch, case):
    rows = [a.item_payload("run", "AAA", {})]
    method, table = "POST", "strategy_discovery_items"
    if case == "runs": table = "strategy_discovery_runs"
    if case == "patch": method = "PATCH"
    if case == "empty": rows = []
    if case == "too_many": rows *= a.WRITE_BATCH_SIZE + 1
    if case == "keys": rows[0].pop("notes")
    if case == "bytes": monkeypatch.setattr(a, "WRITE_BATCH_BYTES", 1)
    with pytest.raises(ValueError):
        a.db_call(method, table, body=rows)


def test_3689_items_bulk_acknowledged_and_independently_paginated(configured, monkeypatch):
    items = {f"X{i:05}": {"fixture": i} for i in range(3689)}
    stored, writes, reads = [], [], []
    def db(method, table, params=None, body=None):
        assert table == "strategy_discovery_items"
        if method == "POST":
            writes.append(body)
            stored.extend(body)
            return list(reversed(body))  # Response ordering is not contractual.
        reads.append(params)
        offset = int(params["offset"])
        return stored[offset:offset+100]
    monkeypatch.setattr(a, "db_call", db)
    result = a.persist_items("run", items)
    assert len(writes) == 37 and len(writes[-1]) == 89
    assert result["persistence_outcome"] == "ALL_ACKNOWLEDGED"
    assert len(result["expected"]) == 3689 and not result["unacknowledged_symbols"]
    assert a.verify_items("run", result["expected"]) and len(reads) == 37
    stored[-1]["mover_snapshot"] = {}
    assert not a.verify_items("run", result["expected"])


@pytest.mark.parametrize("bad", ["timeout", "missing", "duplicate", "changed", "extra", "null_field_missing"])
def test_bad_second_batch_never_retries_or_acknowledges_partial_response(configured, monkeypatch, bad):
    monkeypatch.setattr(a, "WRITE_BATCH_SIZE", 2)
    items = {f"X{i}": {} for i in range(5)}
    calls = []
    def db(method, table, body):
        calls.append(body)
        if len(calls) == 1: return body
        if bad == "timeout": raise TimeoutError("PRIVATE_ERROR")
        if bad == "missing": return body[:1]
        if bad == "duplicate": return [body[0], body[0]]
        if bad == "extra": return body + [body[0]]
        altered = [dict(row) for row in body]
        if bad == "changed": altered[1]["notes"] = "wrong"
        if bad == "null_field_missing": altered[1].pop("provisional_tier")
        return altered
    monkeypatch.setattr(a, "db_call", db)
    result = a.persist_items("run", items)
    assert len(calls) == 2 and set(result["expected"]) == {"X0", "X1"}
    assert result["unacknowledged_symbols"] == ["X2", "X3", "X4"]
    assert result["write_ambiguity_or_failure"]
    assert "PRIVATE_ERROR" not in json.dumps(result)


def test_byte_limit_splits_batches_and_oversized_item_stops_without_dispatch(configured, monkeypatch):
    items = {s: {"fixture": "\\u2603" * 50} for s in ("AAA", "BBB", "CCC")}
    size = len(a.encoded_body(a.audited_body([a.item_payload("run", "AAA", items["AAA"])])))
    monkeypatch.setattr(a, "WRITE_BATCH_BYTES", size)
    calls = []
    def db(method, table, body):
        calls.append(body)
        assert len(a.encoded_body(a.audited_body(body))) <= size
        return body
    monkeypatch.setattr(a, "db_call", db)
    result = a.persist_items("run", items)
    assert len(calls) == 3 and len(result["expected"]) == 3
    calls.clear()
    monkeypatch.setattr(a, "WRITE_BATCH_BYTES", size-1)
    result = a.persist_items("run", items)
    assert not calls and result["persistence_outcome"] == "PAYLOAD_LIMIT"
    assert result["unacknowledged_symbols"] == ["AAA", "BBB", "CCC"]


@pytest.mark.parametrize("wall_deadline", [False, True])
def test_persistence_time_limit_stops_between_batches(configured, monkeypatch, wall_deadline):
    monkeypatch.setattr(a, "WRITE_BATCH_SIZE", 1)
    elapsed = [0]
    monkeypatch.setattr(a.time, "monotonic", lambda: elapsed[0])
    calls = []
    def db(method, table, body):
        calls.append(body)
        if wall_deadline:
            monkeypatch.setattr(a, "now", lambda: a.STOP-timedelta(minutes=2))
        else:
            elapsed[0] = 180
        return body
    monkeypatch.setattr(a, "db_call", db)
    result = a.persist_items("run", {"AAA": {}, "BBB": {}})
    assert len(calls) == 1 and result["persistence_outcome"] == "TIME_BUDGET"
    assert result["unacknowledged_symbols"] == ["BBB"]
