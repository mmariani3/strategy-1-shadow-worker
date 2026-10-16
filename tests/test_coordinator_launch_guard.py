"""Offline controller/review acceptance. No real process, provider or DB calls."""
from copy import deepcopy
from dataclasses import replace
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import uuid

import pytest

from coordinator_launch_guard import (Policy, Blocked, SERVICES, SERVICE, WORKSPACE, DATABASE, URL,
    MASTERS, NOTICE_CASES, REQUIRED_FILES, preflight, notification_evidence)
from coordinator_acceptance_controller import Controller, snapshot_baseline
from catalyst_review_contract import review_record, FIELDS
from setup_evidence import digest
from test_catalyst_source_evidence import collector, packet, META
from test_coordinator_acceptance import NOW, wired, run


def services(active=False):
    return [{"id":sid, "ownerId":WORKSPACE, "autoDeploy":"no", "autoDeployTrigger":"off",
        "suspended":"not_suspended" if active and sid == SERVICE else "suspended"} for sid in sorted(SERVICES)]


@pytest.fixture
def tmp_path():
    # The machine's shared pytest temp root is inaccessible. Keep exclusive
    # synthetic attempt files in a fresh workspace directory; no cleanup/delete.
    path=Path(__file__).resolve().parents[2]/"tooling"/"launch-offline-evidence"/uuid.uuid4().hex
    path.mkdir(parents=True)
    return path


