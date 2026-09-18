"""Human-readable process evidence. Supabase remains the only signal store."""
from datetime import datetime, timezone

from fastapi import HTTPException

JOURNAL_SPREADSHEET_ID = "1C4BAHQBzgU2hC64yIAHfQkwjSIuPm3pc7i-AIKrbk4w"
ENTRY_LABELS = {
    "opening_range_premarket_high_break": "Opening-range / premarket high break",
    "vwap_reclaim_rejection": "VWAP reclaim / rejection",
    "first_clean_pullback": "First clean pullback",
}
CHANNELS = {
    "earnings_guidance": "Earnings / Guidance", "corporate_news": "Corporate News",
    "analyst_actions": "Analyst Actions", "sector_industry": "Sector / Industry",
    "premarket_movers_unusual_activity": "Premarket Movers / Unusual Activity", "macro_economic_calendar": "Macro / Economic Calendar",
    "cross_source_verification": "Cross-Source Verification",
}


def candidate_projection(c, signal=None):
    if c.get("experiment_class") != "STRATEGY_1" or c.get("data_kind") != "MARKET":
        raise HTTPException(status_code=409, detail="Only explicitly classified market observations enter the strategy Journal.")
    decision = ""
    if signal:
        inputs = signal.get("decision_inputs") or {}
        if (str(signal["id"]) != str(c.get("last_signal_id"))
                or not c.get("journal_trade_id") or not signal.get("worker_version")
                or signal.get("experiment_class") != "STRATEGY_1"
                or inputs.get("data_kind") != "MARKET"
                or str(inputs.get("candidate_id")) != str(c["id"])
                or signal.get("journal_trade_id") != c.get("journal_trade_id")
                or signal["symbol"] != c["symbol"] or signal["ruleset_version"] != c["ruleset_version"]
                or signal["decision"] != c.get("last_worker_decision")
                or str(inputs.get("run_id")) != str(c.get("run_id"))):
            raise HTTPException(status_code=409, detail="Candidate/signal trace mismatch; no journal write.")
        decision = signal["decision"].replace("_", " ")
    state = c.get("operational_state") or "HOLD_UNRESOLVED"
    # An evaluation in progress must not overwrite a prior completed decision with stale output.
    if c.get("reason_code") == "EVALUATION_PENDING":
        signal, decision = None, ""
    return {"sheet_name": "Premarket Candidates", "key_column": "Candidate ID", "key": str(c["id"]), "values": {
        "Date": str(c["session_date"]), "Discovery Phase": "Premarket" if c["discovery_phase"] == "PREMARKET" else "Post-Open Refresh",
        "Ticker": c["symbol"], "Catalyst Summary": c.get("catalyst_summary") or "",
        "Catalyst Tier": c.get("catalyst_tier") or "", "Ruleset Version": c["ruleset_version"],
        "Planned Entry Model": ENTRY_LABELS.get(c.get("entry_model"), "TBD / None"),
        "Trigger / Level": c.get("trigger_definition") or "", "Candidate ID": str(c["id"]),
        "Operational State": state, "Setup Status": "HOLD_UNRESOLVED" if state == "HOLD_UNRESOLVED" else "WORKER_READY",
        "Worker Decision": decision, "Final Decision": decision if state != "HOLD_UNRESOLVED" else "",
        "Wait / Block Reason": c.get("reason_code") or "REVIEW_REQUIRED",
        "Signal ID": str(signal["id"]) if signal else "", "Notes": c.get("notes") or "",
    }, "trace": {"run_id": str(c.get("run_id")) if c.get("run_id") else None,
                 "candidate_id": str(c["id"]), "signal_id": str(signal["id"]) if signal else None,
                 "journal_trade_id": c.get("journal_trade_id")}}


