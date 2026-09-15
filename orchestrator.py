import hmac
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Literal

import requests
from fastapi import FastAPI, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, model_validator

APP_VERSION = "0.4.0-shadow-orchestrator"
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
    rows = r.json()
    if len(rows) != 1:
        raise HTTPException(status_code=409, detail="Candidate changed or update did not match exactly one row.")
    return rows


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
        "market_data_source": (f"alpaca_{ALPACA_DATA_FEED}" if data_timestamp and
                               event_type in ("PRICE_CHECK", "TRIGGER_OBSERVED") else None),
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
    model_config = {"extra": "forbid"}
    experiment_class: Literal["STRATEGY_1", "INFRASTRUCTURE_TEST"] = "STRATEGY_1"
    source_discovery_item_id: str | None = None
    session_date: date
    discovery_phase: Literal["PREMARKET", "POST_OPEN"]
    symbol: str = Field(min_length=1, max_length=12)
    direction: Literal["LONG", "SHORT"]
    ruleset_version: str = "v0.3"
    data_timestamp: datetime | None = None
    data_quality_ok: bool | None = None
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
    model_config = {"extra": "forbid"}
    confirmed: bool
    data_quality_ok: bool | None = None
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
        "data_quality_ok": c.get("data_quality_ok"),
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



class ReevaluationIn(ConfirmationIn):
    confirmed: Literal[False] = False


def get_candidate(candidate_id: str) -> dict[str, Any]:
    from uuid import UUID
    try:
        UUID(candidate_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="candidate_id must be a UUID.")
    rows = sb_select("strategy_candidates", {"select": "*", "id": f"eq.{candidate_id}", "limit": "1"})
    if not rows:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    return rows[0]


def valid_timestamp(value: str | datetime) -> datetime:
    try:
        dt = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=422, detail="A valid timezone-aware data timestamp is required.")
    if dt.tzinfo is None or dt > datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="Data timestamp must be timezone-aware and cannot be in the future.")
    return dt



