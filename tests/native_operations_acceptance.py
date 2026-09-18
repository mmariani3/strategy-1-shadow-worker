"""Loopback-only PostgreSQL acceptance. No external HTTP, Sheets or production writes."""
import argparse
from datetime import datetime
import json
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import requests
from shadow_operations import Store,process,validate_job,report
from journal_writer import writer_lock,JournalConflict


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--connection-file',required=True)
    config=json.loads(Path(p.parse_args().connection_file).read_text())
    assert config['host']=='127.0.0.1'
    def blocked(*a,**k):raise AssertionError('External HTTP is forbidden')
    requests.sessions.Session.request=blocked
    database='operations_acceptance_'+uuid4().hex
    with psycopg.connect(**config,autocommit=True) as admin:
        admin.execute(sql.SQL('create database {}').format(sql.Identifier(database)))
    config['dbname']=database
    root=Path(__file__).resolve().parents[1]
    with psycopg.connect(**config,autocommit=True) as admin:
        admin.execute('create table strategy_discovery_runs(id uuid,run_key text unique,session_date date,phase text,'
                      'ruleset_version text,experiment_class text,status text,candidates_discovered integer);'
                      'create table strategy_discovery_items(id uuid,run_id uuid);')
        admin.execute((root/'supabase/migrations/20260918173946_shadow_operation_events.sql').read_text())
        admin.execute('grant usage on schema public to service_role; grant select on strategy_discovery_runs,strategy_discovery_items to service_role')
    job=dict(session_date='2026-09-18',phase='PREMARKET',ruleset_version='v0.3',run_class='INFRASTRUCTURE_TEST',
             scheduled_at='2026-09-18T06:00:00-07:00',deadline='2026-09-18T06:01:00-07:00',movers_top=20,news_hours=18)
    key=validate_job(job);calls=[];contended=[]
    class FakeRemote:
        def calendar(self,day):return [{'date':day,'open':'09:30','close':'16:00'}]
        def healthy(self):return True
        def dispatch(self,job):
            calls.append(job)
            with psycopg.connect(**config,autocommit=True,row_factory=dict_row) as competitor:
                competitor.execute('set role service_role')
                # A distinct connection can see the already committed intent while the first lock is held.
                assert 'DISPATCHED' in [e['event_type'] for e in Store(competitor).events(key)]
                try:
                    with writer_lock(competitor,'discovery-operation:'+key):raise AssertionError('Lock admitted competitor')
                except JournalConflict:contended.append(True)
            with psycopg.connect(**config,autocommit=True) as simulated_coordinator:
                simulated_coordinator.execute('insert into strategy_discovery_runs values(%s,%s,%s,%s,%s,%s,%s,0)',
                    (uuid4(),key,job['session_date'],job['phase'],'v0.3','INFRASTRUCTURE_TEST','PARTIAL'))
            raise requests.Timeout('injected lost acknowledgement')
    clock=lambda:datetime.fromisoformat(job['scheduled_at'])
    with psycopg.connect(**config,autocommit=True,row_factory=dict_row) as first:
        first.execute('set role service_role')
        with writer_lock(first,'discovery-operation:'+key):
            assert process(job,Store(first),FakeRemote(),clock)=='AMBIGUOUS'
    # Simulate a process restart: new database session, no in-memory history.
    with psycopg.connect(**config,autocommit=True,row_factory=dict_row) as restarted:
        restarted.execute('set role service_role');store=Store(restarted)
        with writer_lock(restarted,'discovery-operation:'+key):
            assert process(job,store,FakeRemote(),clock)=='PARTIAL'
            size=len(store.events(key))
            assert process(job,store,FakeRemote(),clock)=='PARTIAL'
            assert len(store.events(key))==size
        assert report([job],store)['opportunity_outcome']=='UNKNOWN'
    assert len(calls)==1 and contended==[True]
    print(json.dumps({'status':'PASSED','database':database,'dispatch_count':1,'competing_session':'BLOCKED',
        'intent_durable_before_request':True,'restart':'source reconciled without replay','external_http':False}))


if __name__=='__main__':main()
