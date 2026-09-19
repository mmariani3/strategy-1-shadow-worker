"""Isolated infrastructure regressions, never genuine strategy observations."""
from copy import deepcopy
import json
import pytest

from evidence_review import canonical, digest
from research_gaps import (VERSIONS, FAILURE_CAPABILITY, DOCUMENT_AUTHORITY,
    prepare_gap_request, gap_schema)
from research_context import prepare_context_request
from research_citations import selectable_catalog
from research_reviewer import parse_response, ReviewBlocked
from review_attempts import AttemptLedger, execute_once
from test_evidence_review import authorities, snapshot, NOW
from test_research_reviewer import masters, ledger_path
from test_research_facts import fact_case, reply
from test_research_context import draft_for as context_draft, material as context_material, claim


def draft_for(p, supported=False):
    d = context_draft(p)
    if supported: context_material(d)
    c = d['materiality_coverage']
    c.pop('missing_documents')
    c.update(evidence_gaps=[], document_followups=[])
    d['verification_basis'] = 'UNRESOLVED'
    return d


def gap():
    return dict(missing_fact='Magnitude relative to capitalization', why_material='Needed for the proposed dilution impact assessment.',
        captured_evidence_limit='Captured amount alone does not establish the denominator.', evidence=[])


def followup():
    return dict(document='Referenced legal opinion', question='Does this document supply any relevant economic terms?',
        reason='Optional context only; absence does not establish necessity.', gap_index=None, evidence=[])


@pytest.fixture
def gap_case(fact_case, masters):
    p,_ = fact_case
    return p, prepare_gap_request(p, masters, 'offline-fixture', 12000, 250000, NOW)


@pytest.mark.parametrize('basis',['MISSING_CORROBORATION','SHARED_ORIGIN','DIFFERENT_EVENT','CONFLICT_REVIEW_REQUIRED','CORROBORATION_PROPOSED'])
def test_no_automatic_observed_failure_even_with_real_source_quotes(gap_case,basis):
    p,r=gap_case;d=draft_for(p);d['verification_basis']=basis
    claim(d,'same_event_verification').update(evidence_state='OBSERVED_FAILURE', evidence=d['target']['evidence'])
    with pytest.raises(ReviewBlocked,match='VERIFICATION_FAILURE_ADAPTER_UNAVAILABLE'):
        parse_response(p,r,reply(d),NOW)


@pytest.mark.parametrize('basis',['UNRESOLVED','MISSING_CORROBORATION','SHARED_ORIGIN','DIFFERENT_EVENT','CONFLICT_REVIEW_REQUIRED'])
def test_provenance_and_conflict_concerns_preserved_as_unresolved(gap_case,basis):
    p,r=gap_case;d=draft_for(p);d['verification_basis']=basis
    c=claim(d,'same_event_verification');c.update(rationale='Isolated observation requires further review.',evidence=d['target']['evidence'])
    out=parse_response(p,r,reply(d),NOW)
    assert out['research_binding']['verification_basis']==basis
    assert out['research_binding']['verification_failure_capability']==FAILURE_CAPABILITY
    assert next(c for c in out['review_artifact']['review']['claims'] if c['criterion']=='same_event_verification')['assessment']=='UNRESOLVED'
    assert not out['eligible_for_handoff']


def test_proposed_corroboration_keeps_existing_two_source_gate(gap_case):
    p,r=gap_case;d=draft_for(p)
    claim(d,'same_event_verification').update(evidence_state='OBSERVED_SUPPORT',evidence=d['target']['evidence'])
    with pytest.raises(ReviewBlocked,match='VERIFICATION_BASIS_CONFLICT'):parse_response(p,r,reply(d),NOW)
    d['verification_basis']='CORROBORATION_PROPOSED'
    with pytest.raises(ReviewBlocked,match='SAME_EVENT_REQUIRES_DISTINCT_SOURCES'):parse_response(p,r,reply(d),NOW)