def update_candidate(c: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    revision = c.get("lifecycle_revision", 0)
    r = requests.patch(f"{SUPABASE_URL.rstrip('/')}/rest/v1/strategy_candidates",
                       headers=_sb_headers(),
                       params={"id": f"eq.{c['id']}", "lifecycle_revision": f"eq.{revision}"},
                       json={**record, "lifecycle_revision": revision + 1}, timeout=15)
    if not r.ok:
        raise HTTPException(status_code=502, detail="Candidate lifecycle update failed.")
    rows = r.json()
    if len(rows) != 1:
        raise HTTPException(status_code=409, detail="Candidate changed concurrently; re-read before retry.")
    return rows[0]

def persist_worker(c: dict[str, Any], worker: dict[str, Any]) -> dict[str, Any]:
    decision, state, code = worker.get("decision"), worker.get("operational_state"), worker.get("reason_code")
    valid = {"TRADE": {"TRADE_READY"}, "NO_TRADE": {"REJECTED"},
             "WAIT": {"HOLD_UNRESOLVED", "WAITING_FOR_TRIGGER"}}
    if state not in valid.get(decision, set()) or not isinstance(code, str) or not code.strip():
        raise HTTPException(status_code=502, detail="Worker response lacks a valid operational classification.")
    if decision == "TRADE" and not c.get("trigger_confirmed"):
        raise HTTPException(status_code=502, detail="Unconfirmed candidate cannot accept a TRADE classification.")
    if state == "WAITING_FOR_TRIGGER" and (
        code != "TRIGGER_NOT_CONFIRMED" or c.get("trigger_confirmed")
        or not c.get("trigger_definition") or c.get("trigger_price") is None
        or c.get("trigger_operator") not in ("GTE", "LTE")
    ):
        state, code = "HOLD_UNRESOLVED", "MONITOR_TRIGGER_SPEC_UNRESOLVED"
    if state == "WAITING_FOR_TRIGGER" and c.get("trigger_observed_at"):
        state = "CONFIRMATION_REQUIRED"
    status = ("SHADOW_TRADE" if decision == "TRADE" else "NO_TRADE"
              if decision == "NO_TRADE" else "CONFIRMATION_REQUIRED"
              if state == "CONFIRMATION_REQUIRED" else "WAITING")
    updated = update_candidate(c, {
        "last_worker_decision": decision, "last_signal_id": worker.get("supabase_record_id"),
        "operational_state": state, "reason_code": code, "status": status,
        "active": decision == "WAIT",
    })
    write_event(c["id"], "WORKER_EVALUATED", data_timestamp=c.get("data_timestamp"),
                payload={"decision": decision, "operational_state": state, "reason_code": code,
                         "worker_operational_state": worker["operational_state"],
                         "reasons": worker.get("reasons", []), "signal_id": worker.get("supabase_record_id")})
    return updated


def evaluate_stored(c: dict[str, Any]):
    # Disable monitoring until this evaluation succeeds.
    c = update_candidate(c,
                         {"operational_state": "HOLD_UNRESOLVED", "reason_code": "EVALUATION_PENDING"})
    worker = call_worker(candidate_to_worker_payload(
        c, data_timestamp=c.get("data_timestamp"),
        trigger_confirmed=bool(c.get("trigger_confirmed")),
        triggered_at=c.get("trigger_confirmed_at")))
    updated = persist_worker(c, worker)
    return {"candidate_id": c["id"], "mode": "SHADOW", "broker_execution_enabled": False,
            "operational_state": updated["operational_state"], "reason_code": updated["reason_code"],
            "worker": worker}


def context_updates(review: ConfirmationIn):
    updates = review.model_dump(mode="json", exclude={"confirmed", "confirmation_source"}, exclude_none=True)
    valid_timestamp(review.data_timestamp)
    if not review.confirmation_source.strip():
        raise HTTPException(status_code=422, detail="A nonblank review/confirmation source is required.")
    return updates


@app.post("/candidates/ingest")
def ingest_candidate(candidate: CandidateIn, credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme)):
    require_auth(credentials)
    record = candidate.model_dump(mode="json")
    if candidate.data_timestamp is not None:
        valid_timestamp(candidate.data_timestamp)
    record.update({"status": "WAITING", "active": True,
                   "operational_state": "HOLD_UNRESOLVED", "reason_code": "EVALUATION_PENDING"})
    existing = []
    if candidate.source_discovery_item_id:
        existing = sb_select("strategy_candidates", {"select": "*",
                             "source_discovery_item_id": f"eq.{candidate.source_discovery_item_id}", "limit": "1"})
    if existing:
        c = existing[0]
        if c.get("last_signal_id"):
            return {"candidate_id": c["id"], "operational_state": c.get("operational_state"),
                    "reason_code": c.get("reason_code"), "idempotent_replay": True,
                    "worker": {"decision": c.get("last_worker_decision"),
                               "supabase_record_id": c["last_signal_id"]}}
    else:
        c = sb_insert("strategy_candidates", record)[0]
        write_event(c["id"], "INGESTED", payload={"source": "structured_ingestion",
                    "version": APP_VERSION, "source_discovery_item_id": candidate.source_discovery_item_id})
    if not c.get("journal_trade_id"):
        c = update_candidate(c,
                      {"journal_trade_id": f"S1-{c['session_date'].replace('-', '')}-{c['symbol']}-{c['id']}"})
    return evaluate_stored(c)


@app.get("/candidates/active")
def active_candidates(credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme)):
    require_auth(credentials)
    return sb_select("strategy_candidates", {"select": "*", "active": "eq.true", "order": "created_at.asc"})


@app.post("/candidates/{candidate_id}/reevaluate")
def reevaluate(candidate_id: str, review: ReevaluationIn,
               credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme)):
    require_auth(credentials)
    c = get_candidate(candidate_id)
    if c.get("last_worker_decision") in ("TRADE", "NO_TRADE") or c.get("status") == "CLOSED":
        raise HTTPException(status_code=409, detail="Terminal candidate cannot be re-evaluated.")
    updates = context_updates(review)
    if review.data_quality_ok is None:
        updates["data_quality_ok"] = None
    if c.get("data_timestamp") and valid_timestamp(review.data_timestamp) < valid_timestamp(c["data_timestamp"]):
        raise HTTPException(status_code=422, detail="Re-evaluation data cannot move backwards in time.")
    updates.update({"operational_state": "HOLD_UNRESOLVED", "reason_code": "EVALUATION_PENDING"})
    if not c.get("journal_trade_id"):
        updates["journal_trade_id"] = f"S1-{c['session_date'].replace('-', '')}-{c['symbol']}-{c['id']}"
    c = update_candidate(c, updates)
    write_event(c["id"], "UPDATED", data_timestamp=review.data_timestamp.isoformat(),
                payload={"source": review.confirmation_source, "prospective_reevaluation": True})
    return evaluate_stored(c)


