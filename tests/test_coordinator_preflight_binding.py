"""Invented offline provider responses; no credential stores or hosted calls."""
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
import hashlib
import json
import os

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from coordinator_acceptance_app import create_app, app
from coordinator_runtime_preflight import (ReadOnlyProbes, ProbePermit, Credentials, source_hash,
    CALENDAR, QUOTES, BARS, DB_READ, DB_URL, START_COMMAND, from_deployed_environment)
from coordinator_rehearsal_binding import (RehearsalPermit, ReadOnlyRuntimeClient, RehearsalConnections, rehearse)
from coordinator_launch_guard import REQUIRED_FILES, MASTERS, SERVICE, DATABASE, URL, WORKSPACE, Blocked
from coordinator_service_adapters import RenderAdapter, DatabaseCollector, REPO, RENDER, AdapterError
from test_coordinator_adapters import Session, Response, Connection
from test_coordinator_launch_guard import tmp_path, services
from test_coordinator_acceptance import NOW


@pytest.fixture
def probes(tmp_path):
    for name in REQUIRED_FILES: (tmp_path/name).write_text('OFFLINE_SOURCE_'+name)
    instant=NOW.replace(minute=0,second=0)
    p=ProbePermit(instant.date(),'a'*40,source_hash(tmp_path),instant-timedelta(minutes=1),instant+timedelta(minutes=9))
    responses={
        CALENDAR:[{'date':'2026-10-12','open':'09:30','close':'16:00'},
                  {'date':'2026-10-13','open':'09:30','close':'16:00'}],
        QUOTES:{'quotes':{'SPY':{'t':'2026-10-13T12:59:59Z','bp':1,'ap':2}}},
        BARS:{'bars':{'SPY':[{'t':'2026-10-12T04:00:00Z','c':1}]},'next_page_token':None},
        DB_READ:[{'id':'OFFLINE'}]}
    s=Session(lambda method,url,**kw:Response(responses[url]))
    identity={'service':SERVICE,'database_url':DB_URL,'ruleset':'v0.3','commit':p.commit}
    clock=[instant]
    c=ReadOnlyProbes(permit=p,credentials=Credentials('OFFLINE_TOKEN','OFFLINE_KEY','OFFLINE_SECRET','OFFLINE_DB'),
        session=s,directory=tmp_path,identity=lambda:identity,now=lambda:clock[0])
    return c,responses,identity,clock,tmp_path


def test_read_only_preflight_authentication_and_fixed_credential_routing(probes):
    c,_,_,_,_=probes
    data=c.check('Bearer OFFLINE_TOKEN')
    assert data['scope']=='NORMAL_COORDINATOR_NO_SCAN' and data['scan_enabled'] is False
    assert data['reference_price_approved'] is False and data['historical_prior_session']=='2026-10-12'
    assert len(data['authenticated_probes'])==4
    assert [args for args,kw in c.session.calls]==[('GET',url) for url in (CALENDAR,QUOTES,BARS,DB_READ)]
    for args,kw in c.session.calls:
        assert kw['allow_redirects'] is False and kw['stream'] is True
        if args[1]==DB_READ: assert kw['headers']=={'Accept':'application/json','apikey':'OFFLINE_DB'}
        else: assert 'apikey' not in kw['headers'] and kw['headers']['APCA-API-SECRET-KEY']=='OFFLINE_SECRET'
    assert c.session.calls[2][1]['params']['start']=='2026-10-12T00:00:00-04:00'
    assert 'OFFLINE_SECRET' not in json.dumps(data) and 'OFFLINE_DB' not in repr(c.credentials)


@pytest.mark.parametrize('token',[None,'','Bearer wrong','Bearer ü'])
def test_unauthorized_preflight_never_calls_provider(probes,token):
    c,*_=probes
    with pytest.raises(HTTPException) as exc: c.check(token)
    assert exc.value.status_code==401 and not c.session.calls


