import hmac
import json
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Literal

import requests
from fastapi import FastAPI, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, model_validator
from review_contract import CurrentReview, readiness_problem
from build_info import implementation_version
from discovery_collection import collect_news, collect_ism_calendar, collect_weekly_calendar
from premarket_collection import collect_premarket
from premarket_evidence_collection import collect_premarket_with_prior
from shadow_evidence_routes import router as shadow_evidence_router
from coordinator_acceptance_controls import active as acceptance_controls, coverage_ledger
from catalyst_source_evidence import SourceCollector
from shadow_evidence_workflow import attach_prior_evidence

APP_VERSION = "0.13.0-coordinator-acceptance-local"
IMPLEMENTATION_VERSION = implementation_version("discovery_coordinator", APP_VERSION)
RULESET_VERSION = os.getenv("RULESET_VERSION", "v0.3")

DISCOVERY_SERVICE_TOKEN = os.getenv("DISCOVERY_SERVICE_TOKEN")
DISCOVERY_SCHEDULER_TOKEN = os.getenv("DISCOVERY_SCHEDULER_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET")
ORCHESTRATOR_URL = os.getenv(
    "ORCHESTRATOR_URL",
    "https://strategy-1-shadow-orchestrator.onrender.com",
)
ORCHESTRATOR_TOKEN = os.getenv("ORCHESTRATOR_TOKEN")
SEC_USER_AGENT = os.getenv(
    "SEC_USER_AGENT",
    "Strategy1Research contact@example.com",
)
FRED_API_KEY = os.getenv("FRED_API_KEY")

app = FastAPI(
    title="Strategy #1 Discovery Coordinator",
    version=APP_VERSION,
    description=(
        "Phase-1 shadow premarket discovery coordinator. It automates wide-net "
        "evidence collection and scan coverage, but does not invent catalyst "
        "materiality, catalyst tier, cross-source verification, or trade qualification."
    ),
)

bearer = HTTPBearer(auto_error=False)
app.include_router(shadow_evidence_router)

CATALYST_FORMS = {"8-K", "10-Q", "10-K", "6-K"}


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
    configured_tokens = [
        token
        for token in (
            DISCOVERY_SERVICE_TOKEN,
            DISCOVERY_SCHEDULER_TOKEN,
        )
        if token
    ]
    if not configured_tokens:
        raise HTTPException(
            status_code=503,
            detail=(
                "No discovery authentication token is configured."
            ),
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing bearer token.")

    if not any(
        hmac.compare_digest(credentials.credentials, token)
        for token in configured_tokens
    ):
        raise HTTPException(status_code=403, detail="Invalid bearer token.")


def sb_headers(prefer: bool = True) -> dict[str, str]:
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        raise HTTPException(
            status_code=503,
            detail="Supabase server credentials are not configured.",
        )
    headers = {
        "apikey": SUPABASE_SECRET_KEY,
        **({"Authorization": f"Bearer {SUPABASE_SECRET_KEY}"}
           if SUPABASE_SECRET_KEY.count(".") == 2 else {}),
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = "return=representation"
    return headers


def attributable(record):
    if acceptance_controls():
        return {**record, "transition_context": acceptance_controls().context.copy()}
    review = record.get("qualification_review") or record.get("rejection_review") or (record.get("setup_review") or {}).get("current_review") or {}
    return {**record, "transition_context": {"owner": "discovery_coordinator",
        "implementation_version": IMPLEMENTATION_VERSION, "reviewer": review.get("reviewer"),
        "reason": record.get("operational_state") or record.get("promotion_status") or record.get("status") or "DISCOVERY_UPDATE"}}


def sb_insert(
    table: str,
    record: dict[str, Any],
) -> list[dict[str, Any]]:
    if acceptance_controls():
        raise HTTPException(403, "USE_BOUNDED_ACCEPTANCE_STORAGE_ONLY")
    r = requests.post(
        f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table}",
        headers=sb_headers(),
        json=attributable(record),
        timeout=20,
    )
    if not r.ok:
        raise HTTPException(
            status_code=502,
            detail=f"Supabase insert failed: {r.status_code} {r.text[:500]}",
        )
    return r.json()


def sb_update(
    table: str,
    row_id: str,
    record: dict[str, Any],
) -> list[dict[str, Any]]:
    if acceptance_controls():
        raise HTTPException(403, "ITEM_MUTATIONS_DISABLED_DURING_ACCEPTANCE")
    r = requests.patch(
        f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table}",
        headers=sb_headers(),
        params={"id": f"eq.{row_id}"},
        json=attributable(record),
        timeout=20,
    )
    if not r.ok:
        raise HTTPException(
            status_code=502,
            detail=f"Supabase update failed: {r.status_code} {r.text[:500]}",
        )

    rows = r.json()
    if not rows:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Supabase update matched zero rows for "
                f"{table} id={row_id}"
            ),
        )
    return rows


def finalize_discovery_run(
    run_key: str,
    record: dict[str, Any],
) -> dict[str, Any]:
    """
    Finalize by deterministic run_key and verify the persisted result.

    This prevents an HTTP-success/zero-row PATCH from leaving a run
    silently stuck in IN_PROGRESS.
    """
    controls = acceptance_controls()
    if controls:
        r = controls.database("PATCH", "strategy_discovery_runs", headers=sb_headers(),
                              params={"run_key": "eq."+run_key}, body=record)
    else:
        r = requests.patch(
            f"{SUPABASE_URL.rstrip('/')}/rest/v1/strategy_discovery_runs",
            headers=sb_headers(),
            params={"run_key": f"eq.{run_key}"},
            json=attributable(record),
            timeout=20,
        )
    if not r.ok:
        raise HTTPException(
            status_code=502,
            detail=(
                "Supabase discovery-run finalization failed: "
                f"HTTP {r.status_code}"
            ),
        )

    rows = r.json()
    if len(rows) != 1:
        raise HTTPException(
            status_code=502,
            detail=(
                "Discovery-run finalization did not update exactly "
                f"one row for run_key={run_key}; matched={len(rows)}"
            ),
        )

    persisted = get_existing_run_by_key(run_key)
    if not persisted:
        raise HTTPException(
            status_code=502,
            detail=(
                "Discovery-run finalization verification failed: "
                "run could not be re-read."
            ),
        )

    if persisted.get("status") == "IN_PROGRESS":
        raise HTTPException(
            status_code=502,
            detail=(
                "Discovery-run finalization verification failed: "
                "status is still IN_PROGRESS."
            ),
        )

    if controls and any(persisted.get(k) != v for k, v in record.items()):
        raise HTTPException(502, "RUN_FINALIZATION_READBACK_MISMATCH")

    expected_count = record.get("candidates_discovered")
    if (
        expected_count is not None
        and persisted.get("candidates_discovered") != expected_count
    ):
        raise HTTPException(
            status_code=502,
            detail=(
                "Discovery-run finalization verification failed: "
                "candidate count mismatch."
            ),
        )

    return persisted