def discovery_projection(item, run):
    review = item.get("qualification_review") or {}
    setup = item.get("setup_review") or {}
    state = item.get("operational_state") or item.get("promotion_status") or "REVIEW_REQUIRED"
    key = str(item.get("orchestrator_candidate_id") or item["id"])
    return {"sheet_name": "Premarket Candidates", "key_column": "Candidate ID", "key": key, "values": {
        "Date": str(run["session_date"]), "Discovery Phase": "Premarket" if run["phase"] == "PREMARKET" else "Post-Open Refresh",
        "Ticker": item["symbol"], "Discovery Channel": ", ".join(item.get("discovered_via") or []),
        "Catalyst Summary": review.get("catalyst_summary") or "Review required; raw evidence retained in Supabase",
        "Primary Source / Verification": "; ".join(s["source"] for s in review.get("catalyst_sources", [])),
        "Catalyst Tier": review.get("catalyst_tier") or "", "Ruleset Version": run["ruleset_version"],
        "Planned Entry Model": ENTRY_LABELS.get(setup.get("entry_model"), "TBD / None"),
        "Trigger / Level": setup.get("trigger_definition") or "", "Candidate ID": key,
        "Operational State": state, "Setup Status": "SETUP_REQUIRED" if not setup else state,
        "Worker Decision": "", "Final Decision": "NO TRADE" if state == "REJECTED" else "",
        "Wait / Block Reason": item.get("rejection_reason") or state, "Signal ID": "",
        "Rejection Reason": item.get("rejection_reason") or "", "Notes": item.get("notes") or "",
    }, "trace": {"run_id": str(run["id"]), "candidate_id": key, "signal_id": None, "journal_trade_id": None}}


def run_projection(run):
    phase_labels = {"PREMARKET": "Premarket", "POST_OPEN": "Post-Open Refresh"}
    phase = run.get("phase")
    if phase not in phase_labels:
        raise HTTPException(status_code=409, detail="Discovery phase missing or invalid; no journal write.")
    try:
        started = run.get("created_at")
        if isinstance(started, str):
            started = datetime.fromisoformat(started.replace("Z", "+00:00"))
        if not isinstance(started, datetime) or started.utcoffset() is None:
            raise ValueError("A timezone-aware source timestamp is required.")
        scan_time = started.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError, OverflowError) as exc:
        raise HTTPException(status_code=409, detail="Scan start timestamp missing or ambiguous; no journal write.") from exc
    # created_at is the collection start, never the preview/retry time or updated_at.
    context = f"Discovery phase: {phase} ({phase_labels[phase]}). Scan started at: {scan_time}."
    values = {"Date": str(run["session_date"]), "Run ID": str(run["id"]),
              "Scan Time": scan_time,
              "Ruleset Version": run["ruleset_version"], "Candidates Discovered": run.get("candidates_discovered") or 0,
              "Scan Status": {"COMPLETE": "Complete", "PARTIAL": "Partial", "DATA_UNAVAILABLE": "Data Unavailable"}.get(run["status"], "Partial"),
              "Notes": context + (" " + run["notes"] if run.get("notes") else "")}
    for key, header in CHANNELS.items():
        status = (run.get("channel_status") or {}).get(key)
        values[header] = "Checked" if status in {
            "CHECKED_FRED_RELEASE_CALENDAR", "CHECKED_ALPACA_SCREENER", "CHECKED_ALPACA_NEWS", "Checked"
        } else "Unavailable"
    return {"sheet_name": "Scan Coverage", "key_column": "Run ID", "key": str(run["id"]), "values": values,
            "trace": {"run_id": str(run["id"]), "phase": phase, "scan_started_at": scan_time,
                      "channel_status": run.get("channel_status") or {}}}


def project_run(run, items, candidates, signals):
    if run.get("experiment_class") != "STRATEGY_1":
        raise HTTPException(status_code=409, detail="Infrastructure or unclassified runs cannot enter the strategy Journal.")
    by_item = {str(c["source_discovery_item_id"]): c for c in candidates if c.get("source_discovery_item_id")}
    if len(by_item) != len(candidates):
        raise HTTPException(status_code=409, detail="Missing or duplicate discovery links.")
    by_signal = {str(s["id"]): s for s in signals}
    rows = [run_projection(run)]
    for item in items:
        c = by_item.get(str(item["id"]))
        if str(item["run_id"]) != str(run["id"]):
            raise HTTPException(status_code=409, detail="Run/item mismatch.")
        if c:
            if str(c.get("run_id")) != str(run["id"]) or c["symbol"] != item["symbol"]:
                raise HTTPException(status_code=409, detail="Run/candidate mismatch.")
            signal = by_signal.get(str(c.get("last_signal_id")))
            if c.get("last_signal_id") and not signal:
                raise HTTPException(status_code=409, detail="Signal missing.")
            row = candidate_projection(c, signal)
        else:
            if item.get("orchestrator_candidate_id"):
                raise HTTPException(status_code=409, detail="Linked candidate missing.")
            row = discovery_projection(item, run)
        rows.append(row)
    if len(by_item) != sum(1 for item in items if str(item["id"]) in by_item):
        raise HTTPException(status_code=409, detail="Candidate is outside the discovery funnel.")
    return rows