@pytest.mark.parametrize('case',['expired','early','wrong_service','production_db','ruleset','commit','source_changed',
    'calendar_missing_today','calendar_duplicate','early_close','quotes_empty','historical_wrong_date','pagination',
    'bad_price','database_bad_shape','redirect','credential_missing','timeout','oversized'])
def test_preflight_failure_is_safe_and_never_retries(probes,case):
    c,r,identity,clock,path=probes
    if case=='expired': clock[0]=c.permit.expires_at
    if case=='early': clock[0]=c.permit.not_before-timedelta(seconds=1)
    if case=='wrong_service': identity['service']='production'
    if case=='production_db': identity['database_url']='https://production.invalid'
    if case=='ruleset': identity['ruleset']='v0.4'
    if case=='commit': identity['commit']='f'*40
    if case=='source_changed': (path/'build_info.py').write_text('CHANGED')
    if case=='calendar_missing_today': r[CALENDAR]=r[CALENDAR][:1]
    if case=='calendar_duplicate': r[CALENDAR].append(r[CALENDAR][0])
    if case=='early_close': r[CALENDAR][1]['close']='13:00'
    if case=='quotes_empty': r[QUOTES]={'quotes':{}}
    if case=='historical_wrong_date': r[BARS]['bars']['SPY'][0]['t']='2026-10-09T04:00:00Z'
    if case=='pagination': r[BARS]['next_page_token']='unread'
    if case=='bad_price': r[BARS]['bars']['SPY'][0]['c']=float('nan')
    if case=='database_bad_shape': r[DB_READ]={'private':'OFFLINE_SECRET'}
    if case=='redirect': c.session.response=Response(b'OFFLINE_SECRET',302)
    if case=='credential_missing': c.credentials=replace(c.credentials,alpaca_secret='')
    if case=='timeout': c.session.response=TimeoutError('OFFLINE_SECRET')
    if case=='oversized': c.session.response=Response(b'x'*(256*1024+1))
    with pytest.raises(HTTPException) as exc: c.check('Bearer OFFLINE_TOKEN')
    assert exc.value.status_code==503 and exc.value.detail=='AUTHENTICATED_PREFLIGHT_UNVERIFIED'
    assert len(c.session.calls)<=4 and len({a[1] for a,k in c.session.calls})==len(c.session.calls)


def test_preflight_excludes_concurrent_probes(probes):
    c,*_=probes
    c.lock.acquire()
    try:
        with pytest.raises(HTTPException) as exc: c.check('Bearer OFFLINE_TOKEN')
        assert exc.value.status_code==409 and not c.session.calls
    finally: c.lock.release()


def test_preflight_time_budget_rejects_slow_response(probes):
    c,*_=probes
    ticks=iter([0,0,21])
    c.clock=lambda:next(ticks)
    with pytest.raises(HTTPException): c.check('Bearer OFFLINE_TOKEN')
    assert len(c.session.calls)==1


def test_rehearsal_app_never_unlocks_scan(probes,monkeypatch):
    import discovery_coordinator as d
    c,*_=probes
    monkeypatch.setattr(d,'DISCOVERY_SERVICE_TOKEN','OFFLINE_TOKEN')
    client=TestClient(create_app(preflight_service=c))
    assert client.get('/acceptance/preflight').status_code==401
    assert client.get('/acceptance/preflight',headers={'Authorization':'Bearer OFFLINE_TOKEN'}).status_code==200
    result=client.post('/scan/run-once',headers={'Authorization':'Bearer OFFLINE_TOKEN'},json={
        'session_date':'2026-10-13','phase':'PREMARKET','run_class':'INFRASTRUCTURE_TEST','include_dated_prior_evidence':True})
    assert result.status_code==503 and result.json()['detail']=='HOSTED_ADMISSION_NOT_IMPLEMENTED'
    assert len(c.session.calls)==4
    assert client.post('/acceptance/preflight').status_code==403
    with pytest.raises(ValueError): create_app(lambda:None,preflight_service=c)
    assert TestClient(app).get('/acceptance/preflight').status_code==503


