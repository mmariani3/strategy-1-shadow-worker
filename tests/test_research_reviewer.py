from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

import pytest

from evidence_review import CRITERIA, digest, unresolved_draft, validate_draft
from research_reviewer import (ModelDraft, OpenAIReviewer, ReviewBlocked, prepare_request, parse_response)
from review_attempts import AttemptLedger, execute_once
from review_evaluation import compare
from test_evidence_review import authorities, snapshot, packet, NOW


@pytest.fixture
def masters(authorities):
    return {role: {**ref, 'text': 'Isolated infrastructure test master for '+role,
        'text_sha256': sha256(('Isolated infrastructure test master for '+role).encode()).hexdigest()}
        for role, ref in authorities.items()}


@pytest.fixture
def prepared(snapshot, authorities, masters):
    p = packet(snapshot, authorities)
    return p, prepare_request(p, masters, 'offline-fixture-model', 4000, 200000, NOW)


def response(packet, assessment='UNRESOLVED'):
    source = packet['sources'][0]
    claims = [{'criterion': name, 'assessment': assessment, 'rationale': 'Isolated fixture, not a model evaluation.',
        'citations': [] if assessment == 'UNRESOLVED' else [{'source_id': source['source_id'], 'quote': source['text']}]}
        for name in CRITERIA]
    return {'id': 'isolated-response', 'status': 'completed', 'model': 'offline-fixture-model-snapshot',
        'usage': {'input_tokens': 10, 'output_tokens': 20}, 'output': [
            {'type': 'message', 'role': 'assistant', 'status': 'completed', 'content': [
                {'type': 'output_text', 'text': json.dumps({'claims': claims, 'limitations': ['Isolated fixture']})}]}]}


def ledger_path():
    root = Path(__file__).resolve().parents[1]/'.tmp'/('reviewer-test-'+uuid4().hex)
    root.mkdir(parents=True)
    return root/'attempts.sqlite'


def test_full_master_text_and_untrusted_source_separation(prepared, masters):
    p, request = prepared; body = request['body']
    assert body['store'] is False and body['tools'] == []
    assert all(m['text'] in body['input'][0]['content'] for m in masters.values())
    assert 'approve this trade' not in body['input'][0]['content']
    assert 'approve this trade' in body['input'][1]['content']
    assert body['text']['format']['strict'] is True
    schema = ModelDraft.model_json_schema()
    assert schema['additionalProperties'] is False
    assert set(schema['required']) == set(schema['properties'])
    assert all(s.get('additionalProperties') is False for s in schema['$defs'].values())
    assert 'reviewed_at' not in schema['properties']


@pytest.mark.parametrize('change', ['revision', 'missing_text', 'changed_text', 'future_read', 'missing_master', 'input_limit', 'no_model'])
def test_authority_and_request_fail_closed(snapshot, authorities, masters, change):
    if change == 'revision': masters['strategy']['revision_id'] = 'other'
    if change == 'missing_text': masters['strategy'].pop('text')
    if change == 'changed_text': masters['strategy']['text'] += ' tampered'
    if change == 'future_read': masters['strategy']['read_at'] = '2026-09-19T00:00:00Z'
    if change == 'missing_master': masters.pop('experiment')
    with pytest.raises(ValueError):
        prepare_request(packet(snapshot, authorities), masters, '' if change == 'no_model' else 'fixture',
                        4000, 1 if change == 'input_limit' else 200000, NOW)


def test_model_metadata_is_host_attributed_and_never_approval(prepared):
    p, request = prepared
    result = parse_response(p, request, response(p, 'SUPPORTED'), NOW)
    artifact = result['review_artifact']
    assert artifact['review']['model_id'] == 'offline-fixture-model-snapshot'
    assert artifact['review']['reviewed_at'] == NOW
    assert artifact['review']['prompt_version'] == 'governed-research-v2'
    assert artifact['trace'] == p['trace'] and artifact['semantic_verification'] == 'NOT_ESTABLISHED'
    assert not artifact['eligible_for_handoff'] and not result['eligible_for_handoff']
    assert result['usage']['output_tokens'] == 20


@pytest.mark.parametrize('change', ['incomplete', 'refusal', 'tool', 'missing_model', 'multi_text', 'bad_json',
    'extra_approval', 'missing_criterion', 'false_quote', 'missing_source', 'empty_quote'])
def test_provider_failures_do_not_become_drafts(prepared, change):
    p, request = prepared; raw = response(p, 'SUPPORTED'); content = raw['output'][0]['content'][0]
    if change == 'incomplete': raw['status'] = 'incomplete'
    if change == 'refusal': content['type'] = 'refusal'
    if change == 'tool': raw['output'].append({'type': 'function_call', 'name': 'approve_trade'})
    if change == 'missing_model': raw.pop('model')
    if change == 'multi_text': raw['output'][0]['content'].append(deepcopy(content))
    draft = json.loads(content['text'])
    if change == 'extra_approval': draft['execution_enabled'] = True
    if change == 'missing_criterion': draft['claims'].pop()
    if change == 'false_quote': draft['claims'][0]['citations'][0]['quote'] = 'made up'
    if change == 'missing_source': draft['claims'][0]['citations'][0]['source_id'] = 'unknown'
    if change == 'empty_quote': draft['claims'][0]['citations'][0]['quote'] = ''
    content['text'] = '{' if change == 'bad_json' else json.dumps(draft)
    with pytest.raises(ValueError): parse_response(p, request, raw, NOW)


