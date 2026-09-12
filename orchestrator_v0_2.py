import hmac
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Literal

import requests
from fastapi import FastAPI, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, model_validator

APP_VERSION = "0.2.0-shadow-orchestrator"
RULESET_VERSION = os.getenv("RULESET_VERSION", "v0.3")
ORCHESTRATOR_TOKEN = os.getenv("ORCHESTRATOR_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")
STRATEGY_WORKER_URL = os.getenv("STRATEGY_WORKER_URL", "https://strategy-1-shadow-worker.onrender.com")
WORKER_TOKEN = os.getenv("WORKER_TOKEN")
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET")
ALPACA_DATA_FEED = os.getenv("ALPACA_DATA_FEED", "iex").lower()
if ALPACA_DATA_FEED not in {"iex", "sip"}:
    ALPACA_DATA_FEED = "iex"

app = FastAPI(
    title="Strategy #1 Shadow Orchestrator",
    version=APP_VERSION,
    description=(
        "Shadow-mode candidate ingestion and prospective trigger-observation service. "
        "It never submits broker orders and never converts a price-level observation "
        "into trigger confirmation by itself."
    ),
)
bearer_scheme = HTTPBearer(auto_error=False)


def wait_for_dependency(
    base_url: str,
    name: str,
    *,
    attempts: int = 4,
    connect_timeout: int = 5,
    read_timeout: int = 45,
) -> None:
    """Wake/check a downstream Render service before a dependent call.

    Only GET /health is retried. This avoids blindly replaying side-effecting
    POST requests while still tolerating Render cold starts and transient
    network failures.
    """
    import time

    delays = (0, 2, 5, 10)
    last_error = "unknown dependency error"
    for attempt in range(attempts):
        if attempt:
            time.sleep(delays[min(attempt, len(delays) - 1)])
        try:
            r = requests.get(
                f"{base_url.rstrip('/')}/health",
                timeout=(connect_timeout, read_timeout),
            )
            if r.ok:
                return
            last_error = f"HTTP {r.status_code}: {r.text[:300]}"
        except requests.RequestException as exc:
            last_error = f"{type(exc).__name__}: {str(exc)[:300]}"
    raise HTTPException(
        status_code=503,
        detail=f"{name} unavailable after cold-start retries: {last_error}",
    )


def require_auth(credentials: HTTPAuthorizationCredentials | None) -> None:
    if not ORCHESTRATOR_TOKEN:
        raise HTTPException(status_code=503, detail="ORCHESTRATOR_TOKEN is not configured.")
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing bearer token.")
    if not hmac.compare_digest(credentials.credentials, ORCHESTRATOR_TOKEN):
        raise HTTPException(status_code=403, detail="Invalid bearer token.")


