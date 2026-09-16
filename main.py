import hmac
import os
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_DOWN
from typing import Any, Literal

import requests
from fastapi import FastAPI, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, model_validator
from review_contract import CurrentReview, review_problem, evidence_class_problem
from build_info import implementation_version

APP_VERSION = "0.2.0-shadow"
STRATEGY_ID = "STRATEGY_1"
RULESET_VERSION = os.getenv("RULESET_VERSION", "v0.3")
WORKER_VERSION = implementation_version("main", APP_VERSION)

MAX_DOLLAR_RISK = Decimal(os.getenv("MAX_DOLLAR_RISK", "50"))
MAX_DAILY_LOSS_DOLLARS = Decimal(os.getenv("MAX_DAILY_LOSS_DOLLARS", "100"))
MAX_TRADES_PER_DAY = int(os.getenv("MAX_TRADES_PER_DAY", "3"))
MAX_NOTIONAL = Decimal(os.getenv("MAX_NOTIONAL", "10000"))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")
WORKER_TOKEN = os.getenv("WORKER_TOKEN")

APPROVED_ENTRY_MODELS = {
    "opening_range_premarket_high_break",
    "vwap_reclaim_rejection",
    "first_clean_pullback",
}

app = FastAPI(
    title="Strategy #1 Shadow Worker",
    version=APP_VERSION,
    description=(
        "Deterministic Strategy #1 v0.3 shadow evaluator. "
        "Records TRADE / WAIT / NO_TRADE decisions to Supabase. "
        "This service does not submit broker orders."
    ),
)

bearer_scheme = HTTPBearer(auto_error=False)


class CatalystSource(BaseModel):
    source: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    headline_or_event: str = Field(min_length=1)
    event_timestamp: datetime


class Candidate(BaseModel):
    session_date: date | None = None
    current_review: CurrentReview | None = None
    confirmation_review_id: str | None = None
    data_kind: Literal["MARKET", "SYNTHETIC"]
    run_id: str | None = None
    candidate_id: str = Field(min_length=1)
    source_discovery_item_id: str | None = None
    symbol: str = Field(min_length=1, max_length=12)
    direction: Literal["LONG", "SHORT"]
    journal_trade_id: str | None = None
    evaluated_at: datetime | None = None
    market_data_source: str = Field(min_length=1)
    data_timestamp: datetime | None = None
    data_quality_ok: bool | None = None
    consolidated_data: bool | None = None
    consolidated_data_required: bool | None = None

    experiment_class: Literal["STRATEGY_1", "INFRASTRUCTURE_TEST"]
    ruleset_version: str = "v0.3"
    market_regime: Literal["Bullish", "Bearish", "Mixed", "Choppy"] | None = None

    market_context_ok: bool | None = None
    liquidity_ok: bool | None = None
    participation_ok: bool | None = None
    price_extended_or_chasing: bool | None = None
    major_macro_event_imminent: bool | None = None
    clean_structure: bool | None = None
    target_validated: bool | None = None
    stop_would_widen: bool | None = None
    fomo_or_revenge_motive: bool | None = None

    catalyst_summary: str | None = None
    catalyst_tier: Literal["A", "B", "C"] | None = None
    catalyst_event_at: datetime | None = None
    catalyst_material: bool | None = None
    materiality_rationale: str | None = None
    catalyst_verified: bool | None = None
    catalyst_cross_source_verified: bool | None = None
    catalyst_sources: list[CatalystSource] = Field(default_factory=list)

    relative_strength_ok: bool | None = None
    rvol: Decimal | None = None
    rvol_consolidated: bool | None = None

    entry_model: str | None = None
    trigger_definition: str | None = None
    trigger_price: Decimal | None = None
    trigger_confirmed: bool = False
    triggered_at: datetime | None = None
    missed_trigger: bool | None = None
    after_first_minute: bool | None = None

    entry_price: Decimal | None = None
    stop_price: Decimal | None = None
    target_price: Decimal | None = None

    realized_daily_loss_dollars: Decimal | None = None
    executed_trades_today: int | None = None

    decision_inputs: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None

    @model_validator(mode="after")
    def normalize_symbol(self):
        self.symbol = self.symbol.upper().strip()
        return self


