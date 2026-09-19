"""Synthetic infrastructure cases; structural admission is not semantic truth."""
from copy import deepcopy
import json
import pytest
from evidence_review import canonical,digest
from research_subjects import VERSIONS,prepare_subject_request,subject_schema
from research_gaps import prepare_gap_request
from research_reviewer import parse_response,ReviewBlocked
from research_citations import selectable_catalog
from review_attempts import AttemptLedger,execute_once
from test_evidence_review import authorities,snapshot,NOW
from test_research_reviewer import masters,ledger_path
from test_research_facts import fact_case,reply
from test_research_gaps import draft_for as old_draft,gap,followup
from test_research_context import claim


def draft_for(p,supported=False):
    d=old_draft(p,supported);e=d['selected_event'];symbol=e.pop('subject_symbol')
    e['subject']=dict(kind='ISSUER',name='Fixture issuer',symbol=symbol,evidence=deepcopy(e['evidence']))
    roles={'instrument_identity':'TARGET','catalyst_event':'EVENT','event_timing':'EVENT',
        'publication_timing':'PUBLICATION','document_coverage':'TARGET'}
    for f in d['facts']:
        f.pop('subject_symbol');f['subject_role']=roles[f['topic']]
    return d


def organization(d,kind='ORGANIZATION'):
    e=d['selected_event'];e['subject'].update(kind=kind,name='Fixture central bank',symbol=None)
    e['relationship']='READ_THROUGH'
    return d


@pytest.fixture
def subject_case(fact_case,masters):
    p,_=fact_case
    return p,prepare_subject_request(p,masters,'offline-fixture',12000,250000,NOW)


@pytest.mark.parametrize('kind',['ORGANIZATION','ECONOMIC_EVENT'])
def test_named_nonticker_subject_no_symbol_leak_and_stable_trace(subject_case,kind):
    p,r=subject_case;d=organization(draft_for(p),kind)
    out=parse_response(p,r,reply(d),NOW);b=out['research_binding']
    assert b['selected_event']['subject']==d['selected_event']['subject']
    assert b['selected_event']['subject']['symbol'] is None
    assert b['event_subject_id'] and b['subject_citations']
    assert 'internal-subject:' not in canonical(out)
    assert 'subject_symbol' not in b['selected_event']
    assert all('subject_symbol' not in f for f in out['fact_findings'])
    assert all(f['event_subject_id']==b['event_subject_id'] for f in out['fact_findings'] if f['subject_role']=='EVENT')
    assert all(f['selected_event_id']==b['selected_event_id'] for f in out['fact_findings'])
    assert out['materiality_evidence_coverage']['selected_event_id']==b['selected_event_id']
    assert all(c['selected_event_id']==b['selected_event_id'] for c in b['claims'])
    assert out['review_artifact']['trace']==p['trace'] and not out['eligible_for_handoff']
    assert parse_response(p,r,reply(d),NOW)==out


@pytest.mark.parametrize('bad',['empty_name','empty_evidence','fake_ticker','metadata','duplicate','unknown_named',
    'unknown_evidence','issuer_no_symbol','direct_organization','direct_other','read_target','read_unknown',
    'fact_role','publication_role','unknown_event_fact','legacy_symbol','subject_extra'])
def test_inconsistent_or_uncited_subjects_fail_closed(subject_case,bad):
    p,r=subject_case;d=organization(draft_for(p));e=d['selected_event'];s=e['subject']
    if bad=='empty_name':s['name']=' '
    if bad=='empty_evidence':s['evidence']=[]
    if bad=='fake_ticker':s['symbol']='BOJ'
    if bad=='metadata':s['evidence']=[dict(excerpt_id=next(k for k,v in selectable_catalog(p).items() if v['category']=='PUBLICATION_METADATA'))]
    if bad=='duplicate':s['evidence']*=2
    if bad=='unknown_named':s['kind']='UNKNOWN'
    if bad=='unknown_evidence':s.update(kind='UNKNOWN',name=None)
    if bad=='issuer_no_symbol':s['kind']='ISSUER'
    if bad=='direct_organization':e['relationship']='DIRECT'
    if bad=='direct_other':e['relationship']='DIRECT';s.update(kind='ISSUER',symbol='OTHER')
    if bad=='read_target':s.update(kind='ISSUER',symbol=p['symbol'])
    if bad=='read_unknown':s.update(kind='UNKNOWN',name=None,evidence=[])
    if bad=='fact_role':d['facts'][1]['subject_role']='TARGET'
    if bad=='publication_role':d['facts'][3]['subject_role']='EVENT'
    if bad=='unknown_event_fact':s.update(kind='UNKNOWN',name=None,evidence=[]);e.update(relationship='UNRESOLVED',target_link='UNRESOLVED')
    if bad=='legacy_symbol':e['subject_symbol']='BOJ'
    if bad=='subject_extra':s['approved']=True
    with pytest.raises(ValueError):parse_response(p,r,reply(d),NOW)


