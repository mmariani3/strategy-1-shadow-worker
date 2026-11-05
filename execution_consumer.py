import hmac, os
from datetime import datetime, timezone
from typing import Any

import requests
from fastapi import FastAPI, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

APP_VERSION = '0.2.0-shadow-execution'
EXECUTION_ENABLED = False  # Phase 1 boundary; environment overrides cannot enable submission.
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SECRET_KEY = os.getenv('SUPABASE_SECRET_KEY')
EXECUTOR_URL = os.getenv('EXECUTOR_URL','https://day-trading-paper-executor.onrender.com')
EXECUTOR_TOKEN = os.getenv('EXECUTOR_TOKEN')
SERVICE_TOKEN = os.getenv('EXECUTION_SERVICE_TOKEN')
ALLOWED_RULESET = os.getenv('RULESET_VERSION','v0.3')

app = FastAPI(title='Strategy #1 Execution Consumer', version=APP_VERSION,
              description='Phase-1 shadow execution consumer + lifecycle monitor. Broker submission is hard-disabled.')
bearer = HTTPBearer(auto_error=False)


def wait_for_dependency(
    base_url: str,
    name: str,
    *,
    attempts: int = 4,
    connect_timeout: int = 5,
    read_timeout: int = 45,
) -> None:
    """Wake/check a downstream Render service before a dependent call.

    Only GET /health is retried. This avoids blindly replaying side-effecting
    POST requests while still tolerating Render cold starts and transient
    network failures.
    """
    import time

    delays = (0, 2, 5, 10)
    last_error = "unknown dependency error"
    for attempt in range(attempts):
        if attempt:
            time.sleep(delays[min(attempt, len(delays) - 1)])
        try:
            r = requests.get(
                f"{base_url.rstrip('/')}/health",
                timeout=(connect_timeout, read_timeout),
            )
            if r.ok:
                return
            last_error = f"HTTP {r.status_code}: {r.text[:300]}"
        except requests.RequestException as exc:
            last_error = f"{type(exc).__name__}: {str(exc)[:300]}"
    raise HTTPException(
        status_code=503,
        detail=f"{name} unavailable after cold-start retries: {last_error}",
    )


def auth(c: HTTPAuthorizationCredentials|None):
    if not SERVICE_TOKEN:
        raise HTTPException(503,'EXECUTION_SERVICE_TOKEN is not configured.')
    if c is None or c.scheme.lower() != 'bearer':
        raise HTTPException(401,'Missing bearer token.')
    if not hmac.compare_digest(c.credentials, SERVICE_TOKEN):
        raise HTTPException(403,'Invalid bearer token.')


def sb_headers(prefer=True):
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        raise HTTPException(503,'Supabase server credentials are not configured.')
    h={'apikey':SUPABASE_SECRET_KEY,'Content-Type':'application/json'}
    if prefer: h['Prefer']='return=representation'
    return h


def sb_get(table:str, params:dict[str,str]):
    r=requests.get(f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table}", headers=sb_headers(False), params=params, timeout=15)
    if not r.ok: raise HTTPException(502,f'Supabase query failed: {r.status_code} {r.text[:400]}')
    return r.json()


def sb_post(table:str, row:dict[str,Any]):
    r=requests.post(f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table}", headers=sb_headers(True), json=row, timeout=15)
    if not r.ok: raise HTTPException(502,f'Supabase insert failed: {r.status_code} {r.text[:400]}')
    return r.json()


def sb_patch(table:str, filters:dict[str,str], row:dict[str,Any]):
    params={k:f'eq.{v}' for k,v in filters.items()}
    r=requests.patch(f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table}", headers=sb_headers(True), params=params, json=row, timeout=15)
    if not r.ok: raise HTTPException(502,f'Supabase update failed: {r.status_code} {r.text[:400]}')
    return r.json()