@app.post("/monitor/run-once")
def monitor_run_once(credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme)):
    require_auth(credentials)
    candidates = sb_select("strategy_candidates", {
        "select": "*", "active": "eq.true", "operational_state": "eq.WAITING_FOR_TRIGGER",
        "last_worker_decision": "eq.WAIT", "trigger_confirmed": "eq.false", "order": "created_at.asc"})
    results = []
    for c in candidates:
        try:
            # Re-read so an earlier snapshot cannot monitor a candidate now held or terminal.
            c = get_candidate(c["id"])
            if not (c.get("active") and c.get("operational_state") == "WAITING_FOR_TRIGGER"
                    and c.get("last_worker_decision") == "WAIT" and not c.get("trigger_confirmed")):
                continue
            if c.get("experiment_class") != "STRATEGY_1":
                raise HTTPException(status_code=409, detail="Infrastructure candidates cannot be monitored.")
            if c.get("consolidated_data_required") is True and ALPACA_DATA_FEED != "sip":
                update_candidate(c,
                          {"operational_state": "HOLD_UNRESOLVED", "reason_code": "CONSOLIDATED_DATA_UNAVAILABLE"})
                results.append({"candidate_id": c["id"], "result": "FAIL_CLOSED_DATA"})
                continue
            price, ts = latest_alpaca_trade(c["symbol"])
            observed_dt = valid_timestamp(ts)
            if price <= 0 or not price.is_finite():
                raise HTTPException(status_code=422, detail="Observed price must be positive and finite.")
            if c.get("created_at") and observed_dt < valid_timestamp(c["created_at"]):
                raise HTTPException(status_code=422, detail="Trade observation predates prospective candidate creation.")
            if c.get("data_timestamp") and observed_dt < valid_timestamp(c["data_timestamp"]):
                raise HTTPException(status_code=422, detail="Trade observation predates the latest candidate review.")
            c = update_candidate(c, {"data_timestamp": ts,
                                     "market_data_source": f"alpaca_{ALPACA_DATA_FEED}",
                                     "consolidated_data": ALPACA_DATA_FEED == "sip"})
            evaluated = evaluate_stored(c)
            if evaluated["operational_state"] != "WAITING_FOR_TRIGGER":
                results.append({"candidate_id": c["id"], "result": evaluated["operational_state"]})
                continue
            c = get_candidate(c["id"])
            if c.get("operational_state") != "WAITING_FOR_TRIGGER":
                continue
            write_event(c["id"], "PRICE_CHECK", data_timestamp=ts, observed_price=price)
            if trigger_crossed(c, price):
                update_candidate(c,
                          {"status": "CONFIRMATION_REQUIRED", "operational_state": "CONFIRMATION_REQUIRED",
                           "reason_code": "TRIGGER_OBSERVED_NOT_CONFIRMED",
                           "trigger_observed_at": ts})
                write_event(c["id"], "TRIGGER_OBSERVED", data_timestamp=ts, observed_price=price,
                            payload={"trigger_price": c["trigger_price"], "trigger_operator": c["trigger_operator"],
                                     "note": "Observation only; explicit confirmation and Worker re-evaluation required."})
                results.append({"candidate_id": c["id"], "result": "TRIGGER_OBSERVED"})
            else:
                results.append({"candidate_id": c["id"], "result": "NO_CHANGE"})
        except Exception as exc:
            try:
                update_candidate(c,
                          {"operational_state": "HOLD_UNRESOLVED", "reason_code": "MONITOR_EVALUATION_FAILED"})
                write_event(c["id"], "ERROR", payload={"reason": str(exc)[:500]})
            except Exception:
                pass
            results.append({"candidate_id": c["id"], "result": "ERROR"})
    return {"mode": "SHADOW", "broker_execution_enabled": False,
            "trigger_confirmation_automatic": False, "checked": len(candidates), "results": results}