def sb_select(
    table: str,
    params: dict[str, str],
) -> list[dict[str, Any]]:
    if acceptance_controls():
        r = acceptance_controls().database("GET", table, headers=sb_headers(False), params=params)
    else:
        r = requests.get(
        f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table}",
        headers=sb_headers(prefer=False),
        params=params,
        timeout=20,
        )
    if not r.ok:
        raise HTTPException(
            status_code=502,
            detail=f"Supabase query failed: HTTP {r.status_code}",
        )
    return r.json()



def make_run_key(req: "ScanRequest") -> str:
    """
    Deterministic idempotency key for one logical discovery scan.
    Retries for the same Strategy #1 session/phase/ruleset/run class
    return the existing run instead of creating duplicate evidence.
    """
    return "|".join(
        [
            "STRATEGY_1",
            req.session_date.isoformat(),
            req.phase,
            RULESET_VERSION,
            req.run_class,
        ]
    )


def get_existing_run_by_key(run_key: str) -> dict[str, Any] | None:
    rows = sb_select(
        "strategy_discovery_runs",
        {
            "select": "*",
            "run_key": f"eq.{run_key}",
            "limit": "1",
        },
    )
    return rows[0] if rows else None


def create_run_once(
    req: "ScanRequest",
    run_key: str,
) -> tuple[dict[str, Any], bool]:
    """
    Create the run exactly once.

    Returns (run, created_new). The unique database index is the
    authoritative duplicate guard. A race between two retries is
    handled by re-reading the existing row after a uniqueness conflict.
    """
    if acceptance_controls():
        return acceptance_controls().claim(req, run_key, headers=sb_headers())
    existing = get_existing_run_by_key(run_key)
    if existing:
        return existing, False

    payload = {
        "session_date": req.session_date.isoformat(),
        "phase": req.phase,
        "ruleset_version": RULESET_VERSION,
        "run_key": run_key,
        "experiment_class": req.run_class,
        "status": "IN_PROGRESS",
        "channel_status": {},
        "notes": (
            f"{req.run_class} | "
            f"Discovery Coordinator {APP_VERSION}"
        ),
    }

    r = requests.post(
        f"{SUPABASE_URL.rstrip('/')}/rest/v1/strategy_discovery_runs",
        headers=sb_headers(),
        json=attributable(payload),
        timeout=20,
    )

    if r.ok:
        return r.json()[0], True

    # PostgreSQL unique-violation code 23505 is expected if two
    # identical requests race. Re-read the winner instead of failing.
    if r.status_code in (409, 400) and "23505" in r.text:
        existing = get_existing_run_by_key(run_key)
        if existing:
            return existing, False

    raise HTTPException(
        status_code=502,
        detail=(
            "Supabase idempotent run insert failed: "
            f"{r.status_code} {r.text[:500]}"
        ),
    )


def alpaca_headers() -> dict[str, str]:
    if not ALPACA_API_KEY or not ALPACA_API_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Alpaca data credentials are not configured.",
        )
    return {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_API_SECRET,
    }


def source_get(url, **kwargs):
    controls = acceptance_controls()
    return controls.source_get(url, **kwargs) if controls else requests.get(url, **kwargs)


def fetch_movers(top: int = 20) -> dict[str, Any]:
    r = source_get(
        "https://data.alpaca.markets/v1beta1/screener/stocks/movers",
        headers=alpaca_headers(),
        params={"top": top},
        timeout=15,
    )
    if not r.ok:
        raise RuntimeError(
            f"Alpaca movers failed: {r.status_code} {r.text[:250]}"
        )
    return r.json()


def fetch_news(hours: int = 96) -> dict[str, Any]:
    return collect_news(alpaca_headers(), hours, get=source_get,
                        include_content=acceptance_controls() is not None)


def fetch_fred_release_calendar(
    session_date: date,
) -> list[dict[str, Any]]:
    """
    Fetch the FRED release calendar and retain releases scheduled for
    session_date.

    This is coverage/audit data only. The coordinator does NOT decide
    whether a release is "major" or "imminent"; those strategy judgments
    remain explicit structured inputs until the governing rules define a
    deterministic method.
    """
    if not FRED_API_KEY:
        raise RuntimeError("FRED_API_KEY is not configured.")

    r = source_get(
        "https://api.stlouisfed.org/fred/releases/dates",
        params={
            "api_key": FRED_API_KEY,
            "file_type": "json",
            "include_release_dates_with_no_data": "true",
            "order_by": "release_date",
            "sort_order": "desc",
            "limit": 1000,
        },
        timeout=20,
    )
    if not r.ok:
        raise RuntimeError(
            f"FRED release calendar failed: {r.status_code} {r.text[:250]}"
        )

    body = r.json()
    raw_events = body.get("release_dates") or []
    target = session_date.isoformat()

    events: list[dict[str, Any]] = []
    for event in raw_events:
        event_date = (
            event.get("date")
            or event.get("release_date")
        )
        if event_date != target:
            continue

        events.append(
            {
                "source": "FRED",
                "source_type": "official_economic_release_calendar",
                "release_id": event.get("release_id"),
                "release_name": event.get("release_name"),
                "release_date": event_date,
                "release_last_updated": event.get("release_last_updated"),
                "source_endpoint": "fred/releases/dates",
            }
        )

    return events


def sec_headers() -> dict[str, str]:
    return {
        "User-Agent": SEC_USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
    }


def fetch_ticker_map() -> dict[str, int]:
    r = source_get(
        "https://www.sec.gov/files/company_tickers.json",
        headers=sec_headers(),
        timeout=20,
    )
    if not r.ok:
        raise RuntimeError(f"SEC ticker map failed: {r.status_code}")

    raw = r.json()
    return {
        v["ticker"].upper(): int(v["cik_str"])
        for v in raw.values()
    }