def build_payload(s:dict[str,Any]):
    required=['symbol','direction','qty','entry_price','stop_price','target_price','triggered_at','decision','ruleset_version','entry_model','market_data_source','journal_trade_id']
    missing=[k for k in required if s.get(k) in (None,'')]
    if missing: return None, missing
    return {k:s.get(k) for k in required}, []


@app.get('/health')
def health():
    return {'ok':True,'mode':'CONTROLLED_PAPER' if EXECUTION_ENABLED else 'SHADOW', 'version':APP_VERSION,
            'ruleset_version':ALLOWED_RULESET,'broker_execution_enabled':EXECUTION_ENABLED}


@app.post('/consume/run-once')
def consume(c:HTTPAuthorizationCredentials|None=Security(bearer)):
    auth(c)
    # Only evaluate deterministic TRADE signals. In Phase 1, record WOULD_SUBMIT and never call executor.
    rows=sb_get('strategy_signals',{
        'select':'*',
        'decision':'eq.TRADE',
        'status':'eq.SHADOW',
        'ruleset_version':f'eq.{ALLOWED_RULESET}',
        'order':'created_at.asc',
        'limit':'50'
    })
    out=[]
    for s in rows:
        # skip already audited signal ids
        seen=sb_get('execution_shadow_audit',{'select':'id,status','signal_id':f"eq.{s['id']}",'limit':'1'})
        if seen:
            out.append({'signal_id':s['id'],'result':'DUPLICATE_SKIPPED','audit_status':seen[0]['status']})
            continue
        payload,missing=build_payload(s)
        if missing:
            audit=sb_post('execution_shadow_audit',{
                'signal_id':s['id'],'journal_trade_id':s.get('journal_trade_id'),'mode':'SHADOW',
                'action':'VALIDATION_FAILED','status':'ERROR','error':'Missing executable fields: '+', '.join(missing),
                'metadata':{'ruleset_version':s.get('ruleset_version')}
            })[0]
            out.append({'signal_id':s['id'],'result':'FAIL_CLOSED','missing':missing,'audit_id':audit['id']})
            continue
        audit_row={'signal_id':s['id'],'journal_trade_id':s.get('journal_trade_id'),
                   'mode':'CONTROLLED_PAPER' if EXECUTION_ENABLED else 'SHADOW',
                   'action':'SUBMIT' if EXECUTION_ENABLED else 'WOULD_SUBMIT','status':'WOULD_SUBMIT',
                   'executor_url':EXECUTOR_URL,'executor_payload':payload,
                   'metadata':{'consumer_version':APP_VERSION,'ruleset_version':ALLOWED_RULESET}}
        audit=sb_post('execution_shadow_audit',audit_row)[0]
        if not EXECUTION_ENABLED:
            out.append({'signal_id':s['id'],'result':'WOULD_SUBMIT','audit_id':audit['id'],'broker_called':False})
            continue
        if not EXECUTOR_TOKEN:
            sb_patch('execution_shadow_audit',{'id':audit['id']},{'status':'ERROR','error':'EXECUTOR_TOKEN missing'})
            out.append({'signal_id':s['id'],'result':'FAIL_CLOSED','reason':'EXECUTOR_TOKEN missing'})
            continue
        wait_for_dependency(
            EXECUTOR_URL,
            "Paper Executor",
        )
        try:
            r=requests.post(
                f"{EXECUTOR_URL.rstrip('/')}/paper/bracket",
                headers={
                    'Authorization':f'Bearer {EXECUTOR_TOKEN}',
                    'Content-Type':'application/json'
                },
                json=payload,
                timeout=(5,45),
            )
        except requests.RequestException as exc:
            sb_patch(
                'execution_shadow_audit',
                {'id':audit['id']},
                {
                    'status':'ERROR',
                    'error':(
                        'Executor submission transport failure after health check: '
                        + f'{type(exc).__name__}: {str(exc)[:300]}'
                    )
                }
            )
            out.append({
                'signal_id':s['id'],
                'result':'FAIL_CLOSED_TRANSPORT',
            })
            continue
        if not r.ok:
            sb_patch('execution_shadow_audit',{'id':audit['id']},{'status':'ERROR','error':f'{r.status_code} {r.text[:500]}'})
            out.append({'signal_id':s['id'],'result':'EXECUTOR_ERROR','status_code':r.status_code})
            continue
        resp=r.json(); oid=resp.get('id') or resp.get('order_id') or resp.get('alpaca_order_id')
        sb_patch('execution_shadow_audit',{'id':audit['id']},{'status':'SUBMITTED','executor_response':resp,'alpaca_order_id':oid,'submitted_at':datetime.now(timezone.utc).isoformat()})
        sb_patch('strategy_signals',{'id':s['id']},{'status':'SUBMITTED','alpaca_order_id':oid,'executor_response':resp,'execution_status':'SUBMITTED'})
        out.append({'signal_id':s['id'],'result':'SUBMITTED','alpaca_order_id':oid})
    return {'mode':'CONTROLLED_PAPER' if EXECUTION_ENABLED else 'SHADOW','broker_execution_enabled':EXECUTION_ENABLED,'checked':len(rows),'results':out}


