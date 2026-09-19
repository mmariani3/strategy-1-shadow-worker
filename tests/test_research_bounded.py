"""Isolated v7 infrastructure regressions. No API calls or strategy observations."""
from copy import deepcopy
import json

import pytest

from evidence_review import canonical, digest
from research_bounded import VERSIONS, bounded_schema, prepare_bounded_request
from research_citations import selectable_catalog
from research_facts import excerpt_catalog
from research_scoped import prepare_scoped_request
from research_reviewer import parse_response, ReviewBlocked
from review_attempts import AttemptLedger, execute_once
from test_evidence_review import authorities, snapshot, NOW
from test_research_reviewer import masters, ledger_path
from test_research_facts import fact_case, reply
from test_research_scoped import draft_for as scoped_draft, repeated_packet, anchors


def draft_for(p):
    draft = scoped_draft(p)
    coverage = draft['materiality_coverage']
    coverage['missing_documents'] = coverage.pop('missing_document_reasons')
    return draft


@pytest.fixture
def bounded_case(fact_case, masters):
    packet, _ = fact_case
    return packet, prepare_bounded_request(packet, masters, 'offline-fixture', 12000, 250000, NOW)


def test_full_packet_bound_schema_and_unchanged_evidence(bounded_case, masters):
    packet, request = bounded_case
    before = deepcopy(packet)
    schema = request['body']['text']['format']['schema']
    ids = schema['$defs']['Selection']['properties']['excerpt_id']['enum']
    assert ids == sorted(selectable_catalog(packet))
    assert set(excerpt_catalog(packet)) - set(ids)  # Nonselectable context still present.
    assert 'missing_document_reasons' not in schema['$defs']['UnifiedCoverage']['properties']
    assert schema['additionalProperties'] is False
    assert all(s['additionalProperties'] is False and set(s['required']) == set(s['properties'])
               for s in schema['$defs'].values())
    old = prepare_scoped_request(packet, masters, 'offline-fixture', 12000, 250000, NOW)
    assert old['body']['input'][-1] == request['body']['input'][-1]
    assert old['request_id'] != request['request_id'] and packet == before
    size = len(canonical(request['body']).encode('utf-8'))
    assert prepare_bounded_request(packet, masters, 'offline-fixture', 12000, size, NOW) == request
    with pytest.raises(ReviewBlocked, match='INPUT_LIMIT_EXCEEDED_NO_TRUNCATION'):
        prepare_bounded_request(packet, masters, 'offline-fixture', 12000, size - 1, NOW)


@pytest.mark.parametrize('count,width,blocked', [(0,21,True),(714,21,False),(715,21,True),(1001,5,True)])
def test_schema_limits_never_truncate_catalog(bounded_case, monkeypatch, count, width, blocked):
    import research_bounded as module
    packet, _ = bounded_case
    handles = {('E'+str(i).zfill(width-1)): {} for i in range(count)}
    monkeypatch.setattr(module, 'selectable_catalog', lambda p: handles)
    if blocked:
        with pytest.raises(ReviewBlocked, match='NO_SELECTABLE_EVIDENCE|SCHEMA_LIMIT_EXCEEDED_NO_TRUNCATION'):
            bounded_schema(packet)
    else:
        assert bounded_schema(packet)['$defs']['Selection']['properties']['excerpt_id']['enum'] == sorted(handles)
    assert len(handles) == count


@pytest.mark.parametrize('bad', ['unknown_id','wrong_quote','empty_quote','extra_offset'])
def test_provider_cannot_bypass_exact_citation_validation(bounded_case, bad):
    packet, request = bounded_case
    draft = draft_for(packet)
    selection = draft['facts'][0]['evidence'][0]
    if bad == 'unknown_id': selection['excerpt_id'] = 'Emissing_one_character'
    if bad == 'wrong_quote': selection['supporting_text'] = 'Invented text not in the source.'
    if bad == 'empty_quote': selection['supporting_text'] = ' '
    if bad == 'extra_offset': selection['start'] = 0
    with pytest.raises(ValueError): parse_response(packet, request, reply(draft), NOW)


