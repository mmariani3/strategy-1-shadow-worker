"""Offline security boundary tests. No real download/install/service port."""
from contextlib import ExitStack
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import ssl
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock, patch
import zipfile

import pytest
import security_ca_build as b

WORKSPACE = Path(__file__).resolve().parents[2]


def test_exact_worker_manifest():
    b.verify_manifest()
    assert b.REQUIREMENTS.read_text().splitlines() == [
        "fastapi==0.116.1", "uvicorn[standard]==0.35.0", "pydantic==2.11.7",
        "requests==2.32.5", "certifi==2026.10.23"]


def test_changed_manifest_blocks_every_port(tmp_path, monkeypatch):
    p = tmp_path / "requirements.txt"
    p.write_text("requests\n")
    monkeypatch.setattr(b, "REQUIREMENTS", p)
    with patch.object(b, "download_pip_wheel") as download, patch.object(b, "run_child") as run:
        with pytest.raises(b.BuildRejected, match="REQUIREMENTS_CHANGED"):
            b.build_worker()
    download.assert_not_called()
    run.assert_not_called()


@pytest.mark.parametrize("content", ["", "not a certificate", "-----BEGIN CERTIFICATE-----\ninvalid\n-----END CERTIFICATE-----"])
def test_invalid_bundle_fails_closed(tmp_path, content):
    p = tmp_path / "ca.pem"
    p.write_text(content)
    with pytest.raises(Exception):
        b.verify_bundle(p)


def test_affected_bundle_blocks_context_and_transport():
    with patch.object(b, "roots", return_value=b.BLOCKED_ROOTS), patch.object(b.ssl, "create_default_context") as ctx:
        with pytest.raises(b.BuildRejected, match="AFFECTED_CA_ROOT"):
            b.verify_bundle("synthetic")
    ctx.assert_not_called()


@pytest.mark.parametrize("hostname,mode,certs", [(False,ssl.CERT_REQUIRED,[b"x"]), (True,ssl.CERT_NONE,[b"x"]), (True,ssl.CERT_REQUIRED,[])])
def test_nonverifying_context_rejected(hostname, mode, certs):
    ctx = SimpleNamespace(check_hostname=hostname, verify_mode=mode, get_ca_certs=lambda **k: certs)
    with patch.object(b, "roots", return_value={"synthetic"}), patch.object(b.ssl, "create_default_context", return_value=ctx):
        with pytest.raises(b.BuildRejected, match="INVALID_CA_CONTEXT"):
            b.verify_bundle("synthetic")


def test_no_secrets_proxy_or_python_injection_in_child_environment():
    values = dict(PATH="local-path", LANG="C", WORKER_TOKEN="SYNTHETIC", ALPACA_API_KEY="SYNTHETIC",
                  SUPABASE_URL="SYNTHETIC", SUPABASE_SECRET_KEY="SYNTHETIC", HTTPS_PROXY="SYNTHETIC",
                  REQUESTS_CA_BUNDLE="SYNTHETIC", CURL_CA_BUNDLE="SYNTHETIC", SSL_CERT_FILE="SYNTHETIC",
                  SSL_CERT_DIR="SYNTHETIC", PYTHONPATH="SYNTHETIC", PYTHONHOME="SYNTHETIC",
                  PIP_INDEX_URL="SYNTHETIC", PIP_TRUSTED_HOST="SYNTHETIC", HOME="SYNTHETIC")
    with patch.dict(os.environ, values, clear=True):
        clean = b.sanitized_environment()
    assert clean == {"PATH":"local-path", "LANG":"C", "PIP_CONFIG_FILE":os.devnull, "PYTHONDONTWRITEBYTECODE":"1"}


class Response:
    def __init__(self, url, status, data):
        self.url, self.status, self.data = url, status, data
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def geturl(self): return self.url
    def read(self, size):
        assert size == 2_000_001
        return self.data


@pytest.mark.parametrize("url,status,data", [("https://invalid.example/wheel",200,b""), (b.PIP_URL,302,b""),
                                            (b.PIP_URL,200,b"tampered"), (b.PIP_URL,200,b"x"*2_000_001)], ids=["redirect","status","hash","oversized"])