@app.post("/candidates/{candidate_id}/confirm-trigger")
def confirm_trigger(candidate_id: str, confirmation: ConfirmationIn,
                    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme)):
    require_auth(credentials)
    c = get_candidate(candidate_id)
    if c.get("last_worker_decision") in ("TRADE", "NO_TRADE") or c.get("status") == "CLOSED":
        raise HTTPException(status_code=409, detail="Terminal candidate cannot be confirmed.")
    updates = context_updates(confirmation)
    if confirmation.data_quality_ok is None:
        updates["data_quality_ok"] = None
    if not confirmation.confirmed:
        write_event(c["id"], "UPDATED", data_timestamp=confirmation.data_timestamp.isoformat(),
                    payload={"confirmation_source": confirmation.confirmation_source, "confirmed": False})
        return {"candidate_id": c["id"], "decision": "WAIT", "operational_state": c.get("operational_state"),
                "reason": "Trigger not confirmed."}
    if c.get("operational_state") != "CONFIRMATION_REQUIRED" or not c.get("trigger_observed_at"):
        raise HTTPException(status_code=409, detail="Prospective trigger observation is required before confirmation.")
    if valid_timestamp(confirmation.data_timestamp) < valid_timestamp(c["trigger_observed_at"]):
        raise HTTPException(status_code=422, detail="Confirmation data predates trigger observation.")
    if c.get("data_timestamp") and valid_timestamp(confirmation.data_timestamp) < valid_timestamp(c["data_timestamp"]):
        raise HTTPException(status_code=422, detail="Confirmation data predates the latest candidate review.")
    updates.update({"trigger_confirmed": True,
                    "trigger_confirmed_at": confirmation.data_timestamp.isoformat(),
                    "trigger_confirmation_source": confirmation.confirmation_source,
                    "operational_state": "HOLD_UNRESOLVED", "reason_code": "EVALUATION_PENDING"})
    c = update_candidate(c, updates)
    write_event(c["id"], "TRIGGER_CONFIRMED", data_timestamp=confirmation.data_timestamp.isoformat(),
                payload={"confirmation_source": confirmation.confirmation_source})
    return evaluate_stored(c)


# Journal writes use the connected Google account. These authenticated endpoints
# supply a validated projection and reconcile freshly read Sheet rows by ID.
JOURNAL_SPREADSHEET_ID = "1C4BAHQBzgU2hC64yIAHfQkwjSIuPm3pc7i-AIKrbk4w"
ENTRY_LABELS = {
    "opening_range_premarket_high_break": "Opening-range / premarket high break",
    "vwap_reclaim_rejection": "VWAP reclaim / rejection",
    "first_clean_pullback": "First clean pullback",
}


