import copy
from datetime import datetime
from types import SimpleNamespace

import pytest
import requests
import shadow_operations as ops


@pytest.fixture
def job():
    return dict(session_date='2026-09-18',phase='PREMARKET',ruleset_version='v0.3',
        run_class='INFRASTRUCTURE_TEST',scheduled_at='2026-09-18T06:00:00-07:00',
        deadline='2026-09-18T06:01:00-07:00',movers_top=20,news_hours=18)


class Memory:
    def __init__(self):self.history=[];self.source=None
    def events(self,key):return copy.deepcopy(self.history)
    def append(self,key,kind,payload):
        event={'event_type':kind,'payload':copy.deepcopy(payload)}
        if not self.history or self.history[-1]!=event:self.history.append(event)
    def run(self,key):return self.source


class Remote:
    def __init__(self):self.calls=0;self.closed=False;self.failure=False;self.health=True
    def calendar(self,day):return [] if self.closed else [{'date':day,'open':'09:30','close':'16:00'}]
    def healthy(self):return self.health
    def dispatch(self,job):
        self.calls+=1
        if self.failure:raise requests.Timeout('secret exception must not enter history')
        return {'run_id':'local-test'}


def at(value):return lambda:datetime.fromisoformat(value)


def test_dispatch_intent_survives_timeout_and_never_reposts(job):
    store,remote=Memory(),Remote();remote.failure=True
    clock=at(job['scheduled_at'])
    assert ops.process(job,store,remote,clock)=='AMBIGUOUS'
    assert ops.process(job,store,remote,clock)=='AMBIGUOUS'
    assert remote.calls==1 and 'secret' not in str(store.history)
    assert [e['event_type'] for e in store.history]==['PLANNED','DISPATCHED','AMBIGUOUS','AMBIGUOUS']
    before=len(store.history)
    ops.process(job,store,remote,clock)
    assert len(store.history)==before


def test_crash_after_intent_requires_reconciliation_not_retry(job):
    store,remote=Memory(),Remote();key=ops.validate_job(job)
    store.append(key,'PLANNED',job);store.append(key,'DISPATCHED',{})
    assert ops.process(job,store,remote,at(job['scheduled_at']))=='AMBIGUOUS'
    assert remote.calls==0


@pytest.mark.parametrize('status', ['COMPLETE','PARTIAL','DATA_UNAVAILABLE','IN_PROGRESS'])
def test_recovers_source_by_stable_key_after_restart(job,status):
    store,remote=Memory(),Remote();key=ops.validate_job(job)
    store.append(key,'PLANNED',job);store.append(key,'DISPATCHED',{})
    store.source=dict(id='local',session_date=job['session_date'],phase=job['phase'],ruleset_version='v0.3',
                      experiment_class=job['run_class'],status=status,candidates_discovered=2,item_count=2)
    expected=status if status!='IN_PROGRESS' else 'AMBIGUOUS'
    assert ops.process(job,store,remote,at('2026-09-19T06:30:00-07:00'))==expected
    assert remote.calls==0
    assert ops.report([job],store)['opportunity_outcome']=='UNKNOWN'


def test_missing_funnel_rows_cannot_claim_complete(job):
    store,remote=Memory(),Remote()
    store.source=dict(id='local',session_date=job['session_date'],phase=job['phase'],ruleset_version='v0.3',
                      experiment_class=job['run_class'],status='COMPLETE',candidates_discovered=2,item_count=1)
    assert ops.process(job,store,remote,at(job['scheduled_at']))=='AMBIGUOUS'


def test_official_closed_session_does_not_scan_or_count_zero_opportunities(job):
    store,remote=Memory(),Remote();remote.closed=True
    assert ops.process(job,store,remote,at(job['scheduled_at']))=='CLOSED'
    assert remote.calls==0
    assert ops.report([job],store)['opportunity_outcome']=='UNKNOWN'


@pytest.mark.parametrize('when,expected', [('2026-09-18T05:59:59-07:00','PLANNED'),
    ('2026-09-18T06:01:00-07:00','MISSED'),('2026-09-19T06:00:00-07:00','MISSED')])
def test_no_early_or_late_scan(job,when,expected):
    store,remote=Memory(),Remote()
    assert ops.process(job,store,remote,at(when))==expected
    assert remote.calls==0


def test_cold_start_cannot_move_dispatch_past_deadline(job):
    store,remote=Memory(),Remote();times=iter([datetime.fromisoformat(job['scheduled_at']),datetime.fromisoformat(job['deadline'])])
    assert ops.process(job,store,remote,lambda:next(times))=='MISSED'
    assert remote.calls==0


def test_unavailable_calendar_recovers_without_duplicate_incidents(job):
    store,remote=Memory(),Remote();original=remote.calendar
    def fail(day):raise requests.ConnectionError('private connection')
    remote.calendar=fail
    for _ in range(3):assert ops.process(job,store,remote,at(job['scheduled_at']))=='CALENDAR_UNAVAILABLE'
    assert len(store.history)==2
    remote.calendar=original
    assert ops.process(job,store,remote,at(job['scheduled_at']))=='DISPATCHED'
    assert remote.calls==1


def test_postopen_early_close_respected(job):
    job.update(phase='POST_OPEN',scheduled_at='2026-09-18T13:00:00-04:00',deadline='2026-09-18T13:01:00-04:00')
    store,remote=Memory(),Remote()
    remote.calendar=lambda day:[{'date':day,'open':'09:30','close':'13:00'}]
    assert ops.process(job,store,remote,at(job['scheduled_at']))=='WINDOW_INVALID'
    assert remote.calls==0


def test_dst_uses_declared_offsets_and_eastern_calendar(job):
    job.update(session_date='2026-11-02',scheduled_at='2026-11-02T06:00:00-08:00',deadline='2026-11-02T06:01:00-08:00')
    assert ops.process(job,Memory(),Remote(),at('2026-11-02T14:00:00+00:00'))=='DISPATCHED'


def test_schedule_cannot_be_silently_changed(job):
    store,remote=Memory(),Remote();ops.process(job,store,remote,at('2026-09-18T05:00:00-07:00'))
    job['deadline']='2026-09-18T06:02:00-07:00'
    with pytest.raises(ValueError,match='Persisted job changed'):ops.process(job,store,remote,at(job['scheduled_at']))


def test_store_requires_durable_autocommit():
    with pytest.raises(ValueError):ops.Store(SimpleNamespace(autocommit=False))


@pytest.mark.parametrize('body,expected', [({'ok':True,'mode':'SHADOW','ruleset_version':'v0.3','broker_execution_enabled':False},True),
    ({'ok':True,'mode':'PAPER','ruleset_version':'v0.3','broker_execution_enabled':True},False), ({'ok':True},False)])
def test_health_checks_actual_service_contract(monkeypatch,body,expected):
    monkeypatch.setenv('DISCOVERY_URL','https://staging.invalid')
    monkeypatch.setattr(ops.requests,'get',lambda *a,**k:SimpleNamespace(raise_for_status=lambda:None,json=lambda:body))
    assert ops.Remote().healthy() is expected


def test_default_cli_is_offline_and_disabled(monkeypatch,job,capsys):
    import json
    monkeypatch.setattr(ops.Path,'read_text',lambda *a,**k:json.dumps([job]))
    monkeypatch.setattr('sys.argv',['shadow_operations','--plan','test-only-plan.json'])
    monkeypatch.setattr(ops.psycopg,'connect',lambda *a,**k:pytest.fail('Must not connect'))
    ops.main()
    assert 'DISABLED_PREVIEW' in capsys.readouterr().out
