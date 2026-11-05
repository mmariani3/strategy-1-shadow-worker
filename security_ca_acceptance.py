"""Staging-only, health-only acceptance adapter; no authority installed by import."""
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import socket
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request

import security_ca_build as build

SERVICE = "srv-dal8a2m7bikc73enjn5g"
SCOPE = "ONE_NORMAL_WORKER_CA_ACCEPTANCE"
VERSION = "normal-worker-ca-acceptance-v1"
ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "security_ca_acceptance_manifest.json"
TARGETS = ("https://render.com/", "https://dv-g3b-emudhra.we-have-a-problem.com/", "https://dv-g3b-aaa-emudhra.we-have-a-problem.com/")
OVERRIDES = frozenset({"REQUESTS_CA_BUNDLE","CURL_CA_BUNDLE","SSL_CERT_FILE","SSL_CERT_DIR","HTTP_PROXY","HTTPS_PROXY","ALL_PROXY","NO_PROXY","NETRC","PYTHONPATH","PYTHONHOME"})
BROKER_FIELDS = frozenset({"ALPACA_API_KEY","ALPACA_API_SECRET","APCA_API_KEY_ID","APCA_API_SECRET_KEY","ALPACA_SECRET_KEY"})


def now(): return datetime.now(timezone.utc)


def need(value, code):
    if not value: raise RuntimeError(code)


def timestamp(value):
    result = datetime.fromisoformat(value.replace("Z","+00:00"))
    need(result.tzinfo is not None,"TIMEZONE_REQUIRED")
    return result


def validate_manifest(data):
    need(data.get("schema")==VERSION and data.get("armed") is True and data.get("scope")==SCOPE,"UNARMED_MANIFEST")
    need(data.get("service")==SERVICE and re.fullmatch(r"[a-f0-9]{32}",data.get("authorization_id") or ""),"MANIFEST_IDENTITY")
    start,end = timestamp(data["starts_at"]),timestamp(data["expires_at"])
    need((end-start).total_seconds()==1200 and start<=now()<end,"RUNTIME_WINDOW")
    expected = {"main.py","review_contract.py","build_info.py","security_ca_build.py","security_ca_acceptance.py","requirements.txt"}
    need(set(data.get("source_files",{}))==expected,"SOURCE_SET")
    for name,digest in data["source_files"].items():
        need(not (ROOT/name).is_symlink() and hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,"RUNTIME_SOURCE_CHANGED")
    return start,end


def runtime_guard(data):
    start,end = validate_manifest(data)
    need(os.getenv("RENDER")=="true" and os.getenv("RENDER_SERVICE_ID")==SERVICE,"RUNTIME_TARGET")
    need(re.fullmatch(r"[a-f0-9]{40}",os.getenv("RENDER_GIT_COMMIT", "")),"RUNTIME_COMMIT")
    names = {name.upper() for name in os.environ}
    need(not names & BROKER_FIELDS,"BROKER_FIELD_PRESENT")
    # Reject names even if empty: do not silently mask a configured override.
    need(not names & OVERRIDES,"TRUST_OR_PROXY_OVERRIDE_PRESENT")
    need(os.getenv("SUPABASE_URL", "").rstrip("/")=="https://cihwmameyylixouggwxk.supabase.co","STAGING_IDENTITY")
    need("main" not in sys.modules,"APPLICATION_IMPORTED_EARLY")
    return start,end


def classify(request, url):
    need(url in TARGETS,"UNAPPROVED_TLS_TARGET")
    try:
        request(url)
        return "TLS_ACCEPTED"
    except ssl.SSLCertVerificationError:
        return "CERTIFICATE_REJECTED"
    except urllib.error.URLError as error:
        return "CERTIFICATE_REJECTED" if isinstance(error.reason,ssl.SSLCertVerificationError) else "INCONCLUSIVE"
    except Exception:
        return "INCONCLUSIVE"


def certificate_checks(end):
    # Exact direct versions and all three patched bundle checks are shared with
    # the already tested build module, in a fresh runtime interpreter.
    installed = build.installed_report()
    need(installed["application_imported"] is False,"APPLICATION_IMPORTED_EARLY")
    import requests
    session = requests.Session()
    session.headers.clear();session.cookies.clear();session.auth=None
    need(session.verify is True and session.trust_env is True,"DEFAULT_REQUESTS_TRUST")
    sent = []
    def request_get(url):
        # Prepare directly: Session.prepare_request can read ambient .netrc.
        # The session still resolves its actual default CA/proxy settings below.
        prepared = requests.Request("GET",url).prepare()
        need(not {k.lower() for k in prepared.headers} & {"authorization","proxy-authorization","cookie"},"AMBIENT_AUTH_REJECTED")
        settings = session.merge_environment_settings(url,{},True,None,None)
        need(settings.get("verify") is True and not settings.get("proxies") and settings.get("cert") is None,"EFFECTIVE_REQUESTS_TRUST")
        response = None
        try:
            sent.append(url)
            response = session.send(prepared,timeout=(3,5),allow_redirects=False,**settings)
        except requests.exceptions.SSLError as error:
            if "CERTIFICATE_VERIFY_FAILED" in str(error) or "certificate verify failed" in str(error).lower():
                raise ssl.SSLCertVerificationError("certificate validation failed") from None
            raise RuntimeError("INCONCLUSIVE_TLS") from None
        finally:
            if response is not None: response.close()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=build.verify_bundle(build.OS_CA)),build.NoRedirect())
    def stdlib_get(url):
        sent.append(url)
        try:
            with opener.open(urllib.request.Request(url,method="GET"),timeout=5): pass
        except urllib.error.HTTPError:
            pass  # HTTP responses prove TLS; redirects are never followed.
    rows=[];anchor=time.monotonic()
    try:
        for client,request in (("Requests_default_certifi",request_get),("stdlib_explicit_OS_CA",stdlib_get)):
            for url in TARGETS:
                need(now()<end and time.monotonic()-anchor<70,"TLS_BUDGET")
                rows.append({"client":client,"destination":url,"outcome":classify(request,url)})
    finally:
        session.close()
    need(sent==list(TARGETS)*2,"EXACT_SIX_REQUESTS")
    need([x["outcome"] for x in rows]==["TLS_ACCEPTED","CERTIFICATE_REJECTED","CERTIFICATE_REJECTED"]*2,"TLS_FAILED_OR_INCONCLUSIVE")
    return {"checks":rows,"installed":installed,"fixed_tls_attempts":len(sent),"effective_requests_verify":True,"trust_override_fields_present":False,"auth_headers_used":False}


