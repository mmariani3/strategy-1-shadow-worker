"""Fixed Supabase connector bridge for NO-SCAN preservation, never scan acceptance.

The execute_sql callback is the authenticated host tool, not a DB password or
cached result. Constructors perform no IO/network. No credentials are loaded.
Fingerprints cover every row but are NOT detailed row evidence for discovery.
"""
from datetime import date
from pathlib import Path
import hashlib
import json
import re
import time
import uuid

from coordinator_launch_guard import DATABASE, need, fresh, timestamp
from coordinator_service_adapters import TABLES, fail
from setup_evidence import digest

KIND = "NO_SCAN_FULL_TABLE_FINGERPRINT_V1"
MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 100000
HEX = re.compile("[a-f0-9]{64}")


def connector_arguments(day, nonce):
    need(type(day) is date and re.fullmatch("[a-f0-9]{32}", nonce), "CONNECTOR_REQUEST_SCOPE")
    run_key = f"STRATEGY_1|{day.isoformat()}|PREMARKET|v0.3|INFRASTRUCTURE_TEST"
    query = Path(__file__).with_suffix(".sql").read_text(encoding="utf-8")
    selects = []
    for name in TABLES:
        selects.append(f"""SELECT '{name}' AS name, count(*) AS rows,
 encode(sha256(convert_to(coalesce(string_agg(
 encode(sha256(convert_to(to_jsonb(t)::text,'UTF8')),'hex'),'' ORDER BY t.id::text COLLATE "C"),''),'UTF8')),'hex') AS sha256
 FROM public.{name} t""")
    query = query.replace("__FINGERPRINT_SELECTS__", "\nUNION ALL\n".join(selects))
    query = query.replace("__TABLE_NAMES__", ",".join("'"+n+"'" for n in TABLES))
    query = query.replace("__NONCE__", nonce).replace("__RUN_KEY__", run_key)
    return {"project_id": DATABASE, "query": query}


def decode_result(result):
    """Accept the actual MCP envelope or its structured single evidence row."""
    need(len(json.dumps(result, allow_nan=False).encode()) <= MAX_BYTES, "CONNECTOR_RESPONSE_LIMIT")
    if isinstance(result, dict):
        need(not result.get("isError", False), "CONNECTOR_PROVIDER_ERROR")
        if "content" in result:
            need(len(result["content"]) == 1 and result["content"][0]["type"] == "text",
                 "CONNECTOR_CONTENT_SHAPE")
            result = json.loads(result["content"][0]["text"])
        if isinstance(result, dict) and "result" in result:
            value = result["result"]
            if isinstance(value, str):
                # The provider's disclaimer is outside the data block.
                match = re.search(r"\n<untrusted-data-([a-f0-9-]+)>\s*\n([\s\S]*?)\n</untrusted-data-\1>", value)
                need(match is not None, "CONNECTOR_DATA_BOUNDARY")
                result = json.loads(match[2])
            else:
                result = value
    need(isinstance(result, list) and len(result) == 1 and set(result[0]) == {"evidence"},
         "CONNECTOR_RESULT_SHAPE")
    return result[0]["evidence"]


def preservation_baseline(data):
    """Tagged domains prevent swapping a full-row baseline for a fingerprint."""
    if data.get("kind") == KIND:
        return {"kind": KIND, "tables": data["table_fingerprints"]}
    need("kind" not in data, "UNKNOWN_SNAPSHOT_KIND")
    from coordinator_acceptance_controller import snapshot_baseline
    return {"kind": "FULL_ROW_SNAPSHOT", "tables": snapshot_baseline(data["snapshot"])}


