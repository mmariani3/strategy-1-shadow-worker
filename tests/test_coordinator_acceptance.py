"""Invented offline data. No provider, hosted database, or trading connections."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

import discovery_coordinator as d
from coordinator_acceptance_app import create_app, app as locked_app
from coordinator_acceptance_controls import Controls, DATABASE, SERVICE, CHANNELS, active
from test_premarket_evidence_pipeline import collect

NOW = datetime(2026, 10, 13, 13, 0, 5, tzinfo=timezone.utc)
REQUEST = {"session_date": "2026-10-13", "phase": "PREMARKET", "run_class": "INFRASTRUCTURE_TEST",
           "include_dated_prior_evidence": True}
REAL_SEC_FETCH = d.fetch_recent_sec


def response(body, status=200):
    return SimpleNamespace(status_code=status, ok=200 <= status < 300,
                           json=lambda: deepcopy(body), text="OFFLINE_PRIVATE_DIAGNOSTIC")


class Database:
    def __init__(self):
        self.runs = [{"id": "prior-run", "run_key": "prior-key", "notes": "preserve-original"}]
        self.items = [{"id": "prior-item", "run_id": "prior-run", "symbol": "PRIOR", "original": [1, 2]}]
        self.calls = []
        self.events = []  # Simulated trigger records, NOT a real PostgreSQL proof.
        self.lose_ack = False
        self.corrupt_read = False
        self.corrupt_final = False
        self.race = False

    def __call__(self, method, url, **kw):
        assert url.startswith(DATABASE+"/rest/v1/")
        assert kw["allow_redirects"] is False
        table = url.rsplit("/", 1)[-1]
        self.calls.append((method, table))
        rows = self.runs if table == "strategy_discovery_runs" else self.items
        params, body = kw["params"], kw["json"]
        if method == "GET":
            found = [r for r in rows if all(r.get(k) == v[3:] for k, v in params.items() if v.startswith("eq."))]
            found = sorted(found, key=lambda r: r.get("symbol", ""))
            offset = int(params.get("offset", 0))
            found = deepcopy(found[offset:offset+int(params.get("limit", 100))])
            if self.corrupt_read and table == "strategy_discovery_items" and found:
                found[0]["promotion_status"] = "PROMOTED"
            if self.corrupt_final and table == "strategy_discovery_runs" and found and found[0].get("status") == "PARTIAL":
                found[0]["channel_status"] = {}
            return response(found)
        if method == "POST":
            incoming = body if isinstance(body, list) else [body]
            if table == "strategy_discovery_runs" and any(r.get("run_key") == body["run_key"] for r in rows):
                return response({"code": "23505"}, 409)
            created = [dict(deepcopy(r), id=f"{table}-{len(rows)+i}") for i, r in enumerate(incoming)]
            rows.extend(created)
            for row in created:
                self.audit(row, None, table)
            if self.race and table == "strategy_discovery_runs":
                return response({"code": "23505"}, 409)
            if self.lose_ack and table == "strategy_discovery_items":
                raise TimeoutError("OFFLINE_PRIVATE_DIAGNOSTIC")
            return response(created, 201)
        assert method == "PATCH" and table == "strategy_discovery_runs"
        found = [r for r in rows if r["run_key"] == params["run_key"][3:]]
        for row in found:
            before = deepcopy(row)
            row.update(deepcopy(body))
            self.audit(row, before, table)
        return response(found)

    def audit(self, after, before, table):
        item = table == "strategy_discovery_items"
        self.events.append({"id": f"event-{len(self.events)}", "run_id": after["run_id"] if item else after["id"],
            "discovery_item_id": after["id"] if item else None,
            "payload": {**deepcopy(after["transition_context"]), "after": deepcopy(after), "before": before}})

    def snapshot(self):
        return deepcopy({"runs": self.runs, "items": self.items, "events": self.events,
                         "protected_tables": {"strategy_candidates": [], "strategy_signals": [],
                                              "strategy_candidate_events": [],
                                              "execution_shadow_audit": [], "journal_deliveries": []}})


@pytest.fixture
def wired(monkeypatch):
    monkeypatch.setenv("RENDER_SERVICE_ID", SERVICE)
    monkeypatch.setattr(d, "SUPABASE_URL", DATABASE)
    monkeypatch.setattr(d, "SUPABASE_SECRET_KEY", "OFFLINE_DB")
    monkeypatch.setattr(d, "DISCOVERY_SERVICE_TOKEN", "OFFLINE_AUTH")
    monkeypatch.setattr(d, "DISCOVERY_SCHEDULER_TOKEN", None)
    monkeypatch.setattr(d, "ALPACA_API_KEY", "OFFLINE_KEY")
    monkeypatch.setattr(d, "ALPACA_API_SECRET", "OFFLINE_SECRET")
    data, _ = collect(count=5, active=2, missing=("S00004",))
    original = deepcopy(data)
    monkeypatch.setattr(d, "collect_premarket_with_prior", lambda *a, **k: deepcopy(data))
    monkeypatch.setattr(d, "fetch_movers", lambda *a: {"gainers": [{"symbol": "MOVER", "price": 9}]})
    monkeypatch.setattr(d, "fetch_fred_release_calendar", lambda *a: [])
    monkeypatch.setattr(d, "collect_ism_calendar", lambda *a, **k: [])
    monkeypatch.setattr(d, "collect_weekly_calendar", lambda *a, **k: [])
    headlines = ["earnings release", "acquisition", "analyst upgrade", "sector peers"]
    monkeypatch.setattr(d, "fetch_news", lambda *a: {"news": [
        {"id": i+1, "headline": h, "symbols": [f"S{i:05}"],
         "source": "OFFLINE_ISSUER", "url": f"https://example.invalid/evidence/{i}",
         "created_at": "2026-10-12T23:00:00Z", "updated_at": "2026-10-13T12:00:00Z"}
        for i, h in enumerate(headlines)], "collection": {"pages_received": 1,
        "feed_exhausted": True, "outcome": "FEED_EXHAUSTED", "requested_start": "2026-10-09T13:00:00Z",
        "requested_end": NOW.isoformat()}})
    monkeypatch.setattr(d, "fetch_ticker_map", lambda: {"S00000": 1, "S00001": 2})
    monkeypatch.setattr(d, "fetch_recent_sec", lambda *a: [
        {"source": "SEC EDGAR", "form": "8-K", "accession": "offline-only",
         "filing_date": "2026-10-12", "url": "https://example.invalid/unrelated-event"}])
    db, wall, tick, made = Database(), [NOW], [0], []
    def factory():
        controls = Controls(session_date=NOW.date(), implementation="OFFLINE_IMPLEMENTATION",
                            transport=db, now=lambda: wall[0], clock=lambda: tick[0])
        made.append(controls)
        return controls
    client = TestClient(create_app(factory))
    return SimpleNamespace(db=db, client=client, wall=wall, tick=tick, data=data, original=original,
                           controls=made, factory=factory)


def run(wired, **changes):
    return wired.client.post("/scan/run-once", json={**REQUEST, **changes},
                             headers={"Authorization": "Bearer OFFLINE_AUTH"})


def test_normal_scan_persists_separate_prior_and_all_six_channels(wired):
    old = deepcopy((wired.db.runs[0], wired.db.items[0]))
    result = run(wired)
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["status"] == "PARTIAL" and body["storage_verified"]
    assert body["full_discovery_accepted"] is False and body["strategy_evidence_eligible"] is False
    channels = body["coverage"]["channels"]
    assert set(channels) == set(CHANNELS)
    for i, channel in enumerate(CHANNELS[:4]):
        assert channels[channel]["matched_source_ids"] == [str(i+1)]
        assert channels[channel]["channel_complete"] is False
    assert channels[CHANNELS[5]]["breaking_macro"].startswith("DATA_UNAVAILABLE")
    items = {r["symbol"]: r for r in wired.db.items if r["id"] != "prior-item"}
    assert set(items) == {"S00000", "S00001", "S00002", "S00003", "MOVER"}
    active_item = items["S00000"]["mover_snapshot"]["premarket_activity"]
    assert active_item["previous_close_status"] == "UNAVAILABLE"
    assert active_item["previous_close_unavailable_reason"] == "WRONG_PREVIOUS_SESSION"
    assert active_item["gap_percent_unadjusted"] is None
    assert items["S00002"]["mover_snapshot"]["dated_prior_session_evidence"]["item"]["status"] == "RAW_DAILY_CLOSE_REVIEW_REQUIRED"
    assert items["MOVER"]["mover_snapshot"]["dated_prior_session_evidence"]["item"]["reason"] == "SYMBOL_NOT_REQUESTED"
    for row in items.values():
        assert row["verification_status"] == row["promotion_status"] == "REVIEW_REQUIRED"
        assert row["provisional_tier"] is None
        assert row["mover_snapshot"]["discovery_trace"]["same_event_verified"] is False
        assert row["transition_context"]["strategy_evidence_eligible"] is False
    notes = json.loads(wired.db.runs[-1]["notes"])
    assert notes["normal_coordinator_path"] and not notes["universe_coverage_rows_persisted"]
    assert notes["collection_manifest"]["universe_symbols"] == [f"S{i:05}" for i in range(5)]
    assert old == (wired.db.runs[0], wired.db.items[0])
    assert wired.data == wired.original and active() is None


@pytest.mark.parametrize("change", [{"run_class": "STRATEGY_1"}, {"phase": "POST_OPEN"},
    {"session_date": "2026-10-14"}, {"include_dated_prior_evidence": False}])
def test_request_scope_rejects_before_claim(wired, change):
    assert run(wired, **change).status_code == 403
    assert wired.db.calls == []


@pytest.mark.parametrize("minutes", [-1, 1, 15, 1440])
def test_date_and_minute_gate_precedes_database(wired, minutes):
    wired.wall[0] += timedelta(minutes=minutes)
    assert run(wired).status_code == 403 and not wired.db.calls


@pytest.mark.parametrize("field,value", [("SUPABASE_URL", "https://production.invalid"), ("RULESET_VERSION", "v99")])
def test_identity_rejected(wired, monkeypatch, field, value):
    monkeypatch.setattr(d, field, value)
    assert run(wired).status_code == 403 and not wired.db.calls


def test_wrong_service_rejected(wired, monkeypatch):
    monkeypatch.setenv("RENDER_SERVICE_ID", "production")
    assert run(wired).status_code == 403 and not wired.db.calls


@pytest.mark.parametrize("path", ["/items/abc/qualify", "/items/abc/setup", "/items/abc/promote",
    "/items/abc/reject", "/runs/scheduled", "/evidence/preview", "/orders", "/journal", "/monitor"])
def test_prohibited_routes_have_no_side_effect(wired, path):
    result = wired.client.post(path, json={}, headers={"Authorization": "Bearer OFFLINE_AUTH"})
    assert result.status_code == 403 and not wired.db.calls


def test_missing_or_bad_auth_never_claims(wired):
    for auth in ({}, {"Authorization": "Bearer WRONG"}):
        assert wired.client.post("/scan/run-once", json=REQUEST, headers=auth).status_code in (401, 403)
    assert not wired.db.calls


def test_exported_app_is_locked_even_with_valid_auth(wired):
    result = TestClient(locked_app).post("/scan/run-once", json=REQUEST,
        headers={"Authorization": "Bearer OFFLINE_AUTH"})
    assert result.status_code == 503 and not wired.db.calls


def test_repeat_and_reconstructed_controller_never_collect_twice(wired, monkeypatch):
    assert run(wired).status_code == 200
    before = deepcopy((wired.db.runs, wired.db.items))
    monkeypatch.setattr(d, "fetch_news", lambda *a: pytest.fail("Replay fetched sources"))
    replay = run(wired)
    assert replay.status_code == 200 and replay.json()["idempotent_replay"]
    assert before == (wired.db.runs, wired.db.items)
    assert len(wired.controls) == 2 and wired.controls[0] is not wired.controls[1]


def test_run_key_same_date_changed_request_conflicts(wired):
    assert run(wired).status_code == 200
    before = deepcopy((wired.db.runs, wired.db.items))
    assert run(wired, news_hours=12).status_code == 409
    assert before == (wired.db.runs, wired.db.items)


def test_atomic_unique_race_loser_does_not_collect(wired, monkeypatch):
    wired.db.race = True
    monkeypatch.setattr(d, "fetch_news", lambda *a: pytest.fail("Race loser fetched sources"))
    result = run(wired)
    assert result.status_code == 200 and result.json()["idempotent_replay"]
    assert result.json()["status"] == "IN_PROGRESS"
    assert len(wired.db.items) == 1


def test_lost_ack_readback_match_remains_failure_no_retry(wired):
    wired.db.lose_ack = True
    result = run(wired)
    assert result.status_code == 200 and not result.json()["storage_verified"]
    stored = json.loads(wired.db.runs[-1]["notes"])["storage"]
    assert stored["readback_matches"] and stored["ambiguous_symbols"]
    assert stored["acknowledged_count"] == 0
    assert wired.db.calls.count(("POST", "strategy_discovery_items")) == 1
    assert "OFFLINE_PRIVATE_DIAGNOSTIC" not in result.text + wired.db.runs[-1]["notes"]


def test_changed_readback_cannot_pass(wired):
    wired.db.corrupt_read = True
    assert run(wired).json()["storage_verified"] is False


def test_finalization_checks_channel_fields_not_only_count(wired):
    wired.db.corrupt_final = True
    assert run(wired).status_code == 502


def test_unavailable_channels_and_sec_not_valid_zero(wired, monkeypatch):
    def fail(*a, **k):
        raise RuntimeError("OFFLINE_PRIVATE_DIAGNOSTIC")
    for name in ("fetch_news", "fetch_fred_release_calendar", "collect_ism_calendar", "collect_weekly_calendar", "fetch_recent_sec"):
        monkeypatch.setattr(d, name, fail)
    result = run(wired)
    assert result.status_code == 200
    ledger = result.json()["coverage"]
    assert all(ledger["channels"][c]["status"] == "DATA_UNAVAILABLE" for c in (*CHANNELS[:4], CHANNELS[5]))
    assert ledger["sec_by_symbol"]["S00000"]["status"] == "UNAVAILABLE_OR_BUDGET_EXHAUSTED"
    assert "OFFLINE_PRIVATE_DIAGNOSTIC" not in result.text + wired.db.runs[-1]["notes"]


def test_zero_news_results_does_not_invent_channel_completion(wired, monkeypatch):
    monkeypatch.setattr(d, "fetch_news", lambda *a: {"news": [], "collection": {
        "pages_received": 1, "feed_exhausted": True, "outcome": "FEED_EXHAUSTED"}})
    channels = run(wired).json()["coverage"]["channels"]
    assert all(channels[c]["no_matching_leads"] and not channels[c]["channel_complete"] for c in CHANNELS[:4])


def test_late_source_and_write_deadline_fail_closed(wired):
    control = wired.factory()
    control.admit(d.ScanRequest(**REQUEST), service=SERVICE, database=DATABASE, ruleset="v0.3")
    called = []
    def late(*a, **k):
        called.append(a)
        wired.wall[0] += timedelta(minutes=10)
        return response({})
    control.transport = late
    with pytest.raises(HTTPException):
        control.source_get("https://data.alpaca.markets/v2/stocks/bars")
    with pytest.raises(HTTPException):
        control.source_get("https://data.alpaca.markets/v2/stocks/bars")
    assert len(called) == 1
    wired.wall[0] = NOW + timedelta(minutes=15)
    with pytest.raises(HTTPException):
        control.database("POST", "strategy_discovery_runs", headers={}, body={})
    assert len(called) == 1


@pytest.mark.parametrize("url", ["http://data.alpaca.markets/v2/stocks/bars",
    "https://paper-api.alpaca.markets/v2/orders", "https://api.alpaca.markets/v2/orders",
    "https://attacker.invalid/", "https://user:password@data.alpaca.markets/v2/stocks/bars"])
def test_source_destination_allowlist(wired, url):
    control = wired.factory()
    control.admit(d.ScanRequest(**REQUEST), service=SERVICE, database=DATABASE, ruleset="v0.3")
    with pytest.raises(HTTPException):
        control.source_get(url)
    assert not wired.db.calls


def test_independent_readback_verifier(wired):
    from coordinator_acceptance_verify import verify
    before = wired.db.snapshot()
    assert run(wired).status_code == 200
    result = verify(before, wired.db.snapshot(), run_key=d.make_run_key(d.ScanRequest(**REQUEST)),
                    implementation="OFFLINE_IMPLEMENTATION")
    assert result["passed"], result
    assert (result["new_runs"], result["new_items"], result["new_events"]) == (1, 5, 7)


@pytest.mark.parametrize("tamper", ["old_item", "old_run", "order", "missing_audit", "audit_after",
    "new_extra_item", "channel", "classification", "digest", "run_chain", "new_unrelated_run"])
def test_independent_verifier_rejects_corruption(wired, tamper):
    from coordinator_acceptance_verify import verify
    before = wired.db.snapshot()
    assert run(wired).status_code == 200
    after = wired.db.snapshot()
    if tamper == "old_item": after["items"][0]["original"].append(3)
    elif tamper == "old_run": after["runs"][0]["notes"] = "changed"
    elif tamper == "order": after["protected_tables"]["execution_shadow_audit"].append({"order": "forbidden"})
    elif tamper == "missing_audit": after["events"].pop(1)
    elif tamper == "audit_after": after["events"][1]["payload"]["after"]["symbol"] = "CHANGED"
    elif tamper == "new_extra_item": after["items"].append(dict(after["items"][-1], id="extra", symbol="EXTRA"))
    elif tamper == "run_chain": after["events"][-1]["payload"]["before"] = None
    elif tamper == "new_unrelated_run": after["runs"].append({"id": "alien", "run_key": "alien"})
    else:
        notes = json.loads(after["runs"][-1]["notes"])
        if tamper == "channel": notes["coverage"]["channels"].pop("analyst_actions")
        elif tamper == "classification": notes["strategy_evidence_eligible"] = True
        else: notes["storage"]["expected_digest"] = "bad"
        after["runs"][-1]["notes"] = json.dumps(notes)
    assert not verify(before, after, run_key=d.make_run_key(d.ScanRequest(**REQUEST)),
                      implementation="OFFLINE_IMPLEMENTATION")["passed"]


def test_symbol_less_news_retained_for_macro_sector_review(wired, monkeypatch):
    monkeypatch.setattr(d, "fetch_news", lambda *a: {"news": [{"id": 71, "symbols": [],
        "headline": "OFFLINE central bank announcement", "url": "https://example.invalid/71"}],
        "collection": {"pages_received": 1, "outcome": "FEED_EXHAUSTED", "feed_exhausted": True}})
    result = run(wired).json()["coverage"]
    assert result["unassigned_news_source_ids"] == ["71"]
    assert result["news_source_manifest"][0]["url"] == "https://example.invalid/71"
    assert not result["full_discovery_accepted"]


def test_acceptance_database_rejects_injected_qualification(wired):
    assert run(wired).status_code == 200
    c = wired.controls[-1]
    row = {k: v for k, v in wired.db.items[-1].items() if k not in ("id", "transition_context")}
    row["qualification_review"] = {"approved": True}
    calls = len(wired.db.calls)
    with pytest.raises(HTTPException):
        c.database("POST", "strategy_discovery_items", headers={}, body=row)
    with pytest.raises(HTTPException):
        c.database("PATCH", "strategy_discovery_runs", headers={}, params={"run_key": "eq."+c.run_key},
                   body={"status": "COMPLETE"})
    assert len(wired.db.calls) == calls


def test_source_call_cap_and_context_reset(wired):
    c = wired.factory()
    c.admit(d.ScanRequest(**REQUEST), service=SERVICE, database=DATABASE, ruleset="v0.3")
    calls = []
    c.source_limit = 1
    c.transport = lambda *a, **k: calls.append(a) or response({})
    with c.activate():
        c.source_get("https://data.alpaca.markets/v2/stocks/bars")
        with pytest.raises(HTTPException): c.source_get("https://data.alpaca.markets/v2/stocks/bars")
    assert active() is None and len(calls) == 1


def test_multiple_storage_pages_and_preservation(wired, monkeypatch):
    monkeypatch.setattr(d, "fetch_news", lambda *a: {"news": [{"id": i, "symbols": [f"NEWS{i:04}"],
        "headline": "OFFLINE earnings", "url": f"https://example.invalid/{i}"} for i in range(211)],
        "collection": {"pages_received": 5, "feed_exhausted": True, "outcome": "FEED_EXHAUSTED"}})
    result = run(wired)
    assert result.status_code == 200 and result.json()["storage_verified"]
    assert result.json()["candidates_discovered"] == 214
    assert wired.db.calls.count(("POST", "strategy_discovery_items")) == 3
    assert wired.db.calls.count(("GET", "strategy_discovery_items")) == 3


@pytest.mark.parametrize("function,args", [(d.qualify_item, ("x", None)), (d.construct_setup, ("x", None)),
    (d.reserve_artifact, ("x", "rejection_review", {})), (d.sb_insert, ("strategy_candidates", {}))])
def test_direct_mutation_helpers_also_blocked(wired, function, args):
    with wired.factory().activate(), pytest.raises(HTTPException) as error:
        function(*args)
    assert error.value.status_code == 403 and not wired.db.calls


def test_offline_explicit_rejection_preserves_attribution(monkeypatch):
    monkeypatch.setattr(d, "require_auth", lambda _: None)
    monkeypatch.setattr(d, "discovery_context", lambda _: ({"id": "fixture-item"},
                        {"id": "fixture-run", "experiment_class": "INFRASTRUCTURE_TEST"}))
    captured = {}
    monkeypatch.setattr(d, "reserve_artifact", lambda item, column, record: captured.update(
        item=item, column=column, row=d.attributable(record)))
    result = d.reject_item("fixture-item", d.RejectionRequest(reviewer="OFFLINE_REVIEWER",
        reviewed_at=datetime.now(timezone.utc)-timedelta(seconds=1), reason="OFFLINE unrelated event fixture"), None)
    assert result["operational_state"] == "REJECTED"
    assert captured["row"]["transition_context"]["reviewer"] == "OFFLINE_REVIEWER"
    assert captured["row"]["rejection_reason"] == "OFFLINE unrelated event fixture"
    assert captured["row"]["promotion_status"] == "REJECTED"


def test_independent_verifier_rejects_changed_prior_binding(wired):
    from coordinator_acceptance_verify import verify
    before = wired.db.snapshot()
    assert run(wired).status_code == 200
    after = wired.db.snapshot()
    item = next(r for r in after["items"] if r["symbol"] == "S00000")
    item["mover_snapshot"]["dated_prior_session_evidence"]["item"]["feed"] = "iex"
    result = verify(before, after, run_key=d.make_run_key(d.ScanRequest(**REQUEST)), implementation="OFFLINE_IMPLEMENTATION")
    assert "DATED_PRIOR_BINDING" in result["failures"]


def test_byte_bounded_batches_include_audit_context(wired, monkeypatch):
    monkeypatch.setattr(d, "fetch_news", lambda *a: {"news": [
        {"id": i, "symbols": [f"BULK{i}"], "headline": "OFFLINE", "summary": "x"*400000}
        for i in range(3)], "collection": {"pages_received": 1, "outcome": "FEED_EXHAUSTED"}})
    original = wired.db.__call__
    sizes = []
    def transport(method, url, **kw):
        if method == "POST" and url.endswith("strategy_discovery_items"):
            sizes.append(len(json.dumps(kw["json"]).encode()))
        return original(method, url, **kw)
    factory = wired.factory
    def controlled():
        c = factory()
        c.transport = transport
        return c
    wired.client = TestClient(create_app(controlled))
    assert run(wired).json()["storage_verified"]
    assert len(sizes) >= 2 and max(sizes) <= 1024*1024


@pytest.mark.parametrize("body", [{}, {"filings": {"recent": {"form": ["8-K"], "filingDate": [],
    "accessionNumber": [], "primaryDocument": []}}}, {"filings": {"recent": {
    "form": ["8-K"], "filingDate": ["2026-10-14"], "accessionNumber": ["offline"], "primaryDocument": ["x"]}}}])
def test_malformed_or_future_sec_is_not_empty_success(wired, body):
    c = wired.factory()
    c.admit(d.ScanRequest(**REQUEST), service=SERVICE, database=DATABASE, ruleset="v0.3")
    c.transport = lambda *a, **k: response(body)
    with c.activate(), pytest.raises(ValueError):
        REAL_SEC_FETCH("OFFLINE", 1)


def test_stream_deadline_checked_during_body_read(wired):
    c = wired.factory()
    c.admit(d.ScanRequest(**REQUEST), service=SERVICE, database=DATABASE, ruleset="v0.3")
    def chunks(*a, **k):
        yield b"first"
        wired.wall[0] += timedelta(minutes=10)
        yield b"late"
    r = response({})
    r.iter_content = chunks
    c.transport = lambda *a, **k: r
    streamed = c.source_get("https://nfs.faireconomy.media/ff_calendar_thisweek.json", stream=True)
    iterator = iter(streamed.iter_content(100))
    assert next(iterator) == b"first"
    with pytest.raises(HTTPException): next(iterator)
