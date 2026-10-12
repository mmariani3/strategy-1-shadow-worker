from copy import deepcopy
import json

import pytest

from main import APPROVED_ENTRY_MODELS
from review_contract import CURRENT_FIELDS
from setup_evidence import AUTHORITY, ENTRY_MODELS, build_setup_evidence

AS_OF = "2026-10-12T13:35:00Z"


@pytest.fixture
def inputs():
    plan = dict(candidate_id="SYNTHETIC-ONLY", symbol="TEST", direction="LONG", session_date="2026-10-12",
        entry_model="first_clean_pullback", recorded_at="2026-10-12T13:31:00Z",
        trigger_definition="Synthetic predefined level; confirmation remains unresolved",
        structural_rationale="Synthetic fixture structure", stop_rationale="Synthetic invalidation",
        target_rationale="Synthetic resistance", invalidation_conditions="Synthetic setup failure",
        source_ref="fixture:plan", trigger_price="10", entry_price="10", stop_price="9", target_price="12",
        authority=dict(AUTHORITY))
    provenance = dict(symbol="TEST", at="2026-10-12T13:33:00Z", received_at="2026-10-12T13:34:01Z",
                      feed="sip", delayed=False, source_ref="fixture:market")
    observations = dict(quote={**provenance, "bid": "10.1", "ask": "10.2"},
        bars=[{**provenance, "end_at": "2026-10-12T13:34:00Z", "o": 10, "h": 11, "l": 9.5, "c": 10.5, "v": 120}])
    return plan, observations


def test_measurements_do_not_approve_any_review_or_trigger(inputs):
    packet = build_setup_evidence(*inputs, as_of=AS_OF)
    assert ENTRY_MODELS == set(APPROVED_ENTRY_MODELS)
    assert packet["status"] == "NEEDS_CURRENT_REVIEW"
    assert packet["measurements"]["reward_risk"] == "2"
    assert packet["measurements"]["quote"]["spread"] == "0.1"
    bars = packet["measurements"]["observed_bars"]
    assert bars["last_close_at_or_above_trigger"] is True
    assert bars["trigger_confirmed"] is False
    assert bars["complete_window_verified"] is False
    assert set(CURRENT_FIELDS) <= packet["unresolved_reviews"].keys()
    assert all(r["status"] == "UNRESOLVED" for r in packet["unresolved_reviews"].values())
    assert packet["strategy_eligible"] is packet["broker_execution_enabled"] is False
    assert packet["experiment_class"] == "INFRASTRUCTURE_TEST"
    assert "current_review" not in packet


@pytest.mark.parametrize("field,value", [("feed", "iex"), ("delayed", True), ("symbol", "WRONG"),
    ("at", "2026-10-12T13:30:00Z"), ("at", "2026-10-11T13:33:00Z"),
    ("at", "2026-10-12T13:36:00Z"), ("at", "2026-10-12T13:33:00"),
    ("source_ref", ""), ("received_at", "2026-10-12T13:32:00Z"),
    ("received_at", "2026-10-12T13:36:00Z"), ("ask", "9"), ("bid", "NaN")])
def test_wrong_feed_identity_time_and_bad_quote_fail_closed(inputs, field, value):
    plan, obs = inputs
    obs["quote"][field] = value
    packet = build_setup_evidence(plan, obs, as_of=AS_OF)
    assert "quote" not in packet["measurements"]
    assert packet["status"] == "EVIDENCE_INCOMPLETE"


def test_expired_claimed_validity_is_rejected_and_future_expiry_is_not_approval(inputs):
    plan, obs = inputs
    obs["quote"].update(valid_until=AS_OF, validity_policy_ref="fixture:policy")
    assert "quote" not in build_setup_evidence(plan, obs, as_of=AS_OF)["measurements"]
    obs["quote"]["valid_until"] = "2026-10-12T13:36:00Z"
    packet = build_setup_evidence(plan, obs, as_of=AS_OF)
    assert packet["evidence"][0]["freshness_approved"] is False
    assert packet["unresolved_reviews"]["data_current"]["status"] == "UNRESOLVED"


@pytest.mark.parametrize("field,value", [("end_at", "2026-10-12T13:36:00Z"), ("h", 8), ("v", -1),
                                         ("v", True), ("v", 1.5), ("c", "Infinity")])