def _sb_headers() -> dict[str, str]:
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Supabase server credentials are not configured.")
    return {
        "apikey": SUPABASE_SECRET_KEY,
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def sb_insert(table: str, record: dict[str, Any]) -> list[dict[str, Any]]:
    r = requests.post(f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table}", headers=_sb_headers(), json=record, timeout=15)
    if not r.ok:
        raise HTTPException(status_code=502, detail=f"Supabase insert failed: {r.status_code} {r.text[:500]}")
    return r.json()


def sb_update(table: str, filters: dict[str, str], record: dict[str, Any]) -> list[dict[str, Any]]:
    params = {k: f"eq.{v}" for k, v in filters.items()}
    r = requests.patch(f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table}", headers=_sb_headers(), params=params, json=record, timeout=15)
    if not r.ok:
        raise HTTPException(status_code=502, detail=f"Supabase update failed: {r.status_code} {r.text[:500]}")
    return r.json()


def sb_select(table: str, params: dict[str, str]) -> list[dict[str, Any]]:
    headers = _sb_headers().copy()
    headers.pop("Prefer", None)
    r = requests.get(f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table}", headers=headers, params=params, timeout=15)
    if not r.ok:
        raise HTTPException(status_code=502, detail=f"Supabase query failed: {r.status_code} {r.text[:500]}")
    return r.json()


def write_event(candidate_id: str, event_type: str, *, data_timestamp: str | None = None, observed_price: Decimal | None = None, payload: dict[str, Any] | None = None) -> None:
    sb_insert("strategy_candidate_events", {
        "candidate_id": candidate_id,
        "event_type": event_type,
        "event_at": datetime.now(timezone.utc).isoformat(),
        "market_data_source": f"alpaca_{ALPACA_DATA_FEED}" if data_timestamp else None,
        "data_timestamp": data_timestamp,
        "observed_price": str(observed_price) if observed_price is not None else None,
        "payload": payload or {},
    })


class CatalystSource(BaseModel):
    source: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    headline_or_event: str = Field(min_length=1)
    event_timestamp: datetime


class CandidateIn(BaseModel):
    experiment_class: Literal["STRATEGY_1", "INFRASTRUCTURE_TEST"] = "STRATEGY_1"
    source_discovery_item_id: str | None = None
    session_date: date
    discovery_phase: Literal["PREMARKET", "POST_OPEN"]
    symbol: str = Field(min_length=1, max_length=12)
    direction: Literal["LONG", "SHORT"]
    ruleset_version: str = "v0.3"
    market_data_source: str = Field(min_length=1)
    consolidated_data: bool | None = None
    consolidated_data_required: bool | None = None
    market_regime: Literal["Bullish", "Bearish", "Mixed", "Choppy"] | None = None
    market_context_ok: bool | None = None
    liquidity_ok: bool | None = None
    participation_ok: bool | None = None
    relative_strength_ok: bool | None = None
    price_extended_or_chasing: bool | None = None
    major_macro_event_imminent: bool | None = None
    stop_would_widen: bool | None = None
    fomo_or_revenge_motive: bool | None = None
    target_validated: bool | None = None
    clean_structure: bool | None = None
    catalyst_summary: str = Field(min_length=1)
    catalyst_tier: Literal["A", "B", "C"]
    catalyst_event_at: datetime | None = None
    catalyst_material: bool | None = None
    materiality_rationale: str | None = None
    catalyst_verified: bool | None = None
    catalyst_cross_source_verified: bool | None = None
    catalyst_sources: list[CatalystSource] = Field(default_factory=list)
    entry_model: str | None = None
    trigger_definition: str | None = None
    trigger_price: Decimal | None = None
    trigger_operator: Literal["GTE", "LTE"] | None = None
    entry_price: Decimal | None = None
    stop_price: Decimal | None = None
    target_price: Decimal | None = None
    realized_daily_loss_dollars: Decimal | None = None
    executed_trades_today: int | None = None
    after_first_minute: bool | None = None
    missed_trigger: bool | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_candidate(self):
        self.symbol = self.symbol.strip().upper()
        if self.ruleset_version != RULESET_VERSION:
            raise ValueError(f"ruleset_version must match configured {RULESET_VERSION}")
        if (self.trigger_price is None) != (self.trigger_operator is None):
            raise ValueError("trigger_price and trigger_operator must be supplied together")
        return self


class ConfirmationIn(BaseModel):
    confirmed: bool
    confirmation_source: str = Field(min_length=1)
    data_timestamp: datetime
    entry_price: Decimal | None = None
    market_data_source: str | None = None
    market_regime: Literal["Bullish", "Bearish", "Mixed", "Choppy"] | None = None
    market_context_ok: bool | None = None
    liquidity_ok: bool | None = None
    participation_ok: bool | None = None
    relative_strength_ok: bool | None = None
    price_extended_or_chasing: bool | None = None
    major_macro_event_imminent: bool | None = None
    stop_would_widen: bool | None = None
    fomo_or_revenge_motive: bool | None = None
    target_validated: bool | None = None
    clean_structure: bool | None = None
    consolidated_data: bool | None = None
    consolidated_data_required: bool | None = None
    realized_daily_loss_dollars: Decimal | None = None
    executed_trades_today: int | None = None
    after_first_minute: bool | None = None
    missed_trigger: bool | None = None


def candidate_to_worker_payload(c: dict[str, Any], *, data_timestamp: str | None, trigger_confirmed: bool, triggered_at: str | None) -> dict[str, Any]:
    return {
        "experiment_class": c.get("experiment_class", "STRATEGY_1"),
        "symbol": c["symbol"], "direction": c["direction"], "journal_trade_id": c.get("journal_trade_id"),
        "market_data_source": c["market_data_source"], "data_timestamp": data_timestamp,
        "data_quality_ok": True if data_timestamp else None,
        "consolidated_data": c.get("consolidated_data"), "consolidated_data_required": c.get("consolidated_data_required"),
        "ruleset_version": c["ruleset_version"], "market_regime": c.get("market_regime"),
        "market_context_ok": c.get("market_context_ok"), "liquidity_ok": c.get("liquidity_ok"),
        "participation_ok": c.get("participation_ok"), "relative_strength_ok": c.get("relative_strength_ok"),
        "price_extended_or_chasing": c.get("price_extended_or_chasing"),
        "major_macro_event_imminent": c.get("major_macro_event_imminent"),
        "stop_would_widen": c.get("stop_would_widen"), "fomo_or_revenge_motive": c.get("fomo_or_revenge_motive"),
        "target_validated": c.get("target_validated"), "clean_structure": c.get("clean_structure"),
        "catalyst_summary": c["catalyst_summary"], "catalyst_tier": c["catalyst_tier"],
        "catalyst_event_at": c.get("catalyst_event_at"), "catalyst_material": c.get("catalyst_material"),
        "materiality_rationale": c.get("materiality_rationale"), "catalyst_verified": c.get("catalyst_verified"),
        "catalyst_cross_source_verified": c.get("catalyst_cross_source_verified"), "catalyst_sources": c.get("catalyst_sources") or [],
        "entry_model": c.get("entry_model"), "trigger_definition": c.get("trigger_definition"),
        "trigger_price": c.get("trigger_price"), "trigger_confirmed": trigger_confirmed, "triggered_at": triggered_at,
        "entry_price": c.get("entry_price"), "stop_price": c.get("stop_price"), "target_price": c.get("target_price"),
        "realized_daily_loss_dollars": c.get("realized_daily_loss_dollars"), "executed_trades_today": c.get("executed_trades_today"),
        "after_first_minute": c.get("after_first_minute"), "missed_trigger": c.get("missed_trigger"),
        "decision_inputs": {
            "candidate_id": c["id"], "orchestrator_version": APP_VERSION,
            "trigger_observed_at": c.get("trigger_observed_at"), "trigger_confirmation_source": c.get("trigger_confirmation_source"),
        },
        "notes": c.get("notes"),
    }


def call_worker(payload: dict[str, Any]) -> dict[str, Any]:
    if not WORKER_TOKEN:
        raise HTTPException(status_code=503, detail="WORKER_TOKEN is not configured for worker handoff.")
    wait_for_dependency(
        STRATEGY_WORKER_URL,
        "Strategy Worker",
    )
    try:
        r = requests.post(
            f"{STRATEGY_WORKER_URL.rstrip('/')}/evaluate",
            headers={
                "Authorization": f"Bearer {WORKER_TOKEN}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=(5, 45),
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Strategy Worker handoff failed after successful health check: "
                f"{type(exc).__name__}: {str(exc)[:300]}"
            ),
        ) from exc
    if not r.ok:
        raise HTTPException(status_code=502, detail=f"Strategy Worker failed: {r.status_code} {r.text[:500]}")
    return r.json()


def latest_alpaca_trade(symbol: str) -> tuple[Decimal, str]:
    if not ALPACA_API_KEY or not ALPACA_API_SECRET:
        raise HTTPException(status_code=503, detail="Alpaca market-data credentials are not configured.")
    r = requests.get(
        f"https://data.alpaca.markets/v2/stocks/{symbol}/trades/latest",
        headers={"APCA-API-KEY-ID": ALPACA_API_KEY, "APCA-API-SECRET-KEY": ALPACA_API_SECRET},
        params={"feed": ALPACA_DATA_FEED}, timeout=10,
    )
    if not r.ok:
        raise HTTPException(status_code=502, detail=f"Alpaca market-data request failed: {r.status_code} {r.text[:300]}")
    trade = (r.json().get("trade") or {})
    if "p" not in trade or "t" not in trade:
        raise HTTPException(status_code=502, detail="Alpaca response did not contain latest trade price/timestamp.")
    return Decimal(str(trade["p"])), str(trade["t"])


def trigger_crossed(c: dict[str, Any], price: Decimal) -> bool:
    if c.get("trigger_price") is None or c.get("trigger_operator") is None:
        return False
    tp = Decimal(str(c["trigger_price"]))
    return (c["trigger_operator"] == "GTE" and price >= tp) or (c["trigger_operator"] == "LTE" and price <= tp)


@app.get("/health")
def health():
    return {
        "ok": True, "mode": "SHADOW", "version": APP_VERSION, "ruleset_version": RULESET_VERSION,
        "broker_execution_enabled": False, "trigger_confirmation_automatic": False, "alpaca_data_feed": ALPACA_DATA_FEED,
    }


@app.post("/candidates/ingest")
def ingest_candidate(candidate: CandidateIn, credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme)):
    require_auth(credentials)
    record = candidate.model_dump(mode="json")
    record.update({"status": "WAITING", "active": True})

    existing = []
    if candidate.source_discovery_item_id:
        existing = sb_select(
            "strategy_candidates",
            {
                "select": "*",
                "source_discovery_item_id": (
                    f"eq.{candidate.source_discovery_item_id}"
                ),
                "limit": "1",
            },
        )

    if existing:
        c = existing[0]
        write_event(
            c["id"],
            "INGEST_REPLAY",
            payload={
                "source": "structured_ingestion",
                "version": APP_VERSION,
                "source_discovery_item_id": (
                    candidate.source_discovery_item_id
                ),
            },
        )
    else:
        c = sb_insert("strategy_candidates", record)[0]
        write_event(
            c["id"],
            "INGESTED",
            payload={
                "source": "structured_ingestion",
                "version": APP_VERSION,
                "source_discovery_item_id": (
                    candidate.source_discovery_item_id
                ),
            },
        )

    worker = call_worker(
        candidate_to_worker_payload(
            c,
            data_timestamp=None,
            trigger_confirmed=False,
            triggered_at=None,
        )
    )
    sb_update("strategy_candidates", {"id": c["id"]}, {
        "last_worker_decision": worker["decision"], "last_signal_id": worker.get("supabase_record_id"),
        "status": "NO_TRADE" if worker["decision"] == "NO_TRADE" else "WAITING", "active": worker["decision"] != "NO_TRADE",
    })
    write_event(c["id"], "WORKER_EVALUATED", payload={"decision": worker["decision"], "reasons": worker["reasons"], "signal_id": worker.get("supabase_record_id")})
    return {"candidate_id": c["id"], "worker": worker}