def test_previously_admissible_two_source_failure_is_blocked_without_relabeling_history(gap_case,masters):
    p,r=gap_case;catalog=selectable_catalog(p);by_source={}
    for k,v in catalog.items():
        if v['category'] in {'NEWS_TEXT','DOCUMENT_TEXT'}:by_source.setdefault(v['source_id'],k)
    assert len(by_source)>=2
    refs=[dict(excerpt_id=k) for k in list(by_source.values())[:2]]
    old=context_draft(p)
    claim(old,'same_event_verification').update(evidence_state='OBSERVED_FAILURE',evidence=refs,rationale='No independent corroboration captured.')
    old_req=prepare_context_request(p,masters,'offline-fixture',12000,250000,NOW)
    preserved=parse_response(p,old_req,reply(old),NOW)
    new=draft_for(p);claim(new,'same_event_verification').update(claim(old,'same_event_verification'))
    new['verification_basis']='SHARED_ORIGIN'
    with pytest.raises(ReviewBlocked,match='VERIFICATION_FAILURE_ADAPTER_UNAVAILABLE'):parse_response(p,r,reply(new),NOW)
    assert parse_response(p,old_req,reply(old),NOW)==preserved


@pytest.mark.parametrize('count',[0,500,1001])
def test_expanded_schema_budget_fails_closed(gap_case,monkeypatch,count):
    import research_gaps as module
    p,_=gap_case;catalog={'E'+str(i).zfill(20):dict(category='DOCUMENT_TEXT') for i in range(count)}
    monkeypatch.setattr(module,'selectable_catalog',lambda p:catalog)
    with pytest.raises(ReviewBlocked):gap_schema(p)
    assert len(catalog)==count


def test_optional_absent_document_does_not_block_narrow_materiality(gap_case):
    p,r=gap_case;d=draft_for(p,True);c=d['materiality_coverage'];c['document_followups']=[followup()]
    out=parse_response(p,r,reply(d),NOW);record=out['materiality_evidence_coverage']
    assert record['status']=='SUFFICIENT_FOR_RESEARCH' and record['evidence_gaps']==[]
    assert record['document_followups'][0]['authority']==DOCUMENT_AUTHORITY
    assert record['document_followups'][0]['gap_id'] is None
    assert 'missing_documents' not in record and 'missing_document_reasons' not in record
    assert not out['eligible_for_handoff']


def test_real_fact_gap_blocks_materiality_and_keeps_linked_research_question(gap_case):
    p,r=gap_case;d=draft_for(p,True);c=d['materiality_coverage']
    c.update(status='INCOMPLETE',evidence_gaps=[gap()],document_followups=[dict(followup(),gap_index=0)])
    with pytest.raises(ReviewBlocked,match='MATERIALITY_COVERAGE_NOT_SUFFICIENT'):parse_response(p,r,reply(d),NOW)
    claim(d,'catalyst_materiality_tier')['evidence_state']='INSUFFICIENT_EVIDENCE'
    out=parse_response(p,r,reply(d),NOW);rec=out['materiality_evidence_coverage']
    assert rec['evidence_gaps'][0]['missing_fact']==gap()['missing_fact']
    assert rec['document_followups'][0]['gap_id']==rec['evidence_gaps'][0]['gap_id']
    assert rec['evidence_gaps'][0]['semantic_verification']=='NOT_ESTABLISHED'
    old=deepcopy(out);d['selected_event']['description']='Different event.'
    other=parse_response(p,r,reply(d),NOW)
    assert other['materiality_evidence_coverage']['evidence_gaps'][0]['gap_id']!=rec['evidence_gaps'][0]['gap_id'] and out==old


@pytest.mark.parametrize('bad',['document_only','sufficient_gap','legacy_required','authority_override','duplicate_gap','duplicate_followup',
    'empty_fact','empty_impact','empty_limit','empty_question','bad_gap','negative_gap','bool_gap','string_gap','gap_metadata','followup_metadata','unknown_ref','duplicate_ref'])
