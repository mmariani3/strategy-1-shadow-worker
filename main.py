import hmac
import os
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from typing import Any, Literal

import requests
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, model_validator

APP_VERSION = "0.1.0-shadow"
STRATEGY_ID = "STRATEGY_1"
RULESET_VERSION = os.getenv("RULESET_VERSION", "v0.3")
WORKER_VERSION = os.getenv("WORKER_VERSION", APP_VERSION)

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


class CatalystSource(BaseModel):
    source: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    headline_or_event: str = Field(min_length=1)
    event_timestamp: datetime


class Candidate(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)
    direction: Literal["LONG", "SHORT"]
    journal_trade_id: str | None = None
    evaluated_at: datetime | None = None
    market_data_source: str = Field(min_length=1)
    data_timestamp: datetime | None = None
    data_quality_ok: bool | None = None
    consolidated_data: bool | None = None

    experiment_class: Literal["STRATEGY_1", "INFRASTRUCTURE_TEST"] = "STRATEGY_1"
    ruleset_version: str = "v0.3"
    market_regime: Literal["Bullish", "Bearish", "Mixed", "Choppy"] | None = None

    market_context_ok: bool | None = None
    liquidity_ok: bool | None = None
    participation_ok: bool | None = None
    price_extended_or_chasing: bool | None = None
    major_macro_event_imminent: bool | None = None
    clean_structure: bool | None = None

    catalyst_summary: str | None = None
    catalyst_tier: Literal["A", "B", "C"] | None = None
    catalyst_event_at: datetime | None = None
    catalyst_material: bool | None = None
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
    missed_trigger: bool | None = None
    after_first_minute: bool | None = None

    entry_price: Decimal | None = None
    stop_price: Decimal | None = None
    target_price: Decimal | None = None

    realized_daily_loss_dollars: Decimal = Decimal("0")
    executed_trades_today: int = 0

    decision_inputs: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None

    @model_validator(mode="after")
    def normalize_symbol(self):
        self.symbol = self.symbol.upper().strip()
        return self


class Decision(BaseModel):
    decision: Literal["TRADE", "WAIT", "NO_TRADE"]
    reasons: list[str]
    qty: int | None = None
    risk_per_share: Decimal | None = None
    planned_rr: Decimal | None = None
    dollar_risk: Decimal | None = None
    notional: Decimal | None = None
    supabase_record_id: str | None = None


