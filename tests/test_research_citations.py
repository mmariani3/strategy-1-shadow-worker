"""Isolated infrastructure regressions; no production observations or paid calls."""
import json
from copy import deepcopy

import pytest

from evidence_review import canonical, digest, source
from research_citations import (VERSIONS, SelectedDraft, prepare_selection_request,
                               selectable_catalog)
from research_facts import excerpt_catalog
from research_reviewer import parse_response, ReviewBlocked
from review_attempts import AttemptLedger, execute_once
from test_evidence_review import authorities, snapshot, NOW
from test_research_reviewer import masters, ledger_path
from test_research_facts import fact_case, draft_for, reply


@pytest.fixture
def selection_case(fact_case, masters):
    p, _ = fact_case
    return p, prepare_selection_request(p, masters, 'offline-fixture', 12000, 250000, NOW)


def selected(p):
    d = draft_for(p)
    catalog = selectable_catalog(p)
    for group in ('facts', 'claims'):
        for item in d[group]:
            item['evidence'] = [dict(excerpt_id=k, supporting_text=catalog[k]['text'])
                                for k in item.pop('excerpt_ids')]
    return d


def test_positive_support_is_precise_and_research_only(selection_case):
    p, req = selection_case; d = selected(p)
    text = 'LOCALW is a warrant; LOCAL is common stock.'
    d['facts'][0]['evidence'][0]['supporting_text'] = text
    d['claims'][0].update(evidence_state='OBSERVED_SUPPORT', evidence=d['facts'][2]['evidence'])
    result = parse_response(p, req, reply(d), NOW)
    assert result['fact_findings'][0]['citations'][0]['quote'] == text
    assert result['review_artifact']['review']['claims'][0]['assessment'] == 'SUPPORTED'
    assert result['eligible_for_handoff'] is False
    assert result['review_artifact']['semantic_verification'] == 'NOT_ESTABLISHED'
    assert result['prompt_version'] == VERSIONS[1]


@pytest.mark.parametrize('case', ['bb_timing', 'lpbbw_mixed_identity', 'lpbbw_wrong_publication'])
def test_observed_workflow_citation_failures_remain_rejected(selection_case, case):
    p, req = selection_case; d = selected(p)
    workflow = next(k for k, r in excerpt_catalog(p).items() if r['category']=='WORKFLOW_METADATA')
    index = {'bb_timing': 2, 'lpbbw_mixed_identity': 0, 'lpbbw_wrong_publication': 3}[case]
    selection = dict(excerpt_id=workflow, supporting_text='Announcement and publication text from another passage.')
    if case == 'lpbbw_mixed_identity': d['facts'][index]['evidence'].append(selection)
    else: d['facts'][index]['evidence'] = [selection]
    with pytest.raises(ReviewBlocked, match='EXCERPT_NOT_SELECTABLE'):
        parse_response(p, req, reply(d), NOW)


@pytest.mark.parametrize('support', ['', '   ', 'This clause exists in another document.'])
def test_wrong_or_empty_support_cannot_pass_with_real_handle(selection_case, support):
    p, req = selection_case; d = selected(p)
    d['facts'][0]['evidence'][0]['supporting_text'] = support
    with pytest.raises(ReviewBlocked, match='SUPPORT_TEXT_EXCERPT_MISMATCH'):
        parse_response(p, req, reply(d), NOW)


def test_actual_other_passage_is_not_support_for_selected_handle(selection_case, masters):
    p, _ = selection_case; p = deepcopy(p)
    p['sources'].append(source('retrieved_document', {'text': 'Separate isolated fixture: the issuer published results.'}, NOW))
    p['packet_id'] = digest({k:v for k,v in p.items() if k != 'packet_id'})
    req = prepare_selection_request(p, masters, 'offline-fixture', 12000, 250000, NOW)
    d = selected(p)
    d['facts'][0]['evidence'][0]['supporting_text'] = 'the issuer published results.'
    with pytest.raises(ReviewBlocked, match='SUPPORT_TEXT_EXCERPT_MISMATCH'):
        parse_response(p, req, reply(d), NOW)


def test_short_quote_must_have_unambiguous_original_source_location(selection_case, masters):
    p, _ = selection_case; p = deepcopy(p)
    p['sources'].append(source('retrieved_document', {'text': 'fixture repeated clause; fixture repeated clause.'}, NOW))
    p['packet_id'] = digest({k:v for k,v in p.items() if k != 'packet_id'})
    req = prepare_selection_request(p, masters, 'offline-fixture', 12000, 250000, NOW)
    d = selected(p)
    handle = next(k for k,r in selectable_catalog(p).items() if r['text'].startswith('fixture repeated'))
    d['facts'][0]['evidence'] = [dict(excerpt_id=handle, supporting_text='fixture repeated clause')]
    with pytest.raises(ReviewBlocked, match='SUPPORT_TEXT_NOT_UNIQUE'):
        parse_response(p, req, reply(d), NOW)