def journal_projection(c: dict[str, Any], item: dict[str, Any] | None,
                       run: dict[str, Any] | None, signal: dict[str, Any]):
    inputs = signal.get("decision_inputs") or {}
    if (signal.get("id") != c.get("last_signal_id")
        or inputs.get("candidate_id") != c["id"]
        or not c.get("journal_trade_id")
        or signal.get("journal_trade_id") != c["journal_trade_id"]
        or signal.get("decision") != c.get("last_worker_decision")
        or signal.get("symbol") != c["symbol"]
        or signal.get("ruleset_version") != c["ruleset_version"]):
        raise HTTPException(status_code=409, detail="Candidate/signal traceability is incomplete or inconsistent.")
    if not c.get("operational_state") or c.get("reason_code") == "EVALUATION_PENDING":
        raise HTTPException(status_code=409, detail="Candidate requires a completed prospective evaluation.")
    if c.get("source_discovery_item_id") and (
        not item or item.get("id") != c["source_discovery_item_id"]
        or item.get("symbol") != c["symbol"] or not run
        or item.get("run_id") != run.get("id")
        or run.get("session_date") != c["session_date"]):
        raise HTTPException(status_code=409, detail="Discovery run/item/candidate traceability is incomplete.")
    setup_ready = all(c.get(k) is not None for k in
                      ("trigger_price", "trigger_operator", "entry_price", "stop_price", "target_price"))
    setup_ready = setup_ready and c.get("entry_model") in ENTRY_LABELS and bool(c.get("trigger_definition"))
    decision = {"NO_TRADE": "NO TRADE", "WAIT": "WAIT", "TRADE": "TRADE"}[signal["decision"]]
    reasons = signal.get("wait_reasons") or signal.get("rejection_reasons") or []
    notes = c.get("notes") or ""
    trace = {"run_id": run.get("id") if run else None,
             "discovery_item_id": c.get("source_discovery_item_id"), "candidate_id": c["id"],
             "signal_id": signal["id"], "journal_trade_id": c["journal_trade_id"],
             "lifecycle_revision": c.get("lifecycle_revision", 0)}
    rows = [{"sheet_name": "Premarket Candidates", "key_column": "Candidate ID",
             "key": c["id"], "values": {
        "Date": c["session_date"], "Discovery Phase": "Premarket" if c["discovery_phase"] == "PREMARKET" else "Post-Open Refresh",
        "Ticker": c["symbol"], "Catalyst Summary": c["catalyst_summary"],
        "Catalyst Tier": c["catalyst_tier"], "Ruleset Version": c["ruleset_version"],
        "Planned Entry Model": ENTRY_LABELS.get(c.get("entry_model"), "TBD / None"),
        "Trigger / Level": c.get("trigger_definition") or "",
        "Candidate ID": c["id"], "Signal ID": signal["id"], "Operational State": c["operational_state"],
        "Setup Status": "WORKER_READY" if setup_ready else "SETUP_REQUIRED",
        "Worker Decision": decision, "Final Decision": decision,
        "Wait / Block Reason": c["reason_code"] + (": " + " | ".join(reasons) if reasons else ""),
        "Notes": notes,
    }}, {"sheet_name": "Signal Queue", "key_column": "Signal ID", "key": signal["id"], "values": {
        "Signal ID": signal["id"], "Created At": signal.get("created_at") or signal["evaluated_at"],
        "Decision": decision, "Status": signal["status"], "Symbol": c["symbol"],
        "Direction": c["direction"], "Qty": signal.get("qty"), "Entry Price": signal.get("entry_price"),
        "Stop Price": signal.get("stop_price"), "Target Price": signal.get("target_price"),
        "Triggered At": signal.get("triggered_at"), "Ruleset Version": c["ruleset_version"],
        "Entry Model": c.get("entry_model"), "Market Data Source": signal.get("market_data_source"),
        "Journal Trade ID": c["journal_trade_id"], "Notes": notes,
    }}]
    if run:
        # Do not manufacture channel coverage, liquidity counts, or watchlist totals.
        rows.append({"sheet_name": "Scan Coverage", "key_column": "Run ID", "key": run["id"], "values": {
            "Date": run["session_date"], "Scan Status": {"COMPLETE": "Complete", "PARTIAL": "Partial", "DATA_UNAVAILABLE": "Data Unavailable"}.get(run["status"], "Partial"),
            "Candidates Discovered": run.get("candidates_discovered"),
            "Ruleset Version": run["ruleset_version"], "Notes": run.get("notes") or "", "Run ID": run["id"],
        }})
    return {"mode": "SHADOW", "broker_execution_enabled": False,
            "spreadsheet_id": JOURNAL_SPREADSHEET_ID, "trace": trace, "rows": rows,
            "trade_journal_write_enabled": False}


def load_journal_projection(candidate_id: str):
    c = get_candidate(candidate_id)
    signals = sb_select("strategy_signals", {"select": "*", "id": f"eq.{c.get('last_signal_id')}", "limit": "1"}) if c.get("last_signal_id") else []
    if not signals:
        raise HTTPException(status_code=409, detail="Worker signal is the first missing artifact.")
    item, run = None, None
    if c.get("source_discovery_item_id"):
        items = sb_select("strategy_discovery_items", {"select": "*", "id": f"eq.{c['source_discovery_item_id']}", "limit": "1"})
        item = items[0] if items else None
        runs = sb_select("strategy_discovery_runs", {"select": "*", "id": f"eq.{item['run_id']}", "limit": "1"}) if item else []
        run = runs[0] if runs else None
    result = journal_projection(c, item, run, signals[0])
    # A concurrent lifecycle update invalidates this projection; the writer must
    # request a new plan immediately before applying a Sheets write.
    if get_candidate(candidate_id).get("lifecycle_revision", 0) != c.get("lifecycle_revision", 0):
        raise HTTPException(status_code=409, detail="Candidate changed during journal read; retry projection.")
    return result