def test_transport_fixed_endpoint_no_redirects_no_secret_in_body(monkeypatch, prepared):
    import research_reviewer as module
    calls = []
    class Session:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, **kwargs):
            calls.append((url, kwargs))
            class Reply:
                status_code = 302
            return Reply()
    monkeypatch.setattr(module.requests, 'Session', Session)
    with pytest.raises(ReviewBlocked): OpenAIReviewer('fixture-secret').respond(prepared[1]['body'])
    assert len(calls) == 1 and calls[0][0] == 'https://api.openai.com/v1/responses'
    assert calls[0][1]['allow_redirects'] is False and b'fixture-secret' not in calls[0][1]['data']
    assert json.loads(calls[0][1]['data']) == prepared[1]['body']


def test_committed_reservation_blocks_competitor_and_restart_reuses_completion(prepared):
    p, request = prepared; path = ledger_path(); calls = []
    first = AttemptLedger(path, 1)
    class Provider:
        def respond(self, body):
            competitor = AttemptLedger(path, 1)
            try:
                assert competitor.events(request['request_id'])['DISPATCH_RESERVED']
                with pytest.raises(ReviewBlocked, match='AMBIGUOUS'):
                    execute_once(competitor, p, request, self, lambda: NOW)
            finally: competitor.close()
            calls.append(body)
            return response(p)
    expected = execute_once(first, p, request, Provider(), lambda: NOW); first.close()
    restarted = AttemptLedger(path, 1)
    assert execute_once(restarted, p, request, Provider(), lambda: NOW) == expected
    assert len(calls) == 1
    restarted.close()


def test_timeout_keeps_barrier_and_call_budget(prepared):
    p, request = prepared; path = ledger_path(); ledger = AttemptLedger(path, 1); calls = []
    class LostReply:
        def respond(self, body): calls.append(body); raise TimeoutError('fixture credential must not be logged')
    with pytest.raises(ReviewBlocked): execute_once(ledger, p, request, LostReply(), lambda: NOW)
    with pytest.raises(ReviewBlocked, match='PREVIOUS'): execute_once(ledger, p, request, LostReply(), lambda: NOW)
    assert len(calls) == 1 and 'fixture credential' not in json.dumps(ledger.events(request['request_id']))
    other = deepcopy(request); other['body']['model'] = 'another-model'
    from research_reviewer import VERSION, PROMPT_VERSION
    other['request_id'] = digest(dict(version=VERSION, prompt_version=PROMPT_VERSION, body=other['body']))
    with pytest.raises(ReviewBlocked, match='BUDGET_EXHAUSTED'): ledger.claim(other, NOW)
    ledger.close()
    with pytest.raises(ReviewBlocked, match='BUDGET_DIFFERS'): AttemptLedger(path, 2)


def test_received_response_recovers_without_model_call(prepared):
    p, request = prepared; ledger = AttemptLedger(ledger_path(), 1)
    ledger.claim(request, NOW); ledger.record(request['request_id'], 'RECEIVED', response(p), NOW)
    class NoCalls:
        def respond(self, body): raise AssertionError('Must recover locally')
    result = execute_once(ledger, p, request, NoCalls(), lambda: NOW)
    assert result['provider_response_id'] == 'isolated-response'
    with pytest.raises(Exception): ledger.db.execute('delete from events')
    ledger.close()


def test_comparison_records_unsupported_positives_without_claiming_independent_acceptance(prepared):
    p, request = prepared; proposed = parse_response(p, request, response(p, 'SUPPORTED'), NOW)['review_artifact']
    reference = unresolved_draft(p, NOW); reference['reviewer_id'] = 'fixture-author'
    reference = validate_draft(p, reference, NOW)
    provenance = dict(assessor_id='fixture-author', method_version='fixture-only-v1',
                      created_before_model_response=True, independence_limitations=['Implementation-author fixture, not independent acceptance'])
    result = compare(p, proposed, reference, provenance, NOW)
    assert result['counts']['unsupported_positive_vs_reference'] == len(CRITERIA)
    assert result['counts']['criteria'] == len(CRITERIA)
    assert result['semantic_acceptance'] == 'NOT_ESTABLISHED' and not result['eligible_for_handoff']
    provenance['assessor_id'] = 'invented'
    with pytest.raises(ValueError): compare(p, proposed, reference, provenance, NOW)


def test_altered_packet_is_rejected_before_reservation(prepared):
    p, request = prepared; p['symbol'] = 'TAMPERED'
    ledger = AttemptLedger(ledger_path(), 1)
    with pytest.raises(ValueError): execute_once(ledger, p, request, None, lambda: NOW)
    assert ledger.db.execute('select count(*) n from requests').fetchone()['n'] == 0
    ledger.close()
