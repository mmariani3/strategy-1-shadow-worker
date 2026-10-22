"""Read-only, fixed-target authentication probes. No scan or write capability.

Constructors require explicit inputs. Only the separately invoked rehearsal app
factory reads its deployed environment; importing this module does not do so.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, time as daytime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
import hashlib
import hmac
import json
import math
import re
import threading
import time

from fastapi import HTTPException
from coordinator_launch_guard import SERVICE, DATABASE, PACIFIC, REQUIRED_FILES, need, timestamp
from setup_evidence import digest
from coordinator_service_adapters import safe_steps, error_diagnostic

DB_URL='https://'+DATABASE+'.supabase.co'
CALENDAR='https://paper-api.alpaca.markets/v2/calendar'
QUOTES='https://data.alpaca.markets/v2/stocks/quotes/latest'
BARS='https://data.alpaca.markets/v2/stocks/bars'
DB_READ=DB_URL+'/rest/v1/strategy_discovery_runs'
START_COMMAND='uvicorn coordinator_acceptance_app:create_rehearsal_app --factory --host 0.0.0.0 --port $PORT'


class PreflightFailure(HTTPException):
    def __init__(self, diagnostics):
        super().__init__(503, 'AUTHENTICATED_PREFLIGHT_UNVERIFIED')
        self.diagnostics = safe_steps(diagnostics)


def source_hash(directory):
    root=Path(directory)
    return digest({name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in sorted(REQUIRED_FILES)})


@dataclass(frozen=True)
class ProbePermit:
    day: date
    commit: str
    source_hash: str
    not_before: datetime
    expires_at: datetime

    def validate(self, now):
        need(now.tzinfo is not None and now.astimezone(PACIFIC).date()==self.day,'PROBE_DATE')
        need(self.not_before.tzinfo is not None and self.expires_at.tzinfo is not None
             and self.not_before<=now<self.expires_at
             and timedelta(0)<self.expires_at-self.not_before<=timedelta(minutes=15)
             and self.not_before.astimezone(PACIFIC).date()==self.day
             and self.expires_at.astimezone(PACIFIC).date()==self.day,'PROBE_WINDOW')
        need(bool(re.fullmatch('[a-f0-9]{40}',self.commit)) and
             bool(re.fullmatch('[a-f0-9]{64}',self.source_hash)),'PROBE_CODE')


@dataclass(frozen=True, repr=False)
class Credentials:
    incoming_token: str=field(repr=False)
    alpaca_key: str=field(repr=False)
    alpaca_secret: str=field(repr=False)
    database_key: str=field(repr=False)


class ReadOnlyProbes:
    def __init__(self, *, permit, credentials, session, directory, identity, now=None, monotonic=None):
        self.permit=permit; self.credentials=credentials; self.session=session
        self.directory=Path(directory); self.identity=identity
        self.now=now or (lambda:datetime.now(timezone.utc)); self.clock=monotonic or time.monotonic
        self.lock=threading.Lock()
        session.trust_env=False; session.auth=None; session.headers.clear(); session.cookies.clear()
        for adapter in getattr(session,'adapters',{}).values():
            need(adapter.max_retries.total==0 and adapter.max_retries.redirect in (None,0),'PROBE_RETRIES')

    def guard(self):
        self.permit.validate(self.now())
        need(self.identity()=={'service':SERVICE,'database_url':DB_URL,'ruleset':'v0.3',
                              'commit':self.permit.commit},'PROBE_RUNTIME_IDENTITY')
        need(source_hash(self.directory)==self.permit.source_hash,'PROBE_RUNTIME_SOURCE')
        need(all(isinstance(v,str) and v for v in (self.credentials.incoming_token,
             self.credentials.alpaca_key,self.credentials.alpaca_secret,self.credentials.database_key)),
             'PROBE_CREDENTIALS_UNAVAILABLE')

    def get(self, url, params, deadline):
        need(url in {CALENDAR,QUOTES,BARS,DB_READ},'PROBE_TARGET')
        self.permit.validate(self.now())
        remaining=min(5,deadline-self.clock(),(self.permit.expires_at-self.now()).total_seconds())
        need(remaining>0,'PROBE_BUDGET')
        c=self.credentials
        headers={'Accept':'application/json'}
        if url==DB_READ:
            headers['apikey']=c.database_key
            if c.database_key.count('.')==2: headers['Authorization']='Bearer '+c.database_key
        else:
            headers.update({'APCA-API-KEY-ID':c.alpaca_key,'APCA-API-SECRET-KEY':c.alpaca_secret})
        response=None
        try:
            response=self.session.request('GET',url,params=params,headers=headers,
                timeout=(min(2,remaining),remaining),allow_redirects=False,stream=True)
            self._probe_status=response.status_code
            need(response.status_code==200,'PROBE_RESPONSE')
            raw=bytearray()
            for chunk in response.iter_content(16384):
                need(self.clock()<deadline and self.now()<self.permit.expires_at,'PROBE_DEADLINE')
                need(isinstance(chunk,bytes) and len(raw)+len(chunk)<=256*1024,'PROBE_SIZE')
                raw.extend(chunk)
            need(self.clock()<deadline and self.now()<self.permit.expires_at,'PROBE_DEADLINE')
            return json.loads(raw)
        finally:
            if response is not None: response.close()

    def check(self, authorization):
        token=self.credentials.incoming_token
        if not token or not isinstance(authorization,str) or not hmac.compare_digest(authorization.encode(),('Bearer '+token).encode()):
            raise HTTPException(401,'AUTHENTICATION_REQUIRED')
        if not self.lock.acquire(blocking=False): raise HTTPException(409,'PREFLIGHT_ALREADY_RUNNING')
        diagnostics=[]; phase='guard'; step_start=self.clock(); self._probe_status=None
        def completed():
            diagnostics.append({'phase':phase,'error':'OK','http_status':self._probe_status,
                                'elapsed_seconds':self.clock()-step_start})
        try:
            self.guard()
            completed()
            started=self.now(); deadline=self.clock()+20; day=self.permit.day
            phase='paper_calendar'; step_start=self.clock(); self._probe_status=None
            rows=self.get(CALENDAR,{'start':(day-timedelta(days=30)).isoformat(),'end':day.isoformat()},deadline)
            need(isinstance(rows,list) and 1<len(rows)<=31,'CALENDAR_UNAVAILABLE')
            dates=[date.fromisoformat(row['date']) for row in rows]
            need(len(set(dates))==len(dates) and day in dates and
                 all(day-timedelta(days=30)<=d<=day for d in dates),'CALENDAR_DATES')
            today=rows[dates.index(day)]
            need(today['open']=='09:30' and today['close']=='16:00','NONSTANDARD_SESSION')
            prior=max(d for d in dates if d<day)
            eastern=ZoneInfo('America/New_York')
            completed()
            phase='sip'; step_start=self.clock(); self._probe_status=None
            quotes=self.get(QUOTES,{'symbols':'SPY','feed':'sip'},deadline)
            quote=quotes['quotes']['SPY']
            timestamp(quote['t'])
            need(all(type(quote[k]) in (int,float) and math.isfinite(quote[k]) and quote[k]>=0
                     for k in ('bp','ap')),'SIP_QUOTE_SHAPE')
            completed()
            phase='historical_sip'; step_start=self.clock(); self._probe_status=None
            bars=self.get(BARS,{'symbols':'SPY','timeframe':'1Day',
                'start':datetime.combine(prior,daytime.min,tzinfo=eastern).isoformat(),
                'end':datetime.combine(prior,daytime(23,59,59),tzinfo=eastern).isoformat(),
                'feed':'sip','adjustment':'raw','limit':2,'sort':'asc'},deadline)
            need(bars.get('next_page_token') is None and len(bars['bars']['SPY'])==1,'HISTORICAL_INCOMPLETE')
            bar=bars['bars']['SPY'][0]
            need(timestamp(bar['t']).astimezone(eastern).date()==prior
                 and type(bar['c']) in (int,float) and math.isfinite(bar['c']) and bar['c']>0,'HISTORICAL_DATE')
            completed()
            phase='staging_database'; step_start=self.clock(); self._probe_status=None
            records=self.get(DB_READ,{'select':'id','limit':'1'},deadline)
            need(isinstance(records,list) and len(records)<=1 and
                 all(set(r)=={'id'} and isinstance(r['id'],str) for r in records),'DATABASE_READ_SHAPE')
            completed()
            phase='validation'; step_start=self.clock(); self._probe_status=None
            self.guard()
            need(self.clock()<deadline,'PROBE_DEADLINE')
            completed()
            return {'checked_at':started.isoformat(),'commit':self.permit.commit,'source_hash':self.permit.source_hash,
                'session_date':day.isoformat(),'database_id':DATABASE,'mode':'SHADOW',
                'broker_execution_enabled':False,'qualification_enabled':False,'journal_enabled':False,
                'strategy_evidence_eligible':False,'scan_enabled':False,'scope':'NORMAL_COORDINATOR_NO_SCAN',
                'authenticated_probes':{k:'AUTHENTICATED_READ_ONLY' for k in
                    ('paper_calendar','sip','historical_sip','staging_database')},
                'historical_prior_session':prior.isoformat(),'reference_price_approved':False,
                'diagnostics':safe_steps(diagnostics),
                'database_read_scope':'ONE_ROW_ACCESS_ONLY_NOT_SCHEMA_OR_INTEGRITY_ACCEPTANCE'}
        except Exception as exc:
            diagnostics.append({'phase':phase, **error_diagnostic(exc,status=self._probe_status,
                                elapsed=self.clock()-step_start)})
            raise PreflightFailure(diagnostics) from None
        finally:
            self.lock.release()


def from_deployed_environment(environ, *, directory, session):
    """Explicit factory only. The manifest is NOT created or installed here."""
    try:
        path=Path(environ['COORDINATOR_REHEARSAL_MANIFEST'])
        need(path.is_absolute() and path.stat().st_size<=16384,'REHEARSAL_MANIFEST')
        data=json.loads(path.read_text())
        need(set(data)=={'scope','session_date','commit','source_hash','not_before','expires_at'}
             and data['scope']=='NORMAL_COORDINATOR_NO_SCAN','REHEARSAL_MANIFEST_SCOPE')
        permit=ProbePermit(date.fromisoformat(data['session_date']),data['commit'],data['source_hash'],
                           timestamp(data['not_before']),timestamp(data['expires_at']))
        credentials=Credentials(*(environ.get(k,'') for k in
            ('DISCOVERY_SERVICE_TOKEN','ALPACA_API_KEY','ALPACA_API_SECRET','SUPABASE_SECRET_KEY')))
        def identity():
            return {'service':environ.get('RENDER_SERVICE_ID'),'database_url':environ.get('SUPABASE_URL'),
                    'ruleset':environ.get('RULESET_VERSION'),'commit':environ.get('RENDER_GIT_COMMIT')}
        return ReadOnlyProbes(permit=permit,credentials=credentials,session=session,directory=directory,identity=identity)
    except Exception:
        raise RuntimeError('REHEARSAL_CONFIGURATION_UNAVAILABLE') from None
