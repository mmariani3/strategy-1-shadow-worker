"""Disabled-by-default discovery dispatcher and durable process report. No trade decisions."""
import argparse
from datetime import date, datetime, time, timezone
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
import requests

from journal_writer import writer_lock

VERSION = '1.0.0-shadow-operations'
EASTERN = ZoneInfo('America/New_York')
FINAL = {'COMPLETE', 'PARTIAL', 'DATA_UNAVAILABLE'}


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('An explicit timezone is required.')
    return parsed


def validate_job(job):
    fields = {'session_date','phase','ruleset_version','run_class','scheduled_at','deadline','movers_top','news_hours'}
    if set(job) != fields or job['ruleset_version'] != 'v0.3':
        raise ValueError('Unexpected job contract or ruleset.')
    if job['phase'] not in ('PREMARKET','POST_OPEN') or job['run_class'] not in ('STRATEGY_1','INFRASTRUCTURE_TEST'):
        raise ValueError('Explicit phase and experiment classification required.')
    day = date.fromisoformat(job['session_date'])
    start, end = timestamp(job['scheduled_at']), timestamp(job['deadline'])
    if not start < end or any(t.astimezone(EASTERN).date() != day for t in (start,end)):
        raise ValueError('Job window must lie within its declared Eastern session date.')
    if any(type(job[k]) is not int or job[k] <= 0 for k in ('movers_top','news_hours')):
        raise ValueError('Positive integer discovery collection parameters required.')
    return '|'.join(('STRATEGY_1',job['session_date'],job['phase'],job['ruleset_version'],job['run_class']))


def session_bounds(day, calendar):
    if not isinstance(calendar, list):
        raise ValueError('Invalid calendar response.')
    if not calendar:
        return None
    if len(calendar) != 1 or calendar[0].get('date') != day:
        raise ValueError('Calendar must identify exactly the requested session.')
    row = calendar[0]
    opened, closed = [datetime.combine(date.fromisoformat(day), time.fromisoformat(row[k]), EASTERN)
                      for k in ('open','close')]
    if not opened < closed:
        raise ValueError('Invalid calendar hours.')
    return opened, closed


class Store:
    """Connection must be session-capable and autocommit; never wrap dispatch in a transaction."""
    def __init__(self, conn):
        if not conn.autocommit:
            raise ValueError('Dispatch intent must be independently durable.')
        self.conn = conn

    def events(self, key):
        return self.conn.execute('select event_type,payload from public.shadow_operation_events where job_key=%s order by id', (key,)).fetchall()

    def append(self, key, kind, payload):
        previous = self.events(key)
        if previous and previous[-1]['event_type'] == kind and previous[-1]['payload'] == payload:
            return  # Repeated unchanged incidents do not flood the audit/report.
        self.conn.execute('insert into public.shadow_operation_events(job_key,event_type,implementation_version,payload) '
                          'values(%s,%s,%s,%s)',
                          (key,kind,VERSION,Jsonb(payload)))

    def run(self, key):
        return self.conn.execute('select r.id,r.run_key,r.session_date,r.phase,r.ruleset_version,r.experiment_class,r.status,r.candidates_discovered, '
                                 '(select count(*) from public.strategy_discovery_items i where i.run_id=r.id) as item_count '
                                 'from public.strategy_discovery_runs r where r.run_key=%s', (key,)).fetchone()


class Remote:
    def __init__(self):
        self.discovery = os.environ['DISCOVERY_URL'].rstrip('/')
        url = urlsplit(self.discovery)
        if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.path:
            raise ValueError('Explicit HTTPS discovery origin required.')

    def calendar(self, day):
        # Fixed paper host, read-only calendar. No order, position or account mutation routes.
        response = requests.get('https://paper-api.alpaca.markets/v2/calendar', params={'start':day,'end':day},
            headers={'APCA-API-KEY-ID':os.environ['ALPACA_API_KEY'],
                     'APCA-API-SECRET-KEY':os.environ['ALPACA_API_SECRET']}, timeout=(5,30))
        response.raise_for_status()
        return response.json()

    def healthy(self):
        response = requests.get(self.discovery + '/health', timeout=(5,45))
        response.raise_for_status()
        body = response.json()
        return (body.get('ruleset_version') == 'v0.3' and body.get('ok') is True
                and body.get('mode') == 'SHADOW' and body.get('broker_execution_enabled') is False)

    def dispatch(self, job):
        response = requests.post(self.discovery + '/scan/run-once',
            headers={'Authorization':'Bearer ' + os.environ['DISCOVERY_SCHEDULER_TOKEN']},
            json={k:job[k] for k in ('session_date','phase','run_class','movers_top','news_hours')}, timeout=(5,240))
        response.raise_for_status()
        return response.json()


