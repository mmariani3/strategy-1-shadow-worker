"""Opt-in, staging-only acceptance. All persisted fixtures are infrastructure tests.

Uses actual Render/Supabase transport. No orders, quotes, Sheets, or production writes.
Requires ignored connection JSON created during authorized staging provisioning.
"""
import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from conftest import candidate_data
from discovery_coordinator import QualificationRequest, SetupRequest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--connection-file', required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--apply-staging-fixtures', action='store_true', required=True)
    args = parser.parse_args()
    config = json.loads(Path(args.connection_file).read_text())
    assert config['supabase_url'] == 'https://cihwmameyylixouggwxk.supabase.co'
    urls = config['services']
    for component, url in urls.items():
        assert url == f'https://strategy1-pr1-staging-{component}.onrender.com'
    db_headers = {'apikey': config['supabase_key'], 'Authorization': 'Bearer ' + config['supabase_key'], 'Prefer': 'return=representation'}
    checks, records, health = [], [], {}

    def db(method, table, body=None, params=None, headers=None, expected=200):
        r = requests.request(method, config['supabase_url'] + '/rest/v1/' + table,
                             json=body, params=params, headers=headers or db_headers, timeout=30)
        assert r.status_code == expected, (table, r.status_code)
        return r.json()

    def post(component, path, body=None, expected=200, auth=True):
        headers = {'Authorization': 'Bearer ' + config['tokens'][component]} if auth else {}
        r = requests.post(urls[component] + path, json=body, headers=headers, timeout=90)
        assert r.status_code == expected, (component, path, r.status_code, r.text[:400])
        return r.json()

    for component, url in urls.items():
        r = requests.get(url + '/health', timeout=90)
        assert r.status_code == 200, (component, r.status_code)
        health[component] = r.json()
        assert health[component]['broker_execution_enabled'] is False
        assert health[component]['mode'] == 'SHADOW'
        if component == 'worker':
            assert args.expected_commit in health[component]['worker_version']
    checks.append('three SHADOW health endpoints and Worker revision')
    post('orchestrator', '/monitor/run-once', expected=401, auth=False)
    checks.append('unauthenticated request rejected')

    # A publishable key is deliberately used to test denied table access.
    public_headers = {'apikey': 'sb_publishable_pahvFEjrPBjWvv8283XBLQ_XU-_PC_h'}
    assert db('GET', 'strategy_candidates', params={'select': 'id'}, headers=public_headers) == []
    denied = requests.post(config['supabase_url'] + '/rest/v1/strategy_discovery_runs',
                           json={'id': str(uuid4())}, headers=public_headers, timeout=30)
    assert denied.status_code in (401, 403)
    checks.append('publishable role cannot read rows or insert')

    for missing in (True, False):
        data = candidate_data.__wrapped__()
        data.update(experiment_class='INFRASTRUCTURE_TEST', data_kind='SYNTHETIC',
                    market_data_source='INFRASTRUCTURE_TEST SYNTHETIC',
                    notes='INFRASTRUCTURE_TEST hosted acceptance; excluded from Strategy #1 evidence')
        run, item = str(uuid4()), str(uuid4())
        db('POST', 'strategy_discovery_runs', {
            'id': run, 'session_date': data['session_date'], 'phase': 'POST_OPEN',
            'status': 'PARTIAL', 'run_key': 'INFRASTRUCTURE_TEST-' + run,
            'ruleset_version': 'v0.3', 'experiment_class': 'INFRASTRUCTURE_TEST',
            'candidates_discovered': 1, 'notes': data['notes']}, expected=201)
        db('POST', 'strategy_discovery_items', {'id': item, 'run_id': run,
            'symbol': 'INFRA', 'operational_state': 'WATCHLIST_CANDIDATE'}, expected=201)
        qualification = {k: v for k, v in data.items() if k in QualificationRequest.model_fields}
        qualification.update(reviewer='hosted infrastructure acceptance', reviewed_at=data['current_review']['reviewed_at'])
        q = post('discovery', f'/items/{item}/qualify', qualification)
        assert q['candidate_id'] is None and q['setup_status'] == 'SETUP_REQUIRED'
        assert db('GET', 'strategy_candidates', params={'source_discovery_item_id': 'eq.' + item}) == []
        setup = {k: v for k, v in data.items() if k in SetupRequest.model_fields}
        setup.update(setup_rationale='INFRASTRUCTURE_TEST predefined fixture', trigger_operator='GTE')
        if missing:
            setup.pop('data_quality_ok')
        result = post('discovery', f'/items/{item}/setup', setup)
        replay = post('discovery', f'/items/{item}/setup', setup)
        cid = result['candidate_id']
        assert replay['idempotent_replay'] and replay['candidate_id'] == cid
        # Infrastructure classification takes precedence over strategy evaluation.
        assert result['operational_state'] == 'REJECTED', result
        candidate = db('GET', 'strategy_candidates', params={'id': 'eq.' + cid})[0]
        assert candidate['experiment_class'] == 'INFRASTRUCTURE_TEST' and candidate['data_kind'] == 'SYNTHETIC'
        signal = db('GET', 'strategy_signals', params={'id': 'eq.' + candidate['last_signal_id']})[0]
        assert signal['decision_inputs']['run_id'] == run and signal['decision_inputs']['candidate_id'] == cid
        assert signal['journal_trade_id'] == candidate['journal_trade_id']
        assert args.expected_commit in signal['worker_version'] and 'sha256=' in signal['worker_version']
        assert signal['status'] == 'SHADOW' and signal['decision'] == 'NO_TRADE'
        assert signal['decision_inputs']['reason_code'] == 'INFRASTRUCTURE_TEST'
        events = db('GET', 'strategy_candidate_events', params={'candidate_id': 'eq.' + cid})
        assert events
        audited = [e for e in events if 'before' in e['payload'] and 'after' in e['payload']]
        assert audited and all(e['event_at'] and e['payload']['implementation_version']
                               and e['payload']['owner'] and e['payload']['reason'] for e in audited)
        discovery_events = db('GET', 'strategy_discovery_events', params={'discovery_item_id': 'eq.' + item})
        assert ('HOLD_UNRESOLVED' if missing else 'WORKER_READY') in [e['payload'].get('new_state') for e in discovery_events]
        assert len(db('GET', 'strategy_candidates', params={'source_discovery_item_id': 'eq.' + item})) == 1
        assert len(db('GET', 'strategy_signals', params={'decision_inputs->>candidate_id': 'eq.' + cid})) == 1
        records.append({'run_id': run, 'item_id': item, 'candidate_id': cid,
                        'signal_id': signal['id'], 'journal_trade_id': signal['journal_trade_id']})
    checks.extend(['qualification does not construct a candidate', 'incomplete infrastructure setup remains ineligible',
                   'complete structured setup handoff', 'setup retry reuses candidate',
                   'structured trace IDs and actual implementation attribution', 'persisted infrastructure classification'])
    monitored = post('orchestrator', '/monitor/run-once')
    assert monitored['trigger_confirmation_automatic'] is False
    for record in records:
        c = db('GET', 'strategy_candidates', params={'id': 'eq.' + record['candidate_id']})[0]
        assert not c['trigger_confirmed'] and c['operational_state'] == 'REJECTED'
        assert c.get('trigger_observed_at') is None
    checks.append('infrastructure candidates cannot receive market monitoring or confirmation')
    assert db('GET', 'strategy_candidates', params={'select': 'id'}, headers=public_headers) == []
    for table in ('strategy_discovery_events', 'journal_deliveries'):
        denied = requests.get(config['supabase_url'] + '/rest/v1/' + table, headers=public_headers, timeout=30)
        assert denied.status_code in (401, 403)
    checks.append('attributable audit history, unique signals, and populated-table RLS')
    print(json.dumps({'status': 'PASSED', 'commit': args.expected_commit, 'checks': checks,
                      'health': health, 'records': records,
                      'limitations': ['No real-market prospective observation', 'No production deployment',
                                      'No hosted journal writer; credentialed writer tested separately']}))


if __name__ == '__main__':
    main()
