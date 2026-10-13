"""October 13 isolated staging collector/storage acceptance. No strategy routes.

This measures the collector and existing JSON storage contract, not the complete
news/SEC coordinator pipeline. All saved evidence is INFRASTRUCTURE_TEST.
"""
from datetime import date, datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
import re
from pathlib import Path
import time

from fastapi import FastAPI, Header, HTTPException
import requests
from premarket_collection import CALENDAR_URL, SNAPSHOTS_URL, stamp, MARKET_TZ

from premarket_evidence_collection import collect_premarket_with_prior
from premarket_evidence_storage import persist_universe

DAY = date(2026, 10, 13)
LAUNCH = datetime(2026, 10, 13, 13, tzinfo=timezone.utc)
STOP = LAUNCH + timedelta(minutes=15)
EXPIRES = LAUNCH + timedelta(minutes=25)
SERVICE = "srv-dal8abbl550s73cj3jm0"
DB = "https://cihwmameyylixouggwxk.supabase.co"
RUN_KEY = "STRATEGY_1|2026-10-13|PREMARKET|v0.3|INFRASTRUCTURE_TEST"
LABEL = "OCT13_DATED_PRIOR_UNIVERSE_STORAGE_NOT_STRATEGY_EVIDENCE"
WRITE_BATCH_SIZE = 100
WRITE_BATCH_BYTES = 1024 * 1024
FIELDS = "run_id,symbol,discovered_via,mover_snapshot,news_evidence,independent_evidence,catalyst_category,provisional_tier,verification_status,promotion_status,notes"
SOURCE_FILES = ("premarket_oct13_acceptance.py", "premarket_evidence_collection.py",
    "premarket_evidence_storage.py", "premarket_collection.py", "prior_session_evidence.py",
    "shadow_evidence_workflow.py", "setup_evidence.py", "review_contract.py")
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


def now():
    return datetime.now(timezone.utc)


def require(ok):
    if not ok:
        raise ValueError("ACCEPTANCE_GUARD")


def source_hash():
    h = hashlib.sha256()
    for name in SOURCE_FILES:
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
        require(re.fullmatch("[0-9a-f]{40}", os.getenv("RENDER_GIT_COMMIT", "")) is not None)
        require(all(os.getenv(k) for k in ("ALPACA_API_KEY", "ALPACA_API_SECRET", "SUPABASE_SECRET_KEY")))
    except Exception:
        raise HTTPException(503, "STAGING_CONFIGURATION_OR_DATE_UNVERIFIED") from None


def alpaca_headers():
    return {"APCA-API-KEY-ID": os.environ["ALPACA_API_KEY"],
            "APCA-API-SECRET-KEY": os.environ["ALPACA_API_SECRET"]}


def audited_body(body):
    context = {"owner": "premarket_staging_acceptance",
        "implementation_version": os.getenv("RENDER_GIT_COMMIT", "unavailable") + ";" + source_hash(),
        "reason": LABEL, "strategy_evidence_eligible": False}
    if isinstance(body, list):
        require(0 < len(body) <= WRITE_BATCH_SIZE)
        require(all(isinstance(row, dict) and set(row) == set(FIELDS.split(",")) for row in body))
        return [dict(row, transition_context=context) for row in body]
    require(isinstance(body, dict))
    return dict(body, transition_context=context)


def encoded_body(body):
    # Match Requests' JSON serialization, including ASCII escaping and spaces.
    return json.dumps(body, allow_nan=False).encode("utf-8")


