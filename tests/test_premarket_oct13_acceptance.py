"""Offline hosted-path verification. No live data or database requests."""
from copy import deepcopy
from datetime import timedelta
import json

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

import premarket_oct13_acceptance as app
from test_premarket_evidence_pipeline import collect


@pytest.fixture
def configured(monkeypatch):
    for k, v in {"RENDER_SERVICE_ID": app.SERVICE, "SUPABASE_URL": app.DB, "RULESET_VERSION": "v0.3",
                 "RENDER_GIT_COMMIT": "a"*40, "DISCOVERY_SERVICE_TOKEN": "offline-token",
                 "ALPACA_API_KEY": "offline-key", "ALPACA_API_SECRET": "offline-secret",
                 "SUPABASE_SECRET_KEY": "offline-db"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(app, "now", lambda: app.LAUNCH)


def test_separate_date_and_no_strategy_routes():
    import premarket_oct12_acceptance as previous
    assert app.DAY.isoformat() == "2026-10-13" and previous.DAY.isoformat() == "2026-10-12"
    assert app.RUN_KEY != previous.RUN_KEY and app.source_hash() != previous.source_hash()
    assert {(r.path, tuple(r.methods)) for r in app.app.routes} == {
        ("/health", ("GET",)), ("/acceptance/preflight", ("GET",)),
        ("/acceptance/run", ("POST",)), ("/acceptance/result", ("GET",))}


@pytest.mark.parametrize("key,value", [("RENDER_SERVICE_ID", "production"),
    ("SUPABASE_URL", "https://production.invalid"), ("RULESET_VERSION", "wrong"),
    ("RENDER_GIT_COMMIT", "unknown"), ("ALPACA_API_SECRET", "")])
def test_hosted_guard_rejects_invalid_identity_without_network(configured, monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(HTTPException): app.guard("Bearer offline-token")


@pytest.mark.parametrize("offset", [-86400, -1, 60, 86400])
def test_no_run_outside_single_minute(configured, monkeypatch, offset):
    monkeypatch.setattr(app, "now", lambda: app.LAUNCH+timedelta(seconds=offset))
    with pytest.raises(ValueError): app.execute()


def test_existing_run_blocks_all_collection_and_mutation(configured, monkeypatch):
    monkeypatch.setattr(app, "get_run", lambda: {"id": "existing"})
    with pytest.raises(ValueError): app.execute()


def test_full_hosted_path_persists_coverage_and_manifest_once(configured, monkeypatch):
    data, _ = collect(missing=("S00002",))
    monkeypatch.setattr(app, "collect_premarket_with_prior", lambda *a, **k: data)
    run, items, methods = {}, [], []
    def db(method, table, *, params=None, body=None):
        methods.append((method, table))
        if table == "strategy_discovery_runs":
            if method == "GET": return [deepcopy(run)] if run else []
            if method == "POST":
                assert not run
                run.update(body, id="offline-run")
            if method == "PATCH":
                assert params == {"id": "eq.offline-run", "run_key": "eq."+app.RUN_KEY,
                                  "experiment_class": "eq.INFRASTRUCTURE_TEST", "status": "eq.IN_PROGRESS"}
                run.update(body)
            return [deepcopy(run)]
        if method == "POST":
            items.extend(deepcopy(body))
            return deepcopy(body)
        start, limit = int(params["offset"]), int(params["limit"])
        return deepcopy(sorted(items, key=lambda r:r["symbol"])[start:start+limit])
    monkeypatch.setattr(app, "db_call", db)
    response = TestClient(app.app).post("/acceptance/run", headers={"Authorization": "Bearer offline-token"})
    assert response.status_code == 200 and response.json()["accepted"] is True
    assert len(items) == 3 and response.json()["activity_items"] == 1
    assert run["status"] == "PARTIAL" and run["experiment_class"] == "INFRASTRUCTURE_TEST"
    summary = json.loads(run["notes"])
    assert summary["integration"]["all_prior_closes_available"] is False
    assert summary["storage"]["storage_verified"] is True
    assert summary["strategy_evidence_eligible"] is False
    repeated = TestClient(app.app).post("/acceptance/run", headers={"Authorization": "Bearer offline-token"})
    assert repeated.status_code == 503 and len(items) == 3
    assert methods.count(("POST", "strategy_discovery_runs")) == 1


def test_ambiguous_claim_never_starts_collection_or_leaks_error(configured, monkeypatch):
    monkeypatch.setattr(app, "get_run", lambda: None)
    monkeypatch.setattr(app, "db_call", lambda *a, **k: (_ for _ in ()).throw(TimeoutError("PRIVATE")))
    monkeypatch.setattr(app, "collect_premarket_with_prior", lambda *a, **k: pytest.fail("collected"))
    response = TestClient(app.app).post("/acceptance/run", headers={"Authorization": "Bearer offline-token"})
    assert response.status_code == 503 and "PRIVATE" not in response.text


def test_write_cutoff_and_historical_patch_fail_before_transport(configured, monkeypatch):
    monkeypatch.setattr(app, "now", lambda: app.STOP)
    with pytest.raises(ValueError): app.db_call("POST", "strategy_discovery_items", body=[])
    monkeypatch.setattr(app, "now", lambda: app.LAUNCH)
    with pytest.raises(ValueError):
        app.db_call("PATCH", "strategy_discovery_runs", params={"run_key":"eq.old"}, body={"status":"PARTIAL"})