def process(job, store, remote, clock=lambda: datetime.now(timezone.utc)):
    key = validate_job(job)
    prior = {e['event_type']: e['payload'] for e in store.events(key)}
    if 'PLANNED' in prior and prior['PLANNED'] != job:
        raise ValueError('Persisted job changed; do not silently revise its observation window.')
    if 'PLANNED' not in prior:
        store.append(key, 'PLANNED', job)
    # Reconcile existing authoritative evidence before considering another request.
    run = store.run(key)
    if run:
        identity = (str(run['session_date']),run['phase'],run['ruleset_version'],run['experiment_class'])
        if identity != (job['session_date'],job['phase'],job['ruleset_version'],job['run_class']):
            raise ValueError('Run identity conflicts with declared job.')
        state = run['status'] if run['status'] in FINAL and run['candidates_discovered'] == run['item_count'] else 'AMBIGUOUS'
        store.append(key, state, {'run_id':str(run['id']), 'run_status':run['status']})
        return state
    if any(k in prior for k in FINAL):
        store.append(key, 'AMBIGUOUS', {'reason':'Previously reconciled source run is missing.'})
        return 'AMBIGUOUS'
    if 'DISPATCHED' in prior:
        store.append(key, 'AMBIGUOUS', {'reason':'Dispatch outcome unresolved; request will not be replayed.'})
        return 'AMBIGUOUS'
    if 'MISSED' in prior or 'CLOSED' in prior:
        return 'MISSED' if 'MISSED' in prior else 'CLOSED'
    now = clock()
    if now < timestamp(job['scheduled_at']):
        return 'PLANNED'
    try:
        bounds = session_bounds(job['session_date'], remote.calendar(job['session_date']))
    except (requests.RequestException, ValueError, KeyError, TypeError):
        store.append(key, 'CALENDAR_UNAVAILABLE', {'reason':'Session calendar unavailable or invalid.'})
        return 'CALENDAR_UNAVAILABLE'
    if bounds is None:
        store.append(key, 'CLOSED', {'reason':'Official calendar returned no session.'})
        return 'CLOSED'
    opened, closed = bounds
    start, end = timestamp(job['scheduled_at']),timestamp(job['deadline'])
    if ((job['phase']=='PREMARKET' and end > opened) or
            (job['phase']=='POST_OPEN' and not opened <= start < end <= closed)):
        store.append(key, 'WINDOW_INVALID', {'reason':'Configured window conflicts with session hours.'})
        return 'WINDOW_INVALID'
    if now >= end:
        store.append(key, 'MISSED', {'reason':'Declared dispatch window elapsed; no catch-up request.'})
        return 'MISSED'
    try:
        if not remote.healthy():
            raise ValueError('Unready discovery service.')
    except (requests.RequestException, ValueError, KeyError, TypeError):
        store.append(key, 'DEPENDENCY_UNAVAILABLE', {'reason':'Discovery health not verified.'})
        return 'DEPENDENCY_UNAVAILABLE'
    # Health checks can cross the deadline. Recheck the actual clock, never backdate.
    if clock() >= end:
        store.append(key, 'MISSED', {'reason':'Readiness completed after the declared window.'})
        return 'MISSED'
    store.append(key, 'DISPATCHED', {'requested_at':clock().isoformat()})
    try:
        response = remote.dispatch(job)
        if not response.get('run_id'):
            raise ValueError('Missing run identity.')
    except (requests.RequestException, ValueError, KeyError, TypeError):
        store.append(key, 'AMBIGUOUS', {'reason':'Request result uncertain; reconcile source before any further work.'})
        return 'AMBIGUOUS'
    # The HTTP body alone is not persistence proof; reconcile the database on the next pass.
    return 'DISPATCHED'


def report(jobs, store):
    entries = []
    for job in jobs:
        key = validate_job(job)
        events = store.events(key)
        kinds = [e['event_type'] for e in events]
        # Preserve chronological state, including late reconciliation after ambiguous dispatch.
        state = kinds[-1] if kinds else 'NOT_OBSERVED'
        entries.append({'job_key':key,'session_date':job['session_date'],'phase':job['phase'],
                        'process_state':state,'run_class':job['run_class'],'events':events})
    return {'implementation_version':VERSION, 'phase':'SHADOW', 'broker_execution_enabled':False,
            'opportunity_outcome':'UNKNOWN', 'reason':'Discovery-only evidence does not establish opportunity coverage.',
            'jobs':entries}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--report', action='store_true')
    args = parser.parse_args()
    jobs = json.loads(args.plan.read_text(encoding='utf-8'))
    if not isinstance(jobs, list) or not jobs:
        raise ValueError('Nonempty explicit job list required.')
    keys = [validate_job(j) for j in jobs]
    if len(keys) != len(set(keys)):
        raise ValueError('Duplicate session/phase identity.')
    if not args.apply and not args.report:
        print(json.dumps({'status':'DISABLED_PREVIEW','jobs':jobs}))
        return
    if args.apply and os.getenv('SHADOW_OPERATIONS_ENABLED','false').lower() != 'true':
        raise ValueError('Hosted operations remain disabled.')
    with psycopg.connect(os.environ['OPERATIONS_DATABASE_URL'], autocommit=True, row_factory=dict_row) as conn:
        store = Store(conn)
        if args.apply:
            remote = Remote()
            for job,key in zip(jobs,keys):
                with writer_lock(conn, 'discovery-operation:' + key):
                    process(job,store,remote)
        print(json.dumps(report(jobs,store), default=str))


if __name__ == '__main__':
    # Never print driver/HTTP exception text, request headers or credential-bearing URLs.
    try:
        main()
    except Exception as exc:
        print(json.dumps({'status':'BLOCKED','error_type':type(exc).__name__}))
        raise SystemExit(2)
