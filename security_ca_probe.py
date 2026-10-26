"""Bounded credential-free CA acceptance probe; never imports the trading app."""
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request

SERVICE = "srv-dal8a2m7bikc73enjn5g"
EXPIRES = datetime(2026, 10, 26, 4, 0, tzinfo=timezone.utc)
OS_CA = "/etc/ssl/certs/ca-certificates.crt"
TARGETS = ("https://render.com/", "https://dv-g3b-emudhra.we-have-a-problem.com/", "https://dv-g3b-aaa-emudhra.we-have-a-problem.com/")
BLOCKED_ROOTS = frozenset({"86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b", "d7a7a0fb5d7e2731d771e9484ebcdef71d5f0c3e0a2948782bc83ee0ea699ef4"})

def now():
    return datetime.now(timezone.utc)

def roots(path):
    pem = Path(path).read_text(encoding="ascii")
    return {hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert)).hexdigest() for cert in re.findall(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", pem, re.S)}

def sanitized_environment():
    allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG", "LC_ALL", "PORT", "RENDER", "RENDER_SERVICE_ID", "RENDER_GIT_COMMIT"}
    return {key: value for key, value in os.environ.items() if key.upper() in allowed}

def guard():
    if os.getenv("RENDER") != "true" or os.getenv("RENDER_SERVICE_ID") != SERVICE or now() >= EXPIRES:
        raise RuntimeError("HOST_OR_TIME_GUARD")
    if os.getenv("ALPACA_API_KEY") or os.getenv("ALPACA_API_SECRET"):
        raise RuntimeError("BROKER_CREDENTIAL_PRESENT")
    if os.getenv("SUPABASE_URL", "").rstrip("/") != "https://cihwmameyylixouggwxk.supabase.co":
        raise RuntimeError("STAGING_DATABASE_IDENTITY")

def build():
    guard()
    clean = sanitized_environment()
    if not Path(OS_CA).is_file() or roots(OS_CA) & BLOCKED_ROOTS:
        raise RuntimeError("OS_CA_NOT_PATCHED")
    base = [sys.executable, "-m", "pip", "--isolated", "--disable-pip-version-check", "install", "--no-input", "--no-cache-dir", "--index-url", "https://pypi.org/simple", "--use-deprecated=legacy-certs", "--cert", OS_CA]
    # The patched native OS bundle is the explicit verified bootstrap trust.
    # Credentials/proxy configuration are removed from both installer children.
    clean["PIP_CONFIG_FILE"] = os.devnull
    subprocess.run(base + ["--upgrade", "pip==26.2.2"], env=clean, check=True, timeout=120)
    subprocess.run(base + ["-r", "requirements.txt"], env=clean, check=True, timeout=180)
    print(json.dumps({"event": "CA_BUILD_COMPLETE", "os_bundle_sha256": hashlib.sha256(Path(OS_CA).read_bytes()).hexdigest(), "bootstrap_verification": "explicit_patched_OS_CA", "credentials_forwarded": False}), flush=True)

def classify_request(url, request):
    if url not in TARGETS:
        raise RuntimeError("URL_NOT_ALLOWED")
    try:
        request(url)
        return "TLS_ACCEPTED"
    except ssl.SSLCertVerificationError:
        return "CERTIFICATE_REJECTED"
    except urllib.error.URLError as error:
        return "CERTIFICATE_REJECTED" if isinstance(error.reason, ssl.SSLCertVerificationError) else "INCONCLUSIVE"

def run_checks():
    import certifi
    import requests
    if certifi.__version__ != "2026.10.23" or roots(certifi.where()) & BLOCKED_ROOTS:
        raise RuntimeError("CERTIFI_NOT_PATCHED")
    if roots(OS_CA) & BLOCKED_ROOTS:
        raise RuntimeError("OS_CA_NOT_PATCHED")
    session = requests.Session()
    session.trust_env = False
    session.auth = None
    session.headers.clear()
    session.cookies.clear()
    assert session.verify is True
    def requests_get(url):
        response = None
        try:
            response = session.get(url, timeout=(4, 6), allow_redirects=False, stream=True, verify=True)
        except requests.exceptions.SSLError as error:
            # Only explicit certificate validation failures count; protocol or
            # negotiation errors are not proof of compromised-chain rejection.
            if "CERTIFICATE_VERIFY_FAILED" in str(error) or "certificate verify failed" in str(error).lower():
                raise ssl.SSLCertVerificationError("certificate verification failed") from None
            raise RuntimeError("INCONCLUSIVE_SSL_FAILURE") from None
        finally:
            if response is not None:
                response.close()
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=OS_CA)), NoRedirect())
    def stdlib_get(url):
        try:
            with opener.open(urllib.request.Request(url, method="GET"), timeout=6):
                pass
        except urllib.error.HTTPError:
            pass  # A received HTTP status proves this TLS connection succeeded.
    rows = []
    for client, request in (("Requests_certifi", requests_get), ("stdlib_OS_CA", stdlib_get)):
        for url in TARGETS:
            try:
                outcome = classify_request(url, request)
            except Exception:
                outcome = "INCONCLUSIVE"
            rows.append({"client": client, "destination": url, "outcome": outcome})
    expected = ["TLS_ACCEPTED", "CERTIFICATE_REJECTED", "CERTIFICATE_REJECTED"] * 2
    return {"event": "CA_SECURITY_RESULT", "service": SERVICE, "commit": os.getenv("RENDER_GIT_COMMIT"), "checked_at": now().isoformat(),
        "passed": [row["outcome"] for row in rows] == expected, "checks": rows,
        "python": sys.version.split()[0], "openssl": ssl.OPENSSL_VERSION,
        "packages": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
        "certifi_bundle_sha256": hashlib.sha256(Path(certifi.where()).read_bytes()).hexdigest(),
        "os_bundle_sha256": hashlib.sha256(Path(OS_CA).read_bytes()).hexdigest(),
        "system_root_set_sha256": hashlib.sha256("".join(sorted(roots(OS_CA))).encode()).hexdigest(),
        "node_present": bool(shutil.which("node")), "php_present": bool(shutil.which("php")),
        "mode": "SHADOW", "broker_execution_enabled": False, "trading_app_imported": "main" in sys.modules,
        "database_requests": 0, "journal_requests": 0, "broker_requests": 0, "auth_headers_used": False}

def runtime():
    guard()
    clean = sanitized_environment()
    os.environ.clear()
    os.environ.update(clean)
    result = run_checks()
    print(json.dumps(result, sort_keys=True), flush=True)
    body = json.dumps(result).encode()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            allowed = self.path in {"/health", "/security-report"} and now() < EXPIRES
            self.send_response(200 if allowed else 503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body if allowed else b'{"status":"INERT"}')
        def do_POST(self):
            self.send_error(405)
    server = HTTPServer(("0.0.0.0", int(os.getenv("PORT", "10000"))), Handler)
    server.timeout = 1
    deadline = time.monotonic() + 90
    while now() < EXPIRES and time.monotonic() < deadline:
        server.handle_request()
    server.server_close()

if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["--build"]:
            build()
        elif not sys.argv[1:]:
            runtime()
        else:
            raise RuntimeError("INVALID_MODE")
    except Exception:
        print('{"event":"CA_PROBE_FAILED_CLOSED"}', flush=True)
        raise SystemExit(2) from None
