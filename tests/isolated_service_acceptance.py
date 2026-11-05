"""Real HTTP Discovery/Orchestrator/Worker + PostgREST/native PostgreSQL.

Requires a loopback connection JSON and template database produced by the
credentialed writer acceptance. Copies the template into a new disposable DB.
Quotes are injected; no external market requests, Google writes, or deployments.
STRATEGY_1 branch fixtures exist only in the isolated DB and are never evidence.
"""
import argparse, base64, hashlib, hmac, json, os, secrets, subprocess, sys, threading, time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
import requests

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'tests'))
from conftest import candidate_data
from discovery_coordinator import QualificationRequest, SetupRequest
from orchestrator import ConfirmationIn

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--connection-file',required=True); p.add_argument('--template-db',required=True)
    p.add_argument('--postgrest',required=True); p.add_argument('--postgres-bin',required=True)
    args=p.parse_args(); config=json.loads(Path(args.connection_file).read_text())
    assert config['host']=='127.0.0.1' and args.template_db.startswith('writer_acceptance_')
    database='services_acceptance_'+uuid4().hex
    with psycopg.connect(**config,autocommit=True) as admin:
        admin.execute(sql.SQL('create database {} template {}').format(sql.Identifier(database),sql.Identifier(args.template_db)))
    config['dbname']=database; dsn=make_conninfo(**config)
    conn=psycopg.connect(dsn,autocommit=True,row_factory=dict_row)
    conn.execute('alter role service_role bypassrls')
    conn.execute('grant usage on schema public to service_role')
    conn.execute('grant select,insert,update on all tables in schema public to service_role')
    token=secrets.token_urlsafe(32); jwt_secret=secrets.token_urlsafe(48)
    b64=lambda b:base64.urlsafe_b64encode(b).rstrip(b'=')
    unsigned=b64(b'{"alg":"HS256","typ":"JWT"}')+b'.'+b64(json.dumps({'role':'service_role','exp':int(time.time())+1800}).encode())
    jwt=(unsigned+b'.'+b64(hmac.new(jwt_secret.encode(),unsigned,hashlib.sha256).digest())).decode()
    class Gateway(BaseHTTPRequestHandler):
        def log_message(self,*a): pass
        def forward(self):
            if self.headers.get('apikey')!=token or not self.path.startswith('/rest/v1/'):
                self.send_error(403); return
            headers={'Authorization':'Bearer '+jwt,'Content-Type':'application/json','Prefer':self.headers.get('Prefer','')}
            r=requests.request(self.command,'http://127.0.0.1:55440/'+self.path[len('/rest/v1/'):],headers=headers,data=self.rfile.read(int(self.headers.get('Content-Length',0))),timeout=15)
            self.send_response(r.status_code); self.send_header('Content-Type',r.headers.get('Content-Type','application/json')); self.end_headers(); self.wfile.write(r.content)
        do_GET=do_POST=do_PATCH=forward
    gateway=ThreadingHTTPServer(('127.0.0.1',55441),Gateway)
    threading.Thread(target=gateway.serve_forever,daemon=True).start()
    env={**os.environ,'PATH':str(Path(args.postgres_bin).resolve())+os.pathsep+os.environ['PATH'],
         'PGRST_DB_URI':dsn,'PGRST_DB_SCHEMAS':'public','PGRST_SERVER_HOST':'127.0.0.1','PGRST_SERVER_PORT':'55440','PGRST_JWT_SECRET':jwt_secret,
         'SUPABASE_URL':'http://127.0.0.1:55441','SUPABASE_SECRET_KEY':token,
         'WORKER_TOKEN':token,'ORCHESTRATOR_TOKEN':token,'DISCOVERY_SERVICE_TOKEN':token,
         'STRATEGY_WORKER_URL':'http://127.0.0.1:55442','ORCHESTRATOR_URL':'http://127.0.0.1:55443','ALPACA_DATA_FEED':'sip',
         'MAX_DOLLAR_RISK':'50','MAX_DAILY_LOSS_DOLLARS':'100','MAX_TRADES_PER_DAY':'3','MAX_NOTIONAL':'10000'}
    processes=[]; logs=[]
    try:
        commands=[[str(Path(args.postgrest).resolve())]]+[[sys.executable,str(ROOT/'tests/isolated_service_launcher.py'),module,str(port)] for module,port in [('main',55442),('orchestrator',55443),('discovery_coordinator',55444)]]
        for i,command in enumerate(commands):
            log=open(ROOT/'.tmp'/f'service-acceptance-{i}.log','w'); logs.append(log)
            processes.append(subprocess.Popen(command,env=env,cwd=ROOT,stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)))
        for port in (55442,55443,55444):
            for attempt in range(50):
                try:
                    r=requests.get(f'http://127.0.0.1:{port}/health',timeout=1)
                    if r.ok: break
                except requests.RequestException: pass
                time.sleep(.2)
            else: raise RuntimeError(f'Local service {port} did not start; inspect ignored logs')
            assert r.json()['broker_execution_enabled'] is False
        def post(port,path,body=None,expected=200,auth=True):
            r=requests.post(f'http://127.0.0.1:{port}'+path,json=body,headers={'Authorization':'Bearer '+token} if auth else {},timeout=20)
            assert r.status_code==expected,(path,r.status_code,r.text)
            return r.json()
        post(55443,'/monitor/run-once',expected=401,auth=False)
        def prepare(missing=False,infra=False):
            data=candidate_data.__wrapped__(); data['notes']='Isolated branch fixture; excluded from every validation metric'
            run,item=uuid4(),uuid4()
            cls='INFRASTRUCTURE_TEST' if infra else 'STRATEGY_1'
            conn.execute("insert into strategy_discovery_runs(id,session_date,phase,status,run_key,ruleset_version,experiment_class,candidates_discovered,notes) values (%s,%s,'POST_OPEN','PARTIAL',%s,'v0.3',%s,1,'Isolated acceptance only')",(run,data['session_date'],str(run),cls))
            conn.execute("insert into strategy_discovery_items(id,run_id,symbol,operational_state) values (%s,%s,'LOCAL','WATCHLIST_CANDIDATE')",(item,run))
            qualify={k:v for k,v in data.items() if k in QualificationRequest.model_fields}
            qualify.update(reviewer='isolated acceptance',reviewed_at=data['current_review']['reviewed_at'])
            q=post(55444,f'/items/{item}/qualify',qualify); assert q['candidate_id'] is None and q['setup_status']=='SETUP_REQUIRED'
            assert conn.execute('select count(*) n from strategy_candidates where source_discovery_item_id=%s',(item,)).fetchone()['n']==0
            setup={k:v for k,v in data.items() if k in SetupRequest.model_fields}
            setup.update(setup_rationale='Isolated predefined fixture',trigger_operator='GTE')
            if missing: setup.pop('data_quality_ok')
            if infra: setup['data_kind']='SYNTHETIC'
            result=post(55444,f'/items/{item}/setup',setup)
            replay=post(55444,f'/items/{item}/setup',setup)
            assert replay['idempotent_replay'] and replay['candidate_id']==result['candidate_id']
            return result['candidate_id'],str(run),data,result
        held,_,_,held_result=prepare(missing=True)
        assert held_result['operational_state']=='HOLD_UNRESOLVED'
        cid,run,data,result=prepare()
        assert result['operational_state']=='WAITING_FOR_TRIGGER',result
        monitored=post(55443,'/monitor/run-once'); assert monitored['checked']==1 and monitored['results'][0]['result']=='TRIGGER_OBSERVED',monitored
        def candidate(): return conn.execute('select * from strategy_candidates where id=%s',(cid,)).fetchone()
        assert candidate()['trigger_confirmed'] is False
        def review(**changes):
            fresh=candidate_data.__wrapped__(); now=datetime.now(timezone.utc)
            ts=(now-timedelta(milliseconds=1)).isoformat(); fresh['data_timestamp']=ts
            fresh['current_review'].update(data_timestamp=ts,reviewed_at=now.isoformat(),valid_until=(now+timedelta(seconds=60)).isoformat())
            body={k:v for k,v in fresh.items() if k in ConfirmationIn.model_fields}
            return {**body,'confirmed':False,'confirmation_source':'isolated reviewer',**changes}
        resumed=post(55443,f'/candidates/{cid}/confirm-trigger',review(resume_monitoring=True))
        assert resumed['operational_state']=='WAITING_FOR_TRIGGER' and candidate()['trigger_observed_at'] is None
        assert conn.execute("select count(*) n from strategy_candidate_events where candidate_id=%s and event_type='TRIGGER_OBSERVED'",(cid,)).fetchone()['n']==1
        post(55443,'/monitor/run-once')
        blocked=post(55443,f'/candidates/{cid}/confirm-trigger',review(confirmed=True,target_validated=False))
        assert blocked['operational_state']=='HOLD_UNRESOLVED'
        negative=post(55443,f'/candidates/{cid}/confirm-trigger',review(missed_trigger=True))
        assert negative['worker']['decision']=='NO_TRADE' and candidate()['missed_trigger'] is True
        # A separate clean lifecycle must confirm prospectively before a SHADOW TRADE.
        cid,run,data,result=prepare(); post(55443,'/monitor/run-once')
        trade=post(55443,f'/candidates/{cid}/confirm-trigger',review(confirmed=True))
        assert trade['worker']['decision']=='TRADE',trade
        c=candidate(); s=conn.execute('select * from strategy_signals where id=%s',(c['last_signal_id'],)).fetchone()
        assert s['status']=='SHADOW' and s['decision_inputs']['run_id']==run and s['decision_inputs']['candidate_id']==cid
        assert s['journal_trade_id']==c['journal_trade_id'] and 'sha256=' in s['worker_version']
        infra,_,_,result=prepare(infra=True)
        assert conn.execute('select experiment_class from strategy_candidates where id=%s',(infra,)).fetchone()['experiment_class']=='INFRASTRUCTURE_TEST'
        print(json.dumps({'status':'PASSED','database':database,'transport':'real HTTP + PostgREST 16.3 + PostgreSQL 17.6','checks':['auth rejection','qualification without candidate','incomplete setup HOLD','idempotent setup replay','monitor excludes HOLD','crossing observation only','explicit resume preserves history','unapproved target HOLD','negative missed-trigger NO_TRADE','prospective SHADOW TRADE','structured trace IDs','infrastructure classification'],'limitations':['injected quote provider','local gateway adapter; hosted Supabase/Render configuration not exercised']}))
    finally:
        for proc in reversed(processes): proc.terminate()
        for proc in processes:
            try: proc.wait(timeout=10)
            except subprocess.TimeoutExpired: proc.kill()
        for log in logs: log.close()
        gateway.shutdown(); conn.close()

if __name__=='__main__': main()