def test_unknown_subject_preserves_abstention(subject_case):
    p,r=subject_case;d=draft_for(p);e=d['selected_event']
    e.update(subject=dict(kind='UNKNOWN',name=None,symbol=None,evidence=[]),relationship='UNRESOLVED',target_link='UNRESOLVED')
    for f in d['facts'][1:3]:f.update(status='UNRESOLVED',subject_role='UNRESOLVED',evidence=[])
    out=parse_response(p,r,reply(d),NOW)
    assert out['research_binding']['event_subject_id'] is None and not out['eligible_for_handoff']


@pytest.mark.parametrize('bad',['universe','materiality','sufficient','freshness','verification_failure','liquidity'])
def test_subject_representation_never_expands_strategy_eligibility(subject_case,bad):
    p,r=subject_case;d=organization(draft_for(p));d['target'].update(instrument_type='ETF',stock_universe='UNRESOLVED')
    if bad=='universe':d['target']['stock_universe']='EVIDENCED'
    if bad=='materiality':claim(d,'catalyst_materiality_tier')['evidence_state']='OBSERVED_SUPPORT'
    if bad=='sufficient':d['materiality_coverage']['status']='SUFFICIENT_FOR_RESEARCH'
    if bad=='freshness':claim(d,'catalyst_freshness')['evidence_state']='OBSERVED_SUPPORT'
    if bad=='verification_failure':claim(d,'same_event_verification')['evidence_state']='OBSERVED_FAILURE'
    if bad=='liquidity':claim(d,'liquidity')['evidence_state']='OBSERVED_SUPPORT'
    with pytest.raises(ValueError):parse_response(p,r,reply(d),NOW)


def test_etf_named_subject_can_be_recorded_without_qualification(subject_case):
    p,r=subject_case;d=organization(draft_for(p));d['target'].update(instrument_type='ETF',stock_universe='UNRESOLVED')
    out=parse_response(p,r,reply(d),NOW)
    assert all(c['assessment']=='UNRESOLVED' for c in out['review_artifact']['review']['claims'])
    assert not out['eligible_for_handoff']


def test_gap_and_followup_ids_bind_to_typed_event(subject_case):
    p,r=subject_case;d=organization(draft_for(p));c=d['materiality_coverage']
    c.update(status='INCOMPLETE',evidence_gaps=[gap()],document_followups=[dict(followup(),gap_index=0)])
    a=parse_response(p,r,reply(d),NOW);d['selected_event']['subject']['name']='Different fixture institution'
    b=parse_response(p,r,reply(d),NOW)
    for out in (a,b):
        cv=out['materiality_evidence_coverage'];assert cv['document_followups'][0]['gap_id']==cv['evidence_gaps'][0]['gap_id']
        assert cv['document_followups'][0]['authority']=='PROPOSAL_ONLY_NOT_AN_APPROVED_REQUIREMENT'
    assert a['materiality_evidence_coverage']['evidence_gaps'][0]['gap_id']!=b['materiality_evidence_coverage']['evidence_gaps'][0]['gap_id']
    assert a['research_binding']['event_subject_id']!=b['research_binding']['event_subject_id']


def test_plausible_gap_or_wrong_name_is_not_semantically_verified(subject_case):
    p,r=subject_case;d=organization(draft_for(p));d['selected_event']['subject']['name']='Unsupported fixture name'
    d['materiality_coverage'].update(status='INCOMPLETE',evidence_gaps=[dict(gap(),missing_fact='Formal approval of a reported plan')])
    out=parse_response(p,r,reply(d),NOW)
    assert out['research_binding']['semantic_verification']=='NOT_ESTABLISHED'
    assert out['materiality_evidence_coverage']['evidence_gaps'][0]['semantic_verification']=='NOT_ESTABLISHED'
    assert not out['eligible_for_handoff']


def test_optional_documents_do_not_block_issuer_research(subject_case):
    p,r=subject_case;d=draft_for(p,True);d['materiality_coverage']['document_followups']=[followup()]
    out=parse_response(p,r,reply(d),NOW)
    assert out['materiality_evidence_coverage']['status']=='SUFFICIENT_FOR_RESEARCH'