def test_explicit_environment_factory_does_not_contact_provider(probes):
    c,_,identity,_,path=probes
    manifest=path/'rehearsal.json'
    manifest.write_text(json.dumps({'scope':'NORMAL_COORDINATOR_NO_SCAN','session_date':c.permit.day.isoformat(),
        'commit':c.permit.commit,'source_hash':c.permit.source_hash,'not_before':c.permit.not_before.isoformat(),
        'expires_at':c.permit.expires_at.isoformat()}))
    env={'COORDINATOR_REHEARSAL_MANIFEST':str(manifest), 'DISCOVERY_SERVICE_TOKEN':'OFFLINE_TOKEN',
         'ALPACA_API_KEY':'OFFLINE_KEY','ALPACA_API_SECRET':'OFFLINE_SECRET','SUPABASE_SECRET_KEY':'OFFLINE_DB',
         'RENDER_SERVICE_ID':SERVICE,'SUPABASE_URL':DB_URL,'RULESET_VERSION':'v0.3','RENDER_GIT_COMMIT':c.permit.commit}
    built=from_deployed_environment(env,directory=path,session=c.session)
    assert not c.session.calls and built.identity()==identity
    manifest.write_text('{}')
    with pytest.raises(RuntimeError,match='^REHEARSAL_CONFIGURATION_UNAVAILABLE$'):
        from_deployed_environment(env,directory=path,session=c.session)


def test_read_only_runtime_client_has_no_post_method():
    session=Session(Response({}))
    runtime=ReadOnlyRuntimeClient(session=session,token='OFFLINE',expires_at=NOW+timedelta(minutes=10),now=lambda:NOW)
    assert not hasattr(runtime,'post')
    with pytest.raises(AdapterError): runtime.http.call('POST',URL+'/scan/run-once')
    assert not session.calls


