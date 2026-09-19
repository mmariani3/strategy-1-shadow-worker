"""Infrastructure-only v5 regressions; no billable calls or market observations."""
from copy import deepcopy
import json

import pytest

from evidence_review import canonical, digest, source
from research_citations import Selection, selectable_catalog
from research_coverage import (CoverageDraft, VERSIONS, SpanResolver,
                               prepare_coverage_request)
from research_reviewer import parse_response, ReviewBlocked
from review_attempts import AttemptLedger, execute_once
from test_evidence_review import authorities, snapshot, NOW
from test_research_reviewer import masters, ledger_path
from test_research_facts import fact_case, reply
from test_research_citations import selected


@pytest.fixture
def coverage_case(fact_case, masters):
    p, _ = fact_case
    return p, prepare_coverage_request(p, masters, 'offline-fixture', 12000, 250000, NOW)


def draft_for(p):
    d = selected(p)
    d['materiality_coverage'] = dict(status='UNRESOLVED', missing_documents=[],
        rationale='Isolated fixture: adequacy has not been assessed.', evidence=[])
    return d


def claim(d):
    return next(c for c in d['claims'] if c['criterion']=='catalyst_materiality_tier')


def test_distinct_clauses_reuse_anchor_with_precise_attribution(coverage_case):
    p, req = coverage_case; d = draft_for(p)
    anchor = d['facts'][0]['evidence'][0]['excerpt_id']
    d['facts'][0]['evidence'] = [dict(excerpt_id=anchor, supporting_text=t) for t in
        ['LOCALW is a warrant;', 'LOCAL is common stock.']]
    result = parse_response(p,req,reply(d),NOW)
    citations = result['fact_findings'][0]['citations']
    assert len(citations)==2 and citations[0]['start'] != citations[1]['start']
    audit = result['citation_selection_audit']['facts'][0]['spans']
    assert [r['anchor_excerpt_id'] for r in audit]==[anchor,anchor]
    assert result['eligible_for_handoff'] is False


def boundary_packet(p):
    p=deepcopy(p)
    text = ('Infrastructure-only context. '*40 + '\nOn\n' +
        'September 17, the fixture issuer published a patent announcement. '+
        'Additional isolated context. '*60)
    s=source('retrieved_document',{'text':text,'unrelated':'Unrelated isolated field.'},NOW)
    p['sources'].append(s)
    p['packet_id']=digest({k:v for k,v in p.items() if k!='packet_id'})
    return p,s


def test_boundary_spanning_quote_is_anchored_in_same_original_field(coverage_case):
    p,_=coverage_case; p,s=boundary_packet(p)
    resolver=SpanResolver(p)
    anchor=next(k for k,r in resolver.catalog.items() if r['source_id']==s['source_id'] and r['text'].startswith('September 17'))
    support='On\nSeptember 17, the fixture issuer published a patent announcement.'
    row=resolver.resolve([Selection(excerpt_id=anchor,supporting_text=support)])[0]
    assert row['start'] < resolver.catalog[anchor]['start']
    assert s['text'][row['start']:row['end']]==canonical(support)[1:-1]
    # A second anchor does not turn the same source location into new evidence.
    prior=next(k for k,r in resolver.catalog.items() if r['source_id']==s['source_id'] and r['text'].endswith('On\n'))
    with pytest.raises(ReviewBlocked,match='DUPLICATE_SOURCE_SPAN'):
        resolver.resolve([Selection(excerpt_id=k,supporting_text=support) for k in [prior,anchor]])


@pytest.mark.parametrize('kind', ['unrelated_field','unrelated_excerpt','altered_punctuation','duplicate'])
def test_boundary_support_does_not_weaken_exact_matching(coverage_case,kind):
    p,_=coverage_case; p,s=boundary_packet(p); resolver=SpanResolver(p)
    anchor=next(k for k,r in resolver.catalog.items() if r['source_id']==s['source_id'] and r['text'].startswith('September 17'))
    support='September 17, the fixture issuer published a patent announcement.'
    if kind=='unrelated_field': support='Unrelated isolated field.'
    if kind=='unrelated_excerpt':
        anchor=next(k for k,r in resolver.catalog.items() if r['source_id']==s['source_id'] and r['text'].endswith('On\n'))
    if kind=='altered_punctuation': support=support.replace(',', '\x19')
    selections=[Selection(excerpt_id=anchor,supporting_text=support)]
    if kind=='duplicate': selections *= 2
    with pytest.raises(ReviewBlocked): resolver.resolve(selections)


@pytest.mark.parametrize('status', ['INCOMPLETE','UNRESOLVED'])
@pytest.mark.parametrize('state', ['OBSERVED_SUPPORT','OBSERVED_FAILURE'])
def test_known_missing_exhibit_is_not_sufficient_materiality_evidence(coverage_case,status,state):
    p,req=coverage_case; d=draft_for(p)
    # The fact of missing evidence can be established without completing it.
    d['facts'][4]['finding']='The filing references an exhibit absent from the capture.'
    d['facts'][4]['status']='EVIDENCED'
    d['materiality_coverage'].update(status=status,missing_documents=['Exhibit 99.1'])
    claim(d).update(evidence_state=state,evidence=d['facts'][0]['evidence'])
    with pytest.raises(ReviewBlocked,match='MATERIALITY_COVERAGE_NOT_SUFFICIENT'):
        parse_response(p,req,reply(d),NOW)