class JournalRowIn(BaseModel):
    model_config = {"extra": "forbid"}
    row_number: int = Field(ge=2, le=1000)
    values: dict[str, Any]


class JournalSnapshotIn(BaseModel):
    model_config = {"extra": "forbid"}
    sheet_name: Literal["Premarket Candidates", "Scan Coverage", "Signal Queue"]
    headers: list[str]
    rows: list[JournalRowIn] = Field(max_length=999)
    empty_row_number: int = Field(ge=2, le=1000)


class JournalReconcileIn(BaseModel):
    model_config = {"extra": "forbid"}
    candidate_id: str
    spreadsheet_id: Literal["1C4BAHQBzgU2hC64yIAHfQkwjSIuPm3pc7i-AIKrbk4w"]
    lifecycle_revision: int = Field(ge=0)
    snapshots: list[JournalSnapshotIn] = Field(min_length=2, max_length=3)


def reconcile_journal(projection, request: JournalReconcileIn):
    if request.lifecycle_revision != projection["trace"]["lifecycle_revision"]:
        raise HTTPException(status_code=409, detail="Candidate revision changed before journal write.")
    snapshots = {s.sheet_name: s for s in request.snapshots}
    if len(snapshots) != len(request.snapshots):
        raise HTTPException(status_code=422, detail="Duplicate sheet snapshots.")
    patches = []
    for desired in projection["rows"]:
        snapshot = snapshots.get(desired["sheet_name"])
        if not snapshot or len(snapshot.headers) != len(set(snapshot.headers)) or not set(desired["values"]).issubset(snapshot.headers):
            raise HTTPException(status_code=409, detail="Journal schema is missing required headers or has duplicates.")
        if len({r.row_number for r in snapshot.rows}) != len(snapshot.rows):
            raise HTTPException(status_code=422, detail="Duplicate row numbers in snapshot.")
        matches = [r for r in snapshot.rows if r.values.get(desired["key_column"]) == desired["key"]]
        if len(matches) > 1:
            raise HTTPException(status_code=409, detail="Duplicate journal IDs require reconciliation; no write planned.")
        existing = matches[0] if matches else None
        target = existing.row_number if existing else snapshot.empty_row_number
        if not existing and any(r.row_number == target and any(v is not None and v != "" for v in r.values.values()) for r in snapshot.rows):
            raise HTTPException(status_code=409, detail="Planned insertion row is occupied.")
        values = desired["values"].copy()
        if existing:
            for identity in ("Date", "Ticker", "Symbol", "Journal Trade ID", "Ruleset Version"):
                if existing.values.get(identity) not in (None, "", values.get(identity)) and identity in values:
                    raise HTTPException(status_code=409, detail="Journal row identity conflicts with source records.")
            # Notes remain user owned after insertion; signal history remains one row per signal ID.
            values.pop("Notes", None)
            values = {k: v for k, v in values.items() if existing.values.get(k) != v}
        patches.append({"sheet_name": desired["sheet_name"], "row_number": target,
                        "key_column": desired["key_column"], "key": desired["key"],
                        "action": "INSERT" if not existing else "UPDATE" if values else "NOOP", "values": values})
    return {**{k: v for k, v in projection.items() if k != "rows"}, "patches": patches,
            "write_transport": "CONNECTED_GOOGLE_ACCOUNT", "requires_live_read_before_write": True}


@app.get("/journal/candidates/{candidate_id}")
def get_journal_projection(candidate_id: str, credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme)):
    require_auth(credentials)
    return load_journal_projection(candidate_id)


@app.post("/journal/reconcile")
def plan_journal_reconciliation(request: JournalReconcileIn, credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme)):
    require_auth(credentials)
    return reconcile_journal(load_journal_projection(request.candidate_id), request)
