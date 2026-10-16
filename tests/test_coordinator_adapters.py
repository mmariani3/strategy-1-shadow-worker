"""Offline HTTP/DB fixtures plus a real local child with NO network authority."""
from datetime import timedelta
from pathlib import Path
from dataclasses import replace
from types import SimpleNamespace
import hashlib
import json
import subprocess
import sys
import time
import uuid

import pytest

from coordinator_service_adapters import (FixedHTTP, RenderAdapter, RuntimeAdapter, AdapterError,
    DatabaseCollector, EvidenceCollector, BoundPorts, RENDER, TABLES, REPO, URL, SERVICE, WORKSPACE, DATABASE)
from coordinator_driver import WatchdogProcess, drive
from coordinator_launch_guard import REQUIRED_FILES, Blocked
from test_coordinator_acceptance import NOW
from test_coordinator_launch_guard import scenario, services, tmp_path


class Response:
    def __init__(self,body,status=200):
        self.raw=body if isinstance(body,bytes) else json.dumps(body).encode()
        self.status_code=status; self.closed=False
    def iter_content(self,size):
        for i in range(0,len(self.raw),size): yield self.raw[i:i+size]
    def close(self): self.closed=True


class Session:
    def __init__(self,response=None):
        self.response=response or Response({}); self.calls=[]
        self.headers={'old':'must-clear'}; self.cookies={'old':'must-clear'}
        self.auth='old'; self.trust_env=True; self.adapters={}
    def request(self,*a,**kw):
        self.calls.append((a,kw))
        if isinstance(self.response,Exception): raise self.response
        return self.response(*a,**kw) if callable(self.response) else self.response


def http(response=None):
    session=Session(response)
    client=FixedHTTP(session=session,token='OFFLINE_SECRET',allowed={('GET',RENDER+'/services')},
        expires_at=NOW+timedelta(hours=1),now=lambda:NOW)
    return client,session


@pytest.mark.parametrize('url',[RENDER+'/services/'+SERVICE+'/env-vars','http://api.render.com/v1/services',
    'https://attacker.invalid','https://paper-api.alpaca.markets/v2/orders',RENDER+'/services?redirect=bad'])
def test_non_allowlisted_url_fails_before_transport(url):
    c,s=http()
    with pytest.raises(AdapterError): c.call('GET',url)
    assert s.calls==[]


def test_session_isolation_and_response_cleanup():
    r=Response({'ok':True}); c,s=http(r)
    assert c.call('GET',RENDER+'/services')=={'ok':True}
    assert not s.trust_env and s.auth is None and s.cookies=={} and s.headers=={}
    kw=s.calls[0][1]
    assert kw['allow_redirects'] is False and kw['stream'] is True
    assert kw['headers']['Authorization']=='Bearer OFFLINE_SECRET' and r.closed


@pytest.mark.parametrize('response',[Response(b'PRIVATE_DIAGNOSTIC',401),Response(b'PRIVATE_DIAGNOSTIC',302),
    Response(b'PRIVATE_DIAGNOSTIC',429),Response(b'not-json'),TimeoutError('OFFLINE_SECRET PRIVATE_DIAGNOSTIC')],
    ids=['unauthorized','redirect','rate-limit','malformed','timeout'])
def test_errors_redacted_without_retry(response):
    c,s=http(response)
    with pytest.raises(AdapterError) as exc: c.call('GET',RENDER+'/services')
    assert str(exc.value)=='ADAPTER_UNAVAILABLE' and len(s.calls)==1
    if isinstance(response,Response): assert response.closed


def test_response_size_and_expired_auth_fail_closed():
    c,s=http(Response(b'x'*101))
    with pytest.raises(AdapterError): c.call('GET',RENDER+'/services',max_bytes=100)
    c.expires=NOW
    before=len(s.calls)
    with pytest.raises(AdapterError): c.call('GET',RENDER+'/services')
    assert len(s.calls)==before


def test_runtime_post_is_consumed_on_ambiguous_timeout():
    s=Session(TimeoutError('OFFLINE_SECRET'))
    c=RuntimeAdapter(session=s,token='OFFLINE_TOKEN',expires_at=NOW+timedelta(hours=1),now=lambda:NOW)
    body={'session_date':'2026-10-13','phase':'PREMARKET','run_class':'INFRASTRUCTURE_TEST','include_dated_prior_evidence':True}
    with pytest.raises(AdapterError): c.post(URL+'/scan/run-once',body)
    with pytest.raises(Blocked): c.post(URL+'/scan/run-once',body)
    assert len(s.calls)==1


