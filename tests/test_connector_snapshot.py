"""Offline connector boundaries and no-scan controller integration."""
from copy import deepcopy
from dataclasses import replace
from datetime import date, timedelta
import hashlib
import json
import re

import pytest

from coordinator_connector_snapshot import (ConnectorSnapshotCollector, connector_arguments,
    decode_result, preservation_baseline, KIND, MAX_BYTES)
from coordinator_service_adapters import TABLES, AdapterError
from coordinator_launch_guard import DATABASE
from setup_evidence import digest
from test_coordinator_preflight_binding import rehearsal, probes
from test_coordinator_launch_guard import tmp_path
from test_coordinator_acceptance import NOW

EMPTY=hashlib.sha256(b"").hexdigest()


def evidence(query, now=NOW):
    return {"kind":KIND,"nonce":re.search("'nonce','([a-f0-9]+)'",query)[1],
        "run_key":re.search("'run_key','([^']+)'",query)[1],
        "checked_at":now.isoformat(),"finished_at":now.isoformat(),
        "transaction_read_only":"on","transaction_isolation":"repeatable read",
        "mvcc_snapshot":"100:100:","database":"postgres","role":"postgres","complete_visibility":True,
        "tables":[{"name":n,"rows":0,"sha256":EMPTY} for n in TABLES],
        "catalog":[{"name":n,"owner":"postgres","rls":True,"force_rls":False,"acl":None,
            "columns":[{"name":"id"}],"constraints":[],"indexes":[],"triggers":[],"policies":[]} for n in TABLES],
        "matching_run_count":0,"unfinished_run_count":0,"cron_installed":False,"other_active_session_ids":[]}


def wrap(data):
    block="\n<untrusted-data-1234-abcd>\n"+json.dumps([{"evidence":data}])+"\n</untrusted-data-1234-abcd>"
    return {"content":[{"type":"text","text":json.dumps({"result":"Untrusted provider data."+block})}]}


def collector(transform=lambda e:e):
    calls=[]
    def execute_sql(**args):
        calls.append(args)
        return wrap(transform(evidence(args["query"])))
    return ConnectorSnapshotCollector(execute_sql=execute_sql,day=NOW.date(),now=lambda:NOW),calls


def test_one_fixed_project_read_only_complete_query_and_tagged_fingerprints():
    c,calls=collector(); result=c.collect()
    assert len(calls)==1 and calls[0]["project_id"]==DATABASE
    sql=calls[0]["query"]
    assert sql.count("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")==1
    assert "SET LOCAL row_security = off" in sql and "LIMIT " not in sql
    assert all(("FROM public."+n+" t") in sql for n in TABLES)
    assert set(result["table_fingerprints"])==set(TABLES) and "snapshot" not in result
    assert preservation_baseline(result)["kind"]==KIND
    assert result["schema_sha256"]==digest(result["catalog"])
    assert not hasattr(c,"post") and not hasattr(c,"resume")


@pytest.mark.parametrize("change",[
    lambda e:e.update(nonce="0"*32),
    lambda e:e.update(kind="FULL_ROW_SNAPSHOT"),
    lambda e:e.update(run_key="OTHER"),
    lambda e:e.update(transaction_read_only="off"),
    lambda e:e.update(transaction_isolation="read committed"),
    lambda e:e.update(complete_visibility=False),
    lambda e:e.update(role="anon"),
    lambda e:e.update(mvcc_snapshot="unknown"),
    lambda e:e["tables"].pop(),
    lambda e:e["tables"].append(e["tables"][0]),
    lambda e:e["tables"][0].update(rows=True),
    lambda e:e["tables"][0].update(rows=-1),
    lambda e:e["tables"][0].update(rows=100001),
    lambda e:e["tables"][0].update(sha256="a"*64),
    lambda e:e["catalog"].pop(),
    lambda e:e["catalog"][0].update(columns=[]),
    lambda e:e.update(cron_installed=True),
    lambda e:e.update(matching_run_count=True),
    lambda e:e.update(unfinished_run_count=-1),
    lambda e:e.update(checked_at=(NOW-timedelta(seconds=1)).isoformat()),
    lambda e:e.update(finished_at=(NOW+timedelta(seconds=1)).isoformat()),
    lambda e:e.update(other_active_session_ids=["not-pid"]),
])
def test_bad_or_partial_connector_proof_fails_closed_without_retry(change):
    def altered(e): change(e); return e
    c,calls=collector(altered)
    with pytest.raises(AdapterError,match="^CONNECTOR_SNAPSHOT_UNAVAILABLE$"):
        c.collect()
    assert len(calls)==1


