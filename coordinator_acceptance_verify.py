"""Pure independent readback checks; no connection, write, or repair behavior.

Input is a complete independently collected snapshot, not HTTP acceptance flags.
Collector completeness/protected table inventory must be separately established.
"""
from collections import Counter
import hashlib
import json


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _packet_require(ok):
    if not ok:
        raise ValueError("PACKET_INVALID")


def verify_packet(packet, *, run_key, symbol):
    """Independent structural/content checks; cannot prove semantic truth."""
    try:
        _packet_require(packet['schema'] == 'catalyst-review-packet/v1')
        _packet_require(packet['run_key'] == run_key and packet['symbol'] == symbol)
        _packet_require(packet['mode'] == 'SHADOW' and packet['status'] == 'REVIEW_REQUIRED')
        _packet_require(packet['experiment_class'] == 'INFRASTRUCTURE_TEST')
        flags = ('strategy_evidence_eligible', 'same_event_verified', 'source_independence_verified', 'issuer_relationship_verified', 'event_timestamp_verified', 'qualification_created', 'automatic_promotion', 'full_discovery_accepted')
        _packet_require(all((packet[k] is False for k in flags)))
        _packet_require(fingerprint({k: v for k, v in packet.items() if k != 'packet_sha256'}) == packet['packet_sha256'])
        _packet_require(isinstance(packet['sources'], list) and len(packet['sources']) <= 18)
        for record in packet['sources']:
            _packet_require(isinstance(record['source_id'], str) and record['source_id'])
            _packet_require(all((record[k] is False for k in ('same_event_verified', 'source_independence_verified', 'issuer_relationship_verified', 'event_timestamp_verified'))))
            if record['status'] == 'UNAVAILABLE':
                _packet_require(record['reason'] and record['passages'] == [])
                continue
            _packet_require(record['status'] == 'CONTENT_RETRIEVED_REVIEW_REQUIRED')
            _packet_require(record['content_retrieval_proves_catalyst'] is False and record['untrusted_source_content'] is True)
            _packet_require(0 < record['body_bytes'] <= 512 * 1024)
            cursor, fragments = (0, [])
            for passage in record['passages']:
                _packet_require(passage['start'] == cursor and 0 < len(passage['text']) <= 1500)
                cursor += len(passage['text'])
                _packet_require(passage['end'] == cursor)
                fragments.append(passage['text'])
            text = ''.join(fragments)
            _packet_require(0 < cursor == record['retained_text_chars'] <= 24000)
            _packet_require(record['normalized_text_chars'] >= cursor)
            _packet_require(record['text_truncated'] is (record['normalized_text_chars'] > cursor))
            actual = hashlib.sha256(text.encode()).hexdigest()
            _packet_require(actual == record['retained_text_sha256'])
            if not record['text_truncated']:
                _packet_require(actual == record['normalized_text_sha256'])
            for key in ('raw_sha256', 'normalized_text_sha256'):
                _packet_require(len(record[key]) == 64 and all((c in '0123456789abcdef' for c in record[key])))
        return True
    except (AssertionError, KeyError, TypeError, ValueError, AttributeError):
        return False


def verify(before, after, *, run_key, implementation):
    try:
        return _verify(before, after, run_key=run_key, implementation=implementation)
    except (KeyError, TypeError, ValueError, AttributeError, IndexError, OverflowError):
        # Malformed exported evidence is a failed verification, never an
        # unhandled exception or a reason to echo raw record contents.
        return {"passed": False, "failures": ["MALFORMED_SNAPSHOT"],
                "full_discovery_accepted": False, "strategy_evidence_eligible": False}


