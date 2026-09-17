from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
import main as worker


def decision(data, **changes):
    return worker.evaluate(worker.Candidate(**{**data, **changes}))


@pytest.mark.parametrize("confirmed", [False, True])
@pytest.mark.parametrize("approval", [None, False])
def test_target_approval_required(candidate_data, confirmed, approval):
    result = decision(candidate_data, target_validated=approval, trigger_confirmed=confirmed,
                      triggered_at=candidate_data["data_timestamp"])
    assert result.operational_state == "HOLD_UNRESOLVED"
    assert result.reason_code == "TARGET_NOT_VALIDATED"


def test_qualified_wait(candidate_data):
    result = decision(candidate_data)
    assert (result.decision,result.operational_state,result.reason_code) == ("WAIT","WAITING_FOR_TRIGGER","TRIGGER_NOT_CONFIRMED")


def test_confirmed_trade_still_uses_original_risk_limits(candidate_data):
    result = decision(candidate_data, trigger_confirmed=True, triggered_at=candidate_data["data_timestamp"],
                      confirmation_review_id=candidate_data["current_review"]["review_id"])
    assert result.decision == "TRADE"
    assert result.qty == 50 and result.dollar_risk == Decimal("50")
    assert result.planned_rr == Decimal("2")


@pytest.mark.parametrize("change,code", [
    ({"current_review":None},"CURRENT_REVIEW_REQUIRED"),
    ({"liquidity_ok":None},"STRUCTURED_INPUTS_UNRESOLVED"),
    ({"missed_trigger":True},"MISSED_TRIGGER"),
    ({"liquidity_ok":False},"LIQUIDITY_FAILED"),
    ({"target_price":"101"},"RR_BELOW_MINIMUM"),
    ({"realized_daily_loss_dollars":"100"},"DAILY_LOSS_LIMIT"),
    ({"executed_trades_today":3},"DAILY_TRADE_LIMIT"),
    ({"data_kind":"SYNTHETIC"},"SYNTHETIC_EVIDENCE_NOT_STRATEGY"),
    ({"market_data_source":"SYNTHETIC_DEPLOYMENT_A"},"TEST_LABEL_REQUIRES_INFRASTRUCTURE_CLASS"),
])
def test_fail_closed(candidate_data, change, code):
    result=decision(candidate_data,**change)
    assert result.decision != "TRADE"
    assert result.reason_code == code


def test_expired_review(candidate_data):
    candidate_data["current_review"]["valid_until"]=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
    assert decision(candidate_data).reason_code == "REVIEW_EXPIRED_OR_CONTRADICTORY"


def test_old_session_cannot_pass_with_positive_quality_flag(candidate_data):
    old=(datetime.now(timezone.utc)-timedelta(days=7)).isoformat()
    candidate_data["data_timestamp"]=old
    candidate_data["current_review"]["data_timestamp"]=old
    assert decision(candidate_data).reason_code == "REVIEW_SESSION_MISMATCH"


def test_price_refresh_cannot_refresh_approvals(candidate_data):
    candidate_data["data_timestamp"]=datetime.now(timezone.utc).isoformat()
    assert decision(candidate_data).reason_code == "REVIEW_DATA_MISMATCH"


def test_old_confirmation_cannot_pass_new_review(candidate_data):
    assert decision(candidate_data, trigger_confirmed=True, triggered_at=candidate_data["data_timestamp"],
                    confirmation_review_id="old").reason_code == "CURRENT_CONFIRMATION_REQUIRED"


def test_infrastructure_never_becomes_trade(candidate_data):
    result=decision(candidate_data,experiment_class="INFRASTRUCTURE_TEST",data_kind="SYNTHETIC")
    assert result.decision == "NO_TRADE" and result.reason_code == "INFRASTRUCTURE_TEST"


def test_classification_must_be_explicit(candidate_data):
    candidate_data.pop("experiment_class")
    with pytest.raises(ValidationError): worker.Candidate(**candidate_data)


def test_mislabeled_test_cannot_be_persisted(candidate_data):
    c=worker.Candidate(**{**candidate_data,"data_kind":"SYNTHETIC"})
    with pytest.raises(HTTPException) as error:
        worker.write_supabase(c,worker.evaluate(c))
    assert error.value.status_code == 422


def test_signal_persists_trace_and_actual_version(candidate_data, monkeypatch):
    saved={}
    class Response:
        ok=True
        def json(self): return [{"id":"signal"}]
    monkeypatch.setattr(worker,"SUPABASE_URL","http://local")
    monkeypatch.setattr(worker,"SUPABASE_SECRET_KEY","local-only")
    monkeypatch.setattr(worker.requests,"post",lambda *a,**kw:(saved.update(kw["json"]) or Response()))
    candidate_data.update(run_id="run",source_discovery_item_id="item")
    c=worker.Candidate(**candidate_data)
    assert worker.write_supabase(c,worker.evaluate(c)) == "signal"
    assert saved["status"] == "SHADOW"
    assert saved["decision_inputs"]["run_id"] == "run"
    assert saved["decision_inputs"]["candidate_id"] == candidate_data["candidate_id"]
    assert "sha256=" in saved["worker_version"]
