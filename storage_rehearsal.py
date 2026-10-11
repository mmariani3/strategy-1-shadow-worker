"""One October 10 staging-only synthetic storage rehearsal; no market requests.

Separate entrypoint and run key. Never opens or replays October 9's acceptance.
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
import premarket_acceptance as storage

SERVICE = "srv-dal8abbl550s73cj3jm0"
DB = "https://cihwmameyylixouggwxk.supabase.co"
DAY = date(2026, 10, 10)
START = datetime(2026, 10, 11, 0, tzinfo=timezone.utc)
EXPIRES = datetime(2026, 10, 11, 3, tzinfo=timezone.utc)
LABEL = "OCT10_SYNTHETIC_STORAGE_REHEARSAL_NOT_MARKET_OR_STRATEGY_EVIDENCE"
KEY = "STORAGE_REHEARSAL|2026-10-10|PREMARKET|v0.3|INFRASTRUCTURE_TEST"
COUNT = 3689
VERSION = "0.1.0-isolated-storage-rehearsal"
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
require = storage.require


def now():
    return datetime.now(timezone.utc)


def source_hash():
    value = hashlib.sha256()
    for name in ("storage_rehearsal.py", "premarket_acceptance.py", "premarket_collection.py"):
        value.update(name.encode())
        value.update((Path(__file__).parent / name).read_bytes().replace(b"\r\n", b"\n"))
    return value.hexdigest()


def guard(authorization):
    token = os.getenv("DISCOVERY_SERVICE_TOKEN", "")
    if not token or not authorization or not hmac.compare_digest(authorization, "Bearer " + token):
        raise HTTPException(401, "AUTHENTICATION_REQUIRED")
    try:
        require(START <= now() < EXPIRES)
        require(os.getenv("RENDER_SERVICE_ID") == SERVICE)
        require(os.getenv("SUPABASE_URL", "").rstrip("/") == DB)
        require(os.getenv("RULESET_VERSION") == "v0.3" and bool(os.getenv("SUPABASE_SECRET_KEY")))
    except Exception:
        raise HTTPException(503, "REHEARSAL_CONFIGURATION_OR_DATE_UNVERIFIED") from None


def context():
    return {"owner": "synthetic_storage_rehearsal", "reason": LABEL,
            "implementation_version": os.getenv("RENDER_GIT_COMMIT", "unavailable") + ";" + source_hash(),
            "strategy_evidence_eligible": False, "synthetic": True}


def db_call(method, table, *, params=None, body=None):
    require(START <= now() < EXPIRES)
    require(os.getenv("RENDER_SERVICE_ID") == SERVICE and os.getenv("SUPABASE_URL", "").rstrip("/") == DB)
    require((method, table) in {("GET", "strategy_discovery_runs"), ("POST", "strategy_discovery_runs"),
        ("PATCH", "strategy_discovery_runs"), ("GET", "strategy_discovery_items"), ("POST", "strategy_discovery_items")})
    if body is not None:
        if table == "strategy_discovery_items":
            require(method == "POST" and isinstance(body, list) and 0 < len(body) <= storage.WRITE_BATCH_SIZE)
            for row in body:
                require(set(row) == set(storage.FIELDS.split(",")))
                require(row["notes"] == LABEL and row["discovered_via"] == ["SYNTHETIC_STORAGE_FIXTURE"])
            audit_context = context()
            body = [dict(row, transition_context=audit_context) for row in body]
            require(len(storage.encoded_body(body)) <= storage.WRITE_BATCH_BYTES)
        else:
            require(isinstance(body, dict))
            if method == "POST":
                require(body.get("run_key") == KEY and body.get("experiment_class") == "INFRASTRUCTURE_TEST")
            else:
                require(params and params.get("run_key") == "eq." + KEY
                        and params.get("experiment_class") == "eq.INFRASTRUCTURE_TEST"
                        and params.get("status") == "eq.IN_PROGRESS" and params.get("id", "").startswith("eq."))
                require(body.get("status") == "PARTIAL")
            body = dict(body, transition_context=context())
    key = os.environ["SUPABASE_SECRET_KEY"]
    headers = {"apikey": key, "Prefer": "return=representation"}
    if key.count(".") == 2:
        headers["Authorization"] = "Bearer " + key
    response = requests.request(method, DB + "/rest/v1/" + table, params=params, json=body,
                                headers=headers, timeout=(3, 10), allow_redirects=False)
    require(response.status_code == (201 if method == "POST" else 200))
    result = response.json()
    require(isinstance(result, list))
    return result


def get_run():
    rows = db_call("GET", "strategy_discovery_runs", params={"select": "id,status,notes,run_key,experiment_class,candidates_discovered",
        "run_key": "eq." + KEY, "limit": "2"})
    require(len(rows) <= 1)
    if rows:
        require(rows[0]["run_key"] == KEY and rows[0]["experiment_class"] == "INFRASTRUCTURE_TEST")
    return rows[0] if rows else None


def fixture_items():
    # No prices, trades or purported market observations. Fixed 2 KiB padding
    # exercises JSON throughput; it does not model the distribution of live rows.
    return {f"ZZTEST{i:06}": {"synthetic": True, "strategy_evidence_eligible": False,
            "fixture_index": i, "source": "SYNTHETIC_STORAGE_FIXTURE", "padding": "x" * 2048}
            for i in range(COUNT)}


def payload(run_id, symbol, evidence):
    row = storage.item_payload(run_id, symbol, evidence)
    row.update(discovered_via=["SYNTHETIC_STORAGE_FIXTURE"], notes=LABEL)
    return row


@app.get("/health")
def health():
    return {"application": LABEL, "version": VERSION, "commit": os.getenv("RENDER_GIT_COMMIT"),
        "source_hash": source_hash(), "mode": "SHADOW", "broker_execution_enabled": False,
        "journal_routes": False, "market_requests": False, "fixture_count": COUNT,
        "expires_at": EXPIRES.isoformat()}


@app.get("/rehearsal/preflight")
def preflight(authorization: str | None = Header(default=None)):
    guard(authorization)
    try:
        absent = get_run() is None
        return {**health(), "checked_at": now().isoformat(), "database": "STAGING",
                "run_key": KEY, "run_absent": absent}
    except Exception:
        raise HTTPException(503, "REHEARSAL_PREFLIGHT_UNVERIFIED") from None


def execute():
    started = now()
    require(START <= started < EXPIRES-timedelta(minutes=12))
    require(get_run() is None)
    # Unique key claims this run durably, even if the response is lost.
    rows = db_call("POST", "strategy_discovery_runs", body={"session_date": DAY.isoformat(),
        "phase": "PREMARKET", "ruleset_version": "v0.3", "run_key": KEY,
        "experiment_class": "INFRASTRUCTURE_TEST", "status": "IN_PROGRESS",
        "channel_status": {}, "notes": LABEL})
    require(len(rows) == 1 and rows[0]["run_key"] == KEY)
    run_id = rows[0]["id"]
    deadline = started + timedelta(minutes=8)
    summary = storage.persist_items(run_id, fixture_items(), write=db_call, payload=payload,
        context=context(), time_available=lambda: now() < deadline-timedelta(minutes=2))
    expected = summary.pop("expected")
    read_started = time.monotonic()
    verified = storage.verify_items(run_id, expected, read=db_call, before_read=lambda: require(now() < deadline))
    summary.update(label=LABEL, run_id=run_id, run_key=KEY, synthetic=True,
        expected_fixture_count=COUNT, acknowledged_items=len(expected), paginated_fields_verified=verified,
        expected_item_digests=expected, readback_seconds=time.monotonic()-read_started,
        strategy_evidence_eligible=False, full_coordinator_pipeline_accepted=False,
        accepted=len(expected) == COUNT and not summary["unacknowledged_symbols"] and verified)
    notes = json.dumps(summary, sort_keys=True, allow_nan=False)
    require(now() < deadline)
    saved = db_call("PATCH", "strategy_discovery_runs", params={"id": "eq." + run_id, "run_key": "eq." + KEY,
        "experiment_class": "eq.INFRASTRUCTURE_TEST", "status": "eq.IN_PROGRESS"}, body={"status": "PARTIAL",
        "candidates_discovered": len(expected), "channel_status": {}, "notes": notes})
    require(len(saved) == 1)
    record = get_run()
    require(record["id"] == run_id and record["status"] == "PARTIAL" and record["notes"] == notes
            and record["candidates_discovered"] == len(expected))
    return {"accepted": summary["accepted"], "run_id": run_id, "acknowledged_items": len(expected),
            "paginated_fields_verified": verified, "manifest_readback_verified": True,
            "synthetic": True, "strategy_evidence_eligible": False}


@app.post("/rehearsal/run")
def run(authorization: str | None = Header(default=None)):
    guard(authorization)
    try:
        return execute()
    except Exception:
        raise HTTPException(503, "REHEARSAL_STOPPED_RECONCILE_WITHOUT_REPLAY") from None


@app.get("/rehearsal/result")
def result(authorization: str | None = Header(default=None)):
    guard(authorization)
    try:
        record = get_run()
        return {"run_key": KEY, "record": record}
    except Exception:
        raise HTTPException(503, "REHEARSAL_READBACK_UNVERIFIED") from None
