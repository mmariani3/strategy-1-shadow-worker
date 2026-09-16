import hmac
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Literal

import requests
from fastapi import FastAPI, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, model_validator
from review_contract import CurrentReview, CURRENT_FIELDS, review_problem, evidence_class_problem
from build_info import implementation_version

APP_VERSION = "0.5.0-shadow-orchestrator"
IMPLEMENTATION_VERSION = implementation_version("orchestrator", APP_VERSION)
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
    c = get_candidate(candidate_id)
    sb_insert("strategy_candidate_events", {
        "candidate_id": candidate_id,
        "event_type": event_type,
        "event_at": datetime.now(timezone.utc).isoformat(),
        "market_data_source": (f"alpaca_{ALPACA_DATA_FEED}" if data_timestamp and
                               event_type in ("PRICE_CHECK", "TRIGGER_OBSERVED") else None),
        "data_timestamp": data_timestamp,
        "observed_price": str(observed_price) if observed_price is not None else None,
        "payload": {**(payload or {}), "run_id": c.get("run_id"), "candidate_id": candidate_id,
                    "signal_id": c.get("last_signal_id"), "journal_trade_id": c.get("journal_trade_id"),
                    "ruleset_version": c.get("ruleset_version"), "owner": "orchestrator",
                    "implementation_version": IMPLEMENTATION_VERSION,
                    "previous_state": c.get("operational_state"), "new_state": c.get("operational_state")},
    })


class CatalystSource(BaseModel):
    source: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    headline_or_event: str = Field(min_length=1)
    event_timestamp: datetime


class CandidateIn(BaseModel):
    model_config = {"extra": "forbid"}
    experiment_class: Literal["STRATEGY_1", "INFRASTRUCTURE_TEST"]
    data_kind: Literal["MARKET", "SYNTHETIC"]
    run_id: str | None = None
    current_review: CurrentReview | None = None
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
    current_review: CurrentReview | None = None
    resume_monitoring: bool = False
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
        "experiment_class": c["experiment_class"],
        "data_kind": c.get("data_kind"),
        "session_date": c["session_date"],
        "current_review": c.get("current_review"),
        "confirmation_review_id": c.get("confirmation_review_id"),
        "run_id": c.get("run_id"), "candidate_id": c["id"],
        "source_discovery_item_id": c.get("source_discovery_item_id"),
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
            "candidate_id": c["id"], "run_id": c.get("run_id"),
            "source_discovery_item_id": c.get("source_discovery_item_id"),
            "orchestrator_version": IMPLEMENTATION_VERSION,
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
                       json={**record, "lifecycle_revision": revision + 1,
                             "transition_context": {"owner": "orchestrator",
                                 "implementation_version": IMPLEMENTATION_VERSION,
                                 "reason": record.get("reason_code", "LIFECYCLE_UPDATE"),
                                 "reviewer": (record.get("current_review") or c.get("current_review") or {}).get("reviewer")}}, timeout=15)
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
    updates = review.model_dump(mode="json", exclude={"confirmed", "confirmation_source", "resume_monitoring"}, exclude_none=True)
    # Every review supplies current assessments. Omission explicitly invalidates an old approval.
    for field in CURRENT_FIELDS:
        updates[field] = getattr(review, field, None)
    for field in ("clean_structure", "consolidated_data"):
        updates[field] = getattr(review, field, None)
    updates["current_review"] = review.current_review.model_dump(mode="json") if review.current_review else None
    valid_timestamp(review.data_timestamp)
    if not review.confirmation_source.strip():
        raise HTTPException(status_code=422, detail="A nonblank review/confirmation source is required.")
    return updates


