"""Infrastructure-only integration of activity and dated prior-session evidence.

The candidate subset stays separate from the complete universe coverage ledger.
No source field is repaired, no ranking is produced and no review is approved.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import time

import requests

from premarket_collection import collect_premarket
from shadow_evidence_workflow import dated_prior_evidence, attach_prior_evidence
from setup_evidence import digest

COLLECTION_BUDGET_SECONDS = 180
SCHEMA = "premarket-dated-evidence/v1"


def collect_premarket_with_prior(headers, session_date, *, phase="PREMARKET", now=None,
                                 get=None, clock=None):
    """Two bounded GET collectors sharing a 180-second request budget.

    Each adapter retains its original 120-second/120-page caps. The shared
    budget also rejects a late response. Socket timeouts are not a hard process
    kill; hosted use still requires an independent suspension watchdog.
    """
    now = now or datetime.now(timezone.utc)
    get, clock = get or requests.get, clock or time.monotonic
    started = clock()

    def bounded_get(url, **kwargs):
        remaining = COLLECTION_BUDGET_SECONDS - (clock() - started)
        if remaining <= 0:
            raise TimeoutError("COLLECTION_DEADLINE")
        kwargs["timeout"] = tuple(min(t, remaining) for t in kwargs["timeout"])
        response = get(url, **kwargs)
        if clock() - started >= COLLECTION_BUDGET_SECONDS:
            raise TimeoutError("COLLECTION_DEADLINE")
        return response

    activity = collect_premarket(headers, session_date, phase=phase, now=now,
                                get=bounded_get, clock=clock)
    universe = activity["collection"]["universe_symbols"]
    result = {"schema": SCHEMA, "experiment_class": "INFRASTRUCTURE_TEST",
              "strategy_eligible": False, "broker_execution_enabled": False,
              "full_discovery_accepted": False, "items": activity["items"],
              "collection": activity["collection"], "universe_items": {},
              "prior_evidence": None}
    # In particular, never use the daily adapter to bypass the premarket window.
    if not universe:
        result["integration"] = {"outcome": "UNIVERSE_UNAVAILABLE", "collection_complete": False,
                                 "all_prior_closes_available": False, "universe_count": 0}
        return result
    envelope = dated_prior_evidence(headers, universe, session_date,
        now=now + timedelta(seconds=max(0, clock()-started)), get=bounded_get, clock=clock)
    prior = envelope["previous_close"]
    same_session = (prior.get("session_date") == session_date.isoformat()
                    and prior.get("prior_session") == activity["collection"].get("previous_session_date"))
    if not same_session:
        # Keep the conflicting calendar date as diagnostic metadata, but never
        # attach a close obtained for a different session to activity evidence.
        prior["rejected_calendar_prior_session"] = prior.get("prior_session")
        prior["outcome"] = "CALENDAR_UNAVAILABLE_OR_DISAGREEMENT"
        prior["items"] = {s: {"status": "UNAVAILABLE", "reason": "CALENDAR_UNAVAILABLE_OR_DISAGREEMENT"}
                          for s in universe}
        prior["completed_symbols"], prior["unprocessed_symbols"] = [], list(universe)
        envelope["evidence_hash"] = digest(prior)
    result["prior_evidence"] = envelope
    result["items"] = attach_prior_evidence(activity["items"], envelope)
    attachments = attach_prior_evidence({s: {} for s in universe}, envelope)
    no_bars = set(activity["collection"]["no_bars_symbols"])
    for symbol in universe:
        item = result["items"].get(symbol)
        result["universe_items"][symbol] = {
            "schema": SCHEMA, "record_kind": "UNIVERSE_COVERAGE",
            "experiment_class": "INFRASTRUCTURE_TEST", "strategy_eligible": False,
            "session_date": session_date.isoformat(), "symbol": symbol,
            "premarket_status": (item["bar_collection_status"] if item else
                                 "NO_BARS" if symbol in no_bars else "UNPROCESSED"),
            "premarket_activity": deepcopy(item),
            "dated_prior_session_evidence": attachments[symbol]["dated_prior_session_evidence"]}
    complete = (activity["collection"]["outcome"] == "FEED_EXHAUSTED"
                and not activity["collection"]["unprocessed_symbols"] and same_session
                and prior["outcome"] == "COLLECTION_COMPLETE_REVIEW_REQUIRED"
                and not prior["unprocessed_symbols"])
    available = sum(row.get("status") == "RAW_DAILY_CLOSE_REVIEW_REQUIRED"
                    for row in prior["items"].values())
    result["integration"] = {
        "outcome": "COLLECTION_COMPLETE_REVIEW_REQUIRED" if complete else "PARTIAL",
        "collection_complete": complete, "all_prior_closes_available": available == len(universe),
        "calendar_sessions_agree": same_session, "universe_count": len(universe),
        "activity_count": len(result["items"]), "coverage_only_count": len(universe)-len(result["items"]),
        "dated_prior_close_count": available,
        "prior_unavailable_reasons": dict(sorted(Counter(
            row.get("reason", "UNAVAILABLE") for row in prior["items"].values()
            if row.get("status") == "UNAVAILABLE").items())),
        "shared_budget_seconds": COLLECTION_BUDGET_SECONDS,
        "elapsed_seconds": max(0, clock()-started), "snapshot_fields_unchanged": True,
        "strategy_eligible": False, "full_discovery_accepted": False}
    # Compact manifest can go into run notes; the complete per-symbol evidence
    # belongs in the bounded item store, not repeated in each activity record.
    result["collection"]["dated_prior_session_collection"] = {
        **deepcopy(result["integration"]), "evidence_hash": envelope["evidence_hash"],
        "prior_session": prior.get("prior_session"),
        "provenance": {key: prior.get(key) for key in (
            "source", "calendar_source", "feed", "adjustment", "timeframe", "asof",
            "session_date", "requested_at", "requested_start", "requested_end", "pages_received")},
        "completed_symbols": list(prior["completed_symbols"]),
        "unprocessed_symbols": list(prior["unprocessed_symbols"])}
    return result