@pytest.mark.parametrize('size',[100,101])
def test_full_render_page_is_not_assumed_complete(size):
    s=Session(Response([{'service':services()[0]}]*size))
    c=RenderAdapter(session=s,token='OFFLINE',expires_at=NOW+timedelta(hours=1),now=lambda:NOW)
    with pytest.raises(AdapterError): c.inventory()


def test_watchdog_render_client_cannot_resume_or_read_environment():
    s=Session()
    c=RenderAdapter(session=s,token='OFFLINE',expires_at=NOW+timedelta(hours=1),now=lambda:NOW,suspend_only=True)
    with pytest.raises(Blocked): c.resume(SERVICE)
    with pytest.raises(AdapterError): c.http.call('GET',RENDER+'/services/'+SERVICE+'/env-vars')
    assert not s.calls


@pytest.mark.parametrize('status',[200,202])
def test_suspension_verified_by_readback_not_response(status):
    row=next(r for r in services(True) if r['id']==SERVICE)
    def response(method,url,**kw):
        if method=='POST': row['suspended']='suspended'; return Response(b'',status)
        return Response(row)
    s=Session(response)
    c=RenderAdapter(session=s,token='OFFLINE',expires_at=NOW+timedelta(hours=1),now=lambda:NOW,suspend_only=True)
    assert c.suspend(SERVICE)
    assert [a[0] for a,k in s.calls]==['GET','POST','GET']
    assert c.suspend(SERVICE)
    assert len([a for a,k in s.calls if a[0]=='POST'])==1


class Cursor:
    def __init__(self,conn): self.conn=conn; self.sql=''; self.offset=0; self.closed=False
    def execute(self,sql,params=None):
        self.sql=sql; self.offset=0; self.conn.calls.append((sql,params))
        if self.conn.fail and self.conn.fail in sql: raise RuntimeError('PRIVATE_DATABASE_DIAGNOSTIC')
    def table(self): return next(t for t in TABLES if ('public.'+t+' ') in self.sql+' ')
    def fetchone(self):
        if "current_setting" in self.sql: return self.conn.transaction
        if 'count(*)' in self.sql: return (len(self.conn.rows[self.table()])+self.conn.count_delta,)
        if 'jsonb_build_object' in self.sql: return (self.conn.catalog,)
        if 'pg_extension' in self.sql: return (self.conn.cron,)
        raise AssertionError('Unexpected fixed SQL')
    def fetchmany(self,size):
        rows=self.conn.rows[self.table()]
        batch=rows[self.offset:self.offset+size]; self.offset+=size
        return [(r,) for r in batch]
    def fetchall(self): return [(1,)] if self.conn.active_callers else []
    def close(self): self.closed=True


class Connection:
    def __init__(self):
        self.rows={t:[{'id':t+'-'+str(n),'status':'PARTIAL'} for n in range(3)] for t in TABLES}
        self.calls=[]; self.count_delta=0; self.fail=None; self.cron=False; self.active_callers=False
        self.transaction=('on','repeatable read'); self.rolled=False; self.closed=False
        self.catalog={k:[{'name':'OFFLINE_'+k}] for k in ('columns','indexes','triggers','constraints')}
        self.c=Cursor(self)
    def cursor(self,name=None): return Cursor(self) if name else self.c
    def rollback(self): self.rolled=True
    def close(self): self.closed=True


def test_database_consistent_read_only_snapshot_and_connection_cleanup():
    conn=Connection()
    c=DatabaseCollector(connect=lambda:conn,project_id=DATABASE,now=lambda:NOW)
    data=c.collect()
    assert data['baseline']['runs']['count']==3 and len(data['snapshot']['protected_tables'])==5
    assert conn.calls[0][0]=='BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'
    assert all(sql.startswith(('SELECT','select','SET LOCAL','BEGIN')) for sql,_ in conn.calls)
    assert conn.rolled and conn.closed and conn.c.closed


@pytest.mark.parametrize('case',['count_mismatch','duplicate_id','row_limit','byte_limit','query_failure','not_read_only','catalog_missing'])
def test_incomplete_database_evidence_is_rejected(case):
    conn=Connection(); kwargs={}
    if case=='count_mismatch': conn.count_delta=1
    if case=='duplicate_id': conn.rows[TABLES[0]][1]['id']=conn.rows[TABLES[0]][0]['id']
    if case=='row_limit': kwargs['max_rows']=2
    if case=='byte_limit': kwargs['max_bytes']=10
    if case=='query_failure': conn.fail='to_jsonb'
    if case=='not_read_only': conn.transaction=('off','read committed')
    if case=='catalog_missing': conn.catalog['triggers']=[]
    c=DatabaseCollector(connect=lambda:conn,project_id=DATABASE,now=lambda:NOW,**kwargs)
    with pytest.raises(AdapterError) as exc: c.collect()
    assert str(exc.value)=='DATABASE_SNAPSHOT_UNAVAILABLE' and conn.closed and conn.rolled