def _verify(before, after, *, run_key, implementation):
    failures = []
    def check(ok, code):
        if not ok:
            failures.append(code)
    required = {"runs", "items", "events", "protected_tables"}
    check(required <= before.keys() and required <= after.keys(), "SNAPSHOT_INCOMPLETE")
    if failures:
        return {"passed": False, "failures": failures}
    check(before["protected_tables"] == after["protected_tables"], "PROTECTED_TABLES_CHANGED")
    check({"strategy_candidates", "strategy_signals", "strategy_candidate_events", "execution_shadow_audit",
           "journal_deliveries"} <= before["protected_tables"].keys(), "PROTECTED_TABLE_INVENTORY_INCOMPLETE")
    new = {}
    for name in ("runs", "items", "events"):
        old_rows, new_rows = before[name], after[name]
        old_ids, new_ids = [r["id"] for r in old_rows], [r["id"] for r in new_rows]
        old_id_set = set(old_ids)
        check(len(set(old_ids)) == len(old_ids) and len(set(new_ids)) == len(new_ids), "DUPLICATE_ID_"+name)
        indexed = {r["id"]: r for r in new_rows}
        check(all(indexed.get(r["id"]) == r for r in old_rows), "PRIOR_ROWS_CHANGED_"+name)
        new[name] = [r for r in new_rows if r["id"] not in old_id_set]
    runs = new["runs"]
    check(not any(r.get("run_key") == run_key for r in before["runs"]), "RUN_KEY_EXISTED_AT_BASELINE")
    check(len(runs) == 1 and runs[0].get("run_key") == run_key, "EXACTLY_ONE_NEW_RUN_REQUIRED")
    if len(runs) != 1:
        return {"passed": False, "failures": failures}
    run = runs[0]
    check(run.get("status") == "PARTIAL" and run.get("experiment_class") == "INFRASTRUCTURE_TEST",
          "RUN_CLASS_OR_STATUS")
    check(not any(r.get("status") == "IN_PROGRESS" for r in after["runs"]), "UNFINISHED_RUN")
    try:
        notes = json.loads(run["notes"])
        storage = notes["storage"]
        channels = notes["coverage"]["channels"]
        check(set(channels) == {"earnings_guidance", "corporate_news", "analyst_actions", "sector_industry",
                               "premarket_movers_unusual_activity", "macro_economic_calendar"}, "CHANNEL_INVENTORY")
        check(notes["strategy_evidence_eligible"] is False and notes["full_discovery_accepted"] is False,
              "EXPERIMENT_EXCLUSION")
        check(storage["write_outcome"] == "ALL_ACKNOWLEDGED" and not storage["ambiguous_symbols"]
              and not storage["unacknowledged_symbols"], "ACKNOWLEDGEMENT_INCOMPLETE")
    except (KeyError, TypeError, ValueError):
        return {"passed": False, "failures": failures+["SUMMARY_INVALID"]}
    items = new["items"]
    symbols = [r["symbol"] for r in items]
    check(len(set(symbols)) == len(symbols), "DUPLICATE_RUN_SYMBOL")
    check(len(items) == run.get("candidates_discovered") == storage["expected_count"] == storage["acknowledged_count"],
          "ITEM_COUNTS")
    check(sorted(symbols) == sorted(storage["acknowledged_symbols"]), "ACKNOWLEDGED_MANIFEST")
    expected_fields = ("run_id", "symbol", "discovered_via", "mover_snapshot", "news_evidence",
                       "independent_evidence", "catalyst_category", "provisional_tier",
                       "verification_status", "promotion_status", "notes", "transition_context")
    actual = {}
    for row in items:
        check(row.get("run_id") == run["id"], "FOREIGN_RUN_ITEM")
        check(row.get("verification_status") == row.get("promotion_status") == "REVIEW_REQUIRED"
              and row.get("provisional_tier") is None and not row.get("orchestrator_candidate_id")
              and not row.get("qualification_review") and not row.get("setup_review"), "FORBIDDEN_ITEM_STATE")
        check(bool(row.get("discovered_via")), "UNTRACEABLE_ITEM")
        try:
            actual[row["symbol"]] = fingerprint({k: row[k] for k in expected_fields})
        except KeyError:
            check(False, "ITEM_FIELD_MISSING")
        trace = row.get("mover_snapshot", {}).get("discovery_trace", {})
        check(trace.get("run_key") == run_key and trace.get("strategy_evidence_eligible") is False
              and trace.get("same_event_verified") is False, "ITEM_TRACE")
        snapshot = row.get("mover_snapshot", {})
        check(verify_packet(snapshot.get("catalyst_review_packet", {}), run_key=run_key, symbol=row["symbol"]),
              "CATALYST_PACKET_INVALID")
        attachment = snapshot.get("dated_prior_session_evidence", {})
        prior = attachment.get("item", {})
        manifest = notes.get("collection_manifest", {})
        # Missing collector evidence must be explicitly unavailable, never a
        # fabricated close. An available close needs full accepted provenance.
        if prior.get("status") == "RAW_DAILY_CLOSE_REVIEW_REQUIRED":
            check(attachment.get("source_session_date") == run.get("session_date")
                  and attachment.get("prior_session") == manifest.get("previous_session_date")
                  and attachment.get("evidence_hash") == manifest.get("dated_prior_session_collection", {}).get("evidence_hash")
                  and prior.get("session_date") == manifest.get("previous_session_date")
                  and prior.get("asof") == run.get("session_date")
                  and prior.get("feed") == "sip" and prior.get("adjustment") == "raw"
                  and prior.get("strategy_eligible") is False, "DATED_PRIOR_BINDING")
        else:
            check(prior.get("status") == "UNAVAILABLE" and bool(prior.get("reason"))
                  or attachment.get("status") == "UNAVAILABLE" and bool(attachment.get("reason")),
                  "PRIOR_UNAVAILABLE_REASON")
        activity = snapshot.get("premarket_activity", {})
        if activity.get("previous_close_status") == "UNAVAILABLE":
            check(activity.get("gap_percent_unadjusted") is None
                  and bool(activity.get("previous_close_unavailable_reason")), "SNAPSHOT_GAP_REPAIRED")
    check(fingerprint(actual) == storage["expected_digest"], "INDEPENDENT_CONTENT_DIGEST")
    events = new["events"]
    check(len(events) == len(items)+2, "AUDIT_EVENT_COUNT")
    per_item = Counter(e.get("discovery_item_id") for e in events if e.get("discovery_item_id"))
    check(per_item == Counter({r["id"]: 1 for r in items}), "ITEM_AUDIT_COVERAGE")
    indexed_items = {r["id"]: r for r in items}
    for event in events:
        payload = event.get("payload", {})
        check(event.get("run_id") == run["id"] and payload.get("owner") == "discovery_coordinator"
              and payload.get("implementation_version") == implementation
              and payload.get("reason") == "COORDINATOR_STAGING_INFRASTRUCTURE_ACCEPTANCE", "AUDIT_ATTRIBUTION")
        check(payload.get("after", {}).get("transition_context", {}).get("strategy_evidence_eligible") is False,
              "AUDIT_EXPERIMENT_EXCLUSION")
        item_id = event.get("discovery_item_id")
        if item_id:
            check(payload.get("after") == indexed_items.get(item_id) and payload.get("before") is None,
                  "AUDIT_ITEM_AFTER_OR_BEFORE")
    run_events = [e.get("payload", {}) for e in events if not e.get("discovery_item_id")]
    initial = [e for e in run_events if e.get("after", {}).get("status") == "IN_PROGRESS"]
    final = [e for e in run_events if e.get("after", {}).get("status") == "PARTIAL"]
    check(len(initial) == len(final) == 1 and final[0].get("after") == run
          and initial[0].get("before") is None and final[0].get("before") == initial[0].get("after"),
          "AUDIT_RUN_CHAIN")
    return {"passed": not failures, "failures": sorted(set(failures)),
            "new_runs": len(runs), "new_items": len(items), "new_events": len(events),
            "full_discovery_accepted": False, "strategy_evidence_eligible": False,
            "limitations": ["Input snapshot completeness requires separate verification.",
                           "Does not establish semantic catalyst review or notification delivery."]}