@pytest.fixture
def scenario(tmp_path):
    # This date exists only in invented offline fixtures; not a selected hosted date.
    p = Policy(day=date(2026,10,13), commit="a"*40, source_hash="b"*64, deployment="dep-offline",
        files=tuple((n,"c"*64) for n in sorted(REQUIRED_FILES)), masters=tuple((n,"OFFLINE_REV") for n in sorted(MASTERS)),
        schema_hash="d"*64, rehearsal_hash="e"*64, authorization_id="OFFLINE_NOT_USER_APPROVAL",
        authorized_until=NOW.replace(hour=15,minute=0,second=0))
    receipts=[{"case":case,"message_id":"OFFLINE_"+case,"receipt_evidence_id":"OFFLINE_RECEIPT_"+case,
        "outcome":"RECIPIENT_CONFIRMED", "sent_at":p.at(4,0).isoformat(), "received_at":p.at(4,1).isoformat()}
        for case in sorted(NOTICE_CASES)]
    rehearsal={"scope":"NORMAL_COORDINATOR_NO_SCAN", "acceptance_posts":0,
        "session_date":p.day.isoformat(),"commit":p.commit,"source_hash":p.source_hash,"deployment":p.deployment,
        "cleanup_services":services(),"database_status":"INACTIVE","notification_receipts":receipts,
        "watchdog":{"pid":2,"controller_pid":1,"service":SERVICE,"suspension_readback":"suspended",
            "ready_at":p.at(4,10).isoformat(),"resumed_at":p.at(4,11).isoformat(),
            "suspended_at":p.at(4,12).isoformat(),"deadline":p.at(4,13).isoformat()}}
    p=replace(p,rehearsal_hash=digest(rehearsal))
    before={"runs":[],"items":[],"events":[],"protected_tables":{n:[] for n in
        ("strategy_candidates","strategy_signals","strategy_candidate_events","execution_shadow_audit","journal_deliveries")}}

    class Ports:
        implementation_version="OFFLINE_IMPLEMENTATION"
        def __init__(self):
            self.time=p.at(5,45)
            self.calls=[]
            self.active=False
            self.db_status="ACTIVE_HEALTHY"
            self.fail=set()
            self.mutate=lambda e:e
            self.runtime_mutate=lambda e:e
            self.watchdog_mutate=lambda e:e
        def call(self,name):
            self.calls.append(name)
            if name in self.fail: raise TimeoutError("OFFLINE_PRIVATE_DIAGNOSTIC")
        def observations(self):
            self.call("observations")
            return self.mutate({"checked_at":self.time.isoformat(),"policy_hash":p.fingerprint,
                "file_sha256":dict(p.files),"masters":dict(p.masters),"services":services(self.active),
                "deployment":{"id":p.deployment,"commit":p.commit,"source_hash":p.source_hash,
                    "service":SERVICE,"url":URL,"status":"live"},
                "database":{"id":DATABASE,"status":self.db_status,"schema_sha256":p.schema_hash,
                    "matching_run_keys":[],"unfinished_run_ids":[],"baseline":snapshot_baseline(before)},
                "callers":{"active_schedules":[],"conflicting_process_ids":[],"active_pg_cron":[]},
                "rehearsal":deepcopy(rehearsal),"collector_id":"OFFLINE_COLLECTOR",
                "armed":{"policy_hash":p.fingerprint,"rehearsal_hash":p.rehearsal_hash,
                    "session_date":p.day.isoformat(),"verifier_id":"OFFLINE_VERIFIER","created_at":p.at(4,15).isoformat()}})
        def start_watchdog(self,sid,nonce,policy):
            assert sid==SERVICE and policy==p
            self.call("watchdog_start")
            return self.watchdog_receipt(nonce)
        def watchdog_receipt(self,nonce):
            self.call("watchdog_read")
            return self.watchdog_mutate({"heartbeat_at":self.time.isoformat(),"pid":2,"nonce":nonce,
                "policy_hash":p.fingerprint,"service":SERVICE,"suspend_at":p.at(6,20).isoformat(),
                "verify_by":p.at(6,25).isoformat()})
        def resume(self,sid):
            assert sid==SERVICE
            self.active=True  # A failed response may still have resumed it.
            self.call("resume")
        def runtime_probe(self):
            self.call("runtime")
            return self.runtime_mutate({"checked_at":self.time.isoformat(),"commit":p.commit,"source_hash":p.source_hash,
                "session_date":p.day.isoformat(),"database_id":DATABASE,"mode":"SHADOW",
                "broker_execution_enabled":False,"qualification_enabled":False,"journal_enabled":False,
                "strategy_evidence_eligible":False,"authenticated_probes":{n:"AUTHENTICATED_READ_ONLY" for n in
                    ("paper_calendar","sip","historical_sip","staging_database")}})
        def post(self,url,body):
            assert url==URL+"/scan/run-once" and body["run_class"]=="INFRASTRUCTURE_TEST"
            self.call("post")
            return {"accepted":True} # Must never be treated as storage proof.
        def readback(self):
            self.call("readback")
            return {"checked_at":self.time.isoformat(),"before":before,"after":before} # No run: deliberately fails verification.
        def suspend(self,sid):
            assert sid==SERVICE
            self.call("suspend")
            self.active=False
        def cleanup_observations(self):
            self.call("cleanup_read")
            return {"checked_at":self.time.isoformat(),"services":services(self.active)}
        def pause_database(self,db):
            assert db==DATABASE
            self.call("pause_db")
            self.db_status="INACTIVE"
        def database_status(self):
            self.call("db_read")
            return {"checked_at":self.time.isoformat(),"id":DATABASE,"status":self.db_status}
        def stop_watchdog(self,nonce):
            self.call("watchdog_stop")
            return {"nonce":nonce,"process_exited":True}
        def notify(self,code): self.call("notify")
    ports=Ports()
    controller=Controller(p,ports=ports,clock=lambda:ports.time,evidence_directory=tmp_path,controller_pid=1)
    return p,ports,controller,tmp_path


def ready(scenario):
    p,ports,c,_=scenario
    assert c.start()["status"]=="AWAITING_AUTHENTICATED_READINESS"
    ports.time=p.at(5,51)
    assert c.tick()["status"]=="READY_WAITING_SINGLE_DISPATCH_WINDOW"
    ports.time=p.at(6,0)
    return p,ports,c


