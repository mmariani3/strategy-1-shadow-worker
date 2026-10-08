"""October 8 isolated staging collector/storage acceptance. No strategy routes.

This measures the collector and existing JSON storage contract, not the complete
news/SEC coordinator pipeline. All saved evidence is INFRASTRUCTURE_TEST.
"""
from datetime import date, datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import time

from fastapi import FastAPI, Header, HTTPException
import requests
from premarket_collection import collect_premarket, CALENDAR_URL

DAY = date(2026, 10, 8)
LAUNCH = datetime(2026, 10, 8, 13, tzinfo=timezone.utc)
STOP = LAUNCH + timedelta(minutes=15)
EXPIRES = LAUNCH + timedelta(minutes=25)
SERVICE = "srv-dal8abbl550s73cj3jm0"
DB = "https://cihwmameyylixouggwxk.supabase.co"
RUN_KEY = "STRATEGY_1|2026-10-08|PREMARKET|v0.3|INFRASTRUCTURE_TEST"
LABEL = "OCT8_PREMARKET_STORAGE_ACCEPTANCE_NOT_STRATEGY_EVIDENCE"
MAX_ITEMS = 3000
FIELDS = "run_id,symbol,discovered_via,mover_snapshot,news_evidence,independent_evidence,catalyst_category,provisional_tier,verification_status,promotion_status,notes"
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


def now():
    return datetime.now(timezone.utc)