def db_call(method, table, *, params=None, body=None):
    require(table in {"strategy_discovery_runs", "strategy_discovery_items"})
    require(method in {"GET", "POST", "PATCH"} and now() < EXPIRES)
    require(os.getenv("SUPABASE_URL", "").rstrip("/") == DB)
    require(os.getenv("RENDER_SERVICE_ID") == SERVICE)
    if method != "GET":
        require(LAUNCH <= now() < STOP)
        require(table == "strategy_discovery_runs" or method == "POST")
        if table == "strategy_discovery_runs":
            require(isinstance(body, dict))
            if method == "POST":
                require(body.get("run_key") == RUN_KEY and body.get("experiment_class") == "INFRASTRUCTURE_TEST")
                require(body.get("status") == "IN_PROGRESS" and body.get("session_date") == DAY.isoformat())
            else:
                require(params and params.get("run_key") == "eq." + RUN_KEY
                        and params.get("experiment_class") == "eq.INFRASTRUCTURE_TEST"
                        and params.get("status") == "eq.IN_PROGRESS" and params.get("id", "").startswith("eq."))
                require(body.get("status") == "PARTIAL")
    key = os.environ["SUPABASE_SECRET_KEY"]
    headers = {"apikey": key, "Prefer": "return=representation"}
    if key.count(".") == 2:
        headers["Authorization"] = "Bearer " + key
    if body is not None:
        if isinstance(body, list):
            require(table == "strategy_discovery_items" and method == "POST")
        body = audited_body(body)
        if table == "strategy_discovery_items":
            require(len(encoded_body(body)) <= WRITE_BATCH_BYTES)
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
    return {"ok": True, "version": "0.3.0-oct13-dated-prior-acceptance", "application": LABEL, "commit": os.getenv("RENDER_GIT_COMMIT"),
            "source_hash": source_hash(), "mode": "SHADOW", "broker_execution_enabled": False,
            "journal_routes": False, "qualification_routes": False, "session_date": DAY.isoformat(),
            "full_coordinator_pipeline_accepted": False, "strategy_evidence_eligible": False}


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
        snapshot = requests.get(SNAPSHOTS_URL, params={"symbols": "SPY", "feed": "sip"},
                                headers=alpaca_headers(), timeout=(3, 10), allow_redirects=False)
        require(snapshot.status_code == 200)
        snapshot_data = snapshot.json()
        require(isinstance(snapshot_data.get("SPY"), dict))
        diagnostic = {"symbol": "SPY", "feed": "sip", "checked_at": now().isoformat(),
                      "purpose": "READ_ONLY_SESSION_DATE_DIAGNOSTIC_NOT_PREMARKET_ACCEPTANCE"}
        for field in ("dailyBar", "prevDailyBar"):
            try:
                diagnostic[field + "_session_date"] = stamp(snapshot_data["SPY"][field]["t"]).astimezone(MARKET_TZ).date().isoformat()
            except (KeyError, TypeError, ValueError, AttributeError):
                diagnostic[field + "_session_date"] = None
        existing = get_run()
        return {**health(), "checked_at": now().isoformat(), "database": "STAGING",
                "calendar_authenticated": True, "sip_endpoint_authenticated": True,
                "snapshot_endpoint_authenticated": True, "snapshot_diagnostic": diagnostic,
                "run_absent": existing is None, "run_key": RUN_KEY}
    except Exception:
        raise HTTPException(503, "ACCEPTANCE_PREFLIGHT_UNVERIFIED") from None


def execute():
    require(LAUNCH <= now() < LAUNCH+timedelta(minutes=1))
    require(get_run() is None)
    rows = db_call("POST", "strategy_discovery_runs", body={"session_date": DAY.isoformat(),
        "phase": "PREMARKET", "ruleset_version": "v0.3", "run_key": RUN_KEY,
        "experiment_class": "INFRASTRUCTURE_TEST", "status": "IN_PROGRESS", "channel_status": {}, "notes": LABEL})
    require(len(rows) == 1 and rows[0]["run_key"] == RUN_KEY
            and rows[0]["experiment_class"] == "INFRASTRUCTURE_TEST"
            and rows[0]["status"] == "IN_PROGRESS")
    run_id = rows[0]["id"]
    started = time.monotonic()
    data = collect_premarket_with_prior(alpaca_headers(), DAY)
    collection_seconds = time.monotonic()-started
    context = audited_body({})["transition_context"]

    def write(method, table, *, body, context):
        require(context == audited_body({})["transition_context"])
        require(all(row["run_id"] == run_id for row in body))
        return db_call(method, table, body=body)

    if data["universe_items"]:
        persistence = persist_universe(run_id, data, write=write, read=db_call, context=context,
                                      time_available=lambda: now() < STOP-timedelta(minutes=2))
    else:
        persistence = {"collection_storage_accepted": False, "storage_verified": False,
                       "expected_count": 0, "acknowledged_symbols": [], "unacknowledged_symbols": [],
                       "persistence_outcome": "NO_UNIVERSE", "write_requests_attempted": 0}
    summary = {"label": LABEL, "run_id": run_id, "run_key": RUN_KEY,
        "accepted": persistence["collection_storage_accepted"], "collection": data["collection"],
        "integration": data["integration"], "storage": persistence,
        "universe_coverage_rows": len(data["universe_items"]), "activity_items": len(data["items"]),
        "record_kind": "UNIVERSE_COVERAGE_NOT_QUALIFIED_CANDIDATES", "collection_seconds": collection_seconds,
        "full_coordinator_pipeline_accepted": False, "strategy_evidence_eligible": False}
    notes = json.dumps(summary, sort_keys=True, allow_nan=False)
    count = len(persistence["acknowledged_symbols"])
    updated = db_call("PATCH", "strategy_discovery_runs", params={"id": "eq."+run_id,
        "run_key": "eq."+RUN_KEY, "experiment_class": "eq.INFRASTRUCTURE_TEST", "status": "eq.IN_PROGRESS"},
        body={"status": "PARTIAL", "candidates_discovered": count,
              "channel_status": {"premarket_movers_unusual_activity": "PARTIAL_SIP_ACTIVITY_REVIEW_REQUIRED"},
              "notes": notes})
    require(len(updated) == 1)
    saved = get_run()
    require(saved["id"] == run_id and saved["notes"] == notes and saved["status"] == "PARTIAL"
            and saved["candidates_discovered"] == count)
    return {"accepted": persistence["collection_storage_accepted"], "run_id": run_id,
            "collected_items": len(data["universe_items"]), "acknowledged_items": count,
            "activity_items": len(data["items"]), "paginated_fields_verified": persistence["storage_verified"],
            "manifest_readback_verified": True, "collection_seconds": collection_seconds,
            "full_coordinator_pipeline_accepted": False, "strategy_evidence_eligible": False}


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