@app.post("/candidates/ingest")
def ingest_candidate(candidate: CandidateIn, credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme)):
    require_auth(credentials)
    record = candidate.model_dump(mode="json")
    problem = evidence_class_problem(candidate.experiment_class, candidate.data_kind, candidate.market_data_source, candidate.notes)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    if candidate.source_discovery_item_id:
        items = sb_select("strategy_discovery_items", {"select": "*", "id": f"eq.{candidate.source_discovery_item_id}", "limit": "1"})
        if not items or items[0].get("run_id") != candidate.run_id or not items[0].get("setup_review"):
            raise HTTPException(status_code=409, detail="Qualified discovery/setup provenance is required.")
        runs = sb_select("strategy_discovery_runs", {"select": "*", "id": f"eq.{candidate.run_id}", "limit": "1"})
        if (not runs or runs[0].get("experiment_class") != candidate.experiment_class
                or str(runs[0].get("session_date")) != str(candidate.session_date)
                or items[0].get("symbol") != candidate.symbol
                or not items[0].get("qualification_review")
                or items[0].get("promotion_status") == "REJECTED"):
            raise HTTPException(status_code=409, detail="Discovery identity, classification, or qualification conflicts.")
        for field in ("entry_model", "trigger_definition", "trigger_operator", "trigger_price", "entry_price", "stop_price", "target_price"):
            expected = items[0]["setup_review"].get(field)
            if str(record.get(field)) != str(expected):
                raise HTTPException(status_code=409, detail=f"Setup handoff changed {field}.")
        for field, expected in items[0]["qualification_review"].items():
            if field not in ("reviewer", "reviewed_at") and record.get(field) != expected:
                raise HTTPException(status_code=409, detail=f"Qualification handoff changed {field}.")
        # Stable before/after setup ID for prospective journal rows. Existing links remain untouched.
        record["id"] = items[0].get("orchestrator_candidate_id") or items[0]["id"]
    if candidate.data_timestamp is not None:
        valid_timestamp(candidate.data_timestamp)
    record.update({"status": "WAITING", "active": True,
                   "operational_state": "HOLD_UNRESOLVED", "reason_code": "EVALUATION_PENDING",
                   "transition_context": {"owner": "orchestrator", "implementation_version": IMPLEMENTATION_VERSION}})
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
    validate_new_review(c, review)
    updates.update({"trigger_confirmed": False, "trigger_confirmed_at": None, "confirmation_review_id": None})
    if review.resume_monitoring:
        require_resume(c, review)
        updates["trigger_observed_at"] = None
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
            # Observation never renews an earlier market/risk/qualification approval.
            problem = review_problem(c)
            if problem:
                update_candidate(c, {"operational_state": "HOLD_UNRESOLVED", "reason_code": problem})
                results.append({"candidate_id": c["id"], "result": problem})
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
    validate_new_review(c, confirmation)
    if confirmation.resume_monitoring and confirmation.confirmed:
        raise HTTPException(status_code=422, detail="A review cannot confirm and resume waiting together.")
    if c.get("data_timestamp") and valid_timestamp(confirmation.data_timestamp) < valid_timestamp(c["data_timestamp"]):
        raise HTTPException(status_code=422, detail="Confirmation data predates the latest candidate review.")
    if confirmation.confirmed:
        if c.get("operational_state") != "CONFIRMATION_REQUIRED" or not c.get("trigger_observed_at"):
            raise HTTPException(status_code=409, detail="Prospective trigger observation is required before confirmation.")
        if valid_timestamp(confirmation.data_timestamp) < valid_timestamp(c["trigger_observed_at"]):
            raise HTTPException(status_code=422, detail="Confirmation data predates trigger observation.")
        updates.update({"trigger_confirmed": True,
                        "trigger_confirmed_at": confirmation.data_timestamp.isoformat(),
                        "confirmation_review_id": str(confirmation.current_review.review_id) if confirmation.current_review else None,
                        "trigger_confirmation_source": confirmation.confirmation_source})
    else:
        updates.update({"trigger_confirmed": False, "trigger_confirmed_at": None, "confirmation_review_id": None})
        if confirmation.resume_monitoring:
            require_resume(c, confirmation)
            updates["trigger_observed_at"] = None
    updates.update({"operational_state": "HOLD_UNRESOLVED", "reason_code": "EVALUATION_PENDING"})
    c = update_candidate(c, updates)
    write_event(c["id"], "TRIGGER_CONFIRMED" if confirmation.confirmed else "UPDATED",
                data_timestamp=confirmation.data_timestamp.isoformat(),
                payload={"confirmation_source": confirmation.confirmation_source,
                         "review": confirmation.model_dump(mode="json")})
    return evaluate_stored(c)


def validate_new_review(c, review):
    previous = (c.get("current_review") or {}).get("review_id")
    if review.current_review and str(review.current_review.review_id) == previous:
        raise HTTPException(status_code=409, detail="A new evaluation requires a new attributable review.")


def require_resume(c, review):
    if not c.get("trigger_observed_at"):
        raise HTTPException(status_code=409, detail="No outstanding observation to resolve.")
    if review.missed_trigger is not False or not review.current_review:
        raise HTTPException(status_code=422, detail="Explicit current setup review and unmissed trigger required to resume.")
    merged = {**c, **context_updates(review), "trigger_confirmed": False}
    if review_problem(merged):
        raise HTTPException(status_code=422, detail="Current review required to resume monitoring.")
    # Clearing only the active pointer supersedes the observation; immutable events retain it.


@app.get("/journal/candidates/{candidate_id}")
def get_journal_projection(candidate_id: str, credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme)):
    require_auth(credentials)
    from journal_projection import candidate_projection
    c = get_candidate(candidate_id)
    signal = None
    if c.get("last_signal_id"):
        rows = sb_select("strategy_signals", {"select": "*", "id": f"eq.{c['last_signal_id']}", "limit": "1"})
        if not rows:
            raise HTTPException(status_code=409, detail="Signal trace missing.")
        signal = rows[0]
    return candidate_projection(c, signal)
