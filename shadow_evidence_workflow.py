"""Shared evidence functions for Discovery and the isolated staging surface.

These return review material, never setup approvals, worker inputs or DB writes.
"""
from copy import deepcopy

from prior_session_evidence import collect_prior_session_evidence
from setup_evidence import build_setup_evidence, digest


def dated_prior_evidence(headers, symbols, session_date, **transport):
    result = collect_prior_session_evidence(headers, symbols, session_date, **transport)
    return {"schema": "shadow-evidence/v1", "experiment_class": "INFRASTRUCTURE_TEST",
            "mode": "SHADOW", "strategy_eligible": False, "broker_execution_enabled": False,
            "full_discovery_accepted": False, "previous_close": result,
            "evidence_hash": digest(result)}


def attach_prior_evidence(items, envelope):
    """Pure attachment under a new namespace; original snapshot fields survive.

    This is only an evidence envelope. It cannot repair a historical run, replace
    its accepted prior-close fields, change a gap calculation or mark it eligible.
    """
    if (envelope.get("schema") != "shadow-evidence/v1"
            or envelope.get("experiment_class") != "INFRASTRUCTURE_TEST"
            or envelope.get("strategy_eligible") is not False
            or digest(envelope["previous_close"]) != envelope.get("evidence_hash")):
        raise ValueError("INVALID_EVIDENCE_ENVELOPE")
    output = deepcopy(items)
    for symbol, item in output.items():
        item["dated_prior_session_evidence"] = {
            "experiment_class": "INFRASTRUCTURE_TEST", "strategy_eligible": False,
            "evidence_hash": envelope["evidence_hash"],
            "source_session_date": envelope["previous_close"].get("session_date"),
            "prior_session": envelope["previous_close"].get("prior_session"),
            "collection_outcome": envelope["previous_close"].get("outcome"),
            "item": deepcopy(envelope["previous_close"]["items"].get(symbol,
                {"status": "UNAVAILABLE", "reason": "SYMBOL_NOT_REQUESTED"}))}
    return output


def setup_preview(plan, observations, *, as_of, previous_packet=None):
    packet = build_setup_evidence(plan, observations, as_of=as_of, previous_packet=previous_packet)
    return {"schema": "shadow-setup-preview/v1", "mode": "SHADOW", "packet": packet,
            "persisted": False, "promoted": False, "worker_called": False,
            "current_review_created": False, "strategy_eligible": False,
            "broker_execution_enabled": False}