def require(ok):
    if not ok:
        raise ValueError("ACCEPTANCE_GUARD")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def source_hash():
    h = hashlib.sha256()
    for name in ("premarket_acceptance.py", "premarket_collection.py"):
        h.update(name.encode())
        h.update((Path(__file__).parent/name).read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


def guard(authorization):
    token = os.getenv("DISCOVERY_SERVICE_TOKEN", "")
    if not token or not authorization or not hmac.compare_digest(authorization, "Bearer " + token):
        raise HTTPException(401, "AUTHENTICATION_REQUIRED")
    try:
        require(os.getenv("RENDER_SERVICE_ID") == SERVICE)
        require(os.getenv("SUPABASE_URL", "").rstrip("/") == DB)
        require(os.getenv("RULESET_VERSION") == "v0.3")
        require(now() < EXPIRES)
        require(all(os.getenv(k) for k in ("ALPACA_API_KEY", "ALPACA_API_SECRET", "SUPABASE_SECRET_KEY")))
    except Exception:
        raise HTTPException(503, "STAGING_CONFIGURATION_OR_DATE_UNVERIFIED") from None


def alpaca_headers():
    return {"APCA-API-KEY-ID": os.environ["ALPACA_API_KEY"],
            "APCA-API-SECRET-KEY": os.environ["ALPACA_API_SECRET"]}


def db_call(method, table, *, params=None, body=None):
    require(table in {"strategy_discovery_runs", "strategy_discovery_items"})
    require(method in {"GET", "POST", "PATCH"} and now() < EXPIRES)
    require(os.getenv("SUPABASE_URL", "").rstrip("/") == DB)
    if method != "GET":
        require(LAUNCH <= now() < STOP)
        require(table == "strategy_discovery_runs" or method == "POST")
    key = os.environ["SUPABASE_SECRET_KEY"]
    headers = {"apikey": key, "Prefer": "return=representation"}
    if key.count(".") == 2:
        headers["Authorization"] = "Bearer " + key
    if body is not None:
        body = dict(body, transition_context={"owner": "premarket_staging_acceptance",
            "implementation_version": os.getenv("RENDER_GIT_COMMIT", "unavailable") + ";" + source_hash(),
            "reason": LABEL, "strategy_evidence_eligible": False})
    response = requests.request(method, DB + "/rest/v1/" + table, params=params, json=body,
                                headers=headers, timeout=(3, 10), allow_redirects=False)
    require(response.status_code == (201 if method == "POST" else 200))
    rows = response.json()
    require(isinstance(rows, list))
    return rows


def get_run():
    rows = db_call("GET", "strategy_discovery_runs", params={"select": "id,status,notes,candidates_discovered,run_key,experiment_class",
                  "run_key": "eq." + RUN_KEY, "limit": "2"})
    require(len(rows) <= 1)
    if rows:
        require(rows[0]["run_key"] == RUN_KEY and rows[0]["experiment_class"] == "INFRASTRUCTURE_TEST")
    return rows[0] if rows else None


@app.get("/health")
def health():
    return {"ok": True, "application": LABEL, "commit": os.getenv("RENDER_GIT_COMMIT"),
            "source_hash": source_hash(), "mode": "SHADOW", "broker_execution_enabled": False,
            "journal_routes": False, "qualification_routes": False, "session_date": DAY.isoformat()}


@app.get("/acceptance/preflight")
def preflight(authorization: str | None = Header(default=None)):
    guard(authorization)
    try:
        response = requests.get(CALENDAR_URL, params={"start": DAY.isoformat(), "end": DAY.isoformat()},
                                headers=alpaca_headers(), timeout=(3, 10), allow_redirects=False)
        require(response.status_code == 200)
        calendar = response.json()
        require(len(calendar) == 1 and calendar[0]["date"] == DAY.isoformat()
                and calendar[0]["open"] == "09:30" and calendar[0]["close"] == "16:00")
        # Calendar auth alone does not establish SIP entitlement.
        quote = requests.get("https://data.alpaca.markets/v2/stocks/quotes/latest",
                             params={"symbols": "SPY", "feed": "sip"}, headers=alpaca_headers(),
                             timeout=(3, 10), allow_redirects=False)
        require(quote.status_code == 200 and "SPY" in quote.json().get("quotes", {}))
        existing = get_run()
        return {**health(), "checked_at": now().isoformat(), "database": "STAGING",
                "calendar_authenticated": True, "sip_endpoint_authenticated": True,
                "run_absent": existing is None, "run_key": RUN_KEY}
    except Exception:
        raise HTTPException(503, "ACCEPTANCE_PREFLIGHT_UNVERIFIED") from None


def item_payload(run_id, symbol, evidence):
    return {"run_id": run_id, "symbol": symbol, "discovered_via": ["alpaca_sip_premarket_bars"],
            "mover_snapshot": {"premarket_activity": evidence}, "news_evidence": [], "independent_evidence": [],
            "catalyst_category": None, "provisional_tier": None, "verification_status": "REVIEW_REQUIRED",
            "promotion_status": "REVIEW_REQUIRED", "notes": LABEL}


def verify_items(run_id, expected):
    actual = {}
    for offset in range(0, MAX_ITEMS+101, 100):
        require(now() < STOP)
        rows = db_call("GET", "strategy_discovery_items", params={"select": FIELDS,
            "run_id": "eq." + run_id, "order": "symbol.asc,id.asc", "offset": str(offset), "limit": "100"})
        require(len(rows) <= 100)
        for row in rows:
            require(row["symbol"] not in actual)
            actual[row["symbol"]] = digest(row)
        if len(rows) < 100:
            return actual == expected
    return False


def execute():
    require(LAUNCH <= now() < LAUNCH+timedelta(minutes=1))
    require(get_run() is None)
    # Unique run_key is the durable claim. Any ambiguous insert stops; never retry.
    rows = db_call("POST", "strategy_discovery_runs", body={"session_date": DAY.isoformat(),
        "phase": "PREMARKET", "ruleset_version": "v0.3", "run_key": RUN_KEY,
        "experiment_class": "INFRASTRUCTURE_TEST", "status": "IN_PROGRESS", "channel_status": {}, "notes": LABEL})
    require(len(rows) == 1 and rows[0]["run_key"] == RUN_KEY)
    run_id = rows[0]["id"]
    started = time.monotonic()
    data = collect_premarket(alpaca_headers(), DAY)
    collection_seconds = time.monotonic()-started
    expected, skipped = {}, []
    persistence_start = time.monotonic()
    failure = False
    for symbol in sorted(data["items"]):
        if (len(expected) >= MAX_ITEMS or time.monotonic()-persistence_start >= 180
                or now() >= STOP-timedelta(minutes=2) or failure):
            skipped.append(symbol)
            continue
        body = item_payload(run_id, symbol, data["items"][symbol])
        try:
            result = db_call("POST", "strategy_discovery_items", body=body)
            require(len(result) == 1 and all(result[0].get(k) == v for k,v in body.items()))
            expected[symbol] = digest(body)
        except Exception:
            # No retries after an ambiguous write, including the remaining symbols.
            failure = True
            skipped.append(symbol)
    persistence_seconds = time.monotonic()-persistence_start
    verified = verify_items(run_id, expected)
    collection = data["collection"]
    accepted = (bool(expected) and not skipped and verified and collection["outcome"] == "FEED_EXHAUSTED"
                and not collection["unprocessed_symbols"])
    summary = {"label": LABEL, "run_id": run_id, "run_key": RUN_KEY, "accepted": accepted,
        "collection": collection, "collected_items": len(data["items"]), "acknowledged_items": len(expected),
        "unacknowledged_symbols": skipped, "write_ambiguity_or_failure": failure,
        "paginated_fields_verified": verified, "expected_item_digests": expected,
        "collection_seconds": collection_seconds, "persistence_seconds": persistence_seconds,
        "full_coordinator_pipeline_accepted": False, "strategy_evidence_eligible": False}
    notes = json.dumps(summary, sort_keys=True, allow_nan=False)
    updated = db_call("PATCH", "strategy_discovery_runs", params={"id": "eq."+run_id,
        "run_key": "eq."+RUN_KEY, "experiment_class": "eq.INFRASTRUCTURE_TEST", "status": "eq.IN_PROGRESS"},
        body={"status": "PARTIAL", "candidates_discovered": len(expected),
              "channel_status": {"premarket_movers_unusual_activity": "PARTIAL_SIP_ACTIVITY_REVIEW_REQUIRED"}, "notes": notes})
    require(len(updated) == 1)
    saved = get_run()
    require(saved["id"] == run_id and saved["notes"] == notes and saved["status"] == "PARTIAL"
            and saved["candidates_discovered"] == len(expected))
    return {"accepted": accepted, "run_id": run_id, "collected_items": len(data["items"]),
            "acknowledged_items": len(expected), "paginated_fields_verified": verified,
            "manifest_readback_verified": True, "collection_seconds": collection_seconds,
            "persistence_seconds": persistence_seconds, "full_coordinator_pipeline_accepted": False}


@app.post("/acceptance/run")
def run(authorization: str | None = Header(default=None)):
    guard(authorization)
    try:
        return execute()
    except Exception:
        raise HTTPException(503, "ACCEPTANCE_STOPPED_RECONCILE_WITHOUT_REPLAY") from None


@app.get("/acceptance/result")
def result(authorization: str | None = Header(default=None)):
    guard(authorization)
    try:
        record = get_run()
        if record is None:
            return {"run_absent": True, "run_key": RUN_KEY}
        summary = json.loads(record["notes"]) if record["status"] == "PARTIAL" else None
        return {"run_key": RUN_KEY, "run_id": record["id"], "status": record["status"], "summary": summary}
    except Exception:
        raise HTTPException(503, "ACCEPTANCE_READBACK_UNVERIFIED") from None