def test_invalid_bootstrap_never_writes(tmp_path, url, status, data):
    opener = Mock()
    opener.open.return_value = Response(url,status,data)
    path = tmp_path / "pip.whl"
    with patch.object(b,"verify_bundle"), patch.object(b.urllib.request,"build_opener",return_value=opener):
        with pytest.raises(b.BuildRejected): b.download_pip_wheel(path)
    assert not path.exists()
    opener.open.assert_called_once_with(b.PIP_URL, timeout=15)


def test_verified_cached_wheel_download_port_and_exclusive_write(tmp_path):
    wheel = WORKSPACE / "output/security-ca-bootstrap-corrected/pip-26.2.2-py3-none-any.whl"
    data = wheel.read_bytes()
    assert hashlib.sha256(data).hexdigest() == b.PIP_SHA256
    opener = Mock()
    opener.open.return_value = Response(b.PIP_URL,200,data)
    path = tmp_path / "pip.whl"
    with patch.object(b,"verify_bundle") as verify, patch.object(b.urllib.request,"build_opener",return_value=opener) as factory:
        b.download_pip_wheel(path)
        assert isinstance(factory.call_args.args[0], b.urllib.request.ProxyHandler)
        assert factory.call_args.args[0].proxies == {}
        assert isinstance(factory.call_args.args[2], b.NoRedirect)
        assert b.NoRedirect().redirect_request(None) is None
        verify.assert_called_once_with(b.OS_CA)
        with pytest.raises(FileExistsError): b.download_pip_wheel(path)
    assert path.read_bytes() == data
    with zipfile.ZipFile(wheel) as archive:
        bundle = tmp_path / "pip-ca.pem"
        bundle.write_bytes(archive.read("pip/_vendor/certifi/cacert.pem"))
    b.verify_bundle(bundle)


def fixture_build(stack):
    stack.enter_context(patch.object(b,"verify_bundle"))
    stack.enter_context(patch.object(b,"download_pip_wheel"))
    stack.enter_context(patch.object(b.importlib.metadata,"version",return_value="26.2.2"))
    stack.enter_context(patch.object(b.importlib.metadata,"distribution",return_value=SimpleNamespace(locate_file=lambda x: Path("public-pip-ca.pem"))))
    report = {"event":"WORKER_CA_BUILD_VERIFIED", "versions":b.EXPECTED, "application_imported":False}
    return stack.enter_context(patch.object(b,"run_child",return_value=json.dumps(report).encode()))


def test_build_sequence_is_isolated_bounded_and_offline_bootstrap(capsys):
    with ExitStack() as stack:
        run = fixture_build(stack)
        b.build_worker()
    assert run.call_count == 4
    first, install, check, verify = run.call_args_list
    assert "--no-index" in first.args[0] and "--no-deps" in first.args[0]
    assert first.args[2] == 120 and install.args[2] == 180
    assert "--isolated" in first.args[0] and "-I" in first.args[0]
    assert install.args[0][-6:] == ["--index-url","https://pypi.org/simple","--cert",str(b.OS_CA),"-r",str(b.REQUIREMENTS)]
    assert check.args[0][-1] == "check" and check.args[2] == 30
    assert verify.args[0][-1] == "--verify-installed" and verify.args[2] == 30
    assert json.loads(capsys.readouterr().out)["application_imported"] is False


def test_stale_pip_stops_before_requirement_install():
    with ExitStack() as stack:
        run = fixture_build(stack)
        stack.enter_context(patch.object(b.importlib.metadata,"version",return_value="25.0"))
        with pytest.raises(b.BuildRejected, match="PIP_VERSION"): b.build_worker()
    assert run.call_count == 1


def test_bad_os_bundle_stops_before_any_download():
    with patch.object(b,"verify_bundle",side_effect=b.BuildRejected("AFFECTED_CA_ROOT")), patch.object(b,"download_pip_wheel") as d, patch.object(b,"run_child") as r:
        with pytest.raises(b.BuildRejected): b.build_worker()
    d.assert_not_called()
    r.assert_not_called()