def test_single_attempt_ambiguous_post_never_replayed(scenario):
    p,ports,c=ready(scenario)
    ports.fail.add("post")
    report=c.tick()
    assert report["status"]=="RUN_FAILED_OR_AMBIGUOUS_NO_REPLAY" and report["cleanup"]=="VERIFIED"
    assert ports.calls.count("post")==1
    c.tick(); c.start()
    other=Controller(p,ports=ports,clock=lambda:ports.time,evidence_directory=scenario[3],controller_pid=3)
    count=len(ports.calls)
    assert other.start()["status"]=="ATTEMPT_ALREADY_CONSUMED" and len(ports.calls)==count
    assert len(list(scenario[3].glob("*.post-intent.json")))==1
    assert "OFFLINE_PRIVATE_DIAGNOSTIC" not in str(report)


def test_http_accepted_is_not_independent_storage_acceptance(scenario):
    _,ports,c=ready(scenario)
    assert c.tick()["storage_readback"]=="NOT_VERIFIED"
    report=c.tick()
    assert report["status"]=="RUN_FAILED_OR_AMBIGUOUS_NO_REPLAY"
    assert report["storage_readback"]=="NOT_VERIFIED" and ports.calls.count("post")==1


@pytest.mark.parametrize("hour,minute",[(5,44),(5,50),(6,0)])
def test_start_window_rejects_before_activation(scenario,hour,minute):
    p,ports,c,_=scenario
    ports.time=p.at(hour,minute)
    assert c.start()["status"]=="PREPARATION_FAILED_CLOSED"
    assert "resume" not in ports.calls and "post" not in ports.calls


@pytest.mark.parametrize("field,value",[("mode","PAPER"),("broker_execution_enabled",True),
    ("qualification_enabled",True),("journal_enabled",True),("strategy_evidence_eligible",True),
    ("source_hash","WRONG"),("authenticated_probes",{})])
def test_runtime_safety_or_auth_failure_cleans_up(scenario,field,value):
    p,ports,c,_=scenario
    c.start()
    ports.time=p.at(5,51)
    ports.runtime_mutate=lambda x:{**x,field:value}
    report=c.tick()
    assert report["cleanup"]=="VERIFIED" and "post" not in ports.calls


@pytest.mark.parametrize("case",["service", "owner", "autodeploy", "commit", "database", "schema",
    "master", "files", "stale", "future", "run_exists", "unfinished", "caller", "armed", "rehearsal"])
def test_preflight_rejects_inconsistent_evidence(scenario,case):
    p,ports,c,_=scenario
    def mutate(x):
        if case=="service": x["services"].pop()
        if case=="owner": x["services"][0]["ownerId"]="wrong"
        if case=="autodeploy": x["services"][0]["autoDeploy"]="yes"
        if case=="commit": x["deployment"]["commit"]="f"*40
        if case=="database": x["database"]["id"]="production"
        if case=="schema": x["database"]["schema_sha256"]="f"*64
        if case=="master": x["masters"][next(iter(MASTERS))]="changed"
        if case=="files": x["file_sha256"].pop(next(iter(REQUIRED_FILES)))
        if case=="stale": x["checked_at"]=(ports.time-timedelta(seconds=121)).isoformat()
        if case=="future": x["checked_at"]=(ports.time+timedelta(seconds=1)).isoformat()
        if case=="run_exists": x["database"]["matching_run_keys"]=[p.run_key]
        if case=="unfinished": x["database"]["unfinished_run_ids"]=["other"]
        if case=="caller": x["callers"]["active_pg_cron"]=["other"]
        if case=="armed": x["armed"]["verifier_id"]=x["collector_id"]
        if case=="rehearsal": x["rehearsal"]["acceptance_posts"]=1
        return x
    ports.mutate=mutate
    assert c.start()["status"]=="PREPARATION_FAILED_CLOSED"
    assert "resume" not in ports.calls


@pytest.mark.parametrize("case",["missing", "accepted_only", "duplicate", "old"])
def test_notification_receipt_admission(scenario,case):
    p,ports,_,_=scenario
    receipts=ports.observations()["rehearsal"]["notification_receipts"]
    if case=="missing": receipts.pop()
    if case=="accepted_only": receipts[0]["outcome"]="PROVIDER_ACCEPTED"
    if case=="duplicate": receipts[0]["message_id"]=receipts[1]["message_id"]
    if case=="old": receipts[0]["sent_at"]=(p.at(4,0)-timedelta(days=2)).isoformat()
    with pytest.raises(Blocked): notification_evidence(receipts,p)


