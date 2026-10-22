"""Invented providers only; these tests never load credentials or use a network."""
import json
from datetime import timedelta

import pytest
from requests.exceptions import ConnectTimeout, ReadTimeout, ConnectionError
from fastapi.testclient import TestClient

from coordinator_acceptance_app import create_app
from coordinator_launch_guard import URL
from coordinator_service_adapters import safe_steps
from coordinator_runtime_preflight import BARS, QUOTES
from test_coordinator_preflight_binding import rehearsal, probes
from test_coordinator_adapters import Response
from test_coordinator_launch_guard import tmp_path

CANARY = "DO_NOT_EMIT_INVENTED_SECRET"


def runtime_calls(r, suffix):
    return [a for a,k in r.connections.runtime.http.session.calls if a[1].endswith(suffix)]


def assert_safe_failure(r, result):
    assert result['status'] != 'NO_SCAN_CHECKS_PASSED'
    assert result['authentication'] == 'NOT_VERIFIED'
    assert result['cleanup'] == 'VERIFIED'
    assert result['database_unchanged']
    assert not r.active[0] and r.status[0] == 'INACTIVE'
    assert result['acceptance_posts'] == 0 and not result['strategy_evidence_eligible']
    assert CANARY not in json.dumps(result)
    assert all(a[0] == 'GET' for a,k in r.connections.runtime.http.session.calls)
    for path in r.path.glob('*.json'):
        assert CANARY not in path.read_text()


def test_slow_start_then_one_authenticated_probe(rehearsal):
    r=rehearsal; session=r.connections.runtime.http.session; original=session.response
    remaining=[3]
    def response(method,url,**kw):
        if url.endswith('/health') and remaining[0]:
            remaining[0]-=1
            return Response(CANARY.encode(),503)
        return original(method,url,**kw)
    session.response=response
    result=r.run()
    assert result['status']=='NO_SCAN_CHECKS_PASSED'
    assert result['readiness']=={'status':'HTTP_READY_ONLY_NOT_AUTHENTICATED','attempts':4}
    assert len(runtime_calls(r,'/health'))==4 and len(runtime_calls(r,'/acceptance/preflight'))==1
    assert len(result['readiness_diagnostics'])==4
    assert r.p.suspend_at==r.p.not_before+timedelta(minutes=3)
    assert r.p.verify_by==r.p.not_before+timedelta(minutes=8)
    assert r.clock[0]==r.p.suspend_at
    assert result['watchdog_shutdown']=='VERIFIED'
    assert CANARY not in json.dumps(result)


@pytest.mark.parametrize('failure,code,status',[
    (ConnectTimeout(CANARY),'CONNECT_TIMEOUT',None),
    (ReadTimeout(CANARY),'READ_TIMEOUT',None),
    (TimeoutError(CANARY),'TIMEOUT',None),
    (ConnectionError(CANARY),'CONNECTION_FAILED',None),
    (401,'HTTP_STATUS',401),(403,'HTTP_STATUS',403),(503,'HTTP_STATUS',503),
    ('invalid_json','INVALID_JSON',200)])
def test_health_never_substitutes_for_authentication(rehearsal,failure,code,status):
    r=rehearsal; s=r.connections.runtime.http.session; original=s.response
    def response(method,url,**kw):
        if url.endswith('/health'): return original(method,url,**kw)
        if isinstance(failure,Exception): raise failure
        if failure=='invalid_json': return Response(CANARY.encode(),200)
        return Response({'detail':CANARY},failure)
    s.response=response
    result=r.run()
    assert_safe_failure(r,result)
    assert len(runtime_calls(r,'/acceptance/preflight'))==1
    row=next(x for x in result['diagnostics'] if x['phase']=='authentication')
    assert row['error']==code and row['http_status']==status
    assert result['failure_phase']=='authentication'
    assert result['readiness']['status']=='HTTP_READY_ONLY_NOT_AUTHENTICATED'


@pytest.mark.parametrize('failure',[502,503,504,ConnectTimeout(CANARY),ReadTimeout(CANARY)])
def test_readiness_exhaustion_never_calls_authentication(rehearsal,failure):
    r=rehearsal; s=r.connections.runtime.http.session
    def response(*a,**kw):
        if isinstance(failure,Exception): raise failure
        return Response(CANARY.encode(),failure)
    s.response=response
    result=r.run()
    assert_safe_failure(r,result)
    assert 1<len(runtime_calls(r,'/health'))<=15
    assert not runtime_calls(r,'/acceptance/preflight')
    assert r.mono[0]<=30 and result['failure_phase']=='readiness'