def test_bad_or_unfinished_bar_discards_entire_bar_window(inputs, field, value):
    plan, obs = inputs
    obs["bars"][0][field] = value
    packet = build_setup_evidence(plan, obs, as_of=AS_OF)
    assert "observed_bars" not in packet["measurements"]
    assert all(e["kind"] != "bar" for e in packet["evidence"])


def test_duplicate_bars_cannot_inflate_volume(inputs):
    plan, obs = inputs
    obs["bars"].append(deepcopy(obs["bars"][0]))
    assert "observed_bars" not in build_setup_evidence(plan, obs, as_of=AS_OF)["measurements"]


@pytest.mark.parametrize("field,value", [("stop_price", "8"), ("trigger_definition", "Changed trigger"),
                                         ("target_rationale", "Changed structure")])
def test_changed_plan_invalidates_binding(inputs, field, value):
    plan, obs = inputs
    previous = build_setup_evidence(plan, obs, as_of=AS_OF)
    plan[field] = value
    packet = build_setup_evidence(plan, obs, as_of=AS_OF, previous_packet=previous)
    assert packet["plan_changed"] is True
    assert packet["plan_hash"] != previous["plan_hash"]
    assert packet["review_binding_reusable"] is False


def test_changed_market_evidence_changes_packet_even_with_same_plan(inputs):
    plan, obs = inputs
    previous = build_setup_evidence(plan, obs, as_of=AS_OF)
    obs["quote"]["bid"] = "10.15"
    packet = build_setup_evidence(plan, obs, as_of=AS_OF)
    assert packet["plan_hash"] == previous["plan_hash"]
    assert packet["packet_hash"] != previous["packet_hash"]


def test_bad_geometry_and_missing_data_remain_unresolved(inputs):
    plan, obs = inputs
    plan["stop_price"] = "11"
    packet = build_setup_evidence(plan, {}, as_of=AS_OF)
    assert "INVALID_LONG_RISK_GEOMETRY" in packet["problems"]
    assert packet["measurements"] == {}


@pytest.mark.parametrize("change", [{"entry_model": "unapproved"}, {"authority": {}}, {"direction": "SHORT"},
                                  {"recorded_at": "2026-10-12T13:36:00Z"}, {"source_ref": ""}])
def test_unsupported_or_nonprospective_plan_is_unavailable(inputs, change):
    plan, obs = inputs
    plan.update(change)
    assert build_setup_evidence(plan, obs, as_of=AS_OF)["status"] == "UNAVAILABLE"


def test_caller_cannot_inject_approval_or_claim_strategy_evidence(inputs):
    plan, obs = inputs
    obs.update(trigger_confirmed=True, current_review={"setup_current": True}, experiment_class="STRATEGY_1")
    packet = build_setup_evidence(plan, obs, as_of=AS_OF)
    assert "current_review" not in packet
    assert packet["automatic_confirmation"] is False
    assert packet["strategy_eligible"] is False
    json.dumps(packet, allow_nan=False)


def test_context_sources_preserved_but_never_promoted_to_judgment(inputs):
    plan, obs = inputs
    before = build_setup_evidence(plan, obs, as_of=AS_OF)
    obs["supporting_evidence"] = [dict(review_fields=["catalyst_current", "qualification_current"],
        available_at="2026-10-09T12:00:00Z", received_at="2026-10-12T13:30:00Z",
        source_ref="fixture:issuer", summary="Synthetic source claim; not a real catalyst")]
    packet = build_setup_evidence(plan, obs, as_of=AS_OF)
    assert packet["supporting_evidence"][0]["status"] == "UNREVIEWED_SOURCE_CLAIM"
    assert packet["unresolved_reviews"]["catalyst_current"]["status"] == "UNRESOLVED"
    assert packet["packet_hash"] != before["packet_hash"]


@pytest.mark.parametrize("change", [{"available_at": "2026-10-12T13:36:00Z"},
    {"source_ref": ""}, {"review_fields": ["invented_approval"]}])
def test_invalid_context_source_is_not_preserved_as_usable_evidence(inputs, change):
    plan, obs = inputs
    item = dict(review_fields=["market_context_ok"], available_at="2026-10-12T13:30:00Z",
                received_at="2026-10-12T13:34:00Z", source_ref="fixture:index", summary="Synthetic context")
    obs["supporting_evidence"] = [{**item, **change}]
    packet = build_setup_evidence(plan, obs, as_of=AS_OF)
    assert packet["supporting_evidence"] == []
    assert "INVALID_SUPPORTING_SOURCE_EVIDENCE" in packet["problems"]