def test_wrong_database_rejected_before_connection():
    with pytest.raises(Blocked): DatabaseCollector(connect=lambda:pytest.fail('No connection'),project_id='production')


@pytest.mark.parametrize('operation',['rollback','close'])
def test_database_cleanup_failure_invalidates_evidence(operation):
    conn=Connection()
    def broken(): raise RuntimeError('PRIVATE_DIAGNOSTIC')
    setattr(conn,operation,broken)
    collector=DatabaseCollector(connect=lambda:conn,project_id=DATABASE,now=lambda:NOW)
    with pytest.raises(AdapterError,match='^DATABASE_CONNECTION_CLEANUP_UNVERIFIED$'):
        collector.collect()
    assert conn.c.closed


@pytest.mark.parametrize('case',['current','stale_master','other_database','active_session','changed_readback_schema'])
def test_collector_uses_files_and_actual_snapshot_without_restamping(scenario,tmp_path,case):
    p,ports,_,_=scenario
    for name in REQUIRED_FILES: (tmp_path/name).write_text('OFFLINE_FILE_'+name)
    hashes=tuple((name,hashlib.sha256((tmp_path/name).read_bytes()).hexdigest()) for name in sorted(REQUIRED_FILES))
    conn=Connection()
    db=DatabaseCollector(connect=lambda:conn,project_id=DATABASE,now=lambda:ports.time)
    preview=db.collect()
    p=replace(p,files=hashes,schema_hash=preview['schema_sha256'])
    observed=ports.observations()
    status=lambda:{'id':DATABASE if case!='other_database' else 'production','status':'ACTIVE_HEALTHY','checked_at':ports.time.isoformat()}
    master_time=ports.time-timedelta(seconds=121) if case=='stale_master' else ports.time
    if case=='active_session': conn.active_callers=True
    collector=EvidenceCollector(policy=p,source_directory=tmp_path,
        render=SimpleNamespace(inventory=lambda:services(),deployment=lambda policy:observed['deployment']),
        database=db,project_status=status,masters=lambda:{'checked_at':master_time.isoformat(),'revisions':dict(p.masters)},
        callers=lambda:{'checked_at':ports.time.isoformat(),'active_schedules':[],'conflicting_process_ids':[]},
        rehearsal=lambda:observed['rehearsal'],armed=lambda:observed['armed'],collector_id='OFFLINE_COLLECTOR',now=lambda:ports.time)
    if case in {'stale_master','other_database','active_session'}:
        with pytest.raises(Blocked): collector.collect()
    else:
        result=collector.collect()
        assert result['file_sha256']==dict(hashes) and result['database']['baseline']['runs']['count']==3
        if case=='changed_readback_schema':
            conn.catalog['indexes'].append({'name':'UNAPPROVED'})
            with pytest.raises(Blocked): collector.readback()
        else:
            before=collector.readback()['before']
            conn.rows[TABLES[0]].append({'id':'NEW','status':'PARTIAL'})
            after=collector.readback()
            assert after['before']==before and len(after['after']['runs'])==4


def test_bound_ports_pauses_only_fixed_database_after_fresh_isolation(scenario):
    p,_,_,_=scenario
    calls=[]
    ports=BoundPorts(policy=p,render=SimpleNamespace(inventory=lambda:services(True)),runtime_client=None,
        collector=None,watchdog_process=None,project_status=None,pause_project=lambda project:calls.append(project),
        notify=None,render_key='OFFLINE',implementation_version='OFFLINE',now=lambda:NOW)
    with pytest.raises(Blocked): ports.pause_database(DATABASE)
    with pytest.raises(Blocked): ports.pause_database('production')
    assert calls==[]
    ports.render=SimpleNamespace(inventory=lambda:services())
    ports.pause_database(DATABASE)
    assert calls==[DATABASE]


def test_deployment_identity_cannot_be_substituted(scenario):
    p,_,_,_=scenario
    target={'id':SERVICE,'ownerId':WORKSPACE,'repo':REPO,'serviceDetails':{'url':URL,
        'envSpecificDetails':{'startCommand':'uvicorn coordinator_acceptance_app:app --host 0.0.0.0 --port $PORT'}}}
    rows=[{'deploy':{'id':p.deployment,'commit':{'id':'f'*40},'status':'live'}}]
    session=Session(lambda method,url,**kw:Response(rows if url.endswith('/deploys') else target))
    adapter=RenderAdapter(session=session,token='OFFLINE',expires_at=NOW+timedelta(hours=1),now=lambda:NOW)
    with pytest.raises(AdapterError): adapter.deployment(p)


