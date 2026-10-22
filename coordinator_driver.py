"""Bounded driver and independently launched watchdog process handle.

No default credentials, hosted permit or production launcher is installed.
"""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import time

from coordinator_launch_guard import SERVICE, need, isolation, fresh


class WatchdogProcess:
    def __init__(self, *, directory, program_sha256, python=sys.executable, now=None):
        self.directory=Path(directory).resolve()
        self.program=Path(__file__).with_name('coordinator_watchdog_process.py').resolve()
        self.expected=program_sha256
        self.python=python
        self.now=now or (lambda:datetime.now(timezone.utc))
        self.process=None; self.nonce=None; self.policy_hash=None

    def start(self,envelope):
        need(self.process is None and self.directory.is_dir(),'WATCHDOG_ALREADY_STARTED_OR_DIRECTORY')
        need(envelope.get('mode') in {'offline','render','render_rehearsal'} and
             isinstance(envelope.get('nonce'),str) and bool(re.fullmatch('[a-f0-9]{32}',envelope['nonce']))
             and isinstance(envelope.get('policy_hash'),str) and bool(re.fullmatch('[a-f0-9]{64}',envelope['policy_hash'])),
             'WATCHDOG_ENVELOPE_REJECTED')
        need(hashlib.sha256(self.program.read_bytes()).hexdigest()==self.expected,'WATCHDOG_PROGRAM_CHANGED')
        self.nonce=envelope['nonce']; self.policy_hash=envelope['policy_hash']
        payload={**envelope,'service':SERVICE,'directory':str(self.directory),'program_sha256':self.expected}
        try:
            encoded=(json.dumps(payload)+'\n').encode()
            need(len(encoded)<=1024*1024,'WATCHDOG_ENVELOPE_TOO_LARGE')
        except Exception:
            raise RuntimeError('WATCHDOG_ENVELOPE_REJECTED') from None
        # No secrets in argv, env, stdout or stderr. Windows child has no console.
        flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
        self.process=subprocess.Popen([self.python,str(self.program),'--child'],stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags,cwd=str(self.program.parent))
        try:
            self.process.stdin.write(encoded)
            self.process.stdin.flush(); self.process.stdin.close()
        except Exception:
            # An uncertain child may still be alive. Retain its handle and
            # require cleanup reconciliation rather than unconditionally killing it.
            raise RuntimeError('WATCHDOG_START_AMBIGUOUS') from None

    def receipt(self):
        need(self.process is not None and self.process.poll() is None,'WATCHDOG_NOT_RUNNING')
        data=json.loads((self.directory/(self.nonce+'.watchdog-ready.json')).read_text())
        need(data['pid']==self.process.pid and data['nonce']==self.nonce
             and data['policy_hash']==self.policy_hash and data['program_sha256']==self.expected,
             'WATCHDOG_PROCESS_IDENTITY')
        need(hashlib.sha256(self.program.read_bytes()).hexdigest()==self.expected,'WATCHDOG_PROGRAM_CHANGED')
        fresh(data['heartbeat_at'],self.now(),15)
        return data

    def stop_after_cleanup(self, *, services, database, checked_at):
        # Only the handle of the child created here is terminated, never an
        # arbitrary PID read from a file. Actual cleanup readbacks are mandatory.
        fresh(checked_at,self.now(),30)
        isolation(services)
        need(database=={'id':'cihwmameyylixouggwxk','status':'INACTIVE'},'WATCHDOG_CLEANUP_UNVERIFIED')
        need(self.process is not None,'WATCHDOG_NOT_OWNED')
        if self.process.poll() is None:
            self.process.terminate()
        self.process.wait(timeout=5)
        return {'nonce':self.nonce,'process_exited':self.process.poll() is not None}

    def result(self):
        need(self.process is not None,'WATCHDOG_NOT_OWNED')
        data=json.loads((self.directory/(self.nonce+'.watchdog-result.json')).read_text())
        need(data['pid']==self.process.pid and data['nonce']==self.nonce
             and data['policy_hash']==self.policy_hash and data['program_sha256']==self.expected
             and data['service']==SERVICE,'WATCHDOG_RESULT_IDENTITY')
        need(hashlib.sha256(self.program.read_bytes()).hexdigest()==self.expected,'WATCHDOG_PROGRAM_CHANGED')
        fresh(data['checked_at'],self.now(),120)
        return data


def drive(controller, *, monotonic=time.monotonic, sleep=time.sleep, poll_seconds=1):
    """Enforce wall/monotonic coherence and bounded polling; never restart."""
    need(0<poll_seconds<=2,'DRIVER_POLL_BOUND')
    wall_start=controller.clock(); tick_start=monotonic()
    report=controller.start()
    while controller.phase!='TERMINAL':
        wall=controller.clock(); elapsed=monotonic()-tick_start
        if abs((wall-wall_start).total_seconds()-elapsed)>5 or elapsed>45*60:
            return controller.stop('CLOCK_DRIFT_OR_DRIVER_BUDGET')
        report=controller.tick()
        if controller.phase!='TERMINAL': sleep(poll_seconds)
    return report


if __name__=='__main__':
    raise SystemExit('DRIVER_DISABLED_PENDING_REVIEWED_HOSTED_BINDING')
