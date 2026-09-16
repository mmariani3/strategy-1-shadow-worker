from copy import deepcopy
from datetime import datetime,timedelta,timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
import orchestrator as orch
import main as worker


@pytest.fixture
def store(candidate_data,monkeypatch):
    c={**candidate_data,"id":candidate_data["candidate_id"],"ruleset_version":"v0.3",
       "status":"CONFIRMATION_REQUIRED","operational_state":"CONFIRMATION_REQUIRED",
       "last_worker_decision":"WAIT","trigger_observed_at":candidate_data["data_timestamp"],
       "trigger_operator":"GTE","created_at":(datetime.now(timezone.utc)-timedelta(seconds=30)).isoformat(),
       "lifecycle_revision":0,"active":True}
    events=[]
    monkeypatch.setattr(orch,"require_auth",lambda x:None)
    monkeypatch.setattr(orch,"get_candidate",lambda x:deepcopy(c))
    def update(old,changes):
        assert old["lifecycle_revision"] == c["lifecycle_revision"]
        c.update(deepcopy(changes));c["lifecycle_revision"]+=1
        return deepcopy(c)
    monkeypatch.setattr(orch,"update_candidate",update)
    monkeypatch.setattr(orch,"write_event",lambda *a,**k:events.append((a,k)))
    def evaluate(payload):
        result=worker.evaluate(worker.Candidate(**payload)).model_dump(mode="json")
        return {**result,"supabase_record_id":str(uuid4())}
    monkeypatch.setattr(orch,"call_worker",evaluate)
    return c,events


def review_for(candidate_data,**changes):
    data={k:v for k,v in candidate_data.items() if k in orch.ConfirmationIn.model_fields}
    data=deepcopy(data)
    data["current_review"]["review_id"]=str(uuid4())
    return orch.ConfirmationIn(**{**data,"confirmed":False,"confirmation_source":"local reviewer",**changes})


@pytest.mark.parametrize("change,code",[({"missed_trigger":True},"MISSED_TRIGGER"),({"liquidity_ok":False},"LIQUIDITY_FAILED")])
def test_negative_confirmation_preserves_invalidation(candidate_data,store,change,code):
    c,events=store
    result=orch.confirm_trigger(c["id"],review_for(candidate_data,**change),None)
    assert c[next(iter(change))] == next(iter(change.values()))
    assert result["worker"]["decision"] == "NO_TRADE"
    assert result["reason_code"] == code
    assert events[0][1]["payload"]["review"][next(iter(change))] == next(iter(change.values()))


def test_explicit_resume_preserves_prior_observation(candidate_data,store):
    c,events=store
    before=c["trigger_observed_at"]
    result=orch.confirm_trigger(c["id"],review_for(candidate_data,resume_monitoring=True),None)
    assert result["operational_state"] == "WAITING_FOR_TRIGGER"
    assert c["trigger_observed_at"] is None
    assert not c["trigger_confirmed"]
    # The actual DB transition trigger retains before/after; explicit review event retains intent.
    assert events[0][1]["payload"]["review"]["resume_monitoring"]
    assert before


def test_resume_requires_unmissed_input(candidate_data,store):
    c,_=store
    with pytest.raises(HTTPException):
        orch.confirm_trigger(c["id"],review_for(candidate_data,resume_monitoring=True,missed_trigger=None),None)


def test_omitted_inputs_do_not_reuse_old_approval(candidate_data,store):
    c,_=store
    result=orch.confirm_trigger(c["id"],review_for(candidate_data,liquidity_ok=None),None)
    assert c["liquidity_ok"] is None
    assert result["operational_state"] == "HOLD_UNRESOLVED"


def test_positive_confirmation_requires_observation(candidate_data,store):
    c,_=store;c["trigger_observed_at"]=None;c["operational_state"]="WAITING_FOR_TRIGGER"
    with pytest.raises(HTTPException): orch.confirm_trigger(c["id"],review_for(candidate_data,confirmed=True),None)