def test_lossless_schema_and_input_limits(subject_case,masters):
    p,r=subject_case;s=r['body']['text']['format']['schema'];catalog=selectable_catalog(p)
    assert all(catalog[k]['category'] in {'NEWS_TEXT','DOCUMENT_TEXT'} for k in s['$defs']['SubstantiveRef']['properties']['excerpt_id']['enum'])
    view=json.loads(r['body']['input'][-1]['content'].split('\n',1)[1])['packet']
    for source in view['sources']:source['raw']=json.loads(source['text'])
    assert view==p
    manifest=json.loads(r['body']['input'][0]['content'].split('GOVERNING_MASTERS:\n',1)[1].split('\nCRITERION_REFERENCES:',1)[0])
    assert all(manifest[k]['text']==v['text'] for k,v in masters.items())
    size=len(canonical(r['body']).encode());assert prepare_subject_request(p,masters,'offline-fixture',12000,size,NOW)==r
    with pytest.raises(ReviewBlocked,match='INPUT_LIMIT_EXCEEDED'):prepare_subject_request(p,masters,'offline-fixture',12000,size-1,NOW)


@pytest.mark.parametrize('count',[0,500,1001])
def test_typed_subject_schema_budget_rejects_without_truncation(subject_case,monkeypatch,count):
    import research_subjects as module
    p,_=subject_case;catalog={'E'+str(i).zfill(20):dict(category='DOCUMENT_TEXT') for i in range(count)}
    monkeypatch.setattr(module,'selectable_catalog',lambda p:catalog)
    with pytest.raises(ReviewBlocked):subject_schema(p)
    assert len(catalog)==count


@pytest.mark.parametrize('tamper',['schema','evidence','format'])
def test_prebilling_tampering_rejected(subject_case,tamper):
    p,r=subject_case;r=deepcopy(r)
    if tamper=='schema':r['body']['text']['format']['schema']['$defs']['EventSubject']['properties']['kind']['enum'].append('FAKE')
    if tamper=='evidence':r['body']['input'][-1]['content']+='changed'
    if tamper=='format':r['body']['text']['format']['strict']=False
    r['request_id']=digest(dict(version=VERSIONS[0],prompt_version=VERSIONS[1],body=r['body']))
    class Forbidden:
        def respond(self,body):raise AssertionError('No network')
    ledger=AttemptLedger(ledger_path(),1)
    try:
        with pytest.raises(ReviewBlocked):execute_once(ledger,p,r,Forbidden(),lambda:NOW)
        assert ledger.db.execute('select count(*) from requests').fetchone()[0]==0
    finally:ledger.close()


def test_durable_replay_and_original_v9_rejection(subject_case,masters):
    p,r=subject_case;old=old_draft(p);old['selected_event'].update(subject_symbol=None,relationship='READ_THROUGH')
    old_req=prepare_gap_request(p,masters,'offline-fixture',12000,250000,NOW)
    with pytest.raises(ReviewBlocked,match='READ_THROUGH_SUBJECT_REQUIRED'):parse_response(p,old_req,reply(old),NOW)
    response=reply(organization(draft_for(p)));calls=[]
    class Provider:
        def respond(self,body):calls.append(body);return response
    path=ledger_path();ledger=AttemptLedger(path,1)
    try:out=execute_once(ledger,p,r,Provider(),lambda:NOW)
    finally:ledger.close()
    ledger=AttemptLedger(path,1)
    try:assert execute_once(ledger,p,r,Provider(),lambda:NOW)==out and len(calls)==1
    finally:ledger.close()
    assert out['review_artifact']['review']['implementation_version']==VERSIONS[0]
    with pytest.raises(ReviewBlocked,match='READ_THROUGH_SUBJECT_REQUIRED'):parse_response(p,old_req,reply(old),NOW)


def test_default_cli_prepares_without_provider(subject_case,masters,monkeypatch,capsys):
    import run_research_reviewer as cli
    assert cli.prepare_request is prepare_subject_request
    p,_=subject_case;root=ledger_path().parent;pf=root/'p.json';mf=root/'m.json'
    pf.write_text(canonical(p),encoding='utf-8');mf.write_text(canonical(masters),encoding='utf-8')
    def forbidden(*a,**k):raise AssertionError('No credential/provider access')
    monkeypatch.setattr(cli,'OpenAIReviewer',forbidden)
    monkeypatch.setattr(cli,'inspect_packet',lambda *a:dict(report_id='isolated-infrastructure',route='REVIEW_REQUIRED'))
    monkeypatch.setattr('sys.argv',['review','--packet',str(pf),'--masters',str(mf),'--model','offline-fixture',
        '--max-output-tokens','12000','--max-input-bytes','250000','--output',str(root)])
    cli.main();out=json.loads(capsys.readouterr().out)
    assert out['model_calls']==0 and not out['eligible_for_handoff']