@pytest.mark.parametrize('failure',[401,403,301,500,'invalid','unsafe'])
def test_non_transient_health_failure_is_not_retried(rehearsal,failure):
    r=rehearsal
    if failure=='invalid': response=Response(CANARY.encode(),200)
    elif failure=='unsafe': response=Response({'mode':'LIVE','secret':CANARY},200)
    else: response=Response(CANARY.encode(),failure)
    r.connections.runtime.http.session.response=response
    result=r.run()
    assert_safe_failure(r,result)
    assert len(runtime_calls(r,'/health'))==1 and not runtime_calls(r,'/acceptance/preflight')


@pytest.mark.parametrize('where',['observe','watchdog'])
def test_budget_exhausted_before_resume(rehearsal,where):
    r=rehearsal
    obj=r.connections if where=='observe' else r.connections.watchdog
    name='observe' if where=='observe' else 'receipt'
    original=getattr(obj,name)
    def delayed(*a,**kw):
        value=original(*a,**kw)
        r.clock[0]+=timedelta(seconds=80); r.mono[0]+=80
        return value
    setattr(obj,name,delayed)
    result=r.run()
    assert_safe_failure(r,result)
    assert not any(url.endswith('/resume') for method,url in r.calls)
    assert not r.connections.runtime.http.session.calls
    if where=='observe': assert ('STOP_CHILD','LOCAL') not in r.calls


def test_ambiguous_resume_is_not_replayed(rehearsal):
    r=rehearsal; s=r.connections.render.http.session; original=s.response
    def response(method,url,**kw):
        value=original(method,url,**kw)
        if url.endswith('/resume'): raise ReadTimeout(CANARY)
        return value
    s.response=response
    result=r.run()
    assert_safe_failure(r,result)
    assert result['failure_phase']=='resume'
    assert len([x for x in r.calls if x[1].endswith('/resume')])==1
    assert not r.connections.runtime.http.session.calls


def test_attempt_guard_survives_failure(rehearsal):
    r=rehearsal; r.connections.runtime.http.session.response=Response({},401)
    first=r.run(); assert_safe_failure(r,first)
    count=len(r.calls); runtime_count=len(r.connections.runtime.http.session.calls)
    r.clock[0]=r.p.not_before
    second=r.run()
    assert second['status']=='ATTEMPT_ALREADY_CONSUMED'
    assert len(r.calls)==count and len(r.connections.runtime.http.session.calls)==runtime_count
    assert len(list(r.path.glob('*.attempt.json')))==1


def test_provider_progress_is_safe_and_survives_app_boundary(probes):
    c,*_=probes; original=c.session.response
    def response(method,url,**kw):
        if url==BARS: return Response({'private':CANARY},403)
        return original(method,url,**kw)
    c.session.response=response
    response=TestClient(create_app(preflight_service=c)).get(
        '/acceptance/preflight',headers={'Authorization':'Bearer OFFLINE_TOKEN'})
    assert response.status_code==503
    rows=response.json()['detail']['diagnostics']
    assert [(x['phase'],x['error']) for x in rows]==[
        ('guard','OK'),('paper_calendar','OK'),('sip','OK'),('historical_sip','HTTP_STATUS')]
    assert rows[-1]['http_status']==403 and CANARY not in response.text
    assert len(c.session.calls)==3


def test_malformed_provider_evidence_is_not_authenticated(probes):
    c,rows,*_=probes; rows[QUOTES]={'quotes':{'SPY':{'t':CANARY}}}
    response=TestClient(create_app(preflight_service=c)).get(
        '/acceptance/preflight',headers={'Authorization':'Bearer OFFLINE_TOKEN'})
    assert response.status_code==503
    last=response.json()['detail']['diagnostics'][-1]
    assert last['phase']=='sip' and last['error']!='OK'
    assert CANARY not in response.text


def test_provider_diagnostics_are_rebuilt_not_trusted(rehearsal):
    r=rehearsal; s=r.connections.runtime.http.session; original=s.response
    hostile=[{'phase':'sip','error':'HTTP_STATUS','http_status':403,'elapsed_seconds':1,
              'secret':CANARY},{'phase':CANARY,'error':CANARY},
             {'phase':'guard','error':CANARY,'http_status':CANARY,'elapsed_seconds':float('nan')}]
    def response(method,url,**kw):
        if url.endswith('/health'): return original(method,url,**kw)
        return Response({'detail':{'diagnostics':hostile,'body':CANARY}},503)
    s.response=response
    result=r.run()
    assert_safe_failure(r,result)
    assert result['provider_diagnostics']==safe_steps(hostile)
    assert result['provider_diagnostics'][1]=={
        'phase':'guard','error':'UNAVAILABLE','http_status':None,'elapsed_seconds':None}


def test_wall_clock_jump_fails_closed_during_readiness(rehearsal):
    r=rehearsal
    def response(*a,**kw):
        r.clock[0]+=timedelta(seconds=10)
        return Response({},503)
    r.connections.runtime.http.session.response=response
    result=r.run()
    assert_safe_failure(r,result)
    assert not runtime_calls(r,'/acceptance/preflight')
    assert len(runtime_calls(r,'/health'))==1