@app.post('/monitor/run-once')
def monitor(c:HTTPAuthorizationCredentials|None=Security(bearer)):
    auth(c)
    active=sb_get('execution_shadow_audit',{
        'select':'*',
        'status':'in.(SUBMITTED,PARTIALLY_FILLED,FILLED)',
        'order':'created_at.asc',
        'limit':'50'
    })
    out=[]
    for a in active:
        oid=a.get('alpaca_order_id')
        if not oid:
            out.append({'audit_id':a['id'],'result':'NO_ORDER_ID'})
            continue
        if not EXECUTOR_TOKEN:
            out.append({'audit_id':a['id'],'result':'FAIL_CLOSED','reason':'EXECUTOR_TOKEN missing'})
            continue
        wait_for_dependency(
            EXECUTOR_URL,
            "Paper Executor",
        )
        try:
            r=requests.get(
                f"{EXECUTOR_URL.rstrip('/')}/paper/order/{oid}",
                headers={'Authorization':f'Bearer {EXECUTOR_TOKEN}'},
                timeout=(5,45),
            )
        except requests.RequestException as exc:
            out.append({
                'audit_id':a['id'],
                'result':'FAIL_CLOSED_TRANSPORT',
                'detail':f'{type(exc).__name__}: {str(exc)[:300]}',
            })
            continue
        if not r.ok:
            sb_patch('execution_shadow_audit',{'id':a['id']},{'status':'ERROR','error':f'{r.status_code} {r.text[:500]}'})
            out.append({'audit_id':a['id'],'result':'EXECUTOR_ERROR','status_code':r.status_code})
            continue
        resp=r.json()
        parent=(resp.get('status') or resp.get('parent_status') or '').upper()
        filled_qty=resp.get('filled_qty'); avg=resp.get('filled_avg_price')
        # Preserve raw executor response; avoid guessing leg semantics if response shape changes.
        new_status='FILLED' if parent=='FILLED' else ('CANCELLED' if parent=='CANCELED' or parent=='CANCELLED' else 'SUBMITTED')
        sb_patch('execution_shadow_audit',{'id':a['id']},{'status':new_status,'parent_status':parent or None,'filled_qty':filled_qty,'filled_avg_price':avg,'executor_response':resp})
        if a.get('signal_id'):
            sb_patch('strategy_signals',{'id':a['signal_id']},{'execution_status':new_status,'executor_response':resp})
        out.append({'audit_id':a['id'],'result':new_status,'parent_status':parent})
    return {'mode':'CONTROLLED_PAPER' if EXECUTION_ENABLED else 'SHADOW','broker_execution_enabled':EXECUTION_ENABLED,'checked':len(active),'results':out}
