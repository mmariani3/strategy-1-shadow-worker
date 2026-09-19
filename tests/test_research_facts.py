"""Infrastructure fixtures reproducing observed failures; no market observations."""
from copy import deepcopy
import json

import pytest

from evidence_review import CRITERIA, canonical, digest, source
from research_reviewer import ReviewBlocked, parse_response
from research_facts import (TOPICS, VERSIONS, CATALYST_CRITERIA, FactDraft,
    excerpt_catalog, fact_evidence_message, prepare_fact_request)
from review_attempts import AttemptLedger, execute_once
from test_evidence_review import authorities, snapshot, packet, NOW
from test_research_reviewer import masters, ledger_path


@pytest.fixture
def fact_case(snapshot, authorities, masters):
    p = packet(snapshot, authorities)
    p['sources'].append(source('retrieved_document', {'text':
        'ISOLATED INFRASTRUCTURE FIXTURE.\nLOCALW is a warrant; LOCAL is common stock. '
        'On September 17, the issuer announced a merger, previously agreed August 1. '
        'The announcement refers to financial statements in Exhibit 99.1, absent here. '
        'Exact quote: "A" with Unicode café 中文 and \\slashes.'}, NOW))
    p['packet_id'] = digest({k:v for k,v in p.items() if k != 'packet_id'})
    req = prepare_fact_request(p, masters, 'offline-fixture', 12000, 250000, NOW)
    return p, req


def draft_for(p):
    catalog = excerpt_catalog(p)
    document = next(k for k,v in catalog.items() if v['category']=='DOCUMENT_TEXT')
    return dict(facts=[dict(topic=t, status='EVIDENCED', finding='Isolated factual test claim.',
                           excerpt_ids=[document]) for t in TOPICS],
                claims=[dict(criterion=c, evidence_state='INSUFFICIENT_EVIDENCE',
                             rationale='Insufficient captured evidence; isolated test.', excerpt_ids=[]) for c in CRITERIA],
                limitations=['INFRASTRUCTURE_TEST only'])


def reply(d):
    return dict(id='fixture-response', status='completed', model='fixture-snapshot', output=[
        dict(type='message', role='assistant', status='completed',
             content=[dict(type='output_text', text=json.dumps(d))])])


def test_handles_recover_exact_escaped_quotes_without_changing_evidence(fact_case):
    p, req = fact_case; before = deepcopy(p)
    catalog = excerpt_catalog(p)
    result = parse_response(p, req, reply(draft_for(p)), NOW)
    assert p == before
    assert result['review_artifact']['review']['prompt_version'] == VERSIONS[1]
    assert result['fact_findings'][0]['citations'][0]['quote'].find('\\"A\\"') >= 0
    assert result['research_scope'] == 'DOCUMENT_FACTS_AND_CATALYST_ONLY'
    assert result['eligible_for_handoff'] is False
    assert result['review_artifact']['semantic_verification'] == 'NOT_ESTABLISHED'
    for row in catalog.values():
        text = next(s['text'] for s in p['sources'] if s['source_id']==row['source_id'])
        assert text[row['start']:row['end']] == row['quote'] and text.count(row['quote'])==1
    view = json.loads(req['body']['input'][-1]['content'].split('\n',1)[1])['packet']
    for s in view['sources']: s['raw'] = json.loads(s['text'])
    assert view == p
    schema = FactDraft.model_json_schema()
    assert set(schema['required'])==set(schema['properties'])
    assert all(x.get('additionalProperties') is False for x in schema['$defs'].values())


@pytest.mark.parametrize('criterion', sorted(set(CRITERIA)-CATALYST_CRITERIA))
@pytest.mark.parametrize('state', ['OBSERVED_SUPPORT','OBSERVED_FAILURE'])
def test_documents_cannot_clear_or_fail_unmeasured_criteria(fact_case, criterion, state):
    p, req = fact_case; d = draft_for(p)
    claim = next(c for c in d['claims'] if c['criterion']==criterion)
    claim.update(evidence_state=state, excerpt_ids=d['facts'][0]['excerpt_ids'])
    with pytest.raises(ReviewBlocked, match='OUTSIDE_DOCUMENT'):
        parse_response(p, req, reply(d), NOW)


@pytest.mark.parametrize('state', ['OBSERVED_SUPPORT','OBSERVED_FAILURE'])
def test_workflow_status_cannot_replace_substantive_evidence(fact_case, state):
    p, req = fact_case; d = draft_for(p); catalog = excerpt_catalog(p)
    metadata = next(k for k,v in catalog.items() if v['category']=='WORKFLOW_METADATA')
    d['claims'][0].update(evidence_state=state, excerpt_ids=[metadata])
    with pytest.raises(ReviewBlocked, match='SUBSTANTIVE_SOURCE'):
        parse_response(p, req, reply(d), NOW)


