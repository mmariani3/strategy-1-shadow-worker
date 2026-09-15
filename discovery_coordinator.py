import hmac
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Literal

import requests
from fastapi import FastAPI, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, model_validator

APP_VERSION = "0.8.0-shadow-discovery"
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
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = "return=representation"
    return headers


def sb_insert(
    table: str,
    record: dict[str, Any],
) -> list[dict[str, Any]]:
    r = requests.post(
        f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table}",
        headers=sb_headers(),
        json=record,
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
    r = requests.patch(
        f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table}",
        headers=sb_headers(),
        params={"id": f"eq.{row_id}"},
        json=record,
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
    r = requests.patch(
        f"{SUPABASE_URL.rstrip('/')}/rest/v1/strategy_discovery_runs",
        headers=sb_headers(),
        params={"run_key": f"eq.{run_key}"},
        json=record,
        timeout=20,
    )
    if not r.ok:
        raise HTTPException(
            status_code=502,
            detail=(
                "Supabase discovery-run finalization failed: "
                f"{r.status_code} {r.text[:500]}"
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
    r = requests.get(
        f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table}",
        headers=sb_headers(prefer=False),
        params=params,
        timeout=20,
    )
    if not r.ok:
        raise HTTPException(
            status_code=502,
            detail=f"Supabase query failed: {r.status_code} {r.text[:500]}",
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
    existing = get_existing_run_by_key(run_key)
    if existing:
        return existing, False

    payload = {
        "session_date": req.session_date.isoformat(),
        "phase": req.phase,
        "ruleset_version": RULESET_VERSION,
        "run_key": run_key,
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
        json=payload,
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


def fetch_movers(top: int = 20) -> dict[str, Any]:
    r = requests.get(
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


def fetch_news(hours: int = 18) -> dict[str, Any]:
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
        raise RuntimeError(
            f"Alpaca news failed: {r.status_code} {r.text[:250]}"
        )
    return r.json()


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

    r = requests.get(
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
    r = requests.get(
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

    r = requests.get(
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

    cutoff = date.today() - timedelta(days=days)
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
            continue

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
                            "Alpaca documents this endpoint "
                            "as SIP-based movers data."
                        ),
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
                "event_timestamp": (
                    article.get("created_at")
                    or article.get("updated_at")
                ),
                "url": article.get("url"),
                "category": category,
                "alpaca_news_id": article.get("id"),
                "article_symbol_count": len(symbols),
                "symbol_specific": len(symbols) <= 8,
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

    price = mover_snapshot.get("price")
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

    if evidence and all(
        not item.get("symbol_specific", False)
        for item in evidence
    ):
        flags.append("ONLY_BROAD_MULTI_SYMBOL_NEWS")

    if not sec_evidence:
        flags.append("NO_RECENT_DIRECT_SEC_EVIDENCE")

    return flags


class ScanRequest(BaseModel):
    session_date: date
    phase: Literal[
        "PREMARKET",
        "POST_OPEN",
    ] = "PREMARKET"

    run_class: Literal[
        "STRATEGY_1",
        "INFRASTRUCTURE_TEST",
    ] = "STRATEGY_1"

    movers_top: int = Field(
        default=20,
        ge=5,
        le=50,
    )
    news_hours: int = Field(
        default=18,
        ge=1,
        le=48,
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
        "macro_calendar_source": "FRED_RELEASES_DATES",
        "macro_calendar_configured": bool(FRED_API_KEY),
        "automatic_major_macro_classification": False,
    }


@app.post("/scan/run-once")
def run_scan(
    req: ScanRequest,
    credentials: HTTPAuthorizationCredentials | None = Security(
        bearer
    ),
):
    require_auth(credentials)

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

    try:
        macro_events = fetch_fred_release_calendar(
            req.session_date
        )
        macro_checked_at = datetime.now(
            timezone.utc
        ).isoformat()
        channel_status[
            "macro_economic_calendar"
        ] = "CHECKED_FRED_RELEASE_CALENDAR"
    except Exception as e:
        errors.append(str(e))
        channel_status[
            "macro_economic_calendar"
        ] = "DATA_UNAVAILABLE"

    try:
        mover_body = fetch_movers(req.movers_top)

        for symbol, snapshot in normalize_mover_rows(
            mover_body
        ):
            movers[symbol] = snapshot

        channel_status[
            "premarket_movers_unusual_activity"
        ] = "CHECKED_ALPACA_SCREENER"

    except Exception as e:
        errors.append(str(e))

    try:
        news_body = fetch_news(req.news_hours)

        news_by_symbol, _ = normalize_news(
            news_body
        )

        channel_status[
            "earnings_guidance"
        ] = "CHECKED_ALPACA_NEWS"

        channel_status[
            "corporate_news"
        ] = "CHECKED_ALPACA_NEWS"

        channel_status[
            "analyst_actions"
        ] = "CHECKED_ALPACA_NEWS"

        channel_status[
            "sector_industry"
        ] = "CHECKED_ALPACA_NEWS"

    except Exception as e:
        errors.append(str(e))

    symbols = sorted(
        set(movers)
        | set(news_by_symbol)
    )

    ticker_map: dict[str, int] = {}

    try:
        ticker_map = fetch_ticker_map()
    except Exception as e:
        errors.append(str(e))

    inserted = 0

    for symbol in symbols:
        sec_evidence: list[
            dict[str, Any]
        ] = []

        if symbol in ticker_map:
            try:
                sec_evidence = fetch_recent_sec(
                    symbol,
                    ticker_map[symbol],
                )
            except Exception:
                sec_evidence = []

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

        try:
            sb_insert(
                "strategy_discovery_items",
                {
                    "run_id": run["id"],
                    "symbol": symbol,
                    "discovered_via": discovered_via,
                    "mover_snapshot": movers.get(
                        symbol,
                        {},
                    ),
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
                },
            )
            inserted += 1

        except HTTPException:
            raise

        except Exception:
            # Preserve the scan even if one individual
            # discovery item fails to persist.
            pass

    status = "PARTIAL"

    notes = (
        f"{req.run_class} | "
        "Wide-net collection completed. "
        "FRED release-calendar coverage is collected when configured, "
        "but the coordinator does not classify any release as major "
        "or imminent. That remains an explicit structured review gate. "
        "News and SEC evidence remain separate until "
        "explicit cross-source review confirms they "
        "refer to the same catalyst. "
        "Quality flags are review aids only and do not "
        "redefine Strategy #1."
    )

    if errors:
        notes += (
            " Errors: "
            + " | ".join(errors[:5])
        )

    persisted_run = finalize_discovery_run(
        run_key,
        {
            "status": status,
            "channel_status": channel_status,
            "candidates_discovered": inserted,
            "macro_events": macro_events,
            "macro_source": (
                "FRED_RELEASES_DATES"
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
        "run_class": req.run_class,
        "status": persisted_run["status"],
        "candidates_discovered": persisted_run["candidates_discovered"],
        "channel_status": persisted_run["channel_status"],
        "errors": errors,
        "macro_events_found": len(macro_events),
        "idempotent_replay": False,
        "automatic_major_macro_classification": False,
        "automatic_promotion": False,
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



class QualificationRequest(BaseModel):
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
    """Claim an immutable artifact atomically; conflicting concurrent writes fail closed."""
    r = requests.patch(f"{SUPABASE_URL.rstrip('/')}/rest/v1/strategy_discovery_items",
                       headers=sb_headers(),
                       params={"id": f"eq.{item_id}", column: "is.null",
                               "promotion_status": "not.in.(PROMOTED,REJECTED)"},
                       json=record, timeout=20)
    if not r.ok:
        raise HTTPException(status_code=502, detail="Artifact persistence failed.")
    rows = r.json()
    if len(rows) != 1:
        raise HTTPException(status_code=409, detail="Item changed concurrently; re-read and retry the same request.")
    return rows[0]

def qualify_item(item_id: str, review: QualificationRequest):
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
    item, run = discovery_context(item_id)
    if not item.get("qualification_review") or item.get("promotion_status") == "REJECTED":
        raise HTTPException(status_code=409, detail="Explicit catalyst qualification is required before setup.")
    review = QualificationRequest.model_validate(item["qualification_review"])
    geometry = (setup.entry_price - setup.stop_price, setup.target_price - setup.entry_price)
    if review.direction == "SHORT":
        geometry = (setup.stop_price - setup.entry_price, setup.entry_price - setup.target_price)
    if any(value <= 0 for value in geometry):
        raise HTTPException(status_code=422, detail="Invalid directional entry/stop/target geometry.")
    payload = setup.model_dump(mode="json")
    if item.get("setup_review") is not None and item["setup_review"] != payload:
        raise HTTPException(status_code=409, detail="Setup already recorded; conflicting setup rejected.")
    if item.get("promotion_status") == "PROMOTED":
        if not item.get("orchestrator_candidate_id"):
            raise HTTPException(status_code=502, detail="Promoted item is missing its candidate link.")
        return {"discovery_item_id": item_id, "run_id": run["id"],
                "operational_state": "WORKER_READY", "setup_status": "PREDEFINED",
                "candidate_id": item["orchestrator_candidate_id"], "idempotent_replay": True}
    if not ORCHESTRATOR_TOKEN:
        raise HTTPException(status_code=503, detail="ORCHESTRATOR_TOKEN is not configured.")
    # Persist the explicit setup before handoff. WORKER_READY never means TRADE.
    if item.get("setup_review") is None:
        reserve_artifact(item_id, "setup_review",
                         {"setup_review": payload, "operational_state": "WORKER_READY"})
    infrastructure = "INFRASTRUCTURE_TEST" in (run.get("notes") or "")
    body = {**review.model_dump(mode="json"),
            **setup.model_dump(mode="json", exclude={"setup_rationale"}),
            "experiment_class": "INFRASTRUCTURE_TEST" if infrastructure else "STRATEGY_1",
            "source_discovery_item_id": item_id, "session_date": run["session_date"],
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
              {"promotion_status": "PROMOTED", "orchestrator_candidate_id": result["candidate_id"]})
    return {"discovery_item_id": item_id, "run_id": run["id"],
            "operational_state": "WORKER_READY", "setup_status": "PREDEFINED",
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
    # Legacy combined requests use their explicit notes as the setup rationale.
    # Both models are validated before qualification has any side effects.
    from pydantic import ValidationError
    try:
        raw = review.model_dump(mode="json")
        setup = SetupRequest.model_validate({
            **{name: raw[name] for name in SetupRequest.model_fields if name in raw},
            "setup_rationale": raw.get("setup_rationale") or raw.get("notes") or "",
        })
        qualification = QualificationRequest.model_validate({
            **{name: raw[name] for name in QualificationRequest.model_fields if name in raw},
            "catalyst_summary": review.catalyst_sources[0].headline_or_event,
        })
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Combined promotion requires valid catalyst evidence and an explicit setup rationale.") from exc
    qualify_item(item_id, qualification)
    return construct_setup(item_id, setup)
