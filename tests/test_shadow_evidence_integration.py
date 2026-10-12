from copy import deepcopy
from datetime import timedelta
import json
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

import discovery_coordinator as coordinator
import shadow_evidence_api as isolated
import shadow_evidence_routes as routes
from shadow_evidence_workflow import dated_prior_evidence, attach_prior_evidence


@pytest.fixture
def configured(monkeypatch):
    for key, value in {"RENDER_SERVICE_ID": routes.SERVICE, "RULESET_VERSION": "v0.3",
                       "RENDER_GIT_COMMIT": "a"*40, "DISCOVERY_SERVICE_TOKEN": "offline-token",
                       "ALPACA_API_KEY": "offline-key", "ALPACA_API_SECRET": "offline-secret"}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(routes, "now", lambda: routes.NOT_BEFORE + timedelta(minutes=5))
    return {"Authorization": "Bearer offline-token"}


@pytest.mark.parametrize("app", [isolated.app, coordinator.app])
def test_shared_prior_route_authenticates_and_uses_real_adapter_with_mock_transport(app, configured, monkeypatch):
    import prior_session_evidence as adapter
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        if url == adapter.CALENDAR_URL:
            body = [{"date": "2026-10-09"}, {"date": "2026-10-12"}]
        else:
            assert url == adapter.BARS_URL
            assert kwargs["params"]["symbols"] == "SPY,QQQ,IWM"
            body = {"bars": {s: [dict(t="2026-10-09T04:00:00Z", o=10, h=12, l=9, c=11, v=12)]
                             for s in routes.SYMBOLS}}
        return SimpleNamespace(status_code=200, json=lambda: body)
    monkeypatch.setattr(adapter.requests, "get", get)
    client = TestClient(app)
    assert client.get("/evidence/prior-session").status_code == 401
    assert calls == []
    response = client.get("/evidence/prior-session", headers=configured)
    assert response.status_code == 200
    result = response.json()
    assert result["previous_close"]["prior_session"] == "2026-10-09"
    assert len(result["previous_close"]["completed_symbols"]) == 3
    assert result["strategy_eligible"] is False
    assert len(calls) == 2
    assert "offline-secret" not in response.text


def test_isolated_app_has_no_mutating_business_routes():
    assert {(r.path, tuple(sorted(r.methods))) for r in isolated.app.routes} == {
        ("/health", ("GET",)), ("/evidence/prior-session", ("GET",)),
        ("/evidence/setup-preview", ("POST",))}
    h = isolated.health()
    assert h["database_access"] is h["scan_routes"] is h["qualification_routes"] is False
    assert h["broker_execution_enabled"] is h["automatic_confirmation"] is False


@pytest.mark.parametrize("app", [isolated.app, coordinator.app])
def test_empty_preview_returns_unavailable_without_creating_setup(app, configured):
    response = TestClient(app).post("/evidence/setup-preview", headers=configured,
                                   json={"plan": {}, "observations": {}})
    assert response.status_code == 200
    result = response.json()
    assert result["packet"]["status"] == "UNAVAILABLE"
    assert all(result[k] is False for k in ("persisted", "promoted", "worker_called",
                                           "current_review_created", "strategy_eligible"))


@pytest.mark.parametrize("change", ["production", "wrong_rules", "wrong_commit", "expired", "early"])
def test_guard_blocks_read_and_preview_before_any_provider_call(configured, monkeypatch, change):
    if change == "production": monkeypatch.setenv("RENDER_SERVICE_ID", "srv-daie017qj5pc739nck1g")
    if change == "wrong_rules": monkeypatch.setenv("RULESET_VERSION", "v0.4")
    if change == "wrong_commit": monkeypatch.setenv("RENDER_GIT_COMMIT", "unknown")
    if change == "expired": monkeypatch.setattr(routes, "now", lambda: routes.EXPIRES)
    if change == "early": monkeypatch.setattr(routes, "now", lambda: routes.NOT_BEFORE-timedelta(seconds=1))
    c = TestClient(isolated.app)
    assert c.get("/evidence/prior-session", headers=configured).status_code == 503
    assert c.post("/evidence/setup-preview", headers=configured, json={}).status_code == 503


def test_preview_invalid_input_errors_do_not_echo_values(configured):
    c = TestClient(isolated.app)
    response = c.post("/evidence/setup-preview", headers=configured,
                      json={"plan": "PRIVATE_INPUT", "observations": {}})
    assert response.status_code == 422 and "PRIVATE_INPUT" not in response.text
    response = c.post("/evidence/setup-preview", headers=configured, content="x"*(256*1024+1))
    assert response.status_code == 413


def test_attaching_dated_close_preserves_original_diagnostics_and_gaps():
    def get(url, **kwargs):
        body = ([{"date": "2026-10-09"}, {"date": "2026-10-12"}] if "calendar" in url
                else {"bars": {"TEST": [dict(t="2026-10-09T04:00:00Z", o=10, h=12, l=9, c=11, v=12)]}})
        return SimpleNamespace(status_code=200, json=lambda: body)
    checked = routes.NOT_BEFORE
    envelope = dated_prior_evidence({}, ["TEST"], checked.date(), now=checked, get=get)
    original = {"TEST": {"previous_close_status": "UNAVAILABLE", "gap_pct": None,
                           "previous_close_unavailable_reason": "WRONG_PREVIOUS_SESSION"}, "MISSING": {}}
    frozen = deepcopy(original)
    attached = attach_prior_evidence(original, envelope)
    assert original == frozen
    assert attached["TEST"]["previous_close_status"] == "UNAVAILABLE"
    assert attached["TEST"]["gap_pct"] is None
    assert attached["TEST"]["dated_prior_session_evidence"]["item"]["close"] == 11
    assert attached["MISSING"]["dated_prior_session_evidence"]["item"]["reason"] == "SYMBOL_NOT_REQUESTED"
    envelope["previous_close"]["items"]["TEST"]["close"] = 999
    with pytest.raises(ValueError): attach_prior_evidence(original, envelope)


def test_provider_exception_sanitized(configured, monkeypatch):
    monkeypatch.setattr(routes, "dated_prior_evidence", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("PRIVATE")))
    response = TestClient(isolated.app).get("/evidence/prior-session", headers=configured)
    assert response.status_code == 503 and "PRIVATE" not in response.text