@pytest.mark.parametrize("case",["same_process", "stale", "nonce", "deadline"])
def test_watchdog_failure_prevents_resume(scenario,case):
    p,ports,c,_=scenario
    def mutate(x):
        if case=="same_process": x["pid"]=1
        if case=="stale": x["heartbeat_at"]=(ports.time-timedelta(seconds=16)).isoformat()
        if case=="nonce": x["nonce"]="wrong"
        if case=="deadline": x["suspend_at"]=p.at(6,21).isoformat()
        return x
    ports.watchdog_mutate=mutate
    c.start()
    assert "resume" not in ports.calls


def test_watchdog_before_resume_and_db_pause_before_stop(scenario):
    _,ports,c=ready(scenario)
    assert ports.calls.index("watchdog_start")<ports.calls.index("resume")
    c.cleanup()
    assert ports.calls.index("cleanup_read")<ports.calls.index("pause_db")<ports.calls.index("db_read")<ports.calls.index("watchdog_stop")


def test_resume_timeout_still_cleans_up(scenario):
    _,ports,c,_=scenario
    ports.fail.add("resume")
    assert c.start()["cleanup"]=="VERIFIED" and not ports.active


@pytest.mark.parametrize("case",["auth_deadline", "missed_dispatch", "baseline_drift", "late_probe"])
def test_deadline_and_fresh_baseline_fail_closed(scenario,case):
    p,ports,c,_=scenario
    c.start()
    if case=="auth_deadline":
        ports.time=p.at(5,55)
    else:
        ports.time=p.at(5,51); c.tick()
        ports.time=p.at(6,1) if case=="missed_dispatch" else p.at(6,0)
        if case=="baseline_drift":
            def mutate(x): x["database"]["baseline"]["runs"]["count"]+=1; return x
            ports.mutate=mutate
        if case=="late_probe":
            def late(x): ports.time=p.at(6,1); return x
            ports.runtime_mutate=late
    c.tick()
    assert "post" not in ports.calls and c.report["cleanup"]=="VERIFIED"


@pytest.mark.parametrize("failure",["suspend", "cleanup_read", "pause_db", "db_read", "watchdog_stop"])
def test_unresolved_cleanup_preserved(scenario,failure):
    _,ports,c=ready(scenario)
    ports.fail.add(failure)
    report=c.cleanup()
    if failure=="watchdog_stop":
        assert report["watchdog_shutdown"]=="UNRESOLVED" and report["cleanup"]=="VERIFIED"
    else:
        assert report["cleanup"]=="UNRESOLVED" and "watchdog_stop" not in ports.calls
    if failure in {"suspend","cleanup_read"}: assert "pause_db" not in ports.calls


def test_notification_failure_never_blocks_cleanup(scenario):
    _,ports,c=ready(scenario)
    ports.fail.update({"post","notify"})
    report=c.tick()
    assert report["cleanup"]=="VERIFIED" and report["notification"]=="SEND_FAILED_DELIVERY_UNVERIFIED"


def test_cleanup_deadline_and_no_after_window_resume(scenario):
    p,ports,c=ready(scenario)
    ports.time=p.at(6,26)
    report=c.tick()
    assert report["cleanup"]=="VERIFIED" and not report["cleanup_by_deadline"]
    assert ports.calls.count("resume")==1 and "post" not in ports.calls


def test_duplicate_start_does_not_interrupt_current_owner(scenario):
    p,ports,c,path=scenario
    c.start()
    calls=list(ports.calls)
    c.start()
    other=Controller(p,ports=ports,clock=lambda:ports.time,evidence_directory=path,controller_pid=3)
    assert other.start()["status"]=="ATTEMPT_ALREADY_CONSUMED"
    assert ports.calls==calls and ports.active


def test_concurrent_start_only_one_activation(scenario):
    p,ports,c,path=scenario
    other=Controller(p,ports=ports,clock=lambda:ports.time,evidence_directory=path,controller_pid=3)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda obj:obj.start(),[c,other]))
    assert ports.calls.count("resume")==1
    assert {r["status"] for r in results}=={"AWAITING_AUTHENTICATED_READINESS","ATTEMPT_ALREADY_CONSUMED"}


