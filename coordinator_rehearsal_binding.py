"""Explicitly assembled no-scan rehearsal. No credential loader or enabled CLI.

Connector callbacks must be authenticated host integrations. Offline dictionaries
exercise the contract but never authenticate a hosted rehearsal or arm a run.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
import hashlib
import os
import re
import time
import uuid

from coordinator_launch_guard import SERVICE, DATABASE, URL, MASTERS, REQUIRED_FILES, PACIFIC, need, fresh, isolation, timestamp
from coordinator_runtime_preflight import source_hash
from coordinator_service_adapters import FixedHTTP, AdapterError, error_diagnostic, safe_steps
from coordinator_acceptance_controller import consume, snapshot_baseline
from setup_evidence import digest
from coordinator_connector_snapshot import KIND, preservation_baseline


# Readiness may use spare startup time, never the authentication/safety reserve.
# A health request has separate 3s connect and 3s read limits. The authenticated
# request has separate 5s connect and 25s read limits, plus 10s safety margin.
READINESS_MAX_SECONDS = 60
AUTHENTICATION_RESERVE_SECONDS = 40


@dataclass(frozen=True)
class RehearsalPermit:
    day: date
    commit: str
    source_hash: str
    deployment: str
    files: tuple
    masters: tuple
    schema_hash: str
    not_before: datetime
    authorized_until: datetime
    authorization_id: str

    @property
    def suspend_at(self): return self.not_before+timedelta(minutes=3)
    @property
    def verify_by(self): return self.not_before+timedelta(minutes=8)
    @property
    def fingerprint(self): return digest(self.as_dict())
    def as_dict(self):
        return {'day':self.day.isoformat(),'commit':self.commit,'source_hash':self.source_hash,
            'deployment':self.deployment,'files':self.files,'masters':self.masters,'schema_hash':self.schema_hash,
            'not_before':self.not_before.isoformat(),'authorized_until':self.authorized_until.isoformat(),
            'authorization_id':self.authorization_id}
    @classmethod
    def parse(cls, data):
        data=dict(data)
        data['day']=date.fromisoformat(data['day'])
        for key in ('not_before','authorized_until'): data[key]=timestamp(data[key])
        for key in ('files','masters'): data[key]=tuple(tuple(v) for v in data[key])
        return cls(**data)
    def validate(self, now):
        need(now.tzinfo is not None and now.astimezone(PACIFIC).date()==self.day,'REHEARSAL_DATE')
        need(self.not_before.tzinfo is not None and self.authorized_until.tzinfo is not None
             and self.not_before<=now<self.authorized_until
             and self.verify_by<=self.authorized_until<=self.not_before+timedelta(minutes=15)
             and self.not_before.astimezone(PACIFIC).date()==self.day
             and self.authorized_until.astimezone(PACIFIC).date()==self.day,'REHEARSAL_WINDOW')
        need(isinstance(self.authorization_id,str) and bool(self.authorization_id),'REHEARSAL_AUTHORIZATION')
        need(bool(re.fullmatch('[a-f0-9]{40}',self.commit)) and bool(re.fullmatch('dep-[a-z0-9]+',self.deployment)),
             'REHEARSAL_CODE')
        need(set(dict(self.files))==REQUIRED_FILES and len(self.files)==len(REQUIRED_FILES),'REHEARSAL_FILES')
        need(set(dict(self.masters))==MASTERS and len(self.masters)==3
             and all(isinstance(v,str) and v for v in dict(self.masters).values()),'REHEARSAL_MASTERS')
        need(all(isinstance(v,str) and re.fullmatch('[a-f0-9]{64}',v)
             for v in [self.source_hash,self.schema_hash,*dict(self.files).values()]),'REHEARSAL_HASH')
        need(self.source_hash==digest(dict(self.files)),'REHEARSAL_SOURCE_BINDING')


class ReadOnlyRuntimeClient:
    def __init__(self, *, session, token, expires_at, now):
        self.http=FixedHTTP(session=session,token=token,expires_at=expires_at,now=now,
                           allowed={('GET',URL+'/health'),('GET',URL+'/acceptance/preflight')})
    def health(self): return self.http.call('GET',URL+'/health',seconds=3,max_bytes=16384)
    def probe(self):
        return self.http.call('GET',URL+'/acceptance/preflight',seconds=25,
                              max_bytes=65536,preflight_diagnostics=True)

    def wait_ready(self, *, deadline, now, monotonic, sleep):
        """Only health GETs retry. Health is never provider authentication."""
        start=monotonic(); wall=now(); attempts=0
        self.readiness_steps=[]
        def remaining():
            return min((deadline-now()).total_seconds(),
                       READINESS_MAX_SECONDS-(monotonic()-start))
        while attempts<15:
            need(remaining()>6,'REHEARSAL_READINESS_EXHAUSTED')
            need(abs((now()-wall).total_seconds()-(monotonic()-start))<=5,'REHEARSAL_CLOCK_DRIFT')
            attempts+=1
            call_start=monotonic()
            try:
                data=self.health()
            except AdapterError as exc:
                self.readiness_steps.append({'phase':'readiness',**error_diagnostic(
                    exc,elapsed=monotonic()-call_start)})
                # Only cold-start transport/unavailable responses may retry.
                retry=(exc.diagnostic['error'] in
                       {'CONNECT_TIMEOUT','READ_TIMEOUT','TIMEOUT','CONNECTION_FAILED'} or
                       exc.diagnostic['error']=='HTTP_STATUS' and exc.diagnostic['http_status'] in {502,503,504})
                if not retry: raise
                if attempts==15 or remaining()<=7: raise
                sleep(min(2,max(0,remaining()-6)))
                continue
            self.readiness_steps.append({'phase':'readiness','error':'OK','http_status':200,
                                        'elapsed_seconds':monotonic()-call_start})
            need(remaining()>0,'REHEARSAL_READINESS_EXHAUSTED')
            need(type(data) is dict and data.get('mode')=='SHADOW'
                 and all(data.get(k) is False for k in ('broker_execution_enabled','qualification_routes',
                     'journal_routes','automatic_promotion','strategy_evidence_eligible','launch_verifier_installed'))
                 and data.get('readiness')=='NOT_HOSTED_ACCEPTED','REHEARSAL_HEALTH_SAFETY')
            return {'status':'HTTP_READY_ONLY_NOT_AUTHENTICATED','attempts':attempts}
        need(False,'REHEARSAL_READINESS_EXHAUSTED')


class RehearsalConnections:
    def __init__(self, *, permit, render, runtime, database, directory, project_status,
                 pause_project, masters, callers, watchdog_process, render_key, now):
        need(render.rehearsal_only is True and type(runtime) is ReadOnlyRuntimeClient,'NO_SCAN_BINDING')
        self.permit=permit; self.render=render; self.runtime=runtime; self.database=database
        self.directory=Path(directory); self.project_status=project_status; self.pause_project=pause_project
        self.masters=masters; self.callers=callers; self.watchdog=watchdog_process; self._key=render_key; self.now=now

    def observe(self, *, active=False):
        p=self.permit; start=self.now(); p.validate(start)
        hashes={n:hashlib.sha256((self.directory/n).read_bytes()).hexdigest() for n in REQUIRED_FILES}
        need(hashes==dict(p.files) and source_hash(self.directory)==p.source_hash,'REHEARSAL_FILES_CHANGED')
        services=self.render.inventory(); isolation(services,active=active)
        deployed=self.render.deployment(p)
        need(deployed=={'id':p.deployment,'commit':p.commit,'source_hash':p.source_hash,
             'service':SERVICE,'url':URL,'status':'live'},'REHEARSAL_DEPLOYMENT')
        status=self.project_status(); masters=self.masters(); callers=self.callers(); data=self.database.collect()
        for row in (status,masters,callers,data): fresh(row['checked_at'],self.now(),120)
        need(status['id']==DATABASE and status['status']=='ACTIVE_HEALTHY','REHEARSAL_DATABASE')
        need(masters['revisions']==dict(p.masters),'REHEARSAL_MASTER_CHANGED')
        need(callers['active_schedules']==[] and callers['conflicting_process_ids']==[]
             and data['active_pg_cron']==[] and data['other_active_session_ids']==[],'REHEARSAL_CALLER')
        need(data['schema_sha256']==p.schema_hash,'REHEARSAL_SCHEMA')
        key=f'STRATEGY_1|{p.day.isoformat()}|PREMARKET|v0.3|INFRASTRUCTURE_TEST'
        if data.get('kind')==KIND:
            need(data['run_key']==key and data['matching_run_count']==0 and data['unfinished_run_count']==0,
                 'REHEARSAL_EXISTING_RUN')
        else:
            need(not any(r.get('status')=='IN_PROGRESS' or r.get('run_key')==key for r in data['snapshot']['runs']),
                 'REHEARSAL_EXISTING_RUN')
        fresh(start.isoformat(),self.now(),120)
        return data

    def start_watchdog(self, nonce):
        p=self.permit
        self.watchdog.start({'mode':'render_rehearsal','nonce':nonce,'policy_hash':p.fingerprint,
                             'policy':p.as_dict(),'render_key':self._key})
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            try:
                receipt=self.watchdog.receipt()
                need(receipt['mode']=='render_rehearsal' and receipt['service']==SERVICE
                     and receipt['nonce']==nonce and receipt['policy_hash']==p.fingerprint
                     and timestamp(receipt['suspend_at'])==p.suspend_at
                     and timestamp(receipt['verify_by'])==p.verify_by,'REHEARSAL_WATCHDOG')
                return receipt
            except FileNotFoundError: time.sleep(0.1)
        raise RuntimeError('REHEARSAL_WATCHDOG_TIMEOUT')

    def probe(self):
        p=self.permit; data=self.runtime.probe()
        fresh(data['checked_at'],self.now(),30)
        need(data['commit']==p.commit and data['source_hash']==p.source_hash and data['database_id']==DATABASE
             and data['session_date']==p.day.isoformat(),'REHEARSAL_RUNTIME_IDENTITY')
        need(data['scope']=='NORMAL_COORDINATOR_NO_SCAN' and data['scan_enabled'] is False
             and data['mode']=='SHADOW' and all(data[k] is False for k in
                 ('broker_execution_enabled','qualification_enabled','journal_enabled','strategy_evidence_eligible')),
             'REHEARSAL_RUNTIME_SAFETY')
        need(data['authenticated_probes']=={k:'AUTHENTICATED_READ_ONLY' for k in
            ('paper_calendar','sip','historical_sip','staging_database')},'REHEARSAL_AUTHENTICATION')
        return data

    def watchdog_result(self, nonce):
        data=self.watchdog.result()
        need(data['nonce']==nonce and data['mode']=='render_rehearsal' and data['suspended'] is True
             and timestamp(data['suspend_at'])==self.permit.suspend_at
             and timestamp(data['verify_by'])==self.permit.verify_by
             and self.permit.suspend_at<=timestamp(data['checked_at'])<=self.permit.verify_by,
             'REHEARSAL_WATCHDOG_RESULT')
        return data


def rehearse(permit, *, connections, evidence_directory, now, monotonic=time.monotonic, sleep=time.sleep):
    """One bounded attempt; deliberately no scan method, POST intent or retries.

    DB restoration is an explicit prerequisite, outside this engine. Cleanup
    checks still run after ambiguous activation and failed readback.
    """
    root=Path(evidence_directory).resolve()
    need(root.is_dir(),'REHEARSAL_EVIDENCE_DIRECTORY')
    prefix=digest({'scope':'NORMAL_COORDINATOR_NO_SCAN','day':permit.day.isoformat(),'service':SERVICE})
    result={'scope':'NORMAL_COORDINATOR_NO_SCAN','acceptance_posts':0,'status':'NOT_STARTED',
            'authentication':'NOT_VERIFIED','database_unchanged':False,'cleanup':'NOT_VERIFIED',
            'watchdog_suspension':'NOT_VERIFIED','strategy_evidence_eligible':False,'armed':False,
            'session_date':permit.day.isoformat(),'commit':permit.commit,'source_hash':permit.source_hash,
            'deployment':permit.deployment,'permit_hash':permit.fingerprint,'started_at':now().isoformat(),
            'notification_delivery':'NOT_TESTED_NO_MESSAGES_SENT'}
    nonce=uuid.uuid4().hex; owns=False; baseline=None; began=monotonic(); wall=now(); watchdog_started=False
    result['diagnostics']=[]
    def step(phase, operation):
        started=monotonic()
        try:
            value=operation()
        except Exception as exc:
            result['diagnostics'].append({'phase':phase, **error_diagnostic(exc,elapsed=monotonic()-started)})
            if type(exc) is AdapterError and exc.provider_steps:
                result['provider_diagnostics']=safe_steps(exc.provider_steps)
            result.setdefault('failure_phase',phase)
            raise
        else:
            result['diagnostics'].append({'phase':phase,'error':'OK','http_status':None,
                                          'elapsed_seconds':round(monotonic()-started,3)})
            return value
        finally:
            result['diagnostics']=result['diagnostics'][-64:]
    def startup_budget(seconds):
        need(abs((now()-wall).total_seconds()-(monotonic()-began))<=5,'REHEARSAL_CLOCK_DRIFT')
        need((permit.suspend_at-now()).total_seconds()>seconds,'REHEARSAL_STARTUP_BUDGET')
    try:
        need(connections.permit==permit,'REHEARSAL_CONNECTION_PERMIT')
        permit.validate(now())
        need(permit.not_before<=now()<permit.not_before+timedelta(seconds=30),'REHEARSAL_START_WINDOW')
        consume(root/(prefix+'.attempt.json'),{'scope':result['scope'],'permit_hash':permit.fingerprint,'at':now().isoformat()})
        owns=True
        data=step('observe',connections.observe); baseline=preservation_baseline(data)
        consume(root/(prefix+'.baseline.json'),{'baseline':baseline,'evidence':data})
        need(now()<permit.suspend_at-timedelta(seconds=30),'REHEARSAL_PREPARATION_LATE')
        # Resume has two HTTP operations (up to 5+20 seconds each).
        # Reserve 10s minimum readiness, 5+25s probe and 10s safety margin.
        step('validation',lambda:startup_budget(100))
        watchdog_started=True
        receipt=step('watchdog_start',lambda:connections.start_watchdog(nonce))
        need(receipt['pid']!=os.getpid(),'REHEARSAL_WATCHDOG_INDEPENDENCE')
        consume(root/(prefix+'.watchdog-ready.json'),receipt)
        step('validation',lambda:startup_budget(100))
        step('resume',lambda:connections.render.resume(SERVICE))
        step('validation',lambda:startup_budget(50))
        deadline=min(now()+timedelta(seconds=READINESS_MAX_SECONDS),
                     permit.suspend_at-timedelta(seconds=AUTHENTICATION_RESERVE_SECONDS))
        result['readiness']=step('readiness',lambda:connections.runtime.wait_ready(
            deadline=deadline,now=now,monotonic=monotonic,sleep=sleep))
        step('validation',lambda:startup_budget(AUTHENTICATION_RESERVE_SECONDS))
        runtime=step('authentication',connections.probe)
        need(now()<permit.suspend_at,'REHEARSAL_PROBE_LATE')
        result['authentication']='PASS'
        result['provider_diagnostics']=safe_steps(runtime.get('diagnostics'))
        consume(root/(prefix+'.runtime.json'),runtime)
        # Let the independent watchdog perform the suspension. Parent does not
        # suspend before its deadline unless a failure requires early cleanup.
        while now()<permit.suspend_at:
            need(abs((now()-wall).total_seconds()-(monotonic()-began))<=5,'REHEARSAL_CLOCK_DRIFT')
            need(monotonic()-began<8*60,'REHEARSAL_BUDGET')
            sleep(min(1,(permit.suspend_at-now()).total_seconds()))
        # Reserve time for complete DB readback and asynchronous database pause.
        # Missing evidence cannot consume the entire overall cleanup budget.
        proof_deadline=min(permit.suspend_at+timedelta(seconds=30),permit.verify_by-timedelta(minutes=4))
        while now()<proof_deadline:
            try:
                proof=connections.watchdog_result(nonce)
            except FileNotFoundError:
                # Only a not-yet-written result is pending. A present but
                # invalid receipt is terminal and needs immediate cleanup.
                need(monotonic()-began<8*60,'REHEARSAL_BUDGET')
                sleep(1)
            else:
                services=connections.render.inventory(); isolation(services)
                consume(root/(prefix+'.watchdog-result.json'),proof)
                result['watchdog_suspension']='PROVIDER_READBACK_WITHOUT_PARENT_SUSPEND'
                break
        need(result['watchdog_suspension']!='NOT_VERIFIED','REHEARSAL_WATCHDOG_NOT_VERIFIED')
        after=step('database_readback',connections.database.collect)
        need(after['schema_sha256']==permit.schema_hash and preservation_baseline(after)==baseline,
             'REHEARSAL_DATABASE_CHANGED')
        result['database_unchanged']=True
        consume(root/(prefix+'.readback.json'),after)
        result['status']='NO_SCAN_CHECKS_PASSED'
    except FileExistsError:
        result['status']='ATTEMPT_ALREADY_CONSUMED' if not owns else 'EVIDENCE_COLLISION_FAILED_CLOSED'
    except Exception:
        result['status']='REHEARSAL_FAILED_OR_AMBIGUOUS'
    finally:
        result['readiness_diagnostics']=safe_steps(getattr(connections.runtime,'readiness_steps',None))
        if owns:
            try:
                step('cleanup_suspend',lambda:connections.render.suspend(SERVICE))
            except Exception: pass
            try:
                rows=step('cleanup_inventory',connections.render.inventory); isolation(rows)
                # Preserve independent DB readback even on early failure, before pause.
                if baseline is not None and not result['database_unchanged']:
                    try:
                        after=step('cleanup_readback',connections.database.collect)
                        result['database_unchanged']=(after['schema_sha256']==permit.schema_hash
                            and preservation_baseline(after)==baseline)
                        consume(root/(prefix+'.failure-readback.json'),after)
                    except Exception: result['failure_readback']='UNVERIFIED'
                try: step('cleanup_pause',lambda:connections.pause_project(DATABASE))
                except Exception: pass
                # Supabase pause is asynchronous. Request it once, then poll
                # status only within the existing cleanup deadline/budget.
                while True:
                    try:
                        status=step('cleanup_status',connections.project_status); fresh(status['checked_at'],now(),30)
                        need(status['id']==DATABASE,'REHEARSAL_DB_CLEANUP')
                        if status['status']=='INACTIVE': break
                    except Exception:
                        pass
                    need(now()<permit.verify_by and monotonic()-began<8*60,'REHEARSAL_DB_CLEANUP')
                    sleep(min(5,(permit.verify_by-now()).total_seconds()))
                # Refresh service state after DB pause, not just before it.
                rows=connections.render.inventory(); isolation(rows)
                result['cleanup']='VERIFIED'; result['cleanup_by_deadline']=now()<=permit.verify_by
                if not result['cleanup_by_deadline']: result['status']='CLEANUP_DEADLINE_MISSED'
                consume(root/(prefix+'.cleanup.json'),{'services':rows,'database':status,'checked_at':now().isoformat()})
                if watchdog_started:
                    stopped=step('cleanup_watchdog',lambda:connections.watchdog.stop_after_cleanup(services=rows,
                        database={'id':DATABASE,'status':'INACTIVE'},checked_at=now().isoformat()))
                    need(stopped=={'nonce':nonce,'process_exited':True},'REHEARSAL_WATCHDOG_SHUTDOWN')
                    result['watchdog_shutdown']='VERIFIED'
            except Exception:
                result['status']='CLEANUP_OR_WATCHDOG_UNRESOLVED'
            result['finished_at']=now().isoformat()
            try: consume(root/(prefix+'.result.json'),result)
            except Exception: result['result_persistence']='FAILED_PRESERVE_EXISTING'
    return result


if __name__=='__main__':
    raise SystemExit('REHEARSAL_DISABLED_WITHOUT_REVIEWED_AUTHENTICATED_BINDINGS')