@app.get("/candidates/active")
def active_candidates(credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme)):
    require_auth(credentials)
    return sb_select("strategy_candidates", {"select": "*", "active": "eq.true", "order": "created_at.asc"})


@app.post("/monitor/run-once")
def monitor_run_once(credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme)):
    require_auth(credentials)
    candidates = sb_select("strategy_candidates", {
        "select": "*", "active": "eq.true", "status": "in.(WAITING,TRIGGER_OBSERVED,CONFIRMATION_REQUIRED)", "order": "created_at.asc",
    })
    results: list[dict[str, Any]] = []
    for c in candidates:
        try:
            if c.get("trigger_price") is None or c.get("trigger_operator") is None:
                write_event(c["id"], "ERROR", payload={"reason": "No machine-observable trigger price/operator."})
                results.append({"candidate_id": c["id"], "symbol": c["symbol"], "result": "NO_TRIGGER_SPEC"})
                continue
            if c.get("consolidated_data_required") is True and ALPACA_DATA_FEED != "sip":
                write_event(c["id"], "ERROR", payload={"reason": "Consolidated data required but monitor feed is not SIP.", "feed": ALPACA_DATA_FEED})
                results.append({"candidate_id": c["id"], "symbol": c["symbol"], "result": "FAIL_CLOSED_DATA"})
                continue
            price, ts = latest_alpaca_trade(c["symbol"])
            write_event(c["id"], "PRICE_CHECK", data_timestamp=ts, observed_price=price)
            if trigger_crossed(c, price) and not c.get("trigger_observed_at"):
                now = datetime.now(timezone.utc).isoformat()
                sb_update("strategy_candidates", {"id": c["id"]}, {"status": "CONFIRMATION_REQUIRED", "trigger_observed_at": now, "market_data_source": f"alpaca_{ALPACA_DATA_FEED}"})
                write_event(c["id"], "TRIGGER_OBSERVED", data_timestamp=ts, observed_price=price, payload={
                    "trigger_price": c["trigger_price"], "trigger_operator": c["trigger_operator"],
                    "note": "Price-level observation only; not Strategy #1 trigger confirmation.",
                })
                results.append({"candidate_id": c["id"], "symbol": c["symbol"], "result": "TRIGGER_OBSERVED", "price": str(price)})
            else:
                results.append({"candidate_id": c["id"], "symbol": c["symbol"], "result": "NO_CHANGE", "price": str(price)})
        except Exception as exc:
            try:
                write_event(c["id"], "ERROR", payload={"reason": str(exc)[:500]})
            except Exception:
                pass
            results.append({"candidate_id": c["id"], "symbol": c["symbol"], "result": "ERROR", "detail": str(exc)[:300]})
    return {"mode": "SHADOW", "broker_execution_enabled": False, "trigger_confirmation_automatic": False, "checked": len(candidates), "results": results}


