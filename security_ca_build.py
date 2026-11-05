"""Build-only CA bootstrap for the unchanged Worker; importing this does no I/O.

Derived from the accepted November 4 probe. No dates, service authority,
credentials, application imports, deployment APIs or runtime wrapper live here.
The proposed build command is: python security_ca_build.py --build-worker
The normal uvicorn start command is unchanged. Do not execute the build locally
as part of offline acceptance: its download/install ports are mocked in tests.
"""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import ssl
import subprocess
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parent
OS_CA = Path("/etc/ssl/certs/ca-certificates.crt")
REQUIREMENTS = ROOT / "requirements.txt"
REQUIREMENTS_SHA256 = "fe49367946aa1f80570e3f19d2bf086bc14df8f0e028da489ab3ef6820688ebe"
PIP_URL = "https://files.pythonhosted.org/packages/3f/06/3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/pip-26.2.2-py3-none-any.whl"
PIP_SHA256 = "fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70"
BLOCKED_ROOTS = frozenset({"86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b", "d7a7a0fb5d7e2731d771e9484ebcdef71d5f0c3e0a2948782bc83ee0ea699ef4"})
EXPECTED = {"pip": "26.2.2", "certifi": "2026.10.23", "requests": "2.32.5", "fastapi": "0.116.1", "uvicorn": "0.35.0", "pydantic": "2.11.7"}


class BuildRejected(RuntimeError):
    """Only constant, allowlisted codes may cross the command-line boundary."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def roots(path):
    pem = Path(path).read_text(encoding="ascii")
    certificates = re.findall(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", pem, re.S)
    if not certificates:
        raise BuildRejected("EMPTY_CA_BUNDLE")
    return {hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert)).hexdigest() for cert in certificates}


def verify_bundle(path):
    if roots(path) & BLOCKED_ROOTS:
        raise BuildRejected("AFFECTED_CA_ROOT")
    context = ssl.create_default_context(cafile=str(path))
    if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED or not context.get_ca_certs(binary_form=True):
        raise BuildRejected("INVALID_CA_CONTEXT")
    return context


def sanitized_environment():
    allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG", "LC_ALL"}
    clean = {k: v for k, v in os.environ.items() if k.upper() in allowed}
    clean["PIP_CONFIG_FILE"] = os.devnull
    clean["PYTHONDONTWRITEBYTECODE"] = "1"
    return clean


def verify_manifest():
    if REQUIREMENTS.is_symlink() or hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest() != REQUIREMENTS_SHA256:
        raise BuildRejected("REQUIREMENTS_CHANGED")


def download_pip_wheel(destination):
    context = verify_bundle(OS_CA)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context), NoRedirect())
    with opener.open(PIP_URL, timeout=15) as response:
        if response.geturl() != PIP_URL or response.status != 200:
            raise BuildRejected("BOOTSTRAP_RESPONSE")
        data = response.read(2_000_001)
    if len(data) > 2_000_000 or hashlib.sha256(data).hexdigest() != PIP_SHA256:
        raise BuildRejected("BOOTSTRAP_WHEEL_HASH")
    with Path(destination).open("xb") as stream:
        stream.write(data)


def run_child(arguments, clean, timeout):
    # Provider/installer output is never relayed to logs, including on failure.
    try:
        result = subprocess.run(arguments, env=clean, cwd=ROOT, stdin=subprocess.DEVNULL,
                                capture_output=True, check=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        raise BuildRejected("BUILD_CHILD_FAILED") from None
    return result.stdout


def installed_report():
    verify_manifest()
    versions = {name: importlib.metadata.version(name) for name in EXPECTED}
    if versions != EXPECTED:
        raise BuildRejected("INSTALLED_VERSION_MISMATCH")
    import certifi
    import requests
    pip_ca = importlib.metadata.distribution("pip").locate_file("pip/_vendor/certifi/cacert.pem")
    bundles = {"os": OS_CA, "pip": Path(pip_ca), "certifi": Path(certifi.where())}
    if Path(requests.utils.DEFAULT_CA_BUNDLE_PATH).resolve() != bundles["certifi"].resolve():
        raise BuildRejected("REQUESTS_CA_MISMATCH")
    for path in bundles.values():
        verify_bundle(path)
    return {"event": "WORKER_CA_BUILD_VERIFIED", "versions": versions,
            "bundle_sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in bundles.items()},
            "requirements_sha256": REQUIREMENTS_SHA256, "python": sys.version.split()[0],
            "openssl": ssl.OPENSSL_VERSION, "application_imported": "main" in sys.modules}


def build_worker():
    verify_manifest()
    verify_bundle(OS_CA)
    clean = sanitized_environment()
    base = [sys.executable, "-I", "-B", "-m", "pip", "--isolated", "--disable-pip-version-check"]
    install = base + ["install", "--no-input", "--no-cache-dir", "--quiet"]
    with tempfile.TemporaryDirectory(prefix="worker-ca-bootstrap-") as folder:
        wheel = Path(folder) / "pip-26.2.2-py3-none-any.whl"
        download_pip_wheel(wheel)
        run_child(install + ["--no-index", "--no-deps", "--upgrade", str(wheel)], clean, 120)
    if importlib.metadata.version("pip") != EXPECTED["pip"]:
        raise BuildRejected("PIP_VERSION")
    verify_bundle(importlib.metadata.distribution("pip").locate_file("pip/_vendor/certifi/cacert.pem"))
    run_child(install + ["--index-url", "https://pypi.org/simple", "--cert", str(OS_CA), "-r", str(REQUIREMENTS)], clean, 180)
    run_child(base + ["check"], clean, 30)
    # New interpreter: never trust modules cached before dependency installation.
    output = run_child([sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--verify-installed"], clean, 30)
    report = json.loads(output)
    if report.get("event") != "WORKER_CA_BUILD_VERIFIED" or report.get("versions") != EXPECTED or report.get("application_imported") is not False:
        raise BuildRejected("INVALID_INSTALL_RECEIPT")
    print(json.dumps(report, sort_keys=True), flush=True)


def cli(arguments):
    try:
        if arguments == ["--build-worker"]:
            build_worker()
        elif arguments == ["--verify-installed"]:
            print(json.dumps(installed_report(), sort_keys=True), flush=True)
        else:
            raise BuildRejected("INVALID_MODE")
        return 0
    except Exception:
        # No exception, environment or installer text is safe to emit here.
        print('{"event":"WORKER_CA_BUILD_FAILED_CLOSED"}', flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(cli(sys.argv[1:]))
