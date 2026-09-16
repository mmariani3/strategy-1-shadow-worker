from copy import deepcopy
from datetime import datetime,timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
import discovery_coordinator as discovery
from review_contract import readiness_problem


def setup_data(candidate_data):
    return {**{k:v for k,v in candidate_data.items() if k in discovery.SetupRequest.model_fields},
            "setup_rationale":"Local explicit setup","trigger_operator":"GTE"}


def test_setup_accepts_current_data_fields(candidate_data):
    result=discovery.SetupRequest(**setup_data(candidate_data))
    assert result.data_quality_ok and result.data_timestamp
    assert readiness_problem({**result.model_dump(mode="json"),"session_date":candidate_data["session_date"]}) is None


@pytest.mark.parametrize("field",["data_quality_ok","data_timestamp","current_review","liquidity_ok"])
def test_setup_not_ready_with_missing_inputs(candidate_data,field):
    data=setup_data(candidate_data);data.pop(field,None)
    result=discovery.SetupRequest(**data)
    assert readiness_problem({**result.model_dump(mode="json"),"session_date":candidate_data["session_date"]})


def test_handoff_preserves_run_and_review(candidate_data,monkeypatch):
    item_id,run_id=str(uuid4()),str(uuid4())
    review={k:v for k,v in candidate_data.items() if k in discovery.QualificationRequest.model_fields}
    review.update(reviewer="local",reviewed_at=datetime.now(timezone.utc).isoformat())
    item={"id":item_id,"symbol":"LOCAL","qualification_review":review,"promotion_status":"ELIGIBLE_FOR_ORCHESTRATOR"}
    run={"id":run_id,"session_date":candidate_data["session_date"],"phase":"POST_OPEN","experiment_class":"STRATEGY_1"}
    monkeypatch.setattr(discovery,"discovery_context",lambda _:(deepcopy(item),deepcopy(run)))
    monkeypatch.setattr(discovery,"ORCHESTRATOR_TOKEN","local")
    monkeypatch.setattr(discovery,"reserve_artifact",lambda *a,**kw:None)
    monkeypatch.setattr(discovery,"wait_for_dependency",lambda *a,**kw:None)
    monkeypatch.setattr(discovery,"sb_update",lambda *a,**kw:None)
    captured={}
    class Response:
        ok=True
        def json(self): return {"candidate_id":item_id,"operational_state":"WAITING_FOR_TRIGGER"}
    monkeypatch.setattr(discovery.requests,"post",lambda *a,**kw:(captured.update(kw["json"]) or Response()))
    result=discovery.construct_setup(item_id,discovery.SetupRequest(**setup_data(candidate_data)))
    assert captured["run_id"]==run_id
    assert captured["data_timestamp"] and captured["data_quality_ok"]
    assert captured["current_review"]["review_id"]==candidate_data["current_review"]["review_id"]
    assert result["operational_state"]=="WAITING_FOR_TRIGGER"


def test_legacy_combined_contract_cannot_partially_promote(monkeypatch):
    monkeypatch.setattr(discovery,"require_auth",lambda _:None)
    with pytest.raises(HTTPException) as exc: discovery.promote(str(uuid4()),None,None)
    assert exc.value.status_code==410


def test_lower_rr_setup_requires_explicit_clean_structure(candidate_data):
    data=setup_data(candidate_data)
    data["target_price"]="101.75"
    assert readiness_problem({**data,"session_date":candidate_data["session_date"]}) == "CLEAN_STRUCTURE_UNRESOLVED"


def test_discovery_attribution_includes_reviewer():
    payload=discovery.attributable({"qualification_review":{"reviewer":"reviewer"},"operational_state":"WATCHLIST_CANDIDATE"})
    assert payload["transition_context"]["reviewer"] == "reviewer"
    assert "sha256=" in payload["transition_context"]["implementation_version"]
