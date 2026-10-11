"""October 9 isolated staging collector/storage acceptance. No strategy routes.

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
from premarket_collection import collect_premarket, CALENDAR_URL, MAX_ASSETS

DAY = date(2026, 10, 9)
LAUNCH = datetime(2026, 10, 9, 13, tzinfo=timezone.utc)
STOP = LAUNCH + timedelta(minutes=15)
EXPIRES = LAUNCH + timedelta(minutes=25)
SERVICE = "srv-dal8abbl550s73cj3jm0"
DB = "https://cihwmameyylixouggwxk.supabase.co"
RUN_KEY = "STRATEGY_1|2026-10-09|PREMARKET|v0.3|INFRASTRUCTURE_TEST"
LABEL = "OCT9_PREMARKET_STORAGE_ACCEPTANCE_NOT_STRATEGY_EVIDENCE"
MAX_ITEMS = MAX_ASSETS
WRITE_BATCH_SIZE = 100
WRITE_BATCH_BYTES = 1024 * 1024
PERSISTENCE_SECONDS = 180
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
    if method != "GET":
        require(LAUNCH <= now() < STOP)
        require(table == "strategy_discovery_runs" or method == "POST")
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


def verify_items(run_id, expected, *, read=None, before_read=None):
    read = read or db_call
    before_read = before_read or (lambda: require(now() < STOP))
    actual = {}
    for offset in range(0, MAX_ITEMS+101, 100):
        before_read()
        rows = read("GET", "strategy_discovery_items", params={"select": FIELDS,
            "run_id": "eq." + run_id, "order": "symbol.asc,id.asc", "offset": str(offset), "limit": "100"})
        require(len(rows) <= 100)
        for row in rows:
            require(row["symbol"] not in actual)
            actual[row["symbol"]] = digest(row)
        if len(rows) < 100:
            return actual == expected
    return False


def persist_items(run_id, items, *, write=None, payload=None, context=None, time_available=None):
    """Bounded bulk inserts; acknowledge only a fully matched response, never retry."""
    started = time.monotonic()
    expected, symbols = {}, sorted(items)
    write, payload = write or db_call, payload or item_payload
    context = context if context is not None else audited_body({})["transition_context"]
    time_available = time_available or (lambda: now() < STOP-timedelta(minutes=2))
    outcome, failure, attempts = "ALL_ACKNOWLEDGED", False, 0
    offset = 0
    while offset < len(symbols):
        if len(expected) >= MAX_ITEMS:
            outcome = "ITEM_LIMIT"
            break
        if time.monotonic()-started >= PERSISTENCE_SECONDS or not time_available():
            outcome = "TIME_BUDGET"
            break
        batch, batch_bytes = [], 2  # JSON array brackets.
        try:
            for symbol in symbols[offset:offset+min(WRITE_BATCH_SIZE, MAX_ITEMS-len(expected))]:
                row = payload(run_id, symbol, items[symbol])
                row_bytes = len(encoded_body(dict(row, transition_context=context))) + (2 if batch else 0)
                if batch_bytes + row_bytes > WRITE_BATCH_BYTES:
                    break
                batch.append(row)
                batch_bytes += row_bytes
            if not batch:
                outcome = "PAYLOAD_LIMIT"
                break
            # Encoding a batch also consumes the budget; check again before dispatch.
            if time.monotonic()-started >= PERSISTENCE_SECONDS or not time_available():
                outcome = "TIME_BUDGET"
                break
            attempts += 1
            result = write("POST", "strategy_discovery_items", body=batch)
            require(isinstance(result, list) and len(result) == len(batch))
            wanted = {row["symbol"]: row for row in batch}
            seen = set()
            for row in result:
                symbol = row["symbol"]
                require(symbol in wanted and symbol not in seen)
                require(all(k in row and row[k] == v for k, v in wanted[symbol].items()))
                seen.add(symbol)
            expected.update({symbol: digest(row) for symbol, row in wanted.items()})
            offset += len(batch)
        except Exception:
            # Even a timeout may have committed the entire batch. Do not replay it.
            failure, outcome = True, "WRITE_AMBIGUITY_OR_FAILURE"
            break
    return {"expected": expected, "unacknowledged_symbols": symbols[offset:],
            "write_ambiguity_or_failure": failure, "persistence_outcome": outcome,
            "write_requests_attempted": attempts, "write_batch_size": WRITE_BATCH_SIZE,
            "write_batch_bytes": WRITE_BATCH_BYTES, "item_limit": MAX_ITEMS,
            "persistence_seconds": time.monotonic()-started}


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
    persistence = persist_items(run_id, data["items"])
    expected = persistence.pop("expected")
    skipped = persistence["unacknowledged_symbols"]
    persistence_seconds = persistence["persistence_seconds"]
    verified = verify_items(run_id, expected)
    collection = data["collection"]
    accepted = (bool(expected) and not skipped and verified and collection["outcome"] == "FEED_EXHAUSTED"
                and not collection["unprocessed_symbols"])
    summary = {"label": LABEL, "run_id": run_id, "run_key": RUN_KEY, "accepted": accepted,
        "collection": collection, "collected_items": len(data["items"]), "acknowledged_items": len(expected),
        **persistence,
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
