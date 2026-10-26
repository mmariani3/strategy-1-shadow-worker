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
import tempfile
import time
import urllib.error
import urllib.request

SERVICE = "srv-dal8a2m7bikc73enjn5g"
EXPIRES = datetime(2026, 10, 26, 4, 0, tzinfo=timezone.utc)
OS_CA = "/etc/ssl/certs/ca-certificates.crt"
TARGETS = ("https://render.com/", "https://dv-g3b-emudhra.we-have-a-problem.com/", "https://dv-g3b-aaa-emudhra.we-have-a-problem.com/")
BLOCKED_ROOTS = frozenset({"86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b", "d7a7a0fb5d7e2731d771e9484ebcdef71d5f0c3e0a2948782bc83ee0ea699ef4"})
PIP_URL = "https://files.pythonhosted.org/packages/3f/06/3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/pip-26.2.2-py3-none-any.whl"
PIP_SHA256 = "fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70"

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def download_pip_wheel(path):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=OS_CA)), NoRedirect())
    with opener.open(PIP_URL, timeout=15) as response:
        if response.geturl() != PIP_URL:
            raise RuntimeError("BOOTSTRAP_REDIRECT")
        data = response.read(2_000_001)
    if len(data) > 2_000_000 or hashlib.sha256(data).hexdigest() != PIP_SHA256:
        raise RuntimeError("BOOTSTRAP_WHEEL_HASH")
    path.write_bytes(data)

def patched_pip_cafile():
    if importlib.metadata.version("pip") != "26.2.2":
        raise RuntimeError("PIP_VERSION")
    return importlib.metadata.distribution("pip").locate_file("pip/_vendor/certifi/cacert.pem")

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
    base = [sys.executable, "-m", "pip", "--isolated", "--disable-pip-version-check", "install", "--no-input", "--no-cache-dir"]
    # Do not ask the initial pip to make any network request. Download a fixed
    # wheel with verified OS TLS and a PyPI-published SHA256, then install offline.
    clean["PIP_CONFIG_FILE"] = os.devnull
    with tempfile.TemporaryDirectory(prefix="ca-pip-bootstrap-") as folder:
        wheel = Path(folder) / "pip-26.2.2-py3-none-any.whl"
        download_pip_wheel(wheel)
        subprocess.run(base + ["--no-index", "--no-deps", "--upgrade", str(wheel)], env=clean, check=True, timeout=120)
    if roots(patched_pip_cafile()) & BLOCKED_ROOTS:
        raise RuntimeError("PIP_VENDORED_CA_NOT_PATCHED")
    subprocess.run(base + ["--index-url", "https://pypi.org/simple", "--cert", OS_CA, "-r", "requirements.txt"], env=clean, check=True, timeout=180)
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
