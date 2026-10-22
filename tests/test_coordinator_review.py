"""Review regressions, offline fixtures only; no hosted evidence or credentials."""
from copy import deepcopy
import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import discovery_coordinator as d
from coordinator_acceptance_app import create_app
from coordinator_acceptance_controls import coverage_ledger
from coordinator_acceptance_verify import verify
from test_coordinator_acceptance import wired, run, REQUEST


def test_prior_attachment_validated_once_for_whole_candidate_manifest(wired, monkeypatch):
    original = d.attach_prior_evidence
    counts = []
    def attach(items, envelope):
        counts.append(len(items))
        return original(items, envelope)
    monkeypatch.setattr(d, "attach_prior_evidence", attach)
    assert run(wired).status_code == 200
    assert counts == [5]


@pytest.mark.parametrize("operation", ["items", "finalize", "new_claim"])
def test_replayed_control_cannot_write(wired, operation):
    assert run(wired).status_code == 200
    assert run(wired).json()["idempotent_replay"]
    control = wired.controls[-1]
    before = deepcopy(wired.db.snapshot())
    if operation == "items":
        body = {k: v for k, v in wired.db.items[-1].items() if k not in ("id", "transition_context")}
        method, table, params = "POST", "strategy_discovery_items", {}
    elif operation == "finalize":
        body = {"status": "PARTIAL", "notes": "must not replace existing evidence"}
        method, table, params = "PATCH", "strategy_discovery_runs", {"run_key": "eq."+control.run_key}
    else:
        with pytest.raises(HTTPException):
            control.claim(d.ScanRequest(**REQUEST), "DIFFERENT_KEY", headers={})
        assert wired.db.snapshot() == before
        return
    with pytest.raises(HTTPException):
        control.database(method, table, headers={}, body=body, params=params)
    assert wired.db.snapshot() == before


def test_successful_empty_activity_is_not_provider_unavailability():
    result = coverage_ledger({}, {"items": {}, "collection": {"outcome": "FEED_EXHAUSTED",
        "universe_symbols": ["OFFLINE"], "no_bars_symbols": ["OFFLINE"], "unprocessed_symbols": []}}, [], [], {}, {})
    channel = result["channels"]["premarket_movers_unusual_activity"]
    assert channel["status"] == "PARTIAL"
    assert channel["transport_outcome"] == "FEED_EXHAUSTED"
    assert channel["no_activity_rows"] is True and channel["channel_complete"] is False


def test_factory_failure_redacted_and_fails_closed(wired):
    def fail():
        raise RuntimeError("OFFLINE_PRIVATE_DIAGNOSTIC")
    client = TestClient(create_app(fail))
    result = client.post("/scan/run-once", json=REQUEST, headers={"Authorization": "Bearer OFFLINE_AUTH"})
    assert result.status_code == 502 and "OFFLINE_PRIVATE_DIAGNOSTIC" not in result.text
    assert not wired.db.calls


@pytest.mark.parametrize("failure", ["snapshot_shape", "bad_event", "bad_prior", "bad_channel"])
def test_independent_verifier_fails_closed_for_malformed_snapshots(wired, failure):
    before = wired.db.snapshot()
    assert run(wired).status_code == 200
    after = wired.db.snapshot()
    if failure == "snapshot_shape": after["items"] = None
    elif failure == "bad_event": after["events"][-1]["payload"] = None
    elif failure == "bad_prior": after["items"][-1]["mover_snapshot"] = None
    else:
        notes = json.loads(after["runs"][-1]["notes"])
        notes["coverage"]["channels"] = None
        after["runs"][-1]["notes"] = json.dumps(notes)
    result = verify(before, after, run_key=d.make_run_key(d.ScanRequest(**REQUEST)), implementation="OFFLINE_IMPLEMENTATION")
    assert result["passed"] is False and result["failures"]