def test_publication_date_is_not_event_time(fact_case):
    p, req = fact_case; d = draft_for(p); catalog = excerpt_catalog(p)
    published = next(k for k,v in catalog.items() if v['category']=='PUBLICATION_METADATA')
    next(f for f in d['facts'] if f['topic']=='event_timing')['excerpt_ids'] = [published]
    with pytest.raises(ReviewBlocked, match='FACT_SUBSTANTIVE'):
        parse_response(p, req, reply(d), NOW)


@pytest.mark.parametrize('topic,criterion', [('event_timing','catalyst_freshness'),
    ('instrument_identity','catalyst_materiality_tier'),
    ('document_coverage','catalyst_materiality_tier'),('catalyst_event','catalyst_materiality_tier')])
def test_missing_required_facts_keep_catalyst_unresolved(fact_case, topic, criterion):
    p, req = fact_case; d = draft_for(p)
    next(f for f in d['facts'] if f['topic']==topic)['status']='UNRESOLVED'
    next(c for c in d['claims'] if c['criterion']==criterion).update(
        evidence_state='OBSERVED_SUPPORT', excerpt_ids=d['facts'][0]['excerpt_ids'])
    with pytest.raises(ReviewBlocked, match='REQUIRED_FACT_UNRESOLVED'):
        parse_response(p, req, reply(d), NOW)


def test_source_based_assessment_can_pass_but_does_not_establish_truth(fact_case):
    p, req = fact_case; d = draft_for(p)
    d['claims'][0].update(evidence_state='OBSERVED_SUPPORT', excerpt_ids=d['facts'][0]['excerpt_ids'])
    result = parse_response(p,req,reply(d),NOW)
    assert result['review_artifact']['review']['claims'][0]['assessment']=='SUPPORTED'
    assert result['review_artifact']['semantic_verification']=='NOT_ESTABLISHED'


@pytest.mark.parametrize('mutation', ['unknown_handle','master_id','duplicate_handle','missing_topic','duplicate_topic','extra_approval','single_source_match'])
def test_invalid_contract_never_becomes_review(fact_case, mutation):
    p, req = fact_case; d = draft_for(p)
    if mutation=='unknown_handle': d['facts'][0]['excerpt_ids']=['Eunknown']
    if mutation=='master_id': d['facts'][0]['excerpt_ids']=[p['authority_refs']['strategy']['document_id']]
    if mutation=='duplicate_handle': d['facts'][0]['excerpt_ids'] *= 2
    if mutation=='missing_topic': d['facts'].pop()
    if mutation=='duplicate_topic': d['facts'][0]['topic']=d['facts'][1]['topic']
    if mutation=='extra_approval': d['execution_enabled']=True
    if mutation=='single_source_match':
        next(c for c in d['claims'] if c['criterion']=='same_event_verification').update(
            evidence_state='OBSERVED_SUPPORT', excerpt_ids=d['facts'][0]['excerpt_ids'])
    with pytest.raises(ValueError): parse_response(p,req,reply(d),NOW)


def test_tampered_catalog_blocked_before_paid_reservation(fact_case):
    p, req = fact_case; view=json.loads(req['body']['input'][-1]['content'].split('\n',1)[1])
    next(iter(view['excerpt_catalog'].values()))['text']='altered evidence'
    req['body']['input'][-1]['content']='UNTRUSTED_CAPTURED_EVIDENCE_WITH_EXCERPTS_V1:\n'+canonical(view)
    req['request_id']=digest(dict(version=VERSIONS[0],prompt_version=VERSIONS[1],body=req['body']))
    ledger=AttemptLedger(ledger_path(),1)
    try:
        with pytest.raises(ReviewBlocked,match='EVIDENCE_MISMATCH'): execute_once(ledger,p,req,None,lambda:NOW)
        assert ledger.db.execute('select count(*) from requests').fetchone()[0]==0
    finally: ledger.close()


def test_v3_completed_response_replays_without_new_call(fact_case):
    p, req = fact_case; ledger=AttemptLedger(ledger_path(),1); calls=[]
    class Provider:
        def respond(self,body): calls.append(body); return reply(draft_for(p))
    try:
        first=execute_once(ledger,p,req,Provider(),lambda:NOW)
        assert execute_once(ledger,p,req,Provider(),lambda:NOW)==first
        assert len(calls)==1
    finally: ledger.close()


def test_new_input_limit_accounts_for_catalog_without_truncation(fact_case, masters):
    p, req=fact_case; size=len(canonical(req['body']).encode('utf-8'))
    assert prepare_fact_request(p,masters,'offline-fixture',12000,size,NOW)==req
    with pytest.raises(ReviewBlocked,match='INPUT_LIMIT'):
        prepare_fact_request(p,masters,'offline-fixture',12000,size-1,NOW)