def scrub_application_environment():
    allowed={"PATH","SYSTEMROOT","WINDIR","TEMP","TMP","LANG","LC_ALL","PORT","RENDER","RENDER_SERVICE_ID","RENDER_GIT_COMMIT"}
    clean={k:v for k,v in os.environ.items() if k.upper() in allowed}
    os.environ.clear();os.environ.update(clean)


def deny_application_outbound(port, events):
    scope=threading.local();original=socket.socketpair
    def pair(*args,**kwargs):
        scope.pair=True
        try:return original(*args,**kwargs)
        finally:scope.pair=False
    socket.socketpair=pair
    def audit(event,args):
        if event in {"socket.connect","socket.bind"}:
            address=args[1]
            if getattr(scope,"pair",False) and isinstance(address,tuple) and address[0] in {"127.0.0.1","::1"}:return
            if event=="socket.bind" and address==("0.0.0.0",port):return
        elif event=="socket.getaddrinfo":
            if args[0]=="0.0.0.0" and args[1]==port:return
        elif event not in {"socket.gethostbyname","socket.sendto","socket.sendmsg","subprocess.Popen","os.system","os.posix_spawn"}:
            return
        events.append(event)
        raise RuntimeError("APPLICATION_OUTBOUND_DENIED")
    sys.addaudithook(audit)


class HealthOnly:
    def __init__(self,application,report,end,events):
        self.application,self.report,self.end,self.events=application,report,end,events
        self.started=False
    async def __call__(self,scope,receive,send):
        if scope["type"]=="lifespan":
            async def observe(message):
                if message["type"]=="lifespan.startup.complete":self.started=True
                await send(message)
            return await self.application(scope,receive,observe)
        if scope["type"]=="websocket":
            return await send({"type":"websocket.close","code":1008})
        if scope["type"]!="http":return
        method,path=scope["method"],scope["path"]
        healthy=self.started and now()<self.end and not self.events
        allowed=method=="GET" and path in {"/health","/security-report"} and not scope.get("query_string")
        status=200 if allowed and healthy else (503 if allowed else 405 if method!="GET" else 404)
        body=json.dumps({**self.report,"normal_asgi_startup":True,"application_outbound_denied_events":0} if status==200 else {"status":"INERT"}).encode()
        await send({"type":"http.response.start","status":status,"headers":[(b"content-type",b"application/json"),(b"cache-control",b"no-store")]})
        await send({"type":"http.response.body","body":body})


def create_adapter():
    raw=MANIFEST.read_bytes();data=json.loads(raw)
    start,end=runtime_guard(data)
    tls=certificate_checks(end)
    commit=os.environ["RENDER_GIT_COMMIT"]
    port=int(os.getenv("PORT","10000"));need(1024<=port<=65535,"PORT")
    scrub_application_environment()
    events=[];deny_application_outbound(port,events)
    application=importlib.import_module("main")
    health=application.health()
    need(health.get("mode")=="SHADOW" and health.get("broker_execution_enabled") is False,"APPLICATION_BOUNDARY")
    need(application.SUPABASE_SECRET_KEY is None and application.WORKER_TOKEN is None and not events,"APPLICATION_CREDENTIAL_OR_OUTBOUND")
    report={"event":"NORMAL_WORKER_CA_RESULT","version":VERSION,"service":SERVICE,"commit":commit,
            "authorization_id":data["authorization_id"],"manifest_sha256":hashlib.sha256(raw).hexdigest(),
            "adapter_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),"checked_at":now().isoformat(),
            "health":health,"trading_app_imported":True,"application_credentials_removed":True,
            "application_outbound_guard":True,"mutation_routes_disabled":True,"strategy_eligible":False,**tls}
    return HealthOnly(application.app,report,end,events),port,end


def main():
    need(not sys.argv[1:],"NO_ARGUMENTS")
    app,port,end=create_adapter()
    import uvicorn
    server=uvicorn.Server(uvicorn.Config(app,host="0.0.0.0",port=port,access_log=False,log_level="warning",lifespan="on",timeout_graceful_shutdown=5))
    timer=threading.Timer(max(0,(end-now()).total_seconds()),lambda:setattr(server,"should_exit",True));timer.daemon=True;timer.start()
    try:server.run()
    finally:timer.cancel()


if __name__=="__main__":
    try:main()
    except Exception:
        print('{"event":"NORMAL_WORKER_CA_FAILED_CLOSED"}',flush=True)
        raise SystemExit(2) from None
