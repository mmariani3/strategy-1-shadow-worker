"""Separate-process suspension watchdog. Secrets arrive only over stdin.

Only --child accepts a private launch envelope. Offline mode changes an explicitly
named local fake-provider file; it can never construct an HTTP client. Render mode
has suspension-only authority and no credential loader or inherited environment.
Do not launch Render mode without a separately authorized dated rehearsal/run.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

SERVICE="srv-dal8abbl550s73cj3jm0"


def atomic(path,data):
    temporary=path.with_suffix('.pending')
    with temporary.open('w',encoding='utf-8') as handle:
        json.dump(data,handle,sort_keys=True)
        handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary,path)


def child(envelope):
    # Fixed constants validated before any file write, client construction or call.
    if envelope['service']!=SERVICE or not re.fullmatch('[a-f0-9]{32}',envelope['nonce']):
        raise ValueError('WATCHDOG_SCOPE')
    if not re.fullmatch('[a-f0-9]{64}',envelope['policy_hash']): raise ValueError('WATCHDOG_POLICY')
    source_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if envelope['program_sha256']!=source_hash: raise ValueError('WATCHDOG_PROGRAM')
    root=Path(envelope['directory']).resolve()
    if not root.is_dir(): raise ValueError('WATCHDOG_DIRECTORY')
    prefix=root/envelope['nonce']
    ready=prefix.with_suffix('.watchdog-ready.json')
    result=prefix.with_suffix('.watchdog-result.json')
    mode=envelope['mode']
    started=time.monotonic()
    now=lambda:datetime.now(timezone.utc)
    if mode=='offline':
        delay=float(envelope['delay_seconds'])
        if not 0.1<=delay<=5: raise ValueError('OFFLINE_BOUND')
        cutoff=started+delay; finish=cutoff+2
        deadline=datetime.fromtimestamp(now().timestamp()+delay,timezone.utc)
        verify_by=datetime.fromtimestamp(deadline.timestamp()+2,timezone.utc)
        state_path=prefix.with_suffix('.offline-provider.json')
        if not state_path.is_file(): raise ValueError('OFFLINE_PROVIDER_MISSING')
        def suspend():
            state=json.loads(state_path.read_text())
            if state['service']!=SERVICE: raise ValueError('OFFLINE_SERVICE')
            if state.get('failures_remaining',0):
                state['failures_remaining']-=1
                atomic(state_path,state)
                return False
            state['suspended']=True
            atomic(state_path,state)
            return json.loads(state_path.read_text())['suspended'] is True
        pause=0.05
    elif mode in {'render','render_rehearsal'}:
        # imports/client never execute in the offline child.
        from coordinator_launch_guard import Policy, timestamp
        from coordinator_service_adapters import RenderAdapter
        import requests
        from datetime import date
        p=dict(envelope['policy'])
        if mode=='render_rehearsal':
            from coordinator_rehearsal_binding import RehearsalPermit
            policy=RehearsalPermit.parse(p)
        else:
            p['day']=date.fromisoformat(p['day']); p['authorized_until']=timestamp(p['authorized_until'])
            p['files']=tuple(tuple(v) for v in p['files']); p['masters']=tuple(tuple(v) for v in p['masters'])
            policy=Policy(**p)
        policy.validate(now())
        if policy.fingerprint!=envelope['policy_hash']: raise ValueError('WATCHDOG_POLICY_BINDING')
        for filename,expected in policy.files:
            if hashlib.sha256(Path(__file__).with_name(filename).read_bytes()).hexdigest()!=expected:
                raise ValueError('WATCHDOG_PACKAGE_CHANGED')
        if mode=='render_rehearsal':
            if not policy.not_before<=now()<policy.suspend_at: raise ValueError('WATCHDOG_START_WINDOW')
            deadline=policy.suspend_at; verify_by=policy.verify_by
        else:
            if not policy.at(5,40)<=now()<policy.at(5,50): raise ValueError('WATCHDOG_START_WINDOW')
            deadline=policy.at(6,20); verify_by=policy.at(6,25)
        cutoff=started+max(0,(deadline-now()).total_seconds())
        finish=started+max(0,(verify_by-now()).total_seconds())
        adapter=RenderAdapter(session=requests.Session(),token=envelope['render_key'],
                              expires_at=verify_by,suspend_only=True)
        # Actual authenticated identity check before readiness; never return body.
        adapter.target()
        suspend=lambda:adapter.suspend(SERVICE)
        pause=1
    else:
        raise ValueError('WATCHDOG_MODE')
    common={'pid':os.getpid(),'nonce':envelope['nonce'],'policy_hash':envelope['policy_hash'],
        'service':SERVICE,'program_sha256':source_hash,'mode':mode,
        'suspend_at':deadline.isoformat(),'verify_by':verify_by.isoformat()}
    # Bind both clocks AFTER source verification and authenticated setup. Using
    # the process-start monotonic value with a later wall time subtracts setup
    # latency twice and can suspend before the authorized wall-clock deadline.
    anchor=time.monotonic()
    cutoff=anchor+max(0,(deadline-now()).total_seconds())
    finish=anchor+max(0,(verify_by-now()).total_seconds())
    # Wall time is the admission boundary. Monotonic time bounds a backward
    # clock jump; crossing that bound suspends for safety, but cannot satisfy
    # the parent's timestamp acceptance check while wall time is still early.
    while now()<deadline and time.monotonic()<cutoff+5:
        atomic(ready,{**common,'heartbeat_at':now().isoformat()})
        # No caller-created stop file can disable the cleanup deadline. Parent
        # may terminate using its process handle only after verified cleanup.
        time.sleep(min(pause,max(.001,(deadline-now()).total_seconds())))
    suspended=False; attempts=0
    while time.monotonic()<finish and now()<verify_by and attempts<6:
        attempts+=1
        try: suspended=suspend()
        except Exception: suspended=False
        if suspended: break
        time.sleep(min(0.1 if mode=='offline' else 10,max(0,finish-time.monotonic())))
    atomic(result,{**common,'checked_at':now().isoformat(),'suspended':suspended,'attempts':attempts,
        'scope':'STAGING_SERVICE_ONLY_DATABASE_CLEANUP_REQUIRES_CONTROLLER'})
    return 0 if suspended else 2


if __name__=='__main__':
    if sys.argv[1:]!=['--child']: raise SystemExit('WATCHDOG_REQUIRES_PRIVATE_LAUNCH_ENVELOPE')
    try:
        raw=sys.stdin.buffer.readline(1024*1024+1)
        if len(raw)>1024*1024: raise ValueError('WATCHDOG_ENVELOPE_LIMIT')
        raise SystemExit(child(json.loads(raw)))
    except Exception:
        # Do not print exception text or the envelope; it may contain credentials.
        raise SystemExit('WATCHDOG_FAILED_CLOSED') from None