@app.post("/candidates/{candidate_id}/confirm-trigger")
def confirm_trigger(candidate_id: str, confirmation: ConfirmationIn, credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme)):
    require_auth(credentials)
    rows = sb_select("strategy_candidates", {"select": "*", "id": f"eq.{candidate_id}", "limit": "1"})
    if not rows:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    c = rows[0]
    if not confirmation.confirmed:
        write_event(c["id"], "UPDATED", data_timestamp=confirmation.data_timestamp.isoformat(), payload={"confirmation_source": confirmation.confirmation_source, "confirmed": False})
        return {"candidate_id": c["id"], "decision": "WAIT", "reason": "Trigger not confirmed."}
    updates: dict[str, Any] = {
        "trigger_confirmed": True, "trigger_confirmed_at": datetime.now(timezone.utc).isoformat(),
        "trigger_confirmation_source": confirmation.confirmation_source, "status": "TRIGGER_OBSERVED",
    }
    for field in (
        "market_regime", "market_context_ok", "liquidity_ok", "participation_ok", "relative_strength_ok",
        "price_extended_or_chasing", "major_macro_event_imminent", "stop_would_widen", "fomo_or_revenge_motive",
        "target_validated", "clean_structure", "consolidated_data", "consolidated_data_required",
        "realized_daily_loss_dollars", "executed_trades_today", "after_first_minute", "missed_trigger",
        "entry_price", "market_data_source",
    ):
        value = getattr(confirmation, field)
        if value is not None:
            updates[field] = str(value) if isinstance(value, Decimal) else value
    if not c.get("journal_trade_id"):
        updates["journal_trade_id"] = f"S1-{c['session_date'].replace('-', '')}-{c['symbol']}-{c['id'].split('-')[0]}"
    updated = sb_update("strategy_candidates", {"id": c["id"]}, updates)[0]
    write_event(c["id"], "TRIGGER_CONFIRMED", data_timestamp=confirmation.data_timestamp.isoformat(), payload={"confirmation_source": confirmation.confirmation_source})
    worker = call_worker(candidate_to_worker_payload(updated, data_timestamp=confirmation.data_timestamp.isoformat(), trigger_confirmed=True, triggered_at=updated["trigger_confirmed_at"]))
    new_status = "SHADOW_TRADE" if worker["decision"] == "TRADE" else ("NO_TRADE" if worker["decision"] == "NO_TRADE" else "CONFIRMATION_REQUIRED")
    sb_update("strategy_candidates", {"id": c["id"]}, {
        "last_worker_decision": worker["decision"], "last_signal_id": worker.get("supabase_record_id"),
        "status": new_status, "active": worker["decision"] == "WAIT",
    })
    write_event(c["id"], "WORKER_EVALUATED", data_timestamp=confirmation.data_timestamp.isoformat(), payload={"decision": worker["decision"], "reasons": worker["reasons"], "signal_id": worker.get("supabase_record_id")})
    return {"candidate_id": c["id"], "mode": "SHADOW", "broker_execution_enabled": False, "worker": worker}
