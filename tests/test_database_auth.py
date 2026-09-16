"""Legacy service-role JWTs need Authorization; new secret keys use apikey."""
from types import SimpleNamespace
import pytest
import main
import orchestrator
import discovery_coordinator


@pytest.mark.parametrize('key', ['header.payload.signature', 'sb_secret_test-only'])
def test_server_database_requests_authenticate_the_configured_role(monkeypatch, candidate_data, key):
    captured = []
    for module in (main, orchestrator, discovery_coordinator):
        monkeypatch.setattr(module, 'SUPABASE_URL', 'https://staging.invalid')
        monkeypatch.setattr(module, 'SUPABASE_SECRET_KEY', key)
    def post(url, **kwargs):
        captured.append(kwargs['headers'])
        return SimpleNamespace(ok=True, json=lambda: [{'id': 'test-record'}])
    monkeypatch.setattr(main.requests, 'post', post)
    candidate = main.Candidate(**candidate_data)
    main.write_supabase(candidate, main.evaluate(candidate))
    captured.extend([orchestrator._sb_headers(), discovery_coordinator.sb_headers(False)])
    for headers in captured:
        assert headers['apikey'] == key
        if key.count('.') == 2:
            assert headers['Authorization'] == 'Bearer ' + key
        else:
            assert 'Authorization' not in headers
