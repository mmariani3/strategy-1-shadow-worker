"""Isolated infrastructure tests; no provider calls or strategy observations."""
from copy import deepcopy
import json

import pytest

from evidence_review import canonical, digest, source
from research_reviewer import (LEGACY_VERSIONS, ReviewBlocked, evidence_message,
                               prepare_request, parse_response)
from review_attempts import AttemptLedger, execute_once
from test_evidence_review import authorities, snapshot, packet, NOW
from test_research_reviewer import masters, prepared, response, ledger_path


def reidentify(p):
    p['packet_id'] = digest({k:v for k,v in p.items() if k != 'packet_id'})


def test_lossless_view_preserves_unicode_nested_records_citations_and_original(prepared):
    p, _ = prepared
    p['sources'].append(source('retrieved_document', {
        'text': 'Exact Unicode: café 中文 😀\nquotes " and \\slashes',
        'nested': {'zero': 0, 'false': False, 'missing': None, 'ratio': 1.25},
        'items': ['negative evidence', 'do not discard'],
    }, NOW))
    reidentify(p); original = deepcopy(p)
    view = json.loads(evidence_message(p)['content'].split('\n',1)[1])
    assert p == original
    assert all('raw' not in s for s in view['sources'])
    assert [s['text'] for s in view['sources']] == [s['text'] for s in p['sources']]
    for s in view['sources']: s['raw'] = json.loads(s['text'])
    assert canonical(view) == canonical(p)
    assert digest({k:v for k,v in view.items() if k != 'packet_id'}) == p['packet_id']


@pytest.mark.parametrize('change', ['text', 'raw', 'source_id', 'duplicate', 'packet_id'])
def test_conflicting_copies_or_identity_fail_closed(prepared, change):
    p, _ = prepared
    if change == 'text': p['sources'][0]['text'] += ' hidden contradiction'
    if change == 'raw': p['sources'][0]['raw']['unexpected'] = 'do not drop'
    if change == 'source_id': p['sources'][0]['source_id'] = 'wrong'
    if change == 'duplicate': p['sources'].append(deepcopy(p['sources'][0]))
    if change != 'packet_id': reidentify(p)
    else: p['packet_id'] = 'wrong'
    with pytest.raises(ReviewBlocked): evidence_message(p)


def test_capacity_boundary_keeps_full_text_including_last_character(snapshot, authorities, masters):
    p = packet(snapshot, authorities)
    p['sources'].append(source('retrieved_document', {'text': 'A'*130000+'END_MARKER'}, NOW))
    reidentify(p)
    req = prepare_request(p,masters,'fixture',1000,250000,NOW)
    assert 'END_MARKER' in req['body']['input'][-1]['content']
    assert len(canonical(req['body']).encode('utf-8')) < 250000
    old_body = deepcopy(req['body']); old_body['input'][-1] = evidence_message(p,False)
    assert len(canonical(old_body).encode('utf-8')) > 250000
    exact = len(canonical(req['body']).encode('utf-8'))
    assert prepare_request(p,masters,'fixture',1000,exact,NOW) == req
    with pytest.raises(ReviewBlocked,match='INPUT_LIMIT'):
        prepare_request(p,masters,'fixture',1000,exact-1,NOW)


def test_request_tampering_stops_before_call_reservation(prepared):
    p, request = prepared
    view = json.loads(request['body']['input'][-1]['content'].split('\n',1)[1])
    view['sources'].pop()
    request['body']['input'][-1]['content'] = 'UNTRUSTED_CAPTURED_EVIDENCE_LOSSLESS_V1:\n'+canonical(view)
    request['request_id'] = digest(dict(version=request['implementation_version'],
        prompt_version=request['prompt_version'],body=request['body']))
    ledger = AttemptLedger(ledger_path(),1)
    try:
        with pytest.raises(ReviewBlocked,match='EVIDENCE_MISMATCH'):
            execute_once(ledger,p,request,None,lambda:NOW)
        assert ledger.db.execute('select count(*) from requests').fetchone()[0] == 0
    finally: ledger.close()


def test_legacy_received_and_completed_history_recovers_without_relabel_or_calls(prepared):
    p, request = prepared
    request['implementation_version'], request['prompt_version'] = LEGACY_VERSIONS
    request['body']['input'][-1] = evidence_message(p,False)
    request['request_id'] = digest(dict(version=request['implementation_version'],
        prompt_version=request['prompt_version'],body=request['body']))
    path = ledger_path(); ledger = AttemptLedger(path,1)
    ledger.claim(request,NOW); ledger.record(request['request_id'],'RECEIVED',response(p,'SUPPORTED'),NOW)
    class NeverCall:
        def respond(self,body): raise AssertionError('Historical recovery must be offline')
    result = execute_once(ledger,p,request,NeverCall(),lambda:NOW)
    assert result['review_artifact']['review']['implementation_version'] == LEGACY_VERSIONS[0]
    assert result['review_artifact']['review']['prompt_version'] == LEGACY_VERSIONS[1]
    ledger.close(); ledger = AttemptLedger(path,1)
    try:
        assert execute_once(ledger,p,request,NeverCall(),lambda:NOW) == result
        assert not result['eligible_for_handoff']
    finally: ledger.close()


def test_unknown_version_cannot_reserve_or_relabel_response(prepared):
    p, request = prepared; request['implementation_version'] = 'future-unknown'
    ledger = AttemptLedger(ledger_path(),1)
    try:
        with pytest.raises(ReviewBlocked,match='UNSUPPORTED_REQUEST_VERSION'): ledger.claim(request,NOW)
        with pytest.raises(ReviewBlocked,match='UNSUPPORTED_REQUEST_VERSION'):
            parse_response(p,request,response(p),NOW)
        assert ledger.db.execute('select count(*) from requests').fetchone()[0] == 0
    finally: ledger.close()