class ConnectorSnapshotCollector:
    def __init__(self, *, execute_sql, day, now, monotonic=time.monotonic):
        need(callable(execute_sql) and type(day) is date, "CONNECTOR_BINDING_REQUIRED")
        self.execute_sql, self.day, self.now, self.monotonic = execute_sql, day, now, monotonic

    def collect(self):
        try:
            start = self.now()
            began = self.monotonic()
            nonce = uuid.uuid4().hex
            args = connector_arguments(self.day, nonce)
            # Exactly one request. The host must impose its RPC timeout; SQL
            # timeout bounds DB work, not a stalled connector/network call.
            response = self.execute_sql(**args)
            need(0 <= self.monotonic()-began <= 60, "CONNECTOR_DEADLINE")
            e = decode_result(response)
            required = {"kind","nonce","run_key","checked_at","finished_at","transaction_read_only",
                "transaction_isolation","mvcc_snapshot","database","role","complete_visibility","tables",
                "catalog","matching_run_count","unfinished_run_count","cron_installed","other_active_session_ids"}
            need(set(e) == required and e["kind"] == KIND and e["nonce"] == nonce
                 and e["run_key"] == f"STRATEGY_1|{self.day.isoformat()}|PREMARKET|v0.3|INFRASTRUCTURE_TEST",
                 "CONNECTOR_RESPONSE_BINDING")
            fresh(e["checked_at"], self.now(), 60)
            fresh(e["finished_at"], self.now(), 60)
            need(start <= timestamp(e["checked_at"]) <= timestamp(e["finished_at"]) <= self.now(),
                 "CONNECTOR_SERVER_TIME")
            need(e["transaction_read_only"] == "on" and e["transaction_isolation"] == "repeatable read"
                 and e["complete_visibility"] is True and e["role"] == "postgres"
                 and re.fullmatch(r"\d+:\d+:(\d+(,\d+)*)?", e["mvcc_snapshot"]),
                 "CONNECTOR_SNAPSHOT_VISIBILITY")
            rows = e["tables"]
            need(isinstance(rows,list) and len(rows)==len(TABLES)
                 and {r["name"] for r in rows}==set(TABLES), "CONNECTOR_TABLE_COVERAGE")
            for r in rows:
                need(set(r)=={"name","rows","sha256"} and type(r["rows"]) is int
                     and 0<=r["rows"]<=MAX_ROWS and HEX.fullmatch(r["sha256"]), "CONNECTOR_TABLE_DIGEST")
                if r["rows"]==0:
                    need(r["sha256"]==hashlib.sha256(b"").hexdigest(), "CONNECTOR_EMPTY_DIGEST")
            need(sum(r["rows"] for r in rows)<=MAX_ROWS, "CONNECTOR_ROW_LIMIT")
            catalog = e["catalog"]
            need(isinstance(catalog,list) and len(catalog)==len(TABLES)
                 and {r["name"] for r in catalog}==set(TABLES), "CONNECTOR_CATALOG_COVERAGE")
            for r in catalog:
                need(set(r)=={"name","owner","rls","force_rls","acl","columns","constraints","indexes","triggers","policies"}
                     and isinstance(r["columns"],list) and bool(r["columns"])
                     and all(isinstance(r[k],list) for k in ("constraints","indexes","triggers","policies")),
                     "CONNECTOR_CATALOG_SHAPE")
            for name in ("matching_run_count","unfinished_run_count"):
                need(type(e[name]) is int and e[name]>=0, "CONNECTOR_RUN_COUNT")
            # Conservative no-scan gate: cron installation needs a separate
            # reviewed caller inventory; never infer inactivity from installation.
            need(e["cron_installed"] is False, "CONNECTOR_CRON_REVIEW_REQUIRED")
            need(isinstance(e["other_active_session_ids"],list)
                 and all(type(v) is int for v in e["other_active_session_ids"]), "CONNECTOR_CALLER_SHAPE")
            return {"kind":KIND,"checked_at":e["checked_at"],"finished_at":e["finished_at"],
                "table_fingerprints":{r["name"]:{"count":r["rows"],"sha256":r["sha256"]} for r in rows},
                "catalog":catalog,"schema_sha256":digest(catalog),
                "matching_run_count":e["matching_run_count"],"unfinished_run_count":e["unfinished_run_count"],
                "active_pg_cron":[],"other_active_session_ids":e["other_active_session_ids"],
                "run_key":e["run_key"],"nonce":nonce,"mvcc_snapshot":e["mvcc_snapshot"],
                "query_sha256":hashlib.sha256(args["query"].encode()).hexdigest()}
        except Exception:
            fail("CONNECTOR_SNAPSHOT_UNAVAILABLE")