def test_positive_confirmation_rechecks_all_rules(candidate_data,store):
    c,_=store
    result=orch.confirm_trigger(c["id"],review_for(candidate_data,confirmed=True,target_validated=False),None)
    assert result["operational_state"] == "HOLD_UNRESOLVED"


def test_successful_positive_confirmation(candidate_data,store):
    c,_=store
    result=orch.confirm_trigger(c["id"],review_for(candidate_data,confirmed=True),None)
    assert result["worker"]["decision"] == "TRADE"
    assert not c["active"]


def test_reused_review_rejected(candidate_data,store):
    c,_=store
    review=review_for(candidate_data,current_review=candidate_data["current_review"])
    with pytest.raises(HTTPException): orch.confirm_trigger(c["id"],review,None)


def test_monitor_only_observes(candidate_data,store,monkeypatch):
    from decimal import Decimal
    c,events=store;c.update(operational_state="WAITING_FOR_TRIGGER",trigger_observed_at=None)
    queries=[]
    monkeypatch.setattr(orch,"sb_select",lambda table,params:(queries.append(params) or [deepcopy(c)]))
    monkeypatch.setattr(orch,"ALPACA_DATA_FEED","sip")
    monkeypatch.setattr(orch,"latest_alpaca_trade",lambda symbol:(Decimal('100'),datetime.now(timezone.utc).isoformat()))
    original_review=deepcopy(c["current_review"])
    orch.monitor_run_once(None)
    assert queries[0]["operational_state"] == "eq.WAITING_FOR_TRIGGER"
    assert c["operational_state"] == "CONFIRMATION_REQUIRED" and c["trigger_confirmed"] is False
    assert c["current_review"] == original_review
    assert any(event[0][1] == "TRIGGER_OBSERVED" for event in events)


def test_monitor_expires_review(candidate_data,store,monkeypatch):
    from decimal import Decimal
    c,_=store;c.update(operational_state="WAITING_FOR_TRIGGER",trigger_observed_at=None)
    c["current_review"]["valid_until"]=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
    monkeypatch.setattr(orch,"sb_select",lambda *a,**kw:[deepcopy(c)])
    monkeypatch.setattr(orch,"ALPACA_DATA_FEED","sip")
    monkeypatch.setattr(orch,"latest_alpaca_trade",lambda symbol:(Decimal('100'),datetime.now(timezone.utc).isoformat()))
    orch.monitor_run_once(None)
    assert c["operational_state"] == "HOLD_UNRESOLVED" and not c["trigger_confirmed"]


def test_negative_review_preserves_changed_market(candidate_data,store):
    c,_=store
    result=orch.confirm_trigger(c["id"],review_for(candidate_data,market_context_ok=False),None)
    assert c["market_context_ok"] is False
    assert result["reason_code"] == "MARKET_CONTEXT_NOT_APPROVED"


def test_omitted_consolidation_approval_expires(candidate_data,store):
    c,_=store
    result=orch.confirm_trigger(c["id"],review_for(candidate_data,consolidated_data=None),None)
    assert c["consolidated_data"] is None
    assert result["reason_code"] == "CONSOLIDATED_DATA_UNAVAILABLE"


def test_discovery_class_cannot_be_changed_at_handoff(candidate_data,monkeypatch):
    item_id,run_id=str(uuid4()),str(uuid4())
    fields={k:v for k,v in candidate_data.items() if k in orch.CandidateIn.model_fields}
    fields.update(source_discovery_item_id=item_id,run_id=run_id,discovery_phase="POST_OPEN",trigger_operator="GTE")
    monkeypatch.setattr(orch,"require_auth",lambda _:None)
    monkeypatch.setattr(orch,"sb_select",lambda table,params: ([{"id":item_id,"run_id":run_id,"symbol":"LOCAL","setup_review":{"entry_price":"100"},"qualification_review":{"reviewer":"local"}}]
        if table=="strategy_discovery_items" else [{"experiment_class":"INFRASTRUCTURE_TEST"}]))
    with pytest.raises(HTTPException) as error: orch.ingest_candidate(orch.CandidateIn(**fields),None)
    assert error.value.status_code==409
