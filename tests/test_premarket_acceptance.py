"""Offline infrastructure-only endpoint guards and storage verification."""
from datetime import timedelta
import json
from types import SimpleNamespace

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

import premarket_acceptance as a


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


@pytest.mark.parametrize("instant", [a.LAUNCH-timedelta(seconds=1), a.LAUNCH+timedelta(minutes=1)])
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
        return [body]
    monkeypatch.setattr(a,"db_call",db)
    monkeypatch.setattr(a,"get_run",lambda: dict(record) if record else None)
    monkeypatch.setattr(a,"verify_items",lambda rid,expected: not ambiguous)
    result=a.execute()
    assert record["experiment_class"]=="INFRASTRUCTURE_TEST" and record["status"]=="PARTIAL"
    summary=json.loads(record["notes"])
    assert summary["strategy_evidence_eligible"] is False
    assert result["accepted"] is (not ambiguous)
    assert len(writes)==(1 if ambiguous else 3)
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
        return [body]
    monkeypatch.setattr(a,"db_call",db)
    monkeypatch.setattr(a,"get_run",lambda: dict(record) if record else None)
    monkeypatch.setattr(a,"verify_items",lambda *args: True)
    result=a.execute()
    assert result["accepted"] is False and result["acknowledged_items"]==1
    assert json.loads(record["notes"])["unacknowledged_symbols"]==["BBB"]