def fetch_recent_sec(
    symbol: str,
    cik: int,
    days: int = 3,
) -> list[dict[str, Any]]:
    cik10 = str(cik).zfill(10)

    r = source_get(
        f"https://data.sec.gov/submissions/CIK{cik10}.json",
        headers=sec_headers(),
        timeout=20,
    )
    if not r.ok:
        return []

    data = r.json()
    recent = (data.get("filings") or {}).get("recent") or {}

    forms = recent.get("form") or []
    filing_dates = recent.get("filingDate") or []
    accessions = recent.get("accessionNumber") or []
    docs = recent.get("primaryDocument") or []

    controls = acceptance_controls()
    if controls and (not isinstance(data.get("filings"), dict)
            or not isinstance(data["filings"].get("recent"), dict)
            or any(not isinstance(recent.get(k), list) for k in
                   ("form", "filingDate", "accessionNumber", "primaryDocument"))
            or len({len(forms), len(filing_dates), len(accessions), len(docs)}) != 1):
        raise ValueError("SEC_RESPONSE_UNVERIFIED")
    cutoff = (controls.day if controls else date.today()) - timedelta(days=days)
    out = []

    for form, fdate, accession, doc in zip(
        forms,
        filing_dates,
        accessions,
        docs,
    ):
        try:
            filing_date = date.fromisoformat(fdate)
        except Exception:
            if controls:
                raise ValueError("SEC_DATE_UNVERIFIED") from None
            continue

        if controls and filing_date > controls.day:
            raise ValueError("SEC_FUTURE_FILING_UNVERIFIED")

        if filing_date < cutoff or form not in CATALYST_FORMS:
            continue

        acc_nodash = accession.replace("-", "")
        url = (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{cik}/{acc_nodash}/{doc}"
        )

        out.append(
            {
                "source": "SEC EDGAR",
                "source_type": "regulatory_filing",
                "issuer_cik": str(cik),
                "form": form,
                "filing_date": fdate,
                "accession": accession,
                "url": url,
            }
        )

    return out


def classify_channel(text: str) -> str:
    t = text.lower()

    if any(
        k in t
        for k in (
            "earnings",
            "revenue",
            "eps",
            "guidance",
            "outlook",
            "quarter",
            "forecast",
        )
    ):
        return "earnings_guidance"

    if any(
        k in t
        for k in (
            "upgrade",
            "downgrade",
            "price target",
            "initiated",
            "analyst",
        )
    ):
        return "analyst_actions"

    if any(
        k in t
        for k in (
            "acquisition",
            "acquire",
            "merger",
            "contract",
            "customer",
            "fda",
            "regulatory",
            "buyback",
            "capital raise",
            "offering",
            "ceo",
            "management",
            "product launch",
        )
    ):
        return "corporate_news"

    if any(
        k in t
        for k in (
            "sector",
            "industry",
            "competitor",
            "peer",
            "semiconductor",
            "banking",
            "biotech",
            "software",
            "energy",
            "retail",
        )
    ):
        return "sector_industry"

    return "company_news_other"