def test_anchored_occurrence_is_preserved_through_v7(bounded_case, masters):
    packet, _ = bounded_case
    packet, source = repeated_packet(packet)
    excerpt_id, anchor = anchors(packet, source, 'Repeated title.')[1]
    request = prepare_bounded_request(packet, masters, 'offline-fixture', 12000, 250000, NOW)
    draft = draft_for(packet)
    selection = dict(excerpt_id=excerpt_id, supporting_text='Repeated title.')
    draft['facts'][0]['evidence'] = [selection]
    draft['claims'][0].update(evidence_state='OBSERVED_SUPPORT', evidence=[selection])
    result = parse_response(packet, request, reply(draft), NOW)
    cite = result['review_artifact']['review']['claims'][0]['citations'][0]
    assert anchor['start'] <= cite['start'] < anchor['end']
    assert cite['start'] > source['text'].find('Repeated title.')
    assert source['text'][cite['start']:cite['end']] == cite['quote']
    assert result['eligible_for_handoff'] is False


def incomplete(draft):
    draft['materiality_coverage'].update(status='INCOMPLETE', missing_documents=[dict(
        document='Financial terms', reason='Necessary economics are absent from the captured announcement.')])
    return draft


def test_one_document_reason_pair_derives_compatibility_fields_without_guessing(bounded_case, masters):
    packet, request = bounded_case
    draft = incomplete(draft_for(packet)); before = deepcopy(draft)
    result = parse_response(packet, request, reply(draft), NOW)
    coverage = result['materiality_evidence_coverage']
    assert coverage['missing_documents'] == ['Financial terms']
    assert coverage['missing_document_reasons'] == draft['materiality_coverage']['missing_documents']
    assert coverage['semantic_verification'] == 'NOT_ESTABLISHED'
    assert draft == before and result['eligible_for_handoff'] is False
    old = scoped_draft(packet)
    old['materiality_coverage'].update(status='INCOMPLETE', missing_documents=['Financial terms'],
        missing_document_reasons=[dict(document='Financial transaction terms', reason='Terms are absent.')])
    old_req = prepare_scoped_request(packet, masters, 'offline-fixture', 12000, 250000, NOW)
    with pytest.raises(ReviewBlocked, match='MISSING_DOCUMENT_REASON_MISMATCH'):
        parse_response(packet, old_req, reply(old), NOW)


@pytest.mark.parametrize('bad', ['blank_document','blank_reason','duplicate','sufficient_with_missing',
    'incomplete_without_missing','old_two_lists','missing_field','missing_scope'])
def test_invalid_coverage_still_fails(bounded_case, bad):
    packet, request = bounded_case
    draft = incomplete(draft_for(packet)); coverage = draft['materiality_coverage']
    if bad == 'blank_document': coverage['missing_documents'][0]['document'] = ' '
    if bad == 'blank_reason': coverage['missing_documents'][0]['reason'] = ' '
    if bad == 'duplicate': coverage['missing_documents'] *= 2
    if bad == 'sufficient_with_missing': coverage.update(status='SUFFICIENT_FOR_RESEARCH', evidence=draft['facts'][0]['evidence'])
    if bad == 'incomplete_without_missing': coverage['missing_documents'] = []
    if bad == 'old_two_lists': coverage['missing_document_reasons'] = []
    if bad == 'missing_field': coverage.pop('missing_documents')
    if bad == 'missing_scope': coverage.pop('assessment_scope')
    with pytest.raises(ValueError): parse_response(packet, request, reply(draft), NOW)


@pytest.mark.parametrize('bad', ['capability','materiality','same_source','missing_topic','metadata'])
def test_substantive_gates_remain_independent_of_format(bounded_case, bad):
    packet, request = bounded_case
    draft = incomplete(draft_for(packet))
    criterion = {'capability':'liquidity','materiality':'catalyst_materiality_tier','same_source':'same_event_verification'}.get(bad)
    if criterion:
        next(c for c in draft['claims'] if c['criterion'] == criterion).update(
            evidence_state='OBSERVED_SUPPORT', evidence=draft['facts'][0]['evidence'])
    if bad == 'missing_topic': draft['facts'].pop()
    if bad == 'metadata':
        key, row = next((k,r) for k,r in selectable_catalog(packet).items() if r['category'] == 'PUBLICATION_METADATA')
        draft['materiality_coverage']['evidence'] = [dict(excerpt_id=key,supporting_text=row['text'])]
    with pytest.raises(ValueError): parse_response(packet, request, reply(draft), NOW)


