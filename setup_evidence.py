"""Pure measurement packet for a future accepted review method.

No network, persistence, CurrentReview creation or signal/execution interface.
All qualitative judgments stay unresolved, including when measurements exist.
"""
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json

from premarket_collection import MARKET_TZ, stamp
from review_contract import CURRENT_FIELDS

ENTRY_MODELS = {"opening_range_premarket_high_break", "vwap_reclaim_rejection", "first_clean_pullback"}
AUTHORITY = {"rules": "v0.3", "experiment": "v0.5", "automation": "v0.4"}
PLAN_TEXT = ("candidate_id", "symbol", "direction", "session_date", "entry_model",
             "recorded_at", "trigger_definition", "structural_rationale", "stop_rationale",
             "target_rationale", "invalidation_conditions", "source_ref")
PLAN_PRICES = ("trigger_price", "entry_price", "stop_price", "target_price")

# Describes missing evidence, not new strategy rules or approval thresholds.
REVIEW_INPUTS = {
    "market_regime": "Current index/sector conditions and attributable regime assessment",
    "market_context_ok": "Current index/sector evidence and assessment against the Rules",
    "data_quality_ok": "Source identity, SIP provenance, delay, completeness and timestamp checks",
    "consolidated_data_required": "Applicable Rules requirement for each measurement",
    "liquidity_ok": "Current SIP spread/depth and observed executable liquidity; approved assessment",
    "participation_ok": "Complete current volume window and valid comparison baseline",
    "relative_strength_ok": "Aligned symbol/index/sector series and approved assessment",
    "after_first_minute": "Exchange calendar open and prospective observation timestamp",
    "price_extended_or_chasing": "Predeclared structure and current price path; approved assessment",
    "major_macro_event_imminent": "Verified current economic calendar and event timing assessment",
    "missed_trigger": "Predeclared trigger and complete prospective observation history",
    "stop_would_widen": "Original stop, current proposed stop and durable change history",
    "fomo_or_revenge_motive": "Applicable accountable review; cannot infer motive from market bars",
    "target_validated": "Source-backed structural target and current reward/risk assessment",
    "realized_daily_loss_dollars": "Reconciled account fills and session realized-loss ledger",
    "executed_trades_today": "Reconciled unique executed trades for the session",
    "data_current": "Accepted freshness policy and current measurement provenance",
    "catalyst_current": "Verified source documents, event timing and current catalyst review",
    "qualification_current": "Complete discovery coverage, qualification and retained rejections",
    "risk_current": "Current account limits, exposures and structural risk assessment",
    "setup_current": "Approved model, hold/retest/structure evidence and prospective confirmation",
}
assert set(CURRENT_FIELDS) <= set(REVIEW_INPUTS)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def price(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError()
    try:
        parsed = Decimal(str(value))
        if not parsed.is_finite() or parsed <= 0:
            raise ValueError()
        return parsed
    except InvalidOperation:
        raise ValueError() from None


def build_setup_evidence(plan, observations, *, as_of, previous_packet=None):
    """Project supplied evidence. Never choose levels, confirmations or trades.

    Source references are caller claims, not independently verified by this pure
    function. A nonexpired declared validity interval is not freshness approval.
    Synthetic fixtures remain infrastructure evidence; no packet is eligible to
    become a Strategy #1 observation without the separate governing workflow.
    """
    packet = {"schema": "setup-evidence/v1", "status": "UNAVAILABLE", "problems": [],
              "experiment_class": "INFRASTRUCTURE_TEST",
              "authority": dict(AUTHORITY), "strategy_eligible": False,
              "broker_execution_enabled": False, "automatic_confirmation": False,
              "review_binding_reusable": False, "measurements": {}, "evidence": [],
              "supporting_evidence": [],
              "unresolved_reviews": {k: {"status": "UNRESOLVED", "required_evidence": v}
                                     for k, v in REVIEW_INPUTS.items()}}
    problems = packet["problems"]
    try:
        checked = stamp(as_of)
        session = date.fromisoformat(plan["session_date"])
        recorded = stamp(plan["recorded_at"])
        if (checked.astimezone(MARKET_TZ).date() != session
                or recorded.astimezone(MARKET_TZ).date() != session or recorded > checked
                or plan["direction"] != "LONG" or plan["entry_model"] not in ENTRY_MODELS
                or plan.get("authority") != AUTHORITY):
            raise ValueError()
        projected = {k: plan[k] for k in PLAN_TEXT}
        if any(not isinstance(v, str) or not v.strip() for v in projected.values()):
            raise ValueError()
        prices = {k: price(plan[k]) for k in PLAN_PRICES}
        projected.update({k: str(v) for k, v in prices.items()})
        projected["authority"] = dict(AUTHORITY)
        packet.update(as_of=checked.isoformat(), plan=projected, plan_hash=digest(projected))
        if previous_packet is not None:
            packet["plan_changed"] = previous_packet.get("plan_hash") != packet["plan_hash"]
            if packet["plan_changed"]:
                problems.append("PLAN_CHANGED_REVIEW_REQUIRED")
        if not prices["stop_price"] < prices["entry_price"] < prices["target_price"]:
            problems.append("INVALID_LONG_RISK_GEOMETRY")
        else:
            risk = prices["entry_price"] - prices["stop_price"]
            packet["measurements"].update(risk_per_share=str(risk),
                reward_per_share=str(prices["target_price"] - prices["entry_price"]),
                reward_risk=str((prices["target_price"] - prices["entry_price"]) / risk))
        if not isinstance(observations, dict):
            raise ValueError()
    except (ValueError, TypeError, KeyError, AttributeError):
        problems.append("INVALID_PLAN_OR_CHECK_TIME")
        return packet

    def provenance(item):
        at, received = stamp(item["at"]), stamp(item["received_at"])
        if (at.astimezone(MARKET_TZ).date() != session or not recorded <= at <= received <= checked
                or item["symbol"] != projected["symbol"] or item["feed"] != "sip"
                or item.get("delayed") is not False
                or not isinstance(item.get("source_ref"), str) or not item["source_ref"].strip()):
            raise ValueError()
        if item.get("valid_until") is not None:
            expiry = stamp(item["valid_until"])
            if (not isinstance(item.get("validity_policy_ref"), str)
                    or not item["validity_policy_ref"].strip() or expiry <= checked):
                raise ValueError()
        return {"at": at.isoformat(), "received_at": received.isoformat(),
                "symbol": item["symbol"], "feed": "sip", "delayed": False,
                "source_ref": item["source_ref"], "age_seconds": (checked-at).total_seconds(),
                "declared_valid_until": item.get("valid_until"),
                "declared_validity_policy": item.get("validity_policy_ref"),
                "freshness_approved": False, "source_independently_verified": False}

    quote = observations.get("quote")
    try:
        evidence = provenance(quote)
        bid, ask = price(quote["bid"]), price(quote["ask"])
        if ask < bid:
            raise ValueError()
        packet["measurements"]["quote"] = {"bid": str(bid), "ask": str(ask),
            "spread": str(ask-bid), "spread_fraction_of_midpoint": str((ask-bid)/((ask+bid)/2))}
        packet["evidence"].append({"kind": "quote", **evidence})
    except (ValueError, TypeError, KeyError, AttributeError):
        problems.append("QUOTE_MISSING_INVALID_EXPIRED_OR_NONPROSPECTIVE")

    try:
        bars = observations.get("bars")
        if not isinstance(bars, list) or not bars or len(bars) > 2000:
            raise ValueError()
        verified, previous_end = [], None
        for bar in bars:
            evidence = provenance(bar)
            at, end = stamp(bar["at"]), stamp(bar["end_at"])
            if (not at < end <= stamp(bar["received_at"]) <= checked
                    or (previous_end is not None and at < previous_end)):
                raise ValueError()
            previous_end = end
            values = {k: price(bar[k]) for k in ("o", "h", "l", "c")}
            vol = bar["v"]
            if (type(vol) is not int or vol < 0 or values["l"] > min(values["o"], values["c"])
                    or values["h"] < max(values["o"], values["c"]) or values["h"] < values["l"]):
                raise ValueError()
            verified.append({"kind": "bar", **evidence, "end_at": end.isoformat(),
                             **{k: str(v) for k, v in values.items()}, "v": vol})
        packet["measurements"]["observed_bars"] = {
            "count": len(verified), "volume": sum(b["v"] for b in verified),
            "high": str(max(Decimal(b["h"]) for b in verified)),
            "low": str(min(Decimal(b["l"]) for b in verified)),
            "last_close": verified[-1]["c"],
            "last_close_at_or_above_trigger": Decimal(verified[-1]["c"]) >= prices["trigger_price"],
            "complete_window_verified": False, "participation_approved": False,
            "trigger_confirmed": False}
        packet["evidence"].extend(verified)
    except (ValueError, TypeError, KeyError, AttributeError):
        problems.append("BARS_MISSING_INVALID_EXPIRED_OR_NONPROSPECTIVE")

    # Preserve source-backed context separately from prospective market samples.
    # Older documents can explain structure/catalysts, but cannot prove currentness.
    try:
        supplied = observations.get("supporting_evidence", [])
        if not isinstance(supplied, list) or len(supplied) > 100:
            raise ValueError()
        supporting = []
        for item in supplied:
            available, received = stamp(item["available_at"]), stamp(item["received_at"])
            if not available <= received <= checked:
                raise ValueError()
            fields = item["review_fields"]
            if (not isinstance(fields, list) or not fields or len(set(fields)) != len(fields)
                    or any(f not in REVIEW_INPUTS for f in fields)
                    or any(not isinstance(item.get(k), str) or not item[k].strip()
                           for k in ("source_ref", "summary"))):
                raise ValueError()
            supporting.append({"review_fields": list(fields), "source_ref": item["source_ref"],
                "summary": item["summary"], "available_at": available.isoformat(),
                "received_at": received.isoformat(), "age_seconds": (checked-available).total_seconds(),
                "status": "UNREVIEWED_SOURCE_CLAIM", "source_independently_verified": False})
        packet["supporting_evidence"] = supporting
    except (ValueError, TypeError, KeyError, AttributeError):
        problems.append("INVALID_SUPPORTING_SOURCE_EVIDENCE")
    # No observation or source claim can set a CurrentReview flag to true.
    packet["status"] = "EVIDENCE_INCOMPLETE" if problems else "NEEDS_CURRENT_REVIEW"
    packet["packet_hash"] = digest(packet)
    return packet
