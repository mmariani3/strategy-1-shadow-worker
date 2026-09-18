"""Opt-in infrastructure acceptance: native loopback PostgreSQL + dedicated test Sheet.

Requires --apply-test-writes, --connection-file, --credentials, --test-sheet.
Creates a fresh isolated database; never uses the production database or Journal.
Local STRATEGY_1 branch fixtures exercise production projection guards, but every
written row is explicitly excluded from strategy evidence in an INFRASTRUCTURE TEST copy.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from journal_writer import GoogleSheets, PostgresLedger, deliver, source_rows, writer_lock, plan
from journal_projection import JOURNAL_SPREADSHEET_ID


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--connection-file', required=True)
    parser.add_argument('--credentials', required=True)
    parser.add_argument('--test-sheet', required=True)
    parser.add_argument('--apply-test-writes', action='store_true', required=True)
    args = parser.parse_args()
    config = json.loads(Path(args.connection_file).read_text())
    assert config['host'] == '127.0.0.1', 'Only loopback database permitted'
    assert args.test_sheet != JOURNAL_SPREADSHEET_ID, 'Production Journal forbidden'
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(Path(args.credentials).resolve())
    sheets = GoogleSheets(args.test_sheet)
    metadata = sheets.http.get(sheets.base, params={'fields': 'properties.title'}, timeout=30)
    metadata.raise_for_status()
    assert metadata.json()['properties']['title'].startswith('INFRASTRUCTURE TEST -'), 'Test-copy title required'
    database = 'writer_acceptance_' + uuid4().hex
    with psycopg.connect(**config, autocommit=True) as admin:
        admin.execute(sql.SQL('create database {}').format(sql.Identifier(database)))
    config['dbname'] = database
    dsn = make_conninfo(**config)
    with psycopg.connect(dsn, autocommit=True, row_factory=dict_row) as conn:
        schema = json.loads((ROOT/'tests/live_schema_snapshot.json').read_text())
        for role in ('anon', 'authenticated', 'service_role'):
            if not conn.execute('select 1 from pg_roles where rolname=%s', (role,)).fetchone():
                conn.execute(sql.SQL('create role {}').format(sql.Identifier(role)))
        q = lambda s: '"' + s.replace('"', '""') + '"'
        for name in dict.fromkeys(c['table_name'] for c in schema['columns']):
            cols = []
            for c in (c for c in schema['columns'] if c['table_name'] == name):
                typ = c['udt_name']
                if typ.startswith('_'): typ = typ[1:] + '[]'
                cols.append(q(c['column_name'])+' '+typ+(' default '+c['column_default'] if c['column_default'] else '')+(' not null' if c['is_nullable']=='NO' else ''))
            conn.execute('create table public.'+q(name)+' ('+','.join(cols)+')')
        for c in sorted(schema['constraints'], key=lambda c: c['definition'].startswith('FOREIGN')):
            conn.execute('alter table public.'+q(c['table'])+' add constraint '+q(c['name'])+' '+c['definition'])
        names = {c['name'] for c in schema['constraints']}
        for i in schema['indexes']:
            if i['indexname'] not in names: conn.execute(i['indexdef'])
        for name in ('set_updated_at', 'set_strategy_signals_updated_at'):
            conn.execute('create function public.'+name+'() returns trigger language plpgsql as $$ begin new.updated_at=now(); return new; end $$')
        for trigger in schema['triggers']: conn.execute(trigger)
        for migration in sorted((ROOT/'supabase/migrations').glob('*.sql')):
            conn.execute(migration.read_text())
        note = 'INFRASTRUCTURE_TEST: native database/Google transport acceptance; excluded from ALL Strategy #1 evidence.'
        def seed(count):
            run = uuid4()
            conn.execute("insert into strategy_discovery_runs(id,session_date,phase,status,run_key,ruleset_version,experiment_class,candidates_discovered,notes) values (%s,'2026-09-15','PREMARKET','PARTIAL',%s,'v0.3','STRATEGY_1',%s,%s)", (run, 'infrastructure-'+str(run), count, note))
            for state, symbol in list(zip(('REVIEW_REQUIRED','WATCHLIST_CANDIDATE','REJECTED'),('BBAI.WS','DBWATCH','DBREJECT')))[:count]:
                conn.execute('insert into strategy_discovery_items(run_id,symbol,operational_state,notes) values (%s,%s,%s,%s)', (run,symbol,state,note))
            return run
        run = seed(3)
        env = {**os.environ, 'JOURNAL_DATABASE_URL': dsn, 'JOURNAL_SPREADSHEET_ID': args.test_sheet, 'JOURNAL_WRITES_ENABLED':'true'}
        def launch(run_id):
            return subprocess.run([sys.executable,str(ROOT/'journal_writer.py'),'--run-id',str(run_id),'--apply'],env=env,cwd=ROOT,capture_output=True,text=True,timeout=90)
        def success(result):
            if result.returncode: raise RuntimeError(result.stderr)
            return json.loads(result.stdout)
        # A second OS process must fail before touching Sheets while the owner holds the session lock.
        with writer_lock(conn,args.test_sheet):
            blocked = launch(run)
            assert blocked.returncode and 'Another journal writer is active' in blocked.stderr
        first = success(launch(run)); assert first['status']=='VERIFIED' and first['rows']==4
        retry = success(launch(run)); assert retry['status']=='NOOP'
        rows = source_rows(conn,run_id=run)
        snapshot = sheets.read()
        assert not plan(rows,snapshot)
        for row in rows:
            grid=snapshot[row['sheet_name']]['values']; index=grid[0].index(row['key_column'])
            assert sum(len(r)>index and r[index]==row['key'] for r in grid[1:])==1
        # Real accepted Google write followed by a simulated lost acknowledgement.
        ambiguous_run=seed(0)
        class LostAcknowledgement:
            def prepare(self,patches): return sheets.prepare(patches)
            def verify_native(self,patches,stage): return sheets.verify_native(patches,stage)
            def read(self): return sheets.read()
            def write(self,patches):
                sheets.write(patches)
                raise TimeoutError('INJECTED: acknowledgement lost after Google accepted write')
        with writer_lock(conn,args.test_sheet):
            try: deliver(source_rows(conn,run_id=ambiguous_run),LostAcknowledgement(),PostgresLedger(conn,args.test_sheet))
            except TimeoutError: pass
            else: raise AssertionError('Failure injection did not run')
        blocked=launch(ambiguous_run)
        assert blocked.returncode and 'earlier delivery is unresolved' in blocked.stderr
        assert not plan(source_rows(conn,run_id=ambiguous_run),sheets.read())
        statuses=conn.execute('select status,count(*) n from journal_deliveries group by status order by status').fetchall()
        assert statuses==[{'status':'PENDING','n':1},{'status':'VERIFIED','n':1}]
        from journal_writer import reconcile_pending
        with writer_lock(conn,args.test_sheet):
            reconciled=reconcile_pending(sheets,PostgresLedger(conn,args.test_sheet))
        assert reconciled['sheet_writes']==0 and not PostgresLedger(conn,args.test_sheet).pending()
        print(json.dumps({'status':'PASSED','database':database,'source_records':4,'retry':'NOOP','competing_process':'BLOCKED',
            'ambiguous_write':'PENDING preserved, retry blocked, then read-only reconciliation VERIFIED',
            'native_metadata':'Verified on every delivery, including date text and BBAI.WS literal'}))


if __name__=='__main__': main()
