"""Bounded full-universe storage using the existing discovery JSON contract.

There is no default database client, endpoint or credential access here. Caller
must enforce staging/date/auth/watchdog guards and atomically claim a NEW unique
run before invoking this once. An ambiguous write is never replayed.
"""
from copy import deepcopy
import json
import time

from premarket_evidence_collection import SCHEMA
from setup_evidence import digest

MAX_ITEMS = 20000
BATCH_SIZE = 100
BATCH_BYTES = 1024 * 1024
STORAGE_SECONDS = 180
LABEL = "DATED_PRIOR_SESSION_UNIVERSE_COVERAGE_NOT_STRATEGY_EVIDENCE"
FIELDS = "run_id,symbol,discovered_via,mover_snapshot,news_evidence,independent_evidence,catalyst_category,provisional_tier,verification_status,promotion_status,notes"


def require(ok):
    if not ok:
        raise ValueError("EVIDENCE_STORAGE_CONTRACT")


def item_payload(run_id, symbol, evidence):
    require(evidence["schema"] == SCHEMA and evidence["record_kind"] == "UNIVERSE_COVERAGE"
            and evidence["experiment_class"] == "INFRASTRUCTURE_TEST"
            and evidence["strategy_eligible"] is False and evidence["symbol"] == symbol)
    return {"run_id": run_id, "symbol": symbol, "discovered_via": ["alpaca_dated_prior_session_coverage"],
            "mover_snapshot": {"universe_coverage": deepcopy(evidence)},
            "news_evidence": [], "independent_evidence": [], "catalyst_category": None,
            "provisional_tier": None, "verification_status": "REVIEW_REQUIRED",
            "promotion_status": "REVIEW_REQUIRED", "notes": LABEL}


def persist_universe(run_id, collection, *, write, read, context, time_available, clock=None):
    """Write once per batch, validate acknowledgement, then independently read.

    write/read have the existing (method, table, body/params) interface. Write
    adapters must attach exactly the supplied audit context and enforce their
    own fixed staging target and timeouts. Never upsert or retry. Readback scans
    all rows for this run, so extra, missing, changed or duplicate rows fail.
    """
    require(isinstance(run_id, str) and bool(run_id)
            and collection.get("schema") == SCHEMA
            and collection.get("experiment_class") == "INFRASTRUCTURE_TEST"
            and collection.get("strategy_eligible") is False
            and context.get("strategy_evidence_eligible") is False
            and all(context.get(k) for k in ("owner", "implementation_version", "reason")))
    items = collection["universe_items"]
    symbols = sorted(items)
    require(0 < len(symbols) <= MAX_ITEMS
            and set(symbols) == set(collection["collection"]["universe_symbols"]))
    # Validate every payload before the first mutation, rather than partially
    # writing malformed local evidence. These hashes bind every later readback.
    rows = {s: item_payload(run_id, s, items[s]) for s in symbols}
    expected = {s: digest(row) for s, row in rows.items()}
    clock = clock or time.monotonic
    started = clock()

    def permitted():
        return clock()-started < STORAGE_SECONDS and time_available()

    acknowledged, attempted, outcome, offset = [], 0, "ALL_ACKNOWLEDGED", 0
    ambiguous = []
    while offset < len(symbols):
        if not permitted():
            outcome = "TIME_BUDGET"
            break
        batch, size = [], 2
        for symbol in symbols[offset:offset+BATCH_SIZE]:
            row = rows[symbol]
            row_size = len(json.dumps(dict(row, transition_context=context),
                                     allow_nan=False).encode()) + (2 if batch else 0)
            if size+row_size > BATCH_BYTES:
                break
            batch.append(row)
            size += row_size
        if not batch:
            outcome = "PAYLOAD_LIMIT"
            break
        if not permitted():
            outcome = "TIME_BUDGET"
            break
        attempted += 1
        try:
            response = write("POST", "strategy_discovery_items", body=deepcopy(batch), context=deepcopy(context))
            require(isinstance(response, list) and len(response) == len(batch))
            actual = {}
            for row in response:
                require(row["symbol"] not in actual)
                actual[row["symbol"]] = digest({k: row[k] for k in FIELDS.split(",")})
            require(actual == {row["symbol"]: expected[row["symbol"]] for row in batch})
            acknowledged.extend(row["symbol"] for row in batch)
            offset += len(batch)
        except Exception:
            ambiguous = [row["symbol"] for row in batch]
            outcome = "WRITE_AMBIGUITY_OR_FAILURE"
            break

    readback, readback_complete, readback_outcome = {}, False, "UNVERIFIED"
    try:
        for page_offset in range(0, MAX_ITEMS+1, BATCH_SIZE):
            require(permitted())
            page = read("GET", "strategy_discovery_items", params={"select": FIELDS,
                "run_id": "eq."+run_id, "order": "symbol.asc,id.asc",
                "offset": str(page_offset), "limit": str(BATCH_SIZE)})
            require(isinstance(page, list) and len(page) <= BATCH_SIZE)
            for row in page:
                require(row["symbol"] not in readback and row["run_id"] == run_id)
                readback[row["symbol"]] = digest({k: row[k] for k in FIELDS.split(",")})
            if len(page) < BATCH_SIZE:
                readback_complete = True
                break
        readback_outcome = "MATCH" if readback_complete and readback == expected else "MISMATCH"
    except Exception:
        readback_outcome = "UNVERIFIED"
    # A timeout with committed rows may read back MATCH, but the ambiguous write
    # remains a failed acceptance. Retain both facts without replay or deletion.
    storage_verified = outcome == "ALL_ACKNOWLEDGED" and readback_outcome == "MATCH"
    return {"schema": SCHEMA, "status": "PARTIAL", "experiment_class": "INFRASTRUCTURE_TEST",
            "strategy_eligible": False, "full_discovery_accepted": False,
            "storage_verified": storage_verified,
            "collection_storage_accepted": storage_verified and collection["integration"]["collection_complete"],
            "all_prior_closes_available": collection["integration"]["all_prior_closes_available"],
            "expected_count": len(expected), "expected_digest": digest(expected),
            "acknowledged_symbols": acknowledged, "unacknowledged_symbols": symbols[offset:],
            "ambiguous_symbols": ambiguous, "persistence_outcome": outcome,
            "write_requests_attempted": attempted, "readback_outcome": readback_outcome,
            "readback_count": len(readback), "readback_digest": digest(readback),
            "readback_complete": readback_complete}
