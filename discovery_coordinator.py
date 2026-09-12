import hmac
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Literal
from urllib.parse import urljoin

import requests
from fastapi import FastAPI, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, model_validator

APP_VERSION = "0.1.0-shadow-discovery"
RULESET_VERSION = os.getenv("RULESET_VERSION", "v0.3")

DISCOVERY_SERVICE_TOKEN = os.getenv("DISCOVERY_SERVICE_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "https://strategy-1-shadow-orchestrator.onrender.com")
ORCHESTRATOR_TOKEN = os.getenv("ORCHESTRATOR_TOKEN")
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "Strategy1Research contact@example.com")

app = FastAPI(
    title="Strategy #1 Discovery Coordinator",
    version=APP_VERSION,
    description=(
        "Phase-1 shadow premarket discovery coordinator. It automates wide-net evidence collection "
        "and scan coverage, but does not invent catalyst materiality, tier, or trade qualification."
    ),
)
bearer = HTTPBearer(auto_error=False)

CATALYST_FORMS = {"8-K", "10-Q", "10-K", "6-K"}

def require_auth(credentials: HTTPAuthorizationCredentials | None) -> None:
    if not DISCOVERY_SERVICE_TOKEN:
        raise HTTPException(status_code=503, detail="DISCOVERY_SERVICE_TOKEN is not configured.")
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing bearer token.")
    if not hmac.compare_digest(credentials.credentials, DISCOVERY_SERVICE_TOKEN):
        raise HTTPException(status_code=403, detail="Invalid bearer token.")

def sb_headers(prefer=True):
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Supabase server credentials are not configured.")
    h = {"apikey": SUPABASE_SECRET_KEY, "Content-Type": "application/json"}
    if prefer:
        h["Prefer"] = "return=representation"
    return h

def sb_insert(table: str, record: dict[str, Any]) -> list[dict[str, Any]]:
    r = requests.post(f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table}",
                      headers=sb_headers(), json=record, timeout=20)
    if not r.ok:
        raise HTTPException(status_code=502, detail=f"Supabase insert failed: {r.status_code} {r.text[:500]}")
    return r.json()

def sb_update(table: str, row_id: str, record: dict[str, Any]) -> list[dict[str, Any]]:
    r = requests.patch(f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table}",
                       headers=sb_headers(), params={"id": f"eq.{row_id}"},
                       json=record, timeout=20)
    if not r.ok:
        raise HTTPException(status_code=502, detail=f"Supabase update failed: {r.status_code} {r.text[:500]}")
    return r.json()

def sb_select(table: str, params: dict[str, str]) -> list[dict[str, Any]]:
    r = requests.get(f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table}",
                     headers=sb_headers(prefer=False), params=params, timeout=20)
    if not r.ok:
        raise HTTPException(status_code=502, detail=f"Supabase query failed: {r.status_code} {r.text[:500]}")
    return r.json()

def alpaca_headers():
    if not ALPACA_API_KEY or not ALPACA_API_SECRET:
        raise HTTPException(status_code=503, detail="Alpaca data credentials are not configured.")
    return {"APCA-API-KEY-ID": ALPACA_API_KEY, "APCA-API-SECRET-KEY": ALPACA_API_SECRET}

def fetch_movers(top=20):
    r = requests.get("https://data.alpaca.markets/v1beta1/screener/stocks/movers",
                     headers=alpaca_headers(), params={"top": top}, timeout=15)
    if not r.ok:
        raise RuntimeError(f"Alpaca movers failed: {r.status_code} {r.text[:250]}")
    return r.json()

def fetch_news(hours=18):
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)
    r = requests.get(
        "https://data.alpaca.markets/v1beta1/news",
        headers=alpaca_headers(),
        params={
            "start": start.isoformat(),
            "end": end.isoformat(),
            "sort": "desc",
            "limit": 50,
            "include_content": "false",
        },
        timeout=20,
    )
    if not r.ok:
        raise RuntimeError(f"Alpaca news failed: {r.status_code} {r.text[:250]}")
    return r.json()

