"""Request-scoped controls for the NORMAL Coordinator; no deploy/activation code.

No module-level application or permit is provided. A future dated controller
must establish deployment, isolation, watchdog and notification admission.
This module never reads encrypted stores, resumes services or retries writes.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime, time as daytime, timezone
import json
import time
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import requests
from fastapi import HTTPException
from setup_evidence import digest

ACTIVE = ContextVar("coordinator_acceptance_controls", default=None)
SERVICE = "srv-dal8abbl550s73cj3jm0"
DATABASE = "https://cihwmameyylixouggwxk.supabase.co"
CHANNELS = ("earnings_guidance", "corporate_news", "analyst_actions", "sector_industry",
            "premarket_movers_unusual_activity", "macro_economic_calendar")
SOURCE_HOSTS = frozenset(("data.alpaca.markets", "paper-api.alpaca.markets", "www.sec.gov",
                         "data.sec.gov", "api.stlouisfed.org", "www.ismworld.org",
                         "nfs.faireconomy.media"))
ITEM_FIELDS = ("run_id", "symbol", "discovered_via", "mover_snapshot", "news_evidence",
               "independent_evidence", "catalyst_category", "provisional_tier",
               "verification_status", "promotion_status", "notes", "transition_context")


def active():
    return ACTIVE.get()


def require(ok, code, status=409):
    if not ok:
        raise HTTPException(status, code)


class Controls:
    """Finite request budget plus fixed staging-only data access.

    Caller supplies an already verified permit. This is not a launch verifier.
    In particular a dictionary of booleans is NOT hosted arming evidence.
    Offline tests inject all transport; the default transport is never called
    without identity and deadline checks. No broker endpoint is permitted.
    """
    def __init__(self, *, session_date, implementation, transport=None, now=None,
                 clock=None, source_limit=2000, sleep=None):
        self.day = session_date
        self.implementation = implementation
        self.transport = transport or requests.request
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.clock = clock or time.monotonic
        self.started = self.clock()
        self.sleep = sleep or time.sleep
        self.last_sec_request = None
        self.source_limit = min(source_limit, 2000)
        self.source_calls = 0
        self.run_id = None
        self.run_key = None
        self.identity = None
        self.context = {"owner": "discovery_coordinator", "implementation_version": implementation,
                        "reason": "COORDINATOR_STAGING_INFRASTRUCTURE_ACCEPTANCE",
                        "strategy_evidence_eligible": False}
        self.sec = {}
        self.coverage = {}
        self.storage = None
        self.claim_started = False
        self.claim_write_sent = False
        self.owns_run = False
        self.persist_started = False
        self.finalize_sent = False
        self.attempted_symbols = set()

    def seconds_left(self, purpose):
        local = self.now().astimezone(ZoneInfo("America/Los_Angeles"))
        require(local.date() == self.day, "ACCEPTANCE_DATE_EXPIRED", 403)
        cutoff = datetime.combine(self.day, daytime(6, 10 if purpose == "source" else 15),
                                  tzinfo=ZoneInfo("America/Los_Angeles"))
        return min((cutoff-local).total_seconds(),
                   (600 if purpose == "source" else 900) - (self.clock()-self.started))

    def admit(self, req, *, service, database, ruleset):
        require(self.identity is None, "CONTROLS_ALREADY_USED", 403)
        require(service == SERVICE and (database or "").rstrip("/") == DATABASE
                and ruleset == "v0.3" and req.session_date == self.day
                and req.phase == "PREMARKET" and req.run_class == "INFRASTRUCTURE_TEST"
                and req.include_dated_prior_evidence, "ACCEPTANCE_SCOPE_REJECTED", 403)
        local = self.now().astimezone(ZoneInfo("America/Los_Angeles"))
        require(local.date() == self.day and local.hour == 6 and local.minute == 0,
                "ACCEPTANCE_SINGLE_MINUTE_ONLY", 403)
        self.identity = digest({"request": req.model_dump(mode="json"),
                                "implementation": self.implementation,
                                "contract": "normal-coordinator-acceptance/v1"})

    def source_get(self, url, **kwargs):
        parts = urlsplit(url)
        require(self.identity is not None and parts.scheme == "https" and parts.hostname in SOURCE_HOSTS
                and parts.username is None and parts.password is None and parts.port in (None, 443),
                "SOURCE_DESTINATION_REJECTED", 403)
        # Paper API is calendar/assets read-only, never account or order access.
        require(parts.hostname != "paper-api.alpaca.markets" or parts.path in ("/v2/calendar", "/v2/assets"),
                "SOURCE_PATH_REJECTED", 403)
        remaining = self.seconds_left("source")
        require(remaining > 0 and self.source_calls < self.source_limit, "SOURCE_BUDGET_EXHAUSTED")
        if parts.hostname in ("www.sec.gov", "data.sec.gov"):
            # One isolated controller, combined metadata/document budget: <=5/s.
            # Other callers must remain off; this is not a distributed limiter.
            if self.last_sec_request is not None:
                delay = max(0, 0.2-(self.clock()-self.last_sec_request))
                require(remaining > delay, "SEC_RATE_WAIT_EXCEEDS_DEADLINE")
                if delay:
                    self.sleep(delay)
                require(self.clock()-self.last_sec_request >= 0.199999,
                        "SEC_RATE_WAIT_INCOMPLETE")
            remaining = self.seconds_left("source")
            require(remaining > 0, "SOURCE_BUDGET_EXHAUSTED")
            self.last_sec_request = self.clock()
        self.source_calls += 1
        kwargs["timeout"] = (min(3, remaining), min(10, remaining))
        kwargs["allow_redirects"] = False
        response = None
        try:
            response = self.transport("GET", url, **kwargs)
            require(self.seconds_left("source") > 0, "SOURCE_RESPONSE_LATE")
            require(200 <= response.status_code < 300, "SOURCE_HTTP_UNAVAILABLE")
            if kwargs.get("stream"):
                original_iterator = response.iter_content
                def bounded_chunks(*args, **options):
                    for chunk in original_iterator(*args, **options):
                        require(self.seconds_left("source") > 0, "SOURCE_STREAM_LATE")
                        yield chunk
                    require(self.seconds_left("source") > 0, "SOURCE_STREAM_LATE")
                response.iter_content = bounded_chunks
            return response
        except Exception:
            if response is not None and hasattr(response, "close"):
                try:
                    response.close()
                except Exception:
                    pass
            raise HTTPException(502, "SOURCE_UNAVAILABLE_OR_DEADLINE") from None

    def database(self, method, table, *, headers, body=None, params=None):
        require(self.identity is not None, "ACCEPTANCE_NOT_ADMITTED", 403)
        require(table in ("strategy_discovery_runs", "strategy_discovery_items")
                and method in ("GET", "POST", "PATCH"), "DATABASE_OPERATION_REJECTED", 403)
        params = deepcopy(params or {})
        if method == "PATCH":
            require(self.owns_run and not self.finalize_sent
                    and table == "strategy_discovery_runs" and self.run_key
                    and params == {"run_key": "eq."+self.run_key}, "PATCH_SCOPE_REJECTED", 403)
            require(isinstance(body, dict) and set(body) <= {"status", "channel_status", "candidates_discovered",
                    "macro_events", "macro_source", "macro_checked_at", "notes"}
                    and body.get("status") == "PARTIAL", "FINALIZATION_SCOPE_REJECTED", 403)
        if method == "GET":
            require((table == "strategy_discovery_runs" and self.run_key
                     and params.get("run_key") == "eq."+self.run_key)
                    or (table == "strategy_discovery_items" and self.run_id
                        and params.get("run_id") == "eq."+self.run_id), "READ_SCOPE_REJECTED", 403)
        payload = None
        if body is not None:
            rows = body if isinstance(body, list) else [body]
            for row in rows:
                if table == "strategy_discovery_items":
                    require(self.owns_run and not self.finalize_sent
                            and method == "POST" and self.run_id and row.get("run_id") == self.run_id
                            and set(row) == set(ITEM_FIELDS)-{"transition_context"}
                            and row.get("promotion_status") == "REVIEW_REQUIRED"
                            and row.get("verification_status") == "REVIEW_REQUIRED"
                            and row.get("provisional_tier") is None, "ITEM_SCOPE_REJECTED", 403)
                elif method == "POST":
                    require(self.claim_started and not self.claim_write_sent and self.run_key
                            and self.run_id is None and row.get("run_key") == self.run_key
                            and set(row) == {"session_date", "phase", "ruleset_version", "run_key",
                                            "experiment_class", "status", "channel_status", "notes"}
                            and row.get("experiment_class") == "INFRASTRUCTURE_TEST"
                            and row.get("status") == "IN_PROGRESS", "RUN_CLAIM_REJECTED", 403)
            payload = [dict(deepcopy(row), transition_context=deepcopy(self.context)) for row in rows]
            if not isinstance(body, list):
                payload = payload[0]
        remaining = self.seconds_left("write")
        require(remaining > 0, "DATABASE_DEADLINE")
        if method == "POST" and table == "strategy_discovery_runs":
            self.claim_write_sent = True
        elif method == "POST":
            symbols = [row["symbol"] for row in rows]
            require(len(set(symbols)) == len(symbols) and not self.attempted_symbols.intersection(symbols),
                    "ITEM_WRITE_ALREADY_ATTEMPTED")
            self.attempted_symbols.update(symbols)
        elif method == "PATCH":
            self.finalize_sent = True
        try:
            response = self.transport(method, DATABASE+"/rest/v1/"+table, headers=headers,
                json=payload, params=params, timeout=(min(3, remaining), min(10, remaining)),
                allow_redirects=False)
            require(self.seconds_left("write") > 0, "DATABASE_RESPONSE_LATE")
            return response
        except Exception:
            # May have committed. Caller records ambiguity; never retry here.
            raise HTTPException(502, "DATABASE_AMBIGUOUS_OR_UNAVAILABLE") from None

    def claim(self, req, key, *, headers):
        require(not self.claim_started and key == "|".join(("STRATEGY_1", req.session_date.isoformat(),
                req.phase, "v0.3", req.run_class)), "CLAIM_ALREADY_USED_OR_INVALID")
        self.claim_started = True
        self.run_key = key
        def read_existing():
            r = self.database("GET", "strategy_discovery_runs", headers=headers,
                              params={"select": "*", "run_key": "eq."+key, "limit": "2"})
            require(r.status_code == 200, "CLAIM_READ_UNAVAILABLE", 502)
            try:
                rows = r.json()
            except Exception:
                raise HTTPException(502, "CLAIM_READ_INVALID") from None
            require(isinstance(rows, list) and len(rows) <= 1, "CLAIM_READ_INVALID", 502)
            return rows
        def existing(rows):
            row = rows[0]
            try:
                identity = json.loads(row["notes"])["request_identity"]
            except Exception:
                identity = None
            require(identity == self.identity, "RUN_KEY_CONTRACT_CONFLICT")
            require(row.get("experiment_class") == "INFRASTRUCTURE_TEST"
                    and row.get("run_key") == key and row.get("phase") == req.phase
                    and row.get("session_date") == req.session_date.isoformat()
                    and row.get("ruleset_version") == "v0.3", "EXISTING_RUN_SCOPE_MISMATCH")
            self.run_id = row["id"]
            return row, False  # Includes IN_PROGRESS; NEVER restart it.
        rows = read_existing()
        if rows:
            return existing(rows)
        body = {"session_date": req.session_date.isoformat(), "phase": req.phase,
                "ruleset_version": "v0.3", "run_key": key, "experiment_class": "INFRASTRUCTURE_TEST",
                "status": "IN_PROGRESS", "channel_status": {},
                "notes": json.dumps({"request_identity": self.identity, "strategy_evidence_eligible": False})}
        r = self.database("POST", "strategy_discovery_runs", headers=headers, body=body)
        if r.status_code in (400, 409):
            try:
                conflict = r.json().get("code") == "23505"
            except Exception:
                conflict = False
            if conflict:
                rows = read_existing()
                require(bool(rows), "CLAIM_RACE_UNVERIFIED", 502)
                return existing(rows)
        require(r.status_code in (200, 201), "CLAIM_WRITE_AMBIGUOUS", 502)
        try:
            rows = r.json()
        except Exception:
            raise HTTPException(502, "CLAIM_WRITE_AMBIGUOUS") from None
        require(isinstance(rows, list) and len(rows) == 1
                and all(rows[0].get(k) == v for k, v in body.items()), "CLAIM_ACK_INVALID", 502)
        self.run_id = rows[0]["id"]
        self.owns_run = True
        return rows[0], True

    def persist(self, records, *, headers):
        require(self.owns_run and not self.persist_started and not self.finalize_sent, "PERSIST_REPLAY_REJECTED")
        self.persist_started = True
        require(len(records) <= 20000 and len({r["symbol"] for r in records}) == len(records),
                "ITEM_MANIFEST_INVALID")
        expected = {r["symbol"]: digest(dict(r, transition_context=self.context)) for r in records}
        ack, ambiguous, outcome = [], [], "ALL_ACKNOWLEDGED"
        start = 0
        while start < len(records):
            batch, size = [], 2
            for row in records[start:start+100]:
                row_size = len(json.dumps(dict(row, transition_context=self.context), allow_nan=False).encode())
                if size+row_size+(2 if batch else 0) > 1024*1024:
                    break
                size += row_size+(2 if batch else 0)
                batch.append(row)
            if not batch:
                outcome = "BATCH_PAYLOAD_LIMIT"
                break
            try:
                r = self.database("POST", "strategy_discovery_items", headers=headers, body=batch)
                require(r.status_code in (200, 201), "ITEM_ACK_HTTP")
                rows = r.json()
                require(len(rows) == len(batch), "ITEM_ACK_COUNT")
                actual = {row["symbol"]: digest({k: row[k] for k in ITEM_FIELDS}) for row in rows}
                require(actual == {row["symbol"]: expected[row["symbol"]] for row in batch}, "ITEM_ACK_FIELDS")
                ack.extend(row["symbol"] for row in batch)
                start += len(batch)
            except Exception:
                ambiguous = [row["symbol"] for row in batch]
                outcome = "WRITE_AMBIGUITY_OR_FAILURE"
                break
        found, complete = {}, False
        try:
            for offset in range(0, 20001, 100):
                r = self.database("GET", "strategy_discovery_items", headers=headers,
                    params={"select": ",".join(ITEM_FIELDS), "run_id": "eq."+self.run_id,
                            "order": "symbol.asc,id.asc", "offset": str(offset), "limit": "100"})
                require(r.status_code == 200, "READBACK_HTTP")
                rows = r.json()
                require(isinstance(rows, list) and len(rows) <= 100, "READBACK_PAGE")
                for row in rows:
                    require(row["symbol"] not in found and row["run_id"] == self.run_id, "READBACK_DUPLICATE")
                    found[row["symbol"]] = digest({k: row[k] for k in ITEM_FIELDS})
                if len(rows) < 100:
                    complete = True
                    break
        except Exception:
            complete = False
        self.storage = {"expected_count": len(expected), "expected_digest": digest(expected),
                        "acknowledged_count": len(ack), "acknowledged_symbols": ack,
                        "unacknowledged_symbols": sorted(set(expected)-set(ack)),
                        "ambiguous_symbols": ambiguous, "write_outcome": outcome,
                        "readback_complete": complete, "readback_matches": complete and found == expected,
                        "storage_verified": outcome == "ALL_ACKNOWLEDGED" and complete and found == expected}
        return self.storage

    @contextmanager
    def activate(self):
        token = ACTIVE.set(self)
        try:
            yield self
        finally:
            ACTIVE.reset(token)


def coverage_ledger(news, premarket, macro_sources, errors, by_symbol, sec, articles=()):
    """Source transport success is explicitly NOT six-channel completeness."""
    news_info = deepcopy(news or {})
    items = [item for values in by_symbol.values() for item in values]
    categories = {"earnings_guidance": "earnings_guidance", "corporate_news": "corporate_news",
                  "analyst_actions": "analyst_actions", "sector_industry": "sector_industry"}
    ledger = {}
    for channel, category in categories.items():
        matches = sorted({str(i.get("alpaca_news_id")) for i in items if i.get("category") == category})
        ledger[channel] = {"status": "PARTIAL" if news_info.get("pages_received", 0) else "DATA_UNAVAILABLE",
            "source": "ALPACA_NEWS", "source_collection": news_info, "matched_source_ids": matches,
            "transport_outcome": news_info.get("outcome", "PROVIDER_UNAVAILABLE"),
            "no_matching_leads": not matches,
            "classification": "KEYWORD_LEADS_REVIEW_REQUIRED", "channel_complete": False,
            "missing": ["CHANNEL_SPECIFIC_SOURCE_COVERAGE_UNVERIFIED", "EVENT_AND_SYMBOL_REVIEW_REQUIRED"]}
    activity_info = premarket.get("collection", {})
    activity_checked = bool(premarket.get("items")) or activity_info.get("outcome") == "FEED_EXHAUSTED"
    ledger[CHANNELS[4]] = {"status": "PARTIAL" if activity_checked else "DATA_UNAVAILABLE",
        "transport_outcome": activity_info.get("outcome", "PROVIDER_UNAVAILABLE"),
        "no_activity_rows": not bool(premarket.get("items")),
        "source": "ALPACA_SIP_1MIN", "source_collection": deepcopy(premarket.get("collection", {})),
        "channel_complete": False, "missing": ["UNUSUAL_ACTIVITY_AND_ELIGIBILITY_REVIEW_REQUIRED"]}
    ledger[CHANNELS[5]] = {"status": "PARTIAL" if macro_sources else "DATA_UNAVAILABLE",
        "calendar_sources_checked": list(macro_sources), "source_failures": list(errors),
        "calendar_sources": {name: ("RETRIEVED_REVIEW_REQUIRED" if name in macro_sources else "DATA_UNAVAILABLE")
                             for name in ("FRED_RELEASES_DATES", "ISM_RELEASE_CALENDAR", "FOREX_FACTORY_WEEKLY_CALENDAR")},
        "breaking_macro": "DATA_UNAVAILABLE_NOT_SEPARATELY_VERIFIED", "channel_complete": False,
        "missing": ["COMPLETE_CALENDAR_INVENTORY_UNVERIFIED", "BREAKING_MACRO_REVIEW_REQUIRED"]}
    manifest = [{k: deepcopy(article.get(k)) for k in ("id", "symbols", "source", "author", "url",
                "headline", "summary", "created_at", "updated_at")} for article in articles]
    return {"schema": "coordinator-coverage/v1", "channels": ledger, "sec_by_symbol": deepcopy(sec),
            "news_source_manifest": manifest,
            "unassigned_news_source_ids": [str(a.get("id")) for a in articles if not a.get("symbols")],
            "source_origin_independence": "REVIEW_REQUIRED_NOT_INFERRED_FROM_FEED_COUNT",
            "full_discovery_accepted": False, "strategy_evidence_eligible": False}