def require_auth(authorization: str | None):
    if not WORKER_TOKEN:
        raise HTTPException(status_code=503, detail="WORKER_TOKEN is not configured.")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token.")
    supplied = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(supplied, WORKER_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid bearer token.")


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
        return Decision(decision="NO_TRADE", reasons=["Infrastructure tests are not Strategy #1 decisions."])
    if c.ruleset_version != RULESET_VERSION:
        return Decision(
            decision="NO_TRADE",
            reasons=[f"Ruleset mismatch: input={c.ruleset_version}, worker={RULESET_VERSION}."],
        )

    if c.catalyst_tier is None or c.catalyst_summary is None:
        return Decision(decision="NO_TRADE", reasons=["No identifiable catalyst."])
    if c.catalyst_tier == "C":
        return Decision(decision="NO_TRADE", reasons=["Tier C catalyst is insufficient for Strategy #1."])
    if c.catalyst_material is False:
        return Decision(decision="NO_TRADE", reasons=["Catalyst is explicitly non-material."])
    if c.missed_trigger is True:
        return Decision(decision="NO_TRADE", reasons=["Planned trigger was missed; chasing is prohibited."])
    if c.price_extended_or_chasing is True:
        return Decision(decision="NO_TRADE", reasons=["Price is extended / entry would require chasing."])
    if c.major_macro_event_imminent is True:
        return Decision(decision="NO_TRADE", reasons=["Major scheduled macro event is imminent."])
    if c.realized_daily_loss_dollars >= MAX_DAILY_LOSS_DOLLARS:
        return Decision(decision="NO_TRADE", reasons=["Daily loss limit has been reached."])
    if c.executed_trades_today >= MAX_TRADES_PER_DAY:
        return Decision(decision="NO_TRADE", reasons=["Maximum executed trades per day has been reached."])

    geometry = calc_geometry(c)
    if geometry == "INVALID":
        return Decision(decision="NO_TRADE", reasons=["Entry/stop/target geometry is invalid for the direction."])

    risk_per_share = planned_rr = None
    if geometry is not None:
        risk_per_share, _reward, planned_rr = geometry
        if planned_rr < Decimal("1.5"):
            return Decision(
                decision="NO_TRADE",
                reasons=[f"Planned reward/risk {planned_rr:.3f}R is below the 1.5R minimum."],
                risk_per_share=risk_per_share,
                planned_rr=planned_rr,
            )

    unresolved = {
        "market regime": c.market_regime,
        "market context": c.market_context_ok,
        "data quality": c.data_quality_ok,
        "liquidity/execution quality": c.liquidity_ok,
        "participation": c.participation_ok,
        "catalyst verification": c.catalyst_verified,
        "cross-source catalyst verification": c.catalyst_cross_source_verified,
        "relative strength/weakness": c.relative_strength_ok,
        "first-minute restriction": c.after_first_minute,
        "extended/chasing assessment": c.price_extended_or_chasing,
        "macro-event assessment": c.major_macro_event_imminent,
        "missed-trigger assessment": c.missed_trigger,
    }
    missing = [name for name, value in unresolved.items() if value is None]
    if missing:
        return Decision(decision="WAIT", reasons=["Required structured inputs unresolved: " + ", ".join(missing) + "."])

    if c.market_context_ok is False:
        return Decision(decision="WAIT", reasons=["Market context is currently hostile / not approved."])
    if c.data_quality_ok is False:
        return Decision(decision="WAIT", reasons=["Required market data is stale, contradictory, or unreliable."])
    if c.liquidity_ok is False:
        return Decision(decision="NO_TRADE", reasons=["Liquidity / execution quality is unacceptable."])
    if c.participation_ok is False:
        return Decision(decision="WAIT", reasons=["Required participation is not confirmed."])
    if c.relative_strength_ok is False:
        return Decision(decision="WAIT", reasons=["Required relative strength/weakness is not confirmed."])
    if c.catalyst_verified is False or c.catalyst_cross_source_verified is False:
        return Decision(decision="WAIT", reasons=["Catalyst verification is incomplete."])
    if c.after_first_minute is False:
        return Decision(decision="WAIT", reasons=["Strategy #1 cannot trade during the first minute after the open."])

    if c.entry_model not in APPROVED_ENTRY_MODELS:
        return Decision(decision="WAIT", reasons=["Approved entry model is not yet specified."])
    if not c.trigger_definition:
        return Decision(decision="WAIT", reasons=["Predefined trigger is not specified."])
    if c.entry_price is None or c.stop_price is None or c.target_price is None:
        return Decision(decision="WAIT", reasons=["Entry, structural stop, and target must be predefined."])
    if geometry is None:
        return Decision(decision="WAIT", reasons=["Trade geometry is incomplete."])

    risk_per_share, _reward, planned_rr = geometry

    if Decimal("1.5") <= planned_rr < Decimal("2.0"):
        if c.clean_structure is None:
            return Decision(
                decision="WAIT",
                reasons=["1.5R-2.0R setup requires explicit clean_structure input; criterion is not inferred."],
                risk_per_share=risk_per_share,
                planned_rr=planned_rr,
            )
        if c.clean_structure is False:
            return Decision(
                decision="NO_TRADE",
                reasons=["1.5R-2.0R setup does not satisfy the clean-structure requirement."],
                risk_per_share=risk_per_share,
                planned_rr=planned_rr,
            )

    if not c.trigger_confirmed:
        return Decision(
            decision="WAIT",
            reasons=["Predefined trigger has not confirmed prospectively."],
            risk_per_share=risk_per_share,
            planned_rr=planned_rr,
        )

    sizing = size_position(c.entry_price, risk_per_share)
    if sizing is None:
        return Decision(
            decision="NO_TRADE",
            reasons=["Risk/notional ceilings do not permit a positive share quantity."],
            risk_per_share=risk_per_share,
            planned_rr=planned_rr,
        )

    qty, dollar_risk, notional = sizing
    return Decision(
        decision="TRADE",
        reasons=["All currently required Strategy #1 v0.3 shadow-evaluation conditions are satisfied."],
        qty=qty,
        risk_per_share=risk_per_share,
        planned_rr=planned_rr,
        dollar_risk=dollar_risk,
        notional=notional,
    )


def write_supabase(c: Candidate, d: Decision) -> str:
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Supabase server credentials are not configured.")

    now = datetime.now(timezone.utc)
    record = {
        "evaluated_at": (c.evaluated_at or now).isoformat(),
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
            "catalyst_cross_source_verified": c.catalyst_cross_source_verified,
            "price_extended_or_chasing": c.price_extended_or_chasing,
            "major_macro_event_imminent": c.major_macro_event_imminent,
            "missed_trigger": c.missed_trigger,
            "after_first_minute": c.after_first_minute,
            "realized_daily_loss_dollars": str(c.realized_daily_loss_dollars),
            "executed_trades_today": c.executed_trades_today,
            "worker_reasons": d.reasons,
        },
        "journal_trade_id": c.journal_trade_id,
        "notes": c.notes,
    }

    response = requests.post(
        f"{SUPABASE_URL.rstrip('/')}/rest/v1/strategy_signals",
        headers={
            "apikey": SUPABASE_SECRET_KEY,
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
        "broker_execution_enabled": False,
    }


@app.post("/evaluate", response_model=Decision)
def evaluate_candidate(
    candidate: Candidate,
    authorization: str | None = Header(default=None),
):
    require_auth(authorization)
    decision = evaluate(candidate)
    decision.supabase_record_id = write_supabase(candidate, decision)
    return decision