class Decision(BaseModel):
    decision: Literal["TRADE", "WAIT", "NO_TRADE"]
    operational_state: Literal["HOLD_UNRESOLVED", "WAITING_FOR_TRIGGER", "TRADE_READY", "REJECTED"]
    reason_code: str
    reasons: list[str]
    qty: int | None = None
    risk_per_share: Decimal | None = None
    planned_rr: Decimal | None = None
    dollar_risk: Decimal | None = None
    notional: Decimal | None = None
    supabase_record_id: str | None = None


def require_auth(credentials: HTTPAuthorizationCredentials | None):
    if not WORKER_TOKEN:
        raise HTTPException(status_code=503, detail="WORKER_TOKEN is not configured.")
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing bearer token.")
    if credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authentication scheme.")
    if not hmac.compare_digest(credentials.credentials, WORKER_TOKEN):
        raise HTTPException(status_code=403, detail="Invalid bearer token.")


def calc_geometry(c: Candidate):
    if c.entry_price is None or c.stop_price is None or c.target_price is None:
        return None

    if c.direction == "LONG":
        risk = c.entry_price - c.stop_price
        reward = c.target_price - c.entry_price
    else:
        risk = c.stop_price - c.entry_price
        reward = c.entry_price - c.target_price

    if risk <= 0 or reward <= 0:
        return "INVALID"

    return risk, reward, reward / risk


def size_position(entry: Decimal, risk_per_share: Decimal):
    if risk_per_share <= 0 or entry <= 0:
        return None

    risk_qty = int((MAX_DOLLAR_RISK / risk_per_share).to_integral_value(rounding=ROUND_DOWN))
    notional_qty = int((MAX_NOTIONAL / entry).to_integral_value(rounding=ROUND_DOWN))
    qty = min(risk_qty, notional_qty)

    if qty <= 0:
        return None

    return qty, risk_per_share * qty, entry * qty