@pytest.mark.parametrize("response",[
    {"isError":True,"content":[{"type":"text","text":"PRIVATE_DIAGNOSTIC"}]},
    {"content":[{"type":"text","text":"truncated"}]},
    [{"evidence":{}}], [{"evidence":{}},{"evidence":{}}],
    {"result":"\n<untrusted-data-ab>\n[]\n</untrusted-data-cd>"},
    {"content":[{"type":"text","text":"x"*MAX_BYTES}]},
])
def test_malformed_truncated_or_error_response_redacted(response):
    c=ConnectorSnapshotCollector(execute_sql=lambda **kw:response,day=NOW.date(),now=lambda:NOW)
    with pytest.raises(AdapterError) as error: c.collect()
    assert str(error.value)=="CONNECTOR_SNAPSHOT_UNAVAILABLE"
    assert error.value.__cause__ is None


def test_callback_exception_redacted_and_not_retried():
    calls=[]
    def broken(**kw): calls.append(kw); raise RuntimeError("PRIVATE_DIAGNOSTIC")
    c=ConnectorSnapshotCollector(execute_sql=broken,day=NOW.date(),now=lambda:NOW)
    with pytest.raises(AdapterError,match="^CONNECTOR_SNAPSHOT_UNAVAILABLE$"): c.collect()
    assert len(calls)==1


def test_slow_connector_rejected_even_with_fresh_result():
    times=iter([0,61])
    c=ConnectorSnapshotCollector(execute_sql=lambda **kw:wrap(evidence(kw["query"])),
        day=NOW.date(),now=lambda:NOW,monotonic=lambda:next(times))
    with pytest.raises(AdapterError): c.collect()


@pytest.mark.parametrize("nonce",["'; DELETE FROM x;--","0"*31,"G"*32])
def test_sql_parameters_cannot_inject(nonce):
    with pytest.raises(ValueError): connector_arguments(date(2026,10,15),nonce)


@pytest.mark.parametrize("change",["none","row_changed","missing_table","existing_run","unfinished","caller","schema_changed"])
def test_connector_path_through_rehearsal_preserves_shutdown_and_no_scan(rehearsal,change):
    r=rehearsal; calls=[]
    def execute_sql(**kw):
        calls.append(kw)
        e=evidence(kw["query"],r.clock[0])
        if change=="row_changed" and len(calls)>1:
            e["tables"][0].update(rows=1,sha256="b"*64)
        if change=="missing_table": e["tables"].pop()
        if change=="existing_run": e["matching_run_count"]=1
        if change=="unfinished": e["unfinished_run_count"]=1
        if change=="caller": e["other_active_session_ids"]=[123]
        if change=="schema_changed" and len(calls)>1: e["catalog"][0]["rls"]=False
        return wrap(e)
    c=ConnectorSnapshotCollector(execute_sql=execute_sql,day=r.p.day,now=lambda:r.clock[0])
    ref=evidence(connector_arguments(r.p.day,"0"*32)["query"],r.clock[0])
    r.p=replace(r.p,schema_hash=digest(ref["catalog"]))
    r.connections.permit=r.p
    # Fixture's closure retains its original permit; update only the outer call
    # and deployment stub's source-independent schema field is not observed.
    r.connections.database=c
    from coordinator_rehearsal_binding import rehearse
    def sleep(seconds): r.clock[0]+=timedelta(seconds=seconds); r.mono[0]+=seconds
    # Fixture watchdog closure binds its old permit hash; retain all other
    # identity checks and rebind that hash to the new schema permit.
    original_receipt=r.connections.watchdog.receipt
    def receipt(): return {**original_receipt(),"policy_hash":r.p.fingerprint}
    r.connections.watchdog.receipt=receipt
    outcome=rehearse(r.p,connections=r.connections,evidence_directory=r.path,now=lambda:r.clock[0],
        monotonic=lambda:r.mono[0],sleep=sleep)
    assert outcome["acceptance_posts"]==0 and outcome["armed"] is False
    assert not any("/scan" in url for _,url in r.calls)
    if change=="none":
        assert outcome["status"]=="NO_SCAN_CHECKS_PASSED" and outcome["database_unchanged"]
    else:
        assert outcome["status"]!="NO_SCAN_CHECKS_PASSED"
    assert outcome["cleanup"]=="VERIFIED"
    if change in ("missing_table","existing_run","unfinished","caller"):
        assert not any(url.endswith("/resume") for _,url in r.calls)
