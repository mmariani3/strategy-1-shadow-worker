"""Fixed-endpoint clients and collectors. Constructors never read credentials.

No ambient session, retry, deployment, environment, order or Journal API. All
credentials/transports/authorizations must be explicitly supplied by a reviewed
launcher; this module is not that launcher. Tests supply invented transports.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from coordinator_launch_guard import SERVICE, WORKSPACE, DATABASE, URL, REQUIRED_FILES, need, fresh
from coordinator_acceptance_controller import snapshot_baseline

RENDER = "https://api.render.com/v1"
REPO = "https://github.com/mmariani3/strategy-1-shadow-worker"
TABLES = ("strategy_discovery_runs", "strategy_discovery_items", "strategy_discovery_events",
          "strategy_candidates", "strategy_signals", "strategy_candidate_events",
          "execution_shadow_audit", "journal_deliveries")


class AdapterError(RuntimeError):
    pass


def fail(code="ADAPTER_UNAVAILABLE"):
    raise AdapterError(code) from None


class FixedHTTP:
    """Allowlist, bounded streamed JSON, exact credential destination, no retry."""
    def __init__(self, *, session, token, allowed, expires_at, now=None, monotonic=None):
        self.session, self._token = session, token
        self.allowed = frozenset(allowed)
        self.expires = expires_at
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.monotonic = monotonic or time.monotonic
        # Do not inherit netrc, proxy credentials, adapters with retries, cookies
        # or default auth/headers. Caller supplies a dedicated fresh session.
        self.session.trust_env = False
        self.session.auth = None
        self.session.headers.clear()
        self.session.cookies.clear()
        for adapter in getattr(self.session, "adapters", {}).values():
            retries = adapter.max_retries
            need(retries.total == 0 and retries.redirect in (None, 0), "HTTP_RETRY_ADAPTER_REJECTED")
        need(isinstance(token,str) and bool(token) and expires_at.tzinfo is not None, "CREDENTIAL_UNAVAILABLE")

    def call(self, method, url, *, params=None, body=None, statuses=(200,), seconds=20, max_bytes=4*1024*1024):
        response = None
        try:
            need((method,url) in self.allowed, "HTTP_DESTINATION_REJECTED")
            need(self.now() < self.expires and 0 < seconds <= 900, "HTTP_AUTHORIZATION_EXPIRED")
            start = self.monotonic()
            response = self.session.request(method, url, params=params, json=body,
                headers={"Authorization":"Bearer "+self._token, "Accept":"application/json"},
                timeout=(min(5,seconds), seconds), allow_redirects=False, stream=True)
            need(response.status_code in statuses, "HTTP_STATUS_REJECTED")
            raw = bytearray()
            for chunk in response.iter_content(16384):
                need(self.monotonic()-start < seconds and self.now() < self.expires, "HTTP_DEADLINE")
                need(isinstance(chunk,bytes) and len(raw)+len(chunk) <= max_bytes, "HTTP_BODY_LIMIT")
                raw.extend(chunk)
            need(self.monotonic()-start < seconds and self.now() < self.expires, "HTTP_DEADLINE")
            return json.loads(raw) if raw else None
        except Exception:
            fail()  # Never echo tokens, provider text, JSON or request diagnostics.
        finally:
            if response is not None:
                try: response.close()
                except Exception: pass


class RenderAdapter:
    def __init__(self, *, session, token, expires_at, now=None, monotonic=None, suspend_only=False, rehearsal_only=False):
        paths = {("GET",RENDER+"/services"), ("GET",RENDER+"/services/"+SERVICE),
                 ("GET",RENDER+"/services/"+SERVICE+"/deploys"),
                 ("POST",RENDER+"/services/"+SERVICE+"/suspend")}
        if not suspend_only:
            paths.add(("POST",RENDER+"/services/"+SERVICE+"/resume"))
        self.http = FixedHTTP(session=session, token=token, allowed=paths, expires_at=expires_at,
                              now=now, monotonic=monotonic)
        self.suspend_only = suspend_only
        self.rehearsal_only = rehearsal_only

    def inventory(self):
        try:
            rows = self.http.call("GET",RENDER+"/services",params={"ownerId":WORKSPACE,"limit":100})
            need(isinstance(rows,list) and len(rows)<100, "RENDER_INVENTORY_INCOMPLETE")
            result=[]
            for row in rows:
                s=row["service"]
                need(s["ownerId"]==WORKSPACE,"RENDER_OWNER")
                result.append({k:s[k] for k in ("id","ownerId","suspended","autoDeploy","autoDeployTrigger")})
            need(len({r["id"] for r in result})==len(result),"RENDER_DUPLICATE_ID")
            return result
        except Exception: fail("RENDER_INVENTORY_UNAVAILABLE")

    def target(self):
        try:
            row=self.http.call("GET",RENDER+"/services/"+SERVICE)
            need(row["id"]==SERVICE and row["ownerId"]==WORKSPACE,"RENDER_TARGET")
            return row
        except Exception: fail("RENDER_TARGET_UNAVAILABLE")

    def deployment(self, policy):
        try:
            target=self.target()
            need(target["repo"]==REPO and target["serviceDetails"]["url"]==URL,"RENDER_CODE_TARGET")
            from coordinator_runtime_preflight import START_COMMAND
            command=START_COMMAND if self.rehearsal_only else "uvicorn coordinator_acceptance_app:app --host 0.0.0.0 --port $PORT"
            need(target["serviceDetails"]["envSpecificDetails"]["startCommand"] == command, "RENDER_ENTRY_POINT")
            rows=self.http.call("GET",RENDER+"/services/"+SERVICE+"/deploys",params={"limit":1})
            need(len(rows)==1,"RENDER_DEPLOYMENT_COUNT")
            d=rows[0]["deploy"]
            need(d["id"]==policy.deployment and d["commit"]["id"]==policy.commit and d["status"]=="live",
                 "RENDER_DEPLOYMENT_MISMATCH")
            # Render attests commit/deployment, NOT application source bytes.
            # Source hash must come from the independent publication artifact;
            # running runtime probes must separately report it before dispatch.
            return {"id":d["id"],"commit":d["commit"]["id"],"source_hash":policy.source_hash,
                    "service":SERVICE,"url":URL,"status":d["status"]}
        except Exception: fail("RENDER_DEPLOYMENT_UNAVAILABLE")

    def resume(self, service):
        need(service==SERVICE and not self.suspend_only,"RENDER_RESUME_DISABLED")
        self.target()
        self.http.call("POST",RENDER+"/services/"+SERVICE+"/resume",statuses=(202,))

    def suspend(self, service):
        need(service==SERVICE,"RENDER_SUSPEND_TARGET")
        before=self.target()
        if before["suspended"] != "suspended":
            self.http.call("POST",RENDER+"/services/"+SERVICE+"/suspend",statuses=(200,202))
        return self.target()["suspended"]=="suspended"


class RuntimeAdapter:
    def __init__(self, *, session, token, expires_at, now=None, monotonic=None):
        self.http=FixedHTTP(session=session,token=token,expires_at=expires_at,now=now,monotonic=monotonic,
            allowed={("GET",URL+"/acceptance/preflight"),("POST",URL+"/scan/run-once")})
        self.post_used=False

    def probe(self):
        return self.http.call("GET",URL+"/acceptance/preflight",seconds=30)

    def post(self, url, body):
        need(not self.post_used and url==URL+"/scan/run-once", "RUNTIME_POST_ALREADY_USED_OR_TARGET")
        need(set(body)=={"session_date","phase","run_class","include_dated_prior_evidence"}
             and body["phase"]=="PREMARKET" and body["run_class"]=="INFRASTRUCTURE_TEST"
             and body["include_dated_prior_evidence"] is True,"RUNTIME_POST_SCOPE")
        self.post_used=True
        return self.http.call("POST",url,body=body,seconds=900)


CATALOG_SQL = """select jsonb_build_object(
 'columns',(select coalesce(jsonb_agg(to_jsonb(c) order by table_name,ordinal_position),'[]'::jsonb)
    from information_schema.columns c where table_schema='public' and table_name=any(%s)),
 'indexes',(select coalesce(jsonb_agg(to_jsonb(i) order by tablename,indexname),'[]'::jsonb)
    from pg_catalog.pg_indexes i where schemaname='public' and tablename=any(%s)),
 'triggers',(select coalesce(jsonb_agg(jsonb_build_object('table',t.tgrelid::regclass::text,
    'name',t.tgname,'enabled',t.tgenabled,'definition',pg_catalog.pg_get_triggerdef(t.oid),
    'function',pg_catalog.pg_get_functiondef(t.tgfoid)) order by t.tgrelid,t.tgname),'[]'::jsonb)
    from pg_catalog.pg_trigger t join pg_catalog.pg_class c on c.oid=t.tgrelid
    join pg_catalog.pg_namespace n on n.oid=c.relnamespace
    where not t.tgisinternal and n.nspname='public' and c.relname=any(%s)),
 'constraints',(select coalesce(jsonb_agg(jsonb_build_object('table',c.conrelid::regclass::text,
    'name',c.conname,'definition',pg_catalog.pg_get_constraintdef(c.oid)) order by c.conrelid,c.conname),'[]'::jsonb)
    from pg_catalog.pg_constraint c join pg_catalog.pg_class t on t.oid=c.conrelid
    join pg_catalog.pg_namespace n on n.oid=t.relnamespace where n.nspname='public' and t.relname=any(%s)))"""


class DatabaseCollector:
    """DB-API connection supplied by an authorized staging-only connection factory.

    One repeatable-read, read-only transaction covers catalog, counts and ALL
    protected rows. Never accept a caller's arbitrary SQL, table name or DSN.
    Connection identity must be independently bound to the approved project by
    the launcher. A string project ID is not authentication of a DB connection.
    """
    def __init__(self, *, connect, project_id, now=None, max_rows=100000, max_bytes=64*1024*1024):
        need(project_id==DATABASE,"DATABASE_DESTINATION_REJECTED")
        self.connect=connect
        self.now=now or (lambda:datetime.now(timezone.utc))
        self.max_rows=min(max_rows,100000)
        self.max_bytes=min(max_bytes,64*1024*1024)

    def collect(self):
        connection=cursor=None
        try:
            started=self.now()
            connection=self.connect()
            connection.autocommit=True  # Fresh dedicated connection; explicit transaction below.
            cursor=connection.cursor()
            cursor.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '10s'")
            cursor.execute("SELECT current_setting('transaction_read_only'), current_setting('transaction_isolation')")
            need(cursor.fetchone()==('on','repeatable read'),"DATABASE_READ_ONLY_TRANSACTION_REQUIRED")
            tables={}; total_rows=total_bytes=0
            for table in TABLES:
                cursor.execute('SELECT count(*) FROM public.'+table)
                count=cursor.fetchone()[0]
                need(type(count) is int and 0<=count<=self.max_rows-total_rows,"DATABASE_ROW_LIMIT")
                rows=[]
                stream=connection.cursor(name='snapshot_'+table)
                try:
                    # Server cursor avoids eagerly buffering the full table.
                    # Oversized rows return a sentinel and fail, never disappear.
                    stream.execute("SELECT CASE WHEN octet_length(to_jsonb(t)::text)<=2097152 THEN to_jsonb(t) "
                        "ELSE jsonb_build_object('oversized_row',true) END FROM public."+table+' t ORDER BY id')
                    while True:
                        batch=stream.fetchmany(25)
                        if not batch: break
                        for item in batch:
                            row=item[0]
                            need(isinstance(row,dict) and "id" in row,"DATABASE_ROW_SHAPE")
                            total_bytes+=len(json.dumps(row,sort_keys=True,allow_nan=False).encode())
                            total_rows+=1
                            need(total_bytes<=self.max_bytes and total_rows<=self.max_rows,"DATABASE_SNAPSHOT_LIMIT")
                            need(0<=(self.now()-started).total_seconds()<=90,"DATABASE_SNAPSHOT_DEADLINE")
                            rows.append(row)
                finally:
                    stream.close()
                need(len(rows)==count and len({r['id'] for r in rows})==count,"DATABASE_SNAPSHOT_INCOMPLETE")
                tables[table]=rows
            cursor.execute(CATALOG_SQL,(list(TABLES),)*4)
            catalog=cursor.fetchone()[0]
            need(set(catalog)=={'columns','indexes','triggers','constraints'}
                 and all(catalog.values()),"DATABASE_CATALOG_INCOMPLETE")
            cursor.execute("SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_extension WHERE extname='pg_cron')")
            cron=[]
            if cursor.fetchone()[0]:
                cursor.execute("SELECT jobid FROM cron.job WHERE active ORDER BY jobid")
                cron=[r[0] for r in cursor.fetchall()]
            cursor.execute("SELECT pid FROM pg_catalog.pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND state='active' ORDER BY pid")
            callers=[r[0] for r in cursor.fetchall()]
            snapshot={"runs":tables[TABLES[0]],"items":tables[TABLES[1]],"events":tables[TABLES[2]],
                      "protected_tables":{name:tables[name] for name in TABLES[3:]}}
            need(0<=(self.now()-started).total_seconds()<=90,"DATABASE_SNAPSHOT_DEADLINE")
            return {"checked_at":started.isoformat(),"finished_at":self.now().isoformat(),"snapshot":snapshot,
                "baseline":snapshot_baseline(snapshot),"schema_sha256":hashlib.sha256(
                    json.dumps(catalog,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
                "catalog":catalog,"active_pg_cron":cron,"other_active_session_ids":callers}
        except Exception: fail("DATABASE_SNAPSHOT_UNAVAILABLE")
        finally:
            cleanup_failed=False
            if connection is not None:
                try: connection.rollback()
                except Exception: cleanup_failed=True
            if cursor is not None:
                try: cursor.close()
                except Exception: cleanup_failed=True
            if connection is not None:
                try: connection.close()
                except Exception: cleanup_failed=True
            if cleanup_failed: fail("DATABASE_CONNECTION_CLEANUP_UNVERIFIED")


class EvidenceCollector:
    """Compose actual adapter reads; do not restamp cached master/caller proof."""
    def __init__(self, *, policy, source_directory, render, database, project_status,
                 masters, callers, rehearsal, armed, collector_id, now):
        self.policy=policy; self.root=Path(source_directory).resolve()
        self.render=render; self.database=database; self.project_status=project_status
        self.masters=masters; self.callers=callers; self.rehearsal=rehearsal; self.armed=armed
        self.collector_id=collector_id; self.now=now
        self.baseline_snapshot=None

    def collect(self):
        p=self.policy
        p.validate(self.now())
        started=self.now()
        hashes={name:hashlib.sha256((self.root/name).read_bytes()).hexdigest() for name in REQUIRED_FILES}
        services=self.render.inventory()
        deployment=self.render.deployment(p)
        status=self.project_status()
        need(status['id']==DATABASE and status['status']=='ACTIVE_HEALTHY','DATABASE_NOT_READY')
        db=self.database.collect()
        masters=self.masters(); callers=self.callers()
        for item in (status,db,masters,callers): fresh(item['checked_at'],self.now(),120)
        need(db['other_active_session_ids']==[], 'DATABASE_COMPETING_SESSION')
        snapshot=db['snapshot']
        if self.baseline_snapshot is None: self.baseline_snapshot=deepcopy(snapshot)
        # Timestamp the start, including Render reads, rather than relabeling a
        # slow collection as fresh at completion. All provider stamps also checked.
        fresh(started.isoformat(),self.now(),120)
        return {'checked_at':started.isoformat(),
            'policy_hash':p.fingerprint,'file_sha256':hashes,'masters':masters['revisions'],'services':services,
            'deployment':deployment,'database':{'id':DATABASE,'status':status['status'],
                'schema_sha256':db['schema_sha256'],'baseline':db['baseline'],
                'matching_run_keys':[r['run_key'] for r in snapshot['runs'] if r.get('run_key')==p.run_key],
                'unfinished_run_ids':[r['id'] for r in snapshot['runs'] if r.get('status')=='IN_PROGRESS']},
            'callers':{'active_schedules':callers['active_schedules'],
                'conflicting_process_ids':callers['conflicting_process_ids'],'active_pg_cron':db['active_pg_cron']},
            'rehearsal':self.rehearsal(),'armed':self.armed(),'collector_id':self.collector_id}

    def readback(self):
        need(self.baseline_snapshot is not None,'BASELINE_NOT_COLLECTED')
        data=self.database.collect()
        need(data['schema_sha256']==self.policy.schema_hash,'READBACK_SCHEMA_CHANGED')
        return {'checked_at':data['checked_at'],'before':deepcopy(self.baseline_snapshot),'after':data['snapshot']}


class BoundPorts:
    """Concrete controller wiring with explicit, separately authorized handles.

    Connector callbacks (project status/pause, masters/callers, notification)
    remain supplied by the launch integration, never read from status JSON.
    """
    def __init__(self, *, policy, render, runtime_client, collector, watchdog_process,
                 project_status, pause_project, notify, render_key, implementation_version, now):
        self.policy=policy; self.render=render; self.runtime_client=runtime_client
        self.collector=collector; self.watchdog_process=watchdog_process
        self.project_status=project_status; self.pause_project=pause_project; self.send_notice=notify
        self._render_key=render_key; self.implementation_version=implementation_version; self.now=now

    def observations(self): return self.collector.collect()
    def readback(self): return self.collector.readback()
    def runtime_probe(self): return self.runtime_client.probe()
    def post(self,url,body): return self.runtime_client.post(url,body)
    def resume(self,service): return self.render.resume(service)
    def suspend(self,service): return self.render.suspend(service)
    def notify(self,code): return self.send_notice(code)
    def database_status(self): return self.project_status()

    def pause_database(self,project):
        need(project==DATABASE,'DATABASE_PAUSE_TARGET')
        from coordinator_launch_guard import isolation
        isolation(self.render.inventory())
        return self.pause_project(DATABASE)

    def cleanup_observations(self):
        start=self.now()
        rows=self.render.inventory()
        return {'checked_at':start.isoformat(),'services':rows}

    def start_watchdog(self,service,nonce,policy):
        from dataclasses import asdict
        need(service==SERVICE and policy==self.policy,'WATCHDOG_SCOPE')
        data=asdict(policy)
        data['day']=policy.day.isoformat(); data['authorized_until']=policy.authorized_until.isoformat()
        self.watchdog_process.start({'mode':'render','nonce':nonce,'policy_hash':policy.fingerprint,
                                    'policy':data,'render_key':self._render_key})
        end=time.monotonic()+20
        while time.monotonic()<end:
            try: return self.watchdog_process.receipt()
            except FileNotFoundError: time.sleep(0.1)
        fail('WATCHDOG_READY_TIMEOUT')

    def watchdog_receipt(self,nonce):
        need(nonce==self.watchdog_process.nonce,'WATCHDOG_NONCE')
        return self.watchdog_process.receipt()

    def stop_watchdog(self,nonce):
        need(nonce==self.watchdog_process.nonce,'WATCHDOG_NONCE')
        observed=self.cleanup_observations(); db=self.project_status()
        fresh(db['checked_at'],self.now(),30)
        return self.watchdog_process.stop_after_cleanup(services=observed['services'],
            database={'id':db['id'],'status':db['status']},checked_at=observed['checked_at'])