@pytest.fixture
def rehearsal(probes,tmp_path):
    probe,_,_,clock,path=probes
    p=RehearsalPermit(day=probe.permit.day,commit=probe.permit.commit,source_hash=probe.permit.source_hash,
        deployment='dep-offline',files=tuple((n,hashlib.sha256((path/n).read_bytes()).hexdigest()) for n in sorted(REQUIRED_FILES)),
        masters=tuple((n,'OFFLINE_REV') for n in sorted(MASTERS)),schema_hash='d'*64,
        not_before=clock[0],authorized_until=clock[0]+timedelta(minutes=10),authorization_id='OFFLINE_NOT_AUTHORIZATION')
    dbconn=Connection(); db=DatabaseCollector(connect=lambda:dbconn,project_id=DATABASE,now=lambda:clock[0])
    p=replace(p,schema_hash=db.collect()['schema_sha256'])
    active=[False]; status=['ACTIVE_HEALTHY']; calls=[]; mono=[0]; child={}; failures=set()
    def request(method,url,**kw):
        calls.append((method,url))
        if (method,url) in failures: raise TimeoutError('OFFLINE_PRIVATE')
        if child and clock[0]>=p.suspend_at and 'watchdog' not in failures: active[0]=False
        if url==RENDER+'/services': return Response([{'service':r} for r in services(active[0])])
        if url.endswith('/deploys'): return Response([{'deploy':{'id':p.deployment,'commit':{'id':p.commit},'status':'live'}}])
        if url.endswith('/resume'): active[0]=True; return Response(b'',202)
        if url.endswith('/suspend'): active[0]=False; return Response(b'',202)
        target=next(r for r in services(active[0]) if r['id']==SERVICE)
        target.update(repo=REPO,serviceDetails={'url':URL,'envSpecificDetails':{'startCommand':START_COMMAND}})
        return Response(target)
    render=RenderAdapter(session=Session(request),token='OFFLINE_RENDER',expires_at=p.authorized_until,
                         now=lambda:clock[0],rehearsal_only=True)
    runtime=ReadOnlyRuntimeClient(session=Session(lambda *a,**kw:Response(probe.check('Bearer OFFLINE_TOKEN'))),
        token='OFFLINE_TOKEN',expires_at=p.authorized_until,now=lambda:clock[0])
    class Watchdog:
        def start(self,envelope): child.update(envelope)
        def receipt(self):
            return {'pid':os.getpid()+100,'mode':child['mode'],'nonce':child['nonce'],
                'policy_hash':p.fingerprint,'service':SERVICE,'suspend_at':p.suspend_at.isoformat(),
                'verify_by':p.verify_by.isoformat()}
        def result(self):
            if 'child_proof' in failures: raise FileNotFoundError()
            return {**self.receipt(),'suspended':True,'checked_at':clock[0].isoformat()}
        def stop_after_cleanup(self,**kw):
            calls.append(('STOP_CHILD','LOCAL'))
            return {'nonce':child['nonce'],'process_exited':True}
    def pause(project):
        assert project==DATABASE and not active[0]
        calls.append(('PAUSE_DB',project))
        if 'pause' in failures: raise TimeoutError('OFFLINE_PRIVATE')
        status[0]='INACTIVE'
    connections=RehearsalConnections(permit=p,render=render,runtime=runtime,database=db,directory=path,
        project_status=lambda:{'id':DATABASE,'status':status[0],'checked_at':clock[0].isoformat()},pause_project=pause,
        masters=lambda:{'revisions':dict(p.masters),'checked_at':clock[0].isoformat()},
        callers=lambda:{'active_schedules':[],'conflicting_process_ids':[],'checked_at':clock[0].isoformat()},
        watchdog_process=Watchdog(),render_key='OFFLINE_RENDER',now=lambda:clock[0])
    def sleep(seconds): clock[0]+=timedelta(seconds=seconds); mono[0]+=seconds
    def run(): return rehearse(p,connections=connections,evidence_directory=tmp_path,now=lambda:clock[0],
                              monotonic=lambda:mono[0],sleep=sleep)
    return SimpleNamespace(p=p,connections=connections,run=run,clock=clock,mono=mono,failures=failures,
                           calls=calls,active=active,status=status,db=dbconn,path=tmp_path)


def test_full_no_scan_rehearsal_binding_offline(rehearsal):
    r=rehearsal; result=r.run()
    assert result['status']=='NO_SCAN_CHECKS_PASSED' and result['authentication']=='PASS'
    assert result['database_unchanged'] and result['cleanup']=='VERIFIED' and result['cleanup_by_deadline']
    assert result['watchdog_shutdown']=='VERIFIED' and result['acceptance_posts']==0 and result['armed'] is False
    assert not r.active[0] and r.status[0]=='INACTIVE'
    assert not any('/scan' in url for method,url in r.calls)
    assert len(list(r.path.glob('*.baseline.json')))==1 and len(list(r.path.glob('*.readback.json')))==1
    r.clock[0]=r.p.not_before
    before=len(r.calls)
    assert r.run()['status']=='ATTEMPT_ALREADY_CONSUMED' and len(r.calls)==before


@pytest.mark.parametrize('failure',['probe','watchdog','child_proof','pause','database_changed','resume_timeout'])
def test_rehearsal_failures_do_not_allow_scan_or_false_pass(rehearsal,failure):
    r=rehearsal
    if failure=='probe': r.connections.runtime.http.session.response=TimeoutError('OFFLINE_PRIVATE')
    elif failure=='database_changed':
        original=r.connections.probe
        def probe():
            data=original(); r.db.rows['strategy_discovery_runs'][0]['notes']='CHANGED'; return data
        r.connections.probe=probe
    elif failure=='resume_timeout': r.failures.add(('POST',RENDER+'/services/'+SERVICE+'/resume'))
    else: r.failures.add(failure)
    result=r.run()
    assert result['status']!='NO_SCAN_CHECKS_PASSED' and result['acceptance_posts']==0
    assert 'OFFLINE_PRIVATE' not in json.dumps(result)
    if failure=='pause':
        assert result['cleanup']=='NOT_VERIFIED' and ('STOP_CHILD','LOCAL') not in r.calls
    else: assert result['cleanup']=='VERIFIED'