def evaluate(c: Candidate) -> Decision:
    if c.experiment_class != "STRATEGY_1":
        return Decision(decision="NO_TRADE", operational_state="REJECTED", reason_code="INFRASTRUCTURE_TEST", reasons=["Infrastructure tests are not Strategy #1 decisions."])
    if c.ruleset_version != RULESET_VERSION:
        return Decision(
            decision="NO_TRADE", operational_state="REJECTED", reason_code="RULESET_MISMATCH",
            reasons=[f"Ruleset mismatch: input={c.ruleset_version}, worker={RULESET_VERSION}."],
        )

    evidence_error = evidence_class_problem(c.experiment_class, c.data_kind, c.market_data_source, c.notes)
    if evidence_error:
        return Decision(decision="NO_TRADE", operational_state="REJECTED", reason_code=evidence_error,
                        reasons=["Test evidence must be explicitly classified as infrastructure evidence."])

    if c.catalyst_tier is None or c.catalyst_summary is None:
        return Decision(decision="NO_TRADE", operational_state="REJECTED", reason_code="NO_CATALYST", reasons=["No identifiable catalyst."])
    if c.catalyst_tier == "C":
        return Decision(decision="NO_TRADE", operational_state="REJECTED", reason_code="CATALYST_TIER_C", reasons=["Tier C catalyst is insufficient for Strategy #1."])
    if c.catalyst_material is False:
        return Decision(decision="NO_TRADE", operational_state="REJECTED", reason_code="CATALYST_NON_MATERIAL", reasons=["Catalyst is explicitly non-material."])
    if c.stop_would_widen is True:
        return Decision(decision="NO_TRADE", operational_state="REJECTED", reason_code="STOP_WIDENING", reasons=["Trade would require widening the structural stop."])
    if c.fomo_or_revenge_motive is True:
        return Decision(decision="NO_TRADE", operational_state="REJECTED", reason_code="FOMO_REVENGE", reasons=["Entry motive is FOMO/revenge rather than the predefined setup."])
    if c.missed_trigger is True:
        return Decision(decision="NO_TRADE", operational_state="REJECTED", reason_code="MISSED_TRIGGER", reasons=["Planned trigger was missed; chasing is prohibited."])
    if c.price_extended_or_chasing is True:
        return Decision(decision="NO_TRADE", operational_state="REJECTED", reason_code="PRICE_EXTENDED_OR_CHASING", reasons=["Price is extended / entry would require chasing."])
    if c.major_macro_event_imminent is True:
        return Decision(decision="NO_TRADE", operational_state="REJECTED", reason_code="MACRO_EVENT_IMMINENT", reasons=["Major scheduled macro event is imminent."])
    if c.realized_daily_loss_dollars is not None and c.realized_daily_loss_dollars >= MAX_DAILY_LOSS_DOLLARS:
        return Decision(decision="NO_TRADE", operational_state="REJECTED", reason_code="DAILY_LOSS_LIMIT", reasons=["Daily loss limit has been reached."])
    if c.executed_trades_today is not None and c.executed_trades_today >= MAX_TRADES_PER_DAY:
        return Decision(decision="NO_TRADE", operational_state="REJECTED", reason_code="DAILY_TRADE_LIMIT", reasons=["Maximum executed trades per day has been reached."])

    geometry = calc_geometry(c)
    if geometry == "INVALID":
        return Decision(decision="NO_TRADE", operational_state="REJECTED", reason_code="INVALID_GEOMETRY", reasons=["Entry/stop/target geometry is invalid for the direction."])

    risk_per_share = planned_rr = None
    if geometry is not None:
        risk_per_share, _reward, planned_rr = geometry
        if planned_rr < Decimal("1.5"):
            return Decision(
                decision="NO_TRADE", operational_state="REJECTED", reason_code="RR_BELOW_MINIMUM",
                reasons=[f"Planned reward/risk {planned_rr:.3f}R is below the 1.5R minimum."],
                risk_per_share=risk_per_share,
                planned_rr=planned_rr,
            )

    if c.liquidity_ok is False:
        return Decision(decision="NO_TRADE", operational_state="REJECTED", reason_code="LIQUIDITY_FAILED",
                        reasons=["Liquidity / execution quality is unacceptable."])
    if c.target_validated is not True:
        return Decision(decision="WAIT", operational_state="HOLD_UNRESOLVED", reason_code="TARGET_NOT_VALIDATED",
                        reasons=["Structural target approval is required before waiting or confirming."])
    review_error = review_problem(c)
    if review_error:
        return Decision(decision="WAIT", operational_state="HOLD_UNRESOLVED", reason_code=review_error,
                        reasons=["A current attributable review of data, catalyst, qualification, setup and risk is required."])

    unresolved = {
        "market regime": c.market_regime,
        "market context": c.market_context_ok,
        "data quality": c.data_quality_ok,
        "whether consolidated data is required": c.consolidated_data_required,
        "liquidity/execution quality": c.liquidity_ok,
        "participation": c.participation_ok,
        "catalyst materiality": c.catalyst_material,
        "catalyst verification": c.catalyst_verified,
        "cross-source catalyst verification": c.catalyst_cross_source_verified,
        "relative strength/weakness": c.relative_strength_ok,
        "first-minute restriction": c.after_first_minute,
        "extended/chasing assessment": c.price_extended_or_chasing,
        "macro-event assessment": c.major_macro_event_imminent,
        "missed-trigger assessment": c.missed_trigger,
        "stop-widening assessment": c.stop_would_widen,
        "FOMO/revenge assessment": c.fomo_or_revenge_motive,
        "target validation": c.target_validated,
        "daily realized loss state": c.realized_daily_loss_dollars,
        "executed-trades-today state": c.executed_trades_today,
    }
    missing = [name for name, value in unresolved.items() if value is None]
    if missing:
        return Decision(decision="WAIT", operational_state="HOLD_UNRESOLVED", reason_code="STRUCTURED_INPUTS_UNRESOLVED", reasons=["Required structured inputs unresolved: " + ", ".join(missing) + "."])

    if c.market_context_ok is False:
        return Decision(decision="WAIT", operational_state="HOLD_UNRESOLVED", reason_code="MARKET_CONTEXT_NOT_APPROVED", reasons=["Market context is currently hostile / not approved."])
    if c.data_quality_ok is False:
        return Decision(decision="WAIT", operational_state="HOLD_UNRESOLVED", reason_code="DATA_QUALITY_FAILED", reasons=["Required market data is stale, contradictory, or unreliable."])
    if c.consolidated_data_required is True and c.consolidated_data is not True:
        return Decision(decision="WAIT", operational_state="HOLD_UNRESOLVED", reason_code="CONSOLIDATED_DATA_UNAVAILABLE", reasons=["Required consolidated market data is unavailable."])
    if c.liquidity_ok is False:
        return Decision(decision="NO_TRADE", operational_state="REJECTED", reason_code="LIQUIDITY_FAILED", reasons=["Liquidity / execution quality is unacceptable."])
    if c.participation_ok is False:
        return Decision(decision="WAIT", operational_state="HOLD_UNRESOLVED", reason_code="PARTICIPATION_NOT_CONFIRMED", reasons=["Required participation is not confirmed."])
    if c.relative_strength_ok is False:
        return Decision(decision="WAIT", operational_state="HOLD_UNRESOLVED", reason_code="RELATIVE_STRENGTH_NOT_CONFIRMED", reasons=["Required relative strength/weakness is not confirmed."])
    if c.catalyst_verified is False or c.catalyst_cross_source_verified is False:
        return Decision(decision="WAIT", operational_state="HOLD_UNRESOLVED", reason_code="CATALYST_VERIFICATION_INCOMPLETE", reasons=["Catalyst verification is incomplete."])
    if not c.materiality_rationale:
        return Decision(decision="WAIT", operational_state="HOLD_UNRESOLVED", reason_code="MATERIALITY_RATIONALE_MISSING", reasons=["Catalyst materiality rationale is missing."])
    if len(c.catalyst_sources) < 2:
        return Decision(decision="WAIT", operational_state="HOLD_UNRESOLVED", reason_code="CATALYST_EVIDENCE_INCOMPLETE", reasons=["Cross-source catalyst evidence is incomplete."])
    if c.after_first_minute is False:
        return Decision(decision="WAIT", operational_state="HOLD_UNRESOLVED", reason_code="FIRST_MINUTE_RESTRICTION", reasons=["Strategy #1 cannot trade during the first minute after the open."])

    if c.entry_model not in APPROVED_ENTRY_MODELS:
        return Decision(decision="WAIT", operational_state="HOLD_UNRESOLVED", reason_code="ENTRY_MODEL_MISSING_OR_UNAPPROVED", reasons=["Approved entry model is not yet specified."])
    if not c.trigger_definition:
        return Decision(decision="WAIT", operational_state="HOLD_UNRESOLVED", reason_code="TRIGGER_DEFINITION_MISSING", reasons=["Predefined trigger is not specified."])
    if c.trigger_price is None:
        return Decision(decision="WAIT", operational_state="HOLD_UNRESOLVED", reason_code="TRIGGER_PRICE_MISSING", reasons=["Predefined trigger price is not specified."])
    if c.data_timestamp is None:
        return Decision(decision="WAIT", operational_state="HOLD_UNRESOLVED", reason_code="DATA_TIMESTAMP_MISSING", reasons=["Fresh market-data timestamp is missing."])
    if c.entry_price is None or c.stop_price is None or c.target_price is None:
        return Decision(decision="WAIT", operational_state="HOLD_UNRESOLVED", reason_code="SETUP_GEOMETRY_MISSING", reasons=["Entry, structural stop, and target must be predefined."])
    if geometry is None:
        return Decision(decision="WAIT", operational_state="HOLD_UNRESOLVED", reason_code="GEOMETRY_INCOMPLETE", reasons=["Trade geometry is incomplete."])

    risk_per_share, _reward, planned_rr = geometry

    if Decimal("1.5") <= planned_rr < Decimal("2.0"):
        if c.clean_structure is None:
            return Decision(
                decision="WAIT", operational_state="HOLD_UNRESOLVED", reason_code="CLEAN_STRUCTURE_UNRESOLVED",
                reasons=["1.5R-2.0R setup requires explicit clean_structure input; criterion is not inferred."],
                risk_per_share=risk_per_share,
                planned_rr=planned_rr,
            )
        if c.clean_structure is False:
            return Decision(
                decision="NO_TRADE", operational_state="REJECTED", reason_code="CLEAN_STRUCTURE_FAILED",
                reasons=["1.5R-2.0R setup does not satisfy the clean-structure requirement."],
                risk_per_share=risk_per_share,
                planned_rr=planned_rr,
            )

    if not c.trigger_confirmed:
        # Classification only: preserve the existing decision and reason precedence.
        wait_state = "WAITING_FOR_TRIGGER"
        wait_code = "TRIGGER_NOT_CONFIRMED"
        if c.target_validated is not True:
            wait_state, wait_code = "HOLD_UNRESOLVED", "TARGET_NOT_VALIDATED"
        elif c.journal_trade_id is None or not c.journal_trade_id.strip():
            wait_state, wait_code = "HOLD_UNRESOLVED", "JOURNAL_TRADE_ID_MISSING"
        elif size_position(c.entry_price, risk_per_share) is None:
            wait_state, wait_code = "HOLD_UNRESOLVED", "POSITION_SIZE_UNAVAILABLE"
        return Decision(
            decision="WAIT", operational_state=wait_state, reason_code=wait_code,
            reasons=["Predefined trigger has not confirmed prospectively."],
            risk_per_share=risk_per_share,
            planned_rr=planned_rr,
        )
    if c.triggered_at is None:
        return Decision(
            decision="WAIT", operational_state="HOLD_UNRESOLVED", reason_code="TRIGGER_TIMESTAMP_MISSING",
            reasons=["Prospective trigger confirmation timestamp is missing."],
            risk_per_share=risk_per_share,
            planned_rr=planned_rr,
        )
    if c.journal_trade_id is None or not c.journal_trade_id.strip():
        return Decision(
            decision="WAIT", operational_state="HOLD_UNRESOLVED", reason_code="JOURNAL_TRADE_ID_MISSING",
            reasons=["Unique journal_trade_id is required before a prospective TRADE signal."],
            risk_per_share=risk_per_share,
            planned_rr=planned_rr,
        )

    sizing = size_position(c.entry_price, risk_per_share)
    if sizing is None:
        return Decision(
            decision="NO_TRADE", operational_state="REJECTED", reason_code="POSITION_SIZE_UNAVAILABLE",
            reasons=["Risk/notional ceilings do not permit a positive share quantity."],
            risk_per_share=risk_per_share,
            planned_rr=planned_rr,
        )

    qty, dollar_risk, notional = sizing
    return Decision(
        decision="TRADE", operational_state="TRADE_READY", reason_code="ALL_CONDITIONS_SATISFIED",
        reasons=["All currently required Strategy #1 v0.3 shadow-evaluation conditions are satisfied."],
        qty=qty,
        risk_per_share=risk_per_share,
        planned_rr=planned_rr,
        dollar_risk=dollar_risk,
        notional=notional,
    )