def normalize_mover_rows(
    body: dict[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    rows = []

    for side in ("gainers", "losers"):
        for rank, item in enumerate(
            body.get(side, []) or [],
            start=1,
        ):
            symbol = (item.get("symbol") or "").upper()
            if not symbol:
                continue

            rows.append(
                (
                    symbol,
                    {
                        "side": side[:-1]
                        if side.endswith("s")
                        else side,
                        "rank": rank,
                        "price": item.get("price"),
                        "change": item.get("change"),
                        "percent_change": item.get(
                            "percent_change"
                        ),
                        "source": "alpaca_screener_movers",
                        "source_note": (
                            "SIP regular-session mover reference. Before market open "
                            "this endpoint shows the previous trading day's movers. "
                            "Not current premarket price, gap, volume or liquidity."
                        ),
                        "premarket_usable": False,
                        "provider_updated_at": body.get("updated_at"),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            )

    return rows


def normalize_news(
    body: dict[str, Any],
) -> tuple[
    dict[str, list[dict[str, Any]]],
    set[str],
]:
    articles = body.get("news") or body.get("articles") or []
    by_symbol: dict[str, list[dict[str, Any]]] = {}
    channel_seen: set[str] = set()

    for article in articles:
        headline = article.get("headline") or ""
        summary = article.get("summary") or ""
        category = classify_channel(
            headline + " " + summary
        )
        channel_seen.add(category)

        symbols = [
            str(sym).upper().strip()
            for sym in (article.get("symbols") or [])
            if str(sym).strip()
        ]

        for symbol in symbols:
            evidence = {
                "source": (
                    article.get("source")
                    or article.get("author")
                    or "Alpaca News"
                ),
                "source_type": "financial_news",
                "headline_or_event": headline,
                "summary": summary,
                "published_at": article.get("created_at"),
                "updated_at": article.get("updated_at"),
                "event_timestamp": None,
                "feed_timestamp": (
                    article.get("created_at")
                    or article.get("updated_at")
                ),
                "event_timestamp_verified": False,
                "url": article.get("url"),
                "category": category,
                "alpaca_news_id": article.get("id"),
                "article_symbol_count": len(symbols),
                "symbol_specific": False,
                "symbol_relationship": "REVIEW_REQUIRED",
            }
            by_symbol.setdefault(
                symbol,
                [],
            ).append(evidence)

    return by_symbol, channel_seen


def build_quality_flags(
    symbol: str,
    mover_snapshot: dict[str, Any],
    evidence: list[dict[str, Any]],
    sec_evidence: list[dict[str, Any]],
) -> list[str]:
    """
    These are review flags only.
    They do NOT redefine Strategy #1 qualification rules.
    """
    flags: list[str] = []

    # A prior-session reference cannot evaluate today's soft price guideline.
    price = mover_snapshot.get("price") if mover_snapshot.get("premarket_usable") else None
    if price is not None:
        try:
            if float(price) < 5:
                flags.append(
                    "BELOW_GENERAL_$5_UNIVERSE_GUIDELINE"
                )
        except Exception:
            pass

    if mover_snapshot and not evidence:
        flags.append("MOVER_WITHOUT_NEWS_EXPLANATION")

    if mover_snapshot:
        flags.append("REGULAR_SESSION_MOVER_NOT_PREMARKET_DATA")

    if evidence:
        flags.append("UNDERLYING_EVENT_TIME_AND_SYMBOL_RELATIONSHIP_UNVERIFIED")

    if evidence and all(
        not item.get("symbol_specific", False)
        for item in evidence
    ):
        flags.append("SYMBOL_SPECIFIC_CATALYST_UNVERIFIED")

    if not sec_evidence:
        flags.append("NO_RECENT_DIRECT_SEC_EVIDENCE")

    return flags


class ScanRequest(BaseModel):
    session_date: date
    include_dated_prior_evidence: bool = Field(default=False, strict=True)
    phase: Literal[
        "PREMARKET",
        "POST_OPEN",
    ] = "PREMARKET"

    run_class: Literal[
        "STRATEGY_1",
        "INFRASTRUCTURE_TEST",
    ]

    movers_top: int = Field(
        default=20,
        ge=5,
        le=50,
    )
    news_hours: int = Field(
        default=96,
        ge=1,
        le=168,
    )


class CatalystSourceIn(BaseModel):
    source: str
    source_type: str
    headline_or_event: str
    event_timestamp: datetime


class PromoteRequest(BaseModel):
    setup_rationale: str | None = None
    direction: Literal[
        "LONG",
        "SHORT",
    ]

    catalyst_tier: Literal[
        "A",
        "B",
    ]

    catalyst_material: bool
    materiality_rationale: str = Field(min_length=1)
    catalyst_verified: bool
    catalyst_cross_source_verified: bool

    catalyst_sources: list[
        CatalystSourceIn
    ] = Field(min_length=2)

    market_data_source: str

    consolidated_data: bool | None = None
    consolidated_data_required: bool | None = None

    market_regime: Literal[
        "Bullish",
        "Bearish",
        "Mixed",
        "Choppy",
    ] | None = None

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
        if (
            not self.catalyst_material
            or not self.catalyst_verified
            or not self.catalyst_cross_source_verified
        ):
            raise ValueError(
                "Promotion requires material, verified, "
                "cross-source-verified catalyst evidence."
            )
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
        "automatic_cross_source_verification": False,
        "macro_calendar_integrated": True,
        "macro_calendar_source": "FRED_ISM_AND_FOREX_FACTORY_SUPPLEMENTS",
        "macro_calendar_coverage_complete": False,
        "premarket_activity_source_integrated": True,
        "premarket_activity_coverage_complete": False,
        "premarket_activity_source": "ALPACA_SIP_1MIN_BOUNDED_ACTIVE_US_EQUITY",
        "macro_calendar_configured": bool(FRED_API_KEY),
        "automatic_major_macro_classification": False,
        "evidence_routes_staging_only": True,
        "evidence_preview_creates_current_review": False,
    }


@app.post("/scan/run-once")
def run_scan(
    req: ScanRequest,
    credentials: HTTPAuthorizationCredentials | None = Security(
        bearer
    ),
):
    require_auth(credentials)

    if req.include_dated_prior_evidence and not (
        req.run_class == "INFRASTRUCTURE_TEST" and req.phase == "PREMARKET"
        and os.getenv("RENDER_SERVICE_ID") == "srv-dal8abbl550s73cj3jm0"
        and (SUPABASE_URL or "").rstrip("/") == "https://cihwmameyylixouggwxk.supabase.co"
        and RULESET_VERSION == "v0.3"
    ):
        raise HTTPException(403, "DATED_EVIDENCE_STAGING_INFRASTRUCTURE_ONLY")

    controls = acceptance_controls()
    if controls:
        controls.admit(req, service=os.getenv("RENDER_SERVICE_ID"), database=SUPABASE_URL, ruleset=RULESET_VERSION)
    run_key = make_run_key(req)
    run, created_new = create_run_once(req, run_key)

    if not created_new:
        existing_items = sb_select(
            "strategy_discovery_items",
            {
                "select": "id",
                "run_id": f"eq.{run['id']}",
            },
        )
        return {
            "run_id": run["id"],
            "run_key": run_key,
            "experiment_class": run.get("experiment_class"),
            "run_class": req.run_class,
            "status": run.get("status"),
            "candidates_discovered": run.get(
                "candidates_discovered",
                len(existing_items),
            ),
            "channel_status": run.get(
                "channel_status",
                {},
            ),
            "macro_events_found": len(
                run.get("macro_events") or []
            ),
            "idempotent_replay": True,
            "automatic_major_macro_classification": False,
            "automatic_promotion": False,
        }

    channel_status = {
        "earnings_guidance": "DATA_UNAVAILABLE",
        "corporate_news": "DATA_UNAVAILABLE",
        "analyst_actions": "DATA_UNAVAILABLE",
        "sector_industry": "DATA_UNAVAILABLE",
        "premarket_movers_unusual_activity": (
            "DATA_UNAVAILABLE"
        ),
        "macro_economic_calendar": (
            "DATA_UNAVAILABLE"
        ),
        "cross_source_verification": "REVIEW_REQUIRED",
    }

    errors: list[str] = []
    movers: dict[str, dict[str, Any]] = {}
    news_by_symbol: dict[
        str,
        list[dict[str, Any]],
    ] = {}
    macro_events: list[dict[str, Any]] = []
    macro_checked_at: str | None = None
    macro_sources: list[str] = []
    news_collection: dict[str, Any] = {"outcome": "PROVIDER_UNAVAILABLE"}
    news_body = {}

    try:
        macro_events = fetch_fred_release_calendar(
            req.session_date
        )
        macro_checked_at = datetime.now(
            timezone.utc
        ).isoformat()
        channel_status[
            "macro_economic_calendar"
        ] = "PARTIAL_MACRO_SOURCES_REVIEW_REQUIRED"
        macro_sources.append("FRED_RELEASES_DATES")
    except Exception:
        # Provider exceptions can contain credential-bearing URLs or bodies.
        # Persist only fixed source-specific codes, never exception text.
        errors.append("FRED_RELEASE_CALENDAR_UNAVAILABLE")
        channel_status[
            "macro_economic_calendar"
        ] = "DATA_UNAVAILABLE"

    try:
        macro_events.extend(collect_ism_calendar(req.session_date, **({"get": source_get} if controls else {})))
        macro_sources.append("ISM_RELEASE_CALENDAR")
        macro_checked_at = datetime.now(timezone.utc).isoformat()
        channel_status["macro_economic_calendar"] = "PARTIAL_MACRO_SOURCES_REVIEW_REQUIRED"
    except Exception:
        errors.append("ISM_RELEASE_CALENDAR_UNAVAILABLE")

    try:
        macro_events.extend(collect_weekly_calendar(req.session_date, **({"get": source_get} if controls else {})))
        macro_sources.append("FOREX_FACTORY_WEEKLY_CALENDAR")
        macro_checked_at = datetime.now(timezone.utc).isoformat()
        channel_status["macro_economic_calendar"] = "PARTIAL_MACRO_SOURCES_REVIEW_REQUIRED"
    except Exception:
        errors.append("WEEKLY_CALENDAR_UNAVAILABLE")

    try:
        mover_body = fetch_movers(req.movers_top)

        for symbol, snapshot in normalize_mover_rows(
            mover_body
        ):
            movers[symbol] = snapshot

        channel_status[
            "premarket_movers_unusual_activity"
        ] = "PREMARKET_DATA_UNAVAILABLE_REGULAR_SESSION_REFERENCE_ONLY"

    except Exception:
        errors.append("ALPACA_MOVERS_UNAVAILABLE")

    try:
        news_body = fetch_news(req.news_hours)
        news_collection = news_body.get("collection") or {"outcome": "UNVERIFIED_LEGACY_RESPONSE"}
        news_status = ("NEWS_FEED_EXHAUSTED_REVIEW_REQUIRED" if news_collection.get("feed_exhausted")
                       else "NEWS_FEED_INCOMPLETE")

        news_by_symbol, _ = normalize_news(
            news_body
        )

        channel_status[
            "earnings_guidance"
        ] = news_status

        channel_status[
            "corporate_news"
        ] = news_status

        channel_status[
            "analyst_actions"
        ] = news_status

        channel_status[
            "sector_industry"
        ] = news_status

    except Exception:
        errors.append("ALPACA_NEWS_UNAVAILABLE")

    premarket = {"items": {}, "collection": {"outcome": "PROVIDER_UNAVAILABLE"}}
    try:
        if req.include_dated_prior_evidence:
            premarket = collect_premarket_with_prior(alpaca_headers(), req.session_date, phase=req.phase, **({"get": source_get} if controls else {}))
            # The coordinator persists only activity/catalyst leads. Full-universe
            # ledger persistence belongs to the isolated storage acceptance path.
            premarket["collection"]["prior_coverage_rows_persisted_by_coordinator"] = False
        else:
            premarket = collect_premarket(alpaca_headers(), req.session_date, phase=req.phase)
        if premarket["items"]:
            channel_status["premarket_movers_unusual_activity"] = "PARTIAL_SIP_ACTIVITY_REVIEW_REQUIRED"
    except Exception:
        # Never persist headers, response bodies, URLs with tokens, or exception text.
        pass

    symbols = sorted(
        set(movers)
        | set(news_by_symbol)
        | set(premarket["items"])
    )

    ticker_map: dict[str, int] = {}

    try:
        ticker_map = fetch_ticker_map()
    except Exception:
        errors.append("SEC_TICKER_MAP_UNAVAILABLE")

    inserted = 0
    acceptance_rows = []
    source_collector = None
    if controls:
        source_collector = SourceCollector(get=source_get, sec_headers=sec_headers(), now=controls.now)
        source_collector.index_news(news_body.get("news") or news_body.get("articles") or [])
    prior_attachments = {}
    if controls and premarket.get("prior_evidence"):
        # Validate/hash the entire envelope once, not once per discovered symbol.
        prior_attachments = attach_prior_evidence({symbol: {} for symbol in symbols}, premarket["prior_evidence"])

    for symbol in symbols:
        sec_evidence: list[
            dict[str, Any]
        ] = []

        if controls:
            controls.sec[symbol] = {"status": "UNAVAILABLE_NO_CIK", "records": 0}
        if symbol in ticker_map:
            try:
                if controls and (controls.seconds_left("source") <= 0 or controls.source_calls >= controls.source_limit):
                    raise HTTPException(409, "SOURCE_BUDGET_EXHAUSTED")
                sec_evidence = fetch_recent_sec(
                    symbol,
                    ticker_map[symbol],
                )
                if controls:
                    controls.sec[symbol] = {"status": "RETRIEVED_REVIEW_REQUIRED" if sec_evidence else "CHECKED_NO_RECENT_FORMS",
                                            "records": len(sec_evidence),
                                            "checked_at": controls.now().isoformat(),
                                            "window_start": (req.session_date-timedelta(days=3)).isoformat(),
                                            "window_end": req.session_date.isoformat(),
                                            "document_contents_verified": False}
            except Exception:
                sec_evidence = []
                if controls:
                    controls.sec[symbol] = {"status": "UNAVAILABLE_OR_BUDGET_EXHAUSTED", "records": 0}

        evidence = news_by_symbol.get(
            symbol,
            [],
        )

        categories = [
            item.get("category")
            for item in evidence
            if item.get("category")
        ]

        category = (
            categories[0]
            if categories
            else (
                "mover_unexplained"
                if symbol in movers
                else None
            )
        )

        # IMPORTANT:
        # News + SEC evidence does not prove
        # the two sources describe the same catalyst.
        verification = "REVIEW_REQUIRED"

        discovered_via = []

        if symbol in movers:
            discovered_via.append(
                "alpaca_movers"
            )

        if evidence:
            discovered_via.append(
                "alpaca_news"
            )

        if symbol in premarket["items"]:
            discovered_via.append("alpaca_sip_premarket_bars")

        if sec_evidence:
            discovered_via.append(
                "sec_edgar_recent_filing"
            )

        quality_flags = build_quality_flags(
            symbol=symbol,
            mover_snapshot=movers.get(
                symbol,
                {},
            ),
            evidence=evidence,
            sec_evidence=sec_evidence,
        )

        row = {
            "run_id": run["id"],
            "symbol": symbol,
            "discovered_via": discovered_via,
            "mover_snapshot": {
                **movers.get(symbol, {}),
                **({"premarket_activity": premarket["items"][symbol]}
                   if symbol in premarket["items"] else {}),
            },
            "news_evidence": evidence,
            "independent_evidence": (
                sec_evidence
            ),
            "catalyst_category": category,
            "provisional_tier": None,
            "verification_status": (
                verification
            ),
            "promotion_status": (
                "REVIEW_REQUIRED"
            ),
            "notes": (
                f"run_class={req.run_class}; "
                f"evidence_quality_flags="
                f"{quality_flags}; "
                "Evidence co-occurrence is "
                "not catalyst verification. "
                "No automatic catalyst tier, "
                "materiality, or cross-source "
                "verification assignment."
            ),
        }
        if controls:
            row["mover_snapshot"]["catalyst_review_packet"] = source_collector.packet(
                run_key=run_key, symbol=symbol, news_evidence=evidence, sec_evidence=sec_evidence)
            attachment = prior_attachments.get(symbol, {"dated_prior_session_evidence": {
                "status": "UNAVAILABLE", "reason": "COLLECTOR_UNAVAILABLE"}})
            row["mover_snapshot"]["dated_prior_session_evidence"] = attachment["dated_prior_session_evidence"]
            row["mover_snapshot"]["discovery_trace"] = {
                "record_kind": "DISCOVERY_LEAD", "run_key": run_key,
                "strategy_evidence_eligible": False, "sec_collection": controls.sec[symbol],
                "source_ids": [str(i.get("alpaca_news_id")) for i in evidence],
                "same_event_verified": False, "underlying_event_time_verified": False,
                "evidence_review": "REVIEW_REQUIRED"}
            acceptance_rows.append(row)
        else:
            try:
                sb_insert("strategy_discovery_items", row)
                inserted += 1
            except HTTPException:
                raise
            except Exception:
                pass

    if controls:
        controls.coverage = coverage_ledger(news_collection, premarket, macro_sources, errors, news_by_symbol,
            controls.sec, news_body.get("news") or news_body.get("articles") or [])
        controls.coverage["checked_at"] = controls.now().isoformat()
        controls.coverage["source_documents"] = source_collector.summary()
        assigned_ids = {"ALPACA_NEWS:"+str(item.get("alpaca_news_id"))
                        for evidence in news_by_symbol.values() for item in evidence}
        controls.coverage["unassigned_news_content"] = [record for key, record in source_collector.news.items()
                                                        if key not in assigned_ids]
        stored = controls.persist(acceptance_rows, headers=sb_headers())
        inserted = stored["acknowledged_count"]
        channel_status = {k: v["status"] for k, v in controls.coverage["channels"].items()}
        channel_status["cross_source_verification"] = "REVIEW_REQUIRED"

    status = "PARTIAL"

    notes = (
        f"{req.run_class} | "
        "Bounded wide-net collection attempted; full discovery coverage unresolved. "
        "FRED, ISM and Forex Factory are supplemental calendars, not a complete event inventory. "
        "The coordinator does not classify any release as major "
        "or imminent. That remains an explicit structured review gate. "
        "News and SEC evidence remain separate until "
        "explicit cross-source review confirms they "
        "refer to the same catalyst. "
        "Quality flags are review aids only and do not "
        "redefine Strategy #1. "
        "Regular-session movers do not establish current premarket activity. "
        "News publication/update timestamps are not underlying event dates. "
        "SIP minute bars are bounded activity evidence, not qualification or unusual-volume validation. "
        "news_collection=" + json.dumps(news_collection, sort_keys=True)
        + "; premarket_collection=" + json.dumps(premarket["collection"], sort_keys=True)
    )

    if errors:
        notes += (
            " Errors: "
            + " | ".join(errors[:5])
        )

    if controls:
        notes = json.dumps({"request_identity": controls.identity, "strategy_evidence_eligible": False,
            "run_class": "INFRASTRUCTURE_TEST", "normal_coordinator_path": True,
            "coverage": controls.coverage, "storage": controls.storage,
            "collection_manifest": premarket.get("collection", {}),
            "universe_coverage_rows_persisted": False,
            "candidate_count_semantics": "ACKNOWLEDGED_DISCOVERY_LEADS_NOT_QUALIFIED_CANDIDATES",
            "full_discovery_accepted": False, "source_calls": controls.source_calls,
            "macro_events": macro_events, "limitations": [
                "Source retrieval is not catalyst or channel verification.",
                "No Journal delivery or experiment observations.",
                "Universe manifest retained; per-symbol coverage-only rows not persisted by coordinator."]}, sort_keys=True)

    persisted_run = finalize_discovery_run(
        run_key,
        {
            "status": status,
            "channel_status": channel_status,
            "candidates_discovered": inserted,
            "macro_events": macro_events,
            "macro_source": (
                "+".join(macro_sources)
                if macro_checked_at is not None
                else None
            ),
            "macro_checked_at": macro_checked_at,
            "notes": notes,
        },
    )

    return {
        "run_id": run["id"],
        "run_key": run_key,
        "experiment_class": req.run_class,
        "run_class": req.run_class,
        "status": persisted_run["status"],
        "candidates_discovered": persisted_run["candidates_discovered"],
        "channel_status": persisted_run["channel_status"],
        "errors": errors,
        "macro_events_found": len(macro_events),
        "idempotent_replay": False,
        "automatic_major_macro_classification": False,
        "automatic_promotion": False,
        **({"storage_verified": controls.storage["storage_verified"],
            "coverage": controls.coverage, "strategy_evidence_eligible": False,
            "full_discovery_accepted": False} if controls else {}),
    }


@app.get("/runs/latest")
def latest_run(
    credentials: HTTPAuthorizationCredentials | None = Security(
        bearer
    ),
):
    require_auth(credentials)

    runs = sb_select(
        "strategy_discovery_runs",
        {
            "select": "*",
            "order": "created_at.desc",
            "limit": "1",
        },
    )

    if not runs:
        return None

    run = runs[0]

    items = sb_select(
        "strategy_discovery_items",
        {
            "select": "*",
            "run_id": f"eq.{run['id']}",
            "order": "created_at.asc",
        },
    )

    return {
        "run": run,
        "items": items,
    }



def scheduled_market_session(session_date: date) -> dict:
    """Read only the paper market calendar; never infer holidays from a failure."""
    if not 1970 <= session_date.year <= 2029:
        raise HTTPException(503, "Market calendar date outside documented coverage.")
    try:
        response = requests.get(
            "https://paper-api.alpaca.markets/v2/calendar", headers=alpaca_headers(),
            params={"start": session_date.isoformat(), "end": session_date.isoformat()},
            timeout=(5, 30), allow_redirects=False,
        )
        if response.status_code != 200:
            raise ValueError("Calendar HTTP error")
        rows = response.json()
        if not isinstance(rows, list):
            raise ValueError("Invalid calendar")
        if not rows:
            return {"date": session_date.isoformat(), "is_trading_day": False}
        if len(rows) != 1 or rows[0]["date"] != session_date.isoformat():
            raise ValueError("Mismatched calendar")
        from zoneinfo import ZoneInfo
        market_zone = ZoneInfo("America/New_York")
        opened, closed = [datetime.fromisoformat(
            f"{session_date.isoformat()}T{rows[0][key]}"
        ).replace(tzinfo=market_zone) for key in ("open", "close")]
        if opened >= closed:
            raise ValueError("Invalid session hours")
        return {"date": session_date.isoformat(), "is_trading_day": True,
                "open": opened.isoformat(), "close": closed.isoformat()}
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        raise HTTPException(503, "Market calendar unavailable or invalid.") from exc


@app.get("/runs/scheduled")
def scheduled_run(
    session_date: date,
    phase: Literal["PREMARKET", "POST_OPEN"] = "PREMARKET",
    run_class: Literal["STRATEGY_1", "INFRASTRUCTURE_TEST"] = "STRATEGY_1",
    credentials: HTTPAuthorizationCredentials | None = Security(bearer),
):
    """Exact-key readback for scheduler/watchdog; no scan or Journal side effects."""
    require_auth(credentials)
    key = make_run_key(ScanRequest(session_date=session_date, phase=phase, run_class=run_class))
    session = scheduled_market_session(session_date)
    run = get_existing_run_by_key(key)
    summary = None
    if run:
        items = sb_select("strategy_discovery_items", {
            "select": "id", "run_id": f"eq.{run['id']}",
        })
        fields = ("id", "run_key", "session_date", "phase", "ruleset_version",
                  "experiment_class", "status", "created_at", "updated_at",
                  "candidates_discovered", "channel_status", "transition_context")
        summary = {k: run.get(k) for k in fields}
        summary["items_persisted"] = len(items)
    return {"run_key": key, "session": session, "run": summary,
            "calendar_source": "ALPACA_PAPER_MARKET_CALENDAR",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "implementation_version": IMPLEMENTATION_VERSION,
            "mode": "SHADOW", "broker_execution_enabled": False}


class QualificationRequest(BaseModel):
    reviewer: str = Field(min_length=1)
    reviewed_at: datetime
    model_config = {"extra": "forbid"}
    direction: Literal["LONG", "SHORT"]
    catalyst_summary: str = Field(min_length=1)
    catalyst_tier: Literal["A", "B"]
    catalyst_material: Literal[True]
    materiality_rationale: str = Field(min_length=1)
    catalyst_verified: Literal[True]
    catalyst_cross_source_verified: Literal[True]
    catalyst_sources: list[CatalystSourceIn] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_review(self):
        if not self.reviewer.strip() or self.reviewed_at.tzinfo is None or self.reviewed_at > datetime.now(timezone.utc):
            raise ValueError("Attributable, timezone-aware review required.")
        if not self.catalyst_summary.strip() or not self.materiality_rationale.strip():
            raise ValueError("Catalyst summary and materiality rationale must be nonblank.")
        if any(not s.source.strip() or not s.source_type.strip() or
               not s.headline_or_event.strip() or s.event_timestamp.tzinfo is None
               for s in self.catalyst_sources):
            raise ValueError("Evidence requires nonblank source fields and timezone-aware timestamps.")
        if len({s.source.strip().casefold() for s in self.catalyst_sources}) < 2:
            raise ValueError("Cross-source review requires two distinct named sources.")
        return self


class SetupRequest(BaseModel):
    data_kind: Literal["MARKET", "SYNTHETIC"]
    data_timestamp: datetime | None = None
    data_quality_ok: bool | None = None
    current_review: CurrentReview | None = None
    model_config = {"extra": "forbid"}
    setup_rationale: str = Field(min_length=1)
    market_data_source: str = Field(min_length=1)
    entry_model: Literal["opening_range_premarket_high_break",
                         "vwap_reclaim_rejection", "first_clean_pullback"]
    trigger_definition: str = Field(min_length=1)
    trigger_price: Decimal = Field(gt=0)
    trigger_operator: Literal["GTE", "LTE"]
    entry_price: Decimal = Field(gt=0)
    stop_price: Decimal = Field(gt=0)
    target_price: Decimal = Field(gt=0)
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
    realized_daily_loss_dollars: Decimal | None = None
    executed_trades_today: int | None = None
    after_first_minute: bool | None = None
    missed_trigger: bool | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_setup(self):
        if any(not value.strip() for value in
               (self.setup_rationale, self.market_data_source, self.trigger_definition)):
            raise ValueError("Setup rationale, data source, and trigger definition must be nonblank.")
        return self


def discovery_context(item_id: str):
    from uuid import UUID
    try:
        UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="item_id must be a UUID.")
    items = sb_select("strategy_discovery_items",
                      {"select": "*", "id": f"eq.{item_id}", "limit": "1"})
    if not items:
        raise HTTPException(status_code=404, detail="Discovery item not found.")
    item = items[0]
    runs = sb_select("strategy_discovery_runs",
                     {"select": "*", "id": f"eq.{item['run_id']}", "limit": "1"})
    if not runs:
        raise HTTPException(status_code=404, detail="Discovery run not found.")
    return item, runs[0]



def reserve_artifact(item_id: str, column: str, record: dict[str, Any]):
    if acceptance_controls():
        raise HTTPException(403, "REVIEW_MUTATIONS_DISABLED_DURING_ACCEPTANCE")
    """Claim an immutable artifact atomically; conflicting concurrent writes fail closed."""
    r = requests.patch(f"{SUPABASE_URL.rstrip('/')}/rest/v1/strategy_discovery_items",
                       headers=sb_headers(),
                       params={"id": f"eq.{item_id}", column: "is.null",
                               "promotion_status": "not.in.(PROMOTED,REJECTED)"},
                       json=attributable(record), timeout=20)
    if not r.ok:
        raise HTTPException(status_code=502, detail="Artifact persistence failed.")
    rows = r.json()
    if len(rows) != 1:
        raise HTTPException(status_code=409, detail="Item changed concurrently; re-read and retry the same request.")
    return rows[0]

def qualify_item(item_id: str, review: QualificationRequest):
    if acceptance_controls():
        raise HTTPException(403, "QUALIFICATION_DISABLED_DURING_ACCEPTANCE")
    item, run = discovery_context(item_id)
    payload = review.model_dump(mode="json")
    existing = item.get("qualification_review")
    if existing is not None:
        if existing != payload:
            raise HTTPException(status_code=409, detail="Qualification already recorded; conflicting review rejected.")
        return {"discovery_item_id": item_id, "run_id": run["id"],
                "operational_state": item.get("operational_state"),
                "setup_status": "PREDEFINED" if item.get("setup_review") else "SETUP_REQUIRED",
                "candidate_id": item.get("orchestrator_candidate_id"), "idempotent_replay": True}
    if item.get("promotion_status") in ("PROMOTED", "REJECTED"):
        raise HTTPException(status_code=409, detail="Terminal discovery item cannot be qualified.")
    reserve_artifact(item_id, "qualification_review", {
        "qualification_review": payload, "operational_state": "WATCHLIST_CANDIDATE",
        "provisional_tier": review.catalyst_tier, "verification_status": "VERIFIED",
        "materiality_rationale": review.materiality_rationale,
        "promotion_status": "ELIGIBLE_FOR_ORCHESTRATOR",
    })
    return {"discovery_item_id": item_id, "run_id": run["id"],
            "operational_state": "WATCHLIST_CANDIDATE", "setup_status": "SETUP_REQUIRED",
            "candidate_id": None, "idempotent_replay": False}


def construct_setup(item_id: str, setup: SetupRequest):
    if acceptance_controls():
        raise HTTPException(403, "SETUP_DISABLED_DURING_ACCEPTANCE")
    item, run = discovery_context(item_id)
    if run.get("experiment_class") not in ("STRATEGY_1", "INFRASTRUCTURE_TEST"):
        raise HTTPException(status_code=409, detail="Historical run lacks structured class; explicit reconciliation required.")
    if not item.get("qualification_review") or item.get("promotion_status") == "REJECTED":
        raise HTTPException(status_code=409, detail="Explicit catalyst qualification is required before setup.")
    review = QualificationRequest.model_validate(item["qualification_review"])
    geometry = (setup.entry_price - setup.stop_price, setup.target_price - setup.entry_price)
    if review.direction == "SHORT":
        geometry = (setup.stop_price - setup.entry_price, setup.entry_price - setup.target_price)
    if any(value <= 0 for value in geometry):
        raise HTTPException(status_code=422, detail="Invalid directional entry/stop/target geometry.")
    payload = setup.model_dump(mode="json")
    problem = readiness_problem({**payload, "session_date": run["session_date"]})
    readiness = "HOLD_UNRESOLVED" if problem else "WORKER_READY"
    if item.get("setup_review") is not None and item["setup_review"] != payload:
        raise HTTPException(status_code=409, detail="Setup already recorded; conflicting setup rejected.")
    if item.get("promotion_status") == "PROMOTED":
        if not item.get("orchestrator_candidate_id"):
            raise HTTPException(status_code=502, detail="Promoted item is missing its candidate link.")
        return {"discovery_item_id": item_id, "run_id": run["id"],
                "operational_state": item.get("operational_state") or readiness, "setup_status": "PREDEFINED",
                "candidate_id": item["orchestrator_candidate_id"], "idempotent_replay": True}
    if not ORCHESTRATOR_TOKEN:
        raise HTTPException(status_code=503, detail="ORCHESTRATOR_TOKEN is not configured.")
    # Persist the explicit setup before handoff. WORKER_READY never means TRADE.
    if item.get("setup_review") is None:
        reserve_artifact(item_id, "setup_review",
                         {"setup_review": payload, "operational_state": readiness})
    infrastructure = run["experiment_class"] == "INFRASTRUCTURE_TEST"
    body = {**review.model_dump(mode="json", exclude={"reviewer", "reviewed_at"}),
            **setup.model_dump(mode="json", exclude={"setup_rationale"}),
            "experiment_class": "INFRASTRUCTURE_TEST" if infrastructure else "STRATEGY_1",
            "source_discovery_item_id": item_id, "run_id": run["id"], "session_date": run["session_date"],
            "discovery_phase": run["phase"], "symbol": item["symbol"],
            "ruleset_version": RULESET_VERSION,
            "catalyst_event_at": review.catalyst_sources[0].event_timestamp.isoformat(),
            "notes": ((setup.notes or "") + f" | Setup rationale: {setup.setup_rationale}"
                      + f" | Qualified discovery item {item_id}; run_id={run['id']}"
                      + (" | INFRASTRUCTURE_TEST" if infrastructure else ""))}
    wait_for_dependency(ORCHESTRATOR_URL, "Shadow Orchestrator")
    try:
        r = requests.post(f"{ORCHESTRATOR_URL.rstrip('/')}/candidates/ingest",
                          headers={"Authorization": f"Bearer {ORCHESTRATOR_TOKEN}",
                                   "Content-Type": "application/json"},
                          json=body, timeout=(5, 45))
    except requests.RequestException as exc:
        raise HTTPException(status_code=503, detail="Orchestrator handoff unavailable; explicit setup retained.") from exc
    if not r.ok:
        raise HTTPException(status_code=502,
                            detail=f"Orchestrator setup handoff failed: {r.status_code} {r.text[:500]}")
    result = r.json()
    from uuid import UUID
    try:
        UUID(result.get("candidate_id", ""))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=502, detail="Orchestrator response missing a valid candidate_id.")
    sb_update("strategy_discovery_items", item_id,
              {"promotion_status": "PROMOTED", "orchestrator_candidate_id": result["candidate_id"],
               "operational_state": result.get("operational_state", readiness)})
    return {"discovery_item_id": item_id, "run_id": run["id"],
            "operational_state": result.get("operational_state", readiness), "setup_status": "PREDEFINED",
            "candidate_id": result["candidate_id"], "orchestrator": result, "idempotent_replay": False}


@app.post("/items/{item_id}/qualify")
def qualify(item_id: str, review: QualificationRequest,
            credentials: HTTPAuthorizationCredentials | None = Security(bearer)):
    require_auth(credentials)
    return qualify_item(item_id, review)


@app.post("/items/{item_id}/setup")
def setup_item(item_id: str, setup: SetupRequest,
               credentials: HTTPAuthorizationCredentials | None = Security(bearer)):
    require_auth(credentials)
    return construct_setup(item_id, setup)


@app.post("/items/{item_id}/promote", deprecated=True)
def promote(item_id: str, review: PromoteRequest,
            credentials: HTTPAuthorizationCredentials | None = Security(bearer)):
    require_auth(credentials)
    raise HTTPException(status_code=410, detail="Use /qualify then /setup with attributable current review.")


class RejectionRequest(BaseModel):
    model_config = {"extra": "forbid", "str_strip_whitespace": True}
    reviewer: str = Field(min_length=1)
    reviewed_at: datetime
    reason: str = Field(min_length=1)


@app.post("/items/{item_id}/reject")
def reject_item(item_id: str, review: RejectionRequest,
                credentials: HTTPAuthorizationCredentials | None = Security(bearer)):
    require_auth(credentials)
    item, run = discovery_context(item_id)
    if review.reviewed_at.tzinfo is None or review.reviewed_at > datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="Timezone-aware prospective review required.")
    if item.get("orchestrator_candidate_id"):
        raise HTTPException(status_code=409, detail="Review the routed candidate through the Orchestrator.")
    reserve_artifact(item_id, "rejection_review", {
        "rejection_review": review.model_dump(mode="json"), "rejection_reason": review.reason,
        "operational_state": "REJECTED", "promotion_status": "REJECTED"})
    return {"discovery_item_id": item_id, "run_id": run["id"], "operational_state": "REJECTED"}