def test_incomplete_coverage_preserves_useful_facts_without_materiality_conclusion(coverage_case):
    p,req=coverage_case; d=draft_for(p)
    d['materiality_coverage'].update(status='INCOMPLETE',missing_documents=['Exhibit 99.1'],
        evidence=d['facts'][4]['evidence'])
    result=parse_response(p,req,reply(d),NOW)
    assert result['fact_findings'][4]['status']=='EVIDENCED'
    assert result['materiality_evidence_coverage']['status']=='INCOMPLETE'
    assert result['review_artifact']['review']['claims'][1]['assessment']=='UNRESOLVED'


def test_sufficient_research_basis_can_pass_but_is_not_semantic_acceptance(coverage_case):
    p,req=coverage_case; d=draft_for(p)
    d['materiality_coverage'].update(status='SUFFICIENT_FOR_RESEARCH',evidence=d['facts'][0]['evidence'])
    claim(d).update(evidence_state='OBSERVED_SUPPORT',evidence=d['facts'][0]['evidence'])
    r=parse_response(p,req,reply(d),NOW)
    assert r['review_artifact']['review']['claims'][1]['assessment']=='SUPPORTED'
    assert r['materiality_evidence_coverage']['semantic_verification']=='NOT_ESTABLISHED'
    assert r['eligible_for_handoff'] is False


@pytest.mark.parametrize('bad', ['missing_contract','sufficient_with_missing','sufficient_without_citation',
    'incomplete_without_missing','empty_rationale','empty_document_name','metadata_coverage','unknown_anchor'])
def test_coverage_cannot_be_implicitly_promoted(coverage_case,bad):
    p,req=coverage_case; d=draft_for(p); c=d['materiality_coverage']
    if bad=='missing_contract': d.pop('materiality_coverage')
    if bad=='sufficient_with_missing': c.update(status='SUFFICIENT_FOR_RESEARCH',missing_documents=['Exhibit 99.1'],evidence=d['facts'][0]['evidence'])
    if bad=='sufficient_without_citation': c['status']='SUFFICIENT_FOR_RESEARCH'
    if bad=='incomplete_without_missing': c['status']='INCOMPLETE'
    if bad=='empty_rationale': c['rationale']=' '
    if bad=='empty_document_name': c['missing_documents']=[' ']
    if bad=='unknown_anchor': c['evidence']=[dict(excerpt_id='unknown',supporting_text='text')]
    if bad=='metadata_coverage':
        k,r=next((k,r) for k,r in selectable_catalog(p).items() if r['category']=='PUBLICATION_METADATA')
        c['evidence']=[dict(excerpt_id=k,supporting_text=r['text'])]
    with pytest.raises(ValueError): parse_response(p,req,reply(d),NOW)


@pytest.mark.parametrize('bad', ['capability','missing_fact','single_source','missing_topic','workflow'])
def test_existing_gates_remain_active(coverage_case,bad):
    p,req=coverage_case; d=draft_for(p)
    if bad=='capability':
        next(c for c in d['claims'] if c['criterion']=='macro_context').update(evidence_state='OBSERVED_SUPPORT',evidence=d['facts'][0]['evidence'])
    if bad=='missing_fact':
        d['facts'][2]['status']='UNRESOLVED'
        d['claims'][0].update(evidence_state='OBSERVED_SUPPORT',evidence=d['facts'][0]['evidence'])
    if bad=='single_source':
        next(c for c in d['claims'] if c['criterion']=='same_event_verification').update(evidence_state='OBSERVED_SUPPORT',evidence=d['facts'][0]['evidence'])
    if bad=='missing_topic': d['facts'].pop()
    if bad=='workflow':
        from research_facts import excerpt_catalog
        k,r=next((k,r) for k,r in excerpt_catalog(p).items() if r['category']=='WORKFLOW_METADATA')
        d['facts'][0]['evidence']=[dict(excerpt_id=k,supporting_text=r['text'])]
    with pytest.raises(ValueError): parse_response(p,req,reply(d),NOW)


def test_v5_schema_full_packet_and_byte_limit(coverage_case,masters):
    p,req=coverage_case
    view=json.loads(req['body']['input'][-1]['content'].split('\n',1)[1])
    for s in view['packet']['sources']: s['raw']=json.loads(s['text'])
    assert view['packet']==p
    schema=CoverageDraft.model_json_schema()
    assert schema['additionalProperties'] is False and 'materiality_coverage' in schema['required']
    assert all(d['additionalProperties'] is False and set(d['required'])==set(d['properties']) for d in schema['$defs'].values())
    size=len(canonical(req['body']).encode())
    assert prepare_coverage_request(p,masters,'offline-fixture',12000,size,NOW)==req
    with pytest.raises(ReviewBlocked,match='INPUT_LIMIT'):
        prepare_coverage_request(p,masters,'offline-fixture',12000,size-1,NOW)


def test_v5_replays_once_and_tampering_blocks_before_reservation(coverage_case):
    p,req=coverage_case; ledger=AttemptLedger(ledger_path(),1); calls=[]
    class Provider:
        def respond(self,body): calls.append(body); return reply(draft_for(p))
    try:
        bad=deepcopy(req);bad['body']['input'][-1]['content']+='altered'
        bad['request_id']=digest(dict(version=VERSIONS[0],prompt_version=VERSIONS[1],body=bad['body']))
        with pytest.raises(ReviewBlocked,match='EVIDENCE_MISMATCH'):
            execute_once(ledger,p,bad,Provider(),lambda:NOW)
        assert not calls and ledger.db.execute('select count(*) from requests').fetchone()[0]==0
        result=execute_once(ledger,p,req,Provider(),lambda:NOW)
        assert execute_once(ledger,p,req,Provider(),lambda:NOW)==result and len(calls)==1
    finally: ledger.close()