def test_gap_scope_and_followup_integrity(gap_case,bad):
    p,r=gap_case;d=draft_for(p);c=d['materiality_coverage']
    if bad=='document_only':c.update(status='INCOMPLETE',document_followups=[followup()])
    if bad=='sufficient_gap':c.update(status='SUFFICIENT_FOR_RESEARCH',evidence_gaps=[gap()],evidence=d['target']['evidence'])
    if bad=='legacy_required':c['missing_documents']=[dict(document='Legal opinion',reason='Absent')]
    if bad=='authority_override':c['document_followups']=[dict(followup(),required=True)]
    if bad=='duplicate_gap':c['evidence_gaps']=[gap(),gap()]
    if bad=='duplicate_followup':c['document_followups']=[followup(),followup()]
    if bad in ('empty_fact','empty_impact','empty_limit'):
        g=gap();g[{'empty_fact':'missing_fact','empty_impact':'why_material','empty_limit':'captured_evidence_limit'}[bad]]='  ';c['evidence_gaps']=[g]
    if bad=='empty_question':c['document_followups']=[dict(followup(),question='  ')]
    if bad in ('bad_gap','negative_gap','bool_gap','string_gap'):
        c['document_followups']=[dict(followup(),gap_index={'bad_gap':1,'negative_gap':-1,'bool_gap':True,'string_gap':'0'}[bad])]
    if bad in ('gap_metadata','followup_metadata','unknown_ref','duplicate_ref'):
        k=next(k for k,v in selectable_catalog(p).items() if v['category']=='PUBLICATION_METADATA')
        refs=[dict(excerpt_id=k)]
        if bad=='unknown_ref':refs=[dict(excerpt_id='Eunknown')]
        if bad=='duplicate_ref':refs=deepcopy(d['target']['evidence'])*2
        if bad=='followup_metadata':c['document_followups']=[dict(followup(),evidence=refs)]
        else:c['evidence_gaps']=[dict(gap(),evidence=refs)]
    with pytest.raises(ValueError):parse_response(p,r,reply(d),NOW)


@pytest.mark.parametrize('bad',['target','event','freshness_pass','freshness_fail','liquidity','publication_as_event','coverage_category'])
def test_existing_capability_and_binding_gates_stay_closed(gap_case,bad):
    p,r=gap_case;d=draft_for(p,True)
    if bad=='target':d['target']['symbol']='OTHER'
    if bad=='event':d['selected_event']['subject_symbol']='OTHER'
    if bad.startswith('freshness_'):claim(d,'catalyst_freshness').update(evidence_state='OBSERVED_SUPPORT' if bad.endswith('pass') else 'OBSERVED_FAILURE',evidence=d['target']['evidence'])
    if bad=='liquidity':claim(d,'liquidity').update(evidence_state='OBSERVED_SUPPORT',evidence=d['target']['evidence'])
    if bad in ('publication_as_event','coverage_category'):
        k=next(k for k,v in selectable_catalog(p).items() if v['category']=='PUBLICATION_METADATA')
        (d['selected_event'] if bad=='publication_as_event' else d['materiality_coverage'])['evidence']=[dict(excerpt_id=k)]
    with pytest.raises(ValueError):parse_response(p,r,reply(d),NOW)


def test_lossless_preparation_and_substantive_schema(gap_case,masters):
    p,r=gap_case;s=r['body']['text']['format']['schema'];catalog=selectable_catalog(p)
    assert all(catalog[k]['category'] in {'NEWS_TEXT','DOCUMENT_TEXT'} for k in s['$defs']['SubstantiveRef']['properties']['excerpt_id']['enum'])
    assert s['$defs']['Target']['properties']['evidence']['items']=={'$ref':'#/$defs/SubstantiveRef'}
    view=json.loads(r['body']['input'][-1]['content'].split('\n',1)[1])['packet']
    for source in view['sources']:source['raw']=json.loads(source['text'])
    assert view==p
    manifest=json.loads(r['body']['input'][0]['content'].split('GOVERNING_MASTERS:\n',1)[1].split('\nCRITERION_REFERENCES:',1)[0])
    assert all(manifest[k]['text']==v['text'] for k,v in masters.items())
    size=len(canonical(r['body']).encode())
    assert prepare_gap_request(p,masters,'offline-fixture',12000,size,NOW)==r
    with pytest.raises(ReviewBlocked,match='INPUT_LIMIT_EXCEEDED'):prepare_gap_request(p,masters,'offline-fixture',12000,size-1,NOW)


