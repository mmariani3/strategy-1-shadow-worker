"""Elapsed-time offline models, not hosted readiness or real market evidence."""
from datetime import timedelta

import pytest
from requests.exceptions import ReadTimeout, ConnectTimeout

from test_coordinator_preflight_binding import rehearsal, probes
from test_coordinator_launch_guard import tmp_path
from test_coordinator_startup_readiness import assert_safe_failure, runtime_calls
from test_coordinator_adapters import Response


def advance(r, seconds):
    r.clock[0] += timedelta(seconds=seconds)
    r.mono[0] += seconds


def timed_startup(r, *, ready_after, timeout=3.1, exception=ReadTimeout,
                  observe_delay=60.266, resume_delay=7.609):
    original_observe = r.connections.observe
    def observe(*args, **kwargs):
        value = original_observe(*args, **kwargs)
        advance(r, observe_delay)
        return value
    r.connections.observe = observe
    original_resume = r.connections.render.resume
    def resume(*args, **kwargs):
        value = original_resume(*args, **kwargs)
        advance(r, resume_delay)
        return value
    r.connections.render.resume = resume
    session = r.connections.runtime.http.session
    original_response = session.response
    r.connections.runtime.http.monotonic = lambda: r.mono[0]
    first = []
    calls = []
    def response(method, url, **kwargs):
        if url.endswith('/health'):
            if not first: first.append(r.mono[0])
            calls.append(r.mono[0])
            if r.mono[0] - first[0] < ready_after:
                advance(r, timeout)
                raise exception('INVENTED_TIMEOUT_NO_CREDENTIALS')
            advance(r, 0.1)
        else:
            # Successful provider work takes real elapsed time in this model.
            advance(r, 20)
        return original_response(method, url, **kwargs)
    session.response = response
    return calls


@pytest.mark.parametrize('ready_after', [24, 35, 45])
def test_delayed_public_readiness_then_single_authentication(rehearsal, ready_after):
    r = rehearsal
    calls = timed_startup(r, ready_after=ready_after)
    result = r.run()
    assert result['status'] == 'NO_SCAN_CHECKS_PASSED'
    assert result['authentication'] == 'PASS'
    assert 5 < len(calls) <= 15
    assert len(runtime_calls(r, '/acceptance/preflight')) == 1
    assert result['watchdog_suspension'] == 'PROVIDER_READBACK_WITHOUT_PARENT_SUSPEND'
    assert result['database_unchanged'] and result['cleanup'] == 'VERIFIED'
    assert result['watchdog_shutdown'] == 'VERIFIED'
    assert r.p.suspend_at == r.p.not_before + timedelta(seconds=180)
    assert r.p.verify_by == r.p.not_before + timedelta(seconds=480)
    assert r.clock[0] == r.p.suspend_at
    assert result['acceptance_posts'] == 0 and not result['strategy_evidence_eligible']


@pytest.mark.parametrize('timeout,exception', [(3.1, ReadTimeout), (3.1, ConnectTimeout), (6.1, ReadTimeout)])
def test_elapsed_timeouts_exhaust_without_authentication(rehearsal, timeout, exception):
    r = rehearsal
    timed_startup(r, ready_after=999, timeout=timeout, exception=exception)
    result = r.run()
    assert_safe_failure(r, result)
    timing = next(x for x in result['diagnostics'] if x['phase'] == 'readiness')
    assert 45 < timing['elapsed_seconds'] <= 60
    assert len(runtime_calls(r, '/health')) <= 15
    assert not runtime_calls(r, '/acceptance/preflight')
    assert r.clock[0] < r.p.suspend_at - timedelta(seconds=40)


def test_remaining_watchdog_budget_shortens_readiness(rehearsal):
    r = rehearsal
    calls = timed_startup(r, ready_after=45, observe_delay=79, resume_delay=20)
    result = r.run()
    assert_safe_failure(r, result)
    assert result['failure_phase'] == 'readiness'
    assert calls and not runtime_calls(r, '/acceptance/preflight')
    # Start at T0+99: only 41 seconds remain before the authentication reserve.
    assert all(t < 134 for t in calls)
    assert r.clock[0] < r.p.suspend_at - timedelta(seconds=40)


def test_fast_unavailable_responses_keep_fifteen_request_cap(rehearsal):
    r = rehearsal
    r.connections.runtime.http.session.response = Response({}, 503)
    result = r.run()
    assert_safe_failure(r, result)
    assert len(runtime_calls(r, '/health')) == 15
    assert not runtime_calls(r, '/acceptance/preflight')


def test_success_response_past_deadline_cannot_authenticate(rehearsal):
    r = rehearsal
    session = r.connections.runtime.http.session
    original = session.response
    def delayed(*args, **kwargs):
        advance(r, 61)
        return original(*args, **kwargs)
    session.response = delayed
    result = r.run()
    assert_safe_failure(r, result)
    assert not runtime_calls(r, '/acceptance/preflight')