@pytest.mark.parametrize('tamper', ['remove_enum','add_id','strict_false','foreign_schema'])
def test_rehashed_schema_tamper_fails_before_reservation(bounded_case, tamper):
    packet, request = bounded_case
    request = deepcopy(request); fmt = request['body']['text']['format']
    prop = fmt['schema']['$defs']['Selection']['properties']['excerpt_id']
    if tamper == 'remove_enum': prop.pop('enum')
    if tamper == 'add_id': prop['enum'].append('Eforeign')
    if tamper == 'strict_false': fmt['strict'] = False
    if tamper == 'foreign_schema': fmt['schema'] = {}
    request['request_id'] = digest(dict(version=VERSIONS[0],prompt_version=VERSIONS[1],body=request['body']))
    class Forbidden:
        def respond(self, body): raise AssertionError('Must fail before provider dispatch')
    ledger = AttemptLedger(ledger_path(),1)
    try:
        with pytest.raises(ReviewBlocked, match='PACKET_BOUND_SCHEMA_MISMATCH'):
            execute_once(ledger,packet,request,Forbidden(),lambda:NOW)
        assert ledger.db.execute('select count(*) from requests').fetchone()[0] == 0
        with pytest.raises(ReviewBlocked, match='PACKET_BOUND_SCHEMA_MISMATCH'):
            parse_response(packet,request,reply(draft_for(packet)),NOW)
    finally: ledger.close()


def test_original_response_and_attribution_survive_restart(bounded_case):
    packet, request = bounded_case; path = ledger_path(); calls = []
    response = reply(incomplete(draft_for(packet)))
    class Provider:
        def respond(self, body): calls.append(body); return response
    ledger = AttemptLedger(path,1)
    try: result = execute_once(ledger,packet,request,Provider(),lambda:NOW)
    finally: ledger.close()
    ledger = AttemptLedger(path,1)
    try:
        assert execute_once(ledger,packet,request,Provider(),lambda:NOW) == result and len(calls) == 1
        assert ledger.events(request['request_id'])['RECEIVED']['payload'] == response
        attribution = result['review_artifact']['review']
        assert (attribution['implementation_version'],attribution['prompt_version']) == VERSIONS
        assert result['eligible_for_handoff'] is False
    finally: ledger.close()


@pytest.mark.parametrize('mock_review_route', [False,True])
def test_cli_defaults_v7_and_preparation_never_loads_key_or_dispatches(bounded_case,masters,monkeypatch,capsys,mock_review_route):
    import run_research_reviewer as cli
    assert cli.prepare_request is prepare_bounded_request
    packet, _ = bounded_case; root = ledger_path().parent
    packet_file = root/'packet.json'; master_file = root/'masters.json'
    packet_file.write_text(canonical(packet),encoding='utf-8')
    master_file.write_text(canonical(masters),encoding='utf-8')
    def forbidden(*args, **kwargs): raise AssertionError('No credential access or API calls during preparation')
    monkeypatch.setattr(cli,'OpenAIReviewer',forbidden)
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    if mock_review_route:
        monkeypatch.setattr(cli,'inspect_packet',lambda *args:dict(report_id='isolated-mock',route='REVIEW_REQUIRED'))
    monkeypatch.setattr('sys.argv',['review','--packet',str(packet_file),'--masters',str(master_file),
        '--model','offline-fixture','--max-output-tokens','12000','--max-input-bytes','250000','--output',str(root)])
    cli.main(); printed = json.loads(capsys.readouterr().out)
    assert printed['model_calls'] == 0
    if mock_review_route:
        assert printed['status'] == 'PREPARED_NOT_SENT'
        request = json.loads(__import__('pathlib').Path(printed['request_file']).read_text(encoding='utf-8'))
        assert (request['implementation_version'],request['prompt_version']) == VERSIONS
    else: assert printed['status'] == 'EXCLUDED_INFRASTRUCTURE'
    assert json.loads(packet_file.read_text(encoding='utf-8')) == packet