def sec_headers():
    return {"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}

def fetch_ticker_map():
    r = requests.get("https://www.sec.gov/files/company_tickers.json", headers=sec_headers(), timeout=20)
    if not r.ok:
        raise RuntimeError(f"SEC ticker map failed: {r.status_code}")
    raw = r.json()
    return {v["ticker"].upper(): int(v["cik_str"]) for v in raw.values()}

def fetch_recent_sec(symbol: str, cik: int, days=3):
    cik10 = str(cik).zfill(10)
    r = requests.get(f"https://data.sec.gov/submissions/CIK{cik10}.json",
                     headers=sec_headers(), timeout=20)
    if not r.ok:
        return []
    data = r.json()
    recent = (data.get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    filing_dates = recent.get("filingDate") or []
    accessions = recent.get("accessionNumber") or []
    docs = recent.get("primaryDocument") or []
    cutoff = date.today() - timedelta(days=days)
    out = []
    for form, fdate, accession, doc in zip(forms, filing_dates, accessions, docs):
        try:
            d = date.fromisoformat(fdate)
        except Exception:
            continue
        if d < cutoff or form not in CATALYST_FORMS:
            continue
        acc_nodash = accession.replace("-", "")
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nodash}/{doc}"
        out.append({
            "source": "SEC EDGAR",
            "source_type": "regulatory_filing",
            "form": form,
            "filing_date": fdate,
            "accession": accession,
            "url": url,
        })
    return out

def classify_channel(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ("earnings", "revenue", "eps", "guidance", "outlook", "quarter", "forecast")):
        return "earnings_guidance"
    if any(k in t for k in ("upgrade", "downgrade", "price target", "initiated", "analyst")):
        return "analyst_actions"
    if any(k in t for k in ("acquisition", "acquire", "merger", "contract", "customer", "fda", "regulatory",
                            "buyback", "capital raise", "offering", "ceo", "management", "product launch")):
        return "corporate_news"
    if any(k in t for k in ("sector", "industry", "competitor", "peer", "semiconductor", "banking", "biotech",
                            "software", "energy", "retail")):
        return "sector_industry"
    return "company_news_other"

def normalize_mover_rows(body):
    rows = []
    for side in ("gainers", "losers"):
        for rank, item in enumerate(body.get(side, []) or [], start=1):
            symbol = (item.get("symbol") or "").upper()
            if not symbol:
                continue
            rows.append((symbol, {
                "side": side[:-1] if side.endswith("s") else side,
                "rank": rank,
                "price": item.get("price"),
                "change": item.get("change"),
                "percent_change": item.get("percent_change"),
                "source": "alpaca_screener_movers",
                "source_note": "Alpaca documents this endpoint as SIP-based movers data.",
            }))
    return rows

def normalize_news(body):
    articles = body.get("news") or body.get("articles") or []
    by_symbol: dict[str, list[dict[str, Any]]] = {}
    channel_seen = set()
    for a in articles:
        headline = a.get("headline") or ""
        summary = a.get("summary") or ""
        category = classify_channel(headline + " " + summary)
        channel_seen.add(category)
        evidence = {
            "source": a.get("source") or a.get("author") or "Alpaca News",
            "source_type": "financial_news",
            "headline_or_event": headline,
            "summary": summary,
            "event_timestamp": a.get("created_at") or a.get("updated_at"),
            "url": a.get("url"),
            "category": category,
            "alpaca_news_id": a.get("id"),
        }
        for sym in a.get("symbols") or []:
            s = str(sym).upper().strip()
            if s:
                by_symbol.setdefault(s, []).append(evidence)
    return by_symbol, channel_seen

class ScanRequest(BaseModel):
    session_date: date
    phase: Literal["PREMARKET", "POST_OPEN"] = "PREMARKET"
    movers_top: int = Field(default=20, ge=5, le=50)
    news_hours: int = Field(default=18, ge=1, le=48)

class CatalystSourceIn(BaseModel):
    source: str
    source_type: str
    headline_or_event: str
    event_timestamp: datetime

class PromoteRequest(BaseModel):
    direction: Literal["LONG", "SHORT"]
    catalyst_tier: Literal["A", "B"]
    catalyst_material: bool
    materiality_rationale: str = Field(min_length=1)
    catalyst_verified: bool
    catalyst_cross_source_verified: bool
    catalyst_sources: list[CatalystSourceIn] = Field(min_length=2)

    market_data_source: str
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

    entry_model: Literal[
        "opening_range_premarket_high_break",
        "vwap_reclaim_rejection",
        "first_clean_pullback",
    ]
    trigger_definition: str = Field(min_length=1)
    trigger_price: Decimal
    trigger_operator: Literal["GTE", "LTE"]
    entry_price: Decimal
    stop_price: Decimal
    target_price: Decimal

    realized_daily_loss_dollars: Decimal | None = None
    executed_trades_today: int | None = None
    after_first_minute: bool | None = None
    missed_trigger: bool | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def enforce_catalyst(self):
        if not self.catalyst_material or not self.catalyst_verified or not self.catalyst_cross_source_verified:
            raise ValueError("Promotion requires material, verified, cross-source-verified catalyst evidence.")
        return self

@app.get("/health")
def health():
    return {
        "ok": True,
        "mode": "SHADOW",
        "version": APP_VERSION,
        "ruleset_version": RULESET_VERSION,
        "broker_execution_enabled": False,
        "automatic_materiality_or_tier_assignment": False,
        "macro_calendar_integrated": False,
    }

@app.post("/scan/run-once")
def run_scan(req: ScanRequest, credentials: HTTPAuthorizationCredentials | None = Security(bearer)):
    require_auth(credentials)
    run = sb_insert("strategy_discovery_runs", {
        "session_date": req.session_date.isoformat(),
        "phase": req.phase,
        "ruleset_version": RULESET_VERSION,
        "status": "IN_PROGRESS",
        "channel_status": {},
        "notes": f"Discovery Coordinator {APP_VERSION}",
    })[0]

    channel_status = {
        "earnings_guidance": "DATA_UNAVAILABLE",
        "corporate_news": "DATA_UNAVAILABLE",
        "analyst_actions": "DATA_UNAVAILABLE",
        "sector_industry": "DATA_UNAVAILABLE",
        "premarket_movers_unusual_activity": "DATA_UNAVAILABLE",
        "macro_economic_calendar": "DATA_UNAVAILABLE_NOT_INTEGRATED",
        "cross_source_verification": "REVIEW_REQUIRED",
    }
    errors = []
    movers = {}
    news_by_symbol = {}
    news_channels = set()

    try:
        mover_body = fetch_movers(req.movers_top)
        for symbol, snap in normalize_mover_rows(mover_body):
            movers[symbol] = snap
        channel_status["premarket_movers_unusual_activity"] = "CHECKED_ALPACA_SCREENER"
    except Exception as e:
        errors.append(str(e))

    try:
        news_body = fetch_news(req.news_hours)
        news_by_symbol, news_channels = normalize_news(news_body)
        channel_status["earnings_guidance"] = "CHECKED_ALPACA_NEWS"
        channel_status["corporate_news"] = "CHECKED_ALPACA_NEWS"
        channel_status["analyst_actions"] = "CHECKED_ALPACA_NEWS"
        channel_status["sector_industry"] = "CHECKED_ALPACA_NEWS"
    except Exception as e:
        errors.append(str(e))

    symbols = sorted(set(movers) | set(news_by_symbol))
    ticker_map = {}
    try:
        ticker_map = fetch_ticker_map()
    except Exception as e:
        errors.append(str(e))

    inserted = 0
    for symbol in symbols:
        sec_evidence = []
        if symbol in ticker_map:
            try:
                sec_evidence = fetch_recent_sec(symbol, ticker_map[symbol])
            except Exception:
                sec_evidence = []

        evidence = news_by_symbol.get(symbol, [])
        categories = [e.get("category") for e in evidence if e.get("category")]
        category = categories[0] if categories else ("mover_unexplained" if symbol in movers else None)

        verification = "EVIDENCE_PRESENT" if evidence and sec_evidence else "REVIEW_REQUIRED"
        discovered_via = []
        if symbol in movers:
            discovered_via.append("alpaca_movers")
        if evidence:
            discovered_via.append("alpaca_news")
        if sec_evidence:
            discovered_via.append("sec_edgar_recent_filing")

        try:
            sb_insert("strategy_discovery_items", {
                "run_id": run["id"],
                "symbol": symbol,
                "discovered_via": discovered_via,
                "mover_snapshot": movers.get(symbol, {}),
                "news_evidence": evidence,
                "independent_evidence": sec_evidence,
                "catalyst_category": category,
                "provisional_tier": None,
                "verification_status": verification,
                "promotion_status": "REVIEW_REQUIRED",
                "notes": "No automatic catalyst tier/materiality assignment. Human/independent review required before promotion.",
            })
            inserted += 1
        except HTTPException:
            raise
        except Exception:
            pass

    status = "PARTIAL"
    notes = (
        "Wide-net collection completed. Macro/economic calendar is not integrated, so scan cannot be marked Complete. "
        "Alpaca news plus SEC EDGAR may provide independent evidence for some candidates, but catalyst materiality/tier "
        "and watchlist cross-source verification remain explicit review gates."
    )
    if errors:
        notes += " Errors: " + " | ".join(errors[:5])

    sb_update("strategy_discovery_runs", run["id"], {
        "status": status,
        "channel_status": channel_status,
        "candidates_discovered": inserted,
        "notes": notes,
    })
    return {
        "run_id": run["id"],
        "status": status,
        "candidates_discovered": inserted,
        "channel_status": channel_status,
        "errors": errors,
        "automatic_promotion": False,
    }

@app.get("/runs/latest")
def latest_run(credentials: HTTPAuthorizationCredentials | None = Security(bearer)):
    require_auth(credentials)
    runs = sb_select("strategy_discovery_runs", {"select": "*", "order": "created_at.desc", "limit": "1"})
    if not runs:
        return None
    run = runs[0]
    items = sb_select("strategy_discovery_items", {
        "select": "*",
        "run_id": f"eq.{run['id']}",
        "order": "created_at.asc",
    })
    return {"run": run, "items": items}

@app.post("/items/{item_id}/promote")
def promote(item_id: str, review: PromoteRequest,
            credentials: HTTPAuthorizationCredentials | None = Security(bearer)):
    require_auth(credentials)
    if not ORCHESTRATOR_TOKEN:
        raise HTTPException(status_code=503, detail="ORCHESTRATOR_TOKEN is not configured.")
    items = sb_select("strategy_discovery_items", {"select": "*", "id": f"eq.{item_id}", "limit": "1"})
    if not items:
        raise HTTPException(status_code=404, detail="Discovery item not found.")
    item = items[0]
    runs = sb_select("strategy_discovery_runs", {"select": "*", "id": f"eq.{item['run_id']}", "limit": "1"})
    if not runs:
        raise HTTPException(status_code=404, detail="Discovery run not found.")
    run = runs[0]

    summary = None
    if item.get("news_evidence"):
        summary = item["news_evidence"][0].get("headline_or_event")
    if not summary:
        summary = f"Reviewed catalyst evidence for {item['symbol']}"

    body = {
        "session_date": run["session_date"],
        "discovery_phase": run["phase"],
        "symbol": item["symbol"],
        "direction": review.direction,
        "ruleset_version": RULESET_VERSION,
        "market_data_source": review.market_data_source,
        "consolidated_data": review.consolidated_data,
        "consolidated_data_required": review.consolidated_data_required,
        "market_regime": review.market_regime,
        "market_context_ok": review.market_context_ok,
        "liquidity_ok": review.liquidity_ok,
        "participation_ok": review.participation_ok,
        "relative_strength_ok": review.relative_strength_ok,
        "price_extended_or_chasing": review.price_extended_or_chasing,
        "major_macro_event_imminent": review.major_macro_event_imminent,
        "stop_would_widen": review.stop_would_widen,
        "fomo_or_revenge_motive": review.fomo_or_revenge_motive,
        "target_validated": review.target_validated,
        "clean_structure": review.clean_structure,
        "catalyst_summary": summary,
        "catalyst_tier": review.catalyst_tier,
        "catalyst_event_at": review.catalyst_sources[0].event_timestamp.isoformat(),
        "catalyst_material": review.catalyst_material,
        "materiality_rationale": review.materiality_rationale,
        "catalyst_verified": review.catalyst_verified,
        "catalyst_cross_source_verified": review.catalyst_cross_source_verified,
        "catalyst_sources": [s.model_dump(mode="json") for s in review.catalyst_sources],
        "entry_model": review.entry_model,
        "trigger_definition": review.trigger_definition,
        "trigger_price": str(review.trigger_price),
        "trigger_operator": review.trigger_operator,
        "entry_price": str(review.entry_price),
        "stop_price": str(review.stop_price),
        "target_price": str(review.target_price),
        "realized_daily_loss_dollars": str(review.realized_daily_loss_dollars) if review.realized_daily_loss_dollars is not None else None,
        "executed_trades_today": review.executed_trades_today,
        "after_first_minute": review.after_first_minute,
        "missed_trigger": review.missed_trigger,
        "notes": (review.notes or "") + f" | Promoted from discovery item {item_id}",
    }
    r = requests.post(
        f"{ORCHESTRATOR_URL.rstrip('/')}/candidates/ingest",
        headers={"Authorization": f"Bearer {ORCHESTRATOR_TOKEN}", "Content-Type": "application/json"},
        json=body,
        timeout=25,
    )
    if not r.ok:
        raise HTTPException(status_code=502, detail=f"Orchestrator promotion failed: {r.status_code} {r.text[:500]}")
    result = r.json()
    sb_update("strategy_discovery_items", item_id, {
        "provisional_tier": review.catalyst_tier,
        "verification_status": "VERIFIED",
        "materiality_rationale": review.materiality_rationale,
        "promotion_status": "PROMOTED",
        "orchestrator_candidate_id": result.get("candidate_id"),
    })
    return {"discovery_item_id": item_id, "orchestrator": result}