@pytest.mark.parametrize('change',['late_start','wrong_date','source','schema','masters','callers'])
def test_rehearsal_missing_prerequisite_never_resumes(rehearsal,change):
    r=rehearsal
    if change=='late_start': r.clock[0]+=timedelta(seconds=30)
    if change=='wrong_date': r.clock[0]+=timedelta(days=1)
    if change=='source': (r.connections.directory/'build_info.py').write_text('CHANGED')
    if change=='schema': r.db.catalog['indexes'].append({'name':'CHANGED'})
    if change=='masters': r.connections.masters=lambda:{'revisions':{},'checked_at':r.clock[0].isoformat()}
    if change=='callers': r.connections.callers=lambda:{'active_schedules':['ON'],'conflicting_process_ids':[],
                                                       'checked_at':r.clock[0].isoformat()}
    result=r.run()
    assert result['status']!='NO_SCAN_CHECKS_PASSED'
    assert not any(url.endswith('/resume') for method,url in r.calls)


def test_rehearsal_permit_serialization_preserves_binding(rehearsal):
    p=rehearsal.p
    assert RehearsalPermit.parse(json.loads(json.dumps(p.as_dict())))==p
    bad=replace(p,source_hash='f'*64)
    with pytest.raises(Blocked): bad.validate(p.not_before)


def test_connections_cannot_substitute_another_permit(rehearsal):
    r=rehearsal
    r.connections.permit=replace(r.p,deployment='dep-another')
    assert r.run()['status']=='REHEARSAL_FAILED_OR_AMBIGUOUS' and r.calls==[]


def test_no_scan_binding_rejects_scan_capable_runtime(rehearsal):
    from coordinator_service_adapters import RuntimeAdapter
    r=rehearsal
    runtime=RuntimeAdapter(session=Session(),token='OFFLINE',expires_at=r.p.authorized_until,now=lambda:r.clock[0])
    with pytest.raises(Blocked,match='NO_SCAN_BINDING'):
        RehearsalConnections(permit=r.p,render=r.connections.render,runtime=runtime,database=None,
            directory=r.path,project_status=None,pause_project=None,masters=None,callers=None,
            watchdog_process=None,render_key='OFFLINE',now=lambda:r.clock[0])


@pytest.mark.parametrize('case',['expired','bad_policy_hash','changed_files'])
def test_render_rehearsal_child_fails_before_http(rehearsal,monkeypatch,case):
    import coordinator_watchdog_process as module
    from datetime import datetime
    r=rehearsal
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None): return r.p.authorized_until if case=='expired' else r.p.not_before
    monkeypatch.setattr(module,'datetime',Clock)
    path=Path(module.__file__)
    envelope={'service':SERVICE,'nonce':'a'*32,'policy_hash':r.p.fingerprint,
        'program_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'directory':str(r.path),
        'mode':'render_rehearsal','policy':r.p.as_dict(),'render_key':'OFFLINE'}
    # Fixture file hashes deliberately differ from actual package, so the third
    # case stops at source verification before constructing an HTTP client.
    if case=='bad_policy_hash': envelope['policy_hash']='f'*64
    expected={'expired':'REHEARSAL_WINDOW','bad_policy_hash':'WATCHDOG_POLICY_BINDING',
              'changed_files':'WATCHDOG_PACKAGE_CHANGED'}[case]
    with pytest.raises(ValueError,match=expected): module.child(envelope)
    assert not list(r.path.glob('*.watchdog-ready.json'))