def test_driver_detects_clock_jump_and_cleans_up(scenario):
    p,ports,c,_=scenario
    tick=[0]
    def sleep(seconds): tick[0]+=seconds; ports.time+=timedelta(seconds=seconds+10)
    result=drive(c,monotonic=lambda:tick[0],sleep=sleep)
    assert result['status']=='CLOCK_DRIFT_OR_DRIVER_BUDGET' and result['cleanup']=='VERIFIED'
    assert 'post' not in ports.calls


def watchdog_fixture(path,failures=0,delay=0.4):
    nonce=uuid.uuid4().hex
    program=Path(__file__).resolve().parents[1]/'coordinator_watchdog_process.py'
    sha=hashlib.sha256(program.read_bytes()).hexdigest()
    (path/(nonce+'.offline-provider.json')).write_text(json.dumps({'service':SERVICE,'suspended':False,'failures_remaining':failures}))
    envelope={'mode':'offline','nonce':nonce,'policy_hash':'f'*64,'delay_seconds':delay}
    return WatchdogProcess(directory=path,program_sha256=sha),envelope


@pytest.mark.parametrize('failures',[0,1,20])
def test_real_independent_offline_watchdog_process(tmp_path,failures):
    manager,envelope=watchdog_fixture(tmp_path,failures)
    manager.start(envelope)
    try:
        end=time.monotonic()+4
        receipt=None
        while time.monotonic()<end and manager.process.poll() is None:
            try: receipt=manager.receipt(); break
            except FileNotFoundError: time.sleep(0.02)
        assert receipt and receipt['pid']==manager.process.pid and receipt['pid']!=__import__('os').getpid()
        assert receipt['mode']=='offline'
        manager.process.wait(timeout=6)
        result=json.loads((tmp_path/(envelope['nonce']+'.watchdog-result.json')).read_text())
        assert result['suspended'] is (failures<6)
        assert result['attempts']==min(failures+1,6)
        assert 'render_key' not in str(result)
        assert manager.result()==result
    finally:
        if manager.process.poll() is None: manager.process.terminate(); manager.process.wait(timeout=5)


def test_watchdog_outlives_launcher(tmp_path):
    manager,envelope=watchdog_fixture(tmp_path,delay=0.5)
    code="""import json,sys
from coordinator_driver import WatchdogProcess
data=json.loads(sys.stdin.readline())
manager=WatchdogProcess(directory=data['directory'],program_sha256=data['sha'])
manager.start(data['envelope'])
print(json.dumps({'pid':manager.process.pid}))
"""
    payload={'directory':str(tmp_path),'sha':manager.expected,'envelope':envelope}
    launcher=subprocess.run([sys.executable,'-c',code],input=json.dumps(payload),text=True,
        capture_output=True,timeout=8,cwd=str(manager.program.parent),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    assert launcher.returncode==0
    result_path=tmp_path/(envelope['nonce']+'.watchdog-result.json')
    end=time.monotonic()+6
    while not result_path.exists() and time.monotonic()<end: time.sleep(0.05)
    assert json.loads(result_path.read_text())['suspended'] is True


def test_changed_watchdog_program_rejected_before_spawn(tmp_path):
    manager,envelope=watchdog_fixture(tmp_path)
    manager.expected='0'*64
    with pytest.raises(Blocked): manager.start(envelope)
    assert manager.process is None


def test_watchdog_path_injection_rejected_before_spawn(tmp_path):
    manager,envelope=watchdog_fixture(tmp_path)
    envelope['nonce']='../outside'
    with pytest.raises(Blocked): manager.start(envelope)
    assert manager.process is None


@pytest.mark.parametrize('invalid',[object(),'x'*(1024*1024)],ids=['nonserializable','oversized'])
def test_invalid_watchdog_payload_rejected_before_spawn(tmp_path,invalid):
    manager,envelope=watchdog_fixture(tmp_path)
    envelope['invalid']=invalid
    with pytest.raises(RuntimeError,match='^WATCHDOG_ENVELOPE_REJECTED$'):
        manager.start(envelope)
    assert manager.process is None


def test_unverified_cleanup_cannot_stop_child(tmp_path):
    manager,envelope=watchdog_fixture(tmp_path,delay=0.5)
    manager.start(envelope)
    try:
        with pytest.raises(Blocked): manager.stop_after_cleanup(services=services(True),
            database={'id':DATABASE,'status':'INACTIVE'},checked_at=manager.now().isoformat())
        assert manager.process.poll() is None
        manager.process.wait(timeout=6)
    finally:
        if manager.process.poll() is None: manager.process.terminate(); manager.process.wait(timeout=5)