def write_supabase(c: Candidate, d: Decision) -> str:
    problem = evidence_class_problem(c.experiment_class, c.data_kind, c.market_data_source, c.notes)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Supabase server credentials are not configured.")

    now = datetime.now(timezone.utc)
    record = {
        "evaluated_at": now.isoformat(),
        "experiment_class": c.experiment_class,
        "strategy_id": STRATEGY_ID,
        "decision": d.decision,
        "status": "SHADOW",
        "ruleset_version": c.ruleset_version,
        "worker_version": WORKER_VERSION,
        "symbol": c.symbol,
        "direction": c.direction,
        "market_regime": c.market_regime,
        "market_context_ok": c.market_context_ok,
        "market_data_source": c.market_data_source,
        "data_timestamp": c.data_timestamp.isoformat() if c.data_timestamp else None,
        "data_quality_ok": c.data_quality_ok,
        "consolidated_data": c.consolidated_data,
        "catalyst_summary": c.catalyst_summary,
        "catalyst_tier": c.catalyst_tier,
        "catalyst_event_at": c.catalyst_event_at.isoformat() if c.catalyst_event_at else None,
        "catalyst_sources": [s.model_dump(mode="json") for s in c.catalyst_sources],
        "catalyst_verified": c.catalyst_verified,
        "catalyst_material": c.catalyst_material,
        "relative_strength_ok": c.relative_strength_ok,
        "participation_ok": c.participation_ok,
        "rvol": str(c.rvol) if c.rvol is not None else None,
        "rvol_consolidated": c.rvol_consolidated,
        "liquidity_ok": c.liquidity_ok,
        "entry_model": c.entry_model,
        "trigger_definition": c.trigger_definition,
        "trigger_price": str(c.trigger_price) if c.trigger_price is not None else None,
        "trigger_confirmed": c.trigger_confirmed,
        "triggered_at": c.triggered_at.isoformat() if c.triggered_at else None,
        "entry_price": str(c.entry_price) if c.entry_price is not None else None,
        "stop_price": str(c.stop_price) if c.stop_price is not None else None,
        "target_price": str(c.target_price) if c.target_price is not None else None,
        "risk_per_share": str(d.risk_per_share) if d.risk_per_share is not None else None,
        "planned_rr": str(d.planned_rr) if d.planned_rr is not None else None,
        "qty": d.qty,
        "dollar_risk": str(d.dollar_risk) if d.dollar_risk is not None else None,
        "notional": str(d.notional) if d.notional is not None else None,
        "clean_structure": c.clean_structure,
        "avoid_conditions": [],
        "wait_reasons": d.reasons if d.decision == "WAIT" else [],
        "rejection_reasons": d.reasons if d.decision == "NO_TRADE" else [],
        "decision_inputs": {
            **c.decision_inputs,
            "run_id": c.run_id,
            "candidate_id": c.candidate_id,
            "source_discovery_item_id": c.source_discovery_item_id,
            "session_date": c.session_date.isoformat() if c.session_date else None,
            "data_kind": c.data_kind,
            "current_review": c.current_review.model_dump(mode="json") if c.current_review else None,
            "confirmation_review_id": c.confirmation_review_id,
            "catalyst_cross_source_verified": c.catalyst_cross_source_verified,
            "materiality_rationale": c.materiality_rationale,
            "consolidated_data_required": c.consolidated_data_required,
            "target_validated": c.target_validated,
            "stop_would_widen": c.stop_would_widen,
            "fomo_or_revenge_motive": c.fomo_or_revenge_motive,
            "price_extended_or_chasing": c.price_extended_or_chasing,
            "major_macro_event_imminent": c.major_macro_event_imminent,
            "missed_trigger": c.missed_trigger,
            "after_first_minute": c.after_first_minute,
            "realized_daily_loss_dollars": (
                str(c.realized_daily_loss_dollars)
                if c.realized_daily_loss_dollars is not None
                else None
            ),
            "executed_trades_today": c.executed_trades_today,
            "worker_reasons": d.reasons,
            "operational_state": d.operational_state,
            "reason_code": d.reason_code,
        },
        "journal_trade_id": c.journal_trade_id,
        "notes": c.notes,
    }

    response = requests.post(
        f"{SUPABASE_URL.rstrip('/')}/rest/v1/strategy_signals",
        headers={
            "apikey": SUPABASE_SECRET_KEY,
            **({"Authorization": f"Bearer {SUPABASE_SECRET_KEY}"}
               if SUPABASE_SECRET_KEY.count(".") == 2 else {}),
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        json=record,
        timeout=15,
    )
    if not response.ok:
        raise HTTPException(
            status_code=502,
            detail=f"Supabase insert failed ({response.status_code}): {response.text[:500]}",
        )

    rows = response.json()
    if not rows:
        raise HTTPException(status_code=502, detail="Supabase insert returned no record.")
    return rows[0]["id"]


@app.get("/health")
def health():
    return {
        "ok": True,
        "mode": "SHADOW",
        "strategy_id": STRATEGY_ID,
        "ruleset_version": RULESET_VERSION,
        "worker_version": WORKER_VERSION,
        "app_version": APP_VERSION,
        "broker_execution_enabled": False,
    }


@app.post("/evaluate", response_model=Decision)
def evaluate_candidate(
    candidate: Candidate,
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
):
    require_auth(credentials)
    decision = evaluate(candidate)
    decision.supabase_record_id = write_supabase(candidate, decision)
    return decision