def test_bad_vendored_pip_bundle_stops_before_dependency_network():
    with ExitStack() as stack:
        run = fixture_build(stack)
        stack.enter_context(patch.object(b,"verify_bundle",side_effect=[None,b.BuildRejected("AFFECTED_CA_ROOT")]))
        with pytest.raises(b.BuildRejected): b.build_worker()
    assert run.call_count == 1


@pytest.mark.parametrize("error", [subprocess.CalledProcessError(1,["synthetic"],output=b"SYNTHETIC_SECRET"), subprocess.TimeoutExpired(["synthetic"],1), OSError("SYNTHETIC_SECRET")])
def test_installer_failures_are_sanitized(error, capsys):
    with patch.object(b.subprocess,"run",side_effect=error):
        with pytest.raises(b.BuildRejected, match="^BUILD_CHILD_FAILED$"):
            b.run_child(["synthetic"],{},1)
    assert "SYNTHETIC_SECRET" not in capsys.readouterr().out


def test_child_ports_are_bounded_and_capture_only():
    with patch.object(b.subprocess,"run",return_value=SimpleNamespace(stdout=b"ok")) as run:
        assert b.run_child(["synthetic"],{"LANG":"C"},10) == b"ok"
    assert run.call_args.kwargs == dict(env={"LANG":"C"},cwd=b.ROOT,stdin=subprocess.DEVNULL,capture_output=True,check=True,timeout=10)


@pytest.mark.parametrize("versions", [{}, dict(b.EXPECTED,certifi="2026.7.22")])
def test_bad_install_receipt_fails_closed(versions):
    with ExitStack() as stack:
        run = fixture_build(stack)
        run.return_value = json.dumps(dict(event="WORKER_CA_BUILD_VERIFIED",versions=versions,application_imported=False)).encode()
        with pytest.raises(b.BuildRejected, match="INVALID_INSTALL_RECEIPT"): b.build_worker()


def test_wrong_installed_version_rejected_before_imports():
    with patch.object(b.importlib.metadata,"version",return_value="0"):
        with pytest.raises(b.BuildRejected,match="INSTALLED_VERSION_MISMATCH"): b.installed_report()


def test_cli_never_prints_exception(capsys):
    with patch.object(b,"build_worker",side_effect=RuntimeError("SYNTHETIC_SECRET")):
        assert b.cli(["--build-worker"]) == 2
    assert capsys.readouterr().out.strip() == '{"event":"WORKER_CA_BUILD_FAILED_CLOSED"}'


def test_cli_rejects_unspecified_mode(capsys):
    with patch.object(b,"build_worker") as run:
        assert b.cli([]) == 2
    run.assert_not_called()


def test_real_local_requests_uses_patched_certifi():
    import certifi, requests
    assert certifi.__version__ == "2026.10.23"
    assert Path(requests.utils.DEFAULT_CA_BUNDLE_PATH).resolve() == Path(certifi.where()).resolve()
    assert requests.Session().verify is True
    b.verify_bundle(certifi.where())


def test_normal_worker_lifespan_and_health_without_external_calls():
    from fastapi.testclient import TestClient
    import main
    with TestClient(main.app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["mode"] == "SHADOW"
    assert response.json()["broker_execution_enabled"] is False
    assert main.WORKER_TOKEN is None and main.SUPABASE_SECRET_KEY is None


@pytest.mark.parametrize("variable", ["REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"])
def test_existing_application_requests_honors_ca_overrides(variable):
    # Evidence of a remaining deployment gate, not a change to application
    # behavior. Build-child scrubbing does NOT scrub the normal app runtime.
    import requests
    with patch.dict(os.environ, {variable:"SYNTHETIC_UNAPPROVED_BUNDLE"}, clear=True):
        settings = requests.Session().merge_environment_settings("https://invalid.example/", {}, None, None, None)
    assert settings["verify"] == "SYNTHETIC_UNAPPROVED_BUNDLE"