def test_publication_metadata_valid_for_publication_but_not_event(selection_case):
    p, req = selection_case; d = selected(p)
    k, r = next((k,r) for k,r in selectable_catalog(p).items() if r['category']=='PUBLICATION_METADATA')
    selection = dict(excerpt_id=k, supporting_text=r['text'])
    d['facts'][3]['evidence'] = [selection]
    assert parse_response(p, req, reply(d), NOW)['eligible_for_handoff'] is False
    d['facts'][2]['evidence'] = [selection]
    with pytest.raises(ReviewBlocked, match='FACT_SUBSTANTIVE_SOURCE_REQUIRED'):
        parse_response(p, req, reply(d), NOW)


@pytest.mark.parametrize('mutation,code', [('capability','OUTSIDE_DOCUMENT'), ('missing_fact','REQUIRED_FACT'),
    ('duplicate','UNKNOWN_OR_DUPLICATE'), ('single_source','SAME_EVENT'), ('missing_topic','FACT_TOPICS')])
def test_v3_gates_are_preserved(selection_case, mutation, code):
    p, req = selection_case; d = selected(p)
    if mutation == 'capability':
        next(c for c in d['claims'] if c['criterion']=='macro_context').update(
            evidence_state='OBSERVED_SUPPORT', evidence=d['facts'][0]['evidence'])
    if mutation == 'missing_fact':
        d['facts'][2]['status']='UNRESOLVED'
        d['claims'][0].update(evidence_state='OBSERVED_SUPPORT', evidence=d['facts'][0]['evidence'])
    if mutation == 'duplicate': d['facts'][0]['evidence'] *= 2
    if mutation == 'single_source':
        next(c for c in d['claims'] if c['criterion']=='same_event_verification').update(
            evidence_state='OBSERVED_SUPPORT', evidence=d['facts'][0]['evidence'])
    if mutation == 'missing_topic': d['facts'].pop()
    with pytest.raises(ReviewBlocked, match=code): parse_response(p, req, reply(d), NOW)


def test_full_packet_preserved_schema_strict_and_size_checked(selection_case, masters):
    p, req = selection_case
    view = json.loads(req['body']['input'][-1]['content'].split('\n',1)[1])
    assert all(r['category'] not in {'WORKFLOW_METADATA','MARKET_SNAPSHOT'} for r in view['selectable_excerpts'].values())
    for s in view['packet']['sources']: s['raw'] = json.loads(s['text'])
    assert view['packet'] == p
    schema = SelectedDraft.model_json_schema()
    assert schema['additionalProperties'] is False
    assert all(d['additionalProperties'] is False and set(d['required']) == set(d['properties']) for d in schema['$defs'].values())
    size = len(canonical(req['body']).encode())
    assert prepare_selection_request(p, masters, 'offline-fixture',12000,size,NOW)==req
    with pytest.raises(ReviewBlocked, match='INPUT_LIMIT'):
        prepare_selection_request(p, masters, 'offline-fixture',12000,size-1,NOW)


def test_modified_evidence_cannot_reserve_paid_call(selection_case):
    p, req = selection_case; req = deepcopy(req)
    req['body']['input'][-1]['content'] += 'altered'
    req['request_id'] = digest(dict(version=VERSIONS[0],prompt_version=VERSIONS[1],body=req['body']))
    ledger = AttemptLedger(ledger_path(),1)
    try:
        with pytest.raises(ReviewBlocked, match='EVIDENCE_MISMATCH'):
            execute_once(ledger,p,req,None,lambda:NOW)
        assert ledger.db.execute('select count(*) from requests').fetchone()[0]==0
    finally: ledger.close()


def test_v4_replay_does_not_dispatch_twice(selection_case):
    p, req = selection_case; ledger = AttemptLedger(ledger_path(),1); calls=[]
    class Provider:
        def respond(self,body): calls.append(body); return reply(selected(p))
    try:
        result = execute_once(ledger,p,req,Provider(),lambda:NOW)
        assert execute_once(ledger,p,req,Provider(),lambda:NOW)==result
        assert len(calls)==1
    finally: ledger.close()
