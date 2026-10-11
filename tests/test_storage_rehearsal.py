"""Synthetic rehearsal safety and shared persistence contract. No network."""
from datetime import timedelta
from types import SimpleNamespace
import json
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
import storage_rehearsal as r
import premarket_acceptance as old


@pytest.fixture
def configured(monkeypatch):
    for k, v in {"RENDER_SERVICE_ID": r.SERVICE, "SUPABASE_URL": r.DB,
                 "SUPABASE_SECRET_KEY": "offline-key", "DISCOVERY_SERVICE_TOKEN": "offline-token",
                 "RULESET_VERSION": "v0.3"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(r, "now", lambda: r.START + timedelta(minutes=5))


def test_separate_routes_and_original_expiry_remain_closed(configured, monkeypatch):
    assert {p.path for p in r.app.routes} == {"/health", "/rehearsal/preflight", "/rehearsal/run", "/rehearsal/result"}
    assert old.DAY.isoformat() == "2026-10-09"
    assert old.EXPIRES < r.START and old.RUN_KEY != r.KEY
    assert r.health()["market_requests"] is False
    monkeypatch.setattr(old, "now", lambda: r.START)
    with pytest.raises(ValueError): old.execute()


@pytest.mark.parametrize("instant", [r.START-timedelta(seconds=1), r.EXPIRES, r.EXPIRES+timedelta(days=1)])
def test_dates_fail_closed(configured, monkeypatch, instant):
    monkeypatch.setattr(r, "now", lambda: instant)
    with pytest.raises(HTTPException): r.guard("Bearer offline-token")
    with pytest.raises(ValueError): r.execute()


@pytest.mark.parametrize("variable,value", [("RENDER_SERVICE_ID", "production"),
    ("SUPABASE_URL", "https://production.invalid"), ("RULESET_VERSION", "v1.0")])
def test_identity_guards(configured, monkeypatch, variable, value):
    monkeypatch.setenv(variable, value)
    with pytest.raises(HTTPException): r.guard("Bearer offline-token")


def test_auth_and_no_private_error_output(configured, monkeypatch):
    def fail(): raise RuntimeError("PRIVATE_ERROR")
    monkeypatch.setattr(r, "execute", fail)
    client = TestClient(r.app)
    assert client.post("/rehearsal/run").status_code == 401
    response = client.post("/rehearsal/run", headers={"Authorization": "Bearer offline-token"})
    assert response.status_code == 503 and "PRIVATE_ERROR" not in response.text


def test_fixture_is_explicit_synthetic_without_prices():
    items = r.fixture_items()
    assert len(items) == 3689
    assert all(s.startswith("ZZTEST") and e["synthetic"] and not e["strategy_evidence_eligible"] for s, e in items.items())
    assert all(set(e) == {"synthetic", "strategy_evidence_eligible", "fixture_index", "source", "padding"} for e in items.values())


def test_complete_contract_uses_shared_bulk_code_and_retains_partial_status(configured, monkeypatch):
    record, items, writes = {}, [], []
    def db(method, table, params=None, body=None):
        if table == "strategy_discovery_runs":
            if method == "GET": return [dict(record)] if record else []
            record.update(body); record["id"] = "fixture-run"
            return [dict(record)]
        if method == "POST":
            writes.append(body); items.extend(body)
            return list(reversed(body))
        offset = int(params["offset"])
        return items[offset:offset+100]
    monkeypatch.setattr(r, "db_call", db)
    result = r.execute()
    assert result["accepted"] and result["acknowledged_items"] == 3689 and len(writes) == 37
    assert record["status"] == "PARTIAL" and record["experiment_class"] == "INFRASTRUCTURE_TEST"
    assert all(row["notes"] == r.LABEL and row["discovered_via"] == ["SYNTHETIC_STORAGE_FIXTURE"] for row in items)
    summary = json.loads(record["notes"])
    assert summary["synthetic"] and not summary["strategy_evidence_eligible"]
    before = len(writes)
    with pytest.raises(ValueError): r.execute()
    assert len(writes) == before


def test_ambiguous_run_claim_cannot_proceed_to_items(configured, monkeypatch):
    calls = []
    def db(method, table, params=None, body=None):
        calls.append((method, table))
        if method == "GET": return []
        raise TimeoutError("private")
    monkeypatch.setattr(r, "db_call", db)
    with pytest.raises(TimeoutError): r.execute()
    assert calls == [("GET", "strategy_discovery_runs"), ("POST", "strategy_discovery_runs")]


def test_database_request_is_fixed_and_audits_every_row(configured, monkeypatch):
    calls = []
    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return SimpleNamespace(status_code=201, json=lambda: kwargs["json"])
    monkeypatch.setattr(r.requests, "request", request)
    rows = [r.payload("run", "ZZTEST000000", {"synthetic": True})]
    result = r.db_call("POST", "strategy_discovery_items", body=rows)
    assert result[0]["transition_context"]["synthetic"]
    assert calls[0][1] == r.DB + "/rest/v1/strategy_discovery_items"
    assert calls[0][2]["allow_redirects"] is False
    for method, table in [("DELETE", "strategy_discovery_items"), ("POST", "strategy_candidates"), ("PATCH", "strategy_discovery_items")]:
        with pytest.raises(ValueError): r.db_call(method, table, body=rows)
    assert len(calls) == 1


def test_run_patch_cannot_touch_old_records_or_mark_complete(configured):
    for params, body in [({"run_key": "eq."+old.RUN_KEY}, {"status": "PARTIAL"}),
                         ({"run_key": "eq."+r.KEY}, {"status": "COMPLETE"})]:
        with pytest.raises(ValueError): r.db_call("PATCH", "strategy_discovery_runs", params=params, body=body)