@pytest.mark.parametrize('tamper',['substantive_enum','evidence','target','format'])
def test_prebilling_binding_rejects_rehashed_tampering(gap_case,tamper):
    p,r=gap_case;r=deepcopy(r);fmt=r['body']['text']['format']
    if tamper=='substantive_enum':fmt['schema']['$defs']['SubstantiveRef']['properties']['excerpt_id']['enum'].append('Ewrong')
    if tamper=='evidence':r['body']['input'][-1]['content']+='changed'
    if tamper=='target':fmt['schema']['$defs']['Target']['properties']['symbol']['enum']=['OTHER']
    if tamper=='format':fmt['strict']=False
    r['request_id']=digest(dict(version=VERSIONS[0],prompt_version=VERSIONS[1],body=r['body']))
    class Forbidden:
        def respond(self,body):raise AssertionError('No network')
    ledger=AttemptLedger(ledger_path(),1)
    try:
        with pytest.raises(ReviewBlocked):execute_once(ledger,p,r,Forbidden(),lambda:NOW)
        assert ledger.db.execute('select count(*) from requests').fetchone()[0]==0
    finally:ledger.close()


def test_versioned_attribution_trace_and_durable_replay(gap_case,masters):
    p,r=gap_case;d=draft_for(p,True);response=reply(d);calls=[]
    old_req=prepare_context_request(p,masters,'offline-fixture',12000,250000,NOW)
    old=parse_response(p,old_req,reply(context_draft(p)),NOW)
    class Provider:
        def respond(self,body):calls.append(body);return response
    path=ledger_path();ledger=AttemptLedger(path,1)
    try:out=execute_once(ledger,p,r,Provider(),lambda:NOW)
    finally:ledger.close()
    ledger=AttemptLedger(path,1)
    try:assert execute_once(ledger,p,r,Provider(),lambda:NOW)==out and len(calls)==1
    finally:ledger.close()
    assert out['review_artifact']['trace']==p['trace']
    review=out['review_artifact']['review']
    assert (review['implementation_version'],review['prompt_version'])==VERSIONS
    assert old==parse_response(p,old_req,reply(context_draft(p)),NOW)


def test_default_cli_no_credentials_or_provider(gap_case,masters,monkeypatch,capsys):
    import run_research_reviewer as cli
    assert cli.prepare_request is prepare_gap_request
    p,_=gap_case;root=ledger_path().parent;pf=root/'p.json';mf=root/'m.json'
    pf.write_text(canonical(p),encoding='utf-8');mf.write_text(canonical(masters),encoding='utf-8')
    def forbidden(*args,**kwargs):raise AssertionError('No credential/provider access')
    monkeypatch.setattr(cli,'OpenAIReviewer',forbidden)
    monkeypatch.setattr(cli,'inspect_packet',lambda *args:dict(report_id='isolated-infrastructure',route='REVIEW_REQUIRED'))
    monkeypatch.setattr('sys.argv',['review','--packet',str(pf),'--masters',str(mf),'--model','offline-fixture',
        '--max-output-tokens','12000','--max-input-bytes','250000','--output',str(root)])
    cli.main();result=json.loads(capsys.readouterr().out)
    assert result['model_calls']==0 and not result['eligible_for_handoff']
    request=json.loads(__import__('pathlib').Path(result['request_file']).read_text())
    assert (request['implementation_version'],request['prompt_version'])==VERSIONS