def test_complete_offline_controller_with_normal_coordinator_readback(scenario,wired):
    p,ports,c,_=scenario
    before=wired.db.snapshot()
    assert run(wired).status_code==200
    after=wired.db.snapshot()
    def baseline(x): x["database"]["baseline"]=snapshot_baseline(before); return x
    ports.mutate=baseline
    ports.readback=lambda:{"checked_at":ports.time.isoformat(),"before":before,"after":after}
    ready(scenario)
    c.tick()  # one synthetic HTTP attempt
    assert c.tick()["storage_readback"]=="PASS"
    ports.time=p.at(6,20)
    report=c.tick()
    assert report["status"]=="FINISHED" and report["cleanup"]=="VERIFIED" and report["cleanup_by_deadline"]
    assert report["watchdog_shutdown"]=="VERIFIED" and ports.calls.count("post")==1
    assert report["full_discovery_accepted"] is False and report["strategy_evidence_eligible"] is False


@pytest.mark.parametrize("change",[{"commit":"latest"},{"files":()},
    {"authorization_id":""},{"authorized_until":NOW}])
def test_unpinned_or_expired_policy_fails_before_activation(scenario,change):
    p,ports,_,path=scenario
    c=Controller(replace(p,**change),ports=ports,clock=lambda:ports.time,evidence_directory=path,controller_pid=1)
    c.start()
    assert ports.calls == []


def test_cleanup_without_attempt_ownership_has_no_effects(scenario):
    _,ports,c,_=scenario
    assert c.cleanup()["cleanup"]=="NOT_ATTEMPT_OWNER" and ports.calls==[]


@pytest.fixture
def review_fixture():
    c,_=collector()
    p=packet(c,filings=[META])
    source=p["sources"][0]
    text=source["passages"][0]["text"]
    ref={"source_id":source["source_id"],"start":0,"end":len(text),"text_sha256":hashlib.sha256(text.encode()).hexdigest()}
    submission={"run_key":p["run_key"],"symbol":p["symbol"],"packet_sha256":p["packet_sha256"],
        "reviewer_id":"OFFLINE_REVIEWER","reviewed_at":NOW.isoformat(),"disposition":"REVIEW_REQUIRED",
        "findings":{name:{"assessment":"UNKNOWN","rationale":"Unresolved; requires explicit review","citations":[]}
            for name in FIELDS}}
    submission["findings"]["event_identity"]={"assessment":"SUPPORTED","rationale":"Invented passage attribution", "citations":[ref]}
    return p,submission


def test_structured_review_is_citation_validation_not_approval(review_fixture):
    p,s=review_fixture
    result=review_record(p,s,now=NOW)
    assert result["accepted_structure"]
    record=result["record"]
    assert record["candidate_state"]=="REVIEW_REQUIRED" and record["semantic_accuracy_verified"] is False
    assert not record["automatic_promotion"] and not record["strategy_evidence_eligible"]


@pytest.mark.parametrize("case",["packet", "symbol", "future", "approval", "offset", "hash", "source", "missing_citation", "missing_field"])
def test_review_rejects_unbound_or_untraceable_input(review_fixture,case):
    p,s=review_fixture
    ref=s["findings"]["event_identity"]["citations"][0]
    if case=="packet": s["packet_sha256"]="f"*64
    if case=="symbol": s["symbol"]="OTHER"
    if case=="future": s["reviewed_at"]=(NOW+timedelta(seconds=1)).isoformat()
    if case=="approval": s["disposition"]="APPROVED"
    if case=="offset": ref["end"]+=10000
    if case=="hash": ref["text_sha256"]="f"*64
    if case=="source": ref["source_id"]="UNKNOWN"
    if case=="missing_citation": s["findings"]["event_identity"]["citations"]=[]
    if case=="missing_field": s["findings"].pop("event_time")
    assert not review_record(p,s,now=NOW)["accepted_structure"]
