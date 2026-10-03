"""Offline regression coverage: provider diagnostics must not become scan evidence."""
import json

import pytest
import requests

import discovery_coordinator as discovery


@pytest.mark.parametrize("provider,code", [
    ("fetch_fred_release_calendar", "FRED_RELEASE_CALENDAR_UNAVAILABLE"),
    ("fetch_movers", "ALPACA_MOVERS_UNAVAILABLE"),
    ("fetch_news", "ALPACA_NEWS_UNAVAILABLE"),
    ("fetch_ticker_map", "SEC_TICKER_MAP_UNAVAILABLE"),
])
@pytest.mark.parametrize("error_type", [requests.ConnectionError, requests.Timeout, RuntimeError])
def test_provider_failure_diagnostics_never_persist_or_return(monkeypatch, provider, code, error_type):
    # Invented marker only; no runtime credentials, network, or database access.
    marker = "OFFLINE_SYNTHETIC_SECRET_MARKER"
    monkeypatch.setattr(discovery, "require_auth", lambda _: None)
    monkeypatch.setattr(discovery, "create_run_once", lambda *args: ({"id": "offline-run"}, True))
    monkeypatch.setattr(discovery, "fetch_fred_release_calendar", lambda *args: [])
    monkeypatch.setattr(discovery, "fetch_movers", lambda *args: {})
    monkeypatch.setattr(discovery, "fetch_news", lambda *args: {})
    monkeypatch.setattr(discovery, "fetch_ticker_map", lambda *args: {})

    def fail(*args):
        raise error_type("Provider URL ?api_key=" + marker + " response body=" + marker)

    monkeypatch.setattr(discovery, provider, fail)
    persisted = {}

    def finalize(key, record):
        persisted.update(record)
        return record

    monkeypatch.setattr(discovery, "finalize_discovery_run", finalize)
    result = discovery.run_scan(discovery.ScanRequest(
        session_date="2026-10-05", phase="PREMARKET", run_class="INFRASTRUCTURE_TEST"), None)
    assert marker not in json.dumps(result)
    assert marker not in json.dumps(persisted)
    assert result["errors"] == [code]
    assert code in persisted["notes"]
    assert result["status"] == "PARTIAL"
    assert result["automatic_promotion"] is False
